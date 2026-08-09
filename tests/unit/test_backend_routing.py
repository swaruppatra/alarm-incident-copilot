"""Unit tests for the LangGraph conditional-edge ("routing") functions in
apps/backend/graph/nodes.py -- pure functions over AgentState, no LLM/MCP/
Qdrant calls needed. This is the "tool selection" line item from the
assignment's unit test list, plus regression coverage for the two
state-hygiene bugs fixed in await_confirmation_node/execute_write_node.
"""

from langchain_core.messages import AIMessage

from apps.backend.graph.nodes import (
    route_after_confirmation,
    route_after_mcp_call,
    route_after_plan,
    route_after_synthesize,
)
from apps.backend.models import McpTraceEntry


def _ai_message_with_tool_call(name: str, args: dict | None = None) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args or {}, "id": "call_1"}])


class TestRouteAfterPlan:
    def test_no_tool_call_routes_to_synthesize(self):
        state = {"messages": [AIMessage(content="I have enough information.")]}
        assert route_after_plan(state) == "synthesize_answer"

    def test_search_documentation_call_routes_to_retrieve_docs(self):
        state = {"messages": [_ai_message_with_tool_call("search_documentation", {"query": "vibration"})]}
        assert route_after_plan(state) == "retrieve_docs"

    def test_any_other_tool_call_routes_to_call_mcp_tools(self):
        state = {"messages": [_ai_message_with_tool_call("search_assets", {"query": "Boiler"})]}
        assert route_after_plan(state) == "call_mcp_tools"

    def test_create_ticket_call_routes_to_call_mcp_tools_not_synthesize(self):
        # create_ticket is gated inside call_mcp_tools_node (WRITE_TOOLS), not
        # here -- route_after_plan shouldn't special-case it.
        state = {"messages": [_ai_message_with_tool_call("create_ticket", {"req": {}})]}
        assert route_after_plan(state) == "call_mcp_tools"


class TestRouteAfterMcpCall:
    def test_pending_write_routes_to_confirm_write(self):
        state = {"pending_write": {"name": "create_ticket", "args": {}}, "mcp_trace": []}
        assert route_after_mcp_call(state) == "confirm_write"

    def test_last_trace_error_routes_to_error(self):
        state = {
            "pending_write": None,
            "mcp_trace": [
                McpTraceEntry(name="search_assets", args={}, duration=0.1, status="success", retry_count=0),
                McpTraceEntry(name="get_alarms", args={}, duration=0.1, status="error", retry_count=0),
            ],
        }
        assert route_after_mcp_call(state) == "error"

    def test_last_trace_success_routes_to_plan(self):
        state = {
            "pending_write": None,
            "mcp_trace": [McpTraceEntry(name="search_assets", args={}, duration=0.1, status="success", retry_count=0)],
        }
        assert route_after_mcp_call(state) == "plan"

    def test_empty_trace_and_no_pending_write_routes_to_plan(self):
        # Defensive case -- shouldn't normally happen, but must not crash.
        assert route_after_mcp_call({"pending_write": None, "mcp_trace": []}) == "plan"

    def test_pending_write_takes_priority_over_a_stale_error_trace(self):
        state = {
            "pending_write": {"name": "create_ticket", "args": {}},
            "mcp_trace": [McpTraceEntry(name="get_alarms", args={}, duration=0.1, status="error", retry_count=0)],
        }
        assert route_after_mcp_call(state) == "confirm_write"


class TestRouteAfterSynthesize:
    def test_ticket_draft_set_routes_to_await_confirmation(self):
        assert route_after_synthesize({"ticket_draft": object()}) == "await_confirmation"

    def test_no_ticket_draft_routes_to_respond(self):
        assert route_after_synthesize({"ticket_draft": None}) == "respond"

    def test_missing_key_routes_to_respond(self):
        assert route_after_synthesize({}) == "respond"


class TestRouteAfterConfirmation:
    def test_confirmed_true_routes_to_execute_write(self):
        assert route_after_confirmation({"confirmed": True}) == "execute_write"

    def test_confirmed_false_routes_to_respond(self):
        assert route_after_confirmation({"confirmed": False}) == "respond"

    def test_confirmed_none_routes_to_respond(self):
        # The default value before any confirmation has happened.
        assert route_after_confirmation({"confirmed": None}) == "respond"
