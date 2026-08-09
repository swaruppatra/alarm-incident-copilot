"""Integration tests for apps/backend/mcp_clients.py -- the backend-side
MultiServerMCPClient wrapper that both alarm-management and ticketing tools
get loaded through. Covers the two things worth testing here: the
process-wide cache (get_mcp_tools should only ever call
MultiServerMCPClient.get_tools() once, even under concurrent callers) and
find_tool's lookup.

MultiServerMCPClient itself is mocked -- these tests never make a real MCP
connection, they verify mcp_clients.py wires it up correctly (server config,
handle_tool_errors=False) and caches correctly.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

import apps.backend.mcp_clients as mcp_clients_mod
from apps.backend.config import Settings
from apps.backend.mcp_clients import find_tool, get_mcp_tools


def _fake_settings() -> Settings:
    return Settings(
        LLM_API_KEY="test-key",
        MCP_SERVER_URL="http://alarm-mcp.test:9000",
        TICKETING_MCP_SERVER_URL="http://ticketing-mcp.test:9100",
    )


def _fake_tool(name: str) -> MagicMock:
    tool = MagicMock()
    tool.name = name
    return tool


@pytest.fixture(autouse=True)
def reset_cache(monkeypatch):
    """The module-level cache is process-wide by design (that's the point
    of it) -- reset it before/after every test so tests don't leak state
    into each other."""
    monkeypatch.setattr(mcp_clients_mod, "_mcp_tools_cache", None)
    yield
    monkeypatch.setattr(mcp_clients_mod, "_mcp_tools_cache", None)


class TestGetMcpTools:
    async def test_returns_tools_from_get_tools(self, monkeypatch):
        expected_tools = [_fake_tool("search_assets"), _fake_tool("get_ticket")]
        mock_client_instance = MagicMock()
        mock_client_instance.get_tools = AsyncMock(return_value=expected_tools)
        mock_client_cls = MagicMock(return_value=mock_client_instance)

        monkeypatch.setattr(mcp_clients_mod, "MultiServerMCPClient", mock_client_cls)
        monkeypatch.setattr(mcp_clients_mod, "get_settings", _fake_settings)

        tools = await get_mcp_tools()
        assert tools == expected_tools

    async def test_server_config_and_handle_tool_errors_are_wired_correctly(self, monkeypatch):
        mock_client_instance = MagicMock()
        mock_client_instance.get_tools = AsyncMock(return_value=[])
        mock_client_cls = MagicMock(return_value=mock_client_instance)

        monkeypatch.setattr(mcp_clients_mod, "MultiServerMCPClient", mock_client_cls)
        monkeypatch.setattr(mcp_clients_mod, "get_settings", _fake_settings)

        await get_mcp_tools()

        assert mock_client_cls.call_count == 1
        (server_config,), kwargs = mock_client_cls.call_args
        assert server_config == {
            "alarm-management": {"url": "http://alarm-mcp.test:9000/mcp", "transport": "streamable_http"},
            "ticketing": {"url": "http://ticketing-mcp.test:9100/mcp", "transport": "streamable_http"},
        }
        # False so an is_error=True MCP result raises instead of being
        # silently recorded as a successful tool call -- see the comment
        # in mcp_clients.py. A regression here would be a silent
        # error-swallowing bug in production, so it's worth pinning down.
        assert kwargs["handle_tool_errors"] is False

    async def test_second_call_is_served_from_cache_not_a_new_mcp_round_trip(self, monkeypatch):
        expected_tools = [_fake_tool("search_assets")]
        mock_client_instance = MagicMock()
        mock_client_instance.get_tools = AsyncMock(return_value=expected_tools)
        mock_client_cls = MagicMock(return_value=mock_client_instance)

        monkeypatch.setattr(mcp_clients_mod, "MultiServerMCPClient", mock_client_cls)
        monkeypatch.setattr(mcp_clients_mod, "get_settings", _fake_settings)

        first = await get_mcp_tools()
        second = await get_mcp_tools()

        assert first is second
        assert mock_client_cls.call_count == 1  # MultiServerMCPClient constructed only once
        mock_client_instance.get_tools.assert_awaited_once()

    async def test_concurrent_callers_still_only_trigger_one_real_load(self, monkeypatch):
        import asyncio

        call_count = 0

        async def slow_get_tools():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.05)
            return [_fake_tool("search_assets")]

        mock_client_instance = MagicMock()
        mock_client_instance.get_tools = slow_get_tools
        mock_client_cls = MagicMock(return_value=mock_client_instance)

        monkeypatch.setattr(mcp_clients_mod, "MultiServerMCPClient", mock_client_cls)
        monkeypatch.setattr(mcp_clients_mod, "get_settings", _fake_settings)

        results = await asyncio.gather(*(get_mcp_tools() for _ in range(5)))

        assert call_count == 1  # the asyncio.Lock must prevent a stampede
        assert mock_client_cls.call_count == 1
        for result in results:
            assert result is results[0]


class TestFindTool:
    def test_returns_matching_tool(self):
        tools = [_fake_tool("search_assets"), _fake_tool("get_ticket"), _fake_tool("create_ticket")]
        found = find_tool(tools, "get_ticket")
        assert found is tools[1]

    def test_returns_none_for_missing_tool(self):
        tools = [_fake_tool("search_assets")]
        assert find_tool(tools, "nonexistent_tool") is None

    def test_empty_tools_list_returns_none(self):
        assert find_tool([], "search_assets") is None

    def test_returns_first_match_if_names_somehow_collide(self):
        first, second = _fake_tool("dup"), _fake_tool("dup")
        assert find_tool([first, second], "dup") is first
