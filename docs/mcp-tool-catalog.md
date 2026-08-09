# MCP Tool Catalog

Two MCP servers, both FastMCP-based, both callable over stdio (local dev/MCP Inspector) or streamable-http (Docker Compose, `MCP_TRANSPORT=streamable-http`).

## How to Start the MCP Server(s) Independently

```bash
# Alarm Management MCP server
MCP_TRANSPORT=streamable-http MCP_PORT=9000 uv run python -m mcp-servers.alarm-management.mcp

# Ticketing MCP server
MCP_TRANSPORT=streamable-http MCP_PORT=9100 uv run python -m mcp-servers.ticketing.mcp
```

Both also work over stdio (`MCP_TRANSPORT=stdio`, the `.env.example` default) for local inspection with the MCP Inspector or Claude Desktop, without a copilot backend attached at all.

Shared behavior across every tool on both servers, documented once here rather than repeated 19 times below:

- **Authentication:** each server holds one bearer token (`ALARM_API_TOKEN` / `TICKETING_API_TOKEN`) and attaches it to every outbound call to its source API. The token is never accepted as a tool argument, never logged, never returned in a tool result.
- **Timeout:** 5 seconds per attempt (`*_API_TIMEOUT_SECONDS`, default `5.0`).
- **Retry:** up to 3 attempts (`*_API_MAX_RETRIES`, default `3`), exponential backoff (~0.5s/1s/2s, capped 4s, + jitter). Retries only transient failures — network errors and `{500, 502, 503, 504}` responses. A `4xx` is never retried.
- **Error mapping:** the source API's HTTP status is mapped to a structured `error_type` (`401`→`authentication_error`, `404`→`not_found`, `422`→`validation_error`, other `4xx/5xx`→`upstream_error`; exhausted retries on a network-level failure →`upstream_unavailable`) and raised as an MCP `ToolError` carrying `{error_type, detail, status_code, trace_id}` as its JSON message — never a raw stack trace.
- **Trace propagation:** every call accepts an optional `trace_id` argument; if omitted, one is generated (`mcp-{8 hex chars}`) and sent as a request header, echoed back by the source API.
- **Input/output validation:** every tool's arguments and return value are real Pydantic models (shared with the simulator's own request/response schemas) — a malformed call or a malformed upstream response both surface as a `ToolError`, not a silent bad result.

---

## Alarm Management MCP Server

### `search_assets`

- **Purpose:** search assets by name substring, optionally filtered by unit.
- **Input schema:** `query: str`, `limit: int = 10`, `unit: str | None`, `trace_id: str | None`.
- **Output schema:** `AssetSearchResponse { results: Asset[] }`, `Asset { asset_id, asset_name, site, unit, asset_type }`.
- **Source-system operation:** `GET /assets/search`.
- **Example invocation:** `search_assets(query="Boiler Feed Pump", unit="Unit 2")`
- **Example response:** `{"results": [{"asset_id": "AST-0001", "asset_name": "Boiler Feed Pump 101", "site": "EastRefinery", "unit": "Unit 2", "asset_type": "pump"}]}`

### `get_asset_metadata`

- **Purpose:** fetch full metadata for a single asset.
- **Input schema:** `asset_id: str`, `trace_id: str | None`.
- **Output schema:** `AssetMetadata` — `Asset` fields plus `manufacturer, install_date, criticality`.
- **Source-system operation:** `GET /assets/{asset_id}/metadata`. `404` → `not_found` if the asset doesn't exist.
- **Example invocation:** `get_asset_metadata(asset_id="AST-0001")`
- **Example response:** `{"asset_id": "AST-0001", "asset_name": "Boiler Feed Pump 101", "site": "EastRefinery", "unit": "Unit 2", "asset_type": "pump", "manufacturer": "Flowserve", "install_date": "2018-03-01", "criticality": "high"}`

### `get_alarms`

- **Purpose:** list alarms filtered by asset/site/status, paginated and sorted.
- **Input schema:** `asset_id, site, status: str | None`, `page: int = 1`, `page_size: int = 50`, `sort_by: "start_time"|"severity"|"status"|"alarm_name" = "start_time"`, `sort_order: str = "desc"`, `trace_id: str | None`.
- **Output schema:** `AlarmListResponse { data: Alarm[], pagination: PaginationMeta }`.
- **Source-system operation:** `GET /alarms`.
- **Example invocation:** `get_alarms(site="EastRefinery", status="active", page=1, page_size=50)`
- **Example response:** `{"data": [{"alarm_id": "ALM-00002", "asset_id": "AST-0004", "site": "EastRefinery", "alarm_name": "High Discharge Pressure", "severity": "high", "status": "active", "start_time": "2026-07-10T09:23:00", "end_time": null, "ack_delay_seconds": 356}], "pagination": {"page": 1, "page_size": 50, "total_items": 35, "total_pages": 1}}`

### `get_alarm_by_id`

- **Purpose:** fetch a single alarm by ID.
- **Input schema:** `alarm_id: str`, `trace_id: str | None`.
- **Output schema:** `Alarm` (see above). `404` → `not_found` if the alarm doesn't exist.
- **Example invocation:** `get_alarm_by_id(alarm_id="ALM-00002")`
- **Example response:** as the single alarm object shown above.

### `get_alarm_summary`

- **Purpose:** group and aggregate alarms into per-group KPI values.
- **Input schema:** `req: AlarmSummaryRequest { asset_ids?, site?, unit?, time_range: {start_time, end_time}, severity?, alarm_types?, group_by?, kpis: str[] }`, `trace_id: str | None`.
- **Output schema:** `AlarmSummaryResponse { groups: [{group_key, kpi_values: {kpi_name: value}}], time_range }`.
- **Source-system operation:** `POST /alarms/summary`. `group_by` columns outside the supported set → `422`/`validation_error`.
- **Example invocation:** `get_alarm_summary(req={"site": "EastRefinery", "time_range": {"start_time": "2026-05-01T00:00:00", "end_time": "2026-08-01T00:00:00"}, "group_by": ["alarm_name"], "kpis": ["alarm_count"]})`

### `get_alarm_trends`

- **Purpose:** bucket alarms by time and compute per-bucket metric values.
- **Input schema:** `req: AlarmTrendsRequest { asset_ids?, site?, unit?, time_range, bucket: "hourly"|"daily"|"weekly", metrics: str[] }`, `trace_id: str | None`.
- **Output schema:** `AlarmTrendsResponse { points: [{bucket_start, metric_values}] }`.
- **Source-system operation:** `POST /alarms/trends`.

### `get_alarm_correlation`

- **Purpose:** find alarm-name pairs that co-occur within a lag window.
- **Input schema:** `req: AlarmCorrelationRequest { asset_ids: str[], time_range, correlation_method: "cooccurrence", lag_window_minutes: int = 15, severity_threshold: str, min_support: int }`, `trace_id: str | None`.
- **Output schema:** `AlarmCorrelationResponse { pairs: [{alarm_name_a, alarm_name_b, support, confidence}] }`.
- **Source-system operation:** `POST /alarms/correlation`.

### `get_flood_analysis`

- **Purpose:** detect rolling-window bursts of alarms on a unit's assets.
- **Input schema:** `req: FloodAnalysisRequest { unit: str, time_range, threshold_count: int, rolling_window_minutes: int }`, `trace_id: str | None`.
- **Output schema:** `FloodAnalysisResponse { episodes: [{window_start, window_end, alarm_count, top_contributing_assets}] }`.
- **Source-system operation:** `POST /alarms/flood-analysis`.

### `get_rationalization_candidates`

- **Purpose:** flag (asset, alarm_name) pairs that are recurring and/or chronically stale.
- **Input schema:** `req: RationalizationCandidatesRequest { asset_ids?, site?, unit?, time_range, recurrence_threshold: int, stale_minutes_threshold: int = 180 }`, `trace_id: str | None`.
- **Output schema:** `RationalizationCandidatesResponse { candidates: [{alarm_name, asset_id, occurrence_count, avg_unacknowledged_minutes, reason: "recurring"|"stale"|"both"}] }`.
- **Source-system operation:** `POST /alarms/rationalization-candidates`.

### `get_priority_score`

- **Purpose:** compute a 0–100 urgency score for a single alarm.
- **Input schema:** `req: PriorityScoreRequest { alarm_id: str }`, `trace_id: str | None`.
- **Output schema:** `PriorityScoreResponse { alarm_id, priority_score: float, contributing_factors: {factor: weight} }`.
- **Source-system operation:** `POST /alarms/priority-score`.
- **Example invocation:** `get_priority_score(req={"alarm_id": "ALM-00002"})`
- **Example response:** `{"alarm_id": "ALM-00002", "priority_score": 78.5, "contributing_factors": {"severity": 40.0, "asset_criticality": 25.0, "unacknowledged_time": 13.5}}`

### `get_kpi_definitions`

- **Purpose:** list all known KPI definitions.
- **Input schema:** `trace_id: str | None` (no other arguments).
- **Output schema:** `KPIDefinitionsResponse { kpis: [{kpi_name, description, unit?}] }`.
- **Source-system operation:** `GET /analytics/kpi-definitions`.

### `get_operator_recommendations`

- **Purpose:** look up playbook actions for an alarm, optionally enriched by context/history.
- **Input schema:** `req: OperatorRecommendationsRequest { alarm_id: str, include_related: bool = false, include_asset_context: bool = false, include_historical_pattern: bool = false }`, `trace_id: str | None`.
- **Output schema:** `OperatorRecommendationsResponse { alarm_id, recommendations: [{action, rationale, confidence}], related_alarm_ids? }`.
- **Source-system operation:** `POST /recommendations/operator-actions`.
- **Example invocation:** `get_operator_recommendations(req={"alarm_id": "ALM-00002", "include_asset_context": true})`

### `generate_kpi_calculation`

- **Purpose:** register a new ad-hoc calculation under a fresh `calculation_id`.
- **Input schema:** `req: GenerateCalculationRequest { calculation_type: str, filters: {unit?, start_time?, end_time?} }`, `trace_id: str | None`.
- **Output schema:** `GenerateCalculationResponse { calculation_id, calculation_type }`.
- **Source-system operation:** `POST /calculation-code/generate`.

### `execute_kpi_calculation`

- **Purpose:** run a previously generated calculation against matching alarms.
- **Input schema:** `req: ExecuteCalculationRequest { calculation_id: str, filters: {unit?, start_time?, end_time?} }`, `trace_id: str | None`.
- **Output schema:** `ExecuteCalculationResponse { calculation_id, result: dict }`.
- **Source-system operation:** `POST /calculation-code/execute`.

---

## Ticketing MCP Server

### `search_similar_tickets`

- **Purpose:** keyword-search historical tickets by summary/description/labels, ranked by word overlap, optionally filtered by asset.
- **Input schema:** `query: str`, `asset_id: str | None`, `limit: int = 10`, `trace_id: str | None`.
- **Output schema:** `TicketSearchResponse { results: Ticket[] }`.
- **Source-system operation:** `GET /tickets/search`.
- **Example invocation:** `search_similar_tickets(query="vibration bearing", asset_id="AST-0001")`

### `list_open_tickets_for_assets`

- **Purpose:** list non-closed tickets (open/in_progress/resolved) linked to any of the given assets.
- **Input schema:** `asset_ids: str[]`, `trace_id: str | None`.
- **Output schema:** `TicketListResponse { data: Ticket[], pagination: PaginationMeta }`. Note: this tool does its own client-side filtering (drops `status == "closed"` rows) and recomputes the `pagination` block to match the filtered count — it is not a raw passthrough of `GET /tickets`.
- **Source-system operation:** `GET /tickets` (with `page_size=200`, filtered client-side).
- **Example invocation:** `list_open_tickets_for_assets(asset_ids=["AST-0003", "AST-0004"])`

### `get_ticket`

- **Purpose:** fetch a single ticket by ID.
- **Input schema:** `ticket_id: str`, `trace_id: str | None`.
- **Output schema:** `Ticket { ticket_id, summary, description, status, labels, asset_id?, alarm_id?, priority?, created_at, updated_at, resolution_notes? }`. `404` → `not_found` if the ticket doesn't exist.
- **Source-system operation:** `GET /tickets/{ticket_id}`.

### `create_ticket` — WRITE, requires confirmation

- **Purpose:** create a new ticket, or return the existing non-closed ticket for the same `alarm_id` (idempotent per alarm).
- **Input schema:** `req: TicketCreateRequest { summary: str, description: str, status = "open", labels: str[] = [], asset_id?, alarm_id?, priority? }`, `trace_id: str | None`.
- **Output schema:** `Ticket` (as above).
- **Source-system operation:** `POST /tickets`.
- **Confirmation behavior:** the tool's own MCP description states it is a write operation and must not be called with intent to actually create a ticket before the user has explicitly confirmed. Enforced in the orchestration layer, not just documentation: `call_mcp_tools_node` intercepts any `create_ticket`/`update_ticket` call when `state["confirmed"]` isn't `True`, records it as `pending_write`, and routes to `await_confirmation_node` (a LangGraph `interrupt()`) instead of executing it — the GUI must send back an explicit approve before `execute_write_node` actually invokes the tool.
- **Example invocation:** `create_ticket(req={"summary": "High vibration on Boiler Feed Pump 101", "description": "Recurring high-vibration alarm, bearing wear suspected", "asset_id": "AST-0001", "alarm_id": "ALM-00002", "priority": "high"})`

### `update_ticket` — WRITE, requires confirmation

- **Purpose:** partially update a ticket's status/resolution_notes/labels/priority.
- **Input schema:** `ticket_id: str`, `req: TicketUpdateRequest { status?, resolution_notes?, labels?, priority? }` (only fields explicitly set are applied), `trace_id: str | None`.
- **Output schema:** `Ticket` (as above). `404` → `not_found` if the ticket doesn't exist.
- **Source-system operation:** `PATCH /tickets/{ticket_id}`.
- **Confirmation behavior:** identical gating to `create_ticket` (see above).
- **Example invocation:** `update_ticket(ticket_id="TKT-0001", req={"status": "resolved", "resolution_notes": "Bearing replaced, vibration back within limits"})`
