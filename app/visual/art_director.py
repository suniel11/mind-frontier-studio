from __future__ import annotations


def enrich_prompt(base_prompt: str, shot, style: dict, continuity_anchor: str = "") -> str:
    safe_area_text = {
        "lower_third": "keep the lower third visually uncluttered for captions",
        "upper_third": "keep the upper third visually uncluttered for captions",
    }.get(shot.caption_safe_area, "leave clear negative space for captions")

    return (
        f"{base_prompt}\n"
        f"Visual strategy: {shot.visual_type}. "
        f"Framing: {shot.framing}. "
        f"Primary focus: {shot.subject_focus}. "
        f"Composition: {shot.composition}. "
        f"Camera language: {shot.camera_motion}. "
        f"Lens: {style['lens']}. "
        f"Lighting: {style['lighting']}. "
        f"Color treatment: {style['color']}. "
        f"Texture: {style['texture']}. "
        f"Atmosphere: {style['atmosphere']}. "
        f"Composition discipline: {style['composition']}; {safe_area_text}. "
        f"Continuity anchor: {continuity_anchor}. "
        "Portrait 9:16 composition. No text, logo, watermark, celebrity likeness, "
        "copyrighted character, distorted anatomy, duplicate subject, or random wardrobe changes."
    )
