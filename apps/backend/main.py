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
from langchain_core.messages import AIMessage, HumanMessage
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
    edited_args: dict | None = Field(
        None, description="User-edited args to write with instead of the original draft's, if any."
    )


class ChatResponse(BaseModel):
    thread_id: str
    answer: str | None = Field(None, description="The grounded answer, when the turn completed without pausing.")
    requires_confirmation: bool = Field(False, description="True if the graph paused awaiting write approval.")
    pending_write: dict | None = Field(None, description="The tool name/args awaiting approval, when paused.")
    ticket_draft: dict | None = Field(None, description="The drafted ticket, when the turn produced one.")
    citations: list[dict] = Field(default_factory=list, description="RAG citations for this turn's answer.")
    mcp_trace: list[dict] = Field(default_factory=list, description="MCP tool calls made this turn.")


class HistoryMessage(BaseModel):
    role: str = Field(..., description="'user' or 'assistant'.")
    content: str


class HistoryResponse(BaseModel):
    thread_id: str
    messages: list[HistoryMessage] = Field(default_factory=list, description="The thread's chat turns so far.")
    requires_confirmation: bool = Field(False, description="True if the graph is currently paused awaiting write approval.")
    pending_write: dict | None = Field(None, description="The tool name/args awaiting approval, when paused.")
    citations: list[dict] = Field(default_factory=list, description="RAG citations accumulated across the thread.")
    mcp_trace: list[dict] = Field(default_factory=list, description="MCP tool calls made across the thread.")


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


def _pending_write_from_snapshot(snapshot) -> dict | None:
    """Find the pending write a paused thread is currently waiting on.

    state["pending_write"] is only reliably set once call_mcp_tools_node
    gates a raw tool call -- for the more common synthesize_answer_node ->
    ticket_draft path, await_confirmation_node builds the pending write
    locally and passes it straight to interrupt() without ever writing it to
    state (interrupt() pauses before that node's return value is applied).
    So state is checked first, then the paused interrupt's own payload.

    Args:
        snapshot: the thread's current StateSnapshot, from graph.aget_state().

    Returns:
        dict | None: the pending write's {"name", "args", ...}, or None if
            there isn't one.
    """
    pending_write = (snapshot.values or {}).get("pending_write")
    if pending_write is not None:
        return pending_write
    for interrupt_ in snapshot.interrupts:
        payload = interrupt_.value or {}
        if isinstance(payload, dict) and "pending_write" in payload:
            return payload["pending_write"]
    return None


@app.get("/history/{thread_id}", response_model=HistoryResponse)
async def history(thread_id: str) -> HistoryResponse:
    """Reconstruct a thread's visible chat history and current state.

    Lets the GUI restore a conversation after losing its own in-browser
    state (e.g. a WebSocket reconnect resets gr.State) without losing the
    thread's actual context, which is still sitting in the checkpointer.
    ToolMessages and content-less AIMessages (tool-call-only planning steps)
    are skipped. Consecutive assistant messages within one turn are collapsed
    to the last one -- plan_node's final "no more tools needed" response can
    itself carry answer text alongside synthesize_answer_node's, and /chat's
    own ChatResponse.answer already only ever surfaces messages[-1]; without
    collapsing, a resumed thread would show every answer duplicated.

    Args:
        thread_id (str): the conversation thread id.

    Returns:
        HistoryResponse: chat turns, citations/mcp_trace accumulated so far,
            and whether a write confirmation is currently pending. Every
            field is empty/False for a thread_id with no prior state.
    """
    snapshot = await graph.aget_state(_config(thread_id))
    if not snapshot or not snapshot.values:
        return HistoryResponse(thread_id=thread_id)

    messages: list[HistoryMessage] = []
    for msg in snapshot.values.get("messages", []):
        if isinstance(msg, HumanMessage) and msg.content:
            messages.append(HistoryMessage(role="user", content=msg.content))
        elif isinstance(msg, AIMessage) and msg.content:
            if messages and messages[-1].role == "assistant":
                messages[-1] = HistoryMessage(role="assistant", content=msg.content)
            else:
                messages.append(HistoryMessage(role="assistant", content=msg.content))

    requires_confirmation = bool(snapshot.next)
    pending_write = _pending_write_from_snapshot(snapshot) if requires_confirmation else None
    if requires_confirmation:
        # Replaces, not appends: synthesize_answer_node's own answer text
        # (e.g. "Please confirm the details...") may have been collected
        # above alongside the ticket_draft, but ChatResponse.answer is never
        # set on the interrupt branch in the live /chat path (see
        # _to_response) -- this stays consistent with what a live session
        # actually showed for this turn.
        tool_name = (pending_write or {}).get("name", "a write")
        canned = HistoryMessage(
            role="assistant",
            content=f"This turn needs approval before I run `{tool_name}`. Review the draft on the right, then Approve or Reject.",
        )
        if messages and messages[-1].role == "assistant":
            messages[-1] = canned
        else:
            messages.append(canned)

    return HistoryResponse(
        thread_id=thread_id,
        messages=messages,
        requires_confirmation=requires_confirmation,
        pending_write=pending_write,
        citations=[c.model_dump(mode="json") for c in snapshot.values.get("citations", [])],
        mcp_trace=[t.model_dump(mode="json") for t in snapshot.values.get("mcp_trace", [])],
    )


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
        req (ConfirmRequest): the thread id, the user's approve/reject
            decision, and optional edited_args to write instead of the
            original draft's.

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

    pending_write = _pending_write_from_snapshot(snapshot)
    audit.log_confirmation(req.thread_id, pending_write, req.approved, PROMPT_VERSION)

    before = await _mcp_trace_len(req.thread_id)
    result = await graph.ainvoke(
        Command(resume={"approved": req.approved, "edited_args": req.edited_args}), config=config
    )
    audit.log_mcp_trace(req.thread_id, result.get("mcp_trace", [])[before:], PROMPT_VERSION)

    return _to_response(req.thread_id, result)
