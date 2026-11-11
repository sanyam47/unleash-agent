"""
Comprehensive Verification Suite for Dynamic LLM Adaptive Harness Architecture.
Validates:
1. Dynamic Tier Classification (Local 8B vs Cloud Metered Free vs Frontier Paid)
2. Lean vs Full Toolset & System Prompt Token Economy
3. Dual-Engine Markdown Auto-Coercion
4. Deliberate Rate Pacing & Self-Repair Caps
5. Playwright Browser Diagnostics Compression
"""

import sys
import unittest
from pathlib import Path

# Add repo root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.core.adaptive_tier import ExecutionTier, probe_active_compute_tier
from backend.core.agent_tools import get_tool_schemas, get_all_tool_schemas
from backend.core.agent_engine import format_agentic_system_prompt, parse_react_output
from backend.core.browser_gate import compress_browser_diagnostics


class TestDynamicHarnessArchitecture(unittest.TestCase):

    def test_01_tier_classification_local_edge(self):
        """Validates that local models on Ollama (no cloud: prefix) resolve to LITE_EDGE with lean toolset."""
        for local_m in ["cyber-specialist:latest", "dolphin3:latest", "llama3:8b", "qwen2.5-coder:7b"]:
            profile = probe_active_compute_tier(model_name=local_m)
            self.assertEqual(profile["tier"], ExecutionTier.LITE_EDGE, f"Failed for {local_m}")
            self.assertEqual(profile["toolset_mode"], "lean")
            self.assertEqual(profile["system_prompt_mode"], "lean")
            self.assertEqual(profile["self_repair_cap"], 2)
            self.assertEqual(profile["rate_pace_seconds"], 0.0)
            self.assertTrue(profile["compress_diagnostics"])
            self.assertEqual(len(profile["viewports"]), 1)
        print("  ✓ Test 1 Passed: Local Ollama models resolve to LITE_EDGE with lean profile.")

    def test_02_tier_classification_cloud_metered_free(self):
        """Validates that Groq free tier and OpenRouter :free models resolve to CLOUD_METERED."""
        free_models = [
            "cloud:groq:llama-3.3-70b-versatile",
            "cloud:openrouter:cohere/north-mini-code:free",
            "cloud:openrouter:qwen/qwen-2.5-coder-32b-instruct:free",
            "cloud:openrouter:deepseek/deepseek-r1:free",
            "cloud:openrouter:meta-llama/llama-3.3-70b-instruct:free"
        ]
        for m in free_models:
            profile = probe_active_compute_tier(model_name=m)
            self.assertEqual(profile["tier"], ExecutionTier.CLOUD_METERED, f"Failed for {m}")
            self.assertEqual(profile["toolset_mode"], "lean")
            self.assertEqual(profile["self_repair_cap"], 1)
            self.assertEqual(profile["rate_pace_seconds"], 3.0)
            self.assertTrue(profile["compress_diagnostics"])
            self.assertEqual(len(profile["viewports"]), 1)
        print("  ✓ Test 2 Passed: Groq & OpenRouter :free models resolve to CLOUD_METERED.")

    def test_03_tier_classification_frontier_paid(self):
        """Validates that paid frontier models resolve to FRONTIER_ULTRA with full toolset and multi-viewports."""
        frontier_models = [
            "cloud:anthropic:claude-3-5-sonnet",
            "cloud:openai:gpt-4o",
            "cloud:openrouter:anthropic/claude-3.5-sonnet"
        ]
        for m in frontier_models:
            profile = probe_active_compute_tier(model_name=m)
            self.assertEqual(profile["tier"], ExecutionTier.FRONTIER_ULTRA, f"Failed for {m}")
            self.assertEqual(profile["toolset_mode"], "full")
            self.assertEqual(profile["self_repair_cap"], 5)
            self.assertEqual(profile["rate_pace_seconds"], 0.0)
            self.assertFalse(profile["compress_diagnostics"])
            self.assertEqual(len(profile["viewports"]), 3)  # desktop, tablet, mobile
        print("  ✓ Test 3 Passed: Frontier paid models resolve to FRONTIER_ULTRA with full toolset.")

    def test_04_lean_vs_full_prompt_economy(self):
        """Validates that lean system prompt is <400 tokens while preserving production instructions."""
        lean_prompt = format_agentic_system_prompt(
            base_system="You are an expert",
            project_name="cyber_pomodoro_app",
            toolset_mode="lean"
        )
        full_prompt = format_agentic_system_prompt(
            base_system="You are an expert",
            project_name="cyber_pomodoro_app",
            toolset_mode="full"
        )

        lean_words = len(lean_prompt.split())
        full_words = len(full_prompt.split())

        # Word count < 300 words roughly translates to < 400 tokens
        self.assertLess(lean_words, 300, f"Lean prompt too large: {lean_words} words")
        self.assertGreater(full_words, 500, f"Full prompt should have full tools: {full_words} words")
        
        # Verify lean prompt only advertises 3 tools
        self.assertIn("write_project_file", lean_prompt)
        self.assertIn("edit_project_file", lean_prompt)
        self.assertIn("read_project_file", lean_prompt)
        self.assertNotIn("run_in_sandbox", lean_prompt)
        self.assertNotIn("search_knowledge_vault", lean_prompt)
        print(f"  ✓ Test 4 Passed: Lean prompt is {lean_words} words (vs {full_words} words full prompt).")

    def test_05_dual_engine_markdown_auto_coercion(self):
        """Validates that raw markdown code output from chatty models is automatically coerced to disk writing."""
        # 1. Output with explicit language tag
        raw_html_output = """Here is the complete HTML file you requested:
```html
<!DOCTYPE html>
<html lang="en">
<head><title>Pomodoro</title></head>
<body><div id="timer">25:00</div></body>
</html>
```
Hope this helps!"""
        thought, action, args, ans = parse_react_output(raw_html_output)
        self.assertEqual(action, "write_project_file")
        self.assertEqual(args["file_path"], "index.html")
        self.assertIn("<!DOCTYPE html>", args["content"])

        # 2. Output with javascript code fence
        raw_js_output = """Here is the JavaScript code:
```javascript
const timer = document.getElementById('timer');
document.addEventListener('DOMContentLoaded', () => {
    console.log('App ready');
});
```"""
        thought, action, args, ans = parse_react_output(raw_js_output)
        self.assertEqual(action, "write_project_file")
        self.assertEqual(args["file_path"], "app.js")
        self.assertIn("addEventListener", args["content"])

        # 3. Output with generic code fence and CSS styling
        raw_css_output = """```
body {
    margin: 0;
    padding: 0;
    background: #0f172a;
    color: #f8fafc;
}
```"""
        thought, action, args, ans = parse_react_output(raw_css_output)
        self.assertEqual(action, "write_project_file")
        self.assertEqual(args["file_path"], "styles.css")
        self.assertIn("background: #0f172a", args["content"])
        print("  ✓ Test 5 Passed: Dual-Engine auto-coercion converts raw markdown to write_project_file.")

    def test_06_browser_diagnostics_token_budget(self):
        """Validates that browser diagnostics for free models are strictly compressed under 50 words."""
        mock_audit = {
            "valid": False,
            "critical_errors": [
                "BUTTON CRASH: Clicking '#startBtn' threw: TypeError: Cannot read properties of null",
                "UNHANDLED RUNTIME EXCEPTION: ReferenceError: 'synth' is not defined in startTimer()."
            ],
            "diagnostics": [
                {"file": "app.js", "category": "runtime_exception", "message": "synth is not defined"}
            ]
        }
        compressed = compress_browser_diagnostics(mock_audit)
        word_count = len(compressed.split())
        self.assertLess(word_count, 50, f"Compressed output too large: {word_count} words")
        self.assertIn("BUTTON CRASH", compressed)
        self.assertIn("Prescriptive Fix: Correct logic in 'app.js'", compressed)
        print(f"  ✓ Test 6 Passed: Compressed browser diagnostics is {word_count} words (< 50 words).")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("RUNNING DYNAMIC LLM ADAPTIVE HARNESS ARCHITECTURE TEST SUITE")
    print("="*70)
    unittest.main()
