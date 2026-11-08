from typing import Dict, Any, Optional


class SmartSituationAdvisor:
    """
    Intelligent recommendation engine that analyzes task prompt, model parameter scale,
    dataset volume, and available local/cloud hardware to dynamically prescribe optimal
    configurations and highlight recommended options across all settings.
    """

    @staticmethod
    def analyze_situation(
        prompt: str = "",
        sample_count: int = 40,
        selected_model: Optional[str] = None
    ) -> Dict[str, Any]:
        p = (prompt or "").lower().strip()

        # 1. Domain Detection
        if any(k in p for k in ["code", "coding", "python", "javascript", "developer", "sql", "bug", "html", "api", "backend", "frontend", "rust", "c++", "function", "script", "git", "linux", "terminal"]):
            domain_id = "coding"
            domain_label = "💻 Software Engineering & Code Syntax"
            recommended_base_model = "Qwen/Qwen2.5-Coder-1.5B-Instruct"
            ollama_base = "qwen2.5-coder:1.5b"
            model_aliases = ["huihui-ai/Qwen2.5-Coder-1.5B-Instruct-abliterated", "qwen2.5-coder:1.5b", "Qwen/Qwen2.5-Coder-1.5B-Instruct", "qwen", "coder"]
            model_reason = "Qwen 2.5 Coder is the state-of-the-art open-weights architecture for indentation, AST parsing, and programming languages."
            rec_temp = 0.2
            temp_reason = "Low temperature (0.2) eliminates hallucinations and enforces strict syntax correctness."
            rec_rank = 32
            rec_alpha = 64
            rank_reason = "Rank 32 provides high expressivity for nested control flows and data structures."
            suggested_name = "code-expert-assistant"
            rec_persona = "coder"

        elif any(k in p for k in ["malware", "cybersecurity", "hack", "pentest", "uncensored", "security", "exploit", "vulnerability", "virus", "bypass", "payload", "cve", "injection", "reverse", "audit"]):
            domain_id = "cybersecurity"
            domain_label = "🛡️ Cybersecurity & Exploit Analysis"
            recommended_base_model = "cognitivecomputations/dolphin-2.9-llama3-8b"
            ollama_base = "dolphin3:latest"
            model_aliases = ["cognitivecomputations/dolphin-2.9-llama3-8b", "dolphin3:latest", "dolphin", "dolphin-2.9"]
            model_reason = "Dolphin 3 (8B) is stripped of artificial alignment filters, ensuring it analyzes sensitive exploit payloads without refusal."
            rec_temp = 0.4
            temp_reason = "Moderate-low temperature (0.4) balances factual disassembly analysis with creative attack vector mitigation."
            rec_rank = 64
            rec_alpha = 128
            rank_reason = "Rank 64 captures complex assembly heuristics and multi-stage payload analysis."
            suggested_name = "cyber-exploit-analyst"
            rec_persona = "cyber"

        elif any(k in p for k in ["math", "logic", "proof", "solve", "equation", "algorithm", "calculation", "calculus", "algebra", "theorem"]):
            domain_id = "math_logic"
            domain_label = "🔬 Mathematical Logic & Formal Reasoning"
            recommended_base_model = "microsoft/Phi-3.5-mini-instruct"
            ollama_base = "phi3.5:latest"
            model_aliases = ["microsoft/Phi-3.5-mini-instruct", "aifeifei9/Phi-3.5-mini-instruct-abliterated", "phi3.5:latest", "phi-3.5", "phi"]
            model_reason = "Phi-3.5 Mini (3.8B) has the highest concentration of synthetic textbook and formal mathematical reasoning data."
            rec_temp = 0.1
            temp_reason = "Near-zero temperature (0.1) prevents arithmetic drift and enforces step-by-step chain-of-thought proofs."
            rec_rank = 32
            rec_alpha = 64
            rank_reason = "Rank 32 ensures precise step-by-step logical transformation."
            suggested_name = "math-logic-reasoner"
            rec_persona = "custom"

        elif any(k in p for k in ["law", "legal", "complex", "analysis", "enterprise", "medical", "contract", "compliance", "finance", "clinical", "patient"]):
            domain_id = "enterprise_legal"
            domain_label = "⚖️ Deep Analytical & Enterprise Reasoning"
            recommended_base_model = "mistralai/Mistral-7B-Instruct-v0.3"
            ollama_base = "mistral:latest"
            model_aliases = ["mistralai/Mistral-7B-Instruct-v0.3", "MaziyarPanahi/Mistral-7B-Instruct-v0.3-abliterated", "mistral:latest", "mistral", "mistral-7b"]
            model_reason = "Mistral 7B v0.3 excels at long-context comprehension, document extraction, and nuanced policy analysis."
            rec_temp = 0.3
            temp_reason = "Low temperature (0.3) ensures high factual fidelity to legal and technical source documents."
            rec_rank = 64
            rec_alpha = 128
            rank_reason = "Rank 64 captures intricate domain terminologies and regulatory taxonomies."
            suggested_name = "legal-policy-analyst"
            rec_persona = "custom"

        elif any(k in p for k in ["fast", "tiny", "small", "mobile", "edge", "lightweight", "instant", "quick", "low latency"]):
            domain_id = "ultra_fast"
            domain_label = "⚡ Ultra-Fast Low-Latency Assistant"
            recommended_base_model = "meta-llama/Llama-3.2-1B-Instruct"
            ollama_base = "llama3.2:1b"
            model_aliases = ["meta-llama/Llama-3.2-1B-Instruct", "mlabonne/Llama-3.2-1B-Instruct-abliterated", "llama3.2:1b", "llama-3.2-1b"]
            model_reason = "Llama 3.2 1B fits entirely into minimal VRAM and produces instantaneous token streams (>60 tok/sec)."
            rec_temp = 0.6
            temp_reason = "Temperature 0.6 balances fast conversational fluency with coherence."
            rec_rank = 16
            rec_alpha = 32
            rank_reason = "Rank 16 maintains minimal parameter overhead for fast adaptation."
            suggested_name = "fast-assistant-1b"
            rec_persona = "uncensored"

        else:
            domain_id = "general"
            domain_label = "🧠 General Knowledge & Instruction Following"
            recommended_base_model = "meta-llama/Llama-3.2-3B-Instruct"
            ollama_base = "llama3.2:3b"
            model_aliases = ["meta-llama/Llama-3.2-3B-Instruct", "mlabonne/Llama-3.2-3B-Instruct-abliterated", "llama3.2:3b", "llama-3.2-3b"]
            model_reason = "Llama 3.2 3B is the current gold standard sweet spot between 8B intelligence and 1B speed."
            rec_temp = 0.7
            temp_reason = "Temperature 0.7 provides natural, creative, and engaging conversational responses."
            rec_rank = 16
            rec_alpha = 32
            rank_reason = "Rank 16 is optimal for general instruction fine-tuning."
            suggested_name = "expert-assistant"
            rec_persona = "uncensored"

        # 2. Model Scale Hardware Recommendations
        active_model = selected_model or recommended_base_model
        model_str = active_model.lower()

        is_large_model = any(k in model_str for k in ["7b", "8b", "14b", "32b", "dolphin", "mistral"])
        is_medium_model = any(k in model_str for k in ["3b", "3.8b", "phi"])
        is_small_model = any(k in model_str for k in ["1b", "1.5b"])

        # If micro-dataset (<= 5 samples), always recommend Local RTX 3050 for rapid prototyping
        if sample_count <= 5:
            recommended_platform = "local"
            platform_title = "Local RTX 3050 (Instant Prototype • Zero Quota)"
            platform_reason = f"With only {sample_count} sample{'s' if sample_count > 1 else ''}, local execution on your RTX 3050 completes in seconds with zero cloud queue."
            platform_warning = None
            rec_batch_size = 1
            rec_grad_accum = 1
        elif is_large_model:
            recommended_platform = "kaggle"
            platform_title = "Kaggle Cloud (Dual T4 • 32 GB VRAM • 30h Free)"
            platform_reason = (
                "7B–8B models require 24GB+ VRAM during DoRA gradient backpropagation on multi-sample batches. "
                "Google Colab (15GB) will throw an Out-Of-Memory (OOM) crash! "
                "Kaggle's Dual-T4 32GB GPUs are strongly recommended."
            )
            platform_warning = "Google Colab will crash with Out-Of-Memory (OOM) on 8B models. Use Kaggle or Local 1-Click."
            rec_batch_size = 1
            rec_grad_accum = 8
        elif is_medium_model:
            recommended_platform = "colab"
            platform_title = "Google Colab or Kaggle (16 GB - 32 GB VRAM)"
            platform_reason = "3B–4B models fit comfortably within Colab's 16GB T4 VRAM or Kaggle's Dual T4s."
            platform_warning = None
            rec_batch_size = 2
            rec_grad_accum = 4
        else:
            recommended_platform = "local"
            platform_title = "Local RTX 3050 (1-Click • 2 Seconds • Zero Quota)"
            platform_reason = "1B–1.5B models can be compiled and served directly on your local GPU without burning any cloud quota!"
            platform_warning = None
            rec_batch_size = 2
            rec_grad_accum = 4

        # 3. Epochs & Learning Rate depending on sample count
        if sample_count <= 2:
            rec_epochs = 1
            epoch_reason = f"Micro-dataset ({sample_count} sample): 1 epoch prevents immediate single-sample memorization and overfitting."
            rec_lr = "0.0001"
        elif sample_count <= 40:
            rec_epochs = 4
            epoch_reason = "Small dataset (≤40 samples) requires 4 epochs for the model to deeply memorize expert patterns."
            rec_lr = "0.0002"
        elif sample_count <= 150:
            rec_epochs = 3
            epoch_reason = "Balanced dataset size: 3 epochs provides ideal convergence without overfitting."
            rec_lr = "0.0002"
        else:
            rec_epochs = 2
            epoch_reason = "Large dataset (>150 samples): 2 epochs prevents catastrophic loss of general reasoning."
            rec_lr = "0.0001"

        # 4. Algorithm Recommendation
        rec_algo = "dora"
        algo_reason = "DoRA (Weight-Decomposed LoRA) is state-of-the-art; it learns directional weight vectors independently from magnitude, consistently outperforming standard QLoRA."

        return {
            "domain": {
                "id": domain_id,
                "label": domain_label,
            },
            "recommendations": {
                "base_model": {
                    "value": recommended_base_model,
                    "ollama_tag": ollama_base,
                    "aliases": model_aliases,
                    "reason": model_reason
                },
                "suggested_name": suggested_name,
                "persona": rec_persona,
                "platform": {
                    "value": recommended_platform,
                    "title": platform_title,
                    "reason": platform_reason,
                    "warning": platform_warning
                },
                "algorithm": {
                    "value": rec_algo,
                    "reason": algo_reason
                },
                "lora_rank": {
                    "value": rec_rank,
                    "reason": rank_reason
                },
                "lora_alpha": {
                    "value": rec_alpha,
                    "reason": f"Standard scaling rule: Alpha = {rec_alpha} (2x Rank) ensures stable gradient scaling."
                },
                "epochs": {
                    "value": rec_epochs,
                    "reason": epoch_reason
                },
                "learning_rate": {
                    "value": rec_lr,
                    "reason": f"Optimal AdamW-8bit learning rate for {rec_algo.upper()} on {domain_id} domain."
                },
                "temperature": {
                    "value": rec_temp,
                    "reason": temp_reason
                },
                "catastrophic_shield": {
                    "value": True,
                    "reason": "Always keep shield enabled to protect core logic and reasoning from degradation."
                }
            },
            "summary_sentence": (
                f"For {domain_label}, we recommend {recommended_base_model.split('/')[-1]} "
                f"with DoRA Rank {rec_rank} & Temperature {rec_temp} running on {platform_title}."
            )
        }
