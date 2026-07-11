from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


@dataclass
class ReleasePackage:
    title: str
    description: str
    hashtags: list[str]
    pinned_comment: str
    video_path: str
    thumbnail_path: str
    quality_score: int
    publish_ready: bool

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


def _clean_hashtag(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_]", "", value.strip().lstrip("#"))
    return f"#{value}" if value else ""


def build_release_package(
    project_dir: Path,
    output,
    quality_report,
    video_path: Path,
    thumbnail_path: Path,
) -> ReleasePackage:
    seo = getattr(output, "seo", None)
    title = getattr(seo, "title", "") or getattr(output.script, "title", "Mind Frontier")
    description = getattr(seo, "description", "") or output.script.voiceover[:300]
    hashtags = [
        tag
        for tag in (_clean_hashtag(item) for item in (getattr(seo, "hashtags", []) or []))
        if tag
    ][:8]

    pinned_comment = (
        f"What part of “{title}” stayed with you most? "
        "Share your interpretation below."
    )

    package = ReleasePackage(
        title=title,
        description=description,
        hashtags=hashtags,
        pinned_comment=pinned_comment,
        video_path=str(video_path),
        thumbnail_path=str(thumbnail_path),
        quality_score=int(getattr(quality_report, "overall_score", 0)),
        publish_ready=bool(getattr(quality_report, "publish_ready", False)),
    )

    path = project_dir / "release-package.json"
    path.write_text(json.dumps(package.model_dump(), indent=2), encoding="utf-8")
    return package
