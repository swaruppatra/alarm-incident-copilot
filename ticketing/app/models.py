from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from simulator.app.models.common import PaginationMeta

TicketStatus = Literal["open", "in_progress", "resolved", "closed"]


class Ticket(BaseModel):
    ticket_id: str
    summary: str
    description: str
    status: TicketStatus
    labels: list[str]
    asset_id: str | None = None
    alarm_id: str | None = None
    priority: str | None = None
    created_at: datetime
    updated_at: datetime
    resolution_notes: str | None = None


class TicketCreateRequest(BaseModel):
    summary: str
    description: str
    status: TicketStatus = "open"
    labels: list[str] = []
    asset_id: str | None = None
    alarm_id: str | None = None
    priority: str | None = None


class TicketUpdateRequest(BaseModel):
    status: TicketStatus | None = None
    resolution_notes: str | None = None
    labels: list[str] | None = None
    priority: str | None = None


class TicketSearchResponse(BaseModel):
    results: list[Ticket]


class TicketListResponse(BaseModel):
    data: list[Ticket]
    pagination: PaginationMeta
