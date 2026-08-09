import json
import time
from typing import Literal

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.types import interrupt

from apps.backend.config import get_llm
from apps.backend.graph.state import AgentState
from apps.backend.mcp_clients import find_tool, get_mcp_tools
from apps.backend.models import IntentClassification, McpTraceEntry, SynthesizedAnswer
from apps.backend.prompt import (
    CLASSIFY_INTENT_SYSTEM_PROMPT,
    PLAN_SYSTEM_PROMPT,
    SYNTHESIZE_SYSTEM_PROMPT,
)
from rag.retrieval.models import RetrievalQuery
from rag.retrieval.retriever import retrieve
from rag.retrieval.sanity_check import wrap_chunk_for_prompt

RAG_TOOL_NAME = "search_documentation"
MAX_TOOL_CALLS_PER_TURN = 8
WRITE_TOOLS = {"create_ticket", "update_ticket"}

# Tool names whose results represent resolved alarm/asset state -- surfaced
# to synthesize_answer_node via state["alarm_context"] as a clean, structured
# summary, separate from having the LLM re-derive it from raw ToolMessage
# text on every call. Deliberately scoped to "this alarm and its asset, once
# resolved" tools, not fleet-wide analytics (get_alarm_summary/get_alarm_trends/
# get_kpi_definitions/get_rationalization_candidates/*_kpi_calculation) --
# adjust this set if synthesize_answer_node needs to ground on those too.
ALARM_CONTEXT_TOOLS = {
    "search_assets",
    "get_asset_metadata",
    "get_alarms",
    "get_alarm_by_id",
    "get_priority_score",
    "get_operator_recommendations",
    "get_alarm_correlation",
    "get_flood_analysis",
}


async def classify_intent_node(state: AgentState) -> dict:
    """Classify the user's intent from the latest message and update state["intent"].

    Args:
        state (AgentState): the graph state; state["messages"] must be non-empty.

    Returns:
        dict: partial state update, {"intent": <classified intent>}.
    """
    llm = get_llm()
    classifier = llm.with_structured_output(IntentClassification)

    query = state["messages"][-1].content
    result = await classifier.ainvoke([("system", CLASSIFY_INTENT_SYSTEM_PROMPT), ("human", query)])

    return {"intent": result.intent}


@tool(RAG_TOOL_NAME)
def search_documentation(query: str, asset_id: str | None = None, doc_type: str | None = None, top_k: int = 5) -> str:
    """Search operating procedures, troubleshooting guides, maintenance manuals,
    engineering standards, and historical resolution notes for relevant
    documentation. Use this when the user's question needs grounding in
    written guidance or historical context, not just live alarm/ticket data.
    """
    raise NotImplementedError("executed via retrieve_docs_node, not called directly")


async def plan_node(state: AgentState) -> dict:
    """Decide the next tool call (or a direct response) given the conversation so far.

    Args:
        state (AgentState): the graph state; state["messages"] must be non-empty.

    Returns:
        dict: partial state update, {"messages": [<AIMessage, possibly with tool_calls>]}.
    """
    mcp_tools = await get_mcp_tools()
    llm = get_llm()
    # parallel_tool_calls=False enforces "one tool call per turn" at the API
    # level. The system prompt alone doesn't stop the model from returning
    # multiple parallel tool_calls, and both routers below assume exactly one.
    planner = llm.bind_tools([*mcp_tools, search_documentation], parallel_tool_calls=False)

    intent = state.get("intent")
    system_prompt = f"{PLAN_SYSTEM_PROMPT}\n\nClassified intent: {intent}." if intent else PLAN_SYSTEM_PROMPT
    response = await planner.ainvoke([("system", system_prompt), *state["messages"]])

    return {"messages": [response]}


async def call_mcp_tools_node(state: AgentState) -> dict:
    """Execute the tool call(s) requested by the last planning step.

    Loops over state["messages"][-1].tool_calls, invoking each via the loaded
    MCP toolset and recording it in mcp_trace. create_ticket/update_ticket are
    gated behind explicit confirmation (state["confirmed"]): an unconfirmed
    write call is recorded as pending_write and the loop stops there instead
    of executing it, so the graph can route to a confirmation step. Any
    validation error, upstream error, or unreachable server also stops the
    loop early rather than crashing, so the graph can route to error handling.

    Args:
        state (AgentState): the graph state; state["messages"][-1] must be an
            AIMessage with tool_calls (i.e. plan_node must have run first).

    Returns:
        dict: partial state update -- new ToolMessages appended to "messages",
            "mcp_trace" extended, "tool_call_count" incremented,
            "pending_write" set if a write call is awaiting confirmation, and
            "alarm_context" extended for any successful call to a tool in
            ALARM_CONTEXT_TOOLS.
    """
    last_message = state["messages"][-1]
    tool_calls = getattr(last_message, "tool_calls", None) or []
    tools = await get_mcp_tools()

    new_messages: list[ToolMessage] = []
    new_trace: list[McpTraceEntry] = []
    tool_call_count = state.get("tool_call_count", 0)
    pending_write = None
    alarm_context_update: dict | None = None

    for tool_call in tool_calls:
        if tool_call_count >= MAX_TOOL_CALLS_PER_TURN:
            new_messages.append(
                ToolMessage(content="Per-turn tool call limit reached.", tool_call_id=tool_call["id"])
            )
            break

        if tool_call["name"] in WRITE_TOOLS and not state.get("confirmed"):
            pending_write = {"name": tool_call["name"], "args": tool_call["args"], "id": tool_call["id"]}
            break

        tool = find_tool(tools, tool_call["name"])
        if tool is None:
            new_trace.append(
                McpTraceEntry(name=tool_call["name"], args=tool_call["args"], duration=0.0, status="error", retry_count=0)
            )
            new_messages.append(
                ToolMessage(content=f"Tool '{tool_call['name']}' is not available.", tool_call_id=tool_call["id"])
            )
            break

        start = time.monotonic()
        try:
            result = await tool.ainvoke(tool_call["args"])
        except Exception as exc:  # noqa: BLE001 -- must not crash on validation/upstream/network errors
            duration = time.monotonic() - start
            tool_call_count += 1
            new_trace.append(
                McpTraceEntry(
                    name=tool_call["name"], args=tool_call["args"], duration=duration, status="error", retry_count=0
                )
            )
            new_messages.append(ToolMessage(content=f"Tool call failed: {exc}", tool_call_id=tool_call["id"]))
            break

        duration = time.monotonic() - start
        tool_call_count += 1
        new_trace.append(
            McpTraceEntry(
                name=tool_call["name"], args=tool_call["args"], duration=duration, status="success", retry_count=0
            )
        )
        new_messages.append(ToolMessage(content=str(result), tool_call_id=tool_call["id"]))

        if tool_call["name"] in ALARM_CONTEXT_TOOLS:
            alarm_context_update = {**(state.get("alarm_context") or {}), tool_call["name"]: result}

    update: dict = {
        "messages": new_messages,
        "mcp_trace": state.get("mcp_trace", []) + new_trace,
        "tool_call_count": tool_call_count,
    }
    if pending_write is not None:
        update["pending_write"] = pending_write
    if alarm_context_update is not None:
        update["alarm_context"] = alarm_context_update
    return update


async def retrieve_docs_node(state: AgentState) -> dict:
    """Execute the search_documentation tool call requested by the last planning step.

    Calls rag.retrieval.retriever.retrieve, appends results to
    retrieved_chunks/citations, and always answers with a ToolMessage so the
    tool-call/tool-response pairing plan_node's LLM expects stays valid. On
    confident=False, that message is an explicit "no relevant documentation
    found" note (never silently empty) so the next planning step doesn't
    misread silence as "retrieval wasn't attempted". Retrieved chunk content
    is wrapped via sanity_check.wrap_chunk_for_prompt before it ever reaches
    the LLM, same prompt-injection framing used everywhere else RAG output
    is shown.

    Args:
        state (AgentState): the graph state; state["messages"][-1] must be an
            AIMessage with a search_documentation tool call.

    Returns:
        dict: partial state update -- the ToolMessage appended to "messages",
            "retrieved_chunks"/"citations" extended.
    """
    tool_call = state["messages"][-1].tool_calls[0]
    args = tool_call["args"]

    try:
        result = retrieve(
            RetrievalQuery(
                query=args["query"],
                top_k=args.get("top_k", 5),
                asset_id=args.get("asset_id"),
                doc_type=args.get("doc_type"),
            )
        )
    except Exception as exc:  # noqa: BLE001 -- must not crash on a retrieval-layer failure (e.g. Qdrant unreachable)
        content = f"Documentation search failed: {exc}"
        return {"messages": [ToolMessage(content=content, tool_call_id=tool_call["id"])]}

    if not result.confident:
        content = f"No relevant documentation found. {result.message or ''}".strip()
    else:
        content = "\n\n".join(wrap_chunk_for_prompt(chunk) for chunk in result.chunks)

    return {
        "messages": [ToolMessage(content=content, tool_call_id=tool_call["id"])],
        "retrieved_chunks": state.get("retrieved_chunks", []) + result.chunks,
        "citations": state.get("citations", []) + result.citations,
    }


async def synthesize_answer_node(state: AgentState) -> dict:
    """Compose the final grounded answer from alarm_context + retrieved_chunks.

    One LLM call (structured output) combining state["alarm_context"] and
    state["retrieved_chunks"] (wrapped via sanity_check.wrap_chunk_for_prompt,
    same as retrieve_docs_node) plus the conversation so far into a grounded
    answer. If the intent warrants it, the same call also produces a
    ticket_draft for the user to review -- citations themselves are not
    regenerated here, they're already tracked in state["citations"] by
    retrieve_docs_node.

    Args:
        state (AgentState): the graph state; state["messages"] must be non-empty.

    Returns:
        dict: partial state update -- an AIMessage appended to "messages", and
            "ticket_draft" set if the model produced one.
    """
    llm = get_llm()
    synthesizer = llm.with_structured_output(SynthesizedAnswer)

    evidence_parts = []
    if state.get("alarm_context"):
        evidence_parts.append(f"Alarm context:\n{json.dumps(state['alarm_context'], indent=2, default=str)}")
    if state.get("retrieved_chunks"):
        docs = "\n\n".join(wrap_chunk_for_prompt(chunk) for chunk in state["retrieved_chunks"])
        evidence_parts.append(f"Retrieved documentation:\n{docs}")
    evidence = "\n\n".join(evidence_parts) if evidence_parts else "No alarm context or documentation was gathered."

    intent = state.get("intent")
    system_prompt = f"{SYNTHESIZE_SYSTEM_PROMPT}\n\nClassified intent: {intent}." if intent else SYNTHESIZE_SYSTEM_PROMPT
    response = await synthesizer.ainvoke([("system", system_prompt), ("system", evidence), *state["messages"]])

    update: dict = {"messages": [AIMessage(content=response.answer)]}
    if response.ticket_draft is not None:
        update["ticket_draft"] = response.ticket_draft
    return update


async def await_confirmation_node(state: AgentState) -> dict:
    """Pause the graph for GUI approval of a pending ticket write.

    Only reached when ticket_draft or pending_write is set (see
    route_after_synthesize / route_after_mcp_call). Normalizes both possible
    sources of a pending write into a single pending_write shape, then calls
    interrupt() with that payload so the GUI can render Approve/Reject
    controls. Execution pauses here (via a raised GraphInterrupt) until
    resumed with Command(resume={"approved": bool}) -- per interrupt()'s
    documented contract, this whole node re-executes from the top on resume,
    so nothing above the interrupt() call may have a side effect.

    Args:
        state (AgentState): the graph state; state["ticket_draft"] and/or
            state["pending_write"] must be set.

    Returns:
        dict: partial state update. On approval: {"confirmed": True,
            "pending_write": <normalized>} -- execute_write_node reads
            pending_write next and clears it itself. On rejection:
            {"confirmed": False, "pending_write": None, "ticket_draft": None}
            -- both are cleared here, not just left alone, so a rejected
            draft can't leave pending_write/ticket_draft stuck non-None and
            force an unrelated later turn back into this same gate.
    """
    pending = state.get("pending_write")
    if pending is None and state.get("ticket_draft") is not None:
        pending = {"name": "create_ticket", "args": {"req": state["ticket_draft"].model_dump(mode="json")}}

    decision = interrupt({"action": "confirm_write", "pending_write": pending})
    approved = bool(decision.get("approved"))

    if not approved:
        return {"confirmed": False, "pending_write": None, "ticket_draft": None}
    return {"confirmed": True, "pending_write": pending}


async def execute_write_node(state: AgentState) -> dict:
    """Execute the confirmed ticket write via the MCP toolset.

    Only reached after confirmed=True (see route_after_confirmation).
    Idempotency (a non-closed ticket for the same alarm_id is returned as-is
    rather than duplicated) is already handled by the ticketing API itself
    (ticketing/app/main.py's create_ticket), so this just executes the call
    and records it like any other MCP call -- no client-side idempotency
    logic needed here.

    Args:
        state (AgentState): the graph state; state["pending_write"] must be set.

    Returns:
        dict: partial state update -- "mcp_trace" extended with the write's
            outcome, "pending_write" and "ticket_draft" both cleared (not
            just pending_write) so a completed write can't leave ticket_draft
            stuck non-None and force the next, unrelated turn back into
            await_confirmation via route_after_synthesize.
    """
    pending = state["pending_write"]
    tools = await get_mcp_tools()
    tool_ = find_tool(tools, pending["name"])

    start = time.monotonic()
    if tool_ is None:
        status_, duration = "error", 0.0
    else:
        try:
            await tool_.ainvoke(pending["args"])
            status_ = "success"
        except Exception:  # noqa: BLE001 -- must not crash; the trace entry surfaces the failure
            status_ = "error"
        duration = time.monotonic() - start

    return {
        "mcp_trace": state.get("mcp_trace", [])
        + [McpTraceEntry(name=pending["name"], args=pending["args"], duration=duration, status=status_, retry_count=0)],
        "pending_write": None,
        "ticket_draft": None,
    }


async def respond_node(state: AgentState) -> dict:
    """Terminal node: the turn is complete.

    Deliberately a no-op. Everything the GUI needs is already in AgentState
    in its final shape by the time this runs -- answer text (messages[-1]),
    citations panel (citations), MCP trace panel (mcp_trace), and ticket
    preview (ticket_draft) -- so respond exists only as a named graph
    endpoint, not to transform anything.

    Args:
        state (AgentState): the graph state, fully populated by prior nodes.

    Returns:
        dict: {} -- no state change.
    """
    return {}


def route_after_plan(state: AgentState) -> Literal["call_mcp_tools", "retrieve_docs", "synthesize_answer"]:
    """Decide where to go after plan_node, based on what (if anything) it asked for.

    Args:
        state (AgentState): the graph state, as updated by plan_node.

    Returns:
        Literal["call_mcp_tools", "retrieve_docs", "synthesize_answer"]: "retrieve_docs"
            if the last AIMessage's tool call is search_documentation,
            "call_mcp_tools" for any other tool call, "synthesize_answer" if
            there was no tool call at all -- plan_node judged it already has
            enough information, so it's time to compose the final answer.
    """
    tool_calls = getattr(state["messages"][-1], "tool_calls", None)
    if not tool_calls:
        return "synthesize_answer"
    return "retrieve_docs" if tool_calls[0]["name"] == RAG_TOOL_NAME else "call_mcp_tools"


def route_after_mcp_call(state: AgentState) -> Literal["plan", "confirm_write", "error"]:
    """Decide where to go after call_mcp_tools, based on what it just recorded.

    Note this never returns "synthesize_answer": that decision is
    route_after_plan's job, made from the AIMessage plan_node produces. Right
    after call_mcp_tools runs, the last message is always the ToolMessage it
    just appended, which never carries tool_calls -- so on a clean run this
    always loops back to "plan" to let the LLM decide the next step
    (including deciding it's done). "confirm_write" maps to the
    await_confirmation node -- the LLM tried to call create_ticket/
    update_ticket directly as an MCP tool and it was gated.

    Args:
        state (AgentState): the graph state, as updated by call_mcp_tools.

    Returns:
        Literal["plan", "confirm_write", "error"]: "confirm_write" if a write
            call is awaiting confirmation, "error" if the last trace entry
            failed, "plan" otherwise.
    """
    if state.get("pending_write") is not None:
        return "confirm_write"

    trace = state.get("mcp_trace") or []
    if trace and trace[-1].status == "error":
        return "error"

    return "plan"


def route_after_synthesize(state: AgentState) -> Literal["await_confirmation", "respond"]:
    """Decide where to go after synthesize_answer, based on whether it produced a ticket draft.

    Args:
        state (AgentState): the graph state, as updated by synthesize_answer.

    Returns:
        Literal["await_confirmation", "respond"]: "await_confirmation" if a
            ticket_draft was produced and needs the user's approval before
            being created, "respond" otherwise.
    """
    return "await_confirmation" if state.get("ticket_draft") is not None else "respond"


def route_after_confirmation(state: AgentState) -> Literal["execute_write", "respond"]:
    """Decide where to go after await_confirmation, based on the GUI's decision.

    Args:
        state (AgentState): the graph state, as updated by await_confirmation.

    Returns:
        Literal["execute_write", "respond"]: "execute_write" if the user
            approved, "respond" directly if they rejected -- nothing is
            created on a rejection.
    """
    return "execute_write" if state.get("confirmed") else "respond"
