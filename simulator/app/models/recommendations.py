from pydantic import BaseModel


class OperatorRecommendationsRequest(BaseModel):
    alarm_id: str
    include_related: bool = False
    include_asset_context: bool = False
    include_historical_pattern: bool = False

class Recommendation(BaseModel):
    action: str
    rationale: str
    confidence: float

class OperatorRecommendationsResponse(BaseModel):
    alarm_id: str
    recommendations: list[Recommendation]
    related_alarm_ids: list[str] | None = None