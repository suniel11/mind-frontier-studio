from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

DEFAULT_PROFILE = {
    "preferred_motions": ["micro_push", "drift", "pan_right", "static", "dolly_out"],
    "preferred_visual_types": [
        "character_detail",
        "environment",
        "symbolic_object",
        "character_action",
        "character_emotion",
        "environmental_hero",
    ],
    "minimum_quality_score": 85,
    "samples": 0,
}


def load_studio_profile(root: Path) -> dict[str, Any]:
    history_path = root / "studio_memory" / "production-history.jsonl"
    if not history_path.exists():
        return DEFAULT_PROFILE.copy()

    motions = Counter()
    visuals = Counter()
    scores: list[int] = []
    samples = 0

    for line in history_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue

        quality = record.get("quality_report", {})
        score = int(quality.get("overall_score", 0) or 0)
        if score:
            scores.append(score)

        for motion in record.get("motion_types", []) or []:
            if motion:
                motions[str(motion)] += 1

        for visual in record.get("visual_types", []) or []:
            if visual:
                visuals[str(visual)] += 1

        samples += 1

    profile = DEFAULT_PROFILE.copy()
    profile["samples"] = samples

    if motions:
        profile["preferred_motions"] = [name for name, _ in motions.most_common(8)]
    if visuals:
        profile["preferred_visual_types"] = [name for name, _ in visuals.most_common(8)]
    if scores:
        profile["average_quality_score"] = round(sum(scores) / len(scores), 1)

    return profile


def save_studio_profile(root: Path, profile: dict[str, Any]) -> Path:
    memory_dir = root / "studio_memory"
    memory_dir.mkdir(exist_ok=True)
    path = memory_dir / "studio-profile.json"
    path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    return path
