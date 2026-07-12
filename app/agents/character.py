from __future__ import annotations

from typing import TYPE_CHECKING

from app.models import CharacterBible, ShortScript
from app.services.openai_client import structured_response

if TYPE_CHECKING:
    from app.production.specification import ProductionSpecification

INSTRUCTIONS = """
You are the Character Director for Mind Frontier Studio.

Create one fictional recurring character only because this production explicitly
requires one. Adapt the character to the requested medium and visual direction.
The character must be visually distinctive, realistic, age-appropriate, and easy
to reproduce across multiple generated still images.

Do not use a real person's identity, a celebrity, a copyrighted character, a
brand logo, or visible writing. Avoid temporary details that would change from
scene to scene. Keep wardrobe, hair, facial structure, accessories, palette,
and lighting anchors precise and stable.

The prompt_anchor must be one compact paragraph that can be copied verbatim into
every image-generation prompt. It must describe the exact same fictional person.
The negative_constraints must explicitly prevent changes to face, age, hair,
wardrobe, accessories, and body proportions.
"""


def run(
    script: ShortScript,
    production_specification: ProductionSpecification | None = None,
) -> CharacterBible:
    protagonist_direction = getattr(
        production_specification,
        "protagonist_direction",
        None,
    ) or "Create an appropriate fictional recurring character."
    visual_style = getattr(production_specification, "visual_style", None) or "coherent visual style"
    negative_constraints = getattr(
        production_specification,
        "negative_constraints",
        [],
    )
    return structured_response(
        instructions=INSTRUCTIONS,
        prompt=f"""
Create the recurring visual character requested for this production:

Title: {script.title}
Hook: {script.hook}
Voiceover:
{script.voiceover}

Character direction: {protagonist_direction}
Visual style: {visual_style}
Additional negative constraints: {negative_constraints or "None supplied"}

The character should fit the subject without resembling a known person.
Return a production-ready visual bible.
""",
        schema=CharacterBible,
    )
