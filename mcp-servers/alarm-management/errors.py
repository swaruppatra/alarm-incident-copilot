import functools
import json
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

from mcp.server.fastmcp.exceptions import ToolError

F = TypeVar("F", bound=Callable[..., Coroutine[Any, Any, Any]])


class UpstreamError(Exception):
    """Raised by AlarmAPIClient. Message is a JSON string so a calling
    orchestrator can json.loads() it, while still reading as plain text
    if it isn't parsed."""

    def __init__(self, error_type: str, detail: str, status_code: int | None, trace_id: str | None) -> None:
        self.error_type = error_type
        self.status_code = status_code
        self.trace_id = trace_id
        super().__init__(json.dumps(
            {"error_type": error_type, "detail": detail, "status_code": status_code, "trace_id": trace_id}
        ))


def as_mcp_tool_error(fn: F) -> F:
    """Applied to every tool function: turns UpstreamError into ToolError so
    it surfaces to the MCP client as a structured is_error=True result
    instead of crashing the server process."""

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return await fn(*args, **kwargs)
        except UpstreamError as exc:
            raise ToolError(str(exc)) from exc

    return wrapper  # type: ignore[return-value]