from app.models import CharacterBible, ShortScript
from app.services.openai_client import structured_response

INSTRUCTIONS = """
You are the Character Director for Mind Frontier Studio.

Create one fictional recurring protagonist for a cinematic documentary short.
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


def run(script: ShortScript) -> CharacterBible:
    return structured_response(
        instructions=INSTRUCTIONS,
        prompt=f"""
Create a recurring visual protagonist for this short:

Title: {script.title}
Hook: {script.hook}
Voiceover:
{script.voiceover}

The protagonist should fit the subject without resembling a known person.
Return a production-ready visual bible.
""",
        schema=CharacterBible,
    )
