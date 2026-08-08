from mcp.server.fastmcp import FastMCP

from ticketing.app.models import (
    Ticket,
    TicketCreateRequest,
    TicketListResponse,
    TicketSearchResponse,
    TicketUpdateRequest,
)

from .client import TicketingClient
from .config import get_settings
from .errors import as_mcp_tool_error

client = TicketingClient()
mcp = FastMCP("ticketing-mcp", host=get_settings().mcp_host, port=get_settings().mcp_port)


@mcp.tool(
    name="search_similar_tickets",
    description="Keyword-search historical tickets by summary/description/labels, ranked by word overlap, optionally filtered by asset_id.",
)
@as_mcp_tool_error
async def search_similar_tickets(
    query: str, asset_id: str | None = None, limit: int = 10, trace_id: str | None = None
) -> TicketSearchResponse:
    """Keyword-search historical tickets, ranked by word-overlap score.

    Args:
        query: whitespace-separated search terms, matched case-insensitively.
        asset_id: optional hard filter applied before scoring.
        limit: maximum number of results to return.
        trace_id: correlation id to propagate; generated if not supplied.

    Returns:
        TicketSearchResponse: matching tickets sorted by descending score.
    """
    params: dict[str, object] = {"query": query, "limit": limit}
    if asset_id:
        params["asset_id"] = asset_id
    data = await client.request("GET", "/tickets/search", params=params, trace_id=trace_id)
    return TicketSearchResponse(**data)


@mcp.tool(
    name="list_open_tickets_for_assets",
    description="List non-closed tickets (open/in_progress/resolved) linked to any of the given asset_ids.",
)
@as_mcp_tool_error
async def list_open_tickets_for_assets(asset_ids: list[str], trace_id: str | None = None) -> TicketListResponse:
    """List non-closed tickets linked to any of the given asset_ids.

    Args:
        asset_ids: assets to match, sent as repeated asset_id query params.
        trace_id: correlation id to propagate; generated if not supplied.

    Returns:
        TicketListResponse: tickets with status != "closed" for these assets.
    """
    params = {"asset_id": asset_ids, "page_size": 200}
    data = await client.request("GET", "/tickets", params=params, trace_id=trace_id)
    response = TicketListResponse(**data)
    open_tickets = [ticket for ticket in response.data if ticket.status != "closed"]
    return TicketListResponse(
        data=open_tickets,
        pagination=response.pagination.model_copy(
            update={
                "page": 1,
                "page_size": len(open_tickets),
                "total_items": len(open_tickets),
                "total_pages": 1 if open_tickets else 0,
            }
        ),
    )


@mcp.tool(name="get_ticket", description="Fetch a single ticket by ID.")
@as_mcp_tool_error
async def get_ticket(ticket_id: str, trace_id: str | None = None) -> Ticket:
    """Fetch a single ticket by ID.

    Args:
        ticket_id: the ticket identifier, e.g. "TKT-0001".
        trace_id: correlation id to propagate; generated if not supplied.

    Returns:
        Ticket: the matching ticket.
    """
    data = await client.request("GET", f"/tickets/{ticket_id}", trace_id=trace_id)
    return Ticket(**data)


@mcp.tool(
    name="create_ticket",
    description=(
        "Create a new ticket. WRITE OPERATION: this creates real data. "
        "Do not call this with intent to actually create a ticket until the user "
        "has explicitly confirmed they want a ticket created — always confirm first."
    ),
)
@as_mcp_tool_error
async def create_ticket(req: TicketCreateRequest, trace_id: str | None = None) -> Ticket:
    """Create a ticket, or return the existing non-closed ticket for the same alarm_id.

    Args:
        req: the new ticket's fields.
        trace_id: correlation id to propagate; generated if not supplied.

    Returns:
        Ticket: the newly created ticket, or the pre-existing one for req.alarm_id.
    """
    data = await client.request(
        "POST", "/tickets", json_body=req.model_dump(mode="json", exclude_none=True), trace_id=trace_id
    )
    return Ticket(**data)


@mcp.tool(
    name="update_ticket",
    description=(
        "Update a ticket's status/resolution_notes/labels/priority. WRITE OPERATION: "
        "this modifies real data. Do not call this with intent to actually update a "
        "ticket until the user has explicitly confirmed the change — always confirm first."
    ),
)
@as_mcp_tool_error
async def update_ticket(ticket_id: str, req: TicketUpdateRequest, trace_id: str | None = None) -> Ticket:
    """Partially update a ticket's status/resolution_notes/labels/priority.

    Args:
        ticket_id: the ticket identifier to update.
        req: fields to overwrite; only fields explicitly set are applied.
        trace_id: correlation id to propagate; generated if not supplied.

    Returns:
        Ticket: the updated ticket.
    """
    data = await client.request(
        "PATCH",
        f"/tickets/{ticket_id}",
        json_body=req.model_dump(mode="json", exclude_none=True),
        trace_id=trace_id,
    )
    return Ticket(**data)


if __name__ == "__main__":
    transport = get_settings().mcp_transport
    if transport not in ("stdio", "streamable-http"):
        raise ValueError(f"Unsupported MCP_TRANSPORT '{transport}', must be stdio or streamable-http")
    mcp.run(transport=transport)
