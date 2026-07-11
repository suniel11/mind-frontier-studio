from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class ContentIdea:
    title: str
    prompt: str
    category: str
    hook_type: str
    evergreen_score: int
    curiosity_score: int
    emotional_score: int
    production_fit: int
    overall_score: int
    reason: str

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


IDEAS = [
    {
        "title": "Why Smart People Overthink Everything",
        "prompt": "Create a cinematic 45-second documentary about why intelligent people overthink decisions, imagine every possible failure, and delay action. Use a consistent protagonist, symbolic objects, reflective narration, visual variety, short captions, and end with a practical shift toward action.",
        "category": "psychology",
        "hook_type": "identity",
        "evergreen": 96,
        "curiosity": 95,
        "emotion": 90,
        "fit": 96,
    },
    {
        "title": "The Loneliness of Ambition",
        "prompt": "Create a cinematic 45-second documentary about how ambition can isolate people from friends, comfort, and ordinary life. Use a consistent protagonist, quiet environments, symbolic objects, restrained emotion, short captions, and end with a balanced reflection on purpose and connection.",
        "category": "psychology",
        "hook_type": "emotional contradiction",
        "evergreen": 94,
        "curiosity": 92,
        "emotion": 97,
        "fit": 95,
    },
    {
        "title": "Why You Keep Waiting to Feel Ready",
        "prompt": "Create a cinematic 45-second documentary about why people wait for confidence before beginning, even though confidence usually comes after action. Use a consistent protagonist, unfinished work, clocks, empty spaces, short captions, and end with: readiness is created by beginning.",
        "category": "self-improvement",
        "hook_type": "behavioral insight",
        "evergreen": 97,
        "curiosity": 93,
        "emotion": 91,
        "fit": 98,
    },
    {
        "title": "The Psychology of People Pleasing",
        "prompt": "Create a cinematic 45-second documentary about how people pleasing begins as a survival strategy and slowly erases personal identity. Use a consistent protagonist, mirrors, crowded rooms, quiet aftermath, reflective narration, short captions, and end with a boundary-focused insight.",
        "category": "psychology",
        "hook_type": "hidden cause",
        "evergreen": 96,
        "curiosity": 94,
        "emotion": 95,
        "fit": 95,
    },
    {
        "title": "Why Comfort Makes You Restless",
        "prompt": "Create a cinematic 45-second documentary about why a life built only around comfort can create boredom, restlessness, and loss of meaning. Use a consistent protagonist, repetitive spaces, symbolic routine, natural lighting, short captions, and end with the value of meaningful difficulty.",
        "category": "philosophy",
        "hook_type": "paradox",
        "evergreen": 95,
        "curiosity": 96,
        "emotion": 88,
        "fit": 95,
    },
    {
        "title": "The Quiet Damage of Comparison",
        "prompt": "Create a cinematic 45-second documentary about how constant comparison turns other people's progress into evidence against your own worth. Use a consistent protagonist, phone screens without readable text, mirrors, distance, short captions, and end with a return to personal standards.",
        "category": "psychology",
        "hook_type": "relatable pain",
        "evergreen": 98,
        "curiosity": 92,
        "emotion": 96,
        "fit": 97,
    },
    {
        "title": "What Marcus Aurelius Understood About Control",
        "prompt": "Create a cinematic 45-second documentary about the Stoic distinction between what is and is not under our control. Use a recurring modern protagonist, symbolic weather, hands, doors, calm environments, short captions, and end with a practical application for modern life.",
        "category": "philosophy",
        "hook_type": "ancient wisdom",
        "evergreen": 98,
        "curiosity": 90,
        "emotion": 84,
        "fit": 94,
    },
    {
        "title": "Why Your Brain Avoids Discomfort",
        "prompt": "Create a cinematic 45-second documentary about why the brain prefers familiar discomfort over uncertain growth. Use a consistent protagonist, repeated routines, thresholds, doors, shoes, short captions, and end with a small-action approach to change.",
        "category": "psychology",
        "hook_type": "brain explanation",
        "evergreen": 97,
        "curiosity": 95,
        "emotion": 90,
        "fit": 97,
    },
    {
        "title": "The Cost of Never Being Bored",
        "prompt": "Create a cinematic 45-second documentary about how constant stimulation weakens attention, creativity, and self-awareness. Use a consistent protagonist, phone-free symbolic scenes, windows, notebooks, empty rooms, short captions, and end with boredom as a doorway to thought.",
        "category": "attention",
        "hook_type": "modern habit",
        "evergreen": 95,
        "curiosity": 95,
        "emotion": 86,
        "fit": 96,
    },
    {
        "title": "Why Success Can Feel Empty",
        "prompt": "Create a cinematic 45-second documentary about why achieving external goals can still leave people emotionally empty when those goals were borrowed from others. Use a consistent protagonist, trophies, empty rooms, distant city views, short captions, and end with defining success personally.",
        "category": "philosophy",
        "hook_type": "success paradox",
        "evergreen": 94,
        "curiosity": 96,
        "emotion": 95,
        "fit": 94,
    },
]


def _score(idea: dict) -> int:
    return round(
        idea["evergreen"] * 0.28
        + idea["curiosity"] * 0.28
        + idea["emotion"] * 0.22
        + idea["fit"] * 0.22
    )


def get_recommendations(limit: int = 5, category: str | None = None) -> list[ContentIdea]:
    candidates = IDEAS
    if category:
        candidates = [idea for idea in IDEAS if idea["category"].lower() == category.lower()]

    ranked = sorted(candidates, key=_score, reverse=True)

    return [
        ContentIdea(
            title=idea["title"],
            prompt=idea["prompt"],
            category=idea["category"],
            hook_type=idea["hook_type"],
            evergreen_score=idea["evergreen"],
            curiosity_score=idea["curiosity"],
            emotional_score=idea["emotion"],
            production_fit=idea["fit"],
            overall_score=_score(idea),
            reason=(
                f"Strong {idea['hook_type']} hook, high evergreen value, "
                f"and a strong fit for Mind Frontier's visual style."
            ),
        )
        for idea in ranked[:max(1, min(limit, 20))]
    ]
