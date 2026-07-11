from __future__ import annotations

from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from app.atlas_memory.store import list_entities


def search_memory(
    root: Path,
    query: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    normalized = query.lower().strip()
    query_tokens = {token for token in normalized.split() if len(token) >= 2}

    results = []

    for entity in list_entities(root, limit=500):
        name = str(entity["name"]).lower()
        attributes = entity.get("attributes", {})
        haystack = f"{name} {attributes}".lower()

        token_overlap = len(query_tokens & set(haystack.split()))
        ratio = SequenceMatcher(None, normalized, name).ratio()
        score = round(
            ratio * 55
            + token_overlap * 10
            + float(entity.get("confidence", 0)) * 20
        )

        if score <= 5:
            continue

        results.append(
            {
                **entity,
                "search_score": score,
            }
        )

    results.sort(
        key=lambda item: (
            item["search_score"],
            item["confidence"],
            item["evidence_count"],
        ),
        reverse=True,
    )
    return results[:limit]
