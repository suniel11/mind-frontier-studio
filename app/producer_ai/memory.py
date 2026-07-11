from __future__ import annotations

import json
import re
from pathlib import Path


def normalize_topic(value: str) -> set[str]:
    words = re.sub(r"[^a-z0-9 ]", " ", value.lower()).split()
    stopwords = {
        "the", "and", "that", "this", "with", "from", "your", "about",
        "into", "why", "how", "what", "when", "where", "create",
        "cinematic", "second", "documentary", "short",
    }
    return {word for word in words if len(word) >= 4 and word not in stopwords}


def load_recent_topics(root: Path, limit: int = 30) -> list[str]:
    projects_dir = root / "projects"
    if not projects_dir.exists():
        return []

    records: list[tuple[float, str]] = []
    for folder in projects_dir.iterdir():
        if not folder.is_dir():
            continue

        project_path = folder / "project.json"
        if not project_path.exists():
            continue

        try:
            data = json.loads(project_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        topic = str(data.get("topic", "")).strip()
        if topic:
            records.append((folder.stat().st_mtime, topic))

    records.sort(reverse=True)
    return [topic for _, topic in records[:limit]]


def overlap_score(topic: str, recent_topics: list[str]) -> int:
    target = normalize_topic(topic)
    if not target:
        return 0

    highest = 0.0
    for previous in recent_topics:
        other = normalize_topic(previous)
        if not other:
            continue
        union = target | other
        similarity = len(target & other) / len(union) if union else 0.0
        highest = max(highest, similarity)

    return round(highest * 100)
