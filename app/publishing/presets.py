from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ChannelPreset:
    id: str
    name: str
    category: str
    language: str
    audience: str
    playlist: str
    default_hashtags: list[str]
    default_tags: list[str]
    watermark: str
    visibility: str = "private"

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


def load_channel_presets(root: Path) -> list[ChannelPreset]:
    presets_dir = root / "config" / "channels"
    presets_dir.mkdir(parents=True, exist_ok=True)

    presets: list[ChannelPreset] = []
    for path in sorted(presets_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        presets.append(ChannelPreset(**data))

    return presets


def get_channel_preset(root: Path, channel_id: str) -> ChannelPreset:
    for preset in load_channel_presets(root):
        if preset.id == channel_id:
            return preset
    raise FileNotFoundError(f"Channel preset not found: {channel_id}")
