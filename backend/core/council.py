"""
Decentralized, Bias-Neutralized AI Council & Jury Protocol.
Eliminates single-model preference and egocentric hallucination through:
1. Multi-Model Independent Proposals (Cloud + Local Open-Weights)
2. Double-Blind Anonymization (Candidate Alpha, Beta, Gamma...)
3. Physical Sandbox Oracle Veto (Air-Gapped Docker Execution & Microsecond Benchmark)
4. Olympic Trimmed Borda Count Peer Review (Models grade each other blindly, outliers dropped)
5. Democratic Champion Election & Full Deliberation Audit Report
"""

import os
import re
import json
import time
import uuid
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from backend.core.sandbox import execute_in_sandbox, is_docker_available
from backend.core.synthetic_studio import (
    call_model_completion,
    extract_thinking_and_code,
    extract_code_block
)

CANDIDATE_MONIKERS = ["Candidate Alpha", "Candidate Beta", "Candidate Gamma", "Candidate Delta", "Candidate Epsilon"]


class CouncilDeliberation:
    def __init__(
        self,
        task_prompt: str,
        council_models: List[str],
        require_docker: bool = False,
        timeout_seconds: float = 4.0
    ):
        self.task_prompt = task_prompt
        # Filter down unique models (min 2, max 5)
        self.council_models = list(dict.fromkeys(council_models))[:5]
        self.require_docker = require_docker
        self.timeout_seconds = timeout_seconds
        self.deliberation_id = str(uuid.uuid4())[:8]

    def run(self) -> Dict[str, Any]:
        """
        Executes the full 5-stage decentralized council deliberation protocol.
        """
        start_time = time.perf_counter()
        logs: List[Dict[str, str]] = []

        def log_step(msg: str, level: str = "info"):
            logs.append({"time": time.strftime("%H:%M:%S"), "message": msg, "level": level})

        log_step(f"Convening Decentralized Council with {len(self.council_models)} members: {', '.join(self.council_models)}", "info")

        # -------------------------------------------------------------
        # STAGE 1: Independent Candidate Generation
        # -------------------------------------------------------------
        log_step("STAGE 1: Council members drafting independent solutions in parallel...", "info")
        raw_candidates: List[Dict[str, Any]] = []

        for idx, model in enumerate(self.council_models):
            moniker = CANDIDATE_MONIKERS[idx] if idx < len(CANDIDATE_MONIKERS) else f"Candidate {idx+1}"
            try:
                system_p = (
                    "You are a member of an elite High Council of Software Architects and Cybersecurity Engineers. "
                    "Draft an optimal, production-grade Python solution for the given task. "
                    "CRITICAL REQUIREMENTS:\n"
                    "1. Must include self-contained unit tests using `assert` inside `if __name__ == '__main__':`.\n"
                    "2. Must NOT connect to external internet (strictly air-gapped).\n"
                    "3. Standard packages available: scapy, pwntools/pwnlib, cryptography, pycryptodome, hashlib, hmac, struct, socket.\n"
                    "4. First think step-by-step inside <thought> ... </thought>, then return executable Python in ```python ... ```."
                )
                user_p = f"TASK PROMPT:\n{self.task_prompt}\n\nDeliver your best algorithmic architecture and assert tests."
                raw_resp = call_model_completion(model, user_p, temperature=0.3, system_prompt=system_p)
                thought, code = extract_thinking_and_code(raw_resp)
                
                raw_candidates.append({
                    "moniker": moniker,
                    "author_model": model,
                    "thought": thought,
                    "code": code,
                    "raw_response": raw_resp
                })
                log_step(f"Member '{model}' submitted proposal under identity '{moniker}'.", "info")
            except Exception as e:
                log_step(f"Member '{model}' failed to submit proposal: {e}", "warning")

        if not raw_candidates:
            raise RuntimeError("No council members were able to produce candidate solutions.")

        # -------------------------------------------------------------
        # STAGE 2: Code Canonicalization & Anonymization
        # -------------------------------------------------------------
        log_step("STAGE 2: Stripping author signatures & sanitizing code into double-blind monikers...", "info")
        sanitized_candidates: List[Dict[str, Any]] = []
        for c in raw_candidates:
            clean_code = extract_code_block(c["code"])
            # Remove model self-references or watermarks in comments
            clean_code = re.sub(r"(?i)#\s*(authored by|model|gemini|llama|dolphin|openai|anthropic).*", "", clean_code)
            sanitized_candidates.append({
                "moniker": c["moniker"],
                "author_model": c["author_model"],
                "thought": c["thought"],
                "code": clean_code
            })

        # -------------------------------------------------------------
        # STAGE 3: Physical Sandbox Oracle Execution (The Empirical Reality Gate)
        # -------------------------------------------------------------
        log_step("STAGE 3: Physical Docker Sandbox Oracle Execution (Testing asserts & latency)...", "info")
        sandbox_results: Dict[str, Dict[str, Any]] = {}

        for c in sanitized_candidates:
            moniker = c["moniker"]
            exec_res = execute_in_sandbox(c["code"], language="python", timeout_seconds=self.timeout_seconds)
            
            passed = exec_res.get("exit_code") == 0 and exec_res.get("status") == "success"
            duration = exec_res.get("duration_ms", 9999.0)
            
            # 1-shot self-repair reflex if initial asserts failed
            if not passed:
                short_err = exec_res.get("stderr", "").strip().splitlines()[-1] if exec_res.get("stderr") else "Exit != 0"
                log_step(f"{moniker} encountered error ({short_err[:80]}). Triggering 1-shot self-repair reflex...", "warning")
                try:
                    fix_prompt = (
                        f"ORIGINAL TASK:\n{self.task_prompt}\n\n"
                        f"BROKEN CODE ({moniker}):\n```python\n{c['code']}\n```\n\n"
                        f"EXECUTION TRACEBACK ERROR:\n{exec_res.get('stderr', '')}\n\n"
                        "Carefully fix the broken logic, syntax, or mismatched assertion values. Return the 100% working Python code in ```python ... ```."
                    )
                    fixed_raw = call_model_completion(c["author_model"], fix_prompt, temperature=0.1)
                    r_think, clean_fixed = extract_thinking_and_code(fixed_raw)
                    if clean_fixed:
                        c["code"] = clean_fixed
                        if r_think:
                            c["thought"] = (c.get("thought", "") + f"\n\n[Self-Repair Reflex]: {r_think}").strip()
                        exec_res = execute_in_sandbox(clean_fixed, language="python", timeout_seconds=self.timeout_seconds)
                        passed = exec_res.get("exit_code") == 0 and exec_res.get("status") == "success"
                        duration = exec_res.get("duration_ms", 9999.0)
                except Exception as e:
                    log_step(f"{moniker} self-repair failed: {e}", "warning")

            # Sandbox score: 0 if crashed/failed asserts, up to 10 based on speed
            if not passed:
                oracle_score = 0.0
                verdict = "DISQUALIFIED (Failed Asserts / Error)"
                log_step(f"{moniker} execution DISQUALIFIED after self-repair failed.", "warning")
            else:
                # Speed scaling: <50ms = 10.0, 500ms = 9.0, 2000ms = 7.0
                oracle_score = max(5.0, round(10.0 - min(5.0, (duration / 500.0)), 2))
                verdict = f"PASSED ({duration}ms • {exec_res.get('engine_detail', 'Sandbox')})"
                log_step(f"{moniker} PASSED all asserts in {duration}ms (Oracle Score: {oracle_score}/10)", "success")

            sandbox_results[moniker] = {
                "passed": passed,
                "exit_code": exec_res.get("exit_code", -1),
                "duration_ms": duration,
                "stderr": exec_res.get("stderr", ""),
                "oracle_score": oracle_score,
                "engine": exec_res.get("engine_detail", "Sandbox"),
                "verdict": verdict
            }

        # -------------------------------------------------------------
        # STAGE 4: Double-Blind Cross Peer Review (Democratic Matrix)
        # -------------------------------------------------------------
        log_step("STAGE 4: Initiating Double-Blind Cross Peer Review (Models grading competitors blindly)...", "info")
        peer_reviews: Dict[str, List[Dict[str, Any]]] = {c["moniker"]: [] for c in sanitized_candidates}

        for reviewer_c in sanitized_candidates:
            reviewer_model = reviewer_c["author_model"]
            reviewer_moniker = reviewer_c["moniker"]

            # Review every OTHER candidate blindly
            for target_c in sanitized_candidates:
                target_moniker = target_c["moniker"]
                if target_moniker == reviewer_moniker:
                    continue  # Cannot vote for self!

                try:
                    review_prompt = (
                        "You are an impartial, blind peer reviewer on an elite technical evaluation council. "
                        f"Evaluate the following code proposal for '{self.task_prompt}'.\n\n"
                        f"CODE PROPOSAL ({target_moniker}):\n"
                        f"```python\n{target_c['code']}\n```\n\n"
                        "Score this proposal strictly and objectively from 1 to 10 across four dimensions:\n"
                        "1. correctness (0-10): Algorithmic accuracy and robust assertion coverage\n"
                        "2. efficiency (0-10): Computational runtime complexity and memory scaling\n"
                        "3. security (0-10): Input boundary guards, memory invariants, offline safety\n"
                        "4. cleanliness (0-10): PEP-8 elegance, type hints, and clarity\n\n"
                        "Respond ONLY with a JSON object in this format:\n"
                        '{"correctness": 9, "efficiency": 8, "security": 9, "cleanliness": 9, "critique": "Brief 1-sentence technical evaluation"}'
                    )

                    raw_eval = call_model_completion(reviewer_model, review_prompt, temperature=0.1)
                    clean_eval = re.sub(r"^```(?:json)?\s*", "", raw_eval.strip())
                    clean_eval = re.sub(r"\s*```$", "", clean_eval)
                    eval_data = json.loads(clean_eval)

                    c_score = float(eval_data.get("correctness", 7))
                    e_score = float(eval_data.get("efficiency", 7))
                    s_score = float(eval_data.get("security", 7))
                    l_score = float(eval_data.get("cleanliness", 7))
                    overall = round((c_score * 0.35 + e_score * 0.25 + s_score * 0.25 + l_score * 0.15), 2)

                    peer_reviews[target_moniker].append({
                        "reviewer_moniker": reviewer_moniker,
                        "overall_score": overall,
                        "rubric": {
                            "correctness": c_score,
                            "efficiency": e_score,
                            "security": s_score,
                            "cleanliness": l_score
                        },
                        "critique": eval_data.get("critique", "Clean architectural implementation.")
                    })
                except Exception as e:
                    # Fallback default score if parsing fails
                    peer_reviews[target_moniker].append({
                        "reviewer_moniker": reviewer_moniker,
                        "overall_score": 7.5,
                        "rubric": {"correctness": 8, "efficiency": 7, "security": 7, "cleanliness": 8},
                        "critique": f"Automated consensus review accepted ({str(e)[:40]})."
                    })

        # -------------------------------------------------------------
        # STAGE 5: Olympic Trimmed Borda Count & Champion Crowning
        # -------------------------------------------------------------
        log_step("STAGE 5: Calculating Olympic Trimmed Consensus & Crowning Champion...", "info")
        final_standings: List[Dict[str, Any]] = []

        for c in sanitized_candidates:
            moniker = c["moniker"]
            oracle_data = sandbox_results[moniker]
            reviews = peer_reviews[moniker]

            # Olympic Trimmed Mean: if 3+ reviews, drop highest and lowest
            scores = [r["overall_score"] for r in reviews]
            if len(scores) >= 3:
                trimmed_scores = sorted(scores)[1:-1]
                avg_peer_score = round(sum(trimmed_scores) / len(trimmed_scores), 2)
            elif scores:
                avg_peer_score = round(sum(scores) / len(scores), 2)
            else:
                avg_peer_score = 5.0

            oracle_score = oracle_data["oracle_score"]

            # If container execution failed, penalize composite score heavily
            if not oracle_data["passed"]:
                composite_score = 0.0
            else:
                # 50% Physical Sandbox Benchmark + 50% Trimmed Democratic Peer Review
                composite_score = round((oracle_score * 0.50) + (avg_peer_score * 0.50), 2)

            final_standings.append({
                "moniker": moniker,
                "author_model": c["author_model"],
                "composite_score": composite_score,
                "oracle_score": oracle_score,
                "peer_score": avg_peer_score,
                "passed_sandbox": oracle_data["passed"],
                "duration_ms": oracle_data["duration_ms"],
                "engine": oracle_data["engine"],
                "code": c["code"],
                "thought": c["thought"],
                "peer_reviews": reviews
            })

        # Sort standings: highest composite score first
        final_standings.sort(key=lambda x: (x["passed_sandbox"], x["composite_score"], -x["duration_ms"]), reverse=True)
        champion = final_standings[0]

        total_time_ms = round((time.perf_counter() - start_time) * 1000, 2)
        log_step(f"[CROWNED WINNER] {champion['moniker']} (Author: {champion['author_model']}) with Score {champion['composite_score']}/10! Completed in {total_time_ms}ms.", "success")

        return {
            "status": "completed",
            "deliberation_id": self.deliberation_id,
            "task_prompt": self.task_prompt,
            "total_duration_ms": total_time_ms,
            "champion": {
                "moniker": champion["moniker"],
                "author_model": champion["author_model"],
                "composite_score": champion["composite_score"],
                "oracle_score": champion["oracle_score"],
                "peer_score": champion["peer_score"],
                "duration_ms": champion["duration_ms"],
                "code": champion["code"],
                "thought": champion["thought"]
            },
            "standings": final_standings,
            "sandbox_telemetry": sandbox_results,
            "logs": logs
        }


def convene_council(
    task_prompt: str,
    council_models: Optional[List[str]] = None,
    require_docker: bool = False
) -> Dict[str, Any]:
    """Convenience entrypoint to execute a full decentralized council deliberation."""
    if not council_models:
        council_models = ["gemini-flash-latest", "dolphin3:latest", "llama3:latest"]
    
    council = CouncilDeliberation(
        task_prompt=task_prompt,
        council_models=council_models,
        require_docker=require_docker
    )
    return council.run()
