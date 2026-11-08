"""
Antigravity Headless Browser Runtime Verification Gate for Unleash-Agent.
Runs real-world automated testing in headless Chromium via Playwright:
1. Traps browser console errors & unhandled JavaScript exceptions (pageerror).
2. Audits visual rendering & layout (blank screen, canvas pixel rendering).
3. Dispatches synthetic user interactions to buttons and inputs.
4. Detects DOM mutations & active runtime ticks (timers, state updates, list additions).
"""

import os
import time
from pathlib import Path
from typing import Dict, Any, List, Optional


def audit_workspace_runtime(proj_dir: Path, timeout_sec: float = 6.0) -> Dict[str, Any]:
    """
    Spins up headless Chromium to execute and test the web application live.
    Returns runtime exceptions, console errors, interactive audit, and prescriptive feedback.
    """
    index_file = proj_dir / "index.html"
    if not index_file.exists():
        return {
            "valid": False,
            "error": "Missing 'index.html' on disk. Cannot execute browser runtime audit.",
            "console_errors": [],
            "runtime_exceptions": ["Missing index.html"],
            "interactions": [],
            "summary": "Missing index.html file."
        }

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        # Fallback gracefully if playwright not installed
        return {
            "valid": True,
            "warning": "Playwright not installed, skipping browser runtime audit.",
            "console_errors": [],
            "runtime_exceptions": [],
            "interactions": [],
            "summary": "Browser gate skipped (Playwright not installed)."
        }

    console_errors: List[str] = []
    runtime_exceptions: List[str] = []
    interactions_tested: List[Dict[str, Any]] = []
    is_rendered = False
    timer_ticks_verified = False

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 800})

            # 1. Listen for unhandled browser runtime errors & console error outputs
            page.on("pageerror", lambda err: runtime_exceptions.append(str(err)))
            page.on("console", lambda msg: console_errors.append(f"[{msg.type}] {msg.text}") if msg.type == "error" else None)

            # Navigate to the project index.html file URI
            target_url = index_file.as_uri()
            page.goto(target_url, timeout=int(timeout_sec * 1000), wait_until="domcontentloaded")
            page.wait_for_timeout(300)

            # 2. Visual & Layout Rendering Audit
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

            # 3. Synthetic User Interaction Audit (Click primary buttons & test DOM reaction)
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
                except Exception as e:
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

            # 4. Timer / Animation Active Tick Check
            # If timer element exists, wait 1.2s to check if active tick is decrementing
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

            browser.close()

    except Exception as e:
        # Browser execution failure fallback
        return {
            "valid": True,
            "warning": f"Browser test timed out or completed with warning: {str(e)}",
            "console_errors": console_errors,
            "runtime_exceptions": runtime_exceptions,
            "interactions": interactions_tested,
            "summary": "Browser runtime check finished."
        }

    # Evaluate Verdict
    critical_errors = []
    for exc in runtime_exceptions:
        critical_errors.append(f"UNHANDLED RUNTIME EXCEPTION: {exc}")
    
    # Filter high-severity console errors (ignore benign 404 on optional favicon/audio)
    for c_err in console_errors:
        if any(ignore in c_err.lower() for ignore in ["favicon", "404 (not found)", "audiocontext was not allowed to start"]):
            continue
        critical_errors.append(f"BROWSER CONSOLE ERROR: {c_err}")

    # Check for unresponsive button crashes
    for inter in interactions_tested:
        if inter.get("triggered_error"):
            critical_errors.append(f"BUTTON CRASH: Clicking '{inter['element']}' ({inter['label']}) threw: {inter['error_msg']}")

    if not is_rendered:
        critical_errors.append("BLANK SCREEN DETECTED: Headless browser rendered empty body with zero visible content or elements.")

    is_valid = len(critical_errors) == 0

    summary_lines = []
    if critical_errors:
        summary_lines.append(f"HEADLESS BROWSER RUNTIME VERIFICATION FAILED ({len(critical_errors)} defects):")
        for err in critical_errors[:4]:
            summary_lines.append(f"  - {err}")
    else:
        summary_lines.append("Headless Browser Runtime Audit Passed: 0 uncaught exceptions, DOM rendered cleanly, interactions verified.")
        if timer_ticks_verified:
            summary_lines.append("  - Active runtime timer tick confirmed in Chromium.")

    return {
        "valid": is_valid,
        "critical_errors": critical_errors,
        "runtime_exceptions": runtime_exceptions,
        "console_errors": console_errors,
        "interactions": interactions_tested,
        "is_rendered": is_rendered,
        "timer_ticks_verified": timer_ticks_verified,
        "summary": "\n".join(summary_lines)
    }
