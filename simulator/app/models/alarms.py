from datetime import datetime

from pydantic import BaseModel

from .common import PaginationMeta

Severity = str  # "info" | "low" | "medium" | "high" | "critical"


class Alarm(BaseModel):
    alarm_id: str
    asset_id: str
    site: str
    alarm_name: str
    severity: Severity
    status: str          # "active" | "acknowledged" | "cleared"
    start_time: datetime
    end_time: datetime | None = None
    ack_delay_seconds: int | None = None


class AlarmListResponse(BaseModel):
    data: list[Alarm]
    pagination: PaginationMeta