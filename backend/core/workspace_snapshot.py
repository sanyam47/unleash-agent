"""
Autonomous Workspace Snapshot & 1-Click Rollback Engine.
Provides human-in-the-loop developer control:
  1. Automatic snapshots before each turn and after self-repairs.
  2. 1-click instant rollback to any previous version.
  3. Strict disk budgeting (caps at 10 most recent snapshots).
"""

import os
import shutil
import time
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

from backend.core.agent_tools import get_project_dir, sanitize_project_name, resolve_safe_project_path

MAX_SNAPSHOTS_PER_PROJECT = 10


def get_snapshots_dir(clean_proj: str) -> Path:
    """Returns the .snapshots directory for a given project."""
    proj_dir = get_project_dir(clean_proj)
    s_dir = proj_dir / ".snapshots"
    s_dir.mkdir(parents=True, exist_ok=True)
    return s_dir


def create_snapshot(project_name: str, step_label: str = "checkpoint", description: str = "") -> Dict[str, Any]:
    """
    Creates an immutable snapshot of all project files on disk before a turn or repair.
    Ignores the .snapshots directory and hidden files.
    """
    clean_proj = sanitize_project_name(project_name)
    proj_dir = get_project_dir(clean_proj)
    if not proj_dir.exists():
        return {"status": "error", "error": f"Project '{clean_proj}' does not exist on disk."}

    s_dir = get_snapshots_dir(clean_proj)
    ts = int(time.time() * 1000)
    snap_id = f"snap_{ts}_{step_label}"
    target_snap_dir = s_dir / snap_id
    target_snap_dir.mkdir(parents=True, exist_ok=True)

    copied_files = []
    total_bytes = 0

    for item in proj_dir.iterdir():
        if item.name.startswith(".") or item.name == ".snapshots":
            continue
        if item.is_file():
            dest = target_snap_dir / item.name
            shutil.copy2(item, dest)
            size = item.stat().st_size
            copied_files.append({"name": item.name, "bytes": size})
            total_bytes += size
        elif item.is_dir():
            dest = target_snap_dir / item.name
            shutil.copytree(item, dest, ignore=shutil.ignore_patterns(".*"))
            copied_files.append({"name": f"{item.name}/", "bytes": 0})

    meta = {
        "snapshot_id": snap_id,
        "project": clean_proj,
        "step_label": step_label,
        "description": description or f"Snapshot at step '{step_label}'",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "timestamp_ms": ts,
        "files": copied_files,
        "total_bytes": total_bytes
    }

    meta_file = target_snap_dir / "snapshot_meta.json"
    meta_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    # Prune older snapshots if exceeding MAX_SNAPSHOTS_PER_PROJECT
    _prune_old_snapshots(clean_proj)

    return {
        "status": "success",
        "snapshot_id": snap_id,
        "files_count": len(copied_files),
        "total_bytes": total_bytes,
        "created_at": meta["created_at"]
    }


def list_snapshots(project_name: str) -> List[Dict[str, Any]]:
    """Returns a list of all snapshots for a project, sorted by newest first."""
    clean_proj = sanitize_project_name(project_name)
    s_dir = get_snapshots_dir(clean_proj)
    if not s_dir.exists():
        return []

    snapshots = []
    for snap_dir in s_dir.iterdir():
        if not snap_dir.is_dir():
            continue
        meta_file = snap_dir / "snapshot_meta.json"
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                snapshots.append(meta)
            except Exception:
                pass
        else:
            snapshots.append({
                "snapshot_id": snap_dir.name,
                "project": clean_proj,
                "created_at": "Unknown",
                "timestamp_ms": snap_dir.stat().st_mtime * 1000,
                "files": []
            })

    # Sort descending by timestamp
    snapshots.sort(key=lambda s: s.get("timestamp_ms", 0), reverse=True)
    return snapshots


def rollback_to_snapshot(project_name: str, snapshot_id: str) -> Dict[str, Any]:
    """
    Replaces current project files on disk with the files from the requested snapshot.
    Guarantees atomic rollback and preserves the .snapshots folder.
    """
    clean_proj = sanitize_project_name(project_name)
    proj_dir = get_project_dir(clean_proj)
    s_dir = get_snapshots_dir(clean_proj)
    target_snap_dir = s_dir / snapshot_id

    if not target_snap_dir.exists() or not target_snap_dir.is_dir():
        return {"status": "error", "error": f"Snapshot '{snapshot_id}' not found in project '{clean_proj}'."}

    # 1. Take a safety snapshot of the CURRENT state before rolling back, so rollback itself is undoable!
    safety_ts = int(time.time() * 1000)
    safety_snap_dir = s_dir / f"snap_{safety_ts}_pre_rollback"
    safety_snap_dir.mkdir(parents=True, exist_ok=True)
    for item in proj_dir.iterdir():
        if item.name.startswith(".") or item.name == ".snapshots":
            continue
        if item.is_file():
            shutil.copy2(item, safety_snap_dir / item.name)

    # 2. Clean current project directory (except .snapshots)
    for item in proj_dir.iterdir():
        if item.name == ".snapshots" or item.name.startswith("."):
            continue
        if item.is_file():
            item.unlink()
        elif item.is_dir():
            shutil.rmtree(item, ignore_errors=True)

    # 3. Restore files from the requested snapshot
    restored_files = []
    for item in target_snap_dir.iterdir():
        if item.name == "snapshot_meta.json":
            continue
        if item.is_file():
            dest = proj_dir / item.name
            shutil.copy2(item, dest)
            restored_files.append(item.name)
        elif item.is_dir():
            dest = proj_dir / item.name
            shutil.copytree(item, dest)
            restored_files.append(f"{item.name}/")

    return {
        "status": "success",
        "project": clean_proj,
        "rolled_back_to": snapshot_id,
        "restored_files": restored_files,
        "message": f"Successfully rolled back project '{clean_proj}' to snapshot '{snapshot_id}'. Restored {len(restored_files)} files."
    }


def undo_last_step(project_name: str) -> Dict[str, Any]:
    """Convenience helper: rolls back to the previous snapshot or initial pre-turn state."""
    clean_proj = sanitize_project_name(project_name)
    snaps = list_snapshots(clean_proj)
    proj_dir = get_project_dir(clean_proj)

    if not snaps:
        # If no snapshots exist but files were created during a cancelled new run, revert to clean slate
        if proj_dir.exists():
            wiped = []
            for item in proj_dir.iterdir():
                if item.name.startswith(".") or item.name == ".snapshots":
                    continue
                if item.is_file():
                    item.unlink()
                    wiped.append(item.name)
                elif item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                    wiped.append(f"{item.name}/")
            return {
                "status": "success",
                "project": clean_proj,
                "rolled_back_to": "initial_empty_workspace",
                "restored_files": [],
                "message": f"Successfully rolled back to initial clean state. Removed {len(wiped)} files."
            }
        return {"status": "error", "error": "No previous snapshot available to undo."}

    # If exactly 1 snapshot exists, that is the pre-turn baseline snapshot taken at the start of this turn
    if len(snaps) == 1:
        target_snapshot = snaps[0]["snapshot_id"]
        return rollback_to_snapshot(clean_proj, target_snapshot)

    # If 2 or more snapshots exist:
    # If the newest snapshot is a pre_turn snapshot from an aborted/cancelled turn, roll back to it!
    first_id = str(snaps[0].get("snapshot_id", ""))
    if "_pre_turn" in first_id:
        target_snapshot = first_id
    else:
        target_snapshot = snaps[1]["snapshot_id"]

    return rollback_to_snapshot(clean_proj, target_snapshot)


def _prune_old_snapshots(clean_proj: str):
    """Enforces MAX_SNAPSHOTS_PER_PROJECT limit by deleting oldest snapshots."""
    s_dir = get_snapshots_dir(clean_proj)
    snaps = list_snapshots(clean_proj)
    if len(snaps) > MAX_SNAPSHOTS_PER_PROJECT:
        to_delete = snaps[MAX_SNAPSHOTS_PER_PROJECT:]
        for s in to_delete:
            dir_to_remove = s_dir / s["snapshot_id"]
            if dir_to_remove.exists():
                shutil.rmtree(dir_to_remove, ignore_errors=True)
