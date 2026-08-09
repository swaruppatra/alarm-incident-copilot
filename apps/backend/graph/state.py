from typing import Annotated

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from apps.backend.models import McpTraceEntry
from rag.retrieval.models import Citation, RetrievedChunk
from ticketing.app.models import TicketCreateRequest as TicketDraft


class AgentState(TypedDict):
    """State of the graph, used for caching and memoization."""
    messages: Annotated[list, add_messages]
    intent: str | None                    # e.g. "prepare_incident", "search_tickets"
    alarm_context: dict | None             # resolved alarm + asset, once known
    mcp_trace: list[McpTraceEntry]           # every tool call: name, args, duration, status, retry_count
    retrieved_chunks: list[RetrievedChunk]    # from rag.retrieval.retriever
    citations: list[Citation]
    ticket_draft: TicketDraft | None
    pending_write: dict | None                # the write tool call awaiting confirmation
    tool_call_count: int                       # for the per-turn cap
    confirmed: bool | None