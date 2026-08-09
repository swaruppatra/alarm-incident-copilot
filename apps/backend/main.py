"""FastAPI shell around the LangGraph copilot graph. Docker Compose already
commits to this being a separate service (copilot-backend, port 8080) called
over HTTP by the Gradio frontend, so this file's only job is: turn a chat
message into a graph.ainvoke() call, turn a paused interrupt into a
requires_confirmation response the GUI can render Approve/Reject buttons
from, and turn an approval into a graph resume.

Known gap this file works around rather than fixes: AgentState's
ticket_draft/pending_write fields are only ever set by the graph, never
cleared back to None on rejection (and ticket_draft is never cleared even on
a *successful* write) -- see the cross-check notes. /chat defensively resets
them at the start of every new turn so a stale draft from an earlier turn
can't force an unrelated later question into the confirmation gate. That's a
workaround, not the fix -- anything that invokes the graph directly (tests,
a future second frontend) would still hit the underlying bug, which belongs
in graph/nodes.py.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from pydantic import BaseModel, Field

from apps.backend import audit
from apps.backend.graph.build import graph
from apps.backend.prompt import PROMPT_VERSION


class ChatRequest(BaseModel):
    message: str = Field(..., description="The user's message.")
    thread_id: str = Field(..., description="Conversation thread id; same id across a whole conversation.")


class ConfirmRequest(BaseModel):
    thread_id: str = Field(..., description="The thread id whose pending write is being decided.")
    approved: bool = Field(..., description="True to execute the pending write, False to discard it.")


class ChatResponse(BaseModel):
    thread_id: str
    answer: str | None = Field(None, description="The grounded answer, when the turn completed without pausing.")
    requires_confirmation: bool = Field(False, description="True if the graph paused awaiting write approval.")
    pending_write: dict | None = Field(None, description="The tool name/args awaiting approval, when paused.")
    ticket_draft: dict | None = Field(None, description="The drafted ticket, when the turn produced one.")
    citations: list[dict] = Field(default_factory=list, description="RAG citations for this turn's answer.")
    mcp_trace: list[dict] = Field(default_factory=list, description="MCP tool calls made this turn.")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize the audit database once at startup.

    Args:
        app (FastAPI): the FastAPI application instance.

    Returns:
        AsyncIterator[None]: yields control while the app serves requests.
    """
    audit.init_db()
    yield


app = FastAPI(title="Incident and Ticket Enrichment Copilot", lifespan=lifespan)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Report service liveness for readiness checks and orchestration.

    Args:
        None

    Returns:
        dict[str, str]: a simple status payload.
    """
    return {"status": "ok"}


def _config(thread_id: str) -> dict:
    """Build the LangGraph config dict a given conversation thread runs under.

    Args:
        thread_id (str): the conversation thread id.

    Returns:
        dict: {"configurable": {"thread_id": thread_id}}.
    """
    return {"configurable": {"thread_id": thread_id}}


async def _mcp_trace_len(thread_id: str) -> int:
    """Read how many mcp_trace entries this thread's checkpointed state already has.

    Used to compute the "new since this call" slice for audit logging, since
    AgentState.mcp_trace accumulates across the whole conversation thread
    rather than resetting per turn.

    Args:
        thread_id (str): the conversation thread id.

    Returns:
        int: the current mcp_trace length, or 0 for a brand-new thread.
    """
    snapshot = await graph.aget_state(_config(thread_id))
    if not snapshot or not snapshot.values:
        return 0
    return len(snapshot.values.get("mcp_trace", []))


def _to_response(thread_id: str, result: dict) -> ChatResponse:
    """Map a graph.ainvoke() result to the API's ChatResponse shape.

    Args:
        thread_id (str): the conversation thread id.
        result (dict): the dict returned by graph.ainvoke(), either a normal
            completed-turn state or one containing "__interrupt__" if the
            graph paused at await_confirmation_node.

    Returns:
        ChatResponse: requires_confirmation=True with pending_write set if
            the graph paused; otherwise the completed turn's answer,
            citations, mcp_trace, and ticket_draft.
    """
    if "__interrupt__" in result:
        interrupt_payload = result["__interrupt__"][0].value
        return ChatResponse(
            thread_id=thread_id,
            requires_confirmation=True,
            pending_write=interrupt_payload.get("pending_write"),
        )

    answer = result["messages"][-1].content if result.get("messages") else None
    ticket_draft = result.get("ticket_draft")
    return ChatResponse(
        thread_id=thread_id,
        answer=answer,
        citations=[c.model_dump(mode="json") for c in result.get("citations", [])],
        mcp_trace=[t.model_dump(mode="json") for t in result.get("mcp_trace", [])],
        ticket_draft=ticket_draft.model_dump(mode="json") if ticket_draft is not None else None,
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    """Advance the conversation by one user message.

    Args:
        req (ChatRequest): the user's message and conversation thread id.

    Returns:
        ChatResponse: the resulting turn -- either a grounded answer, or
            requires_confirmation=True if a write needs approval.
    """
    config = _config(req.thread_id)
    before = await _mcp_trace_len(req.thread_id)

    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content=req.message)],
            # Defensive per-turn reset -- see this file's module docstring.
            "tool_call_count": 0,
            "confirmed": None,
            "ticket_draft": None,
            "pending_write": None,
        },
        config=config,
    )

    audit.log_mcp_trace(req.thread_id, result.get("mcp_trace", [])[before:], PROMPT_VERSION)

    return _to_response(req.thread_id, result)


@app.post("/confirm", response_model=ChatResponse)
async def confirm(req: ConfirmRequest) -> ChatResponse:
    """Resolve a pending write confirmation and resume the graph.

    Args:
        req (ConfirmRequest): the thread id and the user's approve/reject decision.

    Returns:
        ChatResponse: the completed turn after resuming -- the created
            ticket's outcome if approved, or the same answer with nothing
            written if rejected.

    Raises:
        HTTPException: 409 if this thread has no confirmation currently pending.
    """
    config = _config(req.thread_id)
    snapshot = await graph.aget_state(config)
    if not snapshot or not snapshot.next:
        raise HTTPException(status_code=409, detail="No pending confirmation for this thread_id.")

    pending_write = (snapshot.values or {}).get("pending_write")
    audit.log_confirmation(req.thread_id, pending_write, req.approved, PROMPT_VERSION)

    before = await _mcp_trace_len(req.thread_id)
    result = await graph.ainvoke(Command(resume={"approved": req.approved}), config=config)
    audit.log_mcp_trace(req.thread_id, result.get("mcp_trace", [])[before:], PROMPT_VERSION)

    return _to_response(req.thread_id, result)
