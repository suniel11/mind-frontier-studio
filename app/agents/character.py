from __future__ import annotations

from typing import TYPE_CHECKING

from app.models import CharacterBible, ShortScript
from app.services.openai_client import structured_response

if TYPE_CHECKING:
    from app.production.specification import ProductionSpecification

INSTRUCTIONS = """
You are the Character Director for Mind Frontier Studio.

Create exactly one fictional recurring character -- this is the single
Character Bible for the whole project. It is generated once and every other
subsystem (image prompts for presenter scenes, and narrator voice selection)
must reference this same identity instead of inventing its own. Adapt the
character to the requested medium and visual direction. The character must be
visually distinctive, realistic, age-appropriate, and easy to reproduce
across multiple generated still images.

Do not use a real person's identity, a celebrity, a copyrighted character, a
brand logo, or visible writing. Avoid temporary details that would change from
scene to scene. Keep wardrobe, hair, facial structure, accessories, palette,
and lighting anchors precise and stable.

gender must be a single unambiguous word ("male" or "female") -- it is used
verbatim to pick a matching narrator voice, so it must not be vague, mixed,
or omitted.

The prompt_anchor must be one compact paragraph that can be copied verbatim into
every image-generation prompt. It must describe the exact same fictional person
and must be consistent with the gender, age_range, ethnicity, hair, facial_hair,
and wardrobe fields. The negative_constraints must explicitly prevent changes to
face, age, hair, wardrobe, accessories, and body proportions.

continuity_tags should be a short list of stable, literal descriptors (e.g.
"grey wool coat", "short curly black hair") that other prompts can quote
directly to keep the character identical across scenes.
"""


def _presenter_constraints(production_specification: "ProductionSpecification | None") -> str:
    presenter = getattr(getattr(production_specification, "preferences", None), "presenter", None)
    if presenter is None:
        return "None supplied."

    lines = []
    if presenter.gender:
        lines.append(
            f"- gender MUST be exactly \"{presenter.gender}\". This is an explicit "
            "user instruction and overrides any other creative judgment."
        )
    if presenter.age:
        lines.append(f"- age_range MUST reflect: {presenter.age}")
    if presenter.appearance:
        lines.append(f"- appearance MUST reflect: {presenter.appearance}")
    if presenter.wardrobe:
        lines.append(f"- wardrobe MUST reflect: {presenter.wardrobe}")
    if presenter.continuity:
        lines.append(f"- continuity_tags MUST include: {presenter.continuity}")
    return "\n".join(lines) if lines else "None supplied."


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

Explicit user requirements for this character (these are direct user
instructions and take priority over every other consideration below):
{_presenter_constraints(production_specification)}

The character should fit the subject without resembling a known person.
Return a production-ready visual bible, including an explicit gender
("male" or "female") that a text-to-speech voice will be selected to match.
""",
        schema=CharacterBible,
    )
