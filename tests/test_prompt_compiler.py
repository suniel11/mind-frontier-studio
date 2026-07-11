from types import SimpleNamespace

from app.production.prompt_compiler import compile_prompt


def test_compiled_prompt_contains_required_blocks():
    scene = SimpleNamespace(
        narrative_goal="Create tension",
        story_role="tension",
        shot_type="close_up",
        motion_type="drift",
        caption_safe_area="upper_third",
    )
    composition = SimpleNamespace(
        shot_strategy="symbolic_object",
        subject="an old brass key",
        environment="dim archive room",
        foreground="paper texture",
        recurring_props=["brass key"],
        mood="unease",
        lighting="single side light",
        continuity="same key and room",
    )
    style = {
        "lens": "50mm",
        "color": "muted",
        "texture": "film grain",
        "atmosphere": "dust",
        "composition": "rule of thirds",
    }

    prompt = compile_prompt(scene, composition, style)
    assert "SCENE PURPOSE:" in prompt
    assert "CONTINUITY:" in prompt
    assert "CAPTION SAFE AREA:" in prompt
    assert "NEGATIVE CONSTRAINTS:" in prompt
