"""
Dual-Mode Execution Privacy & Frontier Controller.
Allows users to switch seamlessly between:
  - "air_gapped" : 100% Local & Private (blocks all outbound Cloud LLM, Gemini, SerpAPI, DDG, and HTTP fetches)
  - "hybrid"     : Local-First Balanced (default; local inference & local RAG, permits web search & optional cloud)
  - "frontier"   : Full Frontier Cloud (unlocks cloud LLM reasoning, LLM triple extraction, and deep web research)
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
PRIVACY_CONFIG_PATH = DATA_DIR / "privacy_mode.json"

VALID_MODES = ("air_gapped", "hybrid", "frontier")

MODE_METADATA: Dict[str, Dict[str, Any]] = {
    "air_gapped": {
        "label": "Air-Gapped Local",
        "short": "AIR-GAPPED",
        "description": "Zero outbound internet calls. Blocks Cloud LLMs, SerpAPI, DDG, and external HTTP/Playwright fetches.",
        "outbound_web_allowed": False,
        "cloud_llm_allowed": False,
        "cloud_embeddings_allowed": False,
    },
    "hybrid": {
        "label": "Hybrid (Local + Web)",
        "short": "HYBRID",
        "description": "Local-first privacy for files and memory, with external web search and optional Cloud APIs enabled.",
        "outbound_web_allowed": True,
        "cloud_llm_allowed": True,
        "cloud_embeddings_allowed": False,
    },
    "frontier": {
        "label": "Full Frontier Cloud",
        "short": "FRONTIER",
        "description": "Unrestricted Cloud API reasoning, deep multi-source research, and LLM semantic triple memory extraction.",
        "outbound_web_allowed": True,
        "cloud_llm_allowed": True,
        "cloud_embeddings_allowed": True,
    },
}


def get_privacy_mode() -> str:
    """Returns active execution privacy mode ('air_gapped' | 'hybrid' | 'frontier')."""
    try:
        if PRIVACY_CONFIG_PATH.exists():
            data = json.loads(PRIVACY_CONFIG_PATH.read_text(encoding="utf-8"))
            mode = str(data.get("mode", "hybrid")).strip().lower()
            if mode in VALID_MODES:
                return mode
    except Exception:
        pass
    return "hybrid"


def set_privacy_mode(mode: str) -> Dict[str, Any]:
    """Persists execution privacy mode atomically to disk and returns full status."""
    clean_mode = str(mode or "hybrid").strip().lower()
    if clean_mode not in VALID_MODES:
        raise ValueError(f"Invalid privacy mode '{mode}'. Must be one of: {', '.join(VALID_MODES)}")

    payload = {"mode": clean_mode}
    PRIVACY_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=str(DATA_DIR), prefix="priv_", suffix=".json")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, indent=2))
            fh.flush()
            os.fsync(fh.fileno())
        if PRIVACY_CONFIG_PATH.exists():
            os.replace(tmp_path, PRIVACY_CONFIG_PATH)
        else:
            os.rename(tmp_path, PRIVACY_CONFIG_PATH)
    except Exception:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        raise

    return get_privacy_status()


def is_air_gapped() -> bool:
    """True when strict zero-outbound Air-Gapped Privacy Mode is active."""
    return get_privacy_mode() == "air_gapped"


def is_frontier_mode() -> bool:
    """True when Full Frontier Cloud Mode is active."""
    return get_privacy_mode() == "frontier"


def get_privacy_status() -> Dict[str, Any]:
    """Returns current privacy mode along with capability enforcement flags."""
    mode = get_privacy_mode()
    meta = dict(MODE_METADATA[mode])
    return {
        "status": "success",
        "mode": mode,
        **meta,
    }
