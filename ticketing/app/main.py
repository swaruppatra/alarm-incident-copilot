import json
import math
import sqlite3
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Query, status

from simulator.app.models.common import PaginationMeta
from ticketing.app.auth import require_bearer_token
from ticketing.app.data.db import get_db, init_db
from ticketing.app.errors import register_exception_handlers
from ticketing.app.models import (
    Ticket,
    TicketCreateRequest,
    TicketListResponse,
    TicketSearchResponse,
    TicketUpdateRequest,
)

TICKET_AUTH = [Depends(require_bearer_token)]


def _row_to_ticket(row: sqlite3.Row) -> Ticket:
    """Build the Ticket model from a tickets table row.

    Args:
        row: a sqlite3.Row from the tickets table.

    Returns:
        Ticket: the ticket representation.
    """
    return Ticket(
        ticket_id=row["ticket_id"],
        summary=row["summary"],
        description=row["description"],
        status=row["status"],
        labels=json.loads(row["labels"]),
        asset_id=row["asset_id"],
        alarm_id=row["alarm_id"],
        priority=row["priority"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        resolution_notes=row["resolution_notes"],
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Seed the sqlite database once when the app starts.

    Args:
        app: the FastAPI application instance.

    Returns:
        AsyncIterator[None]: yields control while the app serves requests.
    """
    init_db()
    yield


app = FastAPI(title="Ticketing API Simulator", lifespan=lifespan)
register_exception_handlers(app)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Report service liveness for readiness checks and orchestration.

    Args:
        None

    Returns:
        dict[str, str]: a simple status payload.
    """
    return {"status": "ok"}


@app.get("/tickets/search", response_model=TicketSearchResponse, dependencies=TICKET_AUTH)
def search_tickets(
    query: str = Query(..., min_length=1),
    asset_id: str | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=100),
    db: sqlite3.Connection = Depends(get_db),
) -> TicketSearchResponse:
    """Keyword-match tickets by summary/description/labels, ranked by word overlap.

    Args:
        query: whitespace-separated search terms, matched case-insensitively.
        asset_id: optional hard filter applied before scoring.
        limit: maximum number of results to return.
        db: request-scoped sqlite3 connection.

    Returns:
        TicketSearchResponse: matching tickets sorted by descending word-overlap score.
    """
    sql = "SELECT * FROM tickets"
    params: list[object] = []
    if asset_id is not None:
        sql += " WHERE asset_id = ?"
        params.append(asset_id)
    rows = db.execute(sql, params).fetchall()

    words = query.lower().split()
    scored: list[tuple[int, sqlite3.Row]] = []
    for row in rows:
        haystack = f"{row['summary']} {row['description']} {' '.join(json.loads(row['labels']))}".lower()
        score = sum(1 for word in words if word in haystack)
        if score > 0:
            scored.append((score, row))
    scored.sort(key=lambda pair: pair[0], reverse=True)

    return TicketSearchResponse(results=[_row_to_ticket(row) for _, row in scored[:limit]])


@app.get("/tickets", response_model=TicketListResponse, dependencies=TICKET_AUTH)
def list_tickets(
    asset_id: list[str] | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    db: sqlite3.Connection = Depends(get_db),
) -> TicketListResponse:
    """List tickets filtered by asset_id(s)/status, paginated.

    Args:
        asset_id: optional list of asset_ids (repeated query param) to match.
        status_filter: optional exact-match status filter.
        page: 1-indexed page number.
        page_size: number of rows per page.
        db: request-scoped sqlite3 connection.

    Returns:
        TicketListResponse: the matching page of tickets plus pagination metadata.
    """
    where: list[str] = []
    params: list[object] = []
    if asset_id:
        where.append(f"asset_id IN ({','.join('?' for _ in asset_id)})")
        params.extend(asset_id)
    if status_filter is not None:
        where.append("status = ?")
        params.append(status_filter)

    where_clause = f"WHERE {' AND '.join(where)}" if where else ""
    total_items = db.execute(f"SELECT COUNT(*) FROM tickets {where_clause}", params).fetchone()[0]
    total_pages = math.ceil(total_items / page_size) if total_items else 0

    offset = (page - 1) * page_size
    rows = db.execute(
        f"SELECT * FROM tickets {where_clause} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        [*params, page_size, offset],
    ).fetchall()

    return TicketListResponse(
        data=[_row_to_ticket(row) for row in rows],
        pagination=PaginationMeta(page=page, page_size=page_size, total_items=total_items, total_pages=total_pages),
    )


@app.get("/tickets/{ticket_id}", response_model=Ticket, dependencies=TICKET_AUTH)
def get_ticket(ticket_id: str, db: sqlite3.Connection = Depends(get_db)) -> Ticket:
    """Fetch a single ticket by ID.

    Args:
        ticket_id: the ticket identifier, e.g. "TKT-0001".
        db: request-scoped sqlite3 connection.

    Returns:
        Ticket: the matching ticket.
    """
    row = db.execute("SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Ticket {ticket_id} not found")
    return _row_to_ticket(row)


@app.post("/tickets", response_model=Ticket, dependencies=TICKET_AUTH)
def create_ticket(payload: TicketCreateRequest, db: sqlite3.Connection = Depends(get_db)) -> Ticket:
    """Create a ticket, or return the existing non-closed ticket for the same alarm_id.

    Args:
        payload: the new ticket's fields.
        db: request-scoped sqlite3 connection.

    Returns:
        Ticket: the newly created ticket, or the pre-existing one for payload.alarm_id.
    """
    if payload.alarm_id is not None:
        existing = db.execute(
            "SELECT * FROM tickets WHERE alarm_id = ? AND status != 'closed' ORDER BY created_at ASC LIMIT 1",
            (payload.alarm_id,),
        ).fetchone()
        if existing is not None:
            return _row_to_ticket(existing)

    now = datetime.now().isoformat()  # noqa: DTZ005 -- naive, matches alarms table's timestamp convention
    ticket_id = f"TKT-{uuid.uuid4().hex[:8]}"
    db.execute(
        """INSERT INTO tickets
           (ticket_id, summary, description, status, labels, asset_id, alarm_id, priority,
            created_at, updated_at, resolution_notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            ticket_id,
            payload.summary,
            payload.description,
            payload.status,
            json.dumps(payload.labels),
            payload.asset_id,
            payload.alarm_id,
            payload.priority,
            now,
            now,
            None,
        ),
    )
    db.commit()
    row = db.execute("SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,)).fetchone()
    return _row_to_ticket(row)


@app.patch("/tickets/{ticket_id}", response_model=Ticket, dependencies=TICKET_AUTH)
def update_ticket(ticket_id: str, payload: TicketUpdateRequest, db: sqlite3.Connection = Depends(get_db)) -> Ticket:
    """Partially update a ticket's status/resolution_notes/labels/priority.

    Args:
        ticket_id: the ticket identifier to update.
        payload: fields to overwrite; only fields explicitly set are applied.
        db: request-scoped sqlite3 connection.

    Returns:
        Ticket: the updated ticket.
    """
    row = db.execute("SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Ticket {ticket_id} not found")

    updates = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not updates:
        return _row_to_ticket(row)

    updates["updated_at"] = datetime.now().isoformat()  # noqa: DTZ005
    if "labels" in updates:
        updates["labels"] = json.dumps(updates["labels"])

    set_clause = ", ".join(f"{key} = ?" for key in updates)
    db.execute(f"UPDATE tickets SET {set_clause} WHERE ticket_id = ?", [*updates.values(), ticket_id])
    db.commit()

    updated_row = db.execute("SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,)).fetchone()
    return _row_to_ticket(updated_row)
