import sqlite3
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status

from simulator.app.auth import require_bearer_token
from simulator.app.data.db import get_db
from simulator.app.models.calculations import (
    CalculationFilters,
    ExecuteCalculationRequest,
    ExecuteCalculationResponse,
    GenerateCalculationRequest,
    GenerateCalculationResponse,
)
from simulator.app.tracing import (
    TraceContext,
    apply_trace_response_header,
    get_trace_context,
)

router = APIRouter(prefix="/calculation-code", tags=["calculations"], dependencies=[Depends(require_bearer_token)])

# In-memory calculation_id -> calculation_type registry; process-lifetime only,
# since db.py's schema intentionally has no calculations table.
_CALCULATIONS: dict[str, str] = {}


@router.post("/generate", response_model=GenerateCalculationResponse)
def generate_calculation(payload: GenerateCalculationRequest) -> GenerateCalculationResponse:
    """Register a new calculation_type under a freshly minted calculation_id.

    Args:
        payload: calculation_type and its filters.

    Returns:
        GenerateCalculationResponse: the new calculation_id and its calculation_type.
    """
    calculation_id = f"CALC-{uuid.uuid4().hex[:8]}"
    _CALCULATIONS[calculation_id] = payload.calculation_type
    return GenerateCalculationResponse(calculation_id=calculation_id, calculation_type=payload.calculation_type)


def _filtered_alarms(db: sqlite3.Connection, filters: CalculationFilters) -> list[sqlite3.Row]:
    """Fetch alarms joined with assets, filtered by the optional unit/time bounds.

    Args:
        db: request-scoped sqlite3 connection.
        filters: optional unit/start_time/end_time filters.

    Returns:
        list[sqlite3.Row]: matching alarm rows.
    """
    sql = "SELECT a.* FROM alarms a JOIN assets ast ON ast.asset_id = a.asset_id WHERE 1=1"
    params: list[object] = []
    if filters.unit is not None:
        sql += " AND ast.unit = ?"
        params.append(filters.unit)
    if filters.start_time is not None:
        sql += " AND a.start_time >= ?"
        params.append(filters.start_time)
    if filters.end_time is not None:
        sql += " AND a.start_time <= ?"
        params.append(filters.end_time)
    return db.execute(sql, params).fetchall()


def _compute_result(calculation_type: str, rows: list[sqlite3.Row]) -> dict:
    """Compute a calculation_type-specific result dict from filtered alarm rows.

    Args:
        calculation_type: e.g. "alarm_flood_index", "critical_alarm_density".
        rows: alarm rows matching the request's filters.

    Returns:
        dict: calculation-specific result payload.
    """
    total = len(rows)

    if calculation_type == "alarm_flood_index":
        if total == 0:
            return {"alarm_flood_index": 0.0, "alarm_count": 0}
        starts = sorted(datetime.fromisoformat(row["start_time"]) for row in rows)
        span_hours = max((starts[-1] - starts[0]).total_seconds() / 3600, 1.0)
        return {
            "alarm_flood_index": round(total / span_hours, 4),
            "alarm_count": total,
            "span_hours": round(span_hours, 2),
        }

    if calculation_type == "critical_alarm_density":
        critical = sum(1 for row in rows if row["severity"] in ("high", "critical"))
        return {
            "critical_alarm_density": round(critical / total, 4) if total else 0.0,
            "critical_count": critical,
            "alarm_count": total,
        }

    if calculation_type == "operator_response_efficiency":
        delays = [row["ack_delay_seconds"] / 60 for row in rows if row["ack_delay_seconds"] is not None]
        avg_minutes = sum(delays) / len(delays) if delays else 0.0
        return {
            "operator_response_efficiency": round(max(0.0, 100.0 - avg_minutes), 2),
            "avg_ack_delay_minutes": round(avg_minutes, 2),
            "alarm_count": total,
        }

    if calculation_type == "nuisance_alarm_score":
        counts: dict[tuple[str, str], int] = {}
        for row in rows:
            key = (row["asset_id"], row["alarm_name"])
            counts[key] = counts.get(key, 0) + 1
        recurring = sum(c - 1 for c in counts.values() if c > 1)
        return {"nuisance_alarm_score": round((recurring / total) * 100, 2) if total else 0.0, "alarm_count": total}

    return {"alarm_count": total}


@router.post("/execute", response_model=ExecuteCalculationResponse)
def execute_calculation(
    payload: ExecuteCalculationRequest,
    response: Response,
    ctx: TraceContext = Depends(get_trace_context),
    db: sqlite3.Connection = Depends(get_db),
) -> ExecuteCalculationResponse:
    """Run a previously generated calculation against alarms matching its filters.

    Args:
        payload: calculation_id and filters.
        response: outgoing response, used to echo trace_id.
        ctx: trace/correlation headers read from the request.
        db: request-scoped sqlite3 connection.

    Returns:
        ExecuteCalculationResponse: the calculation_id and its computed result.
    """
    apply_trace_response_header(response, ctx)
    calculation_type = _CALCULATIONS.get(payload.calculation_id)
    if calculation_type is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Calculation {payload.calculation_id} not found"
        )
    rows = _filtered_alarms(db, payload.filters)
    result = _compute_result(calculation_type, rows)
    return ExecuteCalculationResponse(calculation_id=payload.calculation_id, result=result)
