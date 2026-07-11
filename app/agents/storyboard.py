from app.models import CharacterBible, ShortScript, Storyboard, VisualMemory
from app.services.openai_client import structured_response

INSTRUCTIONS = '''
You are the Visual Director for Mind Frontier.
Convert narration into exactly six coherent vertical-video scenes.
Use cinematic visuals that can be generated as still images.
No logos, copyrighted characters, visible writing, or watermarks in image prompts.
On-screen text must be brief.
Scene timing must be continuous and cover the full target duration.
Each image_prompt must describe one concrete portrait-oriented cinematic image.

Build one continuous six-beat story arc:
1. Hook
2. Setup
3. Tension
4. Expansion
5. Climax
6. Resolution

Create a Visual Memory before writing scenes. It must lock locations, recurring
props, production design, time of day, atmosphere, weather, palette, lighting,
lens language, and strict continuity rules.

Every scene must serve one narrative purpose and inherit the Visual Memory.
Do not redesign locations, props, wardrobe, lighting, or atmosphere between scenes.
Emotional intensity must generally rise toward scene 5 and release in scene 6.
Pacing should vary deliberately.
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

Continuity enforcement:
- The same fictional protagonist must remain visually identical whenever present.
- Reuse the same primary location description verbatim across relevant prompts.
- Reuse the same secondary location description verbatim across relevant prompts.
- Recurring props must keep the same material, color, scale, and condition.
- Preserve time of day, weather, palette, lighting direction, and lens language.
- Scene-to-scene changes must be motivated by story.
- Every image_prompt must explicitly include its continuity_anchor.

Create exactly six scenes.
The first begins at second 0 and the last ends at second {target_seconds}.
Use portions of the narration in each scene.
Before the scenes, create:
- visual_memory
- story_arc_summary

For each scene, include:
- story_role: hook, setup, tension, expansion, climax, or resolution
- narrative_goal: what this scene must make the viewer understand or feel
- continuity_anchor: exact visual details that must carry over
- location_id: primary or secondary
- emotional_intensity: integer from 1 to 10
- pacing: fast, medium, slow, or hold
- visual_direction for the editor
- image_prompt for image generation
- shot_type: wide, medium, close_up, extreme_close_up, over_shoulder, or silhouette
- motion_type: dolly_in, dolly_out, pan_left, pan_right, tilt_up, tilt_down, or static
- transition_type: fade, dissolve, or cut
- visual_emotion: one concise emotional direction
- caption_emphasis: the single most important word or phrase

Directorial rules:
- Scene 1 is the hook: use the strongest composition and a decisive dolly_in or close_up.
- Avoid using the same motion more than twice in a row.
- Match motion to emotion: dolly_in for intensity, dolly_out for isolation, pans for discovery, tilts for scale.
- Preserve the exact Character Bible identity whenever the recurring protagonist appears.
- Keep all six scenes visually coherent in palette, lighting, lens language, and production design.
''',
        schema=Storyboard,
    )
