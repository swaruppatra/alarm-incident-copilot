from mcp.server.fastmcp import FastMCP

from simulator.app.models.alarms import Alarm, AlarmListResponse
from simulator.app.models.analytics import (
    AlarmCorrelationRequest,
    AlarmCorrelationResponse,
    AlarmSummaryRequest,
    AlarmSummaryResponse,
    AlarmTrendsRequest,
    AlarmTrendsResponse,
    FloodAnalysisRequest,
    FloodAnalysisResponse,
    KPIDefinitionsResponse,
    PriorityScoreRequest,
    PriorityScoreResponse,
    RationalizationCandidatesRequest,
    RationalizationCandidatesResponse,
)
from simulator.app.models.assets import AssetMetadata, AssetSearchResponse
from simulator.app.models.calculations import (
    ExecuteCalculationRequest,
    ExecuteCalculationResponse,
    GenerateCalculationRequest,
    GenerateCalculationResponse,
)
from simulator.app.models.recommendations import (
    OperatorRecommendationsRequest,
    OperatorRecommendationsResponse,
)

from .client import AlarmManagementClient
from .config import get_settings
from .errors import as_mcp_tool_error

client = AlarmManagementClient()
mcp = FastMCP("alarm-management-mcp", host=get_settings().mcp_host, port=get_settings().mcp_port)


# ####### assets #######

@mcp.tool(name="search_assets", description="Search assets by name substring, optionally filtered by unit.")
@as_mcp_tool_error
async def search_assets(
    query: str, limit: int = 10, unit: str | None = None, trace_id: str | None = None
) -> AssetSearchResponse:
    params = {"query": query, "limit": limit}
    if unit:
        params["unit"] = unit
    data = await client.request("GET", "/assets/search", params=params, trace_id=trace_id)
    return AssetSearchResponse(**data)


@mcp.tool(name="get_asset_metadata", description="Fetch full metadata for a single asset by ID.")
@as_mcp_tool_error
async def get_asset_metadata(asset_id: str, trace_id: str | None = None) -> AssetMetadata:
    """Fetch full metadata for a single asset by ID.

    Args:
        asset_id: the asset identifier, e.g. "AST-0001".
        trace_id: correlation id to propagate; generated if not supplied.

    Returns:
        AssetMetadata: the full asset metadata.
    """
    data = await client.request("GET", f"/assets/{asset_id}/metadata", trace_id=trace_id)
    return AssetMetadata(**data)


# ####### alarms #######

@mcp.tool(name="get_alarms", description="List alarms filtered by asset/site/status, paginated and sorted.")
@as_mcp_tool_error
async def get_alarms(
    asset_id: str | None = None,
    site: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 50,
    sort_by: str = "start_time",
    sort_order: str = "desc",
    trace_id: str | None = None,
) -> AlarmListResponse:
    """List alarms filtered by asset/site/status, paginated and sorted.

    Args:
        asset_id: optional exact-match asset_id filter.
        site: optional exact-match site filter.
        status: optional exact-match status filter.
        page: 1-indexed page number.
        page_size: number of rows per page.
        sort_by: column to sort by.
        sort_order: "asc" or "desc".
        trace_id: correlation id to propagate; generated if not supplied.

    Returns:
        AlarmListResponse: the matching page of alarms plus pagination metadata.
    """
    params: dict[str, object] = {"page": page, "page_size": page_size, "sort_by": sort_by, "sort_order": sort_order}
    if asset_id:
        params["asset_id"] = asset_id
    if site:
        params["site"] = site
    if status:
        params["status"] = status
    data = await client.request("GET", "/alarms", params=params, trace_id=trace_id)
    return AlarmListResponse(**data)


@mcp.tool(name="get_alarm_by_id", description="Fetch a single alarm by ID.")
@as_mcp_tool_error
async def get_alarm_by_id(alarm_id: str, trace_id: str | None = None) -> Alarm:
    """Fetch a single alarm by ID.

    Args:
        alarm_id: the alarm identifier, e.g. "ALM-00001".
        trace_id: correlation id to propagate; generated if not supplied.

    Returns:
        Alarm: the matching alarm.
    """
    data = await client.request("GET", f"/alarms/{alarm_id}", trace_id=trace_id)
    return Alarm(**data)


# ####### analytics #######

@mcp.tool(name="get_alarm_summary", description="Group and aggregate alarms into per-group KPI values.")
@as_mcp_tool_error
async def get_alarm_summary(req: AlarmSummaryRequest, trace_id: str | None = None) -> AlarmSummaryResponse:
    """Group and aggregate alarms into per-group KPI values.

    Args:
        req: asset_ids/site/unit scope, time_range, optional severity/group_by filters, kpis to compute.
        trace_id: correlation id to propagate; generated if not supplied.

    Returns:
        AlarmSummaryResponse: one group per distinct group_by combination.
    """
    data = await client.request(
        "POST", "/alarms/summary", json_body=req.model_dump(mode="json", exclude_none=True), trace_id=trace_id
    )
    return AlarmSummaryResponse(**data)


@mcp.tool(name="get_alarm_trends", description="Bucket alarms by time and compute per-bucket metric values.")
@as_mcp_tool_error
async def get_alarm_trends(req: AlarmTrendsRequest, trace_id: str | None = None) -> AlarmTrendsResponse:
    """Bucket alarms by time and compute per-bucket metric values.

    Args:
        req: asset_ids/site/unit scope, time_range, bucket granularity, metrics to compute.
        trace_id: correlation id to propagate; generated if not supplied.

    Returns:
        AlarmTrendsResponse: one point per bucket, sorted ascending.
    """
    data = await client.request(
        "POST", "/alarms/trends", json_body=req.model_dump(mode="json", exclude_none=True), trace_id=trace_id
    )
    return AlarmTrendsResponse(**data)


@mcp.tool(name="get_alarm_correlation", description="Find alarm-name pairs that co-occur within a lag window.")
@as_mcp_tool_error
async def get_alarm_correlation(
    req: AlarmCorrelationRequest, trace_id: str | None = None
) -> AlarmCorrelationResponse:
    """Find alarm-name pairs that co-occur within a lag window (earlier -> later).

    Args:
        req: asset_ids, time_range, lag_window_minutes, severity_threshold, min_support.
        trace_id: correlation id to propagate; generated if not supplied.

    Returns:
        AlarmCorrelationResponse: co-occurring pairs meeting min_support.
    """
    data = await client.request(
        "POST", "/alarms/correlation", json_body=req.model_dump(mode="json", exclude_none=True), trace_id=trace_id
    )
    return AlarmCorrelationResponse(**data)


@mcp.tool(name="get_flood_analysis", description="Detect rolling-window bursts of alarms on a unit's assets.")
@as_mcp_tool_error
async def get_flood_analysis(req: FloodAnalysisRequest, trace_id: str | None = None) -> FloodAnalysisResponse:
    """Detect rolling-window bursts of alarms on a unit's assets.

    Args:
        req: unit, time_range, threshold_count, rolling_window_minutes.
        trace_id: correlation id to propagate; generated if not supplied.

    Returns:
        FloodAnalysisResponse: non-overlapping episodes meeting threshold_count.
    """
    data = await client.request(
        "POST",
        "/alarms/flood-analysis",
        json_body=req.model_dump(mode="json", exclude_none=True),
        trace_id=trace_id,
    )
    return FloodAnalysisResponse(**data)


@mcp.tool(
    name="get_rationalization_candidates",
    description="Flag (asset, alarm_name) pairs that are recurring and/or chronically stale.",
)
@as_mcp_tool_error
async def get_rationalization_candidates(
    req: RationalizationCandidatesRequest, trace_id: str | None = None
) -> RationalizationCandidatesResponse:
    """Flag (asset, alarm_name) pairs that are recurring and/or chronically stale.

    Args:
        req: asset_ids/site/unit scope, time_range, recurrence_threshold, stale_minutes_threshold.
        trace_id: correlation id to propagate; generated if not supplied.

    Returns:
        RationalizationCandidatesResponse: pairs meeting either threshold.
    """
    data = await client.request(
        "POST",
        "/alarms/rationalization-candidates",
        json_body=req.model_dump(mode="json", exclude_none=True),
        trace_id=trace_id,
    )
    return RationalizationCandidatesResponse(**data)


@mcp.tool(name="get_priority_score", description="Compute a 0-100 urgency score for a single alarm.")
@as_mcp_tool_error
async def get_priority_score(req: PriorityScoreRequest, trace_id: str | None = None) -> PriorityScoreResponse:
    """Compute a 0-100 urgency score for a single alarm from severity/criticality/status.

    Args:
        req: alarm_id.
        trace_id: correlation id to propagate; generated if not supplied.

    Returns:
        PriorityScoreResponse: the score plus its contributing factors.
    """
    data = await client.request(
        "POST",
        "/alarms/priority-score",
        json_body=req.model_dump(mode="json", exclude_none=True),
        trace_id=trace_id,
    )
    return PriorityScoreResponse(**data)


@mcp.tool(name="get_kpi_definitions", description="List all known KPI definitions.")
@as_mcp_tool_error
async def get_kpi_definitions(trace_id: str | None = None) -> KPIDefinitionsResponse:
    """List all known KPI definitions.

    Args:
        trace_id: correlation id to propagate; generated if not supplied.

    Returns:
        KPIDefinitionsResponse: all known KPI definitions.
    """
    data = await client.request("GET", "/analytics/kpi-definitions", trace_id=trace_id)
    return KPIDefinitionsResponse(**data)


# ####### recommendations #######

@mcp.tool(
    name="get_operator_recommendations",
    description="Look up playbook actions for an alarm, optionally enriched by context/history.",
)
@as_mcp_tool_error
async def get_operator_recommendations(
    req: OperatorRecommendationsRequest, trace_id: str | None = None
) -> OperatorRecommendationsResponse:
    """Look up playbook actions for an alarm, optionally enriched by context/history.

    Args:
        req: alarm_id and include_related/include_asset_context/include_historical_pattern flags.
        trace_id: correlation id to propagate; generated if not supplied.

    Returns:
        OperatorRecommendationsResponse: playbook recommendations, sorted by confidence desc.
    """
    data = await client.request(
        "POST",
        "/recommendations/operator-actions",
        json_body=req.model_dump(mode="json", exclude_none=True),
        trace_id=trace_id,
    )
    return OperatorRecommendationsResponse(**data)


# ####### calculations #######

@mcp.tool(
    name="generate_kpi_calculation", description="Register a new calculation_type under a fresh calculation_id."
)
@as_mcp_tool_error
async def generate_kpi_calculation(
    req: GenerateCalculationRequest, trace_id: str | None = None
) -> GenerateCalculationResponse:
    """Register a new calculation_type under a fresh calculation_id.

    Args:
        req: calculation_type and its filters.
        trace_id: correlation id to propagate; generated if not supplied.

    Returns:
        GenerateCalculationResponse: the new calculation_id and its calculation_type.
    """
    data = await client.request(
        "POST",
        "/calculation-code/generate",
        json_body=req.model_dump(mode="json", exclude_none=True),
        trace_id=trace_id,
    )
    return GenerateCalculationResponse(**data)


@mcp.tool(
    name="execute_kpi_calculation", description="Run a previously generated calculation against matching alarms."
)
@as_mcp_tool_error
async def execute_kpi_calculation(
    req: ExecuteCalculationRequest, trace_id: str | None = None
) -> ExecuteCalculationResponse:
    """Run a previously generated calculation against alarms matching its filters.

    Args:
        req: calculation_id and filters.
        trace_id: correlation id to propagate; generated if not supplied.

    Returns:
        ExecuteCalculationResponse: the calculation_id and its computed result.
    """
    data = await client.request(
        "POST",
        "/calculation-code/execute",
        json_body=req.model_dump(mode="json", exclude_none=True),
        trace_id=trace_id,
    )
    return ExecuteCalculationResponse(**data)


if __name__ == "__main__":
    transport = get_settings().mcp_transport
    if transport not in ("stdio", "streamable-http"):
        raise ValueError(f"Unsupported MCP_TRANSPORT '{transport}', must be stdio or streamable-http")
    mcp.run(transport=transport)
