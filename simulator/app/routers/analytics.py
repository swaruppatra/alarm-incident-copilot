import sqlite3
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status

from simulator.app.auth import require_bearer_token
from simulator.app.data.db import get_db
from simulator.app.models.analytics import (
    AlarmCorrelationRequest,
    AlarmCorrelationResponse,
    AlarmSummaryRequest,
    AlarmSummaryResponse,
    AlarmTrendsRequest,
    AlarmTrendsResponse,
    CorrelatedPair,
    FloodAnalysisRequest,
    FloodAnalysisResponse,
    FloodEpisode,
    KPIDefinition,
    KPIDefinitionsResponse,
    PriorityScoreRequest,
    PriorityScoreResponse,
    RationalizationCandidate,
    RationalizationCandidatesRequest,
    RationalizationCandidatesResponse,
    SummaryGroup,
    TrendPoint,
)
from simulator.app.models.common import TimeRange
from simulator.app.tracing import (
    TraceContext,
    apply_trace_response_header,
    get_trace_context,
)

router = APIRouter(tags=["analytics"], dependencies=[Depends(require_bearer_token)])

GROUP_COLUMNS = {"alarm_name", "asset_id", "severity", "status", "site", "asset_name"}
SEVERITY_RANK = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
CRITICALITY_SCORE = {"low": 10.0, "medium": 40.0, "high": 70.0, "critical": 100.0}
SEVERITY_SCORE = {"info": 10.0, "low": 30.0, "medium": 50.0, "high": 75.0, "critical": 100.0}
# An (asset_id, alarm_name) pair recurring at least this often within the
# request's window is treated as a nuisance/suppression candidate.
NUISANCE_OCCURRENCE_THRESHOLD = 3


def _resolve_asset_ids(
    db: sqlite3.Connection, asset_ids: list[str] | None, site: str | None, unit: str | None
) -> list[str]:
    """Resolve the effective asset_id scope from explicit IDs or site/unit filters.

    Args:
        db: request-scoped sqlite3 connection.
        asset_ids: explicit asset_ids, used as-is when given.
        site: optional site filter, used to resolve asset_ids when absent.
        unit: optional unit filter, used to resolve asset_ids when absent.

    Returns:
        list[str]: the asset_ids to scope the query to.
    """
    if asset_ids:
        return asset_ids
    where: list[str] = []
    params: list[object] = []
    if site is not None:
        where.append("site = ?")
        params.append(site)
    if unit is not None:
        where.append("unit = ?")
        params.append(unit)
    where_clause = f"WHERE {' AND '.join(where)}" if where else ""
    rows = db.execute(f"SELECT asset_id FROM assets {where_clause}", params).fetchall()
    return [row["asset_id"] for row in rows]


def _fetch_alarms(
    db: sqlite3.Connection, asset_ids: list[str], time_range: TimeRange, severity: list[str] | None
) -> list[sqlite3.Row]:
    """Fetch alarms (joined with asset_name) filtered by asset_ids/time/severity.

    Args:
        db: request-scoped sqlite3 connection.
        asset_ids: assets to include.
        time_range: inclusive start/end bounds on start_time.
        severity: optional allow-list of severities.

    Returns:
        list[sqlite3.Row]: matching alarm rows, each carrying an asset_name column.
    """
    if not asset_ids:
        return []
    placeholders = ",".join("?" for _ in asset_ids)
    sql = f"""
        SELECT a.*, ast.asset_name AS asset_name
        FROM alarms a JOIN assets ast ON ast.asset_id = a.asset_id
        WHERE a.asset_id IN ({placeholders}) AND a.start_time >= ? AND a.start_time <= ?
    """
    params: list[object] = [*asset_ids, time_range.start_time.isoformat(), time_range.end_time.isoformat()]
    if severity:
        sql += f" AND a.severity IN ({','.join('?' for _ in severity)})"
        params += severity
    return db.execute(sql, params).fetchall()


def _group_key(row: sqlite3.Row, group_by: list[str] | None) -> str:
    """Build the group_key string for a row given the requested group_by columns.

    Args:
        row: an alarm row (with asset_name joined in).
        group_by: columns to group by, or None/empty for a single "all" group.

    Returns:
        str: the "|"-joined group key.
    """
    if not group_by:
        return "all"
    return "|".join(str(row[col]) for col in group_by)


def _compute_kpi_values(rows: list[sqlite3.Row], kpis: list[str]) -> dict[str, float]:
    """Compute the requested KPI values from a set of alarm rows.

    Args:
        rows: alarm rows belonging to one group.
        kpis: KPI names to compute ("alarm_count", "recurring_rate", "avg_ack_delay").

    Returns:
        dict[str, float]: kpi_name -> computed value.
    """
    values: dict[str, float] = {}
    for kpi in kpis:
        if kpi == "alarm_count":
            values[kpi] = float(len(rows))
        elif kpi == "recurring_rate":
            counts: dict[tuple[str, str], int] = {}
            for row in rows:
                key = (row["asset_id"], row["alarm_name"])
                counts[key] = counts.get(key, 0) + 1
            recurring = sum(c - 1 for c in counts.values() if c > 1)
            values[kpi] = round(recurring / len(rows), 4) if rows else 0.0
        elif kpi == "avg_ack_delay":
            delays = [row["ack_delay_seconds"] for row in rows if row["ack_delay_seconds"] is not None]
            values[kpi] = round(sum(delays) / len(delays), 2) if delays else 0.0
        elif kpi == "critical_count":
            values[kpi] = float(sum(1 for row in rows if row["severity"] == "critical"))
        elif kpi == "suppression_candidate_rate":
            counts: dict[tuple[str, str], int] = {}
            for row in rows:
                key = (row["asset_id"], row["alarm_name"])
                counts[key] = counts.get(key, 0) + 1
            nuisance = sum(1 for row in rows if counts[(row["asset_id"], row["alarm_name"])] >= NUISANCE_OCCURRENCE_THRESHOLD)
            values[kpi] = round(nuisance / len(rows), 4) if rows else 0.0
        else:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Unknown kpi '{kpi}'")
    return values


@router.post("/alarms/summary", response_model=AlarmSummaryResponse)
def alarm_summary(
    payload: AlarmSummaryRequest,
    response: Response,
    ctx: TraceContext = Depends(get_trace_context),
    db: sqlite3.Connection = Depends(get_db),
) -> AlarmSummaryResponse:
    """Group and aggregate alarms into per-group KPI values.

    Args:
        payload: asset_ids, time_range, optional severity/group_by filters, kpis to compute.
        response: outgoing response, used to echo trace_id.
        ctx: trace/correlation headers read from the request.
        db: request-scoped sqlite3 connection.

    Returns:
        AlarmSummaryResponse: one SummaryGroup per distinct group_by combination.
    """
    apply_trace_response_header(response, ctx)
    for column in payload.group_by or []:
        if column not in GROUP_COLUMNS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unsupported group_by column '{column}', must be one of {sorted(GROUP_COLUMNS)}",
            )

    # alarm_types is accepted for schema compatibility but not enforced: this
    # simulator's alarms table has no alarm_type taxonomy, only alarm_name/severity.
    asset_ids = _resolve_asset_ids(db, payload.asset_ids, payload.site, payload.unit)
    rows = _fetch_alarms(db, asset_ids, payload.time_range, payload.severity)
    groups: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        groups.setdefault(_group_key(row, payload.group_by), []).append(row)

    summary_groups = [
        SummaryGroup(group_key=key, kpi_values=_compute_kpi_values(group_rows, payload.kpis))
        for key, group_rows in groups.items()
    ]
    return AlarmSummaryResponse(groups=summary_groups, time_range=payload.time_range)


def _bucket_start(dt: datetime, bucket: str) -> str:
    """Truncate a timestamp down to its containing hourly/daily/weekly bucket.

    Args:
        dt: the alarm's start_time.
        bucket: one of "hourly", "daily", "weekly".

    Returns:
        str: ISO-formatted bucket start timestamp.
    """
    if bucket == "hourly":
        return dt.replace(minute=0, second=0, microsecond=0).isoformat()
    if bucket == "daily":
        return dt.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    monday = dt - timedelta(days=dt.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()


@router.post("/alarms/trends", response_model=AlarmTrendsResponse)
def alarm_trends(payload: AlarmTrendsRequest, db: sqlite3.Connection = Depends(get_db)) -> AlarmTrendsResponse:
    """Bucket alarms by time and compute per-bucket metric values.

    Args:
        payload: asset_ids, time_range, bucket granularity, metrics to compute.
        db: request-scoped sqlite3 connection.

    Returns:
        AlarmTrendsResponse: one TrendPoint per bucket, sorted ascending.
    """
    asset_ids = _resolve_asset_ids(db, payload.asset_ids, payload.site, payload.unit)
    rows = _fetch_alarms(db, asset_ids, payload.time_range, severity=None)
    buckets: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        key = _bucket_start(datetime.fromisoformat(row["start_time"]), payload.bucket)
        buckets.setdefault(key, []).append(row)

    points = [
        TrendPoint(bucket_start=key, metric_values=_compute_kpi_values(buckets[key], payload.metrics))
        for key in sorted(buckets)
    ]
    return AlarmTrendsResponse(points=points)


@router.post("/alarms/correlation", response_model=AlarmCorrelationResponse)
def alarm_correlation(
    payload: AlarmCorrelationRequest,
    response: Response,
    ctx: TraceContext = Depends(get_trace_context),
    db: sqlite3.Connection = Depends(get_db),
) -> AlarmCorrelationResponse:
    """Find alarm-name pairs that co-occur within a lag window (earlier -> later).

    Args:
        payload: asset_ids, time_range, lag_window_minutes, severity_threshold, min_support.
        response: outgoing response, used to echo trace_id.
        ctx: trace/correlation headers read from the request.
        db: request-scoped sqlite3 connection.

    Returns:
        AlarmCorrelationResponse: co-occurring pairs meeting min_support.
    """
    apply_trace_response_header(response, ctx)
    threshold_rank = SEVERITY_RANK.get(payload.severity_threshold, 0)
    rows = _fetch_alarms(db, payload.asset_ids, payload.time_range, severity=None)
    events = sorted(
        (row for row in rows if SEVERITY_RANK.get(row["severity"], 0) >= threshold_rank),
        key=lambda row: row["start_time"],
    )

    name_occurrences: dict[str, int] = {}
    for row in events:
        name_occurrences[row["alarm_name"]] = name_occurrences.get(row["alarm_name"], 0) + 1

    window = timedelta(minutes=payload.lag_window_minutes)
    pair_support: dict[tuple[str, str], int] = {}
    for i, earlier in enumerate(events):
        earlier_start = datetime.fromisoformat(earlier["start_time"])
        for later in events[i + 1 :]:
            later_start = datetime.fromisoformat(later["start_time"])
            delta = later_start - earlier_start
            if delta > window:
                break
            if earlier["alarm_name"] == later["alarm_name"]:
                continue
            key = (earlier["alarm_name"], later["alarm_name"])
            pair_support[key] = pair_support.get(key, 0) + 1

    pairs = [
        CorrelatedPair(
            alarm_name_a=name_a,
            alarm_name_b=name_b,
            support=support,
            confidence=round(support / name_occurrences[name_a], 4),
        )
        for (name_a, name_b), support in pair_support.items()
        if support >= payload.min_support
    ]
    return AlarmCorrelationResponse(pairs=pairs)


@router.post("/alarms/flood-analysis", response_model=FloodAnalysisResponse)
def flood_analysis(payload: FloodAnalysisRequest, db: sqlite3.Connection = Depends(get_db)) -> FloodAnalysisResponse:
    """Detect rolling-window bursts of alarms on a unit's assets.

    Args:
        payload: unit, time_range, threshold_count, rolling_window_minutes.
        db: request-scoped sqlite3 connection.

    Returns:
        FloodAnalysisResponse: non-overlapping episodes meeting threshold_count.
    """
    rows = db.execute(
        """SELECT a.* FROM alarms a JOIN assets ast ON ast.asset_id = a.asset_id
           WHERE ast.unit = ? AND a.start_time >= ? AND a.start_time <= ?
           ORDER BY a.start_time ASC""",
        (payload.unit, payload.time_range.start_time.isoformat(), payload.time_range.end_time.isoformat()),
    ).fetchall()

    window = timedelta(minutes=payload.rolling_window_minutes)
    episodes: list[FloodEpisode] = []
    i, n = 0, len(rows)
    while i < n:
        window_start = datetime.fromisoformat(rows[i]["start_time"])
        j = i
        while j < n and datetime.fromisoformat(rows[j]["start_time"]) - window_start <= window:
            j += 1
        window_rows = rows[i:j]
        if len(window_rows) >= payload.threshold_count:
            asset_counts: dict[str, int] = {}
            for row in window_rows:
                asset_counts[row["asset_id"]] = asset_counts.get(row["asset_id"], 0) + 1
            top_assets = sorted(asset_counts, key=lambda asset_id: asset_counts[asset_id], reverse=True)[:3]
            episodes.append(
                FloodEpisode(
                    window_start=window_rows[0]["start_time"],
                    window_end=window_rows[-1]["start_time"],
                    alarm_count=len(window_rows),
                    top_contributing_assets=top_assets,
                )
            )
            i = j
        else:
            i += 1
    return FloodAnalysisResponse(episodes=episodes)


@router.post("/alarms/rationalization-candidates", response_model=RationalizationCandidatesResponse)
def rationalization_candidates(
    payload: RationalizationCandidatesRequest, db: sqlite3.Connection = Depends(get_db)
) -> RationalizationCandidatesResponse:
    """Flag (asset, alarm_name) pairs that are recurring and/or chronically stale.

    Args:
        payload: asset_ids, time_range, recurrence_threshold, stale_minutes_threshold.
        db: request-scoped sqlite3 connection.

    Returns:
        RationalizationCandidatesResponse: pairs meeting either threshold.
    """
    asset_ids = _resolve_asset_ids(db, payload.asset_ids, payload.site, payload.unit)
    rows = _fetch_alarms(db, asset_ids, payload.time_range, severity=None)
    groups: dict[tuple[str, str], list[sqlite3.Row]] = {}
    for row in rows:
        groups.setdefault((row["asset_id"], row["alarm_name"]), []).append(row)

    candidates = []
    for (asset_id, alarm_name), group_rows in groups.items():
        occurrence_count = len(group_rows)
        delays = [row["ack_delay_seconds"] / 60 for row in group_rows if row["ack_delay_seconds"] is not None]
        avg_unacknowledged_minutes = sum(delays) / len(delays) if delays else 0.0
        is_recurring = occurrence_count >= payload.recurrence_threshold
        is_stale = avg_unacknowledged_minutes >= payload.stale_minutes_threshold
        if not is_recurring and not is_stale:
            continue
        reason = "both" if is_recurring and is_stale else ("recurring" if is_recurring else "stale")
        candidates.append(
            RationalizationCandidate(
                alarm_name=alarm_name,
                asset_id=asset_id,
                occurrence_count=occurrence_count,
                avg_unacknowledged_minutes=round(avg_unacknowledged_minutes, 2),
                reason=reason,
            )
        )
    return RationalizationCandidatesResponse(candidates=candidates)


@router.post("/alarms/priority-score", response_model=PriorityScoreResponse)
def priority_score(payload: PriorityScoreRequest, db: sqlite3.Connection = Depends(get_db)) -> PriorityScoreResponse:
    """Compute a 0-100 urgency score for a single alarm from severity/criticality/status.

    Args:
        payload: alarm_id.
        db: request-scoped sqlite3 connection.

    Returns:
        PriorityScoreResponse: the score plus its contributing factors.
    """
    alarm_row = db.execute("SELECT * FROM alarms WHERE alarm_id = ?", (payload.alarm_id,)).fetchone()
    if alarm_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Alarm {payload.alarm_id} not found")
    asset_row = db.execute("SELECT * FROM assets WHERE asset_id = ?", (alarm_row["asset_id"],)).fetchone()

    severity_factor = SEVERITY_SCORE.get(alarm_row["severity"], 0.0)
    criticality_factor = CRITICALITY_SCORE.get(asset_row["criticality"], 0.0) if asset_row else 0.0
    status_factor = {"active": 100.0, "acknowledged": 40.0, "cleared": 0.0}.get(alarm_row["status"], 0.0)

    contributing_factors = {
        "severity": severity_factor,
        "asset_criticality": criticality_factor,
        "status": status_factor,
    }
    score = round(severity_factor * 0.45 + criticality_factor * 0.25 + status_factor * 0.30, 2)
    return PriorityScoreResponse(
        alarm_id=payload.alarm_id, priority_score=score, contributing_factors=contributing_factors
    )


@router.get("/analytics/kpi-definitions", response_model=KPIDefinitionsResponse)
def kpi_definitions(db: sqlite3.Connection = Depends(get_db)) -> KPIDefinitionsResponse:
    """List all known KPI definitions.

    Args:
        db: request-scoped sqlite3 connection.

    Returns:
        KPIDefinitionsResponse: all rows from the kpi_definitions table.
    """
    rows = db.execute("SELECT * FROM kpi_definitions").fetchall()
    return KPIDefinitionsResponse(
        kpis=[KPIDefinition(kpi_name=row["kpi_name"], description=row["description"], unit=row["unit"]) for row in rows]
    )
