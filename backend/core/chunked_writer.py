"""
Chunked Multi-Turn File Writer Engine.
Enables local 8B models to write multi-thousand line production codebases
by chunking large files across turns without token truncation or hallucinations.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
from backend.core.agent_tools import resolve_safe_project_path, sanitize_project_name

_ACTIVE_CHUNK_SESSIONS: Dict[str, Dict[str, Any]] = {}

def get_file_line_count(file_path: Path) -> int:
    """Returns the line count of a file on disk."""
    if not file_path.exists():
        return 0
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def start_chunked_file(project_name: str, file_path: str, initial_chunk: str, total_chunks: Optional[int] = None) -> Dict[str, Any]:
    """
    Initializes a new chunked file with its header / first block.
    Overwrites any existing file to ensure a clean start.
    """
    clean_proj = sanitize_project_name(project_name)
    target = resolve_safe_project_path(clean_proj, file_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    target.write_text(initial_chunk, encoding="utf-8")
    lines = get_file_line_count(target)
    size_bytes = target.stat().st_size

    session_key = f"{clean_proj}:{file_path}"
    _ACTIVE_CHUNK_SESSIONS[session_key] = {
        "project": clean_proj,
        "file": file_path,
        "chunks_written": 1,
        "total_chunks": total_chunks,
        "total_lines": lines,
        "is_finalized": False
    }

    return {
        "status": "success",
        "action": "start_chunked_file",
        "file": file_path,
        "chunk_index": 1,
        "current_lines": lines,
        "bytes_written": size_bytes,
        "message": f"Started chunked file '{file_path}' (Chunk 1, {lines} lines written). Ready for next chunk or append."
    }


def append_chunk_to_file(project_name: str, file_path: str, chunk_content: str, is_final: bool = False) -> Dict[str, Any]:
    """
    Appends a new code block to an existing file, tracking progressive line and byte counts.
    """
    clean_proj = sanitize_project_name(project_name)
    target = resolve_safe_project_path(clean_proj, file_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    with open(target, "a", encoding="utf-8") as f:
        # Ensure clean newline separator before appending next chunk
        if target.stat().st_size > 0 and not chunk_content.startswith(("\n", "\r\n")):
            f.write("\n")
        f.write(chunk_content)

    lines = get_file_line_count(target)
    size_bytes = target.stat().st_size

    session_key = f"{clean_proj}:{file_path}"
    session = _ACTIVE_CHUNK_SESSIONS.get(session_key, {
        "project": clean_proj,
        "file": file_path,
        "chunks_written": 0,
        "total_chunks": None,
        "total_lines": 0,
        "is_finalized": False
    })
    session["chunks_written"] += 1
    session["total_lines"] = lines
    session["is_finalized"] = is_final
    _ACTIVE_CHUNK_SESSIONS[session_key] = session

    return {
        "status": "success",
        "action": "append_chunk_to_file",
        "file": file_path,
        "chunk_index": session["chunks_written"],
        "current_lines": lines,
        "total_bytes": size_bytes,
        "is_finalized": is_final,
        "message": f"Appended chunk to '{file_path}' (Total lines: {lines}, {size_bytes} bytes). {'File finalized.' if is_final else 'Ready for next chunk.'}"
    }


def get_chunk_session(project_name: str, file_path: str) -> Optional[Dict[str, Any]]:
    """Retrieves active chunk authoring session metadata."""
    clean_proj = sanitize_project_name(project_name)
    session_key = f"{clean_proj}:{file_path}"
    return _ACTIVE_CHUNK_SESSIONS.get(session_key)
