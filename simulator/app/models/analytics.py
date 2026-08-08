from typing import Literal

from pydantic import BaseModel

from .common import TimeRange


class AlarmSummaryRequest(BaseModel):
    asset_ids: list[str] | None = None
    site: str | None = None
    unit: str | None = None
    time_range: TimeRange
    severity: list[str] | None = None
    alarm_types: list[str] | None = None
    group_by: list[str] | None = None
    kpis: list[str]

class SummaryGroup(BaseModel):
    group_key: str                        # e.g. the alarm_name this group represents
    kpi_values: dict[str, float]           # {"alarm_count": 42, "recurring_rate": 0.18, ...}

class AlarmSummaryResponse(BaseModel):
    groups: list[SummaryGroup]
    time_range: TimeRange


class AlarmTrendsRequest(BaseModel):
    asset_ids: list[str] | None = None
    site: str | None = None
    unit: str | None = None
    time_range: TimeRange
    bucket: Literal["hourly", "daily", "weekly"]
    metrics: list[str]

class TrendPoint(BaseModel):
    bucket_start: str
    metric_values: dict[str, float]

class AlarmTrendsResponse(BaseModel):
    points: list[TrendPoint]


class AlarmCorrelationRequest(BaseModel):
    asset_ids: list[str]
    time_range: TimeRange
    correlation_method: Literal["cooccurrence"]
    lag_window_minutes: int = 15
    severity_threshold: str
    min_support: int

class CorrelatedPair(BaseModel):
    alarm_name_a: str
    alarm_name_b: str
    support: int          # how many times this pair co-occurred
    confidence: float     # 0-1

class AlarmCorrelationResponse(BaseModel):
    pairs: list[CorrelatedPair]


class FloodAnalysisRequest(BaseModel):
    unit: str
    time_range: TimeRange
    threshold_count: int
    rolling_window_minutes: int

class FloodEpisode(BaseModel):
    window_start: str
    window_end: str
    alarm_count: int
    top_contributing_assets: list[str]

class FloodAnalysisResponse(BaseModel):
    episodes: list[FloodEpisode]


class RationalizationCandidatesRequest(BaseModel):
    asset_ids: list[str] | None = None
    site: str | None = None
    unit: str | None = None
    time_range: TimeRange
    recurrence_threshold: int
    stale_minutes_threshold: int = 180

class RationalizationCandidate(BaseModel):
    alarm_name: str
    asset_id: str
    occurrence_count: int
    avg_unacknowledged_minutes: float
    reason: Literal["recurring", "stale", "both"]

class RationalizationCandidatesResponse(BaseModel):
    candidates: list[RationalizationCandidate]


class PriorityScoreRequest(BaseModel):
    alarm_id: str

class PriorityScoreResponse(BaseModel):
    alarm_id: str
    priority_score: float                    # 0–100, higher = more urgent
    contributing_factors: dict[str, float]

class KPIDefinition(BaseModel):
    kpi_name: str
    description: str
    unit: str | None = None

class KPIDefinitionsResponse(BaseModel):
    kpis: list[KPIDefinition]