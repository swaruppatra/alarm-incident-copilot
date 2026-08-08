from datetime import datetime

from pydantic import BaseModel


class TimeRange(BaseModel):
    start_time: datetime
    end_time: datetime


class PaginationMeta(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int


class ErrorResponse(BaseModel):
    error: str
    detail: str
    trace_id: str | None = None