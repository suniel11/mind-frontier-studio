from app.models import CharacterBible, ShortScript, Storyboard
from app.services.openai_client import structured_response

INSTRUCTIONS = '''
You are the Visual Director for Mind Frontier.
Convert narration into exactly six coherent vertical-video scenes.
Use cinematic visuals that can be generated as still images.
No logos, copyrighted characters, visible writing, or watermarks in image prompts.
On-screen text must be brief.
Scene timing must be continuous and cover the full target duration.
Each image_prompt must describe one concrete portrait-oriented cinematic image.
'''

def run(
    script: ShortScript,
    target_seconds: int,
    character_bible: CharacterBible,
) -> Storyboard:
    return structured_response(
        instructions=INSTRUCTIONS,
        prompt=f'''
Target duration: {target_seconds} seconds
Script:
{script.model_dump_json(indent=2)}

CHARACTER CONSISTENCY RULES:
- Use the exact recurring protagonist described below in at least four scenes.
- Copy the prompt_anchor verbatim into every scene where the protagonist appears.
- Never alter the character's face, age, hairstyle, wardrobe, accessories, or body proportions.
- Use different framing, pose, environment, and camera angle without redesigning the person.
- In scenes without the protagonist, preserve the same color palette and lighting language.

CHARACTER BIBLE:
{character_bible.model_dump_json(indent=2)}

Create exactly six scenes.
The first begins at second 0 and the last ends at second {target_seconds}.
Use portions of the narration in each scene.
For each scene, include:
- visual_direction for the editor
- image_prompt for image generation
''',
        schema=Storyboard,
    )
