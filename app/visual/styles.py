from __future__ import annotations

import json
from pathlib import Path


DEFAULT_STYLE = {
    "name": "documentary",
    "lens": "35mm documentary lens",
    "lighting": "natural directional light with restrained contrast",
    "color": "muted cinematic colors with warm highlights",
    "texture": "natural skin texture, realistic imperfections, subtle film grain",
    "atmosphere": "subtle volumetric atmosphere",
    "composition": "clear subject separation and intentional negative space",
}


def load_style(root: Path, style_name: str = "documentary") -> dict:
    path = root / "styles" / f"{style_name}.json"
    if not path.exists():
        return DEFAULT_STYLE.copy()
    return {**DEFAULT_STYLE, **json.loads(path.read_text(encoding="utf-8"))}
