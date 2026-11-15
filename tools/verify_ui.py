#!/usr/bin/env python3
"""
Autonomous Headless Browser Verification Script
Evaluates web applications across Desktop & Mobile viewports,
captures console errors, failed network requests, and DOM mutations.

Part of the Playwright Browser Gate Skill (Unleash-Agent)
"""

import sys
import json
import argparse
import asyncio
from typing import Dict, Any, List

async def run_browser_verification(url: str, interactive_check: bool = True) -> Dict[str, Any]:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {
            "status": "error",
            "error": "Playwright is not installed. Run 'pip install playwright && playwright install chromium'."
        }

    results: Dict[str, Any] = {
        "status": "passed",
        "url": url,
        "viewports_checked": [],
        "console_errors": [],
        "network_errors": [],
        "interactive_checks": []
    }

    viewports = [
        {"name": "desktop", "width": 1920, "height": 1080},
        {"name": "mobile", "width": 375, "height": 812, "is_mobile": True}
    ]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        for vp in viewports:
            vp_result: Dict[str, Any] = {"viewport": vp["name"], "errors": []}
            context = await browser.new_context(
                viewport={"width": vp["width"], "height": vp["height"]},
                is_mobile=vp.get("is_mobile", False)
            )
            page = await context.new_page()

            # Attach listeners
            page.on("console", lambda msg: results["console_errors"].append({
                "viewport": vp["name"],
                "type": msg.type,
                "text": msg.text
            }) if msg.type in ["error", "warning"] else None)

            page.on("pageerror", lambda exc: results["console_errors"].append({
                "viewport": vp["name"],
                "type": "unhandled_exception",
                "text": str(exc)
            }))

            page.on("requestfailed", lambda req: results["network_errors"].append({
                "viewport": vp["name"],
                "url": req.url,
                "failure": req.failure
            }))

            try:
                response = await page.goto(url, wait_until="networkidle", timeout=12000)
                if response and response.status >= 400:
                    vp_result["errors"].append(f"HTTP Status {response.status} returned.")
            except Exception as e:
                vp_result["errors"].append(f"Navigation failed: {str(e)}")

            # Check for horizontal overflow (common mobile bug)
            try:
                has_overflow = await page.evaluate(
                    "() => document.documentElement.scrollWidth > document.documentElement.clientWidth"
                )
                if has_overflow:
                    vp_result["errors"].append("Layout defect: Horizontal scroll overflow detected.")
            except Exception:
                pass

            # Optional Interactive Element Click Check
            if interactive_check:
                try:
                    clickable = await page.query_selector("button:visible, [role='button']:visible, a:visible")
                    if clickable:
                        before_html = await page.content()
                        await clickable.click(timeout=3000)
                        await page.wait_for_timeout(500)
                        after_html = await page.content()
                        results["interactive_checks"].append({
                            "viewport": vp["name"],
                            "element": await clickable.evaluate("el => el.outerHTML.slice(0, 100)"),
                            "dom_mutated": before_html != after_html
                        })
                except Exception as click_err:
                    results["interactive_checks"].append({
                        "viewport": vp["name"],
                        "note": f"Interactive probe skipped/failed: {str(click_err)}"
                    })

            results["viewports_checked"].append(vp_result)
            await context.close()

        await browser.close()

    # Determine overall pass/fail
    has_fatal_errors = (
        len(results["console_errors"]) > 0 or
        len(results["network_errors"]) > 0 or
        any(len(vp["errors"]) > 0 for vp in results["viewports_checked"])
    )

    if has_fatal_errors:
        results["status"] = "failed"

    return results

def main():
    parser = argparse.ArgumentParser(description="Headless Multi-Viewport Browser Verification Gate")
    parser.add_argument("--url", required=True, help="Target URL or local dev server address (e.g. http://127.0.0.1:3000)")
    parser.add_argument("--interactive-check", action="store_true", default=True, help="Perform click & DOM mutation probe")
    args = parser.parse_args()

    result = asyncio.run(run_browser_verification(args.url, args.interactive_check))
    print(json.dumps(result, indent=2))

    if result.get("status") == "failed":
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
