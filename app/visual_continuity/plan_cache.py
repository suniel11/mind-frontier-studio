from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.core.settings import settings
from app.visual_continuity.models import VisualAssetPlan

CACHE_DIR_NAME = "visual_continuity_cache"

# Field separator guaranteed not to appear in any component (JSON text,
# model ids, floats) -- used instead of a plain "|" so no combination of
# component values can ever collide into the same key.
_SEPARATOR = "\x1f"


def cache_key(
    *,
    storyboard,
    production_specification,
    prompt_version: str,
    model: str,
    max_consecutive_reuse: int,
    min_grouping_confidence: float,
) -> str:
    """Deterministic key over exactly the inputs that can change what a
    correct grouping decision would be: the complete storyboard content,
    the production specification, the planner's own prompt version (bump
    ``app.visual_continuity.planner.PROMPT_VERSION`` whenever INSTRUCTIONS
    changes -- that alone invalidates every prior cache entry), the
    resolved model, and the grouping configuration
    (MAX_CONSECUTIVE_REUSE / MIN_GROUPING_CONFIDENCE). Anything else
    (pricing config, debug flag, project id) does not affect what the
    correct grouping *is*, so it is deliberately excluded.
    """

    storyboard_json = storyboard.model_dump_json()
    spec_json = production_specification.model_dump_json() if production_specification is not None else "null"
    payload = _SEPARATOR.join(
        [
            storyboard_json,
            spec_json,
            prompt_version,
            model,
            str(max_consecutive_reuse),
            f"{min_grouping_confidence:.6f}",
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _cache_dir() -> Path:
    path = Path(settings.root) / "studio_memory" / CACHE_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def get(key: str) -> VisualAssetPlan | None:
    """Look up a previously stored plan for an identical input. Returns
    ``None`` on a miss *or* on a corrupted/unreadable entry -- a broken
    cache file must degrade to "call the model again", never break
    planning."""

    path = _cache_dir() / f"{key}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return VisualAssetPlan(**data)
    except Exception:
        return None


def put(key: str, plan: VisualAssetPlan) -> None:
    path = _cache_dir() / f"{key}.json"
    path.write_text(json.dumps(plan.model_dump(), indent=2), encoding="utf-8")
