import os
import json
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, Optional, List

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = DATA_DIR / "cloud_gpu_config.json"

DEFAULT_CONFIG = {
    "active_provider": "local",  # "local", "kaggle", "colab", "purchased", "cpu_safe"
    "compute_mode": "turbo",     # "turbo" (Cloud Dual T4), "balanced" (Local RTX 3050), "cpu_safe" (0% VRAM)
    "fallback_policy": "prompt_first",  # "prompt_first", "auto_cascade", "auto_resume"
    "custom_remote_url": None,   # e.g. "https://xxxx.loca.lt" or ngrok / cloudflare tunnel
    "waterfall_order": ["kaggle", "colab", "local", "cpu_safe"],
    "providers": {
        "local": {
            "name": "Local RTX 3050 (6GB VRAM)",
            "type": "local",
            "url": "http://127.0.0.1:11434",
            "status": "online",
            "tier": "Free / Offline",
            "total_quota": "Unlimited",
            "remaining_quota": "Unlimited",
            "unit": "Hours",
            "vram": "6.0 GB VRAM"
        },
        "kaggle": {
            "name": "Kaggle Free Dual T4 (30h / Wk)",
            "type": "free_cloud",
            "url": None,
            "connected": False,
            "username": None,
            "status": "ready",
            "tier": "Free Tier (Weekly)",
            "total_quota": 30.0,
            "remaining_quota": 30.0,
            "unit": "Hours/Wk",
            "vram": "30.0 GB (Dual T4)",
            "refresh_schedule": "Every Saturday 00:00 UTC"
        },
        "colab": {
            "name": "Google Colab Free T4 (12h Max)",
            "type": "free_cloud",
            "url": None,
            "connected": False,
            "status": "ready",
            "tier": "Free Tier (Daily)",
            "total_quota": 12.0,
            "remaining_quota": 12.0,
            "unit": "Hours/Session",
            "vram": "16.0 GB (Tesla T4)",
            "refresh_schedule": "Daily Session Reset"
        },
        "cpu_safe": {
            "name": "CPU Safe Mode (0% VRAM)",
            "type": "cpu",
            "url": "http://127.0.0.1:11434",
            "status": "ready",
            "tier": "Offline RAM (0% VRAM)",
            "total_quota": "Unlimited",
            "remaining_quota": "Unlimited",
            "unit": "RAM Safe",
            "vram": "0.0 GB (System RAM)"
        },
        "purchased": {
            "name": "Dedicated Paid Cloud (RunPod / Modal)",
            "type": "paid_credits",
            "url": None,
            "api_key_set": False,
            "status": "unconfigured",
            "tier": "Paid On-Demand",
            "purchased_credits": 0.00,
            "remaining_credits": 0.00,
            "unit": "USD ($)",
            "vram": "24GB - 80GB (A100 / H100 / RTX 4090)"
        }
    }
}


class CloudGpuBridge:
    """
    Unified manager for Local GPU, Free Cloud GPU Waterfall (Kaggle/Colab),
    CPU Safe Mode, and Fallback Policies (Prompt First, Auto-Cascade, Auto-Resume).
    """

    @classmethod
    def load_config(cls) -> Dict[str, Any]:
        if not CONFIG_FILE.exists():
            cls.save_config(DEFAULT_CONFIG)
            return DEFAULT_CONFIG
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Ensure all default top-level keys exist
                for k, v in DEFAULT_CONFIG.items():
                    if k not in data:
                        data[k] = v
                if "cpu_safe" not in data.get("providers", {}):
                    data["providers"]["cpu_safe"] = DEFAULT_CONFIG["providers"]["cpu_safe"]
                return data
        except Exception:
            return DEFAULT_CONFIG

    @classmethod
    def save_config(cls, data: Dict[str, Any]):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[CloudGpuBridge Error]: {e}")

    @classmethod
    def get_compute_mode(cls) -> str:
        """Returns active compute mode: 'turbo', 'balanced', or 'cpu_safe'."""
        config = cls.load_config()
        return config.get("compute_mode", "turbo")

    @classmethod
    def set_compute_mode(cls, mode: str) -> Dict[str, Any]:
        """Sets active compute mode ('turbo', 'balanced', 'cpu_safe') and syncs active_provider."""
        clean_mode = str(mode).strip().lower()
        if clean_mode not in ("turbo", "balanced", "cpu_safe"):
            raise ValueError(f"Unknown compute mode '{mode}'. Choose 'turbo', 'balanced', or 'cpu_safe'.")

        config = cls.load_config()
        config["compute_mode"] = clean_mode

        if clean_mode == "turbo":
            # Prefer kaggle or colab if available, otherwise kaggle
            current = config.get("active_provider")
            if current not in ("kaggle", "colab"):
                config["active_provider"] = "kaggle"
        elif clean_mode == "balanced":
            config["active_provider"] = "local"
        elif clean_mode == "cpu_safe":
            config["active_provider"] = "cpu_safe"

        cls.save_config(config)
        return cls.get_status()

    @classmethod
    def get_fallback_policy(cls) -> str:
        """Returns fallback policy: 'prompt_first', 'auto_cascade', or 'auto_resume'."""
        config = cls.load_config()
        return config.get("fallback_policy", "prompt_first")

    @classmethod
    def set_fallback_policy(cls, policy: str) -> Dict[str, Any]:
        """Sets fallback policy on cloud exhaustion: 'prompt_first', 'auto_cascade', or 'auto_resume'."""
        clean_policy = str(policy).strip().lower()
        if clean_policy not in ("prompt_first", "auto_cascade", "auto_resume"):
            raise ValueError(f"Unknown policy '{policy}'. Choose 'prompt_first', 'auto_cascade', or 'auto_resume'.")

        config = cls.load_config()
        config["fallback_policy"] = clean_policy
        cls.save_config(config)
        return {
            "status": "success",
            "fallback_policy": clean_policy,
            "compute_mode": config.get("compute_mode", "turbo")
        }

    _last_quota_sync: float = 0.0
    _cached_quotas: Dict[str, Any] = {}

    @classmethod
    def get_status(cls, force_sync: bool = False) -> Dict[str, Any]:
        config = cls.load_config()

        # Sync Kaggle live quota if available (cached for 60s for speed)
        now = time.time()
        if force_sync or (now - cls._last_quota_sync > 60.0):
            try:
                from backend.llm_studio.cloud_manager import CloudQuotaManager
                all_q = CloudQuotaManager.get_all_quotas()
                cls._cached_quotas = all_q
                cls._last_quota_sync = now
            except Exception:
                pass

        all_q = cls._cached_quotas
        if all_q:
            if "kaggle" in all_q:
                kq = all_q["kaggle"]
                config["providers"]["kaggle"]["connected"] = kq.get("connected", False)
                config["providers"]["kaggle"]["username"] = kq.get("username")
                config["providers"]["kaggle"]["remaining_quota"] = kq.get("remaining_hours", 30.0)
                config["providers"]["kaggle"]["total_quota"] = kq.get("total_hours", 30.0)
            if "colab" in all_q:
                cq = all_q["colab"]
                config["providers"]["colab"]["remaining_quota"] = cq.get("remaining_hours", 12.0)

        active_key = config.get("active_provider", "local")
        active_provider = config["providers"].get(active_key, config["providers"]["local"])

        # Test active endpoint connectivity
        active_url = cls.get_active_inference_url()
        is_alive = cls._test_endpoint_ping(active_url)

        return {
            "active_provider": active_key,
            "compute_mode": config.get("compute_mode", "turbo"),
            "fallback_policy": config.get("fallback_policy", "prompt_first"),
            "active_name": active_provider["name"],
            "active_url": active_url,
            "is_online": is_alive,
            "tier": active_provider["tier"],
            "remaining_quota": active_provider.get("remaining_quota", active_provider.get("remaining_credits")),
            "unit": active_provider["unit"],
            "vram": active_provider["vram"],
            "providers": config["providers"]
        }

    @classmethod
    def get_active_inference_url(cls) -> str:
        """Returns effective base URL for Ollama chat (Local 11434, Remote Tunnel, or CPU Safe)."""
        config = cls.load_config()
        compute_mode = config.get("compute_mode", "turbo")

        if compute_mode == "balanced" or compute_mode == "cpu_safe":
            return os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")

        active = config.get("active_provider", "local")
        if active in ("local", "cpu_safe"):
            return os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")

        provider = config.get("providers", {}).get(active, {})
        url = provider.get("url") or config.get("custom_remote_url")
        if url and str(url).startswith("http"):
            return str(url).rstrip("/")
        return "http://127.0.0.1:11434"

    @classmethod
    def switch_provider(cls, provider_key: str, custom_url: Optional[str] = None) -> Dict[str, Any]:
        """Switches active GPU target (e.g. 'local', 'kaggle', 'colab', 'cpu_safe', 'purchased')."""
        config = cls.load_config()
        if provider_key not in config["providers"]:
            raise ValueError(f"Unknown provider '{provider_key}'")

        config["active_provider"] = provider_key
        if provider_key in ("kaggle", "colab"):
            config["compute_mode"] = "turbo"
        elif provider_key == "local":
            config["compute_mode"] = "balanced"
        elif provider_key == "cpu_safe":
            config["compute_mode"] = "cpu_safe"

        if custom_url:
            clean_url = custom_url.strip().rstrip("/")
            config["custom_remote_url"] = clean_url
            config["providers"][provider_key]["url"] = clean_url

        cls.save_config(config)
        return cls.get_status()

    @classmethod
    def update_paid_credits(cls, purchased_usd: float, remaining_usd: float, api_key: Optional[str] = None) -> Dict[str, Any]:
        """Updates balance for users who bought cloud GPU compute credits (RunPod / Modal)."""
        config = cls.load_config()
        paid = config["providers"]["purchased"]
        paid["purchased_credits"] = round(float(purchased_usd), 2)
        paid["remaining_credits"] = round(float(remaining_usd), 2)
        if api_key:
            paid["api_key_set"] = True
        paid["status"] = "active" if remaining_usd > 0 else "exhausted"
        cls.save_config(config)
        return cls.get_status()

    @classmethod
    def _test_endpoint_ping(cls, url: Optional[str], timeout: float = 0.6) -> bool:
        """Pings /api/tags to see if Ollama or the remote bridge is responding."""
        if not url or not str(url).startswith("http"):
            return False
        try:
            ping_url = f"{url.rstrip('/')}/api/tags"
            req = urllib.request.Request(ping_url, headers={"User-Agent": "AITrainer-Bridge/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status == 200
        except Exception:
            return False

    @classmethod
    def get_waterfall_status(cls) -> Dict[str, Any]:
        """Tests health across each tier in the waterfall cascade."""
        config = cls.load_config()
        providers = config.get("providers", {})
        order = config.get("waterfall_order", ["kaggle", "colab", "local", "cpu_safe"])

        tier_statuses = []
        for pkey in order:
            pdata = providers.get(pkey, {})
            purl = pdata.get("url") or ("http://127.0.0.1:11434" if pkey in ("local", "cpu_safe") else None)
            is_online = cls._test_endpoint_ping(purl, timeout=0.4) if purl else False

            rem_q = pdata.get("remaining_quota", pdata.get("remaining_credits"))
            tier_statuses.append({
                "provider": pkey,
                "name": pdata.get("name", pkey),
                "url": purl,
                "is_online": is_online,
                "tier": pdata.get("tier"),
                "remaining_quota": rem_q,
                "unit": pdata.get("unit"),
                "vram": pdata.get("vram")
            })

        return {
            "compute_mode": config.get("compute_mode", "turbo"),
            "fallback_policy": config.get("fallback_policy", "prompt_first"),
            "active_provider": config.get("active_provider", "local"),
            "waterfall": tier_statuses
        }

    @classmethod
    def find_next_waterfall_tier(cls, current_tier: Optional[str] = None) -> Optional[str]:
        """
        Determines the next viable tier in the cascade sequence:
        Kaggle -> Colab -> Local RTX 3050 -> CPU Safe.
        """
        config = cls.load_config()
        order = config.get("waterfall_order", ["kaggle", "colab", "local", "cpu_safe"])
        curr = current_tier or config.get("active_provider", "kaggle")

        try:
            curr_idx = order.index(curr)
        except ValueError:
            curr_idx = -1

        candidates = order[curr_idx + 1:] if curr_idx >= 0 else order

        for cand in candidates:
            pdata = config.get("providers", {}).get(cand, {})
            purl = pdata.get("url") or ("http://127.0.0.1:11434" if cand in ("local", "cpu_safe") else None)
            # If it's local or cpu_safe, check local ping
            if cand in ("local", "cpu_safe"):
                if cls._test_endpoint_ping(purl, timeout=0.4):
                    return cand
            elif purl and cls._test_endpoint_ping(purl, timeout=0.5):
                return cand

        # Fallback to cpu_safe as baseline guarantee
        return "cpu_safe"

    @classmethod
    def get_cascaded_model(cls, target_tier: str, current_model: str) -> str:
        """
        Downscales model weights safely when cascading to smaller hardware
        so local GPU / CPU memory doesn't crash with Out-Of-Memory.
        """
        tier = target_tier.lower()
        curr = current_model.lower()

        if tier in ("kaggle", "colab", "turbo"):
            # Can run 32B or 14B comfortably
            if any(k in curr for k in ["70b", "32b", "14b"]):
                return current_model
            return "qwen2.5-coder:32b"

        elif tier in ("local", "balanced"):
            # RTX 3050 6GB: Run 7B or 8B
            if any(k in curr for k in ["70b", "32b", "14b"]):
                return "dolphin3:latest"
            return current_model or "dolphin3:latest"

        elif tier in ("cpu_safe", "cpu"):
            # 0% VRAM: Run fast, low-parameter model
            if any(k in curr for k in ["70b", "32b", "14b", "8b", "7b"]):
                return "qwen2.5-coder:1.5b"
            return current_model or "qwen2.5-coder:1.5b"

        return current_model

    @classmethod
    def check_waterfall_cascade(cls, current_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Evaluates active inference connection and determines cascade actions if quota exhausted or tunnel disconnected.
        """
        config = cls.load_config()
        active_key = config.get("active_provider", "local")
        policy = config.get("fallback_policy", "prompt_first")
        url = current_url or cls.get_active_inference_url()

        is_alive = cls._test_endpoint_ping(url, timeout=2.0)
        if is_alive:
            return {
                "current_alive": True,
                "current_tier": active_key,
                "policy": policy,
                "next_tier": None,
                "action_required": "none",
                "message": f"Active tier '{active_key}' is online and responding."
            }

        # Current endpoint is down/exhausted
        next_tier = cls.find_next_waterfall_tier(active_key)

        if policy == "auto_cascade":
            action = "auto_cascade"
            msg = f"Cloud tier '{active_key}' disconnected. Auto-cascading to '{next_tier}'."
        elif policy == "auto_resume":
            action = "auto_resume"
            msg = f"Cloud tier '{active_key}' exhausted. Execution frozen waiting for quota refill/tunnel."
        else:  # prompt_first
            action = "prompt_user"
            msg = f"Compute boundary reached on tier '{active_key}'. Paused for user choice."

        return {
            "current_alive": False,
            "current_tier": active_key,
            "policy": policy,
            "next_tier": next_tier,
            "action_required": action,
            "message": msg
        }

    @classmethod
    def get_cloud_one_click_script(cls, provider: str = "kaggle") -> str:
        """Returns the copy-paste 1-click startup script for Kaggle / Colab."""
        if provider.lower() == "colab":
            return (
                "# Google Colab Free Tesla T4 (16GB VRAM) 1-Click Bridge\n"
                "!curl -fsSL https://ollama.com/install.sh | sh\n"
                "!nohup ollama serve > ollama.log 2>&1 &\n"
                "!sleep 3\n"
                "!ollama pull qwen2.5-coder:14b\n"
                "!npx localtunnel --port 11434"
            )
        else:  # Kaggle
            return (
                "# Kaggle Dual T4 (30GB VRAM) 1-Click Bridge\n"
                "# In Kaggle Notebook: Accelerator -> Select 'GPU T4 x 2'\n"
                "!curl -fsSL https://ollama.com/install.sh | sh\n"
                "!nohup ollama serve > ollama.log 2>&1 &\n"
                "!sleep 3\n"
                "!ollama pull qwen2.5-coder:32b\n"
                "!npx localtunnel --port 11434"
            )
