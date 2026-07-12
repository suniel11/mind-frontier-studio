from __future__ import annotations

"""Genre-aware presenter frequency defaults.

``ProductionSpecification`` has no explicit genre field (and the frontend is
out of scope here), so the genre is inferred from the free-text fields a
creator already fills in (subject, tone, visual style, ...) using the same
generic-signal-detection approach as the Visual Director's visual-type
selection in app/visual/shot_planner.py -- a bounded classification into the
handful of genres this pipeline's defaults care about, not a topic-specific
image-selection hack.
"""

# Maximum share of a storyboard's scenes that may show a presenter/character,
# by inferred genre. Anything not matched falls back to "general".
PRESENTER_FREQUENCY_CAPS: dict[str, float] = {
    "educational": 0.20,
    "historical": 0.25,
    "science": 0.15,
    "psychology": 0.25,
    "business": 0.20,
    "travel": 0.30,
    "general": 0.25,
}

_GENRE_SIGNALS: dict[str, tuple[str, ...]] = {
    "science": (
        "physics", "chemistry", "biology", "laboratory", "experiment", "scientific",
        "molecule", "cell", "universe", "quantum", "species", "evolution", "electron",
        "microscope", "atom", "genome", "hypothesis", "particle",
    ),
    "historical": (
        "history", "ancient", "century", "empire", "dynasty", "war", "revolution",
        "civilization", "historical", "medieval", "era", "kingdom", "colonial",
    ),
    "psychology": (
        "psychology", "mind", "behavior", "behaviour", "emotion", "cognitive",
        "mental health", "therapy", "brain", "personality", "subconscious", "trauma",
    ),
    "business": (
        "business", "startup", "company", "market", "revenue", "strategy",
        "entrepreneur", "economy", "finance", "investment", "brand", "customer",
    ),
    "travel": (
        "travel", "destination", "journey", "voyage", "explore", "tourism",
        "expedition", "landmark", "itinerary", "backpacking",
    ),
    "educational": (
        "learn", "education", "how to", "explained", "tutorial", "lesson",
        "fundamentals", "beginner", "step by step",
    ),
}


def classify_genre(specification) -> str:
    if specification is None:
        return "general"
    text = " ".join(
        str(getattr(specification, field, "") or "")
        for field in (
            "subject",
            "original_prompt",
            "creative_objective",
            "tone",
            "visual_style",
            "narrative_structure",
        )
    ).casefold()

    scores = {
        genre: sum(1 for cue in cues if cue in text)
        for genre, cues in _GENRE_SIGNALS.items()
    }
    best_genre = max(scores, key=lambda key: scores[key])
    return best_genre if scores[best_genre] > 0 else "general"


def presenter_frequency_cap(specification) -> float:
    # An explicit creator preference (priority 1/2) always wins over the
    # inferred genre default (priority 4).
    explicit = getattr(
        getattr(getattr(specification, "preferences", None), "visuals", None),
        "presenter_frequency",
        None,
    )
    if explicit is not None:
        return explicit
    genre = classify_genre(specification)
    return PRESENTER_FREQUENCY_CAPS.get(genre, PRESENTER_FREQUENCY_CAPS["general"])
