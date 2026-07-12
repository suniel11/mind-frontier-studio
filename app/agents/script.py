from __future__ import annotations

import json
from typing import TYPE_CHECKING

from app.models import ResearchBrief, ShortScript
from app.services.openai_client import structured_response

if TYPE_CHECKING:
    from app.production.specification import ProductionSpecification

INSTRUCTIONS = '''
You are the Script Agent for Mind Frontier.
Write original, production-ready narration suited to the requested format,
audience, tone, narration style, and pacing.
Avoid generic motivational filler, fake certainty, clickbait shouting, and "follow for more."
The first sentence must create immediate curiosity.
Use one memorable idea and end with a strong insight.
Write original wording.
'''


def _specification_context(
    production_specification: ProductionSpecification | None,
) -> str:
    if production_specification is None:
        return ""
    keys = (
        "creative_objective",
        "audience",
        "output_format",
        "tone",
        "narration_style",
        "pacing",
        "hook_strategy",
        "narrative_structure",
        "ending_direction",
        "accuracy_level",
        "production_constraints",
    )
    payload = {
        key: getattr(production_specification, key, None)
        for key in keys
        if getattr(production_specification, key, None) not in (None, "", [])
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def run(
    topic: str,
    research: ResearchBrief,
    target_seconds: int,
    production_specification: ProductionSpecification | None = None,
) -> ShortScript:
    return structured_response(
        instructions=INSTRUCTIONS,
        prompt=f'''
Topic: {topic}
Target duration: {target_seconds} seconds

Research brief:
{research.model_dump_json(indent=2)}

Production direction:
{_specification_context(production_specification) or "Use sound editorial judgment."}

Write a complete voiceover of approximately {target_seconds * 2.2:.0f} words.
The title should be compelling but accurate.
The hook must work in the first two seconds.
The ending should follow the requested ending direction and feel conclusive rather than promotional.
''',
        schema=ShortScript,
    )
