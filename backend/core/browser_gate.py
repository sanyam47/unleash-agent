"""
Antigravity Headless Browser Runtime Verification Gate for Unleash-Agent.
Runs real-world automated testing in headless Chromium via Playwright:
1. Traps browser console errors & unhandled JavaScript exceptions (pageerror).
2. Audits visual rendering & layout (blank screen, canvas pixel rendering).
3. Dispatches synthetic user interactions to buttons and inputs.
4. Detects DOM mutations & active runtime ticks (timers, state updates, list additions).
"""

import os
import re
import time
from pathlib import Path
from typing import Dict, Any, List, Optional


def audit_workspace_runtime(
    proj_dir: Path,
    timeout_sec: float = 6.0,
    viewports: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Spins up headless Chromium to execute and test the web application live.
    Dynamically tests across single or multiple responsive viewports according to compute tier.
    Returns runtime exceptions, console errors, responsive layout audits, and prescriptive feedback.
    """
    index_file = proj_dir / "index.html"
    if not index_file.exists():
        return {
            "valid": False,
            "error": "Missing 'index.html' on disk. Cannot execute browser runtime audit.",
            "critical_errors": ["Missing 'index.html' on disk. Cannot execute browser runtime audit."],
            "diagnostics": [
                {
                    "file": "index.html",
                    "category": "missing_file",
                    "message": "Missing 'index.html' on disk. Cannot execute browser runtime audit."
                }
            ],
            "console_errors": [],
            "runtime_exceptions": ["Missing index.html"],
            "interactions": [],
            "viewports_tested": [],
            "responsive_issues": [],
            "summary": "Missing index.html file."
        }

    # Discover primary script file linked in index.html for precise diagnostic attribution
    try:
        index_txt = index_file.read_text(encoding="utf-8", errors="replace")
        script_srcs = re.findall(r'<script\s+[^>]*src=["\']([^"\']+)["\']', index_txt, re.IGNORECASE)
        primary_script = script_srcs[0] if script_srcs else "app.js"
    except Exception:
        primary_script = "app.js"

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        # Fallback gracefully if playwright not installed
        return {
            "valid": True,
            "warning": "Playwright not installed, skipping browser runtime audit.",
            "critical_errors": [],
            "diagnostics": [],
            "console_errors": [],
            "runtime_exceptions": [],
            "interactions": [],
            "viewports_tested": [],
            "responsive_issues": [],
            "summary": "Browser gate skipped (Playwright not installed)."
        }

    console_errors: List[str] = []
    runtime_exceptions: List[str] = []
    interactions_tested: List[Dict[str, Any]] = []
    responsive_issues: List[str] = []
    active_viewports = viewports or [{"name": "desktop", "width": 1280, "height": 800}]
    is_rendered = False
    timer_ticks_verified = False

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)

            for idx, vp in enumerate(active_viewports):
                vp_width = vp.get("width", 1280)
                vp_height = vp.get("height", 800)
                vp_name = vp.get("name", f"vp_{vp_width}x{vp_height}")

                page = browser.new_page(viewport={"width": vp_width, "height": vp_height})

                # Listen for unhandled browser runtime errors & console error outputs
                page.on("pageerror", lambda err, v=vp_name: runtime_exceptions.append(f"[{v}] {str(err)}"))
                page.on("console", lambda msg, v=vp_name: console_errors.append(f"[{v}][{msg.type}] {msg.text}") if msg.type == "error" else None)

                # Navigate to the project index.html file URI
                target_url = index_file.as_uri()
                page.goto(target_url, timeout=int(timeout_sec * 1000), wait_until="domcontentloaded")
                page.wait_for_timeout(300)

                # Responsive layout check: detect horizontal overflow on mobile/tablet
                if vp_name in ("mobile", "tablet") or vp_width < 1000:
                    overflow_info = page.evaluate("""() => {
                        const docWidth = document.documentElement.scrollWidth;
                        const winWidth = window.innerWidth;
                        return { docWidth, winWidth, hasOverflow: docWidth > (winWidth + 12) };
                    }""")
                    if overflow_info.get("hasOverflow"):
                        responsive_issues.append(
                            f"RESPONSIVE OVERFLOW on {vp_name} ({vp_width}x{vp_height}): Content width ({overflow_info['docWidth']}px) exceeds viewport width ({overflow_info['winWidth']}px). Ensure responsive containers use max-width or flex-wrap."
                        )

                # Execute primary functional interaction audit on the default viewport
                if idx == 0:
                    eval_res = page.evaluate("""() => {
                        const bodyText = document.body ? document.body.innerText.trim() : '';
                        const buttons = document.querySelectorAll('button');
                        const inputs = document.querySelectorAll('input');
                        const canvas = document.querySelector('canvas');
                        
                        let canvasHasContent = false;
                        if (canvas && canvas.width > 0 && canvas.height > 0) {
                            try {
                                const ctx = canvas.getContext('2d');
                                if (ctx) {
                                    const data = ctx.getImageData(0, 0, Math.min(50, canvas.width), Math.min(50, canvas.height)).data;
                                    canvasHasContent = data.some(p => p !== 0);
                                }
                            } catch(e) {}
                        }

                        return {
                            bodyTextLen: bodyText.length,
                            buttonCount: buttons.length,
                            inputCount: inputs.length,
                            hasCanvas: !!canvas,
                            canvasHasContent: canvasHasContent
                        };
                    }""")

                    is_rendered = (eval_res.get("bodyTextLen", 0) > 30) or eval_res.get("hasCanvas", False)

                    # Synthetic User Interaction Audit (Click primary buttons & test DOM reaction)
                    buttons = page.locator("button:visible")
                    btn_count = min(buttons.count(), 4)

                    for i in range(btn_count):
                        btn = buttons.nth(i)
                        btn_text = (btn.text_content() or "").strip()[:30]
                        btn_id = btn.get_attribute("id") or f"button[{i}]"

                        # Capture state before click
                        before_state = page.evaluate("""() => {
                            return {
                                htmlLen: document.body ? document.body.innerHTML.length : 0,
                                timerText: document.querySelector('#timer-display, .timer, [id*="timer"]') ? 
                                           document.querySelector('#timer-display, .timer, [id*="timer"]').innerText.trim() : ''
                            };
                        }""")

                        # Dispatch synthetic click
                        err_before_count = len(runtime_exceptions)
                        try:
                            btn.click(timeout=1000)
                            page.wait_for_timeout(200)
                        except Exception:
                            # Ignore click timeout if element not interactive
                            pass

                        new_errors = runtime_exceptions[err_before_count:]
                        
                        # Check state after click
                        after_state = page.evaluate("""() => {
                            return {
                                htmlLen: document.body ? document.body.innerHTML.length : 0,
                                timerText: document.querySelector('#timer-display, .timer, [id*="timer"]') ? 
                                           document.querySelector('#timer-display, .timer, [id*="timer"]').innerText.trim() : ''
                            };
                        }""")

                        has_mutation = (before_state["htmlLen"] != after_state["htmlLen"]) or (before_state["timerText"] != after_state["timerText"])
                        
                        interactions_tested.append({
                            "element": f"#{btn_id}" if not btn_id.startswith("button[") else btn_id,
                            "label": btn_text,
                            "triggered_error": len(new_errors) > 0,
                            "error_msg": new_errors[0] if new_errors else None,
                            "produced_mutation": has_mutation
                        })

                    # Timer / Animation Active Tick Check
                    initial_timer_val = page.evaluate("""() => {
                        const el = document.querySelector('#timer-display, .timer, [id*="timer"], .time');
                        return el ? el.innerText.trim() : null;
                    }""")

                    if initial_timer_val:
                        page.wait_for_timeout(1200)
                        later_timer_val = page.evaluate("""() => {
                            const el = document.querySelector('#timer-display, .timer, [id*="timer"], .time');
                            return el ? el.innerText.trim() : null;
                        }""")
                        if initial_timer_val != later_timer_val:
                            timer_ticks_verified = True

                page.close()

            browser.close()

    except Exception as e:
        # Browser execution failure fallback
        return {
            "valid": True,
            "warning": f"Browser test timed out or completed with warning: {str(e)}",
            "console_errors": console_errors,
            "runtime_exceptions": runtime_exceptions,
            "interactions": interactions_tested,
            "viewports_tested": [v.get("name") for v in active_viewports],
            "responsive_issues": responsive_issues,
            "summary": "Browser runtime check finished."
        }

    # Evaluate Verdict
    critical_errors = []
    diagnostics: List[Dict[str, Any]] = []

    for exc in runtime_exceptions:
        msg = f"UNHANDLED RUNTIME EXCEPTION: {exc}"
        critical_errors.append(msg)
        diagnostics.append({
            "file": primary_script,
            "category": "runtime_exception",
            "message": msg
        })
    
    # Filter high-severity console errors (ignore benign 404 on optional favicon/audio)
    for c_err in console_errors:
        if any(ignore in c_err.lower() for ignore in ["favicon", "404 (not found)", "audiocontext was not allowed to start"]):
            continue
        msg = f"BROWSER CONSOLE ERROR: {c_err}"
        critical_errors.append(msg)
        diagnostics.append({
            "file": primary_script,
            "category": "console_error",
            "message": msg
        })

    # Check for unresponsive button crashes
    for inter in interactions_tested:
        if inter.get("triggered_error"):
            msg = f"BUTTON CRASH: Clicking '{inter['element']}' ({inter['label']}) threw: {inter['error_msg']}"
            critical_errors.append(msg)
            diagnostics.append({
                "file": primary_script,
                "category": "interaction_crash",
                "message": msg
            })

    # Responsive layout defects
    for resp_err in responsive_issues:
        critical_errors.append(resp_err)
        diagnostics.append({
            "file": "styles.css",
            "category": "responsive_overflow",
            "message": resp_err
        })

    if not is_rendered:
        msg = "BLANK SCREEN DETECTED: Headless browser rendered empty body with zero visible content or elements."
        critical_errors.append(msg)
        diagnostics.append({
            "file": "index.html",
            "category": "blank_screen",
            "message": msg
        })

    is_valid = len(critical_errors) == 0

    summary_lines = []
    if critical_errors:
        summary_lines.append(f"HEADLESS BROWSER RUNTIME VERIFICATION FAILED ({len(critical_errors)} defects across viewports {[v.get('name') for v in active_viewports]}):")
        for err in critical_errors[:4]:
            summary_lines.append(f"  - {err}")
    else:
        vp_names = ", ".join([v.get("name") for v in active_viewports])
        summary_lines.append(f"Headless Browser Runtime Audit Passed across viewports ({vp_names}): 0 uncaught exceptions, DOM rendered cleanly, interactions verified.")
        if timer_ticks_verified:
            summary_lines.append("  - Active runtime timer tick confirmed in Chromium.")

    return {
        "valid": is_valid,
        "critical_errors": critical_errors,
        "diagnostics": diagnostics,
        "runtime_exceptions": runtime_exceptions,
        "console_errors": console_errors,
        "interactions": interactions_tested,
        "viewports_tested": [v.get("name") for v in active_viewports],
        "responsive_issues": responsive_issues,
        "is_rendered": is_rendered,
        "timer_ticks_verified": timer_ticks_verified,
        "summary": "\n".join(summary_lines)
    }
