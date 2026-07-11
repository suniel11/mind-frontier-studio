from __future__ import annotations


def compile_prompt(scene, composition, style: dict, character_bible=None) -> str:
    negative = ""
    if character_bible is not None:
        negative = getattr(character_bible, "negative_constraints", "") or ""

    props = ", ".join(composition.recurring_props) if composition.recurring_props else "none required"

    blocks = [
        f"SCENE PURPOSE: {getattr(scene, 'narrative_goal', '')}",
        f"STORY ROLE: {getattr(scene, 'story_role', '')}",
        f"VISUAL TYPE: {composition.shot_strategy}",
        f"SUBJECT: {composition.subject}",
        f"ENVIRONMENT: {composition.environment}",
        f"FOREGROUND: {composition.foreground}",
        f"RECURRING PROPS: {props}",
        f"MOOD: {composition.mood}",
        f"LIGHTING: {composition.lighting}",
        f"CONTINUITY: {composition.continuity}",
        f"FRAMING: {getattr(scene, 'shot_type', 'medium')}",
        f"CAMERA INTENT: {getattr(scene, 'motion_type', 'dolly_in')}",
        f"STYLE LENS: {style.get('lens', '')}",
        f"STYLE COLOR: {style.get('color', '')}",
        f"STYLE TEXTURE: {style.get('texture', '')}",
        f"STYLE ATMOSPHERE: {style.get('atmosphere', '')}",
        f"COMPOSITION: {style.get('composition', '')}",
        (
            "CAPTION SAFE AREA: keep the "
            f"{getattr(scene, 'caption_safe_area', 'lower_third').replace('_', ' ')} "
            "visually uncluttered"
        ),
        (
            "OUTPUT: portrait 9:16, cinematic documentary still, realistic anatomy, "
            "natural materials, coherent production design"
        ),
        (
            "NEGATIVE CONSTRAINTS: no text, no logo, no watermark, no celebrity likeness, "
            "no copyrighted character, no duplicate subject, no distorted anatomy, "
            "no random wardrobe changes, no inconsistent facial identity"
        ),
    ]

    if negative:
        blocks.append(f"CHARACTER LOCK: {negative}")

    return "\n".join(block for block in blocks if block and not block.endswith(": "))
