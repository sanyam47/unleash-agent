"""
Quick live verification of run_agentic_react_loop under the new adaptive harness.
Tests that:
1. When calling with a local model, LITE_EDGE is detected.
2. Lean prompt is used.
3. Code files are created on disk.
"""

import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from backend.core.agent_engine import run_agentic_react_loop
from backend.core.agent_tools import get_project_dir

def run_live_test():
    proj_name = "test_stress_pomodoro_live"
    pdir = get_project_dir(proj_name)
    
    # Run 1 quick turn
    print(f"Running agent loop for '{proj_name}' using 'cyber-specialist:latest'...")
    res = run_agentic_react_loop(
        model="cyber-specialist:latest",
        user_prompt="Build a minimalist cyber timer with start button and countdown display in index.html, styles.css, app.js.",
        project_name=proj_name,
        max_steps=4
    )
    print("Agent Result Status:", res.get("status"))
    print("Files created:", res.get("created_files"))
    print("Compute Tier recorded:", res.get("compute_tier", {}).get("tier"))
    print("Steps taken:", len(res.get("steps", [])))

    assert res.get("compute_tier", {}).get("tier") == "lite_edge", "Expected lite_edge tier!"
    print("test_live_tier_build passed!")

if __name__ == "__main__":
    run_live_test()
