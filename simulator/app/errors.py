import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse

from simulator.app.models.common import ErrorResponse

logger = logging.getLogger("simulator")


def _trace_id(request: Request) -> str | None:
    """Read the trace_id header from an incoming request, if present.

    Args:
        request: the incoming FastAPI request.

    Returns:
        str | None: the trace_id header value, or None if absent.
    """
    return request.headers.get("trace_id")


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Map HTTPException (401/404/etc.) onto the ErrorResponse schema.

    Args:
        request: the incoming FastAPI request.
        exc: the raised HTTPException.

    Returns:
        JSONResponse: ErrorResponse body with exc's original status code.
    """
    body = ErrorResponse(error=type(exc).__name__, detail=str(exc.detail), trace_id=_trace_id(request))
    return JSONResponse(status_code=exc.status_code, content=body.model_dump())


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Map request validation failures onto the ErrorResponse schema.

    Args:
        request: the incoming FastAPI request.
        exc: the raised RequestValidationError.

    Returns:
        JSONResponse: 422 ErrorResponse body.
    """
    body = ErrorResponse(error="ValidationError", detail=str(exc.errors()), trace_id=_trace_id(request))
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=body.model_dump())


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Map any uncaught exception onto a 500 ErrorResponse without leaking internals.

    Args:
        request: the incoming FastAPI request.
        exc: the uncaught exception.

    Returns:
        JSONResponse: 500 ErrorResponse body.
    """
    logger.exception("Unhandled error", extra={"trace_id": _trace_id(request)})
    body = ErrorResponse(
        error="InternalServerError", detail="An unexpected error occurred", trace_id=_trace_id(request)
    )
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=body.model_dump())


def register_exception_handlers(app: FastAPI) -> None:
    """Attach the 401/404/422/500 exception handlers to the FastAPI app.

    Args:
        app: the FastAPI application instance.

    Returns:
        None
    """
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
