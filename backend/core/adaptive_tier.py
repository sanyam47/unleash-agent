"""
Adaptive Compute Tiering Engine for Unleash-Agent.
Dynamically scales agent intelligence, context window, milestone depth,
and browser evaluation based on active local GPU or Cloud GPU bridge (Kaggle/Colab/A100).
"""

import os
import re
import json
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional


class ExecutionTier:
    CPU_SAFE = "cpu_safe"
    LITE_EDGE = "lite_edge"
    CLOUD_METERED = "cloud_metered"
    CLOUD_BALANCED = "cloud_balanced"
    FRONTIER_ULTRA = "frontier_ultra"


def get_realtime_gpu_headroom_mb() -> Dict[str, Any]:
    """
    Returns real-time GPU memory metrics (total, free, used in MB) and dynamic context recommendation.
    Sub-100ms non-blocking check via nvidia-smi with system RAM fallback.
    """
    try:
        proc = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.free,memory.used", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=2.5,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        if proc.returncode == 0 and proc.stdout.strip():
            first_line = proc.stdout.strip().splitlines()[0]
            parts = [p.strip() for p in first_line.split(",")]
            if len(parts) >= 4:
                gpu_name = parts[0]
                total_mb = float(parts[1])
                free_mb = float(parts[2])
                used_mb = float(parts[3])

                if total_mb >= 22000 and free_mb >= 10000:
                    ctx_rec = 32768
                    clamped = False
                    status_label = "High-VRAM (32K Context)"
                    num_gpu = 1
                elif total_mb >= 11000 and free_mb >= 5000:
                    ctx_rec = 16384
                    clamped = False
                    status_label = "Mid-VRAM (16K Context)"
                    num_gpu = 1
                elif total_mb <= 6500:
                    # 6GB Consumer GPU (e.g. RTX 3050): keep consistent 4096 ctx so KV cache stays in VRAM
                    # and never force num_gpu=0 when Ollama itself holds the resident weights in VRAM.
                    ctx_rec = 4096
                    clamped = True
                    status_label = "6GB VRAM (4K Stable)"
                    num_gpu = 1
                elif free_mb >= 2500:
                    ctx_rec = 8192
                    clamped = False
                    status_label = "Optimal"
                    num_gpu = 1
                else:
                    ctx_rec = 4096
                    clamped = True
                    status_label = "VRAM Guard (4K Context)"
                    num_gpu = 1

                short_gpu = gpu_name.replace("NVIDIA GeForce ", "").replace(" Laptop GPU", "")
                return {
                    "has_gpu": True,
                    "gpu_name": gpu_name,
                    "short_gpu_name": short_gpu,
                    "total_mb": total_mb,
                    "free_mb": free_mb,
                    "used_mb": used_mb,
                    "vram_gb": round(total_mb / 1024.0, 1),
                    "vram_total_gb": round(total_mb / 1024.0, 1),
                    "vram_free_gb": round(free_mb / 1024.0, 1),
                    "vram_used_gb": round(used_mb / 1024.0, 1),
                    "dynamic_context_window": ctx_rec,
                    "context_clamped": clamped,
                    "recommended_num_gpu": num_gpu,
                    "headroom_status": status_label,
                    "pill_display": f"{short_gpu} ({round(free_mb / 1024.0, 1)}GB Free)",
                    "source": "nvidia-smi"
                }
    except Exception:
        pass

    # Fallback to system RAM probe
    try:
        import psutil
        vmem = psutil.virtual_memory()
        ram_gb = round(vmem.total / (1024.0 ** 3), 1)
        free_ram_gb = round(vmem.available / (1024.0 ** 3), 1)
        return {
            "has_gpu": False,
            "gpu_name": f"CPU / Integrated ({ram_gb}GB System RAM)",
            "short_gpu_name": "CPU",
            "total_mb": round(vmem.total / (1024.0 ** 2), 1),
            "free_mb": round(vmem.available / (1024.0 ** 2), 1),
            "used_mb": round((vmem.total - vmem.available) / (1024.0 ** 2), 1),
            "vram_gb": min(4.0, ram_gb / 4.0),
            "vram_total_gb": ram_gb,
            "vram_free_gb": free_ram_gb,
            "vram_used_gb": round((vmem.total - vmem.available) / (1024.0 ** 3), 1),
            "dynamic_context_window": 4096 if free_ram_gb >= 4.0 else 2048,
            "context_clamped": free_ram_gb < 4.0,
            "recommended_num_gpu": 0,
            "headroom_status": "CPU RAM Active",
            "pill_display": f"CPU RAM ({free_ram_gb}GB Free)",
            "source": "psutil"
        }
    except Exception:
        return {
            "has_gpu": False,
            "gpu_name": "Standard Host CPU",
            "short_gpu_name": "CPU",
            "total_mb": 4096.0,
            "free_mb": 2048.0,
            "used_mb": 2048.0,
            "vram_gb": 4.0,
            "vram_total_gb": 4.0,
            "vram_free_gb": 2.0,
            "vram_used_gb": 2.0,
            "dynamic_context_window": 2048,
            "context_clamped": True,
            "recommended_num_gpu": 0,
            "headroom_status": "Fallback",
            "pill_display": "CPU Safe (2GB Free)",
            "source": "fallback"
        }


def probe_local_gpu_hardware() -> Dict[str, Any]:
    """
    Probes host machine for dedicated GPU name, total VRAM, and real-time free VRAM headroom in GB.
    Fast non-blocking check via nvidia-smi with WMI / system RAM fallback.
    """
    return get_realtime_gpu_headroom_mb()


def probe_active_compute_tier(model_name: Optional[str] = None, user_override: Optional[str] = None) -> Dict[str, Any]:
    """Probes hardware, model capabilities, and active Privacy/Frontier mode."""
    profile = _probe_active_compute_tier_impl(model_name=model_name, user_override=user_override)
    try:
        from backend.core.privacy_mode import get_privacy_status
        ps = get_privacy_status()
        profile["privacy_mode"] = ps.get("mode", "hybrid")
        profile["privacy_short"] = ps.get("short", "HYBRID")
        profile["privacy_label"] = ps.get("label", "Hybrid (Local + Web)")
    except Exception:
        profile["privacy_mode"] = "hybrid"
        profile["privacy_short"] = "HYBRID"
        profile["privacy_label"] = "Hybrid (Local + Web)"
    try:
        profile["param_profile"] = get_model_parameter_profile(model_name)
    except Exception:
        pass
    return profile


def _probe_active_compute_tier_impl(model_name: Optional[str] = None, user_override: Optional[str] = None) -> Dict[str, Any]:
    """
    Dynamically determines the optimal compute tier:
      Tier 1: LITE_EDGE       (<12GB VRAM / Local RTX 3050 / 8B models)
      Tier 2: CLOUD_BALANCED  (12GB-32GB VRAM / Kaggle Dual T4 / Colab / 14B-32B models)
      Tier 3: FRONTIER_ULTRA  (>32GB VRAM / A100 / H100 / Multimodal Vision weights)
    """
    if user_override and user_override in (ExecutionTier.CPU_SAFE, ExecutionTier.LITE_EDGE, ExecutionTier.CLOUD_BALANCED, ExecutionTier.FRONTIER_ULTRA):
        override_tier = user_override
    else:
        override_tier = None

    # 1. Check Cloud GPU Bridge state first
    cloud_info = {}
    try:
        from backend.core.cloud_gpu_bridge import CloudGpuBridge
        config = CloudGpuBridge.load_config()
        active_provider = config.get("active_provider", "local")
        providers = config.get("providers", {})
        active_prov_data = providers.get(active_provider, {})
        cloud_info = {
            "provider": active_provider,
            "connected": active_prov_data.get("connected", False) or active_prov_data.get("status") == "online",
            "raw_vram": active_prov_data.get("vram", ""),
            "name": active_prov_data.get("name", "")
        }
    except Exception:
        active_provider = "local"

    # Determine base VRAM and hardware description
    gpu_name = "Local GPU"
    vram_gb = 6.0
    is_cloud_active = False
    local_hw: Dict[str, Any] = {}

    if active_provider == "kaggle" and cloud_info.get("connected"):
        is_cloud_active = True
        vram_gb = 30.0  # Dual T4
        gpu_name = "Kaggle Dual Tesla T4 (30GB VRAM)"
    elif active_provider == "colab" and cloud_info.get("connected"):
        is_cloud_active = True
        vram_gb = 16.0  # Tesla T4
        gpu_name = "Google Colab Tesla T4 (16GB VRAM)"
    elif active_provider == "purchased" and cloud_info.get("connected"):
        is_cloud_active = True
        vram_gb = 48.0
        gpu_name = "Dedicated Cloud GPU (A100 / RTX 4090)"
    else:
        local_hw = probe_local_gpu_hardware()
        vram_gb = local_hw.get("vram_gb", 6.0)
        gpu_name = local_hw.get("gpu_name", "Local GPU")

    # Check Model Multimodal / Param Capabilities & Cloud Metering
    m_lower = (model_name or "").lower()

    is_cloud = False
    cloud_provider = None
    clean_model = m_lower
    try:
        from backend.core.cloud_llm_client import is_cloud_model, parse_cloud_model_string
        if is_cloud_model(model_name or ""):
            is_cloud = True
            prov, sub_m = parse_cloud_model_string(model_name or "")
            cloud_provider = (prov or "").lower()
            clean_model = (sub_m or model_name or "").lower()
    except Exception:
        pass

    # Free / Rate-limited Cloud tier check
    is_metered_free_cloud = is_cloud and (
        cloud_provider == "groq" or
        ":free" in clean_model or
        clean_model.endswith(":free") or
        "/free" in clean_model or
        "-free" in clean_model
    )

    frontier_tokens = (
        "claude-3", "claude-3.5", "claude-3-5", "claude-4", "sonnet", "opus",
        "gpt-4", "gpt-4o", "gpt-5", "o1", "o3", "o4",
        "gemini-1.5-pro", "gemini-2.", "gemini-3", "deepseek-chat", "deepseek-reasoner",
        "deepseek-v3", "deepseek-r1", "llama-3.3-70b", "72b", "405b",
    )
    is_frontier_model = any(k in clean_model for k in frontier_tokens)
    is_frontier_cloud = is_cloud and not is_metered_free_cloud and is_frontier_model

    is_multimodal = any(k in m_lower for k in ["vision", "vl", "llava", "multimodal", "gpt-4", "gpt-5", "claude", "gemini"])
    is_large_weight = any(k in m_lower for k in ["14b", "27b", "32b", "34b", "70b", "72b", "mixtral"])

    # Determine Tier dynamically
    privacy_status = {"mode": "hybrid", "short": "HYBRID", "cloud_llm_allowed": True}
    try:
        from backend.core.privacy_mode import get_privacy_status
        privacy_status = get_privacy_status()
    except Exception:
        pass

    if privacy_status.get("mode") == "air_gapped":
        is_cloud = False
        is_frontier_cloud = False
        is_metered_free_cloud = False

    if override_tier:
        tier = override_tier
    elif is_metered_free_cloud:
        tier = ExecutionTier.CLOUD_METERED
    elif is_frontier_cloud or is_frontier_model or is_multimodal or vram_gb >= 32.0:
        tier = ExecutionTier.FRONTIER_ULTRA
    elif is_cloud_active or is_cloud or vram_gb >= 12.0 or is_large_weight:
        tier = ExecutionTier.CLOUD_BALANCED
    elif local_hw and (not local_hw.get("has_gpu", False) or vram_gb < 2.0):
        tier = ExecutionTier.CPU_SAFE
    else:
        tier = ExecutionTier.LITE_EDGE

    ocr_gpu_allowed = bool(
        (local_hw.get("has_gpu", False) and ((local_hw.get("total_mb", 0) > 7000 and local_hw.get("free_mb", 0) >= 2200) or local_hw.get("free_mb", 0) >= 3500))
        or (is_cloud_active and vram_gb >= 14.0)
    )

    # Generate Tier-specific Adaptive Profiles across Chat, Research, Coding, Memory & OCR
    if tier == ExecutionTier.CLOUD_METERED:
        prov_label = cloud_provider.upper() if cloud_provider else "Cloud"
        return {
            "tier": ExecutionTier.CLOUD_METERED,
            "tier_display": f"CLOUD METERED ({prov_label} Free / Rate-Limited)",
            "gpu_name": f"{prov_label} Free API",
            "vram_gb": vram_gb,
            "is_cloud": True,
            "max_milestones": 4,
            "max_steps": 8,
            "context_window": 8192,
            "toolset_mode": "lean",
            "system_prompt_mode": "lean",
            "self_repair_cap": 1,
            "rate_pace_seconds": 3.0,
            "dual_engine_markdown_fallback": True,
            "compress_diagnostics": True,
            "visual_mode": "dom_delta",
            "viewports": [
                {"name": "desktop", "width": 1280, "height": 800}
            ],
            "chat_profile": {
                "history_limit": 8,
                "num_predict_chat": 1024,
                "num_predict_action": 4096,
                "context_window": 8192,
            },
            "research_profile": {
                "mode": "paced_combined",
                "combine_extract_verify": True,
                "max_queries": 3,
                "max_sources_extract": 8,
                "excerpt_chars": 2400,
                "max_fetch_urls": 4,
                "max_doc_pages": 14,
                "rate_pace_seconds": 2.5,
            },
            "memory_profile": {
                "top_k": 7,
                "max_inject_chars": 2200,
                "max_hops": 3,
                "llm_triple_extraction": False,
            },
            "ocr_profile": {
                "use_gpu": ocr_gpu_allowed,
                "dpi": 150,
            },
            "description": "Cloud Metered mode: Lean toolset (<400 tokens), 3s rate pacing, combined research pass, surgical diagnostics."
        }
    elif tier == ExecutionTier.FRONTIER_ULTRA:
        eff_vram = max(vram_gb, 48.0) if (is_cloud or is_frontier_model) else vram_gb
        return {
            "tier": ExecutionTier.FRONTIER_ULTRA,
            "tier_display": "FRONTIER ULTRA (High-Reasoning / Cloud / Large VRAM)",
            "gpu_name": gpu_name if not is_cloud else f"Frontier API ({clean_model or 'Cloud'})",
            "vram_gb": eff_vram,
            "is_cloud": is_cloud or is_cloud_active,
            "max_milestones": 8,
            "max_steps": 36,
            "context_window": 65536,
            "toolset_mode": "full",
            "system_prompt_mode": "full",
            "self_repair_cap": 5,
            "rate_pace_seconds": 0.0,
            "dual_engine_markdown_fallback": False,
            "compress_diagnostics": False,
            "visual_mode": "multimodal_vision",
            "viewports": [
                {"name": "desktop", "width": 1440, "height": 900},
                {"name": "tablet", "width": 768, "height": 1024},
                {"name": "mobile", "width": 390, "height": 844}
            ],
            "chat_profile": {
                "history_limit": 24,
                "num_predict_chat": 4096,
                "num_predict_action": 8192,
                "context_window": 65536,
            },
            "research_profile": {
                "mode": "frontier_combined",
                "combine_extract_verify": True,
                "max_queries": 5,
                "max_sources_extract": 16,
                "excerpt_chars": 5500,
                "max_fetch_urls": 6,
                "max_doc_pages": 35,
                "rate_pace_seconds": 0.0,
            },
            "memory_profile": {
                "top_k": 10,
                "max_inject_chars": 3600,
                "max_hops": 4,
                "llm_triple_extraction": True,
            },
            "ocr_profile": {
                "use_gpu": ocr_gpu_allowed,
                "dpi": 180,
            },
            "description": "Frontier Ultra mode: Unlocks 65K context, combined deep research pass, LLM cognitive triple extraction, and multi-device testing."
        }
    elif tier == ExecutionTier.CLOUD_BALANCED:
        return {
            "tier": ExecutionTier.CLOUD_BALANCED,
            "tier_display": "CLOUD BALANCED (Mid-High GPU / 14B-32B)",
            "gpu_name": gpu_name,
            "vram_gb": vram_gb,
            "is_cloud": is_cloud_active or is_cloud,
            "max_milestones": 6,
            "max_steps": 24,
            "context_window": 32768,
            "toolset_mode": "full",
            "system_prompt_mode": "full",
            "self_repair_cap": 3,
            "rate_pace_seconds": 0.0,
            "dual_engine_markdown_fallback": True,
            "compress_diagnostics": False,
            "visual_mode": "responsive_matrix",
            "viewports": [
                {"name": "desktop", "width": 1280, "height": 800},
                {"name": "mobile", "width": 390, "height": 844}
            ],
            "chat_profile": {
                "history_limit": 14,
                "num_predict_chat": 1536,
                "num_predict_action": 4096,
                "context_window": 32768,
            },
            "research_profile": {
                "mode": "deep_4_step",
                "combine_extract_verify": False,
                "max_queries": 4,
                "max_sources_extract": 10,
                "excerpt_chars": 3200,
                "max_fetch_urls": 5,
                "max_doc_pages": 20,
                "rate_pace_seconds": 0.0,
            },
            "memory_profile": {
                "top_k": 8,
                "max_inject_chars": 2800,
                "max_hops": 3,
                "llm_triple_extraction": True,
            },
            "ocr_profile": {
                "use_gpu": ocr_gpu_allowed,
                "dpi": 180,
            },
            "description": "Balanced mode: Unlocks 32K context, 10-source research, mobile+desktop verification, and LLM triple extraction."
        }
    elif tier == ExecutionTier.CPU_SAFE:
        return {
            "tier": ExecutionTier.CPU_SAFE,
            "tier_display": "CPU SAFE (Zero-GPU Fallback)",
            "gpu_name": gpu_name or "CPU Only",
            "vram_gb": vram_gb,
            "is_cloud": False,
            "max_milestones": 3,
            "max_steps": 10,
            "context_window": 4096,
            "toolset_mode": "lean",
            "system_prompt_mode": "lean",
            "self_repair_cap": 1,
            "rate_pace_seconds": 0.0,
            "dual_engine_markdown_fallback": True,
            "compress_diagnostics": True,
            "visual_mode": "dom_delta",
            "viewports": [
                {"name": "desktop", "width": 1280, "height": 800}
            ],
            "chat_profile": {
                "history_limit": 4,
                "num_predict_chat": 256,
                "num_predict_action": 1024,
                "context_window": 4096,
            },
            "research_profile": {
                "mode": "4_step_lean",
                "combine_extract_verify": False,
                "max_queries": 2,
                "max_sources_extract": 4,
                "excerpt_chars": 1000,
                "max_fetch_urls": 2,
                "max_doc_pages": 6,
                "rate_pace_seconds": 0.0,
            },
            "memory_profile": {
                "top_k": 4,
                "max_inject_chars": 1200,
                "max_hops": 2,
                "llm_triple_extraction": False,
            },
            "ocr_profile": {
                "use_gpu": False,
                "dpi": 150,
            },
            "description": "Accessible mode: 3 focused milestones, 4K lightweight context, zero GPU requirements."
        }
    else:  # LITE_EDGE
        dynamic_ctx = local_hw.get("dynamic_context_window", 4096)
        return {
            "tier": ExecutionTier.LITE_EDGE,
            "tier_display": "LITE EDGE (Consumer 6GB GPU / Offline 8B)",
            "gpu_name": gpu_name,
            "vram_gb": vram_gb,
            "vram_free_gb": local_hw.get("vram_free_gb", vram_gb),
            "is_cloud": False,
            "max_milestones": 4,
            "max_steps": 14,
            "context_window": dynamic_ctx,
            "dynamic_context_window": dynamic_ctx,
            "context_clamped": local_hw.get("context_clamped", False),
            "headroom_status": local_hw.get("headroom_status", "Optimal"),
            "pill_display": local_hw.get("pill_display", gpu_name),
            "toolset_mode": "lean",
            "system_prompt_mode": "lean",
            "self_repair_cap": 2,
            "rate_pace_seconds": 0.0,
            "dual_engine_markdown_fallback": True,
            "compress_diagnostics": True,
            "visual_mode": "dom_delta",
            "viewports": [
                {"name": "desktop", "width": 1280, "height": 800}
            ],
            "chat_profile": {
                "history_limit": 6,
                "num_predict_chat": 512,
                "num_predict_action": 2048,
                "context_window": dynamic_ctx,
            },
            "research_profile": {
                "mode": "4_step_scaffolding",
                "combine_extract_verify": False,
                "max_queries": 3,
                "max_sources_extract": 6,
                "excerpt_chars": 1400,
                "max_fetch_urls": 3,
                "max_doc_pages": 10,
                "rate_pace_seconds": 0.0,
            },
        "memory_profile": {
                "top_k": 6,
                "max_inject_chars": 1800,
                "max_hops": 3,
                "llm_triple_extraction": False,
            },
            "ocr_profile": {
                "use_gpu": ocr_gpu_allowed,
                "dpi": 150,
            },
            "description": "Optimized offline mode: 4K-stable VRAM cache, structured 4-step 8B scaffolding, zero GPU lock."
        }


_PARAM_PROFILE_CACHE: Dict[str, tuple[float, Dict[str, Any]]] = {}
_PARAM_CACHE_TTL = 600.0


def _parse_param_size_billions(raw: Optional[str]) -> Optional[float]:
    """Parses strings like '3.2B', '8B', '14.8B', '500M', 'qwen2.5:7b' into billions."""
    if not raw:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)\s*([bm])\b", str(raw).lower())
    if not m:
        return None
    val = float(m.group(1))
    unit = m.group(2)
    return round(val / 1000.0, 3) if unit == "m" else val


def _query_ollama_model_info(model_name: str, ollama_url: Optional[str] = None) -> Dict[str, Optional[Any]]:
    """Inspects Ollama /api/show for details.parameter_size AND trained max context_length."""
    out: Dict[str, Optional[Any]] = {"param_billions": None, "trained_max_ctx": None}
    if not model_name:
        return out
    try:
        import urllib.request
        base = ollama_url
        if not base:
            try:
                from backend.core.paths import get_ollama_base_url
                base = get_ollama_base_url()
            except Exception:
                base = "http://127.0.0.1:11434"
        req = urllib.request.Request(
            f"{base.rstrip('/')}/api/show",
            data=json.dumps({"name": model_name}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=1.2) as resp:
            info = json.loads(resp.read().decode("utf-8"))

        details = info.get("details") or {}
        parsed = _parse_param_size_billions(details.get("parameter_size"))
        if parsed is None:
            parsed = _parse_param_size_billions(details.get("family"))
        out["param_billions"] = parsed

        # Inspect model_info.<arch>.context_length for trained window
        model_info = info.get("model_info") or {}
        for k, v in model_info.items():
            if str(k).endswith(".context_length") and isinstance(v, (int, float)) and v > 0:
                out["trained_max_ctx"] = int(v)
                break

        # Fallback: inspect Modelfile parameters line if explicit num_ctx is pinned there
        if out["trained_max_ctx"] is None:
            params_txt = str(info.get("parameters") or "")
            m_ctx = re.search(r"\bnum_ctx\s+(\d+)", params_txt)
            if m_ctx:
                out["trained_max_ctx"] = int(m_ctx.group(1))
    except Exception:
        pass
    return out


def get_model_parameter_profile(model_name: Optional[str], ollama_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Parameter-Adaptive Model Profiler:
    Classifies any local or cloud model into COMPACT (<=4B), BALANCED (5B-15B), or
    FRONTIER (>=16B / Cloud) and dynamically enables or drops scaffolding features so
    every model operates at its maximum output ceiling.
    """
    import time
    raw_name = (model_name or "").strip()
    cache_key = raw_name.lower() or "__default__"
    now = time.monotonic()
    cached = _PARAM_PROFILE_CACHE.get(cache_key)
    if cached and (now - cached[0]) < _PARAM_CACHE_TTL:
        return cached[1]

    param_b: Optional[float] = None
    trained_max_ctx: Optional[int] = None
    is_cloud = False
    try:
        from backend.core.cloud_llm_client import is_cloud_model
        is_cloud = bool(is_cloud_model(raw_name))
    except Exception:
        is_cloud = False

    low = raw_name.lower()
    if is_cloud or any(tok in low for tok in ("gemini", "claude", "gpt-4", "gpt-5", "o1", "o3", "deepseek-r1", "deepseek-v3")):
        is_cloud = True
        param_b = _parse_param_size_billions(raw_name) or 70.0
    else:
        ollama_meta = _query_ollama_model_info(raw_name, ollama_url=ollama_url)
        param_b = _parse_param_size_billions(raw_name)
        if param_b is None:
            param_b = ollama_meta.get("param_billions")
        trained_max_ctx = ollama_meta.get("trained_max_ctx")

    # Determine capability tier cleanly from parameter count (unknown custom local defaults to balanced)
    if is_cloud or (param_b is not None and param_b >= 16.0):
        param_tier = "frontier"
        tier_label = f"FRONTIER ({param_b:.0f}B+ / Cloud)" if param_b else "FRONTIER (Cloud)"
        scaffolding = {
            "inject_few_shot_examples": False,
            "inject_dynamic_app_grounding": False,
            "inject_search_url_hint": False,
            "include_ambient_narrative": True,
            "json_repair_and_retry": False,
            "executive_temperature": 0.15,
            "executive_num_predict": 320,
            "agent_temperature": 0.35,
        }
    elif param_b is not None and param_b < 5.0:
        param_tier = "compact"
        tier_label = f"COMPACT ({param_b:g}B)"
        scaffolding = {
            "inject_few_shot_examples": True,
            "inject_dynamic_app_grounding": True,
            "inject_search_url_hint": True,
            "include_ambient_narrative": False,
            "json_repair_and_retry": True,
            "executive_temperature": 0.05,
            "executive_num_predict": 160,
            "agent_temperature": 0.2,
        }
    else:
        param_tier = "balanced"
        tier_label = f"BALANCED ({param_b:g}B)" if param_b else "BALANCED (Local)"
        scaffolding = {
            "inject_few_shot_examples": False,
            "inject_dynamic_app_grounding": True,
            "inject_search_url_hint": True,
            "include_ambient_narrative": True,
            "json_repair_and_retry": True,
            "executive_temperature": 0.1,
            "executive_num_predict": 220,
            "agent_temperature": 0.3,
        }

    profile = {
        "model": raw_name,
        "param_billions": param_b,
        "trained_max_ctx": trained_max_ctx,
        "param_tier": param_tier,
        "param_label": tier_label,
        "is_cloud": is_cloud,
        "scaffolding": scaffolding,
    }
    _PARAM_PROFILE_CACHE[cache_key] = (now, profile)
    return profile


def resolve_ollama_num_ctx(
    model_name: Optional[str],
    requested_ctx: int = 4096,
    ollama_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Computes explicit Ollama `num_ctx` bounded cleanly by BOTH GPU VRAM headroom and the model's
    trained max context from `/api/show`, preventing silent Ollama default truncation or VRAM spillover.
    """
    headroom = get_realtime_gpu_headroom_mb()
    hw_limit = int(headroom.get("dynamic_context_window", 4096) or 4096)
    if not headroom.get("context_clamped") and float(headroom.get("vram_free_gb", 8.0) or 8.0) < 6.5:
        hw_limit = min(hw_limit, 4096)

    param_prof = get_model_parameter_profile(model_name, ollama_url=ollama_url)
    trained_max = param_prof.get("trained_max_ctx")

    allocated = min(max(1024, int(requested_ctx)), hw_limit)
    if trained_max is not None and trained_max > 0:
        allocated = min(allocated, int(trained_max))

    return {
        "model": model_name or "",
        "requested_ctx": int(requested_ctx),
        "allocated_ctx": int(allocated),
        "hw_limit": int(hw_limit),
        "trained_max_ctx": trained_max,
        "vram_clamped": bool(int(allocated) < int(requested_ctx) and int(hw_limit) < int(requested_ctx)),
        "headroom": headroom,
    }
