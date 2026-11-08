import os
import re
import json
import time
from datetime import datetime
from typing import Dict, Any, Optional

QUOTA_CACHE_FILE = os.path.join(os.getcwd(), "cloud_packages", "cloud_quota_cache.json")


class CloudQuotaManager:
    """
    Manages free cloud GPU quotas, tracks remaining training hours across Kaggle (30h/week free),
    Google Colab (12h session free), and local RTX 3050 GPU.
    """

    @staticmethod
    def get_credentials_status() -> Dict[str, Any]:
        """Checks if Kaggle credentials exist on the host machine."""
        token_env = os.environ.get("KAGGLE_API_TOKEN") or os.environ.get("KAGGLE_KEY")
        user_env = os.environ.get("KAGGLE_USERNAME")
        
        token_file = os.path.expanduser("~/.kaggle/access_token")
        json_file = os.path.expanduser("~/.kaggle/kaggle.json")
        
        has_env = bool(token_env)
        has_file = os.path.exists(token_file) or os.path.exists(json_file)
        
        return {
            "has_credentials": has_env or has_file,
            "username": user_env or (CloudQuotaManager._read_username_from_file() if has_file else None)
        }

    @staticmethod
    def _read_username_from_file() -> Optional[str]:
        json_file = os.path.expanduser("~/.kaggle/kaggle.json")
        if os.path.exists(json_file):
            try:
                with open(json_file, "r") as f:
                    data = json.load(f)
                    return data.get("username")
            except Exception:
                pass
        return None

    @staticmethod
    def save_kaggle_credentials(token_or_username: str, key: Optional[str] = None) -> Dict[str, Any]:
        """Saves Kaggle API token or username+key pair and tests connection."""
        kaggle_dir = os.path.expanduser("~/.kaggle")
        os.makedirs(kaggle_dir, exist_ok=True)
        
        token_or_username = token_or_username.strip()
        if key and key.strip():
            # Username + Key format
            json_path = os.path.join(kaggle_dir, "kaggle.json")
            creds = {"username": token_or_username, "key": key.strip()}
            with open(json_path, "w") as f:
                json.dump(creds, f)
            # Set environment as well
            os.environ["KAGGLE_USERNAME"] = creds["username"]
            os.environ["KAGGLE_KEY"] = creds["key"]
        else:
            # Single Access Token format
            access_token_path = os.path.join(kaggle_dir, "access_token")
            with open(access_token_path, "w") as f:
                f.write(token_or_username)
            os.environ["KAGGLE_API_TOKEN"] = token_or_username

        # Test authentication
        try:
            import kaggle
            kaggle.api.authenticate()
            quota_data = CloudQuotaManager.get_live_kaggle_quota()
            return {
                "status": "success",
                "message": "Successfully connected to Kaggle API!",
                "quota": quota_data
            }
        except Exception as e:
            return {
                "status": "warning",
                "message": f"Saved credentials, but Kaggle verification returned: {str(e)}",
                "detail": str(e)
            }

    @staticmethod
    def get_live_kaggle_quota() -> Dict[str, Any]:
        """Queries live Kaggle API for accelerator quota if credentials exist, else returns baseline."""
        status = CloudQuotaManager.get_credentials_status()
        
        # Load local session usage tracking cache
        local_usage = CloudQuotaManager._read_usage_cache()
        
        if status["has_credentials"]:
            try:
                import kaggle
                kaggle.api.authenticate()
                quota_resp = kaggle.api.quota_view()
                
                # Parse quota_resp
                gpu_info = getattr(quota_resp, "gpu_quota", None)
                refresh_time = getattr(quota_resp, "quota_refresh_time", None)
                
                total_hours = 30.0
                used_hours = local_usage.get("kaggle_used_hours", 0.0)
                remaining_hours = max(0.0, total_hours - used_hours)
                
                if gpu_info:
                    # If Kaggle returns structured fields
                    used_sec = getattr(gpu_info, "used_seconds", None)
                    allocated_sec = getattr(gpu_info, "allocated_seconds", None)
                    if allocated_sec is not None:
                        total_hours = round(allocated_sec / 3600, 1)
                    if used_sec is not None:
                        used_hours = round(used_sec / 3600, 2)
                        remaining_hours = max(0.0, round(total_hours - used_hours, 2))

                refresh_str = str(refresh_time) if refresh_time else "Every Saturday 00:00 UTC"
                
                return {
                    "connected": True,
                    "username": status["username"] or "Kaggle User",
                    "total_hours": total_hours,
                    "used_hours": used_hours,
                    "remaining_hours": remaining_hours,
                    "refresh_schedule": refresh_str,
                    "accelerator": "Dual NVIDIA Tesla T4 (32 GB VRAM)",
                    "tier": "Free Tier (Weekly Quota)"
                }
            except Exception as e:
                pass
                
        # Baseline free tier (30h/week)
        used_hours = local_usage.get("kaggle_used_hours", 0.0)
        remaining_hours = max(0.0, round(30.0 - used_hours, 2))
        
        return {
            "connected": False,
            "username": None,
            "total_hours": 30.0,
            "used_hours": used_hours,
            "remaining_hours": remaining_hours,
            "refresh_schedule": "Every Saturday 00:00 UTC",
            "accelerator": "Dual NVIDIA Tesla T4 (32 GB VRAM)",
            "tier": "Free Tier (30h / Week)"
        }

    @staticmethod
    def _read_usage_cache() -> Dict[str, Any]:
        if os.path.exists(QUOTA_CACHE_FILE):
            try:
                with open(QUOTA_CACHE_FILE, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"kaggle_used_hours": 0.0, "colab_session_hours": 0.0, "last_reset": time.time()}

    @staticmethod
    def record_training_time(provider: str, duration_seconds: float):
        """Records time spent training in the cloud to decrement quota accurately."""
        data = CloudQuotaManager._read_usage_cache()
        hours = duration_seconds / 3600.0
        if provider == "kaggle":
            data["kaggle_used_hours"] = round(data.get("kaggle_used_hours", 0.0) + hours, 3)
        elif provider == "colab":
            data["colab_session_hours"] = round(data.get("colab_session_hours", 0.0) + hours, 3)
        
        os.makedirs(os.path.dirname(QUOTA_CACHE_FILE), exist_ok=True)
        with open(QUOTA_CACHE_FILE, "w") as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def get_all_quotas() -> Dict[str, Any]:
        """Returns comprehensive quota snapshot for Kaggle, Colab, and Local GPU."""
        kaggle_quota = CloudQuotaManager.get_live_kaggle_quota()
        usage = CloudQuotaManager._read_usage_cache()
        
        colab_used = usage.get("colab_session_hours", 0.0)
        colab_remaining = max(0.0, round(12.0 - colab_used, 2))
        
        return {
            "kaggle": kaggle_quota,
            "colab": {
                "tier": "Free Tier",
                "max_session_hours": 12.0,
                "used_session_hours": colab_used,
                "remaining_hours": colab_remaining,
                "accelerator": "NVIDIA Tesla T4 (16 GB VRAM)",
                "reset_type": "Per Session (Resets daily / 12h max)"
            },
            "local": {
                "gpu": "NVIDIA GeForce RTX 3050 6GB Laptop GPU",
                "vram_gb": 5.8,
                "hours": "Unlimited",
                "cost": "100% Free / Offline"
            }
        }


class KaggleAutoPilotRunner:
    """
    Automates 1-Click Kaggle Cloud training via official Kaggle API:
    1. Prepares self-contained notebook embedding the curated dataset
    2. Generates kernel-metadata.json targeting Kaggle's Dual T4 GPU accelerator
    3. Pushes the kernel to Kaggle cloud (kaggle.api.kernels_push)
    4. Tracks status (queued -> running -> complete)
    5. Pulls the finished GGUF model and auto-imports into Ollama on local machine!
    """

    @staticmethod
    def prepare_and_push_kernel(
        session_id: str,
        config: Dict[str, Any],
        samples: list,
        domain_topic: str = "specialized task"
    ) -> Dict[str, Any]:
        creds = CloudQuotaManager.get_credentials_status()
        if not creds.get("has_credentials"):
            raise ValueError("Kaggle credentials not configured. Please connect your Kaggle API key first.")

        username = creds.get("username")
        if not username:
            try:
                import kaggle
                kaggle.api.authenticate()
                username = kaggle.api.get_config_value("username")
            except Exception:
                pass
        if not username:
            username = "sanyam47"

        clean_name = re.sub(r'[^a-zA-Z0-9_\-]', '-', config.get("output_model_name", "custom-llm").strip().lower()).strip('-')
        if not clean_name:
            clean_name = "custom-llm"
        short_id = session_id[:6]
        slug = f"train-{clean_name}-{short_id}"[:45].strip('-')
        title = f"Train {clean_name} {short_id}"[:50]

        kernel_dir = os.path.join(os.getcwd(), "cloud_packages", "kaggle_runs", slug)
        os.makedirs(kernel_dir, exist_ok=True)

        base_model = config.get("base_model", "meta-llama/Llama-3.2-1B-Instruct")
        lora_r = config.get("lora_rank", 16)
        lora_alpha = config.get("lora_alpha", 32)
        epochs = config.get("epochs", 3)
        lr = config.get("learning_rate", 2e-4)
        algo = config.get("algorithm", "dora").lower()
        use_dora = "True" if algo == "dora" else "False"

        # Embedded JSON samples
        samples_json = json.dumps(samples)

        notebook_cells = [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    f"# 🚀 Auto-Pilot Cloud Training: {clean_name}\\n",
                    f"**Base Model:** `{base_model}` | **Method:** {'DoRA' if use_dora == 'True' else 'LoRA'} | **Dual T4 GPUs (32 GB VRAM)**\\n",
                    "Dispatched automatically by AI Studio Personal Foundry."
                ]
            },
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": None,
                "outputs": [],
                "source": [
                    "# Step 0: Unpack Curated Dataset\\n",
                    "import json, os\\n\\n",
                    f"samples = {samples_json}\\n",
                    "with open('dataset.jsonl', 'w', encoding='utf-8') as f:\\n",
                    "    for s in samples:\\n",
                    "        f.write(json.dumps(s) + '\\n')\\n",
                    "print(f'✅ Curated dataset unpacked: {len(samples)} samples ready!')"
                ]
            },
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": None,
                "outputs": [],
                "source": [
                    "# Step 1: Install High-Performance Unsloth & Dependencies\\n",
                    "!pip install --upgrade --no-cache-dir pip\\n",
                    "!pip install \"unsloth[kaggle-new] @ git+https://github.com/unslothai/unsloth.git\" torch torchvision transformers datasets trl peft bitsandbytes accelerate"
                ]
            },
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": None,
                "outputs": [],
                "source": [
                    "# Step 2: Load Model with 4-bit Quantization\\n",
                    "from unsloth import FastLanguageModel\\n",
                    "import torch\\n\\n",
                    f"model, tokenizer = FastLanguageModel.from_pretrained(\\n",
                    f"    model_name='{base_model}',\\n",
                    "    max_seq_length=2048,\\n",
                    "    dtype=None,\\n",
                    "    load_in_4bit=True,\\n",
                    ")\\n\\n",
                    "model = FastLanguageModel.get_peft_model(\\n",
                    "    model,\\n",
                    f"    r={lora_r},\\n",
                    f"    lora_alpha={lora_alpha},\\n",
                    "    target_modules=['q_proj', 'k_proj', 'v_proj', 'o_proj', 'gate_proj', 'up_proj', 'down_proj'],\\n",
                    f"    use_dora={use_dora},\\n",
                    "    lora_dropout=0,\\n",
                    "    bias='none',\\n",
                    "    use_gradient_checkpointing='unsloth',\\n",
                    "    random_state=42,\\n",
                    ")\\n",
                    "print('✅ Model & Adapters successfully initialized on Dual T4 GPUs!')"
                ]
            },
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": None,
                "outputs": [],
                "source": [
                    "# Step 3: Load Dataset\\n",
                    "from datasets import load_dataset\\n\\n",
                    "dataset = load_dataset('json', data_files='dataset.jsonl', split='train')\\n",
                    "alpaca_prompt = '''Below is an instruction that describes a task, paired with an input that provides further context. Write a response that appropriately completes the request.\\n\\n### Instruction:\\n{}\\n\\n### Input:\\n{}\\n\\n### Response:\\n{}'''\\n\\n",
                    "def format_prompts(examples):\\n",
                    "    instructions = examples['instruction']\\n",
                    "    inputs = examples['input']\\n",
                    "    outputs = examples['output']\\n",
                    "    texts = []\\n",
                    "    for inst, inp, out in zip(instructions, inputs, outputs):\\n",
                    "        text = alpaca_prompt.format(inst, inp, out) + tokenizer.eos_token\\n",
                    "        texts.append(text)\\n",
                    "    return {'text': texts}\\n\\n",
                    "dataset = dataset.map(format_prompts, batched=True)\\n",
                    "print(f'✅ Dataset formatted: {len(dataset)} samples ready!')"
                ]
            },
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": None,
                "outputs": [],
                "source": [
                    "# Step 4: SFT Training\\n",
                    "from trl import SFTTrainer\\n",
                    "from transformers import TrainingArguments\\n\\n",
                    "trainer = SFTTrainer(\\n",
                    "    model=model,\\n",
                    "    tokenizer=tokenizer,\\n",
                    "    train_dataset=dataset,\\n",
                    "    dataset_text_field='text',\\n",
                    "    max_seq_length=2048,\\n",
                    "    dataset_num_proc=2,\\n",
                    "    packing=False,\\n",
                    "    args=TrainingArguments(\\n",
                    "        per_device_train_batch_size=2,\\n",
                    "        gradient_accumulation_steps=4,\\n",
                    "        warmup_steps=5,\\n",
                    f"        num_train_epochs={epochs},\\n",
                    f"        learning_rate={lr},\\n",
                    "        fp16=not torch.cuda.is_bf16_supported(),\\n",
                    "        bf16=torch.cuda.is_bf16_supported(),\\n",
                    "        logging_steps=1,\\n",
                    "        optim='adamw_8bit',\\n",
                    "        output_dir='output',\\n",
                    "    ),\\n",
                    ")\\n",
                    "trainer.train()\\n",
                    "print('🎉 Cloud Training Finished!')"
                ]
            },
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": None,
                "outputs": [],
                "source": [
                    "# Step 5: Export GGUF for Ollama\\n",
                    f"model.save_pretrained_gguf('{clean_name}_gguf', tokenizer, quantization_method='q4_k_m')\\n",
                    "print('📦 GGUF Quantized Model successfully exported!')"
                ]
            }
        ]

        nb_data = {
            "cells": notebook_cells,
            "metadata": {
                "language_info": {
                    "name": "python",
                    "pygments_lexer": "ipython3"
                },
                "kernelspec": {
                    "name": "python3",
                    "display_name": "Python 3"
                },
                "accelerator": "GPU"
            },
            "nbformat": 4,
            "nbformat_minor": 2
        }

        nb_path = os.path.join(kernel_dir, "train_kernel.ipynb")
        with open(nb_path, "w", encoding="utf-8") as f:
            json.dump(nb_data, f, indent=2)

        meta_data = {
            "id": f"{username}/{slug}",
            "title": title,
            "code_file": "train_kernel.ipynb",
            "language": "python",
            "kernel_type": "notebook",
            "is_private": "true",
            "enable_gpu": "true",
            "enable_tpu": "false",
            "enable_internet": "true",
            "dataset_sources": [],
            "competition_sources": [],
            "kernel_sources": [],
            "model_sources": []
        }
        meta_path = os.path.join(kernel_dir, "kernel-metadata.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta_data, f, indent=2)

        import kaggle
        kaggle.api.authenticate()
        push_res = kaggle.api.kernels_push(kernel_dir)

        runs_cache_file = os.path.join(os.getcwd(), "cloud_packages", "kaggle_runs", "active_runs.json")
        os.makedirs(os.path.dirname(runs_cache_file), exist_ok=True)
        runs = {}
        if os.path.exists(runs_cache_file):
            try:
                with open(runs_cache_file, "r") as f:
                    runs = json.load(f)
            except Exception:
                pass

        kernel_slug = f"{username}/{slug}"
        runs[kernel_slug] = {
            "session_id": session_id,
            "model_name": clean_name,
            "domain_topic": domain_topic,
            "start_time": time.time(),
            "kernel_slug": kernel_slug,
            "slug": slug,
            "kernel_dir": kernel_dir,
            "status": "queued",
            "url": f"https://www.kaggle.com/code/{kernel_slug}"
        }
        with open(runs_cache_file, "w") as f:
            json.dump(runs, f, indent=2)

        return {
            "status": "queued",
            "kernel_slug": kernel_slug,
            "kernel_url": f"https://www.kaggle.com/code/{kernel_slug}",
            "model_name": clean_name,
            "message": f"Successfully launched Auto-Pilot training on Kaggle Dual T4 Cloud!"
        }

    @staticmethod
    def get_kernel_status(kernel_slug: str) -> Dict[str, Any]:
        """Queries live status of a running Kaggle kernel."""
        try:
            import kaggle
            kaggle.api.authenticate()
            resp = kaggle.api.kernels_status(kernel_slug)
            raw_status = getattr(resp, "status", None) or getattr(resp, "kernel_status", None) or str(resp)
            failure_message = getattr(resp, "failure_message", None)
            return {
                "status": "success",
                "kernel_slug": kernel_slug,
                "remote_status": str(raw_status).lower(),
                "failure_message": failure_message,
                "url": f"https://www.kaggle.com/code/{kernel_slug}"
            }
        except Exception as e:
            return {
                "status": "error",
                "kernel_slug": kernel_slug,
                "error": str(e)
            }

    @staticmethod
    def download_and_import_model(kernel_slug: str) -> Dict[str, Any]:
        """Downloads kernel output files and registers GGUF into Ollama."""
        runs_cache_file = os.path.join(os.getcwd(), "cloud_packages", "kaggle_runs", "active_runs.json")
        runs = {}
        if os.path.exists(runs_cache_file):
            try:
                with open(runs_cache_file, "r") as f:
                    runs = json.load(f)
            except Exception:
                pass

        run_info = runs.get(kernel_slug, {})
        model_name = run_info.get("model_name", "custom-llm")
        domain_topic = run_info.get("domain_topic", "specialized domain task")
        slug = run_info.get("slug", kernel_slug.split("/")[-1])
        output_dir = os.path.join(os.getcwd(), "cloud_packages", "kaggle_runs", slug, "output")
        os.makedirs(output_dir, exist_ok=True)

        import kaggle
        kaggle.api.authenticate()
        files, _ = kaggle.api.kernels_output(kernel_slug, path=output_dir)

        gguf_path = None
        for root, _, filenames in os.walk(output_dir):
            for fn in filenames:
                if fn.endswith(".gguf"):
                    gguf_path = os.path.join(root, fn)
                    break
            if gguf_path:
                break

        if not gguf_path:
            return {
                "status": "warning",
                "message": "Downloaded outputs, but no .gguf file was found yet.",
                "files": os.listdir(output_dir)
            }

        modelfile_content = f"""# Auto-imported from Kaggle Cloud Dual T4
FROM {gguf_path}

PARAMETER temperature 0.4
PARAMETER top_p 0.9
PARAMETER num_ctx 4096

SYSTEM \"\"\"You are a specialized expert model trained on {domain_topic}. Always answer user queries with deep precision, clarity, and authority.\"\"\"
"""
        modelfile_path = os.path.join(output_dir, "Modelfile")
        with open(modelfile_path, "w", encoding="utf-8") as f:
            f.write(modelfile_content)

        import subprocess
        res = subprocess.run(["ollama", "create", model_name, "-f", modelfile_path], capture_output=True, text=True)
        if res.returncode != 0:
            return {
                "status": "error",
                "message": f"Ollama import failed: {res.stderr or res.stdout}"
            }

        start_t = run_info.get("start_time", time.time() - 900)
        duration = max(300.0, time.time() - start_t)
        CloudQuotaManager.record_training_time("kaggle", duration)

        return {
            "status": "imported",
            "model_name": model_name,
            "message": f"Model '{model_name}' successfully fine-tuned on Kaggle Cloud and registered in Ollama & Chat Arena!"
        }
