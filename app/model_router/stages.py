from __future__ import annotations

from enum import Enum


class Stage(str, Enum):
    """Every text-model call site in the production pipeline.

    A handful of these (see ``DETERMINISTIC_STAGES``) have no LLM call site
    today -- their work is already done by deterministic code
    (``app.quality.inspector``, ``app.production.validation``,
    ``app.production.prompt_compiler``, ``app.visual.shot_planner``,
    ``app.learning.memory``). They are still enumerated here, with their own
    ``MODEL_<STAGE>`` environment variable and baseline/profile mapping, so
    the router's configuration surface matches the full pipeline and stays
    ready if any of them grow a model call later -- but nothing invokes the
    router for them yet.
    """

    CREATIVE_DIRECTOR_QUESTIONS = "creative_director_questions"
    CREATIVE_DIRECTOR_BRIEF = "creative_director_brief"
    RESEARCH = "research"
    SCRIPT = "script"
    STORYBOARD = "storyboard"
    CHARACTER = "character"
    VISUAL_DIRECTOR = "visual_director"
    PROMPT_COMPILER = "prompt_compiler"
    SEO = "seo"
    QUALITY_REVIEW = "quality_review"
    MEMORY = "memory"
    METADATA = "metadata"
    VALIDATION = "validation"


DETERMINISTIC_STAGES = frozenset(
    {
        Stage.VISUAL_DIRECTOR,
        Stage.PROMPT_COMPILER,
        Stage.QUALITY_REVIEW,
        Stage.MEMORY,
        Stage.METADATA,
        Stage.VALIDATION,
    }
)

ALL_STAGES: tuple[Stage, ...] = tuple(Stage)


def env_suffix(stage: Stage) -> str:
    return Stage(stage).value.upper()
