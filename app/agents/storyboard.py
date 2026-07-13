from __future__ import annotations

import json
from typing import TYPE_CHECKING, List

from pydantic import BaseModel, Field

from app.model_router.execution import run_agent_stage
from app.model_router.quality_checks import storyboard_validator
from app.model_router.stages import Stage
from app.models import CharacterBible, Scene, ShortScript, Storyboard, VisualMemory
from app.narrative.duration_planning import scenes_for_duration

if TYPE_CHECKING:
    from app.production.specification import ProductionSpecification


# The storyboard LLM's actual wire schema -- deliberately narrower than the
# full ``Scene`` model used throughout the rest of the pipeline. Every field
# below is either read downstream before anything overwrites it, or gates
# storyboard_validator's structural checks. Fields Scene carries for later
# pipeline stages (narrative_beats, director/engine, cinema/director,
# visual_continuity) but that those stages unconditionally overwrite before
# storyboard's own value is ever read -- pacing, transition_type, lens_mm,
# composition, lighting_style, color_tone, focus_target, film_look,
# visual_type, caption_safe_area, visual_asset_group_id -- are intentionally
# absent so the model never spends output tokens inventing values for them.
# No docstring on this class deliberately -- Pydantic serializes class
# docstrings into the JSON schema sent with every request, which would
# inflate prompt tokens on the very call this schema exists to shrink.
class SceneDraft(BaseModel):
    number: int
    start_second: int
    end_second: int
    narration: str
    on_screen_text: str
    visual_direction: str
    image_prompt: str

    story_role: str = "development"
    narrative_goal: str = ""
    continuity_anchor: str = ""
    location_id: str = "primary"
    emotional_intensity: int = Field(default=5, ge=1, le=10)

    subject_focus: str = ""
    shot_type: str = "medium"
    motion_type: str = "dolly_in"
    visual_emotion: str = "reflective"
    caption_emphasis: str = ""


class StoryboardDraft(BaseModel):
    visual_memory: VisualMemory
    story_arc_summary: str
    scenes: List[SceneDraft]


# Expands the LLM's slim draft into a full Storyboard. Fields not present on
# SceneDraft take on Scene's own Python defaults here -- exactly the value
# they would have been unconditionally overwritten with by
# narrative_beats/director/cinema_direction anyway, so this changes nothing
# about what downstream stages ultimately compute.
def _draft_to_storyboard(draft: StoryboardDraft) -> Storyboard:
    return Storyboard(
        visual_memory=draft.visual_memory,
        story_arc_summary=draft.story_arc_summary,
        scenes=[Scene(**scene.model_dump()) for scene in draft.scenes],
    )


def _draft_validator(target_seconds: int):
    check = storyboard_validator(target_seconds=target_seconds)

    def _validate(draft: StoryboardDraft):
        return check(_draft_to_storyboard(draft))

    return _validate


INSTRUCTIONS = """
You are the Visual Director for Mind Frontier Studio.
Convert narration into a coherent sequence of scenes that can be produced as
generated still imagery and assembled into a finished video. The exact number
of scenes will be specified in the request -- it scales with the target
duration, so longer productions get more scenes rather than a few scenes held
on screen for a long time.

Respect the supplied format, aspect ratio, visual style, tone, pacing,
constraints, and whether a recurring character is actually required. Never
invent a human protagonist when the production does not request one. Product,
environmental, abstract, animated, archival, educational, and symbolic imagery
are all valid when appropriate.

No logos, copyrighted characters, unrequested visible writing, or watermarks in
image prompts. On-screen text must be brief. Scene timing must be continuous and
cover the full target duration. Each image prompt must describe one concrete,
renderable composition.

Build a continuous narrative arc:
1. Hook (scene 1 only)
2. A cycle of setup, conflict, insight, and resolution beats repeated as many
   times as needed to fill the requested scene count
3. Final line (last scene only)

Create a Visual Memory before writing scenes. It must lock relevant locations,
recurring props, production design, time of day, atmosphere, palette, lighting,
lens language, and continuity rules. Do not force people, wardrobe, weather, or
locations when they are irrelevant to the production.
"""


def _specification_context(
    production_specification: ProductionSpecification | None,
) -> str:
    if production_specification is None:
        return "Use the legacy vertical short format and established studio style."
    payload = {
        key: value
        for key, value in production_specification.model_dump().items()
        if value not in (None, "", [])
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _character_context(character_bible: CharacterBible | None) -> str:
    if character_bible is None:
        return """
CHARACTER DIRECTION:
- No recurring Character Bible is required for this production.
- Do not invent a default fictional protagonist.
- Choose the most relevant subject for each scene from the script and production specification.
- Preserve continuity for products, objects, environments, graphic motifs, or other recurring subjects.
"""
    return f"""
CHARACTER CONSISTENCY RULES:
- Use the exact recurring fictional character below only where narratively useful.
- Copy the prompt_anchor verbatim whenever the character appears.
- Never alter face, age, hairstyle, wardrobe, accessories, or body proportions.
- Scenes may omit the character when another subject communicates the idea better.

CHARACTER BIBLE:
{character_bible.model_dump_json(indent=2)}
"""


def run(
    script: ShortScript,
    target_seconds: int,
    character_bible: CharacterBible | None = None,
    production_specification: ProductionSpecification | None = None,
) -> Storyboard:
    scene_count = scenes_for_duration(target_seconds)
    result = run_agent_stage(
        Stage.STORYBOARD,
        instructions=INSTRUCTIONS,
        prompt=f"""
Target duration: {target_seconds} seconds
Required scene count: {scene_count}

Script:
{script.model_dump_json(indent=2)}

Production specification:
{_specification_context(production_specification)}

{_character_context(character_bible)}

Continuity enforcement:
- Reuse exact descriptions for recurring locations, objects, characters, and design motifs.
- Preserve relevant palette, lighting direction, lens language, and production design.
- Scene-to-scene changes must be motivated by the story.
- Every image_prompt must explicitly include its continuity_anchor.

Create exactly {scene_count} scenes. The first begins at second 0 and the
last ends at second {target_seconds}. Use portions of the narration in each
scene, distributing the full script across all {scene_count} scenes so no
scene is left with little or no narration.

Scene 1 must use story_role "hook" and the last scene must use story_role
"final_line". Every scene in between must use one of: setup, conflict,
insight, resolution -- reused as many times as needed; do not invent other
role names.

Before the scenes, create visual_memory and story_arc_summary.

For each scene, include:
- story_role: hook, setup, conflict, insight, resolution, or final_line
- narrative_goal: what the scene must make the viewer understand or feel
- continuity_anchor: exact visual details that must carry over
- location_id: primary or secondary
- emotional_intensity: integer from 1 to 10
- visual_direction for the editor
- image_prompt for image generation
- shot_type: a concise production-appropriate framing
- motion_type: dolly_in, dolly_out, pan_left, pan_right, tilt_up, tilt_down, drift, or static
- visual_emotion: one concise emotional direction
- caption_emphasis: the most important word or phrase, or an empty string

Use the strongest composition in scene 1, vary motion deliberately, and keep the
six scenes coherent without forcing a documentary aesthetic or human subject.
""",
        schema=StoryboardDraft,
        validate=_draft_validator(target_seconds),
    )
    return _draft_to_storyboard(result.output)
