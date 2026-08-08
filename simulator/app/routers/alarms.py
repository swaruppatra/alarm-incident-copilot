import math
import sqlite3
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status

from simulator.app.auth import require_bearer_token
from simulator.app.data.db import get_db
from simulator.app.models.alarms import Alarm, AlarmListResponse
from simulator.app.models.common import PaginationMeta

router = APIRouter(prefix="/alarms", tags=["alarms"], dependencies=[Depends(require_bearer_token)])

SORTABLE_COLUMNS = {"start_time", "severity", "status", "alarm_name"}


def _row_to_alarm(row: sqlite3.Row) -> Alarm:
    """Build the Alarm model from an alarms table row.

    Args:
        row: a sqlite3.Row from the alarms table.

    Returns:
        Alarm: the alarm representation.
    """
    return Alarm(
        alarm_id=row["alarm_id"],
        asset_id=row["asset_id"],
        site=row["site"],
        alarm_name=row["alarm_name"],
        severity=row["severity"],
        status=row["status"],
        start_time=row["start_time"],
        end_time=row["end_time"],
        ack_delay_seconds=row["ack_delay_seconds"],
    )


@router.get("", response_model=AlarmListResponse)
def list_alarms(
    asset_id: str | None = Query(default=None),
    site: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    unit: str | None = Query(default=None),
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    sort_by: str = Query(default="start_time"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    db: sqlite3.Connection = Depends(get_db),
) -> AlarmListResponse:
    """List alarms filtered by asset/site/status/unit/time window, paginated.

    Args:
        asset_id: optional exact-match asset_id filter.
        site: optional exact-match site filter.
        status_filter: optional exact-match status filter.
        unit: optional exact-match unit filter (joined via assets).
        start_time: optional inclusive lower bound on start_time.
        end_time: optional inclusive upper bound on start_time.
        page: 1-indexed page number.
        page_size: number of rows per page.
        sort_by: column to sort by, must be in SORTABLE_COLUMNS.
        sort_order: "asc" or "desc".
        db: request-scoped sqlite3 connection.

    Returns:
        AlarmListResponse: the matching page of alarms plus pagination metadata.
    """
    if sort_by not in SORTABLE_COLUMNS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"sort_by must be one of {sorted(SORTABLE_COLUMNS)}",
        )

    where: list[str] = []
    params: list[object] = []
    if asset_id is not None:
        where.append("asset_id = ?")
        params.append(asset_id)
    if site is not None:
        where.append("site = ?")
        params.append(site)
    if status_filter is not None:
        where.append("status = ?")
        params.append(status_filter)
    if unit is not None:
        where.append("asset_id IN (SELECT asset_id FROM assets WHERE unit = ?)")
        params.append(unit)
    if start_time is not None:
        where.append("start_time >= ?")
        params.append(start_time.isoformat())
    if end_time is not None:
        where.append("start_time <= ?")
        params.append(end_time.isoformat())

    where_clause = f"WHERE {' AND '.join(where)}" if where else ""
    total_items = db.execute(f"SELECT COUNT(*) FROM alarms {where_clause}", params).fetchone()[0]
    total_pages = math.ceil(total_items / page_size) if total_items else 0

    order_dir = "ASC" if sort_order == "asc" else "DESC"
    offset = (page - 1) * page_size
    rows = db.execute(
        f"SELECT * FROM alarms {where_clause} ORDER BY {sort_by} {order_dir} LIMIT ? OFFSET ?",
        [*params, page_size, offset],
    ).fetchall()

    return AlarmListResponse(
        data=[_row_to_alarm(row) for row in rows],
        pagination=PaginationMeta(page=page, page_size=page_size, total_items=total_items, total_pages=total_pages),
    )


@router.get("/{alarm_id}", response_model=Alarm)
def get_alarm(alarm_id: str, db: sqlite3.Connection = Depends(get_db)) -> Alarm:
    """Fetch a single alarm by ID.

    Args:
        alarm_id: the alarm identifier, e.g. "ALM-00001".
        db: request-scoped sqlite3 connection.

    Returns:
        Alarm: the matching alarm.
    """
    row = db.execute("SELECT * FROM alarms WHERE alarm_id = ?", (alarm_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Alarm {alarm_id} not found")
    return _row_to_alarm(row)
