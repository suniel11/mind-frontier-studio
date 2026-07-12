from __future__ import annotations

import json
from typing import TYPE_CHECKING

from app.models import CharacterBible, ShortScript, Storyboard
from app.services.openai_client import structured_response

if TYPE_CHECKING:
    from app.production.specification import ProductionSpecification


INSTRUCTIONS = """
You are the Visual Director for Mind Frontier Studio.
Convert narration into six coherent scenes that can be produced as generated
still imagery and assembled into a finished video.

Respect the supplied format, aspect ratio, visual style, tone, pacing,
constraints, and whether a recurring character is actually required. Never
invent a human protagonist when the production does not request one. Product,
environmental, abstract, animated, archival, educational, and symbolic imagery
are all valid when appropriate.

No logos, copyrighted characters, unrequested visible writing, or watermarks in
image prompts. On-screen text must be brief. Scene timing must be continuous and
cover the full target duration. Each image prompt must describe one concrete,
renderable composition.

Build a continuous six-beat arc:
1. Hook
2. Setup
3. Conflict
4. Insight
5. Resolution
6. Final line

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
    return structured_response(
        instructions=INSTRUCTIONS,
        prompt=f"""
Target duration: {target_seconds} seconds

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

Create exactly six scenes for compatibility with the current render engine.
The first begins at second 0 and the last ends at second {target_seconds}.
Use portions of the narration in each scene.

Before the scenes, create visual_memory and story_arc_summary.

For each scene, include:
- story_role: hook, setup, conflict, insight, resolution, or final_line
- narrative_goal: what the scene must make the viewer understand or feel
- continuity_anchor: exact visual details that must carry over
- location_id: primary or secondary
- emotional_intensity: integer from 1 to 10
- pacing: fast, medium, slow, or hold
- visual_direction for the editor
- image_prompt for image generation
- shot_type: a concise production-appropriate framing
- motion_type: dolly_in, dolly_out, pan_left, pan_right, tilt_up, tilt_down, drift, or static
- transition_type: fade, dissolve, cut, or hold
- visual_emotion: one concise emotional direction
- caption_emphasis: the most important word or phrase, or an empty string

Use the strongest composition in scene 1, vary motion deliberately, and keep the
six scenes coherent without forcing a documentary aesthetic or human subject.
""",
        schema=Storyboard,
    )
