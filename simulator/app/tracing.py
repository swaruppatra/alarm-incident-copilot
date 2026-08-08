import logging
from dataclasses import dataclass

from fastapi import Header, Response

logger = logging.getLogger("simulator")


@dataclass
class TraceContext:
    trace_id: str | None
    x_client_id: str | None
    x_metadata_tag: str | None


def get_trace_context(
    trace_id: str | None = Header(default=None, convert_underscores=False),
    x_client_id: str | None = Header(default=None),
    x_metadata_tag: str | None = Header(default=None),
) -> TraceContext:
    """FastAPI dependency that reads trace/correlation headers off the request.

    Args:
        trace_id: the trace_id header value, if present.
        x_client_id: the x-client-id header value, if present.
        x_metadata_tag: the x-metadata-tag header value, if present.

    Returns:
        TraceContext: the captured header values.
    """
    return TraceContext(trace_id=trace_id, x_client_id=x_client_id, x_metadata_tag=x_metadata_tag)


def apply_trace_response_header(response: Response, ctx: TraceContext) -> None:
    """Echo trace_id onto the response header and log the trace context.

    Args:
        response: the outgoing FastAPI response.
        ctx: the trace context captured from the request.

    Returns:
        None
    """
    if ctx.trace_id is not None:
        response.headers["trace_id"] = ctx.trace_id
    logger.info(
        "trace_context",
        extra={"trace_id": ctx.trace_id, "x_client_id": ctx.x_client_id, "x_metadata_tag": ctx.x_metadata_tag},
    )
