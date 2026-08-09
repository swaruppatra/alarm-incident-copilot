"""Integration tests for the ticketing MCP server.

Mirrors tests/integration/test_alarm_mcp_server.py's structure: FastMCP-level
tests (registration, schema validation, happy-path calls, error mapping)
with `client.request` mocked, plus TestTicketingClient exercising
TicketingClient.request directly with the underlying httpx.AsyncClient.request
mocked (auth headers, trace-id, retry/timeout/error-mapping) -- see that
file's module docstring for the layering rationale, which is identical here.

Also covers list_open_tickets_for_assets' client-side post-filtering (it's
the one tool in this server that does more than pass the response straight
through), and the write-tool (create_ticket/update_ticket) request shaping.
"""

import importlib

import httpx
import pytest
from mcp.server.fastmcp.exceptions import ToolError

ticketing_mcp = importlib.import_module("mcp-servers.ticketing.mcp")
ticketing_errors = importlib.import_module("mcp-servers.ticketing.errors")
ticketing_client_mod = importlib.import_module("mcp-servers.ticketing.client")

UpstreamError = ticketing_errors.UpstreamError
TicketingClient = ticketing_client_mod.TicketingClient

EXPECTED_TOOL_NAMES = {
    "search_similar_tickets",
    "list_open_tickets_for_assets",
    "get_ticket",
    "create_ticket",
    "update_ticket",
}


def _ticket(ticket_id: str, status: str = "open", **overrides) -> dict:
    base = {
        "ticket_id": ticket_id,
        "summary": "High vibration on BFP-101",
        "description": "Recurring vibration alarm",
        "status": status,
        "labels": ["vibration"],
        "asset_id": "AST-0001",
        "alarm_id": "ALM-00042",
        "priority": "high",
        "created_at": "2026-08-01T00:00:00Z",
        "updated_at": "2026-08-01T00:00:00Z",
        "resolution_notes": None,
    }
    base.update(overrides)
    return base


@pytest.fixture(autouse=True)
def restore_client_request():
    original = ticketing_mcp.client.request
    yield
    ticketing_mcp.client.request = original


class TestToolRegistration:
    async def test_all_expected_tools_are_registered(self):
        tools = await ticketing_mcp.mcp.list_tools()
        assert {t.name for t in tools} == EXPECTED_TOOL_NAMES

    async def test_write_tools_mention_confirmation_in_their_description(self):
        # create_ticket/update_ticket descriptions are the only signal the
        # planning LLM gets that these are gated write operations -- a
        # regression here (description edited, "confirm" wording dropped)
        # would silently defeat the human-in-the-loop safeguard upstream.
        tools = {t.name: t for t in await ticketing_mcp.mcp.list_tools()}
        assert "confirm" in tools["create_ticket"].description.lower()
        assert "confirm" in tools["update_ticket"].description.lower()


class TestToolCalls:
    async def test_search_similar_tickets_happy_path(self):
        async def fake_request(method, path, **kwargs):
            assert method == "GET"
            assert path == "/tickets/search"
            assert kwargs["params"] == {"query": "vibration", "limit": 10}
            return {"results": [_ticket("TKT-0001")]}

        ticketing_mcp.client.request = fake_request
        _unstructured, structured = await ticketing_mcp.mcp.call_tool("search_similar_tickets", {"query": "vibration"})
        assert structured["results"][0]["ticket_id"] == "TKT-0001"

    async def test_search_similar_tickets_passes_optional_asset_id_filter(self):
        captured = {}

        async def fake_request(method, path, **kwargs):
            captured["params"] = kwargs["params"]
            return {"results": []}

        ticketing_mcp.client.request = fake_request
        await ticketing_mcp.mcp.call_tool("search_similar_tickets", {"query": "vibration", "asset_id": "AST-0001"})
        assert captured["params"] == {"query": "vibration", "limit": 10, "asset_id": "AST-0001"}

    async def test_get_ticket_happy_path(self):
        async def fake_request(method, path, **kwargs):
            assert path == "/tickets/TKT-0005"
            return _ticket("TKT-0005")

        ticketing_mcp.client.request = fake_request
        _unstructured, structured = await ticketing_mcp.mcp.call_tool("get_ticket", {"ticket_id": "TKT-0005"})
        assert structured["ticket_id"] == "TKT-0005"

    async def test_create_ticket_sends_req_body_without_none_fields(self):
        captured = {}

        async def fake_request(method, path, **kwargs):
            captured["method"] = method
            captured["path"] = path
            captured["json_body"] = kwargs["json_body"]
            return _ticket("TKT-NEW")

        ticketing_mcp.client.request = fake_request
        await ticketing_mcp.mcp.call_tool(
            "create_ticket",
            {"req": {"summary": "New issue", "description": "Details", "asset_id": "AST-0002"}},
        )
        assert captured["method"] == "POST"
        assert captured["path"] == "/tickets"
        assert captured["json_body"]["summary"] == "New issue"
        assert captured["json_body"]["asset_id"] == "AST-0002"
        assert "alarm_id" not in captured["json_body"]  # exclude_none=True drops unset optional fields

    async def test_update_ticket_patches_by_ticket_id(self):
        captured = {}

        async def fake_request(method, path, **kwargs):
            captured["method"] = method
            captured["path"] = path
            captured["json_body"] = kwargs["json_body"]
            return _ticket("TKT-0005", status="resolved")

        ticketing_mcp.client.request = fake_request
        await ticketing_mcp.mcp.call_tool(
            "update_ticket", {"ticket_id": "TKT-0005", "req": {"status": "resolved", "resolution_notes": "Bearing replaced"}}
        )
        assert captured["method"] == "PATCH"
        assert captured["path"] == "/tickets/TKT-0005"
        assert captured["json_body"] == {"status": "resolved", "resolution_notes": "Bearing replaced"}


class TestListOpenTicketsForAssets:
    """This tool does client-side post-filtering (status != 'closed') and
    rebuilds the pagination block on top of whatever the API returns --
    worth testing directly rather than assuming the passthrough is exact.
    """

    async def test_closed_tickets_are_filtered_out(self):
        async def fake_request(method, path, **kwargs):
            assert kwargs["params"] == {"asset_id": ["AST-0001"], "page_size": 200}
            return {
                "data": [
                    _ticket("TKT-0001", status="open"),
                    _ticket("TKT-0002", status="closed"),
                    _ticket("TKT-0003", status="in_progress"),
                ],
                "pagination": {"page": 1, "page_size": 200, "total_items": 3, "total_pages": 1},
            }

        ticketing_mcp.client.request = fake_request
        _unstructured, structured = await ticketing_mcp.mcp.call_tool(
            "list_open_tickets_for_assets", {"asset_ids": ["AST-0001"]}
        )
        ids = {t["ticket_id"] for t in structured["data"]}
        assert ids == {"TKT-0001", "TKT-0003"}

    async def test_pagination_block_is_recomputed_to_match_filtered_count(self):
        async def fake_request(method, path, **kwargs):
            return {
                "data": [_ticket("TKT-0001", status="open"), _ticket("TKT-0002", status="closed")],
                "pagination": {"page": 1, "page_size": 200, "total_items": 2, "total_pages": 1},
            }

        ticketing_mcp.client.request = fake_request
        _unstructured, structured = await ticketing_mcp.mcp.call_tool(
            "list_open_tickets_for_assets", {"asset_ids": ["AST-0001"]}
        )
        assert structured["pagination"]["total_items"] == 1
        assert structured["pagination"]["page_size"] == 1

    async def test_all_closed_gives_empty_data_and_zero_total_pages(self):
        async def fake_request(method, path, **kwargs):
            return {
                "data": [_ticket("TKT-0001", status="closed")],
                "pagination": {"page": 1, "page_size": 200, "total_items": 1, "total_pages": 1},
            }

        ticketing_mcp.client.request = fake_request
        _unstructured, structured = await ticketing_mcp.mcp.call_tool(
            "list_open_tickets_for_assets", {"asset_ids": ["AST-0001"]}
        )
        assert structured["data"] == []
        assert structured["pagination"]["total_pages"] == 0


class TestSchemaValidation:
    async def test_create_ticket_missing_req_raises_tool_error(self):
        async def fake_request(method, path, **kwargs):
            raise AssertionError("client.request should never be reached -- validation must fail first")

        ticketing_mcp.client.request = fake_request
        with pytest.raises(ToolError):
            await ticketing_mcp.mcp.call_tool("create_ticket", {})

    async def test_update_ticket_invalid_status_literal_raises_tool_error(self):
        async def fake_request(method, path, **kwargs):
            raise AssertionError("client.request should never be reached -- validation must fail first")

        ticketing_mcp.client.request = fake_request
        with pytest.raises(ToolError):
            await ticketing_mcp.mcp.call_tool(
                "update_ticket", {"ticket_id": "TKT-0001", "req": {"status": "not_a_real_status"}}
            )

    async def test_malformed_upstream_ticket_response_raises_tool_error(self):
        async def fake_request(method, path, **kwargs):
            return {"ticket_id": "TKT-0001"}  # missing required fields

        ticketing_mcp.client.request = fake_request
        with pytest.raises(ToolError):
            await ticketing_mcp.mcp.call_tool("get_ticket", {"ticket_id": "TKT-0001"})


class TestErrorMapping:
    async def test_get_ticket_not_found_surfaces_as_tool_error(self):
        async def failing_request(method, path, **kwargs):
            raise UpstreamError(error_type="not_found", detail="Ticket TKT-9999 not found", status_code=404, trace_id="t-1")

        ticketing_mcp.client.request = failing_request
        with pytest.raises(ToolError, match="not_found"):
            await ticketing_mcp.mcp.call_tool("get_ticket", {"ticket_id": "TKT-9999"})


class TestTicketingClient:
    """Client-level tests, mocking httpx.AsyncClient.request directly --
    see TestAlarmManagementClient in test_alarm_mcp_server.py for the
    identical rationale (this client is a near-duplicate of that one)."""

    def _client(self) -> "TicketingClient":
        return TicketingClient()

    async def test_bearer_token_header_is_sent(self):
        client = self._client()
        captured = {}

        async def fake_request(method, path, *, params=None, json=None, headers=None):
            captured["headers"] = headers
            return httpx.Response(200, json={"ok": True}, request=httpx.Request(method, "http://test/x"))

        client._client.request = fake_request
        await client.request("GET", "/tickets/TKT-0001")
        assert captured["headers"]["Authorization"] == f"Bearer {client._token}"

    async def test_404_is_not_retried(self):
        client = self._client()
        call_count = 0

        async def fake_request(method, path, *, params=None, json=None, headers=None):
            nonlocal call_count
            call_count += 1
            return httpx.Response(404, json={"detail": "not found"}, request=httpx.Request(method, "http://test/x"))

        client._client.request = fake_request
        with pytest.raises(UpstreamError) as exc_info:
            await client.request("GET", "/tickets/TKT-9999")
        assert call_count == 1
        assert exc_info.value.error_type == "not_found"

    async def test_503_is_retried_then_succeeds(self):
        client = self._client()
        call_count = 0

        async def fake_request(method, path, *, params=None, json=None, headers=None):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                return httpx.Response(503, json={"detail": "unavailable"}, request=httpx.Request(method, "http://test/x"))
            return httpx.Response(200, json={"ok": True}, request=httpx.Request(method, "http://test/x"))

        client._client.request = fake_request
        result = await client.request("PATCH", "/tickets/TKT-0001", json_body={"status": "resolved"})
        assert result == {"ok": True}
        assert call_count == 2

    async def test_connect_error_exhausts_retries_and_raises_upstream_unavailable(self):
        client = self._client()
        client._max_retries = 2

        async def failing_request(method, path, *, params=None, json=None, headers=None):
            raise httpx.ConnectError("connection refused")

        client._client.request = failing_request
        with pytest.raises(UpstreamError) as exc_info:
            await client.request("GET", "/tickets/TKT-0001")
        assert exc_info.value.error_type == "upstream_unavailable"
