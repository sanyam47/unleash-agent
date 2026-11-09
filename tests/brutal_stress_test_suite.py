"""
BRUTAL COMPREHENSIVE STRESS TEST SUITE FOR UNLEASH-AGENT
Tests:
  - Pillar 1: Security, Sandboxing & Jail Hardening (Path traversal, blocked commands, ellipsis/stubs, safe storage)
  - Pillar 2: Architecture, Dynamic Hardware Tiers & Stepper Pipelines (VRAM budgeting, adaptive milestone scaling, decomposed goals)
  - Pillar 3: 5-Layer Acceptance Gate & Dynamic Diagnostic Provenance (Runtime crashes, syntax errors, responsive overflow, target attribution)
  - Pillar 4: Autonomous Multi-Turn Agent Execution & Self-Repair (Live Ollama Dolphin3 8B model run)
"""

import os
import sys
import time
import json
import shutil
import subprocess
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from backend.core.agent_tools import (
    resolve_safe_project_path,
    sanitize_project_name,
    _validate_safe_os_path,
    write_project_file,
    read_project_file,
    edit_project_file,
    run_terminal_command,
    get_project_dir,
    PROJECTS_ROOT
)
from backend.core.adaptive_tier import probe_local_gpu_hardware, probe_active_compute_tier, ExecutionTier
from backend.core.goal_stepper import decompose_goals, verify_milestones, format_goal_checklist_for_prompt
from backend.core.browser_gate import audit_workspace_runtime
from backend.core.workspace_validator import validate_workspace

passed_count = 0
failed_count = 0
results_log = []

def record(category, test_name, success, details=""):
    global passed_count, failed_count
    if success:
        passed_count += 1
        print(f"  [PASS] {test_name}")
    else:
        failed_count += 1
        print(f"  [FAIL] {test_name}: {details}")
    results_log.append({
        "category": category,
        "test": test_name,
        "success": success,
        "details": details
    })


# Reusable realistic HTML template to satisfy Layer 2 Semantic Layout Depth Gate
REALISTIC_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <header class="app-header">
        <nav class="navbar">
            <div class="logo">AppSystem</div>
            <ul class="nav-links">
                <li><a href="#hero">Overview</a></li>
                <li><a href="#features">Features</a></li>
            </ul>
        </nav>
        <h1>{headline}</h1>
    </header>
    <main>
        <section id="hero" class="hero-section">
            <p>Production dashboard and interactive control system.</p>
            {content}
        </section>
        <section id="features" class="features-grid">
            <div class="card">
                <h3>Telemetry</h3>
                <p>Real-time metrics and system state monitoring.</p>
            </div>
            <div class="card">
                <h3>Diagnostics</h3>
                <p>Automated acceptance gates and headless verification.</p>
            </div>
        </section>
    </main>
    <footer class="app-footer">
        <p>&copy; 2026 Unleash-Agent Autonomous Workspace. All rights reserved.</p>
    </footer>
    <script src="{script}"></script>
</body>
</html>"""

REALISTIC_CSS = """
body {
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background-color: #0f172a;
    color: #f8fafc;
}
.app-header {
    background: #1e293b;
    padding: 1.5rem 2rem;
    border-bottom: 1px solid #334155;
}
.navbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.nav-links {
    display: flex;
    gap: 1.5rem;
    list-style: none;
    margin: 0;
    padding: 0;
}
.nav-links a {
    color: #94a3b8;
    text-decoration: none;
}
main {
    max-width: 1200px;
    margin: 2rem auto;
    padding: 0 1.5rem;
}
.hero-section {
    background: #1e293b;
    padding: 2rem;
    border-radius: 8px;
    margin-bottom: 2rem;
}
.features-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 1.5rem;
}
.card {
    background: #1e293b;
    padding: 1.5rem;
    border-radius: 8px;
    border: 1px solid #334155;
}
button {
    background: #3b82f6;
    color: white;
    border: none;
    padding: 0.75rem 1.5rem;
    border-radius: 6px;
    cursor: pointer;
    font-weight: 600;
}
button:hover {
    background: #2563eb;
}
.app-footer {
    text-align: center;
    padding: 2rem;
    color: #64748b;
    border-top: 1px solid #1e293b;
}
"""


# ==============================================================================
# PILLAR 1: SECURITY, SANDBOXING & JAIL HARDENING
# ==============================================================================
def run_security_stress_tests():
    print("\n" + "="*70)
    print("PILLAR 1: SECURITY, SANDBOXING & JAIL HARDENING")
    print("="*70)

    # 1.1 Path Traversal via Relative Paths
    test_proj = "sec_audit_proj_1"
    try:
        resolve_safe_project_path(test_proj, "../../secret.txt")
        record("Security", "1.1 Relative Path Traversal Block (../../secret.txt)", False, "Failed to block traversal")
    except PermissionError:
        record("Security", "1.1 Relative Path Traversal Block (../../secret.txt)", True)
    except Exception as e:
        record("Security", "1.1 Relative Path Traversal Block (../../secret.txt)", False, str(e))

    # 1.2 Deep Traversal Block
    try:
        resolve_safe_project_path(test_proj, "../../../../../../../Windows/System32/cmd.exe")
        record("Security", "1.2 Deep Traversal Block (..*7/cmd.exe)", False, "Failed to block traversal")
    except PermissionError:
        record("Security", "1.2 Deep Traversal Block (..*7/cmd.exe)", True)
    except Exception as e:
        record("Security", "1.2 Deep Traversal Block (..*7/cmd.exe)", False, str(e))

    # 1.3 Absolute Path Traversal
    try:
        p = resolve_safe_project_path(test_proj, "C:/Windows/System32/drivers/etc/hosts")
        proj_dir = get_project_dir(test_proj)
        p.relative_to(proj_dir)
        record("Security", "1.3 Absolute Path Stripping & Containment", True)
    except Exception as e:
        record("Security", "1.3 Absolute Path Stripping & Containment", False, str(e))

    # 1.4 Project Name Sanitization
    dirty_names = [
        ("../../etc/shadow", "______etc_shadow"),
        ("malicious;drop table users;", "malicious_drop_table_users_"),
        ("CON", "CON"),
        ("a" * 100, ("a" * 100)[:48])
    ]
    all_clean = True
    for dirty, expected_sub in dirty_names:
        cleaned = sanitize_project_name(dirty)
        if "/" in cleaned or "\\" in cleaned or ";" in cleaned or len(cleaned) > 48:
            all_clean = False
            break
    record("Security", "1.4 Project Name Sanitization & Boundary Cap", all_clean)

    # 1.5 Safe OS Path Validator (_validate_safe_os_path)
    dangerous_paths = [
        Path(r"C:\Windows"),
        Path(r"C:\Windows\System32"),
        Path(r"C:\Program Files"),
        Path(r"C:\Program Files (x86)"),
        Path(r"C:\System Volume Information"),
        Path(r"C:\\"),
        Path(r"D:\ ")
    ]
    os_safe = True
    for dp in dangerous_paths:
        if _validate_safe_os_path(dp) is not None:
            os_safe = False
            break
    record("Security", "1.5 OS System Root Guard (_validate_safe_os_path)", os_safe)

    # 1.6 Blocked Destructive Terminal Commands
    malicious_cmds = [
        "format c: /fs:ntfs",
        "del /s /q c:\\test",
        "rmdir /s /q c:\\test",
        "reg add HKLM\\Software",
        "regedit /s evil.reg",
        "netsh advfirewall set allprofiles state off",
        "shutdown /s /t 0",
        "powershell -encodedCommand JABhAD0AMQA=",
        "cmd.exe /c calc.exe"
    ]
    blocked_all = True
    for cmd in malicious_cmds:
        res = run_terminal_command(test_proj, cmd)
        if res.get("status") != "error" or "SECURITY BLOCK" not in res.get("error", ""):
            blocked_all = False
            print(f"    Failed to block: {cmd} -> {res}")
            break
    record("Security", "1.6 Destructive Command Blacklist Enforcement", blocked_all)

    # 1.7 Ellipsis / Stub Code Injection Rejection
    ellipsis_snippets = [
        ("styles.css", "body {\n  margin: 0;\n  ...\n}"),
        ("app.js", "function run() {\n  /* ... */\n}"),
        ("app.js", "function init() {\n  // ...\n}")
    ]
    rejected_all = True
    for fname, code in ellipsis_snippets:
        res = write_project_file(test_proj, fname, code)
        if res.get("status") != "error" or "ellipsis" not in res.get("error", "").lower():
            rejected_all = False
            print(f"    Failed to reject ellipsis in {fname}: {res}")
            break
    record("Security", "1.7 Ellipsis & Stub Code Injection Rejection", rejected_all)

    # 1.8 Unsafe Storage Detection in Layer 1
    unsafe_js = "function saveUser(u) { localStorage.setItem('user', JSON.stringify(u)); }"
    write_project_file(test_proj, "app.js", unsafe_js)
    html_content = REALISTIC_HTML_TEMPLATE.format(title="Storage Test", headline="Storage Test", content="<p>Test</p>", script="app.js")
    write_project_file(test_proj, "index.html", html_content)
    write_project_file(test_proj, "styles.css", REALISTIC_CSS)
    health = validate_workspace(test_proj)
    has_unsafe = any("UNSAFE STORAGE" in e or "unsafe_storage" in str(d.get("category")) for d in health.get("diagnostics", []) for e in [d.get("message", "")])
    record("Security", "1.8 Bare localStorage Sandboxed Iframe Detection", has_unsafe)

    # Clean up test project
    proj_dir = get_project_dir(test_proj)
    if proj_dir.exists():
        shutil.rmtree(proj_dir, ignore_errors=True)


# ==============================================================================
# PILLAR 2: ARCHITECTURE, DYNAMIC HARDWARE TIERS & STEPPER PIPELINES
# ==============================================================================
def run_architecture_pipeline_tests():
    print("\n" + "="*70)
    print("PILLAR 2: ARCHITECTURE, DYNAMIC HARDWARE TIERS & STEPPER PIPELINES")
    print("="*70)

    # 2.1 Hardware Probe Resolution
    hw = probe_local_gpu_hardware()
    valid_hw = "vram_gb" in hw and hw["vram_gb"] > 0
    record("Architecture", "2.1 Real-Time Hardware & VRAM Probe", valid_hw, f"GPU: {hw.get('gpu_name')}, VRAM: {hw.get('vram_gb')} GB")

    # 2.2 Tier Resolution & Milestone Cap Scaling
    tier_lite = probe_active_compute_tier(model_name="dolphin3:latest")
    tier_cloud = probe_active_compute_tier(model_name="qwen2.5-coder:32b")
    tier_ultra = probe_active_compute_tier(model_name="llava:13b")
    
    tier_scaling = (
        tier_lite["tier"] == ExecutionTier.LITE_EDGE and tier_lite["max_milestones"] == 4 and tier_lite["context_window"] == 8192 and
        tier_cloud["tier"] == ExecutionTier.CLOUD_BALANCED and tier_cloud["max_milestones"] == 6 and
        tier_ultra["tier"] == ExecutionTier.FRONTIER_ULTRA and tier_ultra["max_milestones"] == 8
    )
    record("Architecture", "2.2 Adaptive Tier Sizing & Milestone Caps (4 -> 6 -> 8)", tier_scaling)

    # 2.3 Context Window Budgeting (Prevent 6GB VRAM Swap)
    if hw["vram_gb"] <= 6.5:
        cw_safe = tier_lite["context_window"] <= 8192
    else:
        cw_safe = True
    record("Architecture", "2.3 VRAM Budget Protection (8192 context on <=6GB GPU)", cw_safe, f"Context: {tier_lite['context_window']}")

    # 2.4 Goal Decomposition Dynamic Milestones
    prompt = "Build a comprehensive e-commerce store with product catalog, cart drawer, checkout modal, search filter, and reviews"
    goals_lite = decompose_goals(prompt, max_milestones=4)
    goals_balanced = decompose_goals(prompt, max_milestones=6)
    goals_ultra = decompose_goals(prompt, max_milestones=8)
    decomp_valid = len(goals_lite) <= 4 and len(goals_balanced) <= 6 and len(goals_ultra) <= 8 and len(goals_lite) <= len(goals_balanced) <= len(goals_ultra)
    record("Architecture", "2.4 Dynamic Goal Decomposition Scaling by Tier", decomp_valid)

    # 2.5 Milestone Verification Accuracy (Realistic Code)
    mock_proj = "mock_stepper_proj"
    p_dir = get_project_dir(mock_proj)
    p_dir.mkdir(parents=True, exist_ok=True)
    html_content = REALISTIC_HTML_TEMPLATE.format(title="Pomodoro", headline="Pomodoro App", content="<div id='timer'>25:00</div>", script="app.js")
    (p_dir / "index.html").write_text(html_content, encoding="utf-8")
    (p_dir / "styles.css").write_text(REALISTIC_CSS, encoding="utf-8")
    (p_dir / "app.js").write_text("console.log('init');", encoding="utf-8")

    m_res = verify_milestones(p_dir, goals_lite, current_step=1)
    m1_done = any(m["id"] == "milestone_layout" and m["status"] == "verified" for m in m_res["milestones"])
    record("Architecture", "2.5 AST & DOM Milestone Verification Engine", m1_done)

    # Clean up mock project
    shutil.rmtree(p_dir, ignore_errors=True)


# ==============================================================================
# PILLAR 3: 5-LAYER ACCEPTANCE GATE & DYNAMIC DIAGNOSTIC PROVENANCE
# ==============================================================================
def run_acceptance_gate_provenance_tests():
    print("\n" + "="*70)
    print("PILLAR 3: 5-LAYER ACCEPTANCE GATE & DYNAMIC DIAGNOSTIC PROVENANCE")
    print("="*70)

    # 3.1 JavaScript Syntax Error Attribution
    test_proj = "prov_audit_js_syntax"
    html_content = REALISTIC_HTML_TEMPLATE.format(title="Syntax App", headline="Syntax Test", content="<p>Testing syntax errors</p>", script="app.js")
    write_project_file(test_proj, "index.html", html_content)
    write_project_file(test_proj, "styles.css", REALISTIC_CSS)
    write_project_file(test_proj, "app.js", "function broken( { let x = ; }")
    h_syntax = validate_workspace(test_proj)
    record(
        "Acceptance Gate",
        "3.1 JS Syntax Error -> Attributed to app.js",
        h_syntax.get("valid") is False and h_syntax.get("primary_repair_file") == "app.js",
        f"Target: {h_syntax.get('primary_repair_file')}"
    )

    # 3.2 Browser Runtime Exception Attribution
    test_proj_runtime = "prov_audit_runtime"
    runtime_html = REALISTIC_HTML_TEMPLATE.format(
        title="Runtime App",
        headline="Runtime Test",
        content="<button id='actionBtn'>Do Action</button>",
        script="custom_script.js"
    )
    write_project_file(test_proj_runtime, "index.html", runtime_html)
    write_project_file(test_proj_runtime, "styles.css", REALISTIC_CSS)
    write_project_file(test_proj_runtime, "custom_script.js", """
document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('actionBtn');
    if (btn) {
        btn.addEventListener('click', () => {
            nonExistentObject.doSomething();
        });
    }
});
""")
    h_runtime = validate_workspace(test_proj_runtime)
    record(
        "Acceptance Gate",
        "3.2 Browser Runtime Button Crash -> Attributed to custom_script.js",
        h_runtime.get("valid") is False and h_runtime.get("primary_repair_file") == "custom_script.js",
        f"Target: {h_runtime.get('primary_repair_file')}"
    )

    # 3.3 Dead Interactive Controls (Unbound HTML Buttons)
    test_proj_dead = "prov_audit_dead_controls"
    dead_html = REALISTIC_HTML_TEMPLATE.format(
        title="Dead Control App",
        headline="Interactive Test",
        content="<button id='orphanBtn'>Click Me</button>",
        script="app.js"
    )
    write_project_file(test_proj_dead, "index.html", dead_html)
    write_project_file(test_proj_dead, "styles.css", REALISTIC_CSS)
    write_project_file(test_proj_dead, "app.js", "console.log('ready');")
    h_dead = validate_workspace(test_proj_dead)
    record(
        "Acceptance Gate",
        "3.3 Unbound HTML Buttons (Dead Control) -> Attributed to app.js",
        h_dead.get("primary_repair_file") == "app.js",
        f"Target: {h_dead.get('primary_repair_file')}"
    )

    # 3.4 Responsive Viewport Overflow Attribution
    test_proj_css = "prov_audit_css_overflow"
    css_html = REALISTIC_HTML_TEMPLATE.format(
        title="CSS Overflow App",
        headline="Responsive Test",
        content="<div class='giant'>Wide Overflow Container</div>",
        script="app.js"
    )
    write_project_file(test_proj_css, "index.html", css_html)
    write_project_file(test_proj_css, "styles.css", REALISTIC_CSS + "\n.giant { width: 5000px; height: 100px; background: red; }")
    write_project_file(test_proj_css, "app.js", "console.log('ok');")
    h_css = validate_workspace(test_proj_css, viewports=[{"name": "mobile", "width": 375, "height": 667}])
    record(
        "Acceptance Gate",
        "3.4 Responsive Horizontal Overflow -> Attributed to styles.css",
        h_css.get("valid") is False and h_css.get("primary_repair_file") == "styles.css",
        f"Target: {h_css.get('primary_repair_file')}"
    )

    # 3.5 Blank Rendered Screen
    test_proj_blank = "prov_audit_blank"
    write_project_file(test_proj_blank, "index.html", "<!DOCTYPE html><html><head></head><body></body></html>")
    write_project_file(test_proj_blank, "styles.css", "body { margin: 0; }")
    write_project_file(test_proj_blank, "app.js", "console.log('empty');")
    h_blank = validate_workspace(test_proj_blank)
    record(
        "Acceptance Gate",
        "3.5 Blank Screen Detection -> Attributed to index.html",
        h_blank.get("valid") is False and h_blank.get("primary_repair_file") == "index.html",
        f"Target: {h_blank.get('primary_repair_file')}"
    )

    # 3.6 Summary Prescriptive Formatting
    summary_txt = h_runtime.get("summary", "")
    has_target_header = "[TARGET FILE TO EDIT: 'custom_script.js']" in summary_txt
    has_prescriptive_instr = "Do NOT modify 'index.html'" in summary_txt
    record(
        "Acceptance Gate",
        "3.6 Prescriptive Guidance & Target File Header in Summary",
        has_target_header and has_prescriptive_instr
    )

    # Clean up test projects
    for p in [test_proj, test_proj_runtime, test_proj_dead, test_proj_css, test_proj_blank]:
        shutil.rmtree(get_project_dir(p), ignore_errors=True)


# ==============================================================================
# PILLAR 4: AUTONOMOUS MULTI-TURN AGENT EXECUTION & REPAIR
# ==============================================================================
def run_live_agent_multiturn_stress_test():
    print("\n" + "="*70)
    print("PILLAR 4: AUTONOMOUS MULTI-TURN AGENT EXECUTION & REPAIR (LIVE 8B MODEL)")
    print("="*70)

    from backend.core.agent_engine import run_agentic_react_loop

    proj_name = f"stress_flight_{int(time.time())}"
    print(f"Target Project: {proj_name}")

    # TURN 1: Build complex Space Flight Telemetry Simulator
    turn1_prompt = (
        "Build a Space Flight Telemetry Simulator. "
        "Include a telemetry dashboard with an orbital velocity gauge, fuel percentage bar, "
        "engine thruster toggle button (id='thrusterBtn'), and emergency abort button (id='abortBtn'). "
        "Ensure full interactive JavaScript logic and responsive styling."
    )
    print("\n--- STARTING TURN 1 (Initial Build) ---")
    t0 = time.perf_counter()
    res1 = run_agentic_react_loop(
        model="dolphin3:latest",
        user_prompt=turn1_prompt,
        project_name=proj_name,
        max_steps=10
    )
    t1_dur = round(time.perf_counter() - t0, 2)
    print(f"Turn 1 completed in {t1_dur}s. Steps taken: {len(res1.get('steps', []))}")
    print(f"Created files: {res1.get('created_files')}")
    print(f"Tokens/sec: {res1.get('telemetry', {}).get('tokens_per_second')}")

    # Validate Turn 1 disk files
    proj_dir = get_project_dir(proj_name)
    has_files = (proj_dir / "index.html").exists() and (proj_dir / "app.js").exists() and (proj_dir / "styles.css").exists()
    record("Agent Multi-Turn", "4.1 Turn 1 Core Files Creation (HTML/CSS/JS)", has_files)

    # Audit Turn 1 workspace health
    h1 = validate_workspace(proj_name)
    print(f"Turn 1 Gate Status: Valid={h1.get('valid')}")
    if not h1.get('valid'):
        print(f"Turn 1 Gate Summary:\n{h1.get('summary')}")

    # TURN 2: Brutal Mutation / Feature Addition / Logic Test
    turn2_prompt = (
        "Add a gravity assist calculation button (id='gravityAssistBtn') and an audio alert beep when fuel drops below 10%. "
        "Update the thruster logic in app.js so fuel decreases smoothly when thrusters are active. "
        "Use edit_project_file to surgically update app.js and styles.css without breaking existing elements."
    )
    print("\n--- STARTING TURN 2 (Targeted Feature Addition & Self-Repair) ---")
    chat_hist = [
        {"role": "user", "content": turn1_prompt},
        {"role": "assistant", "content": res1.get("reply", "")}
    ]
    t0 = time.perf_counter()
    res2 = run_agentic_react_loop(
        model="dolphin3:latest",
        user_prompt=turn2_prompt,
        project_name=proj_name,
        chat_history=chat_hist,
        max_steps=12
    )
    t2_dur = round(time.perf_counter() - t0, 2)
    print(f"Turn 2 completed in {t2_dur}s. Steps taken: {len(res2.get('steps', []))}")
    print(f"Tokens/sec: {res2.get('telemetry', {}).get('tokens_per_second')}")

    # Inspect what actions were taken in Turn 2
    actions_taken = [s.get("action") for s in res2.get("steps", []) if s.get("action")]
    print(f"Turn 2 Actions: {actions_taken}")
    
    # Check if app.js and index.html exist and are intact
    js_text = (proj_dir / "app.js").read_text(encoding="utf-8", errors="replace")
    html_text = (proj_dir / "index.html").read_text(encoding="utf-8", errors="replace")
    
    record("Agent Multi-Turn", "4.2 Turn 2 Workspace File Integrity Preserved", (proj_dir / "index.html").exists() and len(html_text) > 100)
    
    # Check final acceptance gate on the modified project
    h2 = validate_workspace(proj_name)
    print(f"Final Gate Status: Valid={h2.get('valid')}")
    print(f"Final Gate Summary:\n{h2.get('summary')}")
    
    # Check that app.js does not have syntax errors
    from backend.core.workspace_validator import validate_javascript_syntax
    js_valid = validate_javascript_syntax(js_text, "app.js")
    record("Agent Multi-Turn", "4.3 app.js Node.js Syntax Validity Post-Edit", js_valid.get("valid") is True, js_valid.get("error", ""))


def main():
    print("="*70)
    print("STARTING BRUTAL STRESS TEST SUITE FOR UNLEASH-AGENT")
    print("="*70)
    start_time = time.perf_counter()

    run_security_stress_tests()
    run_architecture_pipeline_tests()
    run_acceptance_gate_provenance_tests()
    run_live_agent_multiturn_stress_test()

    total_time = round(time.perf_counter() - start_time, 2)
    print("\n" + "="*70)
    print("BRUTAL STRESS TEST SUITE COMPLETE")
    print("="*70)
    print(f"Total Tests Run: {passed_count + failed_count}")
    print(f"Passed: {passed_count}")
    print(f"Failed: {failed_count}")
    print(f"Total Execution Time: {total_time}s")

    # Output detailed report JSON
    report_path = root_dir / "tests" / "stress_test_report.json"
    report_data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total": passed_count + failed_count,
        "passed": passed_count,
        "failed": failed_count,
        "duration_sec": total_time,
        "tests": results_log
    }
    report_path.write_text(json.dumps(report_data, indent=2), encoding="utf-8")
    print(f"Report written to: {report_path}")

if __name__ == "__main__":
    main()
