"""
MiroFish Multi-Agent Persona Simulation Runner
Evaluates AI Studio / Foundry across diverse synthetic user personas.
"""

import os
import sys
import json
import asyncio
import urllib.request

PERSONAS = [
    {
        "id": "senior_ml_researcher",
        "name": "Dr. Aris Thorne",
        "role": "Senior ML / LLM Alignment Researcher",
        "bias": "Extreme focus on training rigor, DoRA decomposition math, evaluation holdouts, and avoiding benchmark leakage.",
        "tone": "Academic, rigorous, uncompromising."
    },
    {
        "id": "frontend_designer",
        "name": "Elena Vance",
        "role": "Principal Product Designer (Linear / Vercel style)",
        "bias": "Allergic to unnecessary text, pill chains, AI buzzwords, and visual clutter. Demands calm, ergonomic developer tools.",
        "tone": "Direct, aesthetic, UX-obsessed."
    },
    {
        "id": "security_architect",
        "name": "Marcus Kane",
        "role": "AppSec & Air-Gap Compliance Auditor",
        "bias": "Paranoid about untrusted Python code execution, Docker micro-VM container breakouts, and local data exfiltration.",
        "tone": "Skeptical, risk-averse, precise."
    },
    {
        "id": "indie_hacker",
        "name": "Leo Sato",
        "role": "Solo AI Builder & Open-Source Hacker",
        "bias": "Loves zero-cost local compute, RTX 3050 offline inference, hating OpenAI subscriptions, wants fast prototypes.",
        "tone": "Enthusiastic, scrappy, speed-oriented."
    },
    {
        "id": "junior_dev",
        "name": "Priya Patel",
        "role": "Junior Full-Stack Developer",
        "bias": "Needs clear intuitive feedback, gets overwhelmed by complex hyperparameters (r, alpha, LoRA), relies on suggestion chips.",
        "tone": "Honest, pragmatic, user-focused."
    },
    {
        "id": "mlops_engineer",
        "name": "Viktor Brandt",
        "role": "Staff MLOps Infrastructure Engineer",
        "bias": "Cares about VRAM limits (5.8GB RTX 3050), Ollama daemon lifecycle, Kaggle cloud API handoff, and artifact registries.",
        "tone": "Engineering-first, telemetry-driven, reliability-focused."
    },
    {
        "id": "ai_skeptic_lead",
        "name": "Clara Higgins",
        "role": "VP of Engineering & AI Skeptic",
        "bias": "Tired of toy AI demos. Asks: 'Does this actually produce weights that solve business problems or is it a wrapper?'",
        "tone": "Pragmatic, bottom-line focused, candid."
    }
]

APP_SEED = """
Product: AI STUDIO / FOUNDRY (Local AI Workstation & Laboratory)
Target Runtime: Local PC with NVIDIA RTX 3050 (6GB VRAM, 5.8GB allocatable) + Ollama Engine (11434).

Core Laboratories:
1. Train AI (Classical ML):
   - Natural language objective interpretation -> LightGBM / Ridge / RandomForest.
   - Built-in Automated Preprocessing: median/mode imputation, robust outlier clipping, standard scaling.
   - One-click suggestion chips (Customer Churn, Fraud Detection, Ticket Routing).
   - Autonomous row synthesis or custom CSV upload.
   - Execution Isolation: AST-secured local worker with memory limits and zero external socket access.
   - Live testing playground for inference & confidence score analysis.

2. Model Lab (Inspection & Surgery):
   - Scikit-learn .pkl registry and version lineage DAG viewer.
   - Targeted model surgery: modify classes, adjust thresholds, inject CSV knowledge with synthetic distribution gap fill.

3. LLM Fine-Tuning Studio:
   - Multi-source dataset harvesting (Hugging Face API, Kaggle, Synthetic).
   - Token curation sliders (min/max tokens, quality threshold, keyword filters).
   - Parameter adaptation: DoRA (Weight-Decomposed LoRA), QLoRA 4-bit NF4, GaLore.
   - Non-intrusive micro-tooltips (.info-hint '?') defining LoRA Rank (r), Alpha, DoRA vs QLoRA, and Epochs without UI clutter.
   - Catastrophic Forgetting Shield (15% general anchor replay + 20% holdout split).
   - Target Dispatch: Local GPU (RTX 3050) vs Kaggle Dual T4 (32GB) vs Colab.
   - Scientific A/B Benchmark Suite on holdouts.

4. Synthetic Dataset Studio:
   - Autonomous multi-model generation pipeline (Generator -> Validation & Repair -> Container Sandbox).
   - Hardened Docker micro-VM air-gap: strict '--network none' (zero socket/LAN/internet access), 256MB RAM cap, '--cap-drop ALL', non-root user, read-only rootfs, ephemeral teardown.
   - Fallback to Windows Job Object kernel jail with auto-kill on close.
   - Evol-Instruct constraint mutations and reasoning traces.
   - Compiled golden .jsonl corpora repository.

5. Decentralized AI Council Chamber:
   - Zero-Bias Consensus Protocol with independent drafting and double-blind peer review.
   - Explicit Consensus Rubric: Correctness (40%) · Security & AST (30%) · Runtime Efficiency (30%).
   - Docker Oracle Reality Gate with '--network none' air-gapped test assertion execution.

6. Local Chat Arena:
   - 100% offline air-gapped chat with local Ollama models (Llama 3, Dolphin 3, Mistral).
   - Multimodal image/screenshot inspection.
   - Persona toggles, temperature, context memory, and RAG retrieval.

Visual Style:
- Antigravity / Linear / Vercel dark theme (obsidian #0d0e11, zinc #141518, 1px subtle borders, clean SVG icons, no decorative emojis, micro-tooltips on hover).
"""

def call_ollama(prompt, model="dolphin3:latest"):
    url = "http://127.0.0.1:11434/api/generate"
    data = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.7, "num_predict": 400}
    }).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            res_data = json.loads(res.read().decode("utf-8"))
            return res_data.get("response", "").strip()
    except Exception as e:
        return f"[Simulation offline fallback for {model}: {e}]"

def run_persona_evaluation(persona):
    prompt = f"""You are {persona['name']}, {persona['role']}.
Your profile and bias: {persona['bias']}
Tone: {persona['tone']}

Here is the specification and design of the application 'AI Studio / Foundry':
{APP_SEED}

Perform your candid review of this application in your distinct persona voice.
Provide:
1. FIRST REACTION (1-2 punchy sentences in character)
2. WHAT STANDS OUT / PRAISE (2 key points from your perspective)
3. WHAT BOTHERS YOU / CRITICAL VULNERABILITIES (2 specific flaws or friction points)
4. YOUR VERDICT SCORE (1-10) and one required change before you would use this daily.

Keep your response punchy, sharp, and authentic to your role."""

    print(f"[*] Simulating persona: {persona['name']} ({persona['role']})...")
    return call_ollama(prompt)

def run_council_synthesis(persona_reviews):
    prompt = f"""You are the MiroFish Simulation Synthesis Engine.
You have collected independent evaluations from 7 diverse developer personas on 'AI Studio / Foundry':

{persona_reviews}

Synthesize these reactions into a structured MiroFish Consensus Report:
1. EXECUTIVE CONSENSUS (Overall market sentiment & average grade)
2. KEY TRIUMPHS (Features all personas agreed were top-tier)
3. CRITICAL FRICTION POINTS & TENSIONS (Where personas disagreed or raised flags)
4. HIGH-PRIORITY ACTION ITEMS (The top 3 engineering/design fixes recommended by the collective swarm)

Format cleanly in markdown with zero marketing filler."""

    print("[*] Running MiroFish Swarm Consensus Synthesis...")
    return call_ollama(prompt)

if __name__ == "__main__":
    print("=" * 60)
    print("MIROFISH MULTI-AGENT PERSONA SIMULATION")
    print("Simulating 7 Autonomous Developer Swarm Personas")
    print("=" * 60)

    reviews = {}
    reviews_text = ""
    for p in PERSONAS:
        rev = run_persona_evaluation(p)
        reviews[p['id']] = {
            "name": p['name'],
            "role": p['role'],
            "review": rev
        }
        reviews_text += f"\n--- {p['name']} ({p['role']}) ---\n{rev}\n"

    synthesis = run_council_synthesis(reviews_text)

    output_path = "mirofish_simulation_report.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"personas": reviews, "synthesis": synthesis}, f, indent=2)

    print("\n" + "=" * 60)
    print("SIMULATION COMPLETE. OUTPUT GENERATED.")
    print("=" * 60)
    print(synthesis)
