from typing import Literal

from pydantic import BaseModel, Field
from ticketing.app.models import TicketCreateRequest as TicketDraft

Intent = Literal["prepare_incident", "search_tickets", "summarize_alarm", "add_procedure", "general_query"]

class McpTraceEntry(BaseModel):
    name: str
    args: dict
    duration: float
    status: Literal["success", "error"]
    retry_count: int

class IntentClassification(BaseModel):
    intent: Intent = Field(..., description="The user's primary intent for this request.")


class SynthesizedAnswer(BaseModel):
    answer: str = Field(..., description="The final grounded answer to show the user.")
    ticket_draft: TicketDraft | None = Field(
        None, description="A draft ticket, only populated if the intent warranted preparing one."
    )
