import re
import json
import hashlib
from typing import List, Dict, Any, Tuple


class DataCurator:
    """
    Data Curation & Filtering Suite:
    Provides length filtering, exact and fuzzy deduplication,
    quality scoring, keyword search, and dataset transformations.
    """

    @staticmethod
    def filter_dataset(
        samples: List[Dict[str, Any]],
        min_tokens: int = 10,
        max_tokens: int = 2048,
        min_quality: float = 0.70,
        deduplicate: bool = True,
        keyword_filter: str = "",
        exclude_keyword: str = ""
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Applies filtering rules across samples and returns the filtered list with metrics.
        """
        original_count = len(samples)
        filtered = []
        seen_hashes = set()
        seen_instructions = set()

        kw_clean = keyword_filter.strip().lower()
        ex_clean = exclude_keyword.strip().lower()

        for s in samples:
            tokens = s.get("token_count", 0)
            quality = s.get("quality_score", 0.0)
            inst = s.get("instruction", "").strip()
            out = s.get("output", "").strip()
            inp = s.get("input", "").strip()
            full_text = f"{inst} {inp} {out}".lower()

            # 1. Token length check
            if tokens < min_tokens or tokens > max_tokens:
                continue

            # 2. Quality score threshold
            if quality < min_quality:
                continue

            # 3. Keyword filtering
            if kw_clean and kw_clean not in full_text:
                continue
            if ex_clean and ex_clean in full_text:
                continue

            # 4. Deduplication
            if deduplicate:
                # Content hash deduplication
                content_hash = hashlib.sha256(full_text.encode("utf-8")).hexdigest()
                if content_hash in seen_hashes:
                    continue
                seen_hashes.add(content_hash)

                # Normalized instruction deduplication
                norm_inst = re.sub(r"\W+", "", inst.lower())
                if norm_inst in seen_instructions:
                    continue
                seen_instructions.add(norm_inst)

            filtered.append(s)

        stats = {
            "initial_samples": original_count,
            "retained_samples": len(filtered),
            "removed_samples": original_count - len(filtered),
            "retention_rate": round((len(filtered) / max(1, original_count)) * 100, 1),
            "avg_tokens": round(sum(s.get("token_count", 0) for s in filtered) / max(1, len(filtered)), 1) if filtered else 0,
            "sources": list(set(s.get("source", "Unknown") for s in filtered))
        }

        return filtered, stats

    @staticmethod
    def export_to_jsonl(samples: List[Dict[str, Any]], file_path: str) -> str:
        """Exports curated samples to standard JSONL format for LLM fine-tuning."""
        with open(file_path, "w", encoding="utf-8") as f:
            for s in samples:
                record = {
                    "instruction": s.get("instruction", ""),
                    "input": s.get("input", ""),
                    "output": s.get("output", "")
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return file_path

    @staticmethod
    def export_to_sharegpt(samples: List[Dict[str, Any]], file_path: str) -> str:
        """Exports curated samples to ShareGPT conversation format."""
        formatted = []
        for s in samples:
            conversations = [
                {"from": "human", "value": f"{s.get('instruction', '')}\n{s.get('input', '')}".strip()},
                {"from": "gpt", "value": s.get("output", "")}
            ]
            formatted.append({"conversations": conversations})

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(formatted, f, indent=2, ensure_ascii=False)
        return file_path
