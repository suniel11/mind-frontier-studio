from __future__ import annotations

from pydantic import BaseModel, Field


class VisualAssetGroup(BaseModel):
    """One generated (or reused) image and every scene that shares it.

    ``scene_numbers`` is a contiguous, ascending run of Storyboard scene
    numbers. A single-scene group is a normal, unshared shot -- most
    productions will have a mix of both.
    """

    group_id: str
    scene_numbers: list[int]
    canonical_prompt: str
    semantic_category: str
    justification: str
    grouping_confidence: float = Field(ge=0.0, le=1.0)


class VisualAssetPlan(BaseModel):
    """The full Visual Asset Economy plan for one storyboard.

    This is both the LLM-facing structured-output schema and the final,
    constraint-enforced plan -- ``app.visual_continuity.planner`` never
    trusts the raw LLM shape as final; every group is re-validated and
    (if necessary) split before this type is considered authoritative.
    """

    groups: list[VisualAssetGroup]
