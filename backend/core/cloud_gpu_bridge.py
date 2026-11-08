import os
import json
import time
import urllib.request
from pathlib import Path
from typing import Dict, Any, Optional

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = DATA_DIR / "cloud_gpu_config.json"

DEFAULT_CONFIG = {
    "active_provider": "local",  # "local", "kaggle", "colab", "runpod", "modal"
    "custom_remote_url": None,   # e.g. "https://xxxx.loca.lt" or ngrok / cloudflare tunnel
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
    Unified manager for Local, Free Cloud (Kaggle/Colab), and Paid Credits (RunPod/Modal).
    Handles 1-click endpoint switching, quota tracking, and live credit balance.
    """

    @classmethod
    def load_config(cls) -> Dict[str, Any]:
        if not CONFIG_FILE.exists():
            cls.save_config(DEFAULT_CONFIG)
            return DEFAULT_CONFIG
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
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
    def get_status(cls) -> Dict[str, Any]:
        config = cls.load_config()
        
        # Sync Kaggle live quota if available from CloudQuotaManager
        try:
            from backend.llm_studio.cloud_manager import CloudQuotaManager
            all_q = CloudQuotaManager.get_all_quotas()
            if "kaggle" in all_q:
                kq = all_q["kaggle"]
                config["providers"]["kaggle"]["connected"] = kq.get("connected", False)
                config["providers"]["kaggle"]["username"] = kq.get("username")
                config["providers"]["kaggle"]["remaining_quota"] = kq.get("remaining_hours", 30.0)
                config["providers"]["kaggle"]["total_quota"] = kq.get("total_hours", 30.0)
            if "colab" in all_q:
                cq = all_q["colab"]
                config["providers"]["colab"]["remaining_quota"] = cq.get("remaining_hours", 12.0)
        except Exception:
            pass

        active_key = config.get("active_provider", "local")
        active_provider = config["providers"].get(active_key, config["providers"]["local"])
        
        # Test endpoint connectivity
        active_url = cls.get_active_inference_url()
        is_alive = cls._test_endpoint_ping(active_url)
        
        return {
            "active_provider": active_key,
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
        """Returns the effective base URL for Ollama chat (Local 11434 or Remote Tunnel)."""
        config = cls.load_config()
        active = config.get("active_provider", "local")
        if active == "local":
            return os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
        
        provider = config.get("providers", {}).get(active, {})
        url = provider.get("url") or config.get("custom_remote_url")
        if url and str(url).startswith("http"):
            return str(url).rstrip("/")
        return "http://127.0.0.1:11434"

    @classmethod
    def switch_provider(cls, provider_key: str, custom_url: Optional[str] = None) -> Dict[str, Any]:
        """Switches active GPU target (e.g. 'local', 'kaggle', 'colab', 'purchased')."""
        config = cls.load_config()
        if provider_key not in config["providers"]:
            raise ValueError(f"Unknown provider '{provider_key}'")
            
        config["active_provider"] = provider_key
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
    def _test_endpoint_ping(cls, url: str) -> bool:
        """Pings /api/tags to see if Ollama or the remote bridge is responding."""
        try:
            ping_url = f"{url.rstrip('/')}/api/tags"
            req = urllib.request.Request(ping_url, headers={"User-Agent": "AITrainer-Bridge/1.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status == 200
        except Exception:
            return False

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
        else: # Kaggle
            return (
                "# Kaggle Dual T4 (30GB VRAM) 1-Click Bridge\n"
                "# In Kaggle Notebook: Accelerator -> Select 'GPU T4 x 2'\n"
                "!curl -fsSL https://ollama.com/install.sh | sh\n"
                "!nohup ollama serve > ollama.log 2>&1 &\n"
                "!sleep 3\n"
                "!ollama pull qwen2.5-coder:32b\n"
                "!npx localtunnel --port 11434"
            )
