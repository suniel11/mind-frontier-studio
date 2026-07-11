from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from app.publishing.presets import ChannelPreset


@dataclass
class PublishPackage:
    project_id: str
    channel_id: str
    title: str
    description: str
    hashtags: list[str]
    tags: list[str]
    pinned_comment: str
    category: str
    language: str
    audience: str
    playlist: str
    visibility: str
    video_path: str
    thumbnail_path: str
    checklist: list[str]
    seo_score: int

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _clean_tag(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_ ]", "", value.strip().lstrip("#")).strip()


def _merge_unique(*groups: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for value in group:
            cleaned = _clean_tag(value)
            key = cleaned.lower()
            if cleaned and key not in seen:
                merged.append(cleaned)
                seen.add(key)
    return merged


def _seo_score(title: str, description: str, tags: list[str], hashtags: list[str]) -> int:
    score = 0
    score += 25 if 35 <= len(title) <= 70 else (15 if title else 0)
    score += 25 if 120 <= len(description) <= 1000 else (15 if description else 0)
    score += 25 if 5 <= len(tags) <= 20 else (15 if tags else 0)
    score += 25 if 3 <= len(hashtags) <= 8 else (15 if hashtags else 0)
    return min(score, 100)


def build_publish_package(project_dir: Path, channel: ChannelPreset) -> PublishPackage:
    release = _read_json(project_dir / "release-package.json")
    project = _read_json(project_dir / "project.json")

    script = project.get("script", {}) if isinstance(project.get("script"), dict) else {}
    seo = project.get("seo", {}) if isinstance(project.get("seo"), dict) else {}

    title = (
        release.get("title")
        or seo.get("title")
        or script.get("title")
        or project_dir.name.replace("-", " ").title()
    ).strip()

    description = (
        release.get("description")
        or seo.get("description")
        or script.get("voiceover", "")[:500]
    ).strip()

    release_hashtags = release.get("hashtags", []) or seo.get("hashtags", []) or []
    hashtags = _merge_unique(release_hashtags, channel.default_hashtags)[:8]
    hashtags = [f"#{tag.replace(' ', '')}" for tag in hashtags]

    topic = str(project.get("topic", ""))
    tags = _merge_unique(
        [
            topic,
            title,
            "cinematic documentary",
            "mind frontier",
            "psychology",
            "philosophy",
            "human behavior",
        ],
        channel.default_tags,
    )[:20]

    pinned_comment = (
        release.get("pinned_comment")
        or f"What idea from “{title}” stayed with you most? Share your interpretation below."
    )

    video_path = project_dir / "mind-frontier-short.mp4"
    thumbnail_path = project_dir / "thumbnail.jpg"

    checklist = [
        "Review the full video on YouTube after upload.",
        "Confirm the first frame has no black gap.",
        "Upload the custom thumbnail.",
        "Paste the final title.",
        "Paste the description and hashtags.",
        "Add the video to the selected playlist.",
        "Set audience to Not made for kids.",
        "Keep the first review upload private.",
        "Add and pin the prepared comment after publishing.",
        "Record views, retention, likes, comments, and subscribers after 24–72 hours.",
    ]

    package = PublishPackage(
        project_id=project_dir.name,
        channel_id=channel.id,
        title=title,
        description=description,
        hashtags=hashtags,
        tags=tags,
        pinned_comment=pinned_comment,
        category=channel.category,
        language=channel.language,
        audience=channel.audience,
        playlist=channel.playlist,
        visibility=channel.visibility,
        video_path=str(video_path),
        thumbnail_path=str(thumbnail_path),
        checklist=checklist,
        seo_score=_seo_score(title, description, tags, hashtags),
    )

    output_dir = project_dir / "upload-package"
    output_dir.mkdir(exist_ok=True)

    (output_dir / "upload.json").write_text(
        json.dumps(package.model_dump(), indent=2),
        encoding="utf-8",
    )
    (output_dir / "title.txt").write_text(title, encoding="utf-8")
    (output_dir / "description.txt").write_text(description, encoding="utf-8")
    (output_dir / "hashtags.txt").write_text(" ".join(hashtags), encoding="utf-8")
    (output_dir / "tags.txt").write_text(", ".join(tags), encoding="utf-8")
    (output_dir / "pinned-comment.txt").write_text(pinned_comment, encoding="utf-8")
    (output_dir / "checklist.txt").write_text(
        "\n".join(f"[ ] {item}" for item in checklist),
        encoding="utf-8",
    )

    return package
