from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class TopicAssessment:
    topic: str
    overall_score: int
    hook_score: int
    curiosity_score: int
    audience_fit: int
    originality_score: int
    production_fit: int
    overlap_penalty: int
    verdict: str
    reasons: list[str]
    suggested_angle: str

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProducerRecommendation:
    title: str
    prompt: str
    score: int
    confidence: int
    category: str
    reasons: list[str]
    assessment: TopicAssessment

    def model_dump(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["assessment"] = self.assessment.model_dump()
        return payload


@dataclass
class ChannelHealth:
    total_projects: int
    ready_projects: int
    published_projects: int
    average_quality: float
    psychology_share: int
    philosophy_share: int
    posting_consistency: int
    health_score: int
    warnings: list[str]

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)
