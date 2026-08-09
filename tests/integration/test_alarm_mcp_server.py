"""Integration tests for the alarm-management MCP server.

Two layers, tested separately:

- TestToolRegistration / TestToolCalls / TestSchemaValidation / TestErrorMapping
  exercise the FastMCP server in-process (`mcp.list_tools()` /
  `mcp.call_tool()`), with `client.request` (AlarmManagementClient's own
  method) mocked. This covers tool discovery, real Pydantic argument
  schema validation, real response-model validation, and the
  UpstreamError -> ToolError mapping done by `as_mcp_tool_error`.

- TestAlarmManagementClient exercises AlarmManagementClient directly, one
  level lower, with the underlying `httpx.AsyncClient.request` mocked.
  This covers what the FastMCP-level tests can't reach: auth header
  injection, trace_id propagation/generation, retry-on-5xx,
  no-retry-on-4xx, retry-exhaustion, and HTTP-status -> UpstreamError
  mapping.

mcp-servers/alarm-management is not a valid dotted import path (hyphens),
so the module is loaded via importlib.import_module with the literal
directory names as path segments -- this works because Python treats
extension-less directories as implicit namespace packages.
"""

import importlib

import httpx
import pytest
from mcp.server.fastmcp.exceptions import ToolError

alarm_mcp = importlib.import_module("mcp-servers.alarm-management.mcp")
alarm_errors = importlib.import_module("mcp-servers.alarm-management.errors")
alarm_client_mod = importlib.import_module("mcp-servers.alarm-management.client")

UpstreamError = alarm_errors.UpstreamError
AlarmManagementClient = alarm_client_mod.AlarmManagementClient

EXPECTED_TOOL_NAMES = {
    "search_assets",
    "get_asset_metadata",
    "get_alarms",
    "get_alarm_by_id",
    "get_alarm_summary",
    "get_alarm_trends",
    "get_alarm_correlation",
    "get_flood_analysis",
    "get_rationalization_candidates",
    "get_priority_score",
    "get_kpi_definitions",
    "get_operator_recommendations",
    "generate_kpi_calculation",
    "execute_kpi_calculation",
}


@pytest.fixture(autouse=True)
def restore_client_request():
    """Every test in this module monkeypatches the module-level `client`
    singleton's `.request` method (since the FastMCP tool closures all
    reference that one instance) -- restore the original after each test
    so tests don't leak mocks into each other."""
    original = alarm_mcp.client.request
    yield
    alarm_mcp.client.request = original


class TestToolRegistration:
    async def test_all_expected_tools_are_registered(self):
        tools = await alarm_mcp.mcp.list_tools()
        assert {t.name for t in tools} == EXPECTED_TOOL_NAMES

    async def test_each_tool_has_a_non_empty_description(self):
        tools = await alarm_mcp.mcp.list_tools()
        for tool in tools:
            assert tool.description, f"{tool.name} has no description"


class TestToolCalls:
    async def test_search_assets_happy_path_returns_structured_content(self):
        async def fake_request(method, path, **kwargs):
            assert method == "GET"
            assert path == "/assets/search"
            assert kwargs["params"] == {"query": "Boiler", "limit": 10}
            return {
                "results": [
                    {"asset_id": "AST-0001", "asset_name": "Boiler Feed Pump", "site": "EastRefinery", "unit": "Unit 2", "asset_type": "pump"}
                ]
            }

        alarm_mcp.client.request = fake_request
        _unstructured, structured = await alarm_mcp.mcp.call_tool("search_assets", {"query": "Boiler"})
        assert structured == {
            "results": [
                {"asset_id": "AST-0001", "asset_name": "Boiler Feed Pump", "site": "EastRefinery", "unit": "Unit 2", "asset_type": "pump"}
            ]
        }

    async def test_search_assets_passes_optional_unit_filter_through(self):
        captured = {}

        async def fake_request(method, path, **kwargs):
            captured["params"] = kwargs["params"]
            return {"results": []}

        alarm_mcp.client.request = fake_request
        await alarm_mcp.mcp.call_tool("search_assets", {"query": "Pump", "unit": "Unit 2"})
        assert captured["params"] == {"query": "Pump", "limit": 10, "unit": "Unit 2"}

    async def test_get_kpi_definitions_takes_no_required_args(self):
        async def fake_request(method, path, **kwargs):
            return {"kpis": []}

        alarm_mcp.client.request = fake_request
        _unstructured, structured = await alarm_mcp.mcp.call_tool("get_kpi_definitions", {})
        assert structured == {"kpis": []}

    async def test_trace_id_is_forwarded_when_provided(self):
        captured = {}

        async def fake_request(method, path, **kwargs):
            captured["trace_id"] = kwargs.get("trace_id")
            return {"kpis": []}

        alarm_mcp.client.request = fake_request
        await alarm_mcp.mcp.call_tool("get_kpi_definitions", {"trace_id": "trace-abc-123"})
        assert captured["trace_id"] == "trace-abc-123"


class TestPagination:
    """get_alarms is the one alarm-management tool with real pagination
    (page/page_size/sort_by/sort_order in, a PaginationMeta block out) --
    worth pinning down on its own rather than assuming it behaves like the
    non-paginated tools covered above.
    """

    async def test_default_page_and_page_size_are_sent_when_omitted(self):
        captured = {}

        async def fake_request(method, path, **kwargs):
            captured["params"] = kwargs["params"]
            return {"data": [], "pagination": {"page": 1, "page_size": 50, "total_items": 0, "total_pages": 0}}

        alarm_mcp.client.request = fake_request
        await alarm_mcp.mcp.call_tool("get_alarms", {})
        assert captured["params"]["page"] == 1
        assert captured["params"]["page_size"] == 50
        assert captured["params"]["sort_by"] == "start_time"
        assert captured["params"]["sort_order"] == "desc"

    async def test_explicit_page_and_page_size_are_forwarded(self):
        captured = {}

        async def fake_request(method, path, **kwargs):
            captured["params"] = kwargs["params"]
            return {"data": [], "pagination": {"page": 3, "page_size": 10, "total_items": 25, "total_pages": 3}}

        alarm_mcp.client.request = fake_request
        await alarm_mcp.mcp.call_tool("get_alarms", {"page": 3, "page_size": 10})
        assert captured["params"]["page"] == 3
        assert captured["params"]["page_size"] == 10

    async def test_pagination_metadata_round_trips_into_structured_content(self):
        async def fake_request(method, path, **kwargs):
            return {
                "data": [],
                "pagination": {"page": 2, "page_size": 20, "total_items": 45, "total_pages": 3},
            }

        alarm_mcp.client.request = fake_request
        _unstructured, structured = await alarm_mcp.mcp.call_tool("get_alarms", {"page": 2, "page_size": 20})
        assert structured["pagination"] == {"page": 2, "page_size": 20, "total_items": 45, "total_pages": 3}

    async def test_missing_pagination_block_in_upstream_response_raises_tool_error(self):
        # AlarmListResponse.pagination is required -- a malformed upstream
        # response missing it must surface as a ToolError, not silently
        # produce a response with pagination=None.
        async def fake_request(method, path, **kwargs):
            return {"data": []}

        alarm_mcp.client.request = fake_request
        with pytest.raises(ToolError):
            await alarm_mcp.mcp.call_tool("get_alarms", {})


class TestSchemaValidation:
    async def test_missing_required_arg_raises_tool_error(self):
        async def fake_request(method, path, **kwargs):
            raise AssertionError("client.request should never be reached -- validation must fail first")

        alarm_mcp.client.request = fake_request
        with pytest.raises(ToolError, match="[Ff]ield required"):
            await alarm_mcp.mcp.call_tool("get_asset_metadata", {})

    async def test_wrong_type_for_page_raises_tool_error(self):
        async def fake_request(method, path, **kwargs):
            raise AssertionError("client.request should never be reached -- validation must fail first")

        alarm_mcp.client.request = fake_request
        with pytest.raises(ToolError):
            await alarm_mcp.mcp.call_tool("get_alarms", {"page": "not-a-number"})

    async def test_invalid_sort_by_literal_raises_tool_error(self):
        async def fake_request(method, path, **kwargs):
            raise AssertionError("client.request should never be reached -- validation must fail first")

        alarm_mcp.client.request = fake_request
        with pytest.raises(ToolError):
            await alarm_mcp.mcp.call_tool("get_alarms", {"sort_by": "priority"})

    async def test_malformed_upstream_response_also_raises_tool_error(self):
        # search_assets declares AssetSearchResponse(**data) -- if the
        # upstream API ever returns a shape that doesn't validate, that
        # should surface as a ToolError too, not an unhandled exception.
        async def fake_request(method, path, **kwargs):
            return {"unexpected_key": "no results field at all"}

        alarm_mcp.client.request = fake_request
        with pytest.raises(ToolError):
            await alarm_mcp.mcp.call_tool("search_assets", {"query": "x"})


class TestErrorMapping:
    async def test_upstream_not_found_error_surfaces_as_tool_error_with_detail(self):
        async def failing_request(method, path, **kwargs):
            raise UpstreamError(error_type="not_found", detail="Asset AST-9999 not found", status_code=404, trace_id="t-1")

        alarm_mcp.client.request = failing_request
        with pytest.raises(ToolError) as exc_info:
            await alarm_mcp.mcp.call_tool("get_asset_metadata", {"asset_id": "AST-9999"})
        message = str(exc_info.value)
        assert "not_found" in message
        assert "Asset AST-9999 not found" in message
        assert "404" in message

    async def test_upstream_unavailable_error_surfaces_as_tool_error(self):
        async def failing_request(method, path, **kwargs):
            raise UpstreamError(error_type="upstream_unavailable", detail="Alarm API unreachable after 3 attempts", status_code=None, trace_id="t-2")

        alarm_mcp.client.request = failing_request
        with pytest.raises(ToolError, match="upstream_unavailable"):
            await alarm_mcp.mcp.call_tool("get_kpi_definitions", {})


class TestAlarmManagementClient:
    """Client-level tests -- one layer below FastMCP, mocking
    httpx.AsyncClient.request directly so retry/timeout/auth/trace-id
    logic (which lives entirely in AlarmManagementClient.request) can be
    exercised without going through tool schema validation at all.
    """

    def _client(self) -> "AlarmManagementClient":
        return AlarmManagementClient()

    async def test_bearer_token_and_trace_id_headers_are_sent(self):
        client = self._client()
        captured = {}

        async def fake_request(method, path, *, params=None, json=None, headers=None):
            captured["headers"] = headers
            return httpx.Response(200, json={"ok": True}, request=httpx.Request(method, "http://test/" + path.lstrip("/")))

        client._client.request = fake_request
        await client.request("GET", "/kpi-definitions", trace_id="trace-xyz")
        assert captured["headers"]["Authorization"] == f"Bearer {client._token}"
        assert captured["headers"]["trace_id"] == "trace-xyz"

    async def test_trace_id_is_auto_generated_when_not_supplied(self):
        client = self._client()
        captured = {}

        async def fake_request(method, path, *, params=None, json=None, headers=None):
            captured["headers"] = headers
            return httpx.Response(200, json={"ok": True}, request=httpx.Request(method, "http://test/x"))

        client._client.request = fake_request
        await client.request("GET", "/x")
        assert captured["headers"]["trace_id"]  # non-empty, auto-generated
        assert captured["headers"]["trace_id"].startswith("mcp-")

    async def test_404_is_not_retried_and_maps_to_not_found(self):
        client = self._client()
        call_count = 0

        async def fake_request(method, path, *, params=None, json=None, headers=None):
            nonlocal call_count
            call_count += 1
            return httpx.Response(404, json={"detail": "Asset not found"}, request=httpx.Request(method, "http://test/x"))

        client._client.request = fake_request
        with pytest.raises(UpstreamError) as exc_info:
            await client.request("GET", "/x")
        assert call_count == 1  # a 4xx must never be retried
        assert exc_info.value.error_type == "not_found"
        assert exc_info.value.status_code == 404

    async def test_401_maps_to_authentication_error(self):
        client = self._client()

        async def fake_request(method, path, *, params=None, json=None, headers=None):
            return httpx.Response(401, json={"detail": "Invalid token"}, request=httpx.Request(method, "http://test/x"))

        client._client.request = fake_request
        with pytest.raises(UpstreamError) as exc_info:
            await client.request("GET", "/x")
        assert exc_info.value.error_type == "authentication_error"

    async def test_422_maps_to_validation_error(self):
        client = self._client()

        async def fake_request(method, path, *, params=None, json=None, headers=None):
            return httpx.Response(422, json={"detail": "bad params"}, request=httpx.Request(method, "http://test/x"))

        client._client.request = fake_request
        with pytest.raises(UpstreamError) as exc_info:
            await client.request("GET", "/x")
        assert exc_info.value.error_type == "validation_error"

    async def test_500_is_retried_then_succeeds(self):
        client = self._client()
        call_count = 0

        async def fake_request(method, path, *, params=None, json=None, headers=None):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return httpx.Response(500, json={"detail": "boom"}, request=httpx.Request(method, "http://test/x"))
            return httpx.Response(200, json={"ok": True}, request=httpx.Request(method, "http://test/x"))

        client._client.request = fake_request
        result = await client.request("GET", "/x")
        assert result == {"ok": True}
        assert call_count == 3

    async def test_500_exhausts_retries_and_raises_upstream_error_on_final_attempt(self):
        # Note: the exhausted-retries path differs by failure kind. A
        # persistent 5xx *status code* still gets a real HTTP response on
        # the final attempt, so `_handle_response` runs and maps it to
        # "upstream_error" (status_code=500) -- "upstream_unavailable" is
        # reserved for network-level failures (see the two tests below),
        # where there's no response at all to map.
        client = self._client()
        client._max_retries = 2
        call_count = 0

        async def fake_request(method, path, *, params=None, json=None, headers=None):
            nonlocal call_count
            call_count += 1
            return httpx.Response(500, json={"detail": "boom"}, request=httpx.Request(method, "http://test/x"))

        client._client.request = fake_request
        with pytest.raises(UpstreamError) as exc_info:
            await client.request("GET", "/x")
        assert call_count == 2
        assert exc_info.value.error_type == "upstream_error"
        assert exc_info.value.status_code == 500

    async def test_connect_error_is_retried_then_raises_upstream_unavailable(self):
        client = self._client()
        client._max_retries = 2

        async def failing_request(method, path, *, params=None, json=None, headers=None):
            raise httpx.ConnectError("connection refused")

        client._client.request = failing_request
        with pytest.raises(UpstreamError) as exc_info:
            await client.request("GET", "/x")
        assert exc_info.value.error_type == "upstream_unavailable"
        assert "connection refused" in exc_info.value.args[0]

    async def test_timeout_is_retried_then_raises_upstream_unavailable(self):
        client = self._client()
        client._max_retries = 2

        async def timing_out_request(method, path, *, params=None, json=None, headers=None):
            raise httpx.TimeoutException("timed out")

        client._client.request = timing_out_request
        with pytest.raises(UpstreamError) as exc_info:
            await client.request("GET", "/x")
        assert exc_info.value.error_type == "upstream_unavailable"
