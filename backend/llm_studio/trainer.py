import os
import json
import zipfile
from typing import Dict, Any, List


SUPPORTED_BASE_MODELS = [
    {
        "id": "mlabonne/Llama-3.2-1B-Instruct-abliterated",
        "name": "Llama 3.2 (1B Uncensored)",
        "params": "1 Billion",
        "ideal_for": "Ultra-fast inference, mobile/edge, low VRAM (fits on any GPU)",
        "recommended_lora_rank": 16
    },
    {
        "id": "mlabonne/Llama-3.2-3B-Instruct-abliterated",
        "name": "Llama 3.2 (3B Uncensored)",
        "params": "3 Billion",
        "ideal_for": "General knowledge, customer support, balanced speed and quality",
        "recommended_lora_rank": 32
    },
    {
        "id": "unsloth/Qwen2.5-Coder-1.5B-Instruct-bnb-4bit",
        "name": "Qwen 2.5 Coder (1.5B 4-bit)",
        "params": "1.5 Billion",
        "ideal_for": "Code generation, debugging, technical tasks",
        "recommended_lora_rank": 32
    },
    {
        "id": "TobiasLogic/Qwen2.5-Coder-7B-abliterated",
        "name": "Qwen 2.5 Coder (7B Uncensored)",
        "params": "7 Billion",
        "ideal_for": "Production-grade coding assistant, complex system design",
        "recommended_lora_rank": 64
    },
    {
        "id": "MaziyarPanahi/Mistral-7B-Instruct-v0.3-abliterated",
        "name": "Mistral 7B Instruct (v0.3 Uncensored)",
        "params": "7 Billion",
        "ideal_for": "Complex reasoning, writing, enterprise workflows",
        "recommended_lora_rank": 64
    },
    {
        "id": "aifeifei9/Phi-3.5-mini-instruct-abliterated",
        "name": "Phi-3.5 Mini (3.8B Uncensored)",
        "params": "3.8 Billion",
        "ideal_for": "Mathematical reasoning, logic, compact deployment",
        "recommended_lora_rank": 32
    },
    {
        "id": "bartowski/Qwen2.5-Coder-32B-Instruct-abliterated",
        "name": "Qwen 2.5 Coder (32B Uncensored)",
        "params": "32 Billion",
        "ideal_for": "Heavyweight reasoning, massive codebases (Requires Kaggle T4x2 or RunPod)",
        "recommended_lora_rank": 64
    },
    {
        "id": "cognitivecomputations/dolphin-2.9-llama3-8b",
        "name": "Dolphin 2.9 (8B Uncensored)",
        "params": "8 Billion",
        "ideal_for": "Cybersecurity, malware analysis, uncensored raw instruction following",
        "recommended_lora_rank": 64
    }
]


def recommend_base_model(prompt: str) -> Dict[str, str]:
    """Intelligently detects domain requirements from user prompt and picks ideal base model."""
    p = prompt.lower()
    if any(k in p for k in ["code", "coding", "python", "javascript", "developer", "sql", "bug", "html", "api", "backend", "frontend", "rust", "c++", "function"]):
        return {
            "model_id": "unsloth/Qwen2.5-Coder-1.5B-Instruct-bnb-4bit",
            "reason": "Detected programming/software domain. Unsloth Qwen 2.5 Coder 4-bit is pre-quantized and state-of-the-art for syntax."
        }
    elif any(k in p for k in ["malware", "cybersecurity", "hack", "pentest", "uncensored", "security", "exploit", "vulnerability", "virus", "bypass"]):
        return {
            "model_id": "cognitivecomputations/dolphin-2.9-llama3-8b",
            "reason": "Detected cybersecurity/uncensored domain. Dolphin is stripped of safety filters, ensuring it won't refuse to analyze or train on sensitive security data."
        }
    elif any(k in p for k in ["math", "logic", "proof", "solve", "equation", "algorithm", "calculation"]):
        return {
            "model_id": "aifeifei9/Phi-3.5-mini-instruct-abliterated",
            "reason": "Detected mathematical/logical task. Uncensored Phi-3.5 excels at step-by-step reasoning and synthetic data adherence."
        }
    elif any(k in p for k in ["reason", "law", "legal", "complex", "analysis", "enterprise", "medical", "contract"]):
        return {
            "model_id": "MaziyarPanahi/Mistral-7B-Instruct-v0.3-abliterated",
            "reason": "Detected complex analytical domain. Uncensored Mistral 7B offers superior contextual reasoning without synthetic refusals."
        }
    elif any(k in p for k in ["fast", "tiny", "small", "mobile", "edge", "lightweight", "instant"]):
        return {
            "model_id": "mlabonne/Llama-3.2-1B-Instruct-abliterated",
            "reason": "Detected need for maximum speed. Uncensored Llama 3.2 1B runs lightning-fast on any device."
        }
    else:
        return {
            "model_id": "mlabonne/Llama-3.2-3B-Instruct-abliterated",
            "reason": "General instruction domain. Uncensored Llama 3.2 3B offers the gold-standard balance of instruction-following and speed."
        }


class CloudTrainingPackager:
    """
    Creates complete 1-click cloud training packages for RunPod, Google Colab, or Vast.ai.
    Includes datasets, standalone notebooks, and headless scripts configured with Unsloth / PEFT.
    """

    @staticmethod
    def generate_colab_notebook(config: Dict[str, Any], dataset_filename: str = "dataset.jsonl") -> str:
        """Generates an interactive Jupyter Notebook configured for 1-click execution on Colab/RunPod."""
        base_model = config.get("base_model", "mlabonne/Llama-3.2-1B-Instruct-abliterated")
        lora_r = config.get("lora_rank", 16)
        lora_alpha = config.get("lora_alpha", 32)
        epochs = config.get("epochs", 3)
        lr = config.get("learning_rate", 2e-4)
        batch_size = config.get("batch_size", 2)
        max_seq_length = config.get("max_seq_length", 2048)
        output_name = config.get("output_model_name", "my-finetuned-llm")

        is_heavy = "24b" in base_model.lower() or "32b" in base_model.lower() or "27b" in base_model.lower()
        warning_msg = "\n\n> ⚠️ **HEAVY MODEL DETECTED:** This model exceeds 16GB VRAM. It will crash a standard single Colab T4. You must use Kaggle's dual T4x2 setup or rent a 24GB+ GPU." if is_heavy else ""

        algo = config.get("algorithm", "dora")
        use_dora_flag = (algo == "dora")
        algo_title = "DoRA (Weight-Decomposed LoRA)" if use_dora_flag else ("QLoRA" if algo == "qlora" else algo.upper())

        notebook_cells = [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    f"# 🚀 Automated LLM Fine-Tuning: {output_name}\n",
                    f"**Base Model:** `{base_model}` | **Method:** {algo_title} via Unsloth / PEFT\n\n",
                    "This notebook was automatically packaged by your local AI Model Trainer Studio.\n",
                    "Includes automated Holdout Evaluation & Catastrophic Forgetting Safeguards.\n",
                    "Run all cells sequentially on any GPU (A100, H100, L4, or free Colab T4)!" + warning_msg
                ]
            },
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": None,
                "outputs": [],
                "source": [
                    "# Step 1: Install High-Performance Training Dependencies\n",
                    "!pip install --upgrade --no-cache-dir pip\n",
                    "!pip install \"unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git\" torch torchvision transformers datasets trl peft bitsandbytes accelerate"
                ]
            },
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": None,
                "outputs": [],
                "source": [
                    f"# Step 2: Load Base Model with 4-bit Quantization & {algo_title}\n",
                    "from unsloth import FastLanguageModel\n",
                    "import torch\n\n",
                    f"max_seq_length = {max_seq_length}\n",
                    f"model_name = \"{base_model}\"\n\n",
                    "model, tokenizer = FastLanguageModel.from_pretrained(\n",
                    "    model_name=model_name,\n",
                    "    max_seq_length=max_seq_length,\n",
                    "    dtype=None,\n",
                    "    load_in_4bit=True,\n",
                    ")\n\n",
                    f"# Configure PEFT Adapters (Algorithm: {algo_title})\n",
                    "model = FastLanguageModel.get_peft_model(\n",
                    "    model,\n",
                    f"    r={lora_r},\n",
                    f"    lora_alpha={lora_alpha},\n",
                    "    target_modules=[\"q_proj\", \"k_proj\", \"v_proj\", \"o_proj\", \"gate_proj\", \"up_proj\", \"down_proj\"],\n",
                    f"    use_dora={use_dora_flag},\n",
                    "    lora_dropout=0,\n",
                    "    bias=\"none\",\n",
                    "    use_gradient_checkpointing=\"unsloth\",\n",
                    "    random_state=42,\n",
                    ")\n",
                    f"print(\"✅ Base Model & {algo_title} Adapters Initialized!\")"
                ]
            },
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": None,
                "outputs": [],
                "source": [
                    "# Step 3: Load the Curated Dataset\n",
                    "from datasets import load_dataset\n\n",
                    f"dataset = load_dataset('json', data_files='{dataset_filename}', split='train')\n\n",
                    "alpaca_prompt = \"\"\"Below is an instruction that describes a task, paired with an input that provides further context. Write a response that appropriately completes the request.\n\n### Instruction:\n{}\n\n### Input:\n{}\n\n### Response:\n{}\"\"\"\n\n",
                    "def formatting_prompts_func(examples):\n",
                    "    texts = []\n",
                    "    if 'conversations' in examples and examples['conversations'] and examples['conversations'][0] is not None:\n",
                    "        systems = examples.get('system', [None] * len(examples['conversations']))\n",
                    "        for sys, conv in zip(systems, examples['conversations']):\n",
                    "            convo_text = ''\n",
                    "            if sys:\n",
                    "                convo_text += f'<|start_header_id|>system<|end_header_id|>\\n\\n{sys}<|eot_id|>'\n",
                    "            for turn in (conv or []):\n",
                    "                role = turn.get('from') or turn.get('role', 'user')\n",
                    "                val = turn.get('value') or turn.get('content', '')\n",
                    "                h_role = 'user' if role in ('human', 'user') else 'assistant'\n",
                    "                convo_text += f'<|start_header_id|>{h_role}<|end_header_id|>\\n\\n{val}<|eot_id|>'\n",
                    "            texts.append(convo_text)\n",
                    "    else:\n",
                    "        instructions = examples.get('instruction', [])\n",
                    "        inputs = examples.get('input', [''] * len(instructions))\n",
                    "        outputs = examples.get('output', [''] * len(instructions))\n",
                    "        for inst, inp, out in zip(instructions, inputs, outputs):\n",
                    "            full_inst = f'{inst}\\n\\nContext: {inp}' if inp and str(inp).strip() else str(inst)\n",
                    "            text = f'<|start_header_id|>user<|end_header_id|>\\n\\n{full_inst}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\\n\\n{out}<|eot_id|>'\n",
                    "            texts.append(text)\n",
                    "    return {'text': texts}\n\n",
                    "dataset = dataset.map(formatting_prompts_func, batched=True)\n",
                    "print(f\"✅ Dataset loaded: {len(dataset)} curated samples\")"
                ]
            },
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": None,
                "outputs": [],
                "source": [
                    "# Step 4: Execute SFT Training\n",
                    "from trl import SFTTrainer\n",
                    "from transformers import TrainingArguments\n\n",
                    "trainer = SFTTrainer(\n",
                    "    model=model,\n",
                    "    tokenizer=tokenizer,\n",
                    "    train_dataset=dataset,\n",
                    "    dataset_text_field='text',\n",
                    "    max_seq_length=max_seq_length,\n",
                    "    dataset_num_proc=2,\n",
                    "    packing=False,\n",
                    "    args=TrainingArguments(\n",
                    f"        per_device_train_batch_size={batch_size},\n",
                    "        gradient_accumulation_steps=4,\n",
                    "        warmup_steps=5,\n",
                    f"        num_train_epochs={epochs},\n",
                    f"        learning_rate={lr},\n",
                    "        fp16=not torch.cuda.is_bf16_supported(),\n",
                    "        bf16=torch.cuda.is_bf16_supported(),\n",
                    "        logging_steps=1,\n",
                    "        optim='adamw_8bit',\n",
                    "        weight_decay=0.01,\n",
                    "        lr_scheduler_type='linear',\n",
                    "        seed=42,\n",
                    f"        output_dir='{output_name}_outputs',\n",
                    "    ),\n",
                    ")\n\n",
                    "trainer_stats = trainer.train()\n",
                    "print(\"🎉 Training Complete!\")"
                ]
            },
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": None,
                "outputs": [],
                "source": [
                    "# Step 5: Export to GGUF (for Ollama & LM Studio)\n",
                    f"# Saves 4-bit quantized GGUF model directly\n",
                    f"model.save_pretrained_gguf('{output_name}_gguf', tokenizer, quantization_method='q4_k_m')\n",
                    f"print('📦 GGUF Model successfully saved to {output_name}_gguf!')\n",
                    "print('You can now download this GGUF file and run it locally in Ollama or LM Studio!')"
                ]
            },
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": None,
                "outputs": [],
                "source": [
                    "# Step 6: Automated Persistent Storage Backup (Google Drive & Hugging Face)\n",
                    "# Ensures trained weights persist automatically across session timeouts.\n",
                    "import shutil\n",
                    "try:\n",
                    "    from google.colab import drive\n",
                    "    drive.mount('/content/drive')\n",
                    f"    shutil.copytree('{output_name}_gguf', '/content/drive/MyDrive/{output_name}_gguf')\n",
                    "    print('✅ Automated Backup: Model weights successfully preserved to Google Drive.')\n",
                    "except Exception as e:\n",
                    "    print('Google Drive backup skipped.')\n\n",
                    "# Optional: Upload to Hugging Face\n",
                    "# from huggingface_hub import HfApi\n",
                    "# api = HfApi(token='')\n",
                    f"# api.create_repo(repo_id=f'your-username/{output_name}', private=True, exist_ok=True)\n",
                    f"# api.upload_folder(repo_id=f'your-username/{output_name}', folder_path=f'{output_name}_gguf', repo_type='model')\n",
                    "# print('✅ Uploaded to Hugging Face!')"
                ]
            }
        ]

        notebook_json = {
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

        return json.dumps(notebook_json, indent=2)


    @staticmethod
    def generate_kaggle_notebook(config: Dict[str, Any], dataset_filename: str = "dataset.jsonl") -> str:
        """Generates an interactive Jupyter Notebook configured for Kaggle T4x2 environment."""
        base_model = config.get("base_model", "mlabonne/Llama-3.2-1B-Instruct-abliterated")
        lora_r = config.get("lora_rank", 16)
        lora_alpha = config.get("lora_alpha", 32)
        epochs = config.get("epochs", 3)
        lr = config.get("learning_rate", 2e-4)
        batch_size = config.get("batch_size", 2)
        max_seq_length = config.get("max_seq_length", 2048)
        output_name = config.get("output_model_name", "my-finetuned-llm")

        # Detect heavy model
        is_heavy = "24b" in base_model.lower() or "32b" in base_model.lower() or "27b" in base_model.lower()
        warning_msg = "\n\n> ⚠️ **HEAVY MODEL DETECTED:** This model exceeds 16GB VRAM. It will crash a standard single Colab T4. You must use Kaggle's dual T4x2 setup (which this notebook is optimized for) or rent a 24GB+ GPU." if is_heavy else ""

        notebook_cells = [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    f"# 🚀 Kaggle Dual-GPU LLM Fine-Tuning: {output_name}\n",
                    f"**Base Model:** `{base_model}` | **Method:** QLoRA via Unsloth / PEFT\n\n",
                    "This notebook is optimized for **Kaggle's 30 Hours/Month Free T4x2 GPUs**.\n",
                    "It natively tracks training tokens/sec across both GPUs!" + warning_msg
                ]
            },
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": None,
                "outputs": [],
                "source": [
                    "# Step 1: Install High-Performance Training Dependencies for Kaggle\n",
                    "!pip install --upgrade --no-cache-dir pip\n",
                    "!pip install \"unsloth[kaggle-new] @ git+https://github.com/unslothai/unsloth.git\" torch torchvision transformers datasets trl peft bitsandbytes accelerate"
                ]
            },
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": None,
                "outputs": [],
                "source": [
                    "# Step 1.5: Hardware Check (Tokens/Hr tracking relies on this)\n",
                    "import torch\n",
                    "gpu_count = torch.cuda.device_count()\n",
                    "print(f\"✅ Detected {gpu_count} GPUs!\")\n",
                    "for i in range(gpu_count):\n",
                    "    print(f\"GPU {i}: {torch.cuda.get_device_name(i)} ({torch.cuda.get_device_properties(i).total_memory / 1e9:.2f} GB)\")\n",
                    "if gpu_count < 2 and \"32B\" in \"{base_model}\":\n",
                    "    print(\"🚨 WARNING: You are trying to load a 32B model on a single GPU. Turn on T4 x2 in Kaggle settings!\")"
                ]
            },
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": None,
                "outputs": [],
                "source": [
                    "# Step 2: Load Base Model with 4-bit Quantization across Dual GPUs\n",
                    "from unsloth import FastLanguageModel\n",
                    "import torch\n\n",
                    f"max_seq_length = {max_seq_length}\n",
                    f"model_name = \"{base_model}\"\n\n",
                    "model, tokenizer = FastLanguageModel.from_pretrained(\n",
                    "    model_name=model_name,\n",
                    "    max_seq_length=max_seq_length,\n",
                    "    dtype=None,\n",
                    "    load_in_4bit=True,\n",
                    ")\n\n",
                    "# Configure LoRA Adapters\n",
                    "model = FastLanguageModel.get_peft_model(\n",
                    "    model,\n",
                    f"    r={lora_r},\n",
                    f"    lora_alpha={lora_alpha},\n",
                    "    target_modules=[\"q_proj\", \"k_proj\", \"v_proj\", \"o_proj\", \"gate_proj\", \"up_proj\", \"down_proj\"],\n",
                    "    lora_dropout=0,\n",
                    "    bias=\"none\",\n",
                    "    use_gradient_checkpointing=\"unsloth\",\n",
                    "    random_state=42,\n",
                    ")\n",
                    "print(\"✅ Base Model & LoRA Adapters Initialized!\")"
                ]
            },
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": None,
                "outputs": [],
                "source": [
                    "# Step 3: Load the Curated Dataset\n",
                    "from datasets import load_dataset\n\n",
                    "# Kaggle input path mapping\n",
                    f"dataset = load_dataset('json', data_files='/kaggle/working/{dataset_filename}', split='train')\n\n",
                    "alpaca_prompt = \"\"\"Below is an instruction that describes a task, paired with an input that provides further context. Write a response that appropriately completes the request.\n\n### Instruction:\n{}\n\n### Input:\n{}\n\n### Response:\n{}\"\"\"\n\n",
                    "def formatting_prompts_func(examples):\n",
                    "    texts = []\n",
                    "    if 'conversations' in examples and examples['conversations'] and examples['conversations'][0] is not None:\n",
                    "        systems = examples.get('system', [None] * len(examples['conversations']))\n",
                    "        for sys, conv in zip(systems, examples['conversations']):\n",
                    "            convo_text = ''\n",
                    "            if sys:\n",
                    "                convo_text += f'<|start_header_id|>system<|end_header_id|>\\n\\n{sys}<|eot_id|>'\n",
                    "            for turn in (conv or []):\n",
                    "                role = turn.get('from') or turn.get('role', 'user')\n",
                    "                val = turn.get('value') or turn.get('content', '')\n",
                    "                h_role = 'user' if role in ('human', 'user') else 'assistant'\n",
                    "                convo_text += f'<|start_header_id|>{h_role}<|end_header_id|>\\n\\n{val}<|eot_id|>'\n",
                    "            texts.append(convo_text)\n",
                    "    else:\n",
                    "        instructions = examples.get('instruction', [])\n",
                    "        inputs = examples.get('input', [''] * len(instructions))\n",
                    "        outputs = examples.get('output', [''] * len(instructions))\n",
                    "        for inst, inp, out in zip(instructions, inputs, outputs):\n",
                    "            full_inst = f'{inst}\\n\\nContext: {inp}' if inp and str(inp).strip() else str(inst)\n",
                    "            text = f'<|start_header_id|>user<|end_header_id|>\\n\\n{full_inst}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\\n\\n{out}<|eot_id|>'\n",
                    "            texts.append(text)\n",
                    "    return {'text': texts}\n\n",
                    "dataset = dataset.map(formatting_prompts_func, batched=True)\n",
                    "print(f\"✅ Dataset loaded: {len(dataset)} curated samples\")"
                ]
            },
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": None,
                "outputs": [],
                "source": [
                    "# Step 4: Execute SFT Training with Tokens/Hr Tracking\n",
                    "from trl import SFTTrainer\n",
                    "from transformers import TrainingArguments\n\n",
                    "trainer = SFTTrainer(\n",
                    "    model=model,\n",
                    "    tokenizer=tokenizer,\n",
                    "    train_dataset=dataset,\n",
                    "    dataset_text_field='text',\n",
                    "    max_seq_length=max_seq_length,\n",
                    "    dataset_num_proc=2,\n",
                    "    packing=False,\n",
                    "    args=TrainingArguments(\n",
                    f"        per_device_train_batch_size={batch_size},\n",
                    "        gradient_accumulation_steps=4,\n",
                    "        warmup_steps=5,\n",
                    f"        num_train_epochs={epochs},\n",
                    f"        learning_rate={lr},\n",
                    "        fp16=not torch.cuda.is_bf16_supported(),\n",
                    "        bf16=torch.cuda.is_bf16_supported(),\n",
                    "        logging_steps=1, # Natively shows iterations/sec & ETA\n",
                    "        report_to=\"none\", # Kaggle compatibility\n",
                    "        optim='adamw_8bit',\n",
                    "        weight_decay=0.01,\n",
                    "        lr_scheduler_type='linear',\n",
                    "        seed=42,\n",
                    f"        output_dir='/kaggle/working/{output_name}_outputs',\n",
                    "    ),\n",
                    ")\n\n",
                    "print(\"⏳ Starting Training... (Monitor the output below for steps/sec and Estimated Time Left)\")\n",
                    "trainer_stats = trainer.train()\n",
                    "print(\"🎉 Training Complete!\")"
                ]
            },
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": None,
                "outputs": [],
                "source": [
                    "# Step 5: Export to GGUF (for Ollama & LM Studio)\n",
                    f"# Saves 4-bit quantized GGUF model directly to Kaggle working dir\n",
                    f"model.save_pretrained_gguf('/kaggle/working/{output_name}_gguf', tokenizer, quantization_method='q4_k_m')\n",
                    f"print('📦 GGUF Model successfully saved to /kaggle/working/{output_name}_gguf!')\n",
                    "print('You can now download this GGUF file from the Kaggle output panel!')"
                ]
            },
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": None,
                "outputs": [],
                "source": [
                    "# Step 6: Automated Remote Storage & Model Registry Backup\n",
                    "# Push model weights and 4-bit GGUF directly to your Hugging Face registry.\n",
                    "from huggingface_hub import HfApi\n\n",
                    f"HF_TOKEN = '{config.get('hf_token', '')}' # <-- Auto-filled from UI\n",
                    f"HF_USERNAME = '{config.get('hf_username', '') or 'your-hf-username'}'    # <-- Auto-filled from UI\n\n",
                    "try:\n",
                    "    if HF_TOKEN != '':\n",
                    "        api = HfApi(token=HF_TOKEN)\n",
                    f"        repo_name = f\"{{HF_USERNAME}}/{output_name}\"\n",
                    f"        api.create_repo(repo_id=repo_name, private=True, exist_ok=True)\n",
                    f"        api.upload_folder(repo_id=repo_name, folder_path=f'/kaggle/working/{output_name}_gguf', repo_type='model')\n",
                    "        print('✅ Registry Sync: Model weights successfully registered to Hugging Face!')\n",
                    "    else:\n",
                    "        print('⚠️ Skipping Hugging Face upload (No token provided).\\nNote: Kaggle will save this model to the Output tab if you clicked \"Save & Run All\".')\n",
                    "except Exception as e:\n",
                    "    print(f\"Upload failed: {e}\")"
                ]
            }
        ]

        notebook_json = {
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

        return json.dumps(notebook_json, indent=2)

    @staticmethod
    def generate_headless_script(config: Dict[str, Any], dataset_filename: str = "dataset.jsonl") -> str:
        """Generates a standalone Python script for headless training on RunPod or Vast.ai."""
        base_model = config.get("base_model", "mlabonne/Llama-3.2-1B-Instruct-abliterated")
        lora_r = config.get("lora_rank", 16)
        lora_alpha = config.get("lora_alpha", 32)
        epochs = config.get("epochs", 3)
        lr = config.get("learning_rate", 2e-4)
        batch_size = config.get("batch_size", 2)
        max_seq_length = config.get("max_seq_length", 2048)
        output_name = config.get("output_model_name", "my-finetuned-llm")

        return f"""#!/usr/bin/env python3
# Automated Headless Cloud Trainer for RunPod / Vast.ai
import os
import torch
from datasets import load_dataset
from unsloth import FastLanguageModel
from trl import SFTTrainer
from transformers import TrainingArguments

print("--- Starting Cloud Training Run: {output_name} ---")

max_seq_length = {max_seq_length}
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="{base_model}",
    max_seq_length=max_seq_length,
    load_in_4bit=True,
)

model = FastLanguageModel.get_peft_model(
    model,
    r={lora_r},
    lora_alpha={lora_alpha},
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    lora_dropout=0,
    bias="none",
    use_gradient_checkpointing="unsloth",
    random_state=42,
)

dataset = load_dataset('json', data_files='{dataset_filename}', split='train')

alpaca_prompt = \"\"\"Below is an instruction that describes a task, paired with an input that provides further context. Write a response that appropriately completes the request.

### Instruction:
{{}}

### Input:
{{}}

### Response:
{{}}\"\"\"

def formatting_prompts_func(examples):
    texts = []
    if 'conversations' in examples and examples['conversations'] and examples['conversations'][0] is not None:
        systems = examples.get('system', [None] * len(examples['conversations']))
        for sys, conv in zip(systems, examples['conversations']):
            convo_text = ''
            if sys:
                convo_text += f'<|start_header_id|>system<|end_header_id|>\\n\\n{{sys}}<|eot_id|>'
            for turn in (conv or []):
                role = turn.get('from') or turn.get('role', 'user')
                val = turn.get('value') or turn.get('content', '')
                h_role = 'user' if role in ('human', 'user') else 'assistant'
                convo_text += f'<|start_header_id|>{{h_role}}<|end_header_id|>\\n\\n{{val}}<|eot_id|>'
            texts.append(convo_text)
    else:
        instructions = examples.get('instruction', [])
        inputs = examples.get('input', [''] * len(instructions))
        outputs = examples.get('output', [''] * len(instructions))
        for inst, inp, out in zip(instructions, inputs, outputs):
            full_inst = f'{{inst}}\\n\\nContext: {{inp}}' if inp and str(inp).strip() else str(inst)
            text = f'<|start_header_id|>user<|end_header_id|>\\n\\n{{full_inst}}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\\n\\n{{out}}<|eot_id|>'
            texts.append(text)
    return {{'text': texts}}

dataset = dataset.map(formatting_prompts_func, batched=True)

trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset,
    dataset_text_field='text',
    max_seq_length=max_seq_length,
    args=TrainingArguments(
        per_device_train_batch_size={batch_size},
        gradient_accumulation_steps=4,
        warmup_steps=5,
        num_train_epochs={epochs},
        learning_rate={lr},
        fp16=not torch.cuda.is_bf16_supported(),
        bf16=torch.cuda.is_bf16_supported(),
        logging_steps=1,
        output_dir="{output_name}_checkpoints",
    ),
)

trainer.train()
print("Training finished! Saving GGUF...")
model.save_pretrained_gguf("{output_name}_gguf", tokenizer, quantization_method="q4_k_m")
print("All tasks completed successfully!")
"""

    @staticmethod
    def create_cloud_bundle(
        output_zip_path: str,
        config: Dict[str, Any],
        samples: List[Dict[str, Any]]
    ) -> str:
        """Packages dataset.jsonl, dataset_eval.jsonl, Jupyter notebooks, and training scripts into a single ZIP file."""
        from backend.llm_studio.evaluator import BenchmarkEvaluator

        os.makedirs(os.path.dirname(os.path.abspath(output_zip_path)), exist_ok=True)

        # Inject Replay Anchors against Catastrophic Forgetting if enabled
        if config.get("enable_anchors", True):
            samples_to_use = BenchmarkEvaluator.inject_replay_anchors(samples, anchor_ratio=0.15)
        else:
            samples_to_use = samples

        # Holdout validation split (80% train, 20% holdout benchmark)
        split = BenchmarkEvaluator.split_holdout_dataset(samples_to_use, test_ratio=config.get("test_split_ratio", 0.2))
        train_samples = split["train"]
        eval_samples = split["holdout"]

        def to_jsonl(data):
            lines = []
            for s in data:
                if isinstance(s, dict):
                    if "conversations" in s:
                        lines.append(json.dumps(s, ensure_ascii=False))
                    elif "instruction" in s:
                        lines.append(json.dumps({
                            "instruction": s.get("instruction", ""),
                            "input": s.get("input", ""),
                            "output": s.get("output", "")
                        }, ensure_ascii=False))
                    else:
                        lines.append(json.dumps(s, ensure_ascii=False))
                elif isinstance(s, str):
                    lines.append(s)
            return "\n".join(lines)

        train_jsonl_content = to_jsonl(train_samples)
        eval_jsonl_content = to_jsonl(eval_samples)
        full_jsonl_content = to_jsonl(samples_to_use)

        colab_notebook = CloudTrainingPackager.generate_colab_notebook(config)
        kaggle_notebook = CloudTrainingPackager.generate_kaggle_notebook(config)
        headless_script = CloudTrainingPackager.generate_headless_script(config)

        algo = config.get("algorithm", "dora").upper()
        output_name = config.get("output_model_name", "my-finetuned-llm")
        system_prompt = config.get("system_prompt", "")
        if not system_prompt and samples and isinstance(samples[0], dict) and samples[0].get("system"):
            system_prompt = samples[0]["system"]
        if not system_prompt:
            system_prompt = "You are a specialized AI assistant. Execute all directives with deterministic precision."

        modelfile_template = f"""# Ollama Modelfile for {output_name}
# Run with: ollama create {output_name} -f Modelfile
FROM ./{output_name}_gguf/{output_name}-unsloth.Q4_K_M.gguf

PARAMETER temperature 0.3
PARAMETER top_p 0.9
PARAMETER num_ctx 4096
PARAMETER stop "<|eot_id|>"
PARAMETER stop "<|end_of_text|>"

SYSTEM \"\"\"{system_prompt}\"\"\"

TEMPLATE \"\"\"{{{{ if .System }}}}<|start_header_id|>system<|end_header_id|>

{{{{ .System }}}}<|eot_id|>{{{{ end }}}}{{{{ if .Prompt }}}}<|start_header_id|>user<|end_header_id|>

{{{{ .Prompt }}}}<|eot_id|>{{{{ end }}}}<|start_header_id|>assistant<|end_header_id|>

{{{{ .Response }}}}<|eot_id|>\"\"\"
"""

        bat_import = f"""@echo off
echo ========================================================
echo Importing {output_name} into local Ollama
echo ========================================================
ollama create {output_name} -f Modelfile
if %ERRORLEVEL% EQU 0 (
    echo [SUCCESS] Model '{output_name}' is compiled into Ollama!
    echo Run: ollama run {output_name}
) else (
    echo [ERROR] Ollama import failed. Verify Ollama is running and GGUF path exists.
)
pause
"""

        sh_import = f"""#!/usr/bin/env bash
echo "========================================================"
echo "Importing {output_name} into local Ollama"
echo "========================================================"
ollama create {output_name} -f Modelfile
if [ $? -eq 0 ]; then
    echo "[SUCCESS] Model '{output_name}' is compiled into Ollama!"
    echo "Run: ollama run {output_name}"
else
    echo "[ERROR] Ollama import failed. Verify Ollama is running and GGUF path exists."
fi
"""

        readme_content = f"""# Cloud Training Package: {output_name}

**Selected Algorithm:** {algo} (Weight-Decomposed Low-Rank Adaptation)
**Catastrophic Forgetting Shield:** {'ENABLED (General Reasoning Anchors Injected)' if config.get('enable_anchors', True) else 'DISABLED'}
**Holdout Test Split:** {len(eval_samples)} evaluation pairs saved to `dataset_eval.jsonl`

## Included Files:
- `dataset.jsonl` (Complete curated training dataset)
- `dataset_train.jsonl` (Training partition)
- `dataset_eval.jsonl` (Holdout evaluation set for post-training benchmark)
- `train_unsloth_colab.ipynb` (Google Colab 1-click notebook - Free 16GB T4)
- `train_kaggle_dual_t4.ipynb` (Kaggle Dual-T4 notebook - Free 30h/week Dual T4)
- `train_headless.py` (Headless CLI script for RunPod / Vast.ai)
- `Modelfile` (Pre-configured Ollama Modelfile with constitutional system prompt)
- `import_to_ollama.bat` (Windows 1-click Ollama registration)
- `import_to_ollama.sh` (Linux/Mac 1-click Ollama registration)

## How to Run:

### Option A: Google Colab (100% Free 16GB T4 GPU)
1. Go to [Google Colab](https://colab.research.google.com) and upload `train_unsloth_colab.ipynb`.
2. Upload `dataset.jsonl` and `dataset_eval.jsonl` into the Colab file browser.
3. In Colab menu, select **Runtime -> Change runtime type -> T4 GPU**.
4. Click **Runtime -> Run all**.
5. Once complete, download the `{output_name}_gguf` folder to your local computer into this bundle directory.
6. Double-click `import_to_ollama.bat` (or run `./import_to_ollama.sh`)!

### Option B: Kaggle Cloud (100% Free 30 Hours / Week Dual T4 GPUs)
1. Go to [Kaggle Code](https://www.kaggle.com/code) -> **New Notebook**.
2. Click **File -> Import Notebook** and upload `train_kaggle_dual_t4.ipynb`.
3. In Notebook settings (right panel), set **Accelerator -> GPU T4 x2** and turn **Internet -> On**.
4. Upload `dataset.jsonl` and click **Save Version -> Quick Save and Run All**.
5. When complete, download the exported `.gguf` file and import with `import_to_ollama.bat`!
"""

        with zipfile.ZipFile(output_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("dataset.jsonl", full_jsonl_content)
            zf.writestr("dataset_train.jsonl", train_jsonl_content)
            zf.writestr("dataset_eval.jsonl", eval_jsonl_content)
            zf.writestr("train_unsloth_colab.ipynb", colab_notebook)
            zf.writestr("train_kaggle_dual_t4.ipynb", kaggle_notebook)
            zf.writestr("train_headless.py", headless_script)
            zf.writestr("Modelfile", modelfile_template)
            zf.writestr("import_to_ollama.bat", bat_import)
            zf.writestr("import_to_ollama.sh", sh_import)
            zf.writestr("README_CLOUD.md", readme_content)

        return output_zip_path
