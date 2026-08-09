import asyncio

from langchain_mcp_adapters.client import MultiServerMCPClient

from apps.backend.config import get_settings

# Loaded once per process and reused -- MultiServerMCPClient.get_tools() makes
# a real MCP round-trip per server, no need to repeat it on every node call.
_mcp_tools_cache: list | None = None
_mcp_tools_lock = asyncio.Lock()


async def get_mcp_tools() -> list:
    """Load (and cache) the MCP toolset from the alarm-management and ticketing servers.

    Args:
        None

    Returns:
        list[BaseTool]: every tool exposed by both configured MCP servers.
    """
    global _mcp_tools_cache
    if _mcp_tools_cache is not None:
        return _mcp_tools_cache
    async with _mcp_tools_lock:
        if _mcp_tools_cache is None:
            settings = get_settings()
            client = MultiServerMCPClient(
                {
                    "alarm-management": {"url": f"{settings.alarm_mcp_url}/mcp", "transport": "streamable_http"},
                    "ticketing": {"url": f"{settings.ticketing_mcp_url}/mcp", "transport": "streamable_http"},
                },
                # False so an MCP-level error (isError=True -- everything our own
                # as_mcp_tool_error decorator produces: validation/upstream/auth
                # failures) raises here instead of silently returning as if it
                # were a normal successful result. Default True would make
                # call_mcp_tools record every one of those as "success".
                handle_tool_errors=False,
            )
            _mcp_tools_cache = await client.get_tools()
    return _mcp_tools_cache


def find_tool(tools: list, name: str):
    """Find a loaded MCP tool by name.

    Args:
        tools (list[BaseTool]): the loaded MCP toolset.
        name (str): the tool name to look up.

    Returns:
        BaseTool | None: the matching tool, or None if no tool has that name.
    """
    return next((t for t in tools if t.name == name), None)
