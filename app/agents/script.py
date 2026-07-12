from __future__ import annotations

import json
from typing import TYPE_CHECKING

from app.model_router.execution import run_agent_stage
from app.model_router.quality_checks import script_validator
from app.model_router.stages import Stage
from app.models import ResearchBrief, ShortScript

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
    return run_agent_stage(
        Stage.SCRIPT,
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
        validate=script_validator(target_seconds=target_seconds),
    ).output


RESIZE_INSTRUCTIONS = '''
You are the Script Agent for Mind Frontier, doing a length correction pass.
A narration you previously wrote was measured against the target runtime and
came out the wrong length. Rewrite only the voiceover to hit the new word
count as closely as possible while preserving the same title, hook idea,
core argument, and ending. Do not pad with filler or repetition -- add or
remove genuine content, examples, or elaboration.
'''


def resize(script: ShortScript, target_words: int) -> ShortScript:
    """Rewrite ``script.voiceover`` to land near ``target_words``.

    Used when a synthesized narration's measured duration misses the
    requested runtime by more than the pipeline's tolerance -- the fix
    targets the actual cause (a script sized wrong) instead of only
    stretching or cropping the rendered video to whatever length the
    narration happened to come out to.
    """

    # Corrective runtime rewrite -- routed through the same Stage.SCRIPT
    # model tier as the original script (Phase 5: "corrective runtime script
    # rewrite -> script model"), with the same baseline-quality fallback.
    return run_agent_stage(
        Stage.SCRIPT,
        instructions=RESIZE_INSTRUCTIONS,
        prompt=f'''
Current script:
{script.model_dump_json(indent=2)}

Rewrite the voiceover to approximately {target_words} words.
Keep the title, hook, and ending direction consistent with the original.
''',
        schema=ShortScript,
        validate=script_validator(target_seconds=round(target_words / 2.2)),
    ).output
