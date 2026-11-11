"""
Live execution test of Groq (Cloud Metered) complex game build.
Tests:
- Dynamic CLOUD_METERED detection
- Lean prompt injection (< 300 words)
- 3s Rate Pacing between turns
- Real-time generation of index.html, styles.css, app.js
- Dual Acceptance Gate verification
"""

import sys
import time
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from backend.core.agent_engine import run_agentic_react_loop
from backend.core.agent_tools import get_project_dir
from backend.core.workspace_validator import validate_workspace

def run_groq_live_build():
    prompt = (
        "Build a complete Cyberpunk Neon Canvas Arcade Game in index.html, styles.css, app.js "
        "with a Start button, canvas player jumping over neon obstacles, live score display, "
        "and Web Audio retro jump sound."
    )
    proj_name = "live_groq_cyberpunk_game"
    
    print("\n" + "="*70)
    print("STARTING LIVE COMPLEX BUILD ON GROQ (CLOUD METERED TIER)")
    print(f"Target: {proj_name}")
    print("="*70)

    t0 = time.time()
    res = run_agentic_react_loop(
        model="cloud:groq:qwen/qwen3.8-27b",
        user_prompt=prompt,
        project_name=proj_name,
        max_steps=6
    )
    elapsed = round(time.time() - t0, 2)

    print("\n" + "="*70)
    print(f"GROQ LIVE BUILD COMPLETED IN {elapsed} SECONDS")
    print("="*70)
    print("Status:", res.get("status"))
    print("Files created:", res.get("created_files"))
    print("Steps count:", len(res.get("steps", [])))
    print("Compute Tier recorded:", res.get("compute_tier", {}).get("tier"))
    print("Telemetry:", res.get("telemetry"))

    for idx, s in enumerate(res.get("steps", [])):
        print(f"  Step {idx+1}: action='{s.get('action')}', status='{s.get('status')}', observation='{str(s.get('observation'))[:60]}'")

    # Run Acceptance Gate on the generated project
    print("\n--- RUNNING DUAL ACCEPTANCE GATE ON GROQ OUTPUT ---")
    gate_res = validate_workspace(proj_name)
    print("Gate Valid:", gate_res.get("valid"))
    print("Gate Summary:\n", gate_res.get("summary"))

if __name__ == "__main__":
    run_groq_live_build()
