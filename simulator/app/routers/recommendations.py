import sqlite3
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status

from simulator.app.auth import require_bearer_token
from simulator.app.data.db import get_db
from simulator.app.models.recommendations import (
    OperatorRecommendationsRequest,
    OperatorRecommendationsResponse,
    Recommendation,
)
from simulator.app.tracing import (
    TraceContext,
    apply_trace_response_header,
    get_trace_context,
)

router = APIRouter(prefix="/recommendations", tags=["recommendations"], dependencies=[Depends(require_bearer_token)])

RELATED_WINDOW_SECONDS = 3600


@router.post("/operator-actions", response_model=OperatorRecommendationsResponse)
def operator_recommendations(
    payload: OperatorRecommendationsRequest,
    response: Response,
    ctx: TraceContext = Depends(get_trace_context),
    db: sqlite3.Connection = Depends(get_db),
) -> OperatorRecommendationsResponse:
    """Look up playbook actions for an alarm, optionally enriched by context/history.

    Args:
        payload: alarm_id and include_related/include_asset_context/include_historical_pattern flags.
        response: outgoing response, used to echo trace_id.
        ctx: trace/correlation headers read from the request.
        db: request-scoped sqlite3 connection.

    Returns:
        OperatorRecommendationsResponse: playbook recommendations, sorted by confidence desc.
    """
    apply_trace_response_header(response, ctx)
    alarm_row = db.execute("SELECT * FROM alarms WHERE alarm_id = ?", (payload.alarm_id,)).fetchone()
    if alarm_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Alarm {payload.alarm_id} not found")

    playbook_rows = db.execute(
        "SELECT * FROM recommendation_playbook WHERE alarm_name = ?", (alarm_row["alarm_name"],)
    ).fetchall()

    confidence_boost = 0.0
    if payload.include_asset_context:
        asset_row = db.execute("SELECT * FROM assets WHERE asset_id = ?", (alarm_row["asset_id"],)).fetchone()
        if asset_row is not None and asset_row["criticality"] in ("high", "critical"):
            confidence_boost += 0.1
    if payload.include_historical_pattern:
        occurrence_count = db.execute(
            "SELECT COUNT(*) FROM alarms WHERE asset_id = ? AND alarm_name = ?",
            (alarm_row["asset_id"], alarm_row["alarm_name"]),
        ).fetchone()[0]
        confidence_boost += min(0.1, occurrence_count * 0.01)

    recommendations = sorted(
        (
            Recommendation(
                action=row["action"],
                rationale=row["rationale"],
                confidence=round(min(1.0, row["confidence"] + confidence_boost), 4),
            )
            for row in playbook_rows
        ),
        key=lambda rec: rec.confidence,
        reverse=True,
    )

    related_alarm_ids = None
    if payload.include_related:
        candidate_rows = db.execute(
            "SELECT alarm_id, start_time FROM alarms WHERE asset_id = ? AND alarm_id != ?",
            (alarm_row["asset_id"], alarm_row["alarm_id"]),
        ).fetchall()
        anchor = datetime.fromisoformat(alarm_row["start_time"])
        related_alarm_ids = [
            row["alarm_id"]
            for row in candidate_rows
            if abs((datetime.fromisoformat(row["start_time"]) - anchor).total_seconds()) <= RELATED_WINDOW_SECONDS
        ]

    return OperatorRecommendationsResponse(
        alarm_id=payload.alarm_id, recommendations=recommendations, related_alarm_ids=related_alarm_ids
    )
