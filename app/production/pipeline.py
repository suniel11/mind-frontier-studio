from __future__ import annotations

from pathlib import Path

from app.production.prompt_compiler import compile_prompt
from app.production.scene_composer import compose_scene
from app.visual.styles import load_style


def compile_storyboard_prompts(
    storyboard,
    project_root: Path,
    character_bible=None,
    style_name: str = "documentary",
):
    style = load_style(project_root, style_name)

    for scene in storyboard.scenes:
        composition = compose_scene(
            scene=scene,
            storyboard=storyboard,
            character_bible=character_bible,
        )
        scene.image_prompt = compile_prompt(
            scene=scene,
            composition=composition,
            style=style,
            character_bible=character_bible,
        )

    return storyboard
