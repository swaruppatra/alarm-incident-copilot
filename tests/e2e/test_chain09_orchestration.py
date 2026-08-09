"""End-to-end orchestration test -- CHAIN-09 from the Postman chaining
collection (postman/chaining/Alarm-API-Chaining.postman_collection.json,
"CHAIN-09 East Active -> Priority -> Recommendation"):

    1) GET  /alarms?site=EastRefinery&status=active   -> pick alarm_id
    2) GET  /alarms/{alarm_id}                        -> alarm detail
    3) POST /alarms/priority-score        {alarm_id}  -> priority score
    4) POST /recommendations/operator-actions {alarm_id} -> recommendations

This test runs it through the same two layers a real request would cross --
the alarm-management FastMCP server's tool functions (search_assets/
get_alarms/etc, with real Pydantic schema validation) calling
AlarmManagementClient.request (real retry/auth/header logic), which in turn
hits the *real* simulator FastAPI app (real routers, real bearer-token auth,
real sqlite queries against seeded test-data/*.json fixtures) -- nothing
about the request/response path is mocked.

The one thing not real is the transport: rather than a subprocess bound to a
TCP port (which `docker compose up` gives you, but a sandboxed/CI pytest run
can't assume), the client's httpx.AsyncClient is pointed at the FastAPI app
via ASGITransport. Every line of application code between the MCP tool call
and the sqlite row still executes for real -- this is the standard way to
get a genuine in-process end-to-end test without standing up real sockets.

For a true over-the-network run, just `cd` to the repo root and run
`docker compose up` and drive the same 4 calls through the GUI or curl
against the running containers -- this test's job is to prove the chaining
logic itself is correct and to catch regressions in CI, not to replace that
demo.
"""

import importlib

import httpx
import pytest

from simulator.app.data.db import init_db
from simulator.app.main import app as simulator_app

alarm_mcp = importlib.import_module("mcp-servers.alarm-management.mcp")
alarm_errors = importlib.import_module("mcp-servers.alarm-management.errors")

UpstreamError = alarm_errors.UpstreamError


@pytest.fixture(scope="module", autouse=True)
def seeded_simulator_over_asgi():
    """Seed the (fresh, temp-path) sqlite DB once, then point the MCP
    server's already-constructed client at the real FastAPI app in-process
    for the duration of this module, restoring the original client after.
    """
    init_db()
    original_client = alarm_mcp.client._client
    alarm_mcp.client._client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=simulator_app), base_url="http://simulator.e2e.test"
    )
    yield
    alarm_mcp.client._client = original_client


class TestChain09EastActivePriorityRecommendation:
    async def test_full_chain_runs_end_to_end_against_the_real_simulator(self):
        # --- Step 1: GET /alarms?site=EastRefinery&status=active ---
        _unstructured, step1 = await alarm_mcp.mcp.call_tool(
            "get_alarms", {"site": "EastRefinery", "status": "active", "page": 1, "page_size": 50}
        )
        assert step1["data"], "expected at least one active EastRefinery alarm in the seeded fixtures"
        for alarm in step1["data"]:
            assert alarm["site"] == "EastRefinery"
            assert alarm["status"] == "active"
        alarm_id = step1["data"][0]["alarm_id"]

        # --- Step 2: GET /alarms/{alarm_id} ---
        _unstructured, step2 = await alarm_mcp.mcp.call_tool("get_alarm_by_id", {"alarm_id": alarm_id})
        assert step2["alarm_id"] == alarm_id
        assert step2["site"] == "EastRefinery"
        asset_id = step2["asset_id"]

        # --- Step 3: POST /alarms/priority-score {alarm_id} ---
        _unstructured, step3 = await alarm_mcp.mcp.call_tool("get_priority_score", {"req": {"alarm_id": alarm_id}})
        assert step3["alarm_id"] == alarm_id
        assert 0 <= step3["priority_score"] <= 100
        assert step3["contributing_factors"]  # non-empty breakdown

        # --- Step 4: POST /recommendations/operator-actions {alarm_id} ---
        _unstructured, step4 = await alarm_mcp.mcp.call_tool(
            "get_operator_recommendations", {"req": {"alarm_id": alarm_id, "include_asset_context": True}}
        )
        assert step4["alarm_id"] == alarm_id
        assert isinstance(step4["recommendations"], list)

        # --- cross-step consistency: every step referenced the same alarm,
        # and the asset thread (step 2 -> asset metadata) is coherent too ---
        _unstructured, asset_metadata = await alarm_mcp.mcp.call_tool("get_asset_metadata", {"asset_id": asset_id})
        assert asset_metadata["asset_id"] == asset_id
        assert asset_metadata["site"] == "EastRefinery"

    async def test_chain_produces_different_results_for_a_different_site(self):
        # Guards against a hardcoded/stubbed response -- WestRefinery must
        # yield a genuinely different (and non-empty, per the fixtures) set.
        _unstructured, east = await alarm_mcp.mcp.call_tool(
            "get_alarms", {"site": "EastRefinery", "status": "active", "page": 1, "page_size": 200}
        )
        _unstructured, west = await alarm_mcp.mcp.call_tool(
            "get_alarms", {"site": "WestRefinery", "status": "active", "page": 1, "page_size": 200}
        )
        east_ids = {a["alarm_id"] for a in east["data"]}
        west_ids = {a["alarm_id"] for a in west["data"]}
        assert east_ids and west_ids
        assert east_ids.isdisjoint(west_ids)

    async def test_wrong_bearer_token_is_rejected_by_the_real_simulator(self):
        # Proves auth is genuinely enforced end-to-end, not bypassed by the
        # in-process transport -- swap in a bad token, restore it after.
        original_token = alarm_mcp.client._token
        alarm_mcp.client._token = "wrong-token"
        try:
            from mcp.server.fastmcp.exceptions import ToolError

            with pytest.raises(ToolError, match="authentication_error"):
                await alarm_mcp.mcp.call_tool("get_alarms", {})
        finally:
            alarm_mcp.client._token = original_token
