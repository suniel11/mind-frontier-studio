from __future__ import annotations

import hashlib


def cache_key(
    prompt: str,
    *,
    aspect_ratio: str,
    style: str = "documentary",
    quality: str = "low",
    preset: str = "gpt-image-1",
) -> str:
    """Hash a Visual Asset Group's identity: canonical prompt, aspect ratio,
    style, rendering quality, and artistic preset -- two scenes only ever
    resolve to the same cache entry when all five match exactly."""

    raw = "|".join([prompt, aspect_ratio, style, quality, preset])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class ImageAssetCache:
    """Per-render-call cache mapping a Visual Asset Group's prompt hash to
    the index of the scene that generated it first.

    Scoped to a single ``build_video`` call (a fresh instance per render),
    matching the spec's "already generated within the current project" --
    this is not a cross-project/persistent cache, only a within-run
    dedup so a group's image is generated exactly once regardless of how
    many scenes reference it.
    """

    def __init__(self) -> None:
        self._first_index: dict[str, int] = {}

    def get(self, key: str) -> int | None:
        return self._first_index.get(key)

    def put(self, key: str, index: int) -> None:
        self._first_index.setdefault(key, index)
