"""
BRUTAL MULTI-TIER STRESS TEST SUITE FOR UNLEASH-AGENT
Tests:
  - Pillar 1: Adversarial Dynamic Tier Profiling & Boundary Inversion (Local 8B vs Cloud Metered Free vs Frontier Paid)
  - Pillar 2: Prompt Token Budget & Tool Schema Isolation Under Extreme Conditions
  - Pillar 3: Dual-Engine Markdown Coercion & Adversarial Output Recovery (Chatter, naked fences, malformed JSON)
  - Pillar 4: Playwright Browser Gate Under Adversarial Web Conditions (Canvas RAF, Web Audio autoplay, state-machines, offline CDNs)
  - Pillar 5: Rate Pacing & Self-Repair Limit Confinement (429 prevention, repair capping, token truncation)
"""

import os
import sys
import re
import time
import json
import shutil
import tempfile
import unittest
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from backend.core.adaptive_tier import ExecutionTier, probe_active_compute_tier, probe_local_gpu_hardware
from backend.core.agent_tools import get_tool_schemas, get_all_tool_schemas, LEAN_TOOLS_SCHEMA, AGENT_TOOLS_SCHEMA
from backend.core.agent_engine import format_agentic_system_prompt, parse_react_output
from backend.core.browser_gate import audit_workspace_runtime, compress_browser_diagnostics
from backend.core.workspace_validator import validate_workspace, validate_javascript_syntax


class BrutalMultiTierStressTestSuite(unittest.TestCase):

    # =========================================================================
    # PILLAR 1: ADVERSARIAL TIER PROFILING & BOUNDARY INVERSION
    # =========================================================================

    def test_p1_01_local_edge_diverse_models(self):
        """Stress-tests local Ollama model strings across various families (Llama, Mistral, Qwen, DeepSeek)."""
        local_models = [
            "cyber-specialist:latest",
            "dolphin3:latest",
            "mistral:7b-instruct-q4_0",
            "qwen2.5-coder:7b",
            "qwen2.5-coder:1.5b-base",
            "codellama:13b",
            "llama3:8b",
            "deepseek-coder:6.7b"
        ]
        for lm in local_models:
            profile = probe_active_compute_tier(model_name=lm)
            self.assertEqual(profile["tier"], ExecutionTier.LITE_EDGE, f"Failed for {lm}")
            self.assertEqual(profile["toolset_mode"], "lean")
            self.assertEqual(profile["system_prompt_mode"], "lean")
            self.assertEqual(profile["self_repair_cap"], 2)
            self.assertEqual(profile["rate_pace_seconds"], 0.0)
            self.assertTrue(profile["compress_diagnostics"])
            self.assertEqual(len(profile["viewports"]), 1)
        print("  [PASS] P1.1: Local Ollama model families strictly resolve to LITE_EDGE.")

    def test_p1_02_cloud_metered_free_endpoints(self):
        """Stress-tests free cloud models (Groq on-demand, OpenRouter free variants)."""
        free_models = [
            "cloud:groq:llama-3.3-70b-versatile",
            "cloud:groq:qwen/qwen3.8-27b",
            "Cloud: Groq (llama-3.3-70b-versatile)",
            "cloud:openrouter:cohere/north-mini-code:free",
            "cloud:openrouter:qwen/qwen-2.5-coder-32b-instruct:free",
            "cloud:openrouter:deepseek/deepseek-r1:free",
            "cloud:openrouter:meta-llama/llama-3.3-70b-instruct:free",
            "cloud:openrouter:liquid/lfm-2.5-2.6b:free",
            "cloud:openrouter:nvidia/nemotron-3.5-lightning:free",
            "Cloud: OpenRouter (meta-llama/llama-3.3-70b-instruct:free)"
        ]
        for fm in free_models:
            profile = probe_active_compute_tier(model_name=fm)
            self.assertEqual(profile["tier"], ExecutionTier.CLOUD_METERED, f"Failed for {fm}")
            self.assertEqual(profile["toolset_mode"], "lean")
            self.assertEqual(profile["self_repair_cap"], 1, f"Failed repair cap for {fm}")
            self.assertEqual(profile["rate_pace_seconds"], 3.0, f"Failed rate pacing for {fm}")
            self.assertTrue(profile["compress_diagnostics"])
            self.assertEqual(len(profile["viewports"]), 1)
        print("  [PASS] P1.2: Free & rate-limited cloud models strictly resolve to CLOUD_METERED.")

    def test_p1_03_frontier_paid_endpoints(self):
        """Stress-tests paid enterprise models (Anthropic Claude 3.5, OpenAI GPT-4o, etc)."""
        frontier_models = [
            "cloud:anthropic:claude-3-5-sonnet",
            "cloud:anthropic:claude-3-5-sonnet-20241022",
            "cloud:openai:gpt-4o",
            "cloud:openai:o1-preview",
            "cloud:openrouter:anthropic/claude-3.5-sonnet",
            "cloud:openrouter:openai/gpt-4o",
            "Cloud: Anthropic (claude-3-5-sonnet)"
        ]
        for pm in frontier_models:
            profile = probe_active_compute_tier(model_name=pm)
            self.assertEqual(profile["tier"], ExecutionTier.FRONTIER_ULTRA, f"Failed for {pm}")
            self.assertEqual(profile["toolset_mode"], "full")
            self.assertEqual(profile["self_repair_cap"], 5)
            self.assertEqual(profile["rate_pace_seconds"], 0.0)
            self.assertFalse(profile["compress_diagnostics"])
            self.assertEqual(len(profile["viewports"]), 3)
        print("  [PASS] P1.3: Paid frontier models strictly resolve to FRONTIER_ULTRA.")

    def test_p1_04_adversarial_malformed_model_inputs(self):
        """Ensures the profiler never crashes on bizarre, null, or garbage inputs."""
        garbage_inputs = [None, "", "   ", "???", "cloud:::", "unknown/random:xyz", "model_with_no_provider"]
        for gb in garbage_inputs:
            profile = probe_active_compute_tier(model_name=gb)
            self.assertIn("tier", profile)
            self.assertIn(profile["tier"], (ExecutionTier.LITE_EDGE, ExecutionTier.CPU_SAFE, ExecutionTier.CLOUD_BALANCED))
            self.assertIsInstance(profile["max_milestones"], int)
            self.assertIsInstance(profile["max_steps"], int)
        print("  [PASS] P1.4: Malformed and adversarial model strings handled gracefully.")

    # =========================================================================
    # PILLAR 2: PROMPT TOKEN BUDGET & TOOL SCHEMA ISOLATION
    # =========================================================================

    def test_p2_01_lean_prompt_token_compression(self):
        """Verifies lean prompt strictly stays under 300 words (< 400 tokens) even with persona injection."""
        base_persona = "You are a cybersecurity focus assistant with high standards for visual design."
        lean_prompt = format_agentic_system_prompt(
            base_system=base_persona,
            project_name="stress_test_app",
            toolset_mode="lean"
        )
        word_count = len(lean_prompt.split())
        self.assertLess(word_count, 300, f"Lean prompt exceeds token budget: {word_count} words")
        print(f"  [PASS] P2.1: Lean system prompt is strictly compressed to {word_count} words.")

    def test_p2_02_tool_schema_airtight_isolation(self):
        """Ensures 100% of unused enterprise tools are stripped from lean mode."""
        lean_tools = get_tool_schemas(mode="lean")
        full_tools = get_tool_schemas(mode="full")

        self.assertEqual(len(lean_tools), 3)
        lean_names = [t["name"] for t in lean_tools]
        self.assertEqual(set(lean_names), {"write_project_file", "edit_project_file", "read_project_file"})

        # Enterprise tools must NOT appear in lean mode
        for enterprise_tool in ["run_in_sandbox", "search_knowledge_vault", "search_internet_dataset", "run_terminal_command", "append_project_file"]:
            self.assertNotIn(enterprise_tool, lean_names)

        # Full mode must have all native tools
        full_names = [t["name"] for t in full_tools]
        self.assertGreaterEqual(len(full_names), 12)
        for enterprise_tool in ["run_in_sandbox", "search_knowledge_vault", "write_project_file", "edit_project_file"]:
            self.assertIn(enterprise_tool, full_names)
        print("  [PASS] P2.2: Tool schemas airtightly isolated (3 tools lean vs 12+ full).")

    # =========================================================================
    # PILLAR 3: DUAL-ENGINE MARKDOWN COERCION & CHATTY RECOVERY
    # =========================================================================

    def test_p3_01_coercion_on_chatty_preamble(self):
        """Coerces chatty model output into write_project_file('index.html')."""
        output = """Sure! I have generated the entire HTML code for your cyberpunk pomodoro station.
I included the audio synthesizer, the timer display, and all the futuristic styling tags.

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Cyberpunk Station</title>
</head>
<body>
    <div id="timer">25:00</div>
    <button id="btn-start">Start</button>
</body>
</html>
```

Let me know if you want me to write the JavaScript next!"""
        thought, action, args, ans = parse_react_output(output)
        self.assertEqual(action, "write_project_file")
        self.assertEqual(args["file_path"], "index.html")
        self.assertIn("<div id=\"timer\">25:00</div>", args["content"])
        print("  [PASS] P3.1: Chatty preamble with ```html coerced to write_project_file('index.html').")

    def test_p3_02_coercion_on_unlabelled_css_block(self):
        """Coerces unlabelled code block with CSS properties into write_project_file('styles.css')."""
        output = """Here are the styles:
```
:root {
    --primary: #00ffcc;
    --bg: #0a0e17;
}
body {
    margin: 0;
    padding: 0;
    background: var(--bg);
    color: var(--primary);
    display: flex;
}
```"""
        thought, action, args, ans = parse_react_output(output)
        self.assertEqual(action, "write_project_file")
        self.assertEqual(args["file_path"], "styles.css")
        self.assertIn("var(--primary)", args["content"])
        print("  [PASS] P3.2: Unlabelled CSS code block coerced to write_project_file('styles.css').")

    def test_p3_03_coercion_on_unlabelled_js_block(self):
        """Coerces unlabelled code block with JS DOM logic into write_project_file('app.js')."""
        output = """```
let timerId = null;
const btnStart = document.getElementById('btn-start');
btnStart.addEventListener('click', () => {
    console.log('Timer started');
});
```"""
        thought, action, args, ans = parse_react_output(output)
        self.assertEqual(action, "write_project_file")
        self.assertEqual(args["file_path"], "app.js")
        self.assertIn("addEventListener", args["content"])
        print("  [PASS] P3.3: Unlabelled JS code block coerced to write_project_file('app.js').")

    # =========================================================================
    # PILLAR 4: PLAYWRIGHT BROWSER GATE ADVERSARIAL STRESS
    # =========================================================================

    def test_p4_01_canvas_game_pixel_and_raf(self):
        """Tests that a 2D Canvas game with animation loop passes without false blank-screen failure."""
        tmp = Path(tempfile.mkdtemp(prefix="stress_canvas_"))
        try:
            (tmp / "index.html").write_text("""<!DOCTYPE html>
<html><body>
<canvas id="game" width="300" height="200"></canvas>
<script src="app.js"></script>
</body></html>""", encoding="utf-8")

            (tmp / "app.js").write_text("""
const canvas = document.getElementById('game');
const ctx = canvas.getContext('2d');
let x = 0;
function loop() {
    ctx.fillStyle = '#111';
    ctx.fillRect(0, 0, 300, 200);
    ctx.fillStyle = '#00ffcc';
    ctx.fillRect(x, 50, 40, 40);
    x = (x + 2) % 300;
    requestAnimationFrame(loop);
}
loop();
""", encoding="utf-8")

            res = audit_workspace_runtime(tmp)
            self.assertTrue(res["valid"], f"Canvas test failed: {res.get('critical_errors')}")
            self.assertTrue(res["is_rendered"])
            print("  [PASS] P4.1: HTML5 Canvas 2D game with requestAnimationFrame loop passes audit cleanly.")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_p4_02_web_audio_autoplay_unlock(self):
        """Tests that immediate AudioContext instantiation on load does not throw autoplay errors."""
        tmp = Path(tempfile.mkdtemp(prefix="stress_audio_"))
        try:
            (tmp / "index.html").write_text("""<!DOCTYPE html>
<html><body>
<h1>Synthesizer</h1>
<button id="beepBtn">Beep</button>
<script src="app.js"></script>
</body></html>""", encoding="utf-8")

            (tmp / "app.js").write_text("""
// Auto-instantiate Web Audio API immediately on script load
const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
document.getElementById('beepBtn').addEventListener('click', () => {
    const osc = audioCtx.createOscillator();
    osc.connect(audioCtx.destination);
    osc.start();
    osc.stop(audioCtx.currentTime + 0.1);
});
""", encoding="utf-8")

            res = audit_workspace_runtime(tmp)
            self.assertTrue(res["valid"], f"Audio test failed: {res.get('critical_errors')}")
            # Ensure no autoplay warning in critical errors
            self.assertFalse(any("audiocontext" in e.lower() for e in res["critical_errors"]))
            print("  [PASS] P4.2: Web Audio API auto-resumes cleanly in headless Chromium.")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_p4_03_state_machine_disabled_button(self):
        """Tests that a disabled button is NOT flagged as an unresponsive dead control."""
        tmp = Path(tempfile.mkdtemp(prefix="stress_disabled_"))
        try:
            (tmp / "index.html").write_text("""<!DOCTYPE html>
<html><body>
<input type="text" id="itemName" placeholder="Item name">
<button id="activeBtn">Add Item</button>
<button id="disabledCheckout" disabled>Checkout (Disabled)</button>
<script src="app.js"></script>
</body></html>""", encoding="utf-8")

            (tmp / "app.js").write_text("""
document.getElementById('activeBtn').addEventListener('click', () => {
    document.body.appendChild(document.createElement('p')).innerText = "Added";
});
""", encoding="utf-8")

            res = audit_workspace_runtime(tmp)
            self.assertTrue(res["valid"], f"Disabled button test failed: {res.get('critical_errors')}")
            # Check interaction records
            disabled_records = [i for i in res["interactions"] if i.get("is_disabled")]
            self.assertEqual(len(disabled_records), 1)
            self.assertEqual(disabled_records[0]["element"], "#disabledCheckout")
            print("  [PASS] P4.3: Disabled state machine buttons exempted from dead control warnings.")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # =========================================================================
    # PILLAR 5: RATE PACING & SELF-REPAIR CONFINEMENT
    # =========================================================================

    def test_p5_01_self_repair_cap_bounds(self):
        """Verifies self-repair caps prevent runaway loops across all tiers."""
        p_free = probe_active_compute_tier(model_name="cloud:groq:llama-3.3-70b-versatile")
        p_local = probe_active_compute_tier(model_name="cyber-specialist:latest")
        p_paid = probe_active_compute_tier(model_name="cloud:anthropic:claude-3-5-sonnet")

        self.assertEqual(p_free["self_repair_cap"], 1)
        self.assertEqual(p_local["self_repair_cap"], 2)
        self.assertEqual(p_paid["self_repair_cap"], 5)
        print("  [PASS] P5.1: Self-repair caps mathematically bounded (1 for free, 2 for local, 5 for paid).")

    def test_p5_02_rate_pacing_deliberate_delay(self):
        """Verifies that free cloud models enforce 3.0s pacing while local and paid stay at 0.0s."""
        p_groq = probe_active_compute_tier(model_name="cloud:groq:llama-3.3-70b-versatile")
        p_openrouter_free = probe_active_compute_tier(model_name="cloud:openrouter:cohere/north-mini-code:free")
        p_local = probe_active_compute_tier(model_name="dolphin3:latest")
        p_paid = probe_active_compute_tier(model_name="cloud:openai:gpt-4o")

        self.assertEqual(p_groq["rate_pace_seconds"], 3.0)
        self.assertEqual(p_openrouter_free["rate_pace_seconds"], 3.0)
        self.assertEqual(p_local["rate_pace_seconds"], 0.0)
        self.assertEqual(p_paid["rate_pace_seconds"], 0.0)
        print("  [PASS] P5.2: Rate pacing enforced at 3.0s for free cloud; 0.0s for local and paid.")

    def test_p5_03_diagnostics_token_confinement(self):
        """Verifies compress_browser_diagnostics caps even multi-error failures to under 50 words."""
        overloaded_failure = {
            "valid": False,
            "critical_errors": [
                "BUTTON CRASH: Clicking '#btn-1' threw: TypeError: Cannot read properties of null",
                "BUTTON CRASH: Clicking '#btn-2' threw: ReferenceError: 'foo' is not defined",
                "BUTTON CRASH: Clicking '#btn-3' threw: SyntaxError: Unexpected token",
                "UNHANDLED RUNTIME EXCEPTION: Error in app.js at line 99",
                "RESPONSIVE OVERFLOW on mobile: 500px > 390px"
            ],
            "diagnostics": [
                {"file": "app.js", "category": "runtime_exception", "message": "error details"},
                {"file": "styles.css", "category": "responsive_overflow", "message": "overflow details"}
            ]
        }
        compressed = compress_browser_diagnostics(overloaded_failure, max_items=3)
        word_count = len(compressed.split())
        self.assertLess(word_count, 50, f"Overloaded failure diagnostics too large: {word_count} words")
        self.assertIn("BROWSER VERIFICATION FAILED:", compressed)
        self.assertIn("Prescriptive Fix:", compressed)
        print(f"  [PASS] P5.3: Overloaded multi-error diagnostics strictly confined to {word_count} words (< 50 words).")


if __name__ == "__main__":
    print("\n" + "="*75)
    print("STARTING BRUTAL MULTI-TIER ADAPTIVE HARNESS STRESS TEST SUITE")
    print("="*75 + "\n")
    suite = unittest.TestLoader().loadTestsFromTestCase(BrutalMultiTierStressTestSuite)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if result.wasSuccessful():
        print("\n" + "="*75)
        print("BRUTAL MULTI-TIER STRESS TEST SUITE: ALL TESTS PASSED SUCCESSFULLY!")
        print("="*75)
        sys.exit(0)
    else:
        print("\n" + "="*75)
        print(f"STRESS TEST FAILURES DETECTED: {len(result.failures)} failures, {len(result.errors)} errors")
        print("="*75)
        sys.exit(1)
