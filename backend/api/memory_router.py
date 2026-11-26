"""
FastAPI Router for Jarvis Cognitive Memory & Personal Knowledge Graph.
Provides endpoints for memory inspection, manual curation, graph querying,
multi-hop traversal, sleep-cycle consolidation, and wiping.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional

from backend.core.memory_pilot import (
    list_all_memories, store_entity, store_relation,
    store_procedural_habit, remember_fact, recall_memory,
    delete_memory, clear_all_memories, get_injected_context,
    query_multi_hop_relations, find_entity_path, get_graph_analytics,
    run_sleep_cycle_consolidation
)

router = APIRouter()


class RememberFactRequest(BaseModel):
    content: str = Field(..., description="Fact or memory content to remember")
    category: str = Field(default="fact", description="Category: fact, contact, preference, etc.")
    importance: int = Field(default=5, ge=1, le=10, description="Importance rating 1-10")
    entity: Optional[str] = Field(default=None, description="Optional entity name")
    relation: Optional[str] = Field(default=None, description="Optional relation")
    target: Optional[str] = Field(default=None, description="Optional target entity")


class EntityRequest(BaseModel):
    name: str = Field(..., description="Entity name (e.g. Dad, Brave, VS Code)")
    entity_type: str = Field(..., description="Entity type: person, software, hardware, etc.")
    attributes: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Key-value attributes")
    importance: int = Field(default=5, ge=1, le=10)


class RelationRequest(BaseModel):
    source_name: str
    relation: str
    target_name: str
    confidence: float = 1.0


class RecallRequest(BaseModel):
    query: str
    category: Optional[str] = None
    top_k: int = 5


class MultiHopRequest(BaseModel):
    start_entity: str
    max_hops: int = Field(default=3, ge=1, le=5)


class PathRequest(BaseModel):
    source: str
    target: str
    max_hops: int = Field(default=4, ge=1, le=6)


@router.get("/stats")
def get_memory_stats() -> Dict[str, Any]:
    """Retrieves high-level metrics of the Cognitive Knowledge Graph."""
    data = list_all_memories(limit=1)
    return {
        "status": "success",
        "counts": data.get("counts", {}),
        "analytics": data.get("analytics", {})
    }


@router.get("/analytics")
def get_analytics_endpoint() -> Dict[str, Any]:
    """Returns network structure, central entity hubs, and graph density."""
    return {"status": "success", "analytics": get_graph_analytics()}


@router.get("/list")
def get_memory_list(search: str = "", category: str = "", limit: int = 60) -> Dict[str, Any]:
    """Lists entities, relations, habits, and raw memories for the UI Inspector."""
    data = list_all_memories(search=search, category=category, limit=limit)
    return data


@router.post("/recall")
def recall_memory_endpoint(req: RecallRequest) -> Dict[str, Any]:
    """Queries the Knowledge Graph, semantic embeddings, and FTS index."""
    results = recall_memory(req.query, category=req.category, top_k=req.top_k)
    return {"status": "success", "query": req.query, "results": results}


@router.post("/remember")
def add_fact(req: RememberFactRequest) -> Dict[str, Any]:
    """Adds a fact or relationship with dense vector embeddings and auto-links graph entities."""
    res = remember_fact(
        content=req.content,
        category=req.category,
        importance=req.importance,
        entity=req.entity,
        relation=req.relation,
        target=req.target
    )
    if not req.entity:
        try:
            from backend.core.memory_pilot import extract_memories_from_turn
            extracted = extract_memories_from_turn(req.content, "")
            res["extracted"] = extracted
        except Exception:
            pass
    return res


@router.post("/entity")
def add_entity(req: EntityRequest) -> Dict[str, Any]:
    """Stores or updates a named entity in the Semantic Knowledge Graph."""
    res = store_entity(
        name=req.name,
        entity_type=req.entity_type,
        attributes=req.attributes,
        importance=req.importance
    )
    return res


@router.post("/relation")
def add_relation(req: RelationRequest) -> Dict[str, Any]:
    """Connects two entities with a directed relationship edge."""
    res = store_relation(
        source_name=req.source_name,
        relation=req.relation,
        target_name=req.target_name,
        confidence=req.confidence
    )
    return res


@router.post("/multi-hop")
def multi_hop_endpoint(req: MultiHopRequest) -> Dict[str, Any]:
    """Explores multi-hop reasoning chains starting from an entity."""
    chains = query_multi_hop_relations(req.start_entity, max_hops=req.max_hops)
    return {
        "status": "success",
        "start_entity": req.start_entity,
        "max_hops": req.max_hops,
        "count": len(chains),
        "chains": chains
    }


@router.post("/path")
def path_endpoint(req: PathRequest) -> Dict[str, Any]:
    """Traces connecting relational path between two entities."""
    paths = find_entity_path(req.source, req.target, max_hops=req.max_hops)
    return {
        "status": "success",
        "source": req.source,
        "target": req.target,
        "paths": paths
    }


@router.post("/consolidate")
def consolidate_endpoint() -> Dict[str, Any]:
    """Triggers autonomous sleep-cycle consolidation (dedup, superseding, habit synthesis)."""
    res = run_sleep_cycle_consolidation()
    return res


@router.delete("/{item_type}/{item_id}")
def remove_memory(item_type: str, item_id: int) -> Dict[str, Any]:
    """Deletes an item from memory (entity, relation, habit, episode, raw)."""
    res = delete_memory(item_type, item_id)
    return res


@router.post("/clear")
def reset_memory() -> Dict[str, Any]:
    """Clears all cognitive memories and resets to baseline defaults."""
    res = clear_all_memories()
    return res
