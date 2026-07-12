from __future__ import annotations


def topic_phrase(scene) -> str:
    """A short, subject-agnostic slice of the scene's own writing.

    Used anywhere a visual category needs to stay grounded in what the scene
    is actually about (a diagram, a map, an abstract metaphor) instead of a
    generic placeholder. Reads whatever the writer put in the scene -- never
    a topic-specific keyword list -- so it works the same for atoms, empires,
    or quarterly earnings.
    """

    text = str(
        getattr(scene, "narrative_goal", "")
        or getattr(scene, "narration", "")
        or ""
    ).strip()
    if len(text) > 160:
        text = text[:160].rsplit(" ", 1)[0] + "..."
    return text
