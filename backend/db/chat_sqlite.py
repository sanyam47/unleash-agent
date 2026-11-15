import sqlite3
import os
import json
import time
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "jobs.db")

def init_chat_db():
    """Initializes high-concurrency SQLite tables for chat sessions and message archives with WAL mode."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # Enable WAL mode for high concurrent read/write throughput
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA synchronous=NORMAL;")
    
    cur.execute("""
    CREATE TABLE IF NOT EXISTS chat_sessions (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        created_at REAL,
        updated_at REAL,
        model TEXT,
        message_count INTEGER DEFAULT 0,
        metadata_json TEXT
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS chat_messages (
        id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT,
        images_json TEXT,
        created_at REAL,
        metadata_json TEXT,
        FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id);")
    conn.commit()
    conn.close()

def sync_sessions_to_sqlite(sessions: List[Dict[str, Any]]) -> bool:
    """Upserts full session graphs and messages into SQLite."""
    try:
        init_chat_db()
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        
        for s in sessions:
            sid = s.get("id")
            if not sid:
                continue
            title = s.get("title", "New Conversation")
            c_at = s.get("createdAt") or time.time()
            u_at = s.get("updatedAt") or c_at
            model = s.get("model", "")
            msgs = s.get("messages", [])
            meta = {k: v for k, v in s.items() if k not in ("id", "title", "createdAt", "updatedAt", "model", "messages")}
            
            cur.execute("""
            INSERT INTO chat_sessions (id, title, created_at, updated_at, model, message_count, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title=excluded.title,
                updated_at=excluded.updated_at,
                model=excluded.model,
                message_count=excluded.message_count,
                metadata_json=excluded.metadata_json;
            """, (sid, title, c_at, u_at, model, len(msgs), json.dumps(meta)))
            
            # Clean and re-insert messages for this session
            cur.execute("DELETE FROM chat_messages WHERE session_id = ?", (sid,))
            for idx, m in enumerate(msgs):
                mid = m.get("id") or f"{sid}_m{idx}_{int(time.time()*1000)}"
                role = m.get("role", "user")
                content = m.get("content", "")
                imgs = json.dumps(m.get("images", []))
                m_time = m.get("timestamp") or time.time()
                m_meta = {k: v for k, v in m.items() if k not in ("id", "role", "content", "images", "timestamp")}
                cur.execute("""
                INSERT INTO chat_messages (id, session_id, role, content, images_json, created_at, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (mid, sid, role, content, imgs, m_time, json.dumps(m_meta)))
                
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[SQLITE SYNC ERROR]: {e}")
        return False

def load_sessions_from_sqlite() -> List[Dict[str, Any]]:
    """Loads all chat sessions and their messages from SQLite with high speed."""
    try:
        init_chat_db()
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        cur.execute("SELECT * FROM chat_sessions ORDER BY updated_at DESC;")
        rows = cur.fetchall()
        
        results = []
        for r in rows:
            sid = r["id"]
            cur.execute("SELECT * FROM chat_messages WHERE session_id = ? ORDER BY created_at ASC;", (sid,))
            m_rows = cur.fetchall()
            
            messages = []
            for mr in m_rows:
                msg = {
                    "id": mr["id"],
                    "role": mr["role"],
                    "content": mr["content"],
                    "images": json.loads(mr["images_json"] or "[]"),
                    "timestamp": mr["created_at"]
                }
                try:
                    meta = json.loads(mr["metadata_json"] or "{}")
                    msg.update(meta)
                except Exception:
                    pass
                messages.append(msg)
                
            sess = {
                "id": sid,
                "title": r["title"],
                "createdAt": r["created_at"],
                "updatedAt": r["updated_at"],
                "model": r["model"],
                "messages": messages
            }
            try:
                s_meta = json.loads(r["metadata_json"] or "{}")
                sess.update(s_meta)
            except Exception:
                pass
            results.append(sess)
            
        conn.close()
        return results
    except Exception as e:
        print(f"[SQLITE LOAD ERROR]: {e}")
        return []
