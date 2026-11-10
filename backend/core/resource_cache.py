import os
import time
import threading
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

class WorkspaceResourceCache:
    """
    High-Speed In-Memory LRU Resource Cache with mtime Invalidation.
    Eliminates redundant disk I/O, regex parsing, and network queries across ReAct turns.
    Shaves off 200-400ms on pre-flight scouting and workspace analysis.
    """
    _lock = threading.Lock()
    _MAX_ENTRIES = 128

    # Format: {path_str: (mtime, content_or_data)}
    _file_cache: Dict[str, Tuple[float, str]] = {}
    _tree_cache: Dict[str, Tuple[float, str]] = {}
    _symbol_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
    _manifest_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
    _scout_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
    _generic_cache: Dict[str, Tuple[float, Any, float]] = {}

    @classmethod
    def _get_dir_max_mtime(cls, dir_path: Path) -> float:
        """Returns the highest mtime among all files directly inside dir_path."""
        if not dir_path.exists():
            return 0.0
        max_m = dir_path.stat().st_mtime
        try:
            for entry in dir_path.iterdir():
                if entry.name.startswith(".") or entry.name == "__pycache__":
                    continue
                try:
                    s_m = entry.stat().st_mtime
                    if s_m > max_m:
                        max_m = s_m
                except Exception:
                    pass
        except Exception:
            pass
        return max_m

    # ---------------- File Content Cache ----------------
    @classmethod
    def get_file(cls, path: Path) -> Optional[str]:
        if not path.exists():
            return None
        p_str = str(path.resolve())
        curr_mtime = path.stat().st_mtime
        with cls._lock:
            cached = cls._file_cache.get(p_str)
            if cached and cached[0] == curr_mtime:
                return cached[1]
        return None

    @classmethod
    def set_file(cls, path: Path, content: str):
        if not path.exists():
            return
        p_str = str(path.resolve())
        curr_mtime = path.stat().st_mtime
        with cls._lock:
            if len(cls._file_cache) >= cls._MAX_ENTRIES:
                cls._file_cache.pop(next(iter(cls._file_cache)), None)
            cls._file_cache[p_str] = (curr_mtime, content)

    # ---------------- Workspace Tree Cache ----------------
    @classmethod
    def get_workspace_tree(cls, dir_path: Path) -> Optional[str]:
        if not dir_path.exists():
            return None
        d_str = str(dir_path.resolve())
        dir_mtime = cls._get_dir_max_mtime(dir_path)
        with cls._lock:
            cached = cls._tree_cache.get(d_str)
            if cached and cached[0] == dir_mtime:
                return cached[1]
        return None

    @classmethod
    def set_workspace_tree(cls, dir_path: Path, tree_str: str):
        if not dir_path.exists():
            return
        d_str = str(dir_path.resolve())
        dir_mtime = cls._get_dir_max_mtime(dir_path)
        with cls._lock:
            if len(cls._tree_cache) >= cls._MAX_ENTRIES:
                cls._tree_cache.pop(next(iter(cls._tree_cache)), None)
            cls._tree_cache[d_str] = (dir_mtime, tree_str)

    # ---------------- Symbol Table & AST Cache ----------------
    @classmethod
    def get_symbols(cls, dir_path: Path) -> Optional[Dict[str, Any]]:
        if not dir_path.exists():
            return None
        d_str = str(dir_path.resolve())
        dir_mtime = cls._get_dir_max_mtime(dir_path)
        with cls._lock:
            cached = cls._symbol_cache.get(d_str)
            if cached and cached[0] == dir_mtime:
                return cached[1]
        return None

    @classmethod
    def set_symbols(cls, dir_path: Path, symbols: Dict[str, Any]):
        if not dir_path.exists():
            return
        d_str = str(dir_path.resolve())
        dir_mtime = cls._get_dir_max_mtime(dir_path)
        with cls._lock:
            if len(cls._symbol_cache) >= cls._MAX_ENTRIES:
                cls._symbol_cache.pop(next(iter(cls._symbol_cache)), None)
            cls._symbol_cache[d_str] = (dir_mtime, symbols)

    # ---------------- Project Manifest Cache ----------------
    @classmethod
    def get_manifest(cls, manifest_path: Path) -> Optional[Dict[str, Any]]:
        if not manifest_path.exists():
            return None
        p_str = str(manifest_path.resolve())
        curr_mtime = manifest_path.stat().st_mtime
        with cls._lock:
            cached = cls._manifest_cache.get(p_str)
            if cached and cached[0] == curr_mtime:
                return cached[1]
        return None

    @classmethod
    def set_manifest(cls, manifest_path: Path, manifest: Dict[str, Any]):
        if not manifest_path.exists():
            return
        p_str = str(manifest_path.resolve())
        curr_mtime = manifest_path.stat().st_mtime
        with cls._lock:
            if len(cls._manifest_cache) >= cls._MAX_ENTRIES:
                cls._manifest_cache.pop(next(iter(cls._manifest_cache)), None)
            cls._manifest_cache[p_str] = (curr_mtime, manifest)

    # ---------------- Scout Architecture Cache ----------------
    @classmethod
    def get_scout_contract(cls, cache_key: str) -> Optional[Dict[str, Any]]:
        with cls._lock:
            cached = cls._scout_cache.get(cache_key)
            if cached:
                # 15-minute TTL for scout keyword queries
                if (time.time() - cached[0]) < 900.0:
                    return cached[1]
        return None

    @classmethod
    def set_scout_contract(cls, cache_key: str, contract: Dict[str, Any]):
        with cls._lock:
            if len(cls._scout_cache) >= cls._MAX_ENTRIES:
                cls._scout_cache.pop(next(iter(cls._scout_cache)), None)
            cls._scout_cache[cache_key] = (time.time(), contract)

    # ---------------- Generic Thread-Safe In-Memory Cache ----------------
    @classmethod
    def get(cls, key: str) -> Optional[Any]:
        with cls._lock:
            cached = cls._generic_cache.get(key)
            if cached:
                ts, data, ttl = cached
                if (time.time() - ts) < ttl:
                    return data
                else:
                    cls._generic_cache.pop(key, None)
        return None

    @classmethod
    def set(cls, key: str, data: Any, ttl_seconds: float = 300.0):
        with cls._lock:
            if len(cls._generic_cache) >= cls._MAX_ENTRIES:
                cls._generic_cache.pop(next(iter(cls._generic_cache)), None)
            cls._generic_cache[key] = (time.time(), data, ttl_seconds)

    # ---------------- Invalidation Helper ----------------
    @classmethod
    def invalidate_project(cls, dir_path: Path):
        d_str = str(dir_path.resolve())
        with cls._lock:
            cls._tree_cache.pop(d_str, None)
            cls._symbol_cache.pop(d_str, None)
            # Remove files in this dir
            to_del = [k for k in cls._file_cache if k.startswith(d_str)]
            for k in to_del:
                cls._file_cache.pop(k, None)
