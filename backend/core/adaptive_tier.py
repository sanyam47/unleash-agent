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
    CLOUD_BALANCED = "cloud_balanced"
    FRONTIER_ULTRA = "frontier_ultra"


def probe_local_gpu_hardware() -> Dict[str, Any]:
    """
    Probes host machine for dedicated GPU name and total VRAM in GB.
    Fast non-blocking check via nvidia-smi with WMI / system RAM fallback.
    """
    try:
        proc = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=2.0
        )
        if proc.returncode == 0 and proc.stdout.strip():
            first_line = proc.stdout.strip().splitlines()[0]
            parts = [p.strip() for p in first_line.split(",")]
            if len(parts) >= 2:
                gpu_name = parts[0]
                total_mb = float(parts[1])
                return {
                    "has_gpu": True,
                    "gpu_name": gpu_name,
                    "vram_gb": round(total_mb / 1024.0, 1),
                    "source": "nvidia-smi"
                }
    except Exception:
        pass

    # Fallback to system RAM probe
    try:
        import psutil
        ram_gb = round(psutil.virtual_memory().total / (1024.0 ** 3), 1)
        return {
            "has_gpu": False,
            "gpu_name": f"CPU / Integrated ({ram_gb}GB System RAM)",
            "vram_gb": min(4.0, ram_gb / 4.0),
            "source": "psutil"
        }
    except Exception:
        return {
            "has_gpu": False,
            "gpu_name": "Standard Host CPU",
            "vram_gb": 4.0,
            "source": "fallback"
        }


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

    # Check Model Multimodal / Param Capabilities
    m_lower = (model_name or "").lower()
    is_multimodal = any(k in m_lower for k in ["vision", "vl", "llava", "multimodal", "gpt-4", "claude", "gemini"])
    is_large_weight = any(k in m_lower for k in ["14b", "32b", "70b"])

    # Determine Tier dynamically
    if override_tier:
        tier = override_tier
    elif is_multimodal or vram_gb >= 40.0:
        tier = ExecutionTier.FRONTIER_ULTRA
    elif is_cloud_active or vram_gb >= 12.0 or is_large_weight:
        tier = ExecutionTier.CLOUD_BALANCED
    elif not local_hw.get("has_gpu", False) or vram_gb < 2.0:
        tier = ExecutionTier.CPU_SAFE
    else:
        tier = ExecutionTier.LITE_EDGE

    # Generate Tier-specific Adaptive Profiles
    if tier == ExecutionTier.FRONTIER_ULTRA:
        return {
            "tier": ExecutionTier.FRONTIER_ULTRA,
            "tier_display": "FRONTIER ULTRA (Enterprise Cloud / Multimodal Vision)",
            "gpu_name": gpu_name,
            "vram_gb": vram_gb,
            "is_cloud": is_cloud_active,
            "max_milestones": 8,
            "max_steps": 36,
            "context_window": 65536,
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
            "is_cloud": is_cloud_active,
            "max_milestones": 6,
            "max_steps": 24,
            "context_window": 32768,
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
            "visual_mode": "dom_delta",
            "viewports": [
                {"name": "desktop", "width": 1280, "height": 800}
            ],
            "description": "Accessible mode: 3 focused milestones, 4k lightweight context, zero GPU requirements."
        }
    else:  # LITE_EDGE
        return {
            "tier": ExecutionTier.LITE_EDGE,
            "tier_display": "LITE EDGE (Consumer RTX 3050 / Offline 8B)",
            "gpu_name": gpu_name,
            "vram_gb": vram_gb,
            "is_cloud": False,
            "max_milestones": 4,
            "max_steps": 14,
            "context_window": 8192,
            "visual_mode": "dom_delta",
            "viewports": [
                {"name": "desktop", "width": 1280, "height": 800}
            ],
            "description": "Optimized offline mode: High-speed text DOM deltas, 4 focused milestones, zero token bloat."
        }
