"""Tests for call_mcp_tools_node (apps/backend/graph/nodes.py) -- the graph
node that actually *invokes* a discovered MCP tool. Complements
tests/integration/test_mcp_client.py, which covers discovery/caching in
mcp_clients.py but never calls tool.ainvoke(); this file covers the
"invocation, invalid args, missing tool, partial failure" ground that
leaves uncovered.

get_mcp_tools() is monkeypatched to return a small fake toolset (plain
objects with a .name and an async .ainvoke, not real MCP tools) --
find_tool() itself is the real function, not mocked.
"""

from langchain_core.messages import AIMessage

import apps.backend.graph.nodes as nodes_mod
from apps.backend.graph.nodes import (
    ALARM_CONTEXT_TOOLS,
    MAX_TOOL_CALLS_PER_TURN,
    call_mcp_tools_node,
)


class _FakeTool:
    """Minimal stand-in for a langchain_mcp_adapters StructuredTool -- just
    enough surface (`.name`, async `.ainvoke`) for call_mcp_tools_node to
    drive it exactly like a real one."""

    def __init__(self, name, result=None, exc: Exception | None = None):
        self.name = name
        self._result = result
        self._exc = exc
        self.calls: list[dict] = []

    async def ainvoke(self, args: dict):
        self.calls.append(args)
        if self._exc is not None:
            raise self._exc
        return self._result


def _ai_message_with_tool_calls(*calls: tuple[str, dict]) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": args, "id": f"call_{i}"} for i, (name, args) in enumerate(calls)],
    )


def _base_state(*calls: tuple[str, dict], confirmed: bool | None = None, tool_call_count: int = 0) -> dict:
    return {
        "messages": [_ai_message_with_tool_calls(*calls)],
        "mcp_trace": [],
        "tool_call_count": tool_call_count,
        "confirmed": confirmed,
    }


class TestSuccessfulInvocation:
    async def test_single_tool_call_succeeds_and_is_traced(self, monkeypatch):
        tool = _FakeTool("search_assets", result={"results": [{"asset_id": "AST-0001"}]})
        monkeypatch.setattr(nodes_mod, "get_mcp_tools", lambda: _async_return([tool]))

        state = _base_state(("search_assets", {"query": "Boiler"}))
        update = await call_mcp_tools_node(state)

        assert tool.calls == [{"query": "Boiler"}]
        assert len(update["mcp_trace"]) == 1
        assert update["mcp_trace"][0].status == "success"
        assert update["mcp_trace"][0].name == "search_assets"
        assert update["tool_call_count"] == 1
        assert len(update["messages"]) == 1
        assert "AST-0001" in update["messages"][0].content

    async def test_alarm_context_tool_updates_alarm_context(self, monkeypatch):
        assert "get_alarm_by_id" in ALARM_CONTEXT_TOOLS
        tool = _FakeTool("get_alarm_by_id", result={"alarm_id": "ALM-00001"})
        monkeypatch.setattr(nodes_mod, "get_mcp_tools", lambda: _async_return([tool]))

        state = _base_state(("get_alarm_by_id", {"alarm_id": "ALM-00001"}))
        update = await call_mcp_tools_node(state)

        assert update["alarm_context"] == {"get_alarm_by_id": {"alarm_id": "ALM-00001"}}

    async def test_non_alarm_context_tool_does_not_touch_alarm_context(self, monkeypatch):
        assert "generate_kpi_calculation" not in ALARM_CONTEXT_TOOLS
        tool = _FakeTool("generate_kpi_calculation", result={"calculation_id": "calc-1"})
        monkeypatch.setattr(nodes_mod, "get_mcp_tools", lambda: _async_return([tool]))

        state = _base_state(("generate_kpi_calculation", {"calculation_type": "x"}))
        update = await call_mcp_tools_node(state)

        assert "alarm_context" not in update

    async def test_alarm_context_is_merged_not_replaced(self, monkeypatch):
        tool = _FakeTool("get_priority_score", result={"priority_score": 80})
        monkeypatch.setattr(nodes_mod, "get_mcp_tools", lambda: _async_return([tool]))

        state = _base_state(("get_priority_score", {"alarm_id": "ALM-1"}))
        state["alarm_context"] = {"get_alarm_by_id": {"alarm_id": "ALM-1"}}
        update = await call_mcp_tools_node(state)

        assert update["alarm_context"] == {
            "get_alarm_by_id": {"alarm_id": "ALM-1"},
            "get_priority_score": {"priority_score": 80},
        }


class TestInvalidArgs:
    async def test_tool_ainvoke_raising_is_caught_and_traced_as_error(self, monkeypatch):
        tool = _FakeTool("get_asset_metadata", exc=ValueError("1 validation error: asset_id required"))
        monkeypatch.setattr(nodes_mod, "get_mcp_tools", lambda: _async_return([tool]))

        state = _base_state(("get_asset_metadata", {}))
        update = await call_mcp_tools_node(state)

        assert update["mcp_trace"][0].status == "error"
        assert update["tool_call_count"] == 1  # still counted -- the attempt happened
        assert "Tool call failed" in update["messages"][0].content
        assert "validation error" in update["messages"][0].content

    async def test_node_does_not_raise_when_the_tool_call_fails(self, monkeypatch):
        # The whole point of the try/except in call_mcp_tools_node is that a
        # bad call never crashes the graph -- it routes to error handling
        # via route_after_mcp_call instead.
        tool = _FakeTool("create_ticket", exc=RuntimeError("boom"))
        monkeypatch.setattr(nodes_mod, "get_mcp_tools", lambda: _async_return([tool]))

        state = _base_state(("create_ticket", {"req": {}}), confirmed=True)
        update = await call_mcp_tools_node(state)  # must not raise
        assert update["mcp_trace"][0].status == "error"


class TestMissingTool:
    async def test_unknown_tool_name_produces_error_trace_and_message(self, monkeypatch):
        monkeypatch.setattr(nodes_mod, "get_mcp_tools", lambda: _async_return([]))

        state = _base_state(("nonexistent_tool", {}))
        update = await call_mcp_tools_node(state)

        assert update["mcp_trace"][0].status == "error"
        assert update["mcp_trace"][0].name == "nonexistent_tool"
        assert "not available" in update["messages"][0].content

    async def test_missing_tool_does_not_increment_tool_call_count(self, monkeypatch):
        # Unlike a real (attempted-and-failed) invocation, a missing tool
        # never actually calls anything -- the attempt budget shouldn't
        # be spent on a lookup miss.
        monkeypatch.setattr(nodes_mod, "get_mcp_tools", lambda: _async_return([]))

        state = _base_state(("nonexistent_tool", {}), tool_call_count=2)
        update = await call_mcp_tools_node(state)

        assert update["tool_call_count"] == 2


class TestPartialFailureMidChain:
    async def test_first_call_succeeds_second_call_fails_stops_after_the_failure(self, monkeypatch):
        good = _FakeTool("search_assets", result={"results": []})
        bad = _FakeTool("get_alarms", exc=RuntimeError("upstream unavailable"))
        monkeypatch.setattr(nodes_mod, "get_mcp_tools", lambda: _async_return([good, bad]))

        state = _base_state(("search_assets", {"query": "x"}), ("get_alarms", {"site": "EastRefinery"}))
        update = await call_mcp_tools_node(state)

        assert len(update["mcp_trace"]) == 2
        assert update["mcp_trace"][0].status == "success"
        assert update["mcp_trace"][1].status == "error"
        assert len(update["messages"]) == 2  # both calls got a ToolMessage response
        assert update["tool_call_count"] == 2

    async def test_first_call_missing_tool_stops_before_the_second_ever_runs(self, monkeypatch):
        second = _FakeTool("get_alarms", result={"data": []})
        monkeypatch.setattr(nodes_mod, "get_mcp_tools", lambda: _async_return([second]))  # "search_assets" absent

        state = _base_state(("search_assets", {"query": "x"}), ("get_alarms", {"site": "EastRefinery"}))
        update = await call_mcp_tools_node(state)

        assert len(update["mcp_trace"]) == 1
        assert update["mcp_trace"][0].name == "search_assets"
        assert update["mcp_trace"][0].status == "error"
        assert second.calls == []  # never reached


class TestWriteToolGate:
    async def test_unconfirmed_write_tool_sets_pending_write_and_stops(self, monkeypatch):
        tool = _FakeTool("create_ticket", result={"ticket_id": "TKT-1"})
        monkeypatch.setattr(nodes_mod, "get_mcp_tools", lambda: _async_return([tool]))

        state = _base_state(("create_ticket", {"req": {"summary": "x"}}), confirmed=False)
        update = await call_mcp_tools_node(state)

        assert update["pending_write"]["name"] == "create_ticket"
        assert tool.calls == []  # never actually invoked
        assert "Awaiting user confirmation" in update["messages"][0].content

    async def test_confirmed_write_tool_is_invoked_normally(self, monkeypatch):
        tool = _FakeTool("create_ticket", result={"ticket_id": "TKT-1"})
        monkeypatch.setattr(nodes_mod, "get_mcp_tools", lambda: _async_return([tool]))

        state = _base_state(("create_ticket", {"req": {"summary": "x"}}), confirmed=True)
        update = await call_mcp_tools_node(state)

        assert tool.calls == [{"req": {"summary": "x"}}]
        assert "pending_write" not in update


class TestToolCallLimit:
    async def test_limit_already_reached_skips_invocation_entirely(self, monkeypatch):
        tool = _FakeTool("search_assets", result={"results": []})
        monkeypatch.setattr(nodes_mod, "get_mcp_tools", lambda: _async_return([tool]))

        state = _base_state(("search_assets", {"query": "x"}), tool_call_count=MAX_TOOL_CALLS_PER_TURN)
        update = await call_mcp_tools_node(state)

        assert tool.calls == []
        assert "limit reached" in update["messages"][0].content
        assert update["tool_call_count"] == MAX_TOOL_CALLS_PER_TURN  # unchanged


async def _async_return(value):
    return value
