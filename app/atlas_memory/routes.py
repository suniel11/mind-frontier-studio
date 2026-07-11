from __future__ import annotations

from fastapi import APIRouter, Query

from app.atlas_memory.graph import rebuild_memory_graph
from app.atlas_memory.search import search_memory
from app.atlas_memory.store import list_entities, list_relations
from app.core.settings import settings

router = APIRouter(prefix="/memory", tags=["Atlas Memory"])


@router.post("/rebuild")
def rebuild_memory():
    return rebuild_memory_graph(settings.root)


@router.get("/overview")
def memory_overview():
    entities = list_entities(settings.root, limit=200)
    relations = list_relations(settings.root, limit=300)

    return {
        "entity_count": len(entities),
        "relation_count": len(relations),
        "top_topics": [
            entity for entity in entities
            if entity["entity_type"] == "topic"
        ][:10],
        "categories": [
            entity for entity in entities
            if entity["entity_type"] == "category"
        ],
        "relations": relations[:50],
    }


@router.get("/search")
def memory_search(
    q: str = Query(min_length=2, max_length=300),
    limit: int = Query(default=20, ge=1, le=100),
):
    return {
        "query": q,
        "results": search_memory(settings.root, q, limit),
    }
