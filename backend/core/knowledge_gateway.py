import os
import re
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

GATEWAY_DATASETS_DIR = Path(__file__).resolve().parent.parent / "data" / "gateway_datasets"
GATEWAY_DATASETS_DIR.mkdir(parents=True, exist_ok=True)

# In-memory registry of loaded datasets
_LOADED_DATASETS: List[Dict[str, Any]] = []
_LAST_LOAD_TIME: float = 0.0


def reload_gateway_datasets(force: bool = False) -> List[Dict[str, Any]]:
    """
    Dynamically loads all datasets from disk.
    Auto-discovers any new .json datasets added without requiring a server reboot!
    """
    global _LOADED_DATASETS, _LAST_LOAD_TIME

    now = time.time()
    if not force and _LOADED_DATASETS and (now - _LAST_LOAD_TIME < 5.0):
        return _LOADED_DATASETS

    datasets = []
    if GATEWAY_DATASETS_DIR.exists():
        for file in sorted(GATEWAY_DATASETS_DIR.glob("*.json")):
            try:
                data = json.loads(file.read_text(encoding="utf-8"))
                if "id" in data and "keywords" in data:
                    data["_file_mtime"] = file.stat().st_mtime
                    datasets.append(data)
            except Exception as e:
                print(f"[GATEWAY WARNING]: Failed to load {file.name}: {e}")

    _LOADED_DATASETS = datasets
    _LAST_LOAD_TIME = now
    return _LOADED_DATASETS


def query_knowledge_gateway(user_prompt: str) -> Dict[str, Any]:
    """
    Zero-Fine-Tuning Knowledge Gateway Routing Engine:
    1. Scans user prompt against all local datasets in < 0.01 seconds.
    2. Identifies the exact architectural blueprint.
    3. Extracts verified reference code (HTML layout, CSS styling, JS state machine).
    4. Formats a lean open-book exam injection (~200 tokens) with 100% offline privacy.
    """
    start_t = time.perf_counter()
    datasets = reload_gateway_datasets()

    if not user_prompt or not datasets:
        return {
            "matched": False,
            "dataset_id": None,
            "dataset_name": None,
            "score": 0,
            "latency_ms": 0.0,
            "injection_text": ""
        }

    lowered = user_prompt.lower()
    # Normalize hyphens and spaces for robust matching (e.g., 'e commerce' == 'e-commerce')
    normalized_prompt = re.sub(r'[\-_]', ' ', lowered)
    best_dataset = None
    best_score = 0

    for ds in datasets:
        score = 0
        keywords = ds.get("keywords", [])
        
        # Word-boundary exact matches (High weight)
        for kw in keywords:
            clean_kw = kw.lower()
            norm_kw = re.sub(r'[\-_]', ' ', clean_kw)
            
            pattern_orig = r'\b' + re.escape(clean_kw) + r'\b'
            pattern_norm = r'\b' + re.escape(norm_kw) + r'\b'
            
            matches = len(re.findall(pattern_orig, lowered)) or len(re.findall(pattern_norm, normalized_prompt))
            if matches > 0:
                # Multi-word keywords get higher weight
                weight = 3 if (" " in clean_kw or "-" in clean_kw) else 1
                score += matches * weight

        if score > best_score:
            best_score = score
            best_dataset = ds

    elapsed_ms = round((time.perf_counter() - start_t) * 1000, 2)

    # Threshold: at least 1 keyword match
    if best_dataset and best_score >= 1:
        arch = best_dataset.get("architecture", {})
        injection = (
            f"\n\n=== REFERENCE DATASET INSPIRATION [Dataset: {best_dataset['name']}] ===\n"
            f"Here is reference architecture and technical patterns for '{arch.get('archetype', 'Web Application')}'.\n"
            f"Use this strictly as inspiration and technical scaffolding, then build exactly what the user requested:\n"
            f"1. HTML STRUCTURE INSPIRATION:\n"
            f"   {arch.get('html_scaffold', '')}\n"
            f"2. CSS DESIGN SYSTEM & LAYOUT PATTERNS:\n"
            f"   {arch.get('css_design_system', '')}\n"
            f"3. JAVASCRIPT STATE MACHINE & DATA PATTERNS:\n"
            f"   {arch.get('js_state_machine', '')}\n"
            f"INSTRUCTION: Take inspiration from the above structure, styling patterns, and state machine, "
            f"but tailor the products, layout, and branding specifically to fulfill the user's prompt: '{user_prompt}'."
        )

        return {
            "matched": True,
            "dataset_id": best_dataset["id"],
            "dataset_name": best_dataset["name"],
            "score": best_score,
            "latency_ms": elapsed_ms,
            "injection_text": injection
        }

    return {
        "matched": False,
        "dataset_id": None,
        "dataset_name": None,
        "score": 0,
        "latency_ms": elapsed_ms,
        "injection_text": ""
    }


def list_available_gateway_datasets() -> List[Dict[str, Any]]:
    """Returns summary of all available datasets in the local gateway library."""
    datasets = reload_gateway_datasets(force=True)
    return [
        {
            "id": d["id"],
            "name": d["name"],
            "description": d.get("description", ""),
            "keyword_count": len(d.get("keywords", []))
        }
        for d in datasets
    ]
