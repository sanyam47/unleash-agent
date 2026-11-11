"""
Cloud LLM Provider Client (Bring Your Own Key - BYOK).
Enables Unleash-Agent to run on top of frontier cloud models:
- OpenRouter (Claude 3.5 Sonnet, DeepSeek-R1, GPT-4o, Llama 3.3 70B)
- OpenAI Direct (GPT-4o, o1, o3-mini)
- Anthropic Direct (Claude 3.5 Sonnet, Claude 3.5 Haiku)
- DeepSeek Direct (DeepSeek-V3, DeepSeek-Reasoner)
- Groq (Ultra-fast Llama 3.3 70B, DeepSeek-R1 Distill)
- Custom OpenAI-Compatible Base URL (vLLM, Together AI, LM Studio)

All API keys are encrypted at rest with AES-256-GCM via CredentialVault.
100% backward compatible: offline local Ollama remains the default.
"""

import os
import re
import json
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from backend.core.credential_vault import store_secret, get_secret, has_secret, delete_secret

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = DATA_DIR / "cloud_llm_config.json"

CLOUD_PROVIDERS: Dict[str, Dict[str, Any]] = {
    "openrouter": {
        "id": "openrouter",
        "name": "OpenRouter",
        "display_title": "OpenRouter (DeepSeek-R1 Free, Llama 3.3 Free, Claude 3.5)",
        "base_url": "https://openrouter.ai/api/v1/chat/completions",
        "default_model": "deepseek/deepseek-r1:free",
        "popular_models": [
            {"id": "deepseek/deepseek-r1:free", "name": "DeepSeek R1 (100% Free Reasoning)"},
            {"id": "meta-llama/llama-3.3-70b-instruct:free", "name": "Llama 3.3 70B Instruct (100% Free)"},
            {"id": "qwen/qwen-2.5-coder-32b-instruct:free", "name": "Qwen 2.5 Coder 32B (100% Free Coding)"},
            {"id": "google/gemini-2.0-flash-exp:free", "name": "Gemini 2.0 Flash (100% Free, 1M Context)"},
            {"id": "anthropic/claude-3.5-sonnet", "name": "Claude 3.5 Sonnet (Paid / Credits)"},
            {"id": "openai/gpt-4o", "name": "GPT-4o (Paid / Credits)"}
        ],
        "auth_type": "bearer",
        "doc_url": "https://openrouter.ai/keys"
    },
    "openai": {
        "id": "openai",
        "name": "OpenAI",
        "display_title": "OpenAI Direct (GPT-4o, o1, o3-mini)",
        "base_url": "https://api.openai.com/v1/chat/completions",
        "default_model": "gpt-4o",
        "popular_models": [
            {"id": "gpt-4o", "name": "GPT-4o (Multimodal Omni)"},
            {"id": "gpt-4o-mini", "name": "GPT-4o Mini (High Speed)"},
            {"id": "o3-mini", "name": "o3-mini (High-Tier Reasoning)"},
            {"id": "o1", "name": "o1 (Deep Reasoning)"}
        ],
        "auth_type": "bearer",
        "doc_url": "https://platform.openai.com/api-keys"
    },
    "anthropic": {
        "id": "anthropic",
        "name": "Anthropic",
        "display_title": "Anthropic Direct (Claude 3.5 Sonnet & Haiku)",
        "base_url": "https://api.anthropic.com/v1/messages",
        "default_model": "claude-3-5-sonnet-20241022",
        "popular_models": [
            {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet (Best Coding LLM)"},
            {"id": "claude-3-5-haiku-20241022", "name": "Claude 3.5 Haiku (Lightning Fast)"}
        ],
        "auth_type": "anthropic",
        "doc_url": "https://console.anthropic.com/settings/keys"
    },
    "deepseek": {
        "id": "deepseek",
        "name": "DeepSeek",
        "display_title": "DeepSeek Direct (DeepSeek-V3 & Reasoner R1)",
        "base_url": "https://api.deepseek.com/v1/chat/completions",
        "default_model": "deepseek-chat",
        "popular_models": [
            {"id": "deepseek-chat", "name": "DeepSeek-V3 (Chat & Coding)"},
            {"id": "deepseek-reasoner", "name": "DeepSeek-R1 (CoT Reasoning)"}
        ],
        "auth_type": "bearer",
        "doc_url": "https://platform.deepseek.com/api_keys"
    },
    "groq": {
        "id": "groq",
        "name": "Groq",
        "display_title": "Groq Cloud (LPU Ultra-Fast 300+ tok/s)",
        "base_url": "https://api.groq.com/openai/v1/chat/completions",
        "default_model": "qwen/qwen3.8-27b",
        "popular_models": [
            {"id": "qwen/qwen3.8-27b", "name": "Qwen 2.5 Coder 27B (Ultra-Fast Coding)"},
            {"id": "openai/gpt-oss-120b", "name": "GPT-OSS 120B (Flagship Reasoning)"},
            {"id": "openai/gpt-oss-20b", "name": "GPT-OSS 20B (High Speed)"},
            {"id": "llama-3.3-70b-versatile", "name": "Llama 3.3 70B (Versatile)"}
        ],
        "auth_type": "bearer",
        "doc_url": "https://console.groq.com/keys"
    },
    "custom": {
        "id": "custom",
        "name": "Custom OpenAI-Compatible",
        "display_title": "Custom Base URL (vLLM, LM Studio, Together, LocalAI)",
        "base_url": "http://localhost:8000/v1/chat/completions",
        "default_model": "default",
        "popular_models": [
            {"id": "default", "name": "Default Model Endpoint"}
        ],
        "auth_type": "bearer",
        "doc_url": ""
    }
}


class CloudLlmManager:
    """Manages cloud LLM provider credentials, model routing, and unified inference."""

    @classmethod
    def load_config(cls) -> Dict[str, Any]:
        default_cfg = {
            "active_provider": None,
            "active_model": None,
            "providers": {}
        }
        if not CONFIG_FILE.exists():
            return default_cfg
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {**default_cfg, **data}
        except Exception:
            return default_cfg

    @classmethod
    def save_config(cls, cfg: Dict[str, Any]):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
        except Exception as e:
            print(f"[CloudLlmManager] Error saving config: {e}")

    @classmethod
    def get_status(cls) -> Dict[str, Any]:
        """Returns public provider statuses without leaking decrypted keys."""
        cfg = cls.load_config()
        active_prov = cfg.get("active_provider")
        active_mod = cfg.get("active_model")

        statuses = []
        for pid, meta in CLOUD_PROVIDERS.items():
            has_key = has_secret(f"cloud_llm_{pid}")
            prov_cfg = cfg.get("providers", {}).get(pid, {})
            key_val = get_secret(f"cloud_llm_{pid}") or ""
            masked_key = (key_val[:6] + "••••" + key_val[-4:]) if len(key_val) >= 10 else ("••••" if has_key else "")

            statuses.append({
                "id": pid,
                "name": meta["name"],
                "display_title": meta["display_title"],
                "configured": has_key,
                "masked_key": masked_key,
                "active": (pid == active_prov),
                "model": prov_cfg.get("model", meta["default_model"]),
                "custom_url": prov_cfg.get("custom_url", meta["base_url"]),
                "popular_models": meta["popular_models"],
                "doc_url": meta["doc_url"]
            })

        return {
            "active_provider": active_prov,
            "active_model": active_mod,
            "providers": statuses
        }

    @classmethod
    def save_key(cls, provider: str, api_key: str, model: Optional[str] = None, custom_url: Optional[str] = None, set_active: bool = True) -> Dict[str, Any]:
        """Encrypts key into CredentialVault and updates provider config."""
        pid = provider.lower().strip()
        if pid not in CLOUD_PROVIDERS:
            raise ValueError(f"Unknown provider '{provider}'. Choose from: {list(CLOUD_PROVIDERS.keys())}")

        clean_key = str(api_key or "").strip()
        if clean_key == "KEEP_EXISTING":
            if not has_secret(f"cloud_llm_{pid}"):
                raise ValueError("No existing key found to keep.")
        else:
            if not clean_key and pid != "custom":
                raise ValueError("API Key cannot be empty.")
            # Save encrypted key in AES-256 vault
            store_secret(f"cloud_llm_{pid}", clean_key)

        cfg = cls.load_config()
        if "providers" not in cfg:
            cfg["providers"] = {}

        selected_model = (model or CLOUD_PROVIDERS[pid]["default_model"]).strip()
        cfg["providers"][pid] = {
            "configured": True,
            "model": selected_model,
            "custom_url": custom_url or CLOUD_PROVIDERS[pid]["base_url"],
            "last_updated": time.time()
        }

        if set_active:
            cfg["active_provider"] = pid
            cfg["active_model"] = f"cloud:{pid}:{selected_model}"

        cls.save_config(cfg)

        return {
            "status": "success",
            "provider": pid,
            "model": selected_model,
            "active_model": cfg.get("active_model"),
            "message": f"Successfully encrypted API key for {CLOUD_PROVIDERS[pid]['name']} in AES-256 vault."
        }

    @classmethod
    def remove_key(cls, provider: str) -> Dict[str, Any]:
        """Deletes encrypted key and resets active provider."""
        pid = provider.lower().strip()
        delete_secret(f"cloud_llm_{pid}")

        cfg = cls.load_config()
        if "providers" in cfg and pid in cfg["providers"]:
            del cfg["providers"][pid]

        if cfg.get("active_provider") == pid:
            cfg["active_provider"] = None
            cfg["active_model"] = None

        cls.save_config(cfg)
        return {"status": "success", "provider": pid, "message": f"Removed credentials for {pid}."}

    @classmethod
    def test_connection(cls, provider: str, api_key: Optional[str] = None, model: Optional[str] = None, custom_url: Optional[str] = None) -> Dict[str, Any]:
        """Sends a 1-token test prompt to verify authentication and connectivity."""
        pid = provider.lower().strip()
        if pid not in CLOUD_PROVIDERS:
            return {"status": "error", "message": f"Unknown provider '{provider}'"}

        key_to_use = (api_key or get_secret(f"cloud_llm_{pid}") or "").strip()
        if not key_to_use and pid != "custom":
            return {"status": "error", "message": f"No API key provided or found in vault for '{pid}'."}

        meta = CLOUD_PROVIDERS[pid]
        target_model = model or meta["default_model"]
        target_url = custom_url or meta["base_url"]

        start_t = time.perf_counter()
        try:
            if meta["auth_type"] == "anthropic":
                # Anthropic Messages API
                payload = {
                    "model": target_model,
                    "max_tokens": 5,
                    "messages": [{"role": "user", "content": "Respond with 'OK'."}]
                }
                headers = {
                    "x-api-key": key_to_use,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                }
            else:
                # Standard OpenAI-Compatible API
                payload = {
                    "model": target_model,
                    "max_tokens": 5,
                    "messages": [{"role": "user", "content": "Respond with 'OK'."}],
                    "temperature": 0.1
                }
                headers = {
                    "Authorization": f"Bearer {key_to_use}",
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) UnleashAgent/1.0"
                }
                if pid == "openrouter":
                    headers["HTTP-Referer"] = "https://github.com/sanyam47/unleash-agent"
                    headers["X-Title"] = "Unleash-Agent"

            req = urllib.request.Request(
                target_url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                res_body = json.loads(resp.read().decode("utf-8"))

            dur_ms = round((time.perf_counter() - start_t) * 1000, 1)

            # Extract greeting
            reply_text = ""
            if "choices" in res_body and res_body["choices"]:
                msg = res_body["choices"][0].get("message", {})
                reply_text = msg.get("content") or msg.get("reasoning") or ""
            elif "content" in res_body and isinstance(res_body["content"], list):
                reply_text = res_body["content"][0].get("text", "")

            return {
                "status": "success",
                "provider": pid,
                "model": target_model,
                "latency_ms": dur_ms,
                "reply": str(reply_text or "").strip(),
                "message": f"Connection verified in {dur_ms}ms! Authentication successful."
            }

        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8", errors="ignore")
            try:
                err_json = json.loads(err_msg)
                err_detail = err_json.get("error", {}).get("message") or err_msg
            except Exception:
                err_detail = err_msg

            if e.code in (401, 403):
                msg = f"Authentication Failed (HTTP {e.code}): Invalid API Key."
            elif e.code == 429:
                msg = f"Rate Limit or Insufficient Quota (HTTP 429): Check your account balance."
            elif e.code == 404:
                msg = f"Model Not Found (HTTP 404): Model '{target_model}' may not be supported by your key."
            else:
                msg = f"API Error (HTTP {e.code}): {err_detail[:120]}"

            return {"status": "error", "http_code": e.code, "message": msg}

        except Exception as e:
            return {"status": "error", "message": f"Connection Error: {str(e)}"}

    @classmethod
    def get_configured_models(cls) -> List[Dict[str, Any]]:
        """Returns list of all configured cloud models for display in the model dropdown."""
        cfg = cls.load_config()
        configured = []
        for pid, pdata in cfg.get("providers", {}).items():
            if not has_secret(f"cloud_llm_{pid}") and pid != "custom":
                continue
            meta = CLOUD_PROVIDERS.get(pid, {})
            model_id = pdata.get("model", meta.get("default_model", "default"))
            configured.append({
                "id": f"cloud:{pid}:{model_id}",
                "name": f"Cloud: {meta.get('name', pid)} ({model_id})",
                "provider": pid,
                "model": model_id,
                "is_cloud": True,
                "parameter_size": "Frontier Cloud",
                "size_gb": 0.0,
                "quantization": "API"
            })
        return configured


def is_cloud_model(model_name: str) -> bool:
    """Detects whether a model identifier represents a cloud provider endpoint."""
    if not model_name:
        return False
    m = model_name.lower().strip()
    if m.startswith("cloud:"):
        return True
    # Known cloud model patterns if passed directly
    if any(m.startswith(prefix) for prefix in ("claude-3", "gpt-4", "o1", "o3", "deepseek-chat", "deepseek-reasoner", "anthropic/", "deepseek/")):
        return True
    return False


def parse_cloud_model_string(model_name: str) -> Tuple[str, str]:
    """
    Parses a cloud model string into (provider_id, actual_model_name).
    Supports:
      'cloud:groq:llama-3.3-70b-versatile' -> ('groq', 'llama-3.3-70b-versatile')
      'Cloud: Groq (llama-3.3-70b-versatile)' -> ('groq', 'llama-3.3-70b-versatile')
      'cloud:openrouter:cohere/north-mini-code:free' -> ('openrouter', 'cohere/north-mini-code:free')
    """
    clean_model = (model_name or "").strip()
    lower_model = clean_model.lower()
    
    provider_id = "openrouter"
    actual_model = clean_model

    if "(" in clean_model and ")" in clean_model:
        inner = re.search(r'\((.*?)\)', clean_model)
        if inner:
            actual_model = inner.group(1).strip()
        if "groq" in lower_model:
            provider_id = "groq"
        elif "anthropic" in lower_model or "claude" in lower_model:
            provider_id = "anthropic" if has_secret("cloud_llm_anthropic") else "openrouter"
        elif "openai" in lower_model or "gpt" in lower_model:
            provider_id = "openai" if has_secret("cloud_llm_openai") else "openrouter"
        elif "deepseek" in lower_model:
            provider_id = "deepseek" if has_secret("cloud_llm_deepseek") else "openrouter"
        elif "openrouter" in lower_model:
            provider_id = "openrouter"
    elif lower_model.startswith("cloud:"):
        parts = clean_model.split(":", 2)
        if len(parts) >= 3:
            provider_id = parts[1].strip().lower()
            actual_model = parts[2].strip()
        elif len(parts) == 2:
            provider_id = parts[1].strip().lower()
            actual_model = CLOUD_PROVIDERS.get(provider_id, {}).get("default_model", "gpt-4o")
    else:
        if "groq" in lower_model:
            provider_id = "groq"
        elif "claude" in lower_model:
            provider_id = "anthropic" if has_secret("cloud_llm_anthropic") else "openrouter"
        elif "gpt" in lower_model or lower_model.startswith("o1") or lower_model.startswith("o3"):
            provider_id = "openai" if has_secret("cloud_llm_openai") else "openrouter"
        elif "deepseek" in lower_model:
            provider_id = "deepseek" if has_secret("cloud_llm_deepseek") else "openrouter"

    return provider_id, actual_model


def call_cloud_llm_chat(
    model: str,
    messages: List[Dict[str, Any]],
    temperature: float = 0.35,
    max_tokens: int = 4096
) -> Dict[str, Any]:
    """
    Executes a chat completion against the configured Cloud LLM API.
    Normalizes response to match Unleash-Agent ReAct output schema:
      {"content": ..., "eval_count": ..., "duration_sec": ...}
    """
    provider_id, actual_model = parse_cloud_model_string(model)

    cfg = CloudLlmManager.load_config()
    prov_cfg = cfg.get("providers", {}).get(provider_id, {})
    meta = CLOUD_PROVIDERS.get(provider_id, CLOUD_PROVIDERS["openrouter"])

    target_url = prov_cfg.get("custom_url") or meta["base_url"]
    api_key = get_secret(f"cloud_llm_{provider_id}") or ""

    if not api_key and provider_id != "custom":
        raise ValueError(
            f"No API key configured for Cloud Provider '{provider_id}'. "
            f"Please save your API key in the UI under Connect Cloud LLM."
        )

    start_t = time.perf_counter()

    if meta["auth_type"] == "anthropic":
        # Anthropic format: separate system prompt from conversational messages
        system_content = ""
        anthropic_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_content += (content + "\n\n")
            else:
                anthropic_messages.append({"role": role, "content": content})

        if not anthropic_messages:
            anthropic_messages = [{"role": "user", "content": "Proceed."}]

        payload = {
            "model": actual_model,
            "max_tokens": max_tokens,
            "messages": anthropic_messages,
            "temperature": temperature
        }
        if system_content.strip():
            payload["system"] = system_content.strip()

        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) UnleashAgent/1.0"
        }
    else:
        # Standard OpenAI-Compatible format
        payload = {
            "model": actual_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) UnleashAgent/1.0"
        }
        if provider_id == "openrouter":
            headers["HTTP-Referer"] = "https://github.com/sanyam47/unleash-agent"
            headers["X-Title"] = "Unleash-Agent"

    req = urllib.request.Request(
        target_url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers
    )

    # Execute API request with automatic 429 rate-limit backoff retry
    max_retries = 3
    backoff = 2.0
    res_data = None
    last_err = None

    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
                break
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code == 429 and attempt < max_retries - 1:
                # Read rate limit error message
                err_body = e.read().decode("utf-8", errors="ignore")
                print(f"[CloudLLM] HTTP 429 Rate Limit (attempt {attempt+1}/{max_retries}). Backing off for {backoff:.1f}s...")
                time.sleep(backoff)
                backoff *= 2.0
                continue
            err_body = e.read().decode("utf-8", errors="ignore")
            try:
                err_detail = json.loads(err_body).get("error", {}).get("message", err_body)
            except Exception:
                err_detail = err_body
            raise RuntimeError(f"Cloud LLM API error (HTTP {e.code}): {err_detail[:200]}") from e
        except Exception as e:
            last_err = e
            raise e

    if res_data is None:
        raise RuntimeError(f"Cloud LLM request failed after {max_retries} retries: {last_err}")

    dur = time.perf_counter() - start_t

    content = ""
    token_count = 0

    if "choices" in res_data and res_data["choices"]:
        choice = res_data["choices"][0]
        msg = choice.get("message", {})
        # Robustly extract content from standard, reasoning, or text fields
        raw_content = msg.get("content")
        if raw_content is None:
            raw_content = msg.get("reasoning") or msg.get("reasoning_content") or choice.get("text", "")
        content = str(raw_content or "")
        token_count = res_data.get("usage", {}).get("completion_tokens", 0)
    elif "content" in res_data and isinstance(res_data["content"], list):
        content = "".join([str(c.get("text", "")) for c in res_data["content"] if c.get("type") == "text"])
        token_count = res_data.get("usage", {}).get("output_tokens", 0)

    return {
        "content": content,
        "eval_count": token_count,
        "duration_sec": dur
    }
