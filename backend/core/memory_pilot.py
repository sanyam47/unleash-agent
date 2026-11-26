"""
Memory Pilot - Phase 6: Advanced Cognitive Knowledge Graph (The Brain of Jarvis).

Implements Hollywood 10/10 Cognitive Memory:
1. Semantic Knowledge Graph: Entities and multi-hop relationships with NetworkX.
2. Dense Semantic Vector Embeddings: High-dimensional conceptual cosine similarity (Gemini + Offline fallback).
3. Multi-Hop Graph Traversal: In-memory DiGraph reasoning over 2-4 relational hops (User -> Friend -> Company -> Project).
4. Autonomous "Sleep Cycle" Consolidation: Background reflection, deduplication, conflict superseding, and habit synthesis.
5. Hybrid Retrieval: Entity recognition + Multi-hop graph expansion + Dense semantic cosine + FTS5 BM25 + Procedural habits.
6. Sub-millisecond context auto-injection (<jarvis_memory>) for Jarvis system prompt.
"""

import os
import re
import json
import sqlite3
import datetime
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set

import numpy as np
import networkx as nx

MEMORY_DIR = Path("backend/data/memory")
MEMORY_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = MEMORY_DIR / "jarvis_memory.db"

EMBEDDING_MODEL = "gemini-embedding-001"
LOCAL_ST_MODEL_NAME = "all-MiniLM-L6-v2"

_LOCAL_ST_MODEL = None
_LOCAL_ST_LOADING = False
_LOCAL_ST_UNAVAILABLE = False
_EMBED_LOCK = threading.Lock()
_QUERY_VEC_CACHE: Dict[str, List[float]] = {}
_QUERY_VEC_CACHE_MAX = 256


def get_db_connection() -> sqlite3.Connection:
    """Returns a SQLite connection with row_factory and WAL mode enabled."""
    conn = sqlite3.connect(str(DB_PATH), timeout=25.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=15000;")
    return conn


def init_memory_db():
    """Initializes cognitive memory tables, FTS5 indexes, and consolidation schema."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # 1. Semantic Entities (People, Tools, Hardware, Locations, Projects)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE COLLATE NOCASE,
                entity_type TEXT NOT NULL,
                attributes TEXT,
                importance INTEGER DEFAULT 5,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 2. Semantic Relations (Graph Edges)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS relations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
                relation TEXT NOT NULL,
                target_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
                confidence REAL DEFAULT 1.0,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(source_id, relation, target_id)
            )
        """)

        # 3. Episodic Events (Chronological Timeline)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS episodic_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_summary TEXT NOT NULL,
                details TEXT,
                salience INTEGER DEFAULT 5,
                tags TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 4. Procedural Habits & Preferences
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS procedural_habits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                habit_key TEXT UNIQUE COLLATE NOCASE,
                rule_text TEXT NOT NULL,
                strength REAL DEFAULT 1.0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 5. Raw Memory Entries & Freeform Notes with Dense Vector Embeddings
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS raw_memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                content TEXT NOT NULL,
                importance INTEGER DEFAULT 5,
                embedding TEXT,
                is_active INTEGER DEFAULT 1,
                superseded_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                access_count INTEGER DEFAULT 0
            )
        """)

        # 6. FTS5 Virtual Table for Sub-Millisecond Search
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                content,
                category,
                entity_names,
                content_rowid UNINDEXED
            )
        """)

        # 7. Consolidation Logs (Sleep Cycle Audit)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS consolidation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                actions_summary TEXT,
                deduplicated_count INTEGER DEFAULT 0,
                pruned_count INTEGER DEFAULT 0,
                habits_synthesized INTEGER DEFAULT 0
            )
        """)

        # Schema migrations for existing databases
        for col_def in [
            ("raw_memories", "embedding TEXT"),
            ("raw_memories", "is_active INTEGER DEFAULT 1"),
            ("raw_memories", "superseded_by INTEGER"),
            ("relations", "is_active INTEGER DEFAULT 1")
        ]:
            tbl, col = col_def
            try:
                cursor.execute(f"ALTER TABLE {tbl} ADD COLUMN {col};")
            except Exception:
                pass

        conn.commit()

    # Seed baseline defaults if DB is newly initialized
    _seed_default_memories_if_needed()


def _seed_default_memories_if_needed():
    """Seeds baseline user profile and environment preferences if newly created."""
    with get_db_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]

    if count == 0:
        store_entity("User", "person", {"role": "Primary Operator / Developer"}, importance=10)
        store_entity("Brave", "software", {"type": "browser", "is_primary": True}, importance=8)
        store_entity("VS Code", "software", {"type": "ide", "is_primary": True}, importance=8)
        store_entity("RTX 3050", "hardware", {"type": "gpu", "vram": "6GB", "platform": "Laptop"}, importance=7)
        store_entity("Windows 11", "os", {"type": "operating_system"}, importance=8)

        store_relation("User", "preferred_browser", "Brave")
        store_relation("User", "preferred_editor", "VS Code")
        store_relation("User", "primary_gpu", "RTX 3050")

        store_procedural_habit("browser", "primary_browser", "Always use Brave as the primary web browser for navigation and searching.")
        store_procedural_habit("code", "code_editor", "Primary code workspace and editor is VS Code.")
        store_procedural_habit("general", "persona", "Provide concise, technically precise, and actionable responses directly.")

        store_episodic_event("Executive Core Initialization", "Initialized Executive Gateway, Vision Pilot, GUI Pilot, Dual-Mode Voice Engine, and Cognitive Knowledge Graph.", salience=8, tags="system,init")


# =========================================================================
# 1. DENSE SEMANTIC VECTOR EMBEDDINGS (UNIFIED LOCAL NEURAL + CLOUD FALLBACK)
# =========================================================================

def _load_local_st_model():
    """Loads cached local SentenceTransformer (all-MiniLM-L6-v2, 384-d) once safely."""
    global _LOCAL_ST_MODEL, _LOCAL_ST_LOADING, _LOCAL_ST_UNAVAILABLE
    if _LOCAL_ST_MODEL is not None:
        return _LOCAL_ST_MODEL
    if _LOCAL_ST_UNAVAILABLE:
        return None
    with _EMBED_LOCK:
        if _LOCAL_ST_MODEL is not None:
            return _LOCAL_ST_MODEL
        if _LOCAL_ST_UNAVAILABLE:
            return None
        _LOCAL_ST_LOADING = True
        try:
            from sentence_transformers import SentenceTransformer
            try:
                _LOCAL_ST_MODEL = SentenceTransformer(LOCAL_ST_MODEL_NAME, local_files_only=True)
            except Exception:
                _LOCAL_ST_MODEL = SentenceTransformer(LOCAL_ST_MODEL_NAME)
        except Exception as e:
            print(f"[Memory Pilot] Local SentenceTransformer unavailable, using fallback: {e}")
            _LOCAL_ST_UNAVAILABLE = True
            _LOCAL_ST_MODEL = None
        finally:
            _LOCAL_ST_LOADING = False
    return _LOCAL_ST_MODEL


def prewarm_local_embedder() -> bool:
    """Warms local 384-d neural embedder in background so live chat recalls take <25ms."""
    if _LOCAL_ST_MODEL is not None or _LOCAL_ST_LOADING or _LOCAL_ST_UNAVAILABLE:
        return _LOCAL_ST_MODEL is not None
    return _load_local_st_model() is not None


def _trigger_async_prewarm():
    """Non-blocking one-shot background warmup for the local neural embedder."""
    if _LOCAL_ST_MODEL is None and not _LOCAL_ST_LOADING and not _LOCAL_ST_UNAVAILABLE:
        try:
            threading.Thread(target=prewarm_local_embedder, daemon=True, name="MemoryEmbedderWarmup").start()
        except Exception:
            pass


def generate_dense_embedding(text: str, allow_cold_import: bool = True) -> Optional[List[float]]:
    """
    Generates normalized dense semantic vector embeddings in a unified 384-d neural space
    using cached SentenceTransformer (all-MiniLM-L6-v2, ~23ms CPU, 0 VRAM contention).
    On cold startup read paths (`allow_cold_import=False`), kicks off async prewarm and
    avoids blocking chat turns during one-time PyTorch import.
    """
    clean_text = str(text or "").strip()
    if not clean_text:
        return None

    cache_key = clean_text[:500].lower()
    if cache_key in _QUERY_VEC_CACHE:
        return _QUERY_VEC_CACHE[cache_key]

    result_vec: Optional[List[float]] = None

    # 1. Primary Unified Neural Space: Local all-MiniLM-L6-v2 (384-d, offline-capable, zero VRAM)
    st_model = _LOCAL_ST_MODEL
    if st_model is None:
        if allow_cold_import:
            st_model = _load_local_st_model()
        else:
            _trigger_async_prewarm()

    if st_model is not None:
        try:
            vec = st_model.encode(clean_text[:2000], convert_to_numpy=True)
            arr = np.array(vec, dtype=np.float32)
            norm = np.linalg.norm(arr)
            if norm > 1e-9:
                arr = arr / norm
            result_vec = arr.tolist()
        except Exception:
            result_vec = None

    # 2. Gemini API Fallback (when SentenceTransformer is absent, e.g. minimal headless install)
    if result_vec is None and (_LOCAL_ST_UNAVAILABLE or allow_cold_import):
        try:
            from backend.core.gemini_client import get_gemini_client
            client = get_gemini_client()
            if client:
                resp = client.models.embed_content(
                    model=EMBEDDING_MODEL,
                    contents=clean_text[:2000]
                )
                if resp and resp.embeddings and len(resp.embeddings) > 0:
                    values = resp.embeddings[0].values
                    arr = np.array(values, dtype=np.float32)
                    norm = np.linalg.norm(arr)
                    if norm > 1e-9:
                        arr = arr / norm
                    result_vec = arr.tolist()
        except Exception:
            pass

    # 3. Deterministic Offline Fallback when neither ST nor Gemini is available
    if result_vec is None:
        try:
            from sklearn.feature_extraction.text import HashingVectorizer
            hv = HashingVectorizer(n_features=512, norm='l2', alternate_sign=False)
            result_vec = hv.transform([clean_text]).toarray()[0].tolist()
        except Exception:
            vec = np.zeros(128, dtype=np.float32)
            for token in clean_text.lower().split():
                h = hash(token) % 128
                vec[h] += 1.0
            norm = np.linalg.norm(vec)
            if norm > 1e-9:
                vec = vec / norm
            result_vec = vec.tolist()

    if result_vec is not None:
        if len(_QUERY_VEC_CACHE) >= _QUERY_VEC_CACHE_MAX:
            _QUERY_VEC_CACHE.pop(next(iter(_QUERY_VEC_CACHE)))
        _QUERY_VEC_CACHE[cache_key] = result_vec

    return result_vec


def vector_cosine_similarity(vec1: Optional[List[float]], vec2: Optional[List[float]]) -> float:
    """Computes cosine similarity between two embeddings ONLY when in matching vector spaces."""
    if not vec1 or not vec2:
        return 0.0
    try:
        a = np.array(vec1, dtype=np.float32)
        b = np.array(vec2, dtype=np.float32)
        # Never slice/compare vectors from different embedding spaces (e.g., 384-d vs 3072-d)
        if a.shape != b.shape:
            return 0.0
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a < 1e-9 or norm_b < 1e-9:
            return 0.0
        sim = float(np.dot(a, b) / (norm_a * norm_b))
        return float(np.clip(sim, -1.0, 1.0))
    except Exception:
        return 0.0


# =========================================================================
# 2. MULTI-HOP KNOWLEDGE GRAPH REASONING (NETWORKX)
# =========================================================================

def build_networkx_graph(conn: Optional[sqlite3.Connection] = None) -> nx.DiGraph:
    """Constructs an in-memory directed NetworkX graph of all active entities and relations."""
    G = nx.DiGraph()
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        entities = conn.execute("SELECT id, name, entity_type, attributes, importance FROM entities").fetchall()
        for ent in entities:
            attrs = json.loads(ent["attributes"] or "{}") if isinstance(ent["attributes"], str) else (ent["attributes"] or {})
            G.add_node(
                ent["name"],
                id=ent["id"],
                entity_type=ent["entity_type"],
                attributes=attrs,
                importance=ent["importance"]
            )

        relations = conn.execute("""
            SELECT r.id, s.name as source_name, r.relation, t.name as target_name, r.confidence
            FROM relations r
            JOIN entities s ON r.source_id = s.id
            JOIN entities t ON r.target_id = t.id
            WHERE r.is_active = 1
        """).fetchall()

        for rel in relations:
            G.add_edge(
                rel["source_name"],
                rel["target_name"],
                relation=rel["relation"],
                confidence=rel["confidence"],
                id=rel["id"]
            )
    finally:
        if should_close:
            conn.close()

    return G


def query_multi_hop_relations(start_entity: str, max_hops: int = 3, conn: Optional[sqlite3.Connection] = None) -> List[Dict[str, Any]]:
    """
    Traverses the Semantic Knowledge Graph up to `max_hops` to uncover indirect connections.
    E.g. User -> Varun -> AWS -> Cloud Migration
    """
    clean_start = str(start_entity).strip()
    if not clean_start:
        return []

    G = build_networkx_graph(conn=conn)

    matched_node = next((n for n in G.nodes if n.lower() == clean_start.lower()), None)
    if not matched_node:
        return []

    results = []
    visited_paths = set()

    for target in G.nodes:
        if target == matched_node:
            continue
        try:
            for path in nx.all_simple_paths(G, source=matched_node, target=target, cutoff=max_hops):
                path_tuple = tuple(path)
                if path_tuple in visited_paths:
                    continue
                visited_paths.add(path_tuple)

                rel_steps = []
                for i in range(len(path) - 1):
                    u, v = path[i], path[i+1]
                    edge_data = G.get_edge_data(u, v) or {}
                    rel_name = edge_data.get("relation", "connected_to")
                    rel_steps.append(rel_name)

                chain_repr = " -> ".join([f"{path[i]} ({rel_steps[i]})" for i in range(len(rel_steps))]) + f" -> {path[-1]}"
                results.append({
                    "start": matched_node,
                    "target": target,
                    "hops": len(path) - 1,
                    "path": path,
                    "relations": rel_steps,
                    "chain": chain_repr
                })
        except Exception:
            continue

    results.sort(key=lambda x: x["hops"])
    return results[:15]


def find_entity_path(source: str, target: str, max_hops: int = 4, conn: Optional[sqlite3.Connection] = None) -> List[Dict[str, Any]]:
    """
    Finds direct or indirect connecting reasoning paths between two entities.
    Supports both directed paths and undirected multi-relational bridges.
    """
    G = build_networkx_graph(conn=conn)
    s_clean = str(source).strip()
    t_clean = str(target).strip()

    s_node = next((n for n in G.nodes if n.lower() == s_clean.lower()), None)
    t_node = next((n for n in G.nodes if n.lower() == t_clean.lower()), None)

    if not s_node or not t_node:
        return []

    paths = []
    # 1. Directed paths
    try:
        for p in nx.all_simple_paths(G, source=s_node, target=t_node, cutoff=max_hops):
            rel_steps = [G.get_edge_data(p[i], p[i+1]).get("relation", "rel") for i in range(len(p)-1)]
            paths.append({
                "source": s_node,
                "target": t_node,
                "path": p,
                "relations": rel_steps,
                "chain": " -> ".join([f"{p[i]} ({rel_steps[i]})" for i in range(len(rel_steps))]) + f" -> {p[-1]}",
                "hops": len(p) - 1,
                "directed": True
            })
    except Exception:
        pass

    # 2. Undirected paths (bridges)
    if not paths:
        try:
            UG = G.to_undirected()
            for p in nx.all_simple_paths(UG, source=s_node, target=t_node, cutoff=max_hops):
                rel_steps = []
                for i in range(len(p) - 1):
                    u, v = p[i], p[i+1]
                    d = G.get_edge_data(u, v) or G.get_edge_data(v, u) or {}
                    rel_steps.append(d.get("relation", "connected_to"))
                paths.append({
                    "source": s_node,
                    "target": t_node,
                    "path": p,
                    "relations": rel_steps,
                    "chain": " -- ".join([f"{p[i]} [{rel_steps[i]}]" for i in range(len(rel_steps))]) + f" -- {p[-1]}",
                    "hops": len(p) - 1,
                    "directed": False
                })
        except Exception:
            pass

    paths.sort(key=lambda x: x["hops"])
    return paths[:5]


def get_graph_analytics() -> Dict[str, Any]:
    """Computes graph structural metrics (central hubs, degree distribution, density)."""
    G = build_networkx_graph()
    num_nodes = G.number_of_nodes()
    num_edges = G.number_of_edges()

    centrality = nx.degree_centrality(G) if num_nodes > 0 else {}
    top_hubs = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "node_count": num_nodes,
        "edge_count": num_edges,
        "density": round(nx.density(G), 4) if num_nodes > 1 else 0.0,
        "top_hubs": [{"entity": k, "centrality": round(v, 3)} for k, v in top_hubs]
    }


# =========================================================================
# 3. SEMANTIC KNOWLEDGE GRAPH (ENTITIES & RELATIONS)
# =========================================================================

def store_entity(name: str, entity_type: str, attributes: Optional[Dict[str, Any]] = None, importance: int = 5, conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    """Stores or updates an entity in the Semantic Knowledge Graph."""
    clean_name = str(name).strip()
    if not clean_name:
        return {"status": "error", "error": "Entity name cannot be empty."}

    attr_json = json.dumps(attributes or {}, ensure_ascii=False)
    now = datetime.datetime.utcnow().isoformat()

    def _do_store(c: sqlite3.Connection):
        cursor = c.cursor()
        existing_row = c.execute(
            "SELECT id, entity_type, attributes FROM entities WHERE name = ? COLLATE NOCASE",
            (clean_name,),
        ).fetchone()

        final_type = entity_type
        merged_attrs = dict(attributes or {})
        if existing_row:
            old_type = existing_row["entity_type"] or "general"
            weak_override_types = {
                "general", "fact", "configuration", "debugging", "task_context",
                "conversation", "task_episode", "user_note", "user_instruction", "verified_research",
            }
            if old_type != "general" and final_type in weak_override_types:
                final_type = old_type
            try:
                old_attrs = json.loads(existing_row["attributes"] or "{}")
                if isinstance(old_attrs, dict):
                    merged_attrs = {**old_attrs, **merged_attrs}
            except Exception:
                pass

        final_attr_json = json.dumps(merged_attrs, ensure_ascii=False)
        cursor.execute("""
            INSERT INTO entities (name, entity_type, attributes, importance, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                entity_type = excluded.entity_type,
                attributes = excluded.attributes,
                importance = MAX(entities.importance, excluded.importance),
                updated_at = excluded.updated_at
        """, (clean_name, final_type, final_attr_json, importance, now, now))
        entity_id = cursor.lastrowid or c.execute("SELECT id FROM entities WHERE name = ?", (clean_name,)).fetchone()[0]
        _index_fts(c, f"{clean_name} {final_type} {final_attr_json}", "entity", clean_name, entity_id)
        return entity_id

    if conn is not None:
        entity_id = _do_store(conn)
    else:
        with get_db_connection() as c:
            entity_id = _do_store(c)
            c.commit()

    return {
        "status": "success",
        "entity_id": entity_id,
        "name": clean_name,
        "type": entity_type,
        "attributes": attributes or {}
    }


def store_relation(source_name: str, relation: str, target_name: str, confidence: float = 1.0, conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    """Creates a directed relationship between two entities."""
    s_name = str(source_name).strip()
    t_name = str(target_name).strip()
    rel = str(relation).strip().lower().replace(" ", "_")

    def _do_rel(c: sqlite3.Connection):
        s_row = c.execute("SELECT id FROM entities WHERE name = ? COLLATE NOCASE", (s_name,)).fetchone()
        if not s_row:
            store_entity(s_name, "general", conn=c)
            s_row = c.execute("SELECT id FROM entities WHERE name = ? COLLATE NOCASE", (s_name,)).fetchone()

        t_row = c.execute("SELECT id FROM entities WHERE name = ? COLLATE NOCASE", (t_name,)).fetchone()
        if not t_row:
            store_entity(t_name, "general", conn=c)
            t_row = c.execute("SELECT id FROM entities WHERE name = ? COLLATE NOCASE", (t_name,)).fetchone()

        s_id = s_row[0]
        t_id = t_row[0]

        c.execute("""
            INSERT INTO relations (source_id, relation, target_id, confidence, is_active)
            VALUES (?, ?, ?, ?, 1)
            ON CONFLICT(source_id, relation, target_id) DO UPDATE SET
                confidence = excluded.confidence,
                is_active = 1
        """, (s_id, rel, t_id, confidence))

    if conn is not None:
        _do_rel(conn)
    else:
        with get_db_connection() as c:
            _do_rel(c)
            c.commit()

    return {
        "status": "success",
        "source": s_name,
        "relation": rel,
        "target": t_name
    }


# =========================================================================
# 4. EPISODIC & PROCEDURAL MEMORY WITH DENSE EMBEDDINGS
# =========================================================================

def store_episodic_event(event_summary: str, details: str = "", salience: int = 5, tags: str = "", conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    """Records an event or past experience with a timestamp in Episodic Memory."""
    now = datetime.datetime.utcnow().isoformat()
    def _do_event(c: sqlite3.Connection):
        cursor = c.cursor()
        cursor.execute("""
            INSERT INTO episodic_events (event_summary, details, salience, tags, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (event_summary, details, salience, tags, now))
        event_id = cursor.lastrowid
        _index_fts(c, f"{event_summary} {details} {tags}", "episodic", tags, event_id)
        return event_id

    if conn is not None:
        event_id = _do_event(conn)
    else:
        with get_db_connection() as c:
            event_id = _do_event(c)
            c.commit()

    return {"status": "success", "event_id": event_id, "summary": event_summary, "timestamp": now}


def store_procedural_habit(category: str, habit_key: str, rule_text: str, strength: float = 1.0, conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    """Stores a procedural habit, user workflow preference, or default operational rule."""
    now = datetime.datetime.utcnow().isoformat()
    def _do_habit(c: sqlite3.Connection):
        cursor = c.cursor()
        cursor.execute("""
            INSERT INTO procedural_habits (category, habit_key, rule_text, strength, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(habit_key) DO UPDATE SET
                rule_text = excluded.rule_text,
                strength = excluded.strength,
                updated_at = excluded.updated_at
        """, (category, habit_key, rule_text, strength, now))
        habit_id = cursor.lastrowid or c.execute("SELECT id FROM procedural_habits WHERE habit_key = ?", (habit_key,)).fetchone()[0]
        _index_fts(c, f"{category} {habit_key} {rule_text}", "procedural", habit_key, habit_id)
        return habit_id

    if conn is not None:
        habit_id = _do_habit(conn)
    else:
        with get_db_connection() as c:
            habit_id = _do_habit(c)
            c.commit()

    return {"status": "success", "habit_id": habit_id, "key": habit_key, "rule": rule_text}


def remember_fact(content: str, category: str = "fact", importance: int = 5,
                  entity: Optional[str] = None, relation: Optional[str] = None, target: Optional[str] = None,
                  dedup: bool = True) -> Dict[str, Any]:
    """
    Unified ingestion API: Stores raw knowledge with dense vector embedding and updates entities/relations.
    Deduplicates near-identical active memories cleanly to prevent bloat.
    """
    clean_content = str(content).strip()
    if not clean_content:
        return {"status": "error", "error": "Memory content cannot be empty."}

    # Generate dense semantic vector embedding (384-d unified neural space)
    dense_vec = generate_dense_embedding(clean_content, allow_cold_import=True)
    vec_json = json.dumps(dense_vec) if dense_vec else None

    now = datetime.datetime.utcnow().isoformat()
    norm_new = re.sub(r"[^a-z0-9]", "", clean_content.lower())

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Check semantic / exact deduplication against active raw memories
        existing_id = None
        if dedup and norm_new:
            active_rows = cursor.execute(
                "SELECT id, content, embedding, importance FROM raw_memories WHERE is_active = 1 ORDER BY id DESC LIMIT 120"
            ).fetchall()
            for r in active_rows:
                norm_old = re.sub(r"[^a-z0-9]", "", (r["content"] or "").lower())
                if norm_new == norm_old:
                    existing_id = r["id"]
                    break
                if dense_vec and r["embedding"]:
                    try:
                        cos = vector_cosine_similarity(dense_vec, json.loads(r["embedding"]))
                        if cos >= 0.91:
                            existing_id = r["id"]
                            break
                    except Exception:
                        pass

        if existing_id is not None:
            cursor.execute(
                "UPDATE raw_memories SET importance = MAX(importance, ?), last_accessed_at = ?, access_count = access_count + 1 WHERE id = ?",
                (importance, now, existing_id),
            )
            raw_id = existing_id
        else:
            cursor.execute("""
                INSERT INTO raw_memories (category, content, importance, embedding, is_active, created_at, last_accessed_at, access_count)
                VALUES (?, ?, ?, ?, 1, ?, ?, 0)
            """, (category, clean_content, importance, vec_json, now, now))
            raw_id = cursor.lastrowid

        entity_names = ""
        if entity:
            entity_names = entity
            store_entity(entity, category, {"note": clean_content[:240]}, importance=importance, conn=conn)
            if relation and target:
                store_relation(entity, relation, target, conn=conn)
                entity_names += f" {target}"

        if existing_id is None:
            _index_fts(conn, clean_content, category, entity_names, raw_id)
        conn.commit()

    return {
        "status": "success",
        "memory_id": raw_id,
        "deduplicated": existing_id is not None,
        "content": clean_content,
        "category": category,
        "importance": importance,
        "has_embedding": dense_vec is not None
    }


def _index_fts(conn: sqlite3.Connection, text: str, category: str, entity_names: str, rowid: int):
    """Indexes text into SQLite FTS5 table."""
    try:
        clean_text = re.sub(r'[\'\"*^~]', ' ', text)
        conn.execute("""
            INSERT INTO memories_fts (content, category, entity_names, content_rowid)
            VALUES (?, ?, ?, ?)
        """, (clean_text, category, entity_names, rowid))
    except Exception:
        pass


# =========================================================================
# 5. COGNITIVE RECALL & HYBRID SCORER (4 FUSED RETRIEVAL STREAMS)
# =========================================================================

def recall_memory(query: str, category: Optional[str] = None, top_k: int = 5, allow_cold_import: bool = False) -> List[Dict[str, Any]]:
    """
    Cognitive Hybrid Recall:
    Combines:
    1. Entity Recognition & Bidirectional Multi-Hop Expansion (NetworkX)
    2. Dense Semantic Vector Cosine Similarity (Conceptual Analogy / 0 Shared Words)
    3. Procedural Habits & Preferences
    4. FTS5 BM25 Search + Recent Episodic Recall
    """
    clean_query = str(query or "").strip()
    if not clean_query:
        return []

    results: List[Dict[str, Any]] = []
    seen_contents = set()
    matched_raw_ids: List[int] = []

    # Pre-generate query vector non-blockingly on hot chat reads
    q_vec = generate_dense_embedding(clean_query, allow_cold_import=allow_cold_import)
    norm_q = re.sub(r"[^a-z0-9]+", "", clean_query.lower())

    with get_db_connection() as conn:
        # Stream 1: Direct Entity Match & Bidirectional Multi-Hop Neighborhood Expansion
        entities = conn.execute("SELECT id, name, entity_type, attributes, importance FROM entities").fetchall()
        for ent in entities:
            ent_name = ent["name"]
            if len(ent_name.strip()) < 2:
                continue
            norm_ent = re.sub(r"[^a-z0-9]+", "", ent_name.lower())
            matched_word = bool(re.search(rf"\b{re.escape(ent_name)}\b", clean_query, re.IGNORECASE))
            matched_compact = bool(len(norm_ent) >= 4 and norm_ent in norm_q)
            if matched_word or matched_compact:
                attrs = json.loads(ent["attributes"] or "{}") if isinstance(ent["attributes"], str) else (ent["attributes"] or {})

                # Outgoing & Incoming 1-hop relations (bidirectional neural associations)
                out_rows = conn.execute("""
                    SELECT r.relation, e.name as other_name
                    FROM relations r
                    JOIN entities e ON r.target_id = e.id
                    WHERE r.source_id = ? AND r.is_active = 1
                """, (ent["id"],)).fetchall()
                in_rows = conn.execute("""
                    SELECT r.relation, e.name as other_name
                    FROM relations r
                    JOIN entities e ON r.source_id = e.id
                    WHERE r.target_id = ? AND r.is_active = 1
                """, (ent["id"],)).fetchall()

                relations_info = [f"{r['relation']} -> {r['other_name']}" for r in out_rows]
                relations_info.extend(f"{r['other_name']} -> {r['relation']} {ent_name}" for r in in_rows[:5])

                # Multi-hop inferences (via NetworkX)
                multi_hop_chains = query_multi_hop_relations(ent_name, max_hops=3, conn=conn)
                deductions = [m["chain"] for m in multi_hop_chains[:3]]

                text_repr = f"{ent_name} ({ent['entity_type']}): {json.dumps(attrs)} {', '.join(relations_info[:6])}"
                if text_repr not in seen_contents:
                    seen_contents.add(text_repr)
                    results.append({
                        "source": "knowledge_graph",
                        "entity": ent_name,
                        "type": ent["entity_type"],
                        "attributes": attrs,
                        "relations": relations_info[:8],
                        "deductions": deductions,
                        "content": text_repr,
                        "score": 1.0,
                        "importance": ent["importance"]
                    })

        # Stream 2: Dense Semantic Vector Cosine Similarity
        if q_vec:
            raw_rows = conn.execute("""
                SELECT id, category, content, importance, embedding
                FROM raw_memories
                WHERE is_active = 1 AND embedding IS NOT NULL
            """).fetchall()

            for r in raw_rows:
                if category and r["category"] != category:
                    continue
                cnt = r["content"]
                if cnt in seen_contents:
                    continue
                try:
                    mem_vec = json.loads(r["embedding"])
                    cos = vector_cosine_similarity(q_vec, mem_vec)
                    # Calibrated threshold for 384-d all-MiniLM-L6-v2 (~0.40+ = strong conceptual similarity)
                    if cos >= 0.40:
                        seen_contents.add(cnt)
                        matched_raw_ids.append(r["id"])
                        norm_score = round(min(1.0, cos * 1.45), 3)
                        results.append({
                            "source": "dense_semantic_vector",
                            "category": r["category"],
                            "content": cnt,
                            "cosine_similarity": round(cos, 4),
                            "score": norm_score,
                            "importance": r["importance"]
                        })
                except Exception:
                    continue

        # Stream 3: Procedural Habits Match
        habits = conn.execute("SELECT category, habit_key, rule_text, strength FROM procedural_habits").fetchall()
        for h in habits:
            key_words = [w for w in re.split(r'[_ -]', h["habit_key"].lower()) if len(w) > 2]
            if any(w in clean_query.lower() for w in key_words) or any(w in h["rule_text"].lower() for w in clean_query.lower().split() if len(w) > 3):
                if h["rule_text"] not in seen_contents:
                    seen_contents.add(h["rule_text"])
                    results.append({
                        "source": "procedural",
                        "category": h["category"],
                        "key": h["habit_key"],
                        "content": h["rule_text"],
                        "score": 0.85 * h["strength"],
                        "importance": 8
                    })

        # Stream 4: SQLite FTS5 BM25 Literal Search
        clean_search = re.sub(r'[^a-zA-Z0-9\s]', ' ', clean_query).strip()
        search_terms = [t for t in clean_search.split() if len(t) > 2]
        if search_terms:
            fts_query = " OR ".join(search_terms[:6])
            try:
                fts_rows = conn.execute("""
                    SELECT content, category, entity_names, rank
                    FROM memories_fts
                    WHERE memories_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                """, (fts_query, top_k * 2)).fetchall()

                for f_row in fts_rows:
                    cnt = f_row["content"]
                    if cnt not in seen_contents:
                        seen_contents.add(cnt)
                        fts_score = max(0.2, 1.0 / (1.0 + abs(float(f_row["rank"]))))
                        results.append({
                            "source": "fts_recall",
                            "category": f_row["category"],
                            "content": cnt,
                            "score": round(fts_score, 3),
                            "importance": 5
                        })
            except Exception:
                pass

        # Update access count & recency only on actually recalled raw memories
        if matched_raw_ids:
            placeholders = ",".join("?" for _ in matched_raw_ids)
            conn.execute(
                f"UPDATE raw_memories SET access_count = access_count + 1, last_accessed_at = CURRENT_TIMESTAMP WHERE id IN ({placeholders})",
                matched_raw_ids,
            )
            conn.commit()

    # Sort descending by composite score & importance
    results.sort(key=lambda x: (x.get("score", 0), x.get("importance", 5)), reverse=True)
    return results[:top_k]


# =========================================================================
# 6. AUTONOMOUS SLEEP-CYCLE CONSOLIDATION
# =========================================================================

def run_sleep_cycle_consolidation() -> Dict[str, Any]:
    """
    Autonomous Sleep-Cycle Consolidation:
    1. Semantic Deduplication: Merges near-identical facts (cosine >= 0.88 or text match)
       into canonical entries and deactivates superseded duplicates.
    2. Contradiction Resolution & Superseding: Resolves conflicting single-target relations
       (e.g., preferred_browser: Firefox vs Brave -> keeps newest active).
    3. Procedural Habit Synthesis: Synthesizes high-order procedural rules from recurring observations.
    4. Records consolidation audit trail in `consolidation_logs`.
    """
    now = datetime.datetime.utcnow().isoformat()
    dedup_count = 0
    superseded_count = 0
    habits_synthesized = 0
    actions_taken = []

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Step 1: Semantic Deduplication of Raw Memories
        raw_rows = cursor.execute("""
            SELECT id, content, category, importance, embedding, created_at
            FROM raw_memories
            WHERE is_active = 1
            ORDER BY importance DESC, id ASC
        """).fetchall()

        # Determine target unified vector dimension (e.g. 384 for all-MiniLM-L6-v2)
        probe_vec = generate_dense_embedding("dimension_probe", allow_cold_import=True)
        target_dim = len(probe_vec) if probe_vec else 0

        active_memories = []
        for r in raw_rows:
            emb = None
            if r["embedding"]:
                try:
                    emb = json.loads(r["embedding"])
                except Exception:
                    emb = None
            if (not emb) or (target_dim and len(emb) != target_dim):
                emb = generate_dense_embedding(r["content"], allow_cold_import=True)
                if emb:
                    cursor.execute("UPDATE raw_memories SET embedding = ? WHERE id = ?", (json.dumps(emb), r["id"]))
            active_memories.append({
                "id": r["id"],
                "content": r["content"],
                "category": r["category"],
                "importance": r["importance"],
                "embedding": emb,
                "created_at": r["created_at"]
            })

        superseded_ids = set()
        for i in range(len(active_memories)):
            m_a = active_memories[i]
            if m_a["id"] in superseded_ids:
                continue

            for j in range(i + 1, len(active_memories)):
                m_b = active_memories[j]
                if m_b["id"] in superseded_ids:
                    continue

                norm_a = re.sub(r'[^a-zA-Z0-9]', '', m_a["content"].lower())
                norm_b = re.sub(r'[^a-zA-Z0-9]', '', m_b["content"].lower())
                is_text_match = (norm_a == norm_b) or (len(norm_a) > 10 and (norm_a in norm_b or norm_b in norm_a))

                cos_sim = 0.0
                if m_a["embedding"] and m_b["embedding"]:
                    cos_sim = vector_cosine_similarity(m_a["embedding"], m_b["embedding"])

                if is_text_match or cos_sim >= 0.88:
                    canonical_id = m_a["id"]
                    dup_id = m_b["id"]
                    superseded_ids.add(dup_id)
                    dedup_count += 1

                    cursor.execute("""
                        UPDATE raw_memories
                        SET is_active = 0, superseded_by = ?
                        WHERE id = ?
                    """, (canonical_id, dup_id))

                    actions_taken.append(f"Deduplicated #{dup_id} into canonical #{canonical_id} (cosine={cos_sim:.2f})")

        # Step 2: Relation Contradiction Resolution
        single_target_relations = {
            "preferred_browser", "preferred_editor", "primary_gpu", "marital_status",
            "current_residence", "primary_phone", "father", "mother"
        }
        for rel_type in single_target_relations:
            dups = cursor.execute("""
                SELECT source_id, COUNT(*) as cnt
                FROM relations
                WHERE relation = ? AND is_active = 1
                GROUP BY source_id
                HAVING cnt > 1
            """, (rel_type,)).fetchall()

            for d in dups:
                s_id = d["source_id"]
                records = cursor.execute("""
                    SELECT id, target_id, created_at
                    FROM relations
                    WHERE source_id = ? AND relation = ? AND is_active = 1
                    ORDER BY created_at DESC, id DESC
                """, (s_id, rel_type)).fetchall()

                if len(records) > 1:
                    keeper = records[0]
                    for stale in records[1:]:
                        cursor.execute("UPDATE relations SET is_active = 0 WHERE id = ?", (stale["id"],))
                        superseded_count += 1
                        actions_taken.append(f"Resolved relation conflict on source #{s_id}: kept latest relation #{keeper['id']}, archived #{stale['id']}")

        # Step 3: Procedural Habit Synthesis from Recurring Patterns
        commute_memories = [m for m in active_memories if m["id"] not in superseded_ids and any(k in m["content"].lower() for k in ["commute", "metro", "bus", "drive", "transit", "indiranagar"])]
        if commute_memories:
            best_commute = max(commute_memories, key=lambda x: x["importance"])
            rule_text = f"User commute habit: {best_commute['content']}"
            cursor.execute("""
                INSERT INTO procedural_habits (category, habit_key, rule_text, strength, updated_at)
                VALUES ('routine', 'daily_commute', ?, 0.95, ?)
                ON CONFLICT(habit_key) DO UPDATE SET rule_text = excluded.rule_text, strength = excluded.strength, updated_at = excluded.updated_at
            """, (rule_text, now))
            habits_synthesized += 1
            actions_taken.append(f"Synthesized procedural habit 'daily_commute' from memory #{best_commute['id']}")

        # Step 4: Record Consolidation Log
        summary = "; ".join(actions_taken) if actions_taken else "Memory graph fully consolidated and aligned. No redundancies."
        cursor.execute("""
            INSERT INTO consolidation_logs (timestamp, actions_summary, deduplicated_count, pruned_count, habits_synthesized)
            VALUES (?, ?, ?, ?, ?)
        """, (now, summary, dedup_count, superseded_count, habits_synthesized))

        conn.commit()

    return {
        "status": "success",
        "consolidated_at": now,
        "deduplicated_count": dedup_count,
        "superseded_count": superseded_count,
        "habits_synthesized": habits_synthesized,
        "actions_taken": actions_taken
    }


# =========================================================================
# 7. CONTEXT AUTO-INJECTION (FOR SYSTEM PROMPT)
# =========================================================================

def get_injected_context(user_prompt: str, max_chars: int = 1800) -> str:
    """
    Fast query to construct the <jarvis_memory> block for prompt injection.
    Includes multi-hop graph deductions and high-confidence semantic vector matches.
    """
    memories = recall_memory(user_prompt, top_k=6, allow_cold_import=False)
    if not memories:
        return ""

    lines = ["<jarvis_memory>", "# Associative Knowledge Graph & Semantic Recall:"]

    contacts = []
    preferences = []
    general_facts = []
    deductions = []

    for m in memories:
        src = m.get("source")
        if src == "knowledge_graph":
            ent = m.get("entity")
            attrs = m.get("attributes", {})
            rels = m.get("relations", [])
            multi_deduct = m.get("deductions", [])

            details = []
            if "phone" in attrs: details.append(f"Phone: {attrs['phone']}")
            if "whatsapp_name" in attrs: details.append(f"WhatsApp: {attrs['whatsapp_name']}")
            if "full_name" in attrs: details.append(f"Name: {attrs['full_name']}")
            if rels: details.append(f"Links: {'; '.join(rels[:5])}")

            line = f"- {ent} ({m.get('type', 'entity')}): {', '.join(details) if details else json.dumps(attrs)[:180]}"
            if m.get("type") == "person" or "contact" in str(attrs).lower():
                contacts.append(line)
            else:
                general_facts.append(line)

            if multi_deduct:
                for d in multi_deduct[:2]:
                    deductions.append(f"- Chain: {d}")

        elif src == "procedural":
            preferences.append(f"- Habit ({m.get('key')}): {m.get('content')}")
        else:
            sim = m.get("cosine_similarity")
            sim_tag = f" [sim={sim:.2f}]" if sim is not None else ""
            general_facts.append(f"- [{m.get('category', 'fact')}{sim_tag}] {str(m.get('content', ''))[:260]}")

    if contacts:
        lines.append("## Directory & Contacts:")
        lines.extend(contacts)
    if preferences:
        lines.append("## Preferences & Habits:")
        lines.extend(preferences)
    if deductions:
        lines.append("## Multi-Hop Connections:")
        lines.extend(deductions[:4])
    if general_facts:
        lines.append("## Connected Memory & Past Work:")
        lines.extend(general_facts[:6])

    lines.append("</jarvis_memory>")
    rendered = "\n".join(lines)
    if len(rendered) > max_chars:
        rendered = rendered[: max_chars - 24] + "\n</jarvis_memory>"
    return rendered


# =========================================================================
# 8. AUTONOMOUS REFLECTION, TASK EPISODES & GRAPH LEARNING
# =========================================================================

_TECH_ENTITY_CATALOG: Dict[str, Tuple[str, str]] = {
    "fastapi": ("FastAPI", "framework"),
    "flask": ("Flask", "framework"),
    "django": ("Django", "framework"),
    "react": ("React", "framework"),
    "next.js": ("Next.js", "framework"),
    "nextjs": ("Next.js", "framework"),
    "vite": ("Vite", "tool"),
    "tailwind": ("Tailwind CSS", "framework"),
    "python": ("Python", "language"),
    "javascript": ("JavaScript", "language"),
    "typescript": ("TypeScript", "language"),
    "sqlite": ("SQLite", "database"),
    "postgres": ("PostgreSQL", "database"),
    "postgresql": ("PostgreSQL", "database"),
    "mongodb": ("MongoDB", "database"),
    "redis": ("Redis", "database"),
    "docker": ("Docker", "platform"),
    "ollama": ("Ollama", "runtime"),
    "pytorch": ("PyTorch", "framework"),
    "torch": ("PyTorch", "framework"),
    "serpapi": ("SerpAPI", "service"),
    "duckduckgo": ("DuckDuckGo", "service"),
    "easyocr": ("EasyOCR", "tool"),
    "pymupdf": ("PyMuPDF", "tool"),
    "playwright": ("Playwright", "tool"),
    "networkx": ("NetworkX", "tool"),
    "uvicorn": ("Uvicorn", "runtime"),
    "cors": ("CORS", "protocol"),
    "oauth": ("OAuth", "protocol"),
    "jwt": ("JWT", "protocol"),
    "sse": ("Server-Sent Events", "protocol"),
    "websocket": ("WebSockets", "protocol"),
    "rag": ("Vector RAG", "architecture"),
    "qlora": ("QLoRA", "architecture"),
    "unleash": ("Unleash-Agent", "project"),
    "gemini": ("Gemini API", "service"),
    "openai": ("OpenAI API", "service"),
    "claude": ("Claude API", "service"),
    "dolphin3": ("Dolphin3 8B", "model"),
    "whisper": ("Whisper STT", "model"),
}


def _detect_tech_entities(text: str) -> List[Tuple[str, str]]:
    """Extracts known canonical technical/domain entities from natural text."""
    found: List[Tuple[str, str]] = []
    seen: Set[str] = set()
    low = (text or "").lower()
    for token, (canon_name, etype) in _TECH_ENTITY_CATALOG.items():
        if re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", low):
            if canon_name not in seen:
                seen.add(canon_name)
                found.append((canon_name, etype))
    return found


def _is_generic_project_name(name: str) -> bool:
    clean = (name or "").strip().lower()
    return not clean or clean in ("default", "default_project", "default_workspace", "project_default", "sandbox")


def extract_memories_from_turn(
    user_msg: str,
    assistant_msg: str = "",
    project_name: str = "",
    mode: str = "chat",
) -> List[Dict[str, Any]]:
    """
    Autonomous Reflection & Associative Graph Extraction:
    Learns contacts, preferences, technical stack nodes, project links, bug fixes,
    configurations, and substantive turn summaries into jarvis_memory.db.
    """
    extracted: List[Dict[str, Any]] = []
    u_text = str(user_msg or "").strip()
    a_text = str(assistant_msg or "").strip()
    if not u_text:
        return extracted

    combined = f"{u_text}\n{a_text[:800]}"
    proj_clean = str(project_name or "").strip()
    has_named_project = not _is_generic_project_name(proj_clean)

    # Pattern A: Explicit "remember that..." / "note that..."
    m_remember = re.search(r"\b(?:remember\s+that|remember|note\s+that|keep\s+in\s+mind\s+that)\s+(.+)", u_text, re.IGNORECASE)
    if m_remember:
        fact = m_remember.group(1).strip().rstrip(".!")
        if len(fact) >= 4:
            res = remember_fact(fact, category="user_instruction", importance=9)
            extracted.append(res)

    # Pattern B: Contact / Relationship definitions
    m_rel1 = re.search(r"\bmy\s+(dad|father|mom|mother|brother|sister|wife|husband|boss|manager|friend|colleague)\s+(?:is|name\s+is)\s+([A-Z][a-zA-Z0-9_\s]+)", u_text, re.IGNORECASE)
    if m_rel1:
        rel_type = m_rel1.group(1).lower()
        person_name = m_rel1.group(2).strip().rstrip(".! ")
        store_entity(person_name, "person", {"relation_to_user": rel_type, "whatsapp_name": person_name}, importance=8)
        store_relation("User", rel_type, person_name)
        title_case_rel = rel_type.capitalize()
        store_entity(title_case_rel, "person", {"full_name": person_name, "relation": rel_type}, importance=9)
        store_relation(title_case_rel, "resolves_to", person_name)
        extracted.append({"entity": person_name, "relation": rel_type})

    # Pattern C: Phone number association
    m_phone = re.search(r"([A-Z][a-zA-Z]+)(?:'s)?\s+(?:number|phone|mobile)\s+is\s+([+\d\s-]{8,15})", u_text, re.IGNORECASE)
    if m_phone:
        p_name = m_phone.group(1).strip()
        p_num = m_phone.group(2).strip()
        store_entity(p_name, "person", {"phone": p_num, "whatsapp_name": p_name}, importance=8)
        extracted.append({"entity": p_name, "phone": p_num})

    # Pattern D: Tool & environment preference
    m_pref = re.search(r"\b(?:i\s+prefer|my\s+favorite|i\s+always\s+use|always\s+use)\s+([a-zA-Z0-9_.\s-]{2,28}?)\s+(?:browser|editor|ide|stack|terminal|framework|database)\b", u_text, re.IGNORECASE)
    if m_pref:
        tool_name = m_pref.group(1).strip()
        if len(tool_name) >= 2 and not re.match(r"^(?:what|which|should|would|could|any|a|the|my|this|that)\b", tool_name, re.IGNORECASE):
            store_procedural_habit("preference", f"pref_{tool_name.lower().replace(' ', '_')}", f"User prefers {tool_name}.", strength=1.0)
            store_entity(tool_name, "tool", {"preferred": True}, importance=7)
            store_relation("User", "prefers", tool_name)
            extracted.append({"habit": tool_name})

    # Pattern E: Tech & Domain Entities + Project Graph Edges
    tech_hits = _detect_tech_entities(combined)
    anchor_entity = proj_clean if has_named_project else "User"

    if has_named_project and tech_hits:
        store_entity(proj_clean, "project", {"last_mode": mode, "topic": u_text[:120]}, importance=7)
        store_relation("User", "worked_on", proj_clean)
        extracted.append({"project": proj_clean})

    for canon_name, etype in tech_hits[:6]:
        store_entity(canon_name, etype, {"last_seen": mode}, importance=6)
        rel_label = "uses" if has_named_project else "works_with"
        store_relation(anchor_entity, rel_label, canon_name)
        extracted.append({"entity": canon_name, "relation": rel_label, "target": anchor_entity})

    # Interconnect co-occurring entities in this turn (e.g. FastAPI <-> CORS or EasyOCR <-> PyMuPDF)
    if len(tech_hits) >= 2:
        primary_tech = tech_hits[0][0]
        for sec_name, _ in tech_hits[1:4]:
            store_relation(primary_tech, "associated_with", sec_name, confidence=0.8)

    # Pattern F: Service ports / endpoints configuration
    port_matches = re.findall(r"\b(?:port|localhost|127\.0\.0\.1)[:\s]+(\d{4,5})\b", u_text, re.IGNORECASE)
    for port in port_matches[:2]:
        port_node = f"Port {port}"
        store_entity(port_node, "endpoint", {"port": port}, importance=6)
        store_relation(anchor_entity, "runs_on", port_node)
        remember_fact(f"{anchor_entity} configured to run on {port_node} ({u_text[:140]}).", category="configuration", importance=7, entity=anchor_entity, relation="runs_on", target=port_node)
        extracted.append({"port": port_node})

    # Pattern G: Bug fixes, root causes, and technical task episodes
    is_bugfix = any(w in u_text.lower() for w in ("fix ", "fixed ", "bug", "error", "cors", "crash", "timeout", "429", "broken", "debug"))
    is_substantive = len(u_text) >= 24 and not re.match(r"^(?:hi|hello|hey|ok|yes|no|thanks|thank you|cool|nice)[.!?\s]*$", u_text, re.IGNORECASE)

    if is_bugfix and a_text:
        fix_summary = f"Troubleshooting/Fix for '{u_text[:110]}': {a_text[:220]}"
        remember_fact(fix_summary, category="debugging", importance=8, entity=tech_hits[0][0] if tech_hits else anchor_entity)
        store_episodic_event(
            event_summary=f"Resolved issue: {u_text[:90]}",
            details=a_text[:300],
            salience=7,
            tags=",".join([t[0] for t in tech_hits[:4]]) or "debugging",
        )
        extracted.append({"bugfix_episode": u_text[:60]})
    elif is_substantive and a_text and len(a_text) >= 40:
        turn_summary = f"User asked ({mode}): {u_text[:130]} | Outcome: {a_text[:210]}"
        remember_fact(
            turn_summary,
            category="task_context" if mode != "chat" else "conversation",
            importance=6 if mode == "chat" else 7,
            entity=tech_hits[0][0] if tech_hits else (proj_clean if has_named_project else None),
        )
        extracted.append({"turn_memory": turn_summary[:60]})

    return extracted


def record_task_episode(
    objective: str,
    summary: str,
    project_name: str = "",
    files: Optional[List[str]] = None,
    tools: Optional[List[str]] = None,
    outcome: str = "completed",
) -> Dict[str, Any]:
    """
    Records a completed agentic coding/execution episode into Episodic Memory,
    Knowledge Graph (Project -> Tech/Files), and Dense Vector RAG.
    """
    clean_obj = str(objective or "").strip()
    clean_sum = str(summary or "").strip()
    proj = str(project_name or "").strip()
    if not clean_obj:
        return {"status": "skipped"}

    has_proj = not _is_generic_project_name(proj)
    node_name = proj if has_proj else (clean_obj[:42].strip() or "Workspace Task")

    tech_hits = _detect_tech_entities(f"{clean_obj}\n{clean_sum}\n{' '.join(files or [])}")
    with get_db_connection() as conn:
        store_entity(
            node_name,
            "project" if has_proj else "task",
            {"objective": clean_obj[:180], "outcome": outcome, "files_count": len(files or [])},
            importance=8,
            conn=conn,
        )
        store_relation("User", "built" if outcome == "completed" else "worked_on", node_name, conn=conn)

        for canon_name, etype in tech_hits[:6]:
            store_entity(canon_name, etype, {"used_in": node_name}, importance=6, conn=conn)
            store_relation(node_name, "uses", canon_name, conn=conn)

        for tool_name in (tools or [])[:4]:
            t_clean = str(tool_name).strip()
            if t_clean:
                store_entity(t_clean, "agent_tool", {"role": "execution"}, importance=5, conn=conn)
                store_relation(node_name, "executed_tool", t_clean, conn=conn)

        files_snippet = f" Files: {', '.join((files or [])[:5])}." if files else ""
        store_episodic_event(
            event_summary=f"Task ({outcome}): {node_name} — {clean_obj[:90]}",
            details=f"{clean_sum[:240]}{files_snippet}",
            salience=8,
            tags=",".join([t[0] for t in tech_hits[:4]] + ([node_name] if has_proj else [])),
            conn=conn,
        )
        conn.commit()

    files_desc = f" Created/edited: {', '.join((files or [])[:5])}." if files else ""
    tech_desc = f" Stack: {', '.join(t[0] for t in tech_hits[:5])}." if tech_hits else ""
    fact_text = f"Completed task in '{node_name}': {clean_obj[:140]}.{tech_desc}{files_desc} Result: {clean_sum[:180]}"
    remember_fact(fact_text, category="task_episode", importance=8, entity=node_name)
    return {"status": "success", "node": node_name, "tech_count": len(tech_hits)}


def record_research_memory(
    objective: str,
    verified_claims: Optional[List[Dict[str, Any]]] = None,
    sources: Optional[List[Dict[str, Any]]] = None,
    summary: str = "",
    project_name: str = "",
) -> Dict[str, Any]:
    """
    Records Verified Research topic, high-authority sources, and verified claims
    into Knowledge Graph and Dense Vector RAG so research accumulates across sessions.
    """
    clean_obj = str(objective or "").strip()
    if not clean_obj:
        return {"status": "skipped"}

    # Clean concise entity name for the research topic
    topic_label = re.sub(r"^(?:research|analyze|compare|verify|fact[- ]?check|investigate)\s+", "", clean_obj, flags=re.IGNORECASE).strip()
    topic_label = re.sub(r"\s+", " ", topic_label)[:52].strip(" .,:-") or "Research Topic"

    tech_hits = _detect_tech_entities(clean_obj)
    v_claims = [c for c in (verified_claims or []) if str(c.get("status", "")).upper() == "VERIFIED"]
    src_list = sources or []

    with get_db_connection() as conn:
        store_entity(
            topic_label,
            "research_topic",
            {"objective": clean_obj[:180], "verified_claims": len(v_claims), "sources": len(src_list)},
            importance=8,
            conn=conn,
        )
        store_relation("User", "researched", topic_label, conn=conn)

        for canon_name, etype in tech_hits[:4]:
            store_entity(canon_name, etype, {}, importance=6, conn=conn)
            store_relation(topic_label, "analyzes", canon_name, conn=conn)

        for src in src_list[:4]:
            loc = str(src.get("location") or src.get("title") or "").strip()
            dom = str(src.get("domain") or "").strip()
            src_node = dom if dom else Path(loc).name[:40]
            if src_node and src_node != "unknown":
                store_entity(src_node, "source", {"authority": src.get("authority_score", 0.5)}, importance=5, conn=conn)
                store_relation(topic_label, "verified_via", src_node, conn=conn)

        store_episodic_event(
            event_summary=f"Verified Research: {topic_label} ({len(v_claims)} verified claims, {len(src_list)} sources)",
            details=summary[:280],
            salience=8,
            tags="verified_research," + ",".join(t[0] for t in tech_hits[:3]),
            conn=conn,
        )
        conn.commit()

    # Store top verified findings in neural vector RAG
    stored_claims = 0
    for vc in v_claims[:3]:
        c_txt = str(vc.get("claim") or "").strip()
        if c_txt:
            remember_fact(
                f"Verified finding on '{topic_label}': {c_txt} (confidence {vc.get('confidence_score', 0)}%)",
                category="verified_research",
                importance=8,
                entity=topic_label,
            )
            stored_claims += 1

    if stored_claims == 0 and summary:
        remember_fact(f"Research summary on '{topic_label}': {summary[:220]}", category="verified_research", importance=7, entity=topic_label)

    return {"status": "success", "topic": topic_label, "stored_claims": stored_claims}


# =========================================================================
# 9. MANAGEMENT & INSPECTOR APIS
# =========================================================================

def list_all_memories(search: str = "", category: str = "", limit: int = 120) -> Dict[str, Any]:
    """Retrieves entities, relations, habits, episodes, raw summaries, and graph analytics."""
    graph_limit = max(limit, 120)
    with get_db_connection() as conn:
        entities = [dict(row) for row in conn.execute("SELECT * FROM entities ORDER BY importance DESC, updated_at DESC LIMIT ?", (graph_limit,)).fetchall()]
        relations = [dict(row) for row in conn.execute("""
            SELECT r.id, s.name as source_name, r.relation, t.name as target_name, r.confidence, r.is_active, r.created_at
            FROM relations r
            JOIN entities s ON r.source_id = s.id
            JOIN entities t ON r.target_id = t.id
            WHERE r.is_active = 1
            ORDER BY r.created_at DESC LIMIT ?
        """, (graph_limit * 2,)).fetchall()]
        habits = [dict(row) for row in conn.execute("SELECT * FROM procedural_habits ORDER BY strength DESC LIMIT ?", (limit,)).fetchall()]
        episodic = [dict(row) for row in conn.execute("SELECT * FROM episodic_events ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()]
        raw = [dict(row) for row in conn.execute("""
            SELECT id, category, content, importance, is_active, created_at, last_accessed_at, access_count,
                   CASE WHEN embedding IS NOT NULL THEN 1 ELSE 0 END AS has_embedding
            FROM raw_memories
            WHERE is_active = 1
            ORDER BY importance DESC, created_at DESC LIMIT ?
        """, (limit,)).fetchall()]
        logs = [dict(row) for row in conn.execute("SELECT * FROM consolidation_logs ORDER BY timestamp DESC LIMIT 5").fetchall()]

        total_entities = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
        total_relations = conn.execute("SELECT COUNT(*) FROM relations WHERE is_active = 1").fetchone()[0]
        total_habits = conn.execute("SELECT COUNT(*) FROM procedural_habits").fetchone()[0]
        total_episodes = conn.execute("SELECT COUNT(*) FROM episodic_events").fetchone()[0]
        total_raw = conn.execute("SELECT COUNT(*) FROM raw_memories WHERE is_active = 1").fetchone()[0]

    analytics = get_graph_analytics()

    return {
        "status": "success",
        "counts": {
            "entities": total_entities,
            "relations": total_relations,
            "habits": total_habits,
            "episodes": total_episodes,
            "raw": total_raw
        },
        "analytics": analytics,
        "entities": entities,
        "relations": relations,
        "habits": habits,
        "episodic": episodic,
        "raw_memories": raw,
        "consolidation_logs": logs
    }


def delete_memory(item_type: str, item_id: int) -> Dict[str, Any]:
    """Deletes an entity, relation, habit, or raw memory by ID."""
    table_map = {
        "entity": ("entities", "id"),
        "relation": ("relations", "id"),
        "habit": ("procedural_habits", "id"),
        "episode": ("episodic_events", "id"),
        "raw": ("raw_memories", "id")
    }
    if item_type not in table_map:
        return {"status": "error", "error": f"Unknown memory item type '{item_type}'"}

    tbl, id_col = table_map[item_type]
    with get_db_connection() as conn:
        conn.execute(f"DELETE FROM {tbl} WHERE {id_col} = ?", (item_id,))
        conn.commit()

    return {"status": "success", "deleted_type": item_type, "id": item_id}


def clear_all_memories() -> Dict[str, Any]:
    """Wipes all cognitive memories and re-seeds baseline."""
    with get_db_connection() as conn:
        for t in ["entities", "relations", "episodic_events", "procedural_habits", "raw_memories", "memories_fts", "consolidation_logs"]:
            try:
                conn.execute(f"DELETE FROM {t}")
            except Exception:
                pass
        conn.commit()
    _seed_default_memories_if_needed()
    return {"status": "success", "message": "All cognitive memories wiped and reset to baseline."}


# Initialize DB on module import
init_memory_db()
