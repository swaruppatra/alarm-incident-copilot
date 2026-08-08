from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from simulator.app.data.db import init_db
from simulator.app.errors import register_exception_handlers
from simulator.app.routers import (
    alarms,
    analytics,
    assets,
    calculations,
    health,
    recommendations,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Seed the sqlite database once when the app starts.

    Args:
        app: the FastAPI application instance.

    Returns:
        AsyncIterator[None]: yields control while the app serves requests.
    """
    init_db()
    yield


app = FastAPI(title="Alarm Management API Simulator", lifespan=lifespan)
register_exception_handlers(app)
app.include_router(health.router)
app.include_router(assets.router)
app.include_router(alarms.router)
app.include_router(analytics.router)
app.include_router(recommendations.router)
app.include_router(calculations.router)
