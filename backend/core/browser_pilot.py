"""
Unleash Jarvis Phase 2: Autonomous Live Browser Pilot & Web Navigator
Built on Playwright with resilient Windows channel fallbacks (Chrome -> Edge -> Chromium).

Empowers Unleash with real web navigation and computer use:
  1. Headless / Headed Web Browsing (`browser_navigate`)
  2. Dynamic DOM Interaction (`browser_click`, `browser_type_text`)
  3. Clean Readability & Structured Data Extraction (`browser_extract_text`)
  4. High-Resolution Visual Page Screenshots (`browser_capture_screenshot`)
  5. Autonomous Multi-Source Deep Search & Reader (`browser_search_and_read`)
"""

import os
import re
import time
import base64
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger("unleash.browser_pilot")

# Screenshot, profile, and download staging directories
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SCREENSHOTS_DIR = DATA_DIR / "browser_screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
PROFILE_DIR = DATA_DIR / "browser_profile"
PROFILE_DIR.mkdir(parents=True, exist_ok=True)


class BrowserSessionManager:
    """
    Stateful Singleton managing the live Playwright browser context.
    Allows multi-step agent actions (Navigate -> Click -> Fill -> Extract)
    across turns without re-launching the browser from scratch each time.
    """
    _instance: Optional["BrowserSessionManager"] = None
    _playwright = None
    _browser = None
    _context = None
    _page = None
    _last_active: float = 0.0
    _is_headless: bool = False

    @classmethod
    def get_instance(cls) -> "BrowserSessionManager":
        if cls._instance is None:
            cls._instance = BrowserSessionManager()
        return cls._instance

    def _ensure_browser(self, headless: bool = False):
        """Initializes or reuses the browser session (persistent profile when visible)."""
        now = time.time()
        # If running in a different headless state or session timed out (>10 min), recycle
        if self._context is not None or self._browser is not None:
            if self._is_headless != headless or (now - self._last_active > 600):
                self.close()

        if self._playwright is None:
            from playwright.sync_api import sync_playwright
            self._playwright = sync_playwright().start()

        if self._context is None:
            channels = ["chrome", "msedge", None]
            launched = False
            last_err = None
            launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]

            for ch in channels:
                try:
                    if not headless:
                        # Visible interactive mode: use persistent profile so logins (GitHub, WhatsApp Web, etc.) persist
                        kwargs: Dict[str, Any] = {
                            "user_data_dir": str(PROFILE_DIR),
                            "headless": False,
                            "viewport": {"width": 1280, "height": 800},
                            "args": launch_args,
                        }
                        if ch:
                            kwargs["channel"] = ch
                        self._context = self._playwright.chromium.launch_persistent_context(**kwargs)
                        self._browser = None
                    else:
                        kwargs = {"headless": True, "args": launch_args}
                        if ch:
                            kwargs["channel"] = ch
                        self._browser = self._playwright.chromium.launch(**kwargs)
                        self._context = self._browser.new_context(
                            viewport={"width": 1280, "height": 800},
                            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                        )
                    self._is_headless = headless
                    launched = True
                    break
                except Exception as e:
                    last_err = e
                    continue

            if not launched:
                raise RuntimeError(f"Failed to launch Chrome or Edge via Playwright: {last_err}")

        if self._page is None or self._page.is_closed():
            existing_pages = self._context.pages if hasattr(self._context, "pages") else []
            self._page = existing_pages[0] if existing_pages else self._context.new_page()
            self._page.set_default_timeout(15000)
            try:
                self._page.on("dialog", lambda d: d.dismiss())
            except Exception:
                pass

        self._last_active = time.time()
        return self._page

    def _get_interactive_elements(self, limit: int = 16) -> List[Dict[str, str]]:
        """Extracts a compact list of visible interactive inputs, buttons, and links with usable selectors."""
        if not self._page:
            return []
        try:
            return self._page.evaluate(
                """(maxItems) => {
                    const out = [];
                    const seen = new Set();
                    const els = document.querySelectorAll('input, textarea, button, [role="button"], a[href]');
                    for (const el of els) {
                        if (out.length >= maxItems) break;
                        const rect = el.getBoundingClientRect();
                        if (rect.width < 8 || rect.height < 8) continue;
                        const tag = el.tagName.toLowerCase();
                        const type = (el.getAttribute('type') || '').toLowerCase();
                        if (tag === 'input' && type === 'hidden') continue;
                        const text = (el.innerText || el.value || el.getAttribute('placeholder') || el.getAttribute('aria-label') || '').replace(/\\s+/g, ' ').trim().slice(0, 50);
                        if (!text && tag === 'a') continue;
                        let sel = '';
                        if (el.id) sel = '#' + CSS.escape(el.id);
                        else if (el.getAttribute('name')) sel = `${tag}[name="${el.getAttribute('name')}"]`;
                        else if (el.getAttribute('aria-label')) sel = `${tag}[aria-label="${el.getAttribute('aria-label').replace(/"/g, '\\\\"')}"]`;
                        else if (el.getAttribute('placeholder')) sel = `${tag}[placeholder="${el.getAttribute('placeholder').replace(/"/g, '\\\\"')}"]`;
                        else if (text) sel = `text=${text}`;
                        if (!sel || seen.has(sel)) continue;
                        seen.add(sel);
                        out.push({ tag, label: text || tag, selector: sel });
                    }
                    return out;
                }""",
                limit,
            ) or []
        except Exception:
            return []

    def navigate(self, url: str, headless: bool = False) -> Dict[str, Any]:
        """Navigates current browser page to the specified URL."""
        clean_url = str(url or "").strip()
        if not clean_url.startswith(("http://", "https://", "data:", "file://")):
            clean_url = "https://" + clean_url

        try:
            page = self._ensure_browser(headless=headless)
            start_t = time.perf_counter()
            resp = page.goto(clean_url, wait_until="domcontentloaded", timeout=20000)
            elapsed = round(time.perf_counter() - start_t, 2)

            title = page.title()
            status_code = resp.status if resp else 200

            try:
                body_text = page.inner_text("body", timeout=3000)[:500]
                body_clean = re.sub(r'\s+', ' ', body_text).strip()
            except Exception:
                body_clean = ""

            elements = self._get_interactive_elements(limit=16)

            return {
                "status": "success",
                "action": "navigate",
                "url": page.url,
                "title": title,
                "http_status": status_code,
                "elapsed_sec": elapsed,
                "snippet": body_clean,
                "interactive_elements": elements,
                "message": f"Navigated to '{title}' ({page.url}) in {elapsed}s"
            }
        except Exception as e:
            return {"status": "error", "error": f"Failed to navigate to '{clean_url}': {str(e)}"}

    def click(self, selector: str, text: Optional[str] = None) -> Dict[str, Any]:
        """Clicks an element by CSS selector or visible text anchor."""
        if not self._page:
            return {"status": "error", "error": "No active browser page. Call 'browser_navigate' first."}

        self._last_active = time.time()
        try:
            target = selector
            if text and not selector:
                target = f"text={text}"
            elif text and selector:
                target = f"{selector}:has-text('{text}')"

            self._page.wait_for_selector(target, timeout=8000)
            self._page.click(target)
            time.sleep(0.5)

            return {
                "status": "success",
                "action": "click",
                "target": target,
                "new_url": self._page.url,
                "new_title": self._page.title(),
                "interactive_elements": self._get_interactive_elements(limit=16),
                "message": f"Successfully clicked element '{target}'. Current page: '{self._page.title()}'"
            }
        except Exception as e:
            return {"status": "error", "error": f"Failed to click '{selector or text}': {str(e)}"}

    def type_text(self, selector: str, text: str, press_enter: bool = False, clear_first: bool = True) -> Dict[str, Any]:
        """Fills text into an input field or search bar."""
        if not self._page:
            return {"status": "error", "error": "No active browser page. Call 'browser_navigate' first."}

        self._last_active = time.time()
        try:
            self._page.wait_for_selector(selector, timeout=8000)
            if clear_first:
                self._page.fill(selector, "")
            self._page.type(selector, text, delay=20)
            
            if press_enter:
                self._page.press(selector, "Enter")
                time.sleep(1.0)

            res = {
                "status": "success",
                "action": "type_text",
                "selector": selector,
                "text_entered": text,
                "pressed_enter": press_enter,
                "current_url": self._page.url,
                "message": f"Typed '{text}' into '{selector}'" + (" and submitted Enter." if press_enter else ".")
            }
            if press_enter:
                res["interactive_elements"] = self._get_interactive_elements(limit=16)
            return res
        except Exception as e:
            return {"status": "error", "error": f"Failed to type text into '{selector}': {str(e)}"}

    def scroll(self, direction: str = "down", amount: int = 800) -> Dict[str, Any]:
        """Scrolls the current active web page up or down, or to top/bottom."""
        if not self._page:
            return {"status": "error", "error": "No active browser page. Call 'browser_navigate' first."}

        self._last_active = time.time()
        try:
            d_lower = str(direction or "down").lower()
            if d_lower in ("bottom", "end"):
                self._page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            elif d_lower in ("top", "start"):
                self._page.evaluate("window.scrollTo(0, 0)")
            else:
                sign = 1 if d_lower in ("down", "next") else -1
                self._page.evaluate(f"window.scrollBy(0, {sign * abs(int(amount or 800))})")

            time.sleep(0.4)
            return {
                "status": "success",
                "action": "scroll",
                "direction": d_lower,
                "amount": amount,
                "current_url": self._page.url,
                "message": f"Scrolled {d_lower} on '{self._page.title()}'"
            }
        except Exception as e:
            return {"status": "error", "error": f"Failed to scroll: {str(e)}"}

    def extract_text(self, selector: Optional[str] = None, max_chars: int = 4000) -> Dict[str, Any]:
        """Extracts clean human-readable text from the active web page."""
        if not self._page:
            return {"status": "error", "error": "No active browser page. Call 'browser_navigate' first."}

        self._last_active = time.time()
        try:
            target = selector or "body"
            raw_text = self._page.inner_text(target, timeout=5000)
            
            # Clean excessive whitespaces and blank lines
            lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
            cleaned_text = "\n".join(lines)[:max_chars]

            # Extract major links on page for follow-up navigation
            links = []
            try:
                link_elements = self._page.query_selector_all("a[href]")
                for a in link_elements[:15]:
                    h = a.get_attribute("href")
                    t = (a.inner_text() or "").strip()
                    if h and t and not h.startswith(("javascript:", "#")):
                        links.append({"text": t[:40], "href": h})
            except Exception:
                pass

            return {
                "status": "success",
                "action": "extract_text",
                "title": self._page.title(),
                "url": self._page.url,
                "content": cleaned_text,
                "total_chars": len(cleaned_text),
                "top_links": links[:8],
                "message": f"Extracted {len(cleaned_text)} characters from '{self._page.title()}'"
            }
        except Exception as e:
            return {"status": "error", "error": f"Failed to extract text: {str(e)}"}

    def capture_screenshot(self, filename: Optional[str] = None, full_page: bool = False) -> Dict[str, Any]:
        """Captures a PNG screenshot of the current page and stores it in data/browser_screenshots."""
        if not self._page:
            return {"status": "error", "error": "No active browser page. Call 'browser_navigate' first."}

        self._last_active = time.time()
        try:
            ts = int(time.time())
            safe_fname = filename or f"screenshot_{ts}.png"
            if not safe_fname.lower().endswith(".png"):
                safe_fname += ".png"

            out_path = SCREENSHOTS_DIR / safe_fname
            self._page.screenshot(path=str(out_path), full_page=full_page)

            # Generate base64 thumbnail for fast frontend/VLM consumption
            b64_str = None
            try:
                with open(out_path, "rb") as img_f:
                    b64_str = base64.b64encode(img_f.read()).decode("utf-8")
            except Exception:
                pass

            return {
                "status": "success",
                "action": "screenshot",
                "file_path": str(out_path),
                "filename": safe_fname,
                "page_title": self._page.title(),
                "page_url": self._page.url,
                "has_base64": b64_str is not None,
                "message": f"Captured screenshot to '{out_path.name}' ({self._page.title()})"
            }
        except Exception as e:
            return {"status": "error", "error": f"Failed to capture screenshot: {str(e)}"}

    def search_and_read(self, query: str, num_results: int = 3) -> Dict[str, Any]:
        """
        Autonomous search and content synthesis pipeline:
        1. Queries DuckDuckGo / Bing without bot blocks
        2. Inspects top result snippets & target links
        3. Navigates to the top result and extracts full article text
        """
        clean_q = str(query or "").strip()
        if not clean_q:
            return {"status": "error", "error": "Query cannot be empty."}

        search_url = f"https://html.duckduckgo.com/html/?q={clean_q.replace(' ', '+')}"
        nav_res = self.navigate(search_url, headless=True)
        if nav_res.get("status") == "error":
            return nav_res

        # Extract top search results
        results = []
        try:
            assert self._page is not None
            links = self._page.query_selector_all(".result__snippet")
            titles = self._page.query_selector_all(".result__title .result__url")
            anchors = self._page.query_selector_all(".result__title a")

            for i in range(min(num_results, len(anchors))):
                title_txt = anchors[i].inner_text().strip()
                href = anchors[i].get_attribute("href") or ""
                snippet = links[i].inner_text().strip() if i < len(links) else ""
                
                # Unwrap duckduckgo redirection url if needed
                if "uddg=" in href:
                    import urllib.parse
                    parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                    real_href = parsed.get("uddg", [href])[0]
                else:
                    real_href = href

                if real_href and not real_href.startswith("/"):
                    results.append({
                        "rank": i + 1,
                        "title": title_txt,
                        "url": real_href,
                        "snippet": snippet
                    })
        except Exception as e:
            logger.warning(f"Error parsing search snippets: {e}")

        # Auto-visit top result if available
        first_article_text = ""
        top_visited_url = ""
        if results:
            first_url = results[0]["url"]
            top_visited_url = first_url
            try:
                self.navigate(first_url, headless=True)
                ext = self.extract_text(max_chars=2500)
                first_article_text = ext.get("content", "")
            except Exception:
                pass

        return {
            "status": "success",
            "action": "search_and_read",
            "query": clean_q,
            "results_found": len(results),
            "top_results": results,
            "visited_top_url": top_visited_url,
            "article_summary": first_article_text[:2000] if first_article_text else (results[0]["snippet"] if results else ""),
            "message": f"Discovered {len(results)} authoritative sources for '{clean_q}'. Read top source: {top_visited_url}"
        }

    def close(self):
        """Cleanly releases browser, page, and playwright resources."""
        try:
            if self._page:
                self._page.close()
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass
        finally:
            self._page = None
            self._context = None
            self._browser = None
            self._playwright = None


# Module-level convenience functions for tool dispatcher
def browser_navigate(url: str, headless: bool = False) -> Dict[str, Any]:
    return BrowserSessionManager.get_instance().navigate(url, headless=headless)

def browser_click(selector: str, text: Optional[str] = None) -> Dict[str, Any]:
    return BrowserSessionManager.get_instance().click(selector, text=text)

def browser_type(selector: str, text: str, press_enter: bool = False) -> Dict[str, Any]:
    return BrowserSessionManager.get_instance().type_text(selector, text, press_enter=press_enter)

def browser_extract(selector: Optional[str] = None, max_chars: int = 4000) -> Dict[str, Any]:
    return BrowserSessionManager.get_instance().extract_text(selector=selector, max_chars=max_chars)

def browser_screenshot(filename: Optional[str] = None, full_page: bool = False) -> Dict[str, Any]:
    return BrowserSessionManager.get_instance().capture_screenshot(filename=filename, full_page=full_page)

def browser_scroll(direction: str = "down", amount: int = 800) -> Dict[str, Any]:
    return BrowserSessionManager.get_instance().scroll(direction=direction, amount=amount)

def browser_search_and_read(query: str, num_results: int = 3) -> Dict[str, Any]:
    return BrowserSessionManager.get_instance().search_and_read(query, num_results=num_results)

def browser_close() -> Dict[str, Any]:
    BrowserSessionManager.get_instance().close()
    return {"status": "success", "message": "Browser session closed."}
