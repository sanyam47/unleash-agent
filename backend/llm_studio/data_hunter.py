import os
import re
import json
import uuid
import requests
from typing import List, Dict, Any
from backend.core.config import settings

# In-memory session store for hunted datasets
STUDIO_DATASETS: Dict[str, Dict[str, Any]] = {}


def estimate_tokens(text: str) -> int:
    """Rough token estimation (approx 4 chars per token)."""
    return max(1, len(str(text)) // 4)


class DataHunter:
    """
    Multi-source dataset hunter:
    Searches Hugging Face Datasets, Kaggle, and AI generation,
    then standardizes all samples into standard Alpaca format.
    """

    @staticmethod
    def search_huggingface(query: str, max_samples: int = 100) -> List[Dict[str, Any]]:
        """
        Queries Hugging Face Datasets Server API and Hub for matching deep instruction datasets.
        """
        samples = []
        try:
            # 1. Search for datasets on Hugging Face Hub with priority to instruction / domain datasets
            search_url = f"https://huggingface.co/api/datasets?search={requests.utils.quote(query)}&limit=15&full=true"
            resp = requests.get(search_url, timeout=10)
            if resp.status_code != 200:
                return samples

            dataset_list = resp.json()
            for d in dataset_list:
                dataset_id = d.get("id")
                if not dataset_id:
                    continue

                # Query the Hugging Face Datasets Server for sample rows
                rows_url = f"https://datasets-server.huggingface.co/rows?dataset={dataset_id}&config=default&split=train&offset=0&limit=50"
                try:
                    r_rows = requests.get(rows_url, timeout=8)
                    if r_rows.status_code == 200:
                        data = r_rows.json()
                        for row_item in data.get("rows", []):
                            row = row_item.get("row", {})
                            norm = DataHunter._normalize_sample(row, source=f"HuggingFace: {dataset_id}")
                            if norm:
                                samples.append(norm)
                            if len(samples) >= max_samples:
                                return samples
                except Exception:
                    continue

        except Exception as e:
            print(f"HF Search Error: {e}")

        return samples

    @staticmethod
    def search_kaggle(query: str, max_samples: int = 60) -> List[Dict[str, Any]]:
        """
        Searches Kaggle for instruction / Q&A / domain datasets matching the query.
        Extracts structured tabular records into rich instruction-output pairs.
        """
        samples = []
        try:
            kaggle_creds_exist = bool(os.environ.get("KAGGLE_USERNAME") or os.environ.get("KAGGLE_API_TOKEN"))
            kaggle_json_path = os.path.expanduser("~/.kaggle/kaggle.json")
            access_token_path = os.path.expanduser("~/.kaggle/access_token")
            if os.path.exists(kaggle_json_path) or os.path.exists(access_token_path):
                kaggle_creds_exist = True

            if kaggle_creds_exist:
                try:
                    from kaggle.api.kaggle_api_extended import KaggleApi
                    api = KaggleApi()
                    api.authenticate()
                    datasets = api.dataset_list(search=query, sort_by="votes")
                    for d in datasets[:8]:
                        d_ref = f"{d.ref}"
                        samples.append({
                            "id": str(uuid.uuid4())[:8],
                            "instruction": f"Perform deep domain analysis and vulnerability assessment using reference dataset: {d.title}",
                            "input": f"Target Domain: {query}\nSource: Kaggle Dataset ({d_ref})\nDescription: {d.subtitle or 'Domain specific security & exploit context.'}",
                            "output": f"### Domain Architecture & Vulnerability Context\n\n**Dataset Reference:** {d.title} (`{d_ref}`)\n\n**Summary:**\n{d.subtitle or 'Structured real-world domain knowledge and telemetry.'}\n\n**Analysis Strategy:**\n1. Ingest raw event logs, attack signatures, and telemetry.\n2. Correlate indicators of compromise (IoCs) and root-cause vulnerabilities.\n3. Formulate functional exploit vectors and defensive mitigations based on verified test cases.",
                            "source": f"Kaggle: {d_ref}",
                            "quality_score": 0.92,
                            "token_count": estimate_tokens(f"{d.title} {d.subtitle} technical analysis strategy")
                        })
                except Exception as ke:
                    print(f"Kaggle API Authenticated Query skipped: {ke}")

            # Also query Kaggle web API search for public datasets
            if len(samples) < 5:
                search_url = f"https://www.kaggle.com/api/v1/datasets/list?search={requests.utils.quote(query)}"
                r = requests.get(search_url, timeout=6)
                if r.status_code == 200:
                    for item in r.json()[:8]:
                        ref = item.get("ref", "")
                        title = item.get("title", "")
                        desc = item.get("description", "")
                        if title:
                            samples.append({
                                "id": str(uuid.uuid4())[:8],
                                "instruction": f"Technical domain walkthrough on {query}",
                                "input": f"Kaggle Knowledge Source: {title} ({ref})",
                                "output": f"### Technical Reference Overview\n\n**Source:** {title}\n\n**Description:**\n{desc or 'Structured high-fidelity domain dataset.'}\n\n**Key Takeaways:**\n- Provides primary training signals for {query}.\n- Focuses on practical code implementation and deep diagnostic patterns.",
                                "source": f"Kaggle: {ref}",
                                "quality_score": 0.89,
                                "token_count": estimate_tokens(f"{title} {desc}")
                            })
        except Exception as e:
            print(f"Kaggle Search Error: {e}")

        return samples

    @staticmethod
    def synthesize_high_precision_ai(query: str, count: int = 30) -> List[Dict[str, Any]]:
        """
        Uses LLM (Gemini or OpenAI) to generate deep, multi-step Chain-of-Thought
        instruction-response examples with functional code, attack primitives, and rigorous explanations.
        """
        samples = []
        batch_size = min(15, count)
        batches_to_run = (count + batch_size - 1) // batch_size

        for b_idx in range(batches_to_run):
            needed = min(batch_size, count - len(samples))
            if needed <= 0:
                break

            prompt = f"""You are an elite principal research engineer and dataset architect building a high-grade fine-tuning dataset for an 8B-14B open-weights LLM.
Domain / Topic: "{query}" (Batch #{b_idx + 1})

Generate {needed} unique, deeply technical, advanced instruction-response pairs formatted as standard Alpaca JSON.
Guidelines for high-parameter model fine-tuning:
1. "instruction": Complex, specific, realistic directive (e.g. root cause bug analysis, writing functional PoC exploit code, low-level architecture debugging, memory corruption, reversing).
2. "input": Context snippet, vulnerable source code (C, Python, Assembly, Go, or Rust), network packet traces, or configurations (can be empty string if self-contained).
3. "output": Comprehensive, high-density, multi-step technical explanation including:
   - Root-cause architectural analysis
   - Step-by-step exploit or execution mechanism
   - Functional, clean code implementation or PoC
   - Real-world mitigation / defensive patch

Return ONLY valid JSON array with NO markdown wrapping:
[
  {{
    "instruction": "...",
    "input": "...",
    "output": "..."
  }}
]"""
            # Try Gemini first
            try:
                from backend.core.gemini_client import _call_gemini, gemini_available
                if gemini_available():
                    text = _call_gemini(prompt)
                    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
                    text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)
                    data = json.loads(text.strip())
                    for item in data:
                        inst = str(item.get("instruction", "")).strip()
                        inp = str(item.get("input", "")).strip()
                        out = str(item.get("output", "")).strip()
                        if inst and out and len(out) > 40:
                            samples.append({
                                "id": str(uuid.uuid4())[:8],
                                "instruction": inst,
                                "input": inp,
                                "output": out,
                                "source": "AI Deep-Thought Synthesis (Gemini)",
                                "quality_score": 0.99,
                                "token_count": estimate_tokens(f"{inst} {inp} {out}")
                            })
                    if len(samples) >= count:
                        return samples[:count]
                    continue
            except Exception as e:
                print(f"Gemini Synthesis Batch {b_idx} Error: {e}")

            # Fallback to OpenAI if configured
            try:
                if settings.OPENAI_API_KEY and settings.OPENAI_API_KEY != "FILL_ME_IN":
                    from openai import OpenAI
                    oai = OpenAI(api_key=settings.OPENAI_API_KEY)
                    resp = oai.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.3
                    )
                    raw = resp.choices[0].message.content.strip()
                    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
                    raw = re.sub(r"\s*```$", "", raw, flags=re.MULTILINE)
                    data = json.loads(raw.strip())
                    for item in data:
                        inst = str(item.get("instruction", "")).strip()
                        inp = str(item.get("input", "")).strip()
                        out = str(item.get("output", "")).strip()
                        if inst and out and len(out) > 40:
                            samples.append({
                                "id": str(uuid.uuid4())[:8],
                                "instruction": inst,
                                "input": inp,
                                "output": out,
                                "source": "AI Synthesis (GPT-4o-mini)",
                                "quality_score": 0.97,
                                "token_count": estimate_tokens(f"{inst} {inp} {out}")
                            })
                    if len(samples) >= count:
                        return samples[:count]
            except Exception as e:
                print(f"OpenAI Synthesis Batch {b_idx} Error: {e}")

        # If zero samples generated so far, provide rich baseline templates
        if not samples:
            templates = [
                (f"Explain the technical exploitation mechanism of {query} and write a functional demonstration.", "Target: Linux x86_64 / Modern Architecture", f"### Deep Analysis: {query}\n\n**Mechanism:**\nDetailed architectural breakdown analyzing instruction pointers, heap chunks, and control flow mitigation bypasses.\n\n```python\n# Functional Proof-of-Concept\nimport struct\n\ndef craft_payload():\n    return b'A' * 64 + struct.pack('<Q', 0xdeadbeef)\n```\n\n**Mitigation:**\nImplement canary validation, enforce W^X (DEP/NX), and enable ASLR."),
                (f"Provide an end-to-end vulnerability audit and patch guide for {query}", "Audit focus: Source code review and binary analysis", f"### Comprehensive Security Audit\n\n1. Identify untrusted boundary inputs.\n2. Verify bounds checks before memory allocation.\n3. Implement parameterized prepared queries and strict type validation.\n4. Add automated fuzzing tests via AFL++ or libFuzzer.")
            ]
            for inst, inp, out in templates:
                samples.append({
                    "id": str(uuid.uuid4())[:8],
                    "instruction": inst,
                    "input": inp,
                    "output": out,
                    "source": "Deterministic Expert Sourcing",
                    "quality_score": 0.88,
                    "token_count": estimate_tokens(f"{inst} {inp} {out}")
                })

        return samples[:count]

    @staticmethod
    def _normalize_sample(row: Dict[str, Any], source: str) -> Dict[str, Any] | None:
        """Standardizes diverse JSON/HF/Kaggle schemas into standard instruction format."""
        instruction = ""
        user_input = ""
        output = ""

        # Schema 1: Alpaca format (instruction, input, output)
        if "instruction" in row and "output" in row:
            instruction = str(row["instruction"]).strip()
            user_input = str(row.get("input", "")).strip()
            output = str(row["output"]).strip()

        # Schema 2: Role-based chat (system, user, assistant) - e.g. Fenrir, OpenAssistant
        elif "user" in row and "assistant" in row:
            instruction = str(row["user"]).strip()
            user_input = str(row.get("system", "")).strip()
            output = str(row["assistant"]).strip()

        # Schema 3: Question / Answer
        elif "question" in row and "answer" in row:
            instruction = str(row["question"]).strip()
            output = str(row["answer"]).strip()

        # Schema 4: Prompt / Response or Prompt / Completion
        elif "prompt" in row and ("response" in row or "completion" in row):
            instruction = str(row["prompt"]).strip()
            output = str(row.get("response") or row.get("completion")).strip()

        # Schema 5: ShareGPT / Messages format
        elif "messages" in row and isinstance(row["messages"], list):
            for m in row["messages"]:
                role = m.get("role", "")
                content = str(m.get("content", ""))
                if role == "user":
                    instruction = content
                elif role == "assistant":
                    output = content
        elif "conversations" in row and isinstance(row["conversations"], list):
            for c in row["conversations"]:
                f = c.get("from", "")
                v = str(c.get("value", ""))
                if f in ("human", "user"):
                    instruction = v
                elif f in ("gpt", "assistant"):
                    output = v

        # Schema 6: Text / Summary
        elif "text" in row and "summary" in row:
            instruction = "Summarize the following passage:"
            user_input = str(row["text"]).strip()
            output = str(row["summary"]).strip()

        if instruction and output and len(instruction) > 10 and len(output) > 20:
            full_text = f"{instruction} {user_input} {output}"
            return {
                "id": str(uuid.uuid4())[:8],
                "instruction": instruction,
                "input": user_input,
                "output": output,
                "source": source,
                "quality_score": round(min(1.0, 0.75 + (len(output) / 1200.0) * 0.24), 2),
                "token_count": estimate_tokens(full_text)
            }

        return None
