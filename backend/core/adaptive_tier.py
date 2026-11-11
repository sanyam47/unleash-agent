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

                if free_mb >= 2500:
                    ctx_rec = 8192
                    clamped = False
                    status_label = "Optimal"
                    num_gpu = 1
                elif free_mb >= 1200:
                    ctx_rec = 2048
                    clamped = True
                    status_label = "Clamped (2K Context)"
                    num_gpu = 1
                else:
                    ctx_rec = 2048
                    clamped = True
                    status_label = "CPU Memory Fallback (<1.2GB Free)"
                    num_gpu = 0

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

    # Free / Rate-limited Cloud tier check:
    # 1. Groq on-demand tier (7,000 ITPM / 1,000 OTPM)
    # 2. OpenRouter free models ending with ':free' or containing 'free' in model id
    is_metered_free_cloud = is_cloud and (
        cloud_provider == "groq" or
        ":free" in clean_model or
        clean_model.endswith(":free") or
        "/free" in clean_model or
        "-free" in clean_model
    )

    is_frontier_cloud = is_cloud and not is_metered_free_cloud and any(
        k in clean_model for k in [
            "claude-3", "claude-3.5", "claude-3-5", "gpt-4", "gpt-4o", "o1", "o3", 
            "gemini-1.5-pro", "gemini-2.0", "deepseek-coder", "llama-3.3-70b"
        ]
    )

    is_multimodal = any(k in m_lower for k in ["vision", "vl", "llava", "multimodal", "gpt-4", "claude", "gemini"])
    is_large_weight = any(k in m_lower for k in ["14b", "32b", "70b"])

    # Determine Tier dynamically
    if override_tier:
        tier = override_tier
    elif is_metered_free_cloud:
        tier = ExecutionTier.CLOUD_METERED
    elif is_frontier_cloud or is_multimodal or vram_gb >= 40.0:
        tier = ExecutionTier.FRONTIER_ULTRA
    elif is_cloud_active or vram_gb >= 12.0 or is_large_weight:
        tier = ExecutionTier.CLOUD_BALANCED
    elif not local_hw.get("has_gpu", False) or vram_gb < 2.0:
        tier = ExecutionTier.CPU_SAFE
    else:
        tier = ExecutionTier.LITE_EDGE

    # Generate Tier-specific Adaptive Profiles
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
            "description": "Cloud Metered mode: Lean 3-tool set (<400 tokens), 3s rate pacing, 1-turn repair cap, surgical diagnostics."
        }
    elif tier == ExecutionTier.FRONTIER_ULTRA:
        return {
            "tier": ExecutionTier.FRONTIER_ULTRA,
            "tier_display": "FRONTIER ULTRA (Enterprise Cloud / Multimodal Vision)",
            "gpu_name": gpu_name if not is_cloud else "Frontier Cloud Cluster",
            "vram_gb": vram_gb,
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
            "description": "High-VRAM mode: Unlocks 8-step deep planning, full multi-device responsive testing, and visual critique."
        }
    elif tier == ExecutionTier.CLOUD_BALANCED:
        return {
            "tier": ExecutionTier.CLOUD_BALANCED,
            "tier_display": "CLOUD BALANCED (Kaggle/Colab T4 / 14B-32B)",
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
            "description": "Balanced mode: Unlocks 6 milestones, mobile+desktop responsive layout checks, and expanded ReAct turns."
        }
    elif tier == ExecutionTier.CPU_SAFE:
        return {
            "tier": ExecutionTier.CPU_SAFE,
            "tier_display": "CPU SAFE (Integrated Graphics / Zero-GPU Fallback)",
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
            "description": "Accessible mode: 3 focused milestones, 4k lightweight context, zero GPU requirements."
        }
    else:  # LITE_EDGE
        dynamic_ctx = local_hw.get("dynamic_context_window", 8192)
        return {
            "tier": ExecutionTier.LITE_EDGE,
            "tier_display": "LITE EDGE (Consumer RTX 3050 / Offline 8B)",
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
            "description": "Optimized offline mode: High-speed text DOM deltas, 4 focused milestones, zero token bloat."
        }
