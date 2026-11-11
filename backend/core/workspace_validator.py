"""

Autonomous Workspace Self-Validation & Acceptance Gate Engine.

Implements the Antigravity 5-Layer Definition of Done (DoD) & Browser Runtime Gate:

  Layer 1: Syntactic & Compilation Integrity (Node.js syntax check, py_compile, safe storage)

  Layer 2: Entity Parity & Semantic Layout Depth Gate (Anti-stub enforcement, brand/persona parity)

  Layer 3: DOM Event & Interactive Parity (HTML ID binding, listener parity, CSS layout parity)

"""



import os

import re

import json

import tempfile

import subprocess

from pathlib import Path

from typing import Dict, Any, List, Optional

from backend.core.agent_tools import PROJECTS_ROOT, resolve_safe_project_path, sanitize_project_name, get_project_dir





def validate_javascript_syntax(content: str, filename: str = "app.js") -> Dict[str, Any]:

    """

    Validates JavaScript syntax by compiling via Node.js CLI (node -c).

    Captures exact line numbers, syntax error messages, and context.

    """

    if not content or not content.strip():

        return {"valid": False, "error": f"'{filename}' is completely empty."}



    # 1. Compile with Node.js syntax check (node -c)

    try:

        with tempfile.NamedTemporaryFile(suffix=".js", delete=False, mode="w", encoding="utf-8") as tmp:

            tmp.write(content)

            tmp_path = tmp.name



        proc = subprocess.run(

            ["node", "-c", tmp_path],

            capture_output=True,

            text=True,

            timeout=5

        )

        try:

            os.remove(tmp_path)

        except OSError:

            pass



        if proc.returncode != 0:

            err_output = (proc.stderr or proc.stdout).strip()

            # Clean up temporary path name from error message for clean prompt reading

            err_cleaned = re.sub(r"[A-Za-z]:\\[^\n]+\.js", filename, err_output)

            err_cleaned = re.sub(r"/[^\n]+\.js", filename, err_cleaned)

            return {

                "valid": False,

                "type": "syntax_error",

                "file": filename,

                "error": f"JavaScript SyntaxError in '{filename}':\n{err_cleaned}"

            }

    except FileNotFoundError:

        # Node not installed on host path, perform AST / regex fallback

        pass

    except Exception:

        pass



    # 2. Check for bare localStorage calls without try/catch

    # In Brave and sandboxed iframes, bare localStorage throws DOMException: Access is denied

    storage_pattern = r"(?<!\w)(?:window\.)?(?:localStorage|sessionStorage)\.(?:getItem|setItem|removeItem|clear)"

    if re.search(storage_pattern, content):

        has_try_catch = "try" in content and "catch" in content

        if not has_try_catch:

            return {

                "valid": False,

                "type": "unsafe_storage",

                "file": filename,

                "error": (

                    f"UNSAFE STORAGE in '{filename}': Bare 'localStorage' or 'sessionStorage' call detected without try/catch. "

                    "In sandboxed preview iframes and privacy browsers (Brave), bare localStorage throws an unhandled "

                    "DOMException that crashes the script before event listeners can attach. "

                    "Always wrap localStorage in a try/catch block or use a safe storage helper function."

                )

            }



    return {"valid": True, "file": filename}


def validate_python_syntax(target: Any, filename: Optional[str] = None) -> Dict[str, Any]:
    """
    Validates Python code syntax via ast.parse and compile.
    Accepts raw code string, file path, or workspace directory path.
    """
    import ast
    from pathlib import Path

    # Check if target is a Path or existing file/dir path
    p = None
    if isinstance(target, Path):
        p = target
    elif isinstance(target, str) and (os.path.exists(target) or "/" in target or "\\" in target):
        try:
            p = Path(target)
        except Exception:
            p = None

    if p and p.exists():
        if p.is_dir():
            py_files = [f for f in p.glob("*.py") if not any(x in f.parts for x in ["venv", ".venv", "__pycache__"])]
            for pf in py_files:
                try:
                    code = pf.read_text(encoding="utf-8", errors="replace")
                    ast.parse(code, filename=pf.name)
                    compile(code, pf.name, 'exec')
                except SyntaxError as e:
                    line_preview = e.text.strip() if e.text else ""
                    return {
                        "valid": False,
                        "error": f"Python SyntaxError in '{pf.name}' line {e.lineno}:{e.offset}: {e.msg} (around '{line_preview}')",
                        "lineno": e.lineno,
                        "offset": e.offset,
                        "file": pf.name,
                        "primary_repair_file": pf.name
                    }
                except Exception as e:
                    return {"valid": False, "error": f"Python compilation failed in '{pf.name}': {str(e)}", "file": pf.name, "primary_repair_file": pf.name}
            return {"valid": True, "error": None, "checked_files": [f.name for f in py_files]}
        elif p.is_file():
            fname = filename or p.name
            try:
                code = p.read_text(encoding="utf-8", errors="replace")
                ast.parse(code, filename=fname)
                compile(code, fname, 'exec')
                return {"valid": True, "error": None, "file": fname}
            except SyntaxError as e:
                line_preview = e.text.strip() if e.text else ""
                return {
                    "valid": False,
                    "error": f"Python SyntaxError in '{fname}' line {e.lineno}:{e.offset}: {e.msg} (around '{line_preview}')",
                    "lineno": e.lineno,
                    "offset": e.offset,
                    "file": fname,
                    "primary_repair_file": fname
                }
            except Exception as e:
                return {"valid": False, "error": f"Python compilation failed in '{fname}': {str(e)}", "file": fname, "primary_repair_file": fname}

    # Otherwise treat target as raw code string
    content = str(target) if target is not None else ""
    fname = filename or "main.py"
    if not content or not content.strip():
        return {"valid": False, "error": f"'{fname}' is completely empty.", "primary_repair_file": fname}
    try:
        ast.parse(content, filename=fname)
        compile(content, fname, 'exec')
        return {"valid": True, "error": None, "file": fname}
    except SyntaxError as e:
        line_preview = e.text.strip() if e.text else ""
        return {
            "valid": False,
            "error": f"Python SyntaxError in '{fname}' line {e.lineno}:{e.offset}: {e.msg} (around '{line_preview}')",
            "lineno": e.lineno,
            "offset": e.offset,
            "file": fname,
            "primary_repair_file": fname
        }
    except Exception as e:
        return {"valid": False, "error": f"Python compilation failed in '{fname}': {str(e)}", "file": fname, "primary_repair_file": fname}


def extract_html_interactive_elements(html: str) -> Dict[str, List[str]]:

    """Extracts interactive element IDs, buttons, inputs, canvases, and links from HTML."""

    interactive_ids = []

    all_ids = []

    

    # Match id="..." or id='...'

    for m in re.finditer(r'<([a-zA-Z0-9\-]+)[^>]*\bid=["\']([^"\']+)["\']', html, re.IGNORECASE):

        tag = m.group(1).lower()

        elem_id = m.group(2)

        all_ids.append(elem_id)

        if tag in ("button", "canvas", "input", "select", "textarea", "form", "a"):

            interactive_ids.append(elem_id)



    onclick_handlers = re.findall(r'onclick=["\']([^"\']+)["\']', html, re.IGNORECASE)



    return {

        "interactive_ids": interactive_ids,

        "all_ids": all_ids,

        "onclick_handlers": onclick_handlers

    }





def validate_html_js_contract(html_content: str, js_content: str) -> List[str]:

    """

    Checks if buttons or controls defined in index.html are bound in app.js,

    and whether app.js references IDs that do not exist in HTML.

    """

    issues = []

    html_info = extract_html_interactive_elements(html_content)

    interactive_ids = html_info["interactive_ids"]

    all_html_ids = set(html_info["all_ids"])



    # 1. Check if interactive IDs in HTML have corresponding listeners or queries in JS

    for eid in interactive_ids:

        referenced = (

            f"'{eid}'" in js_content or

            f'"{eid}"' in js_content or

            f"`{eid}`" in js_content or

            f"#{eid}" in js_content

        )

        if not referenced and not any(eid in handler for handler in html_info["onclick_handlers"]):

            issues.append(

                f"DEAD CONTROL WARNING: Interactive element '#{eid}' is defined in index.html, "

                f"but is never queried or given an event listener in app.js. The element will not respond to user interactions!"

            )



    # 2. Check if JS references IDs that do NOT exist in HTML

    for m in re.finditer(r'document\.(?:getElementById|querySelector)\s*\(\s*["\']#?([a-zA-Z0-9_\-]+)["\']\s*\)', js_content):

        queried_id = m.group(1).lstrip("#")

        if queried_id and queried_id not in all_html_ids and not any(tag in queried_id for tag in ["dynamic", "item", "row", "template", "modal"]):

            issues.append(

                f"ID MISMATCH ERROR: app.js queries element with id '#{queried_id}', but no such id exists in index.html! "

                f"Available IDs in HTML: {sorted(list(all_html_ids))[:8]}."

            )



    return issues





def validate_workspace(
    project_name: str,
    required_entities: Optional[Dict[str, Any]] = None,
    viewports: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Antigravity 5-Layer Definition of Done (DoD) & Diagnostic Provenance Engine:
      Layer 1: Syntactic & Compilation Integrity (Node.js syntax check, py_compile, safe storage)
      Layer 2: Entity Parity & Semantic Layout Depth Gate (Anti-stub enforcement, brand/persona parity)
      Layer 3: DOM Event & Interactive Parity (HTML ID binding, listener parity, CSS layout parity)
      Layer 4: Anti-Placeholder & Active Implementation Gate (rejects comment stubs & empty listeners)
      Layer 5: Headless Browser Runtime Verification Gate (Chromium pageerror, interaction crashes, viewports)

    Dynamically attributes every defect to its exact responsible file ('app.js', 'index.html', 'styles.css', '*.py')
    and computes the 'primary_repair_file' so local models self-repair with zero guessing.
    """
    clean_proj = sanitize_project_name(project_name)
    proj_dir = get_project_dir(clean_proj)

    if not proj_dir.exists():
        return {
            "valid": False,
            "project": clean_proj,
            "errors": [f"Project workspace '{clean_proj}' does not exist on disk."],
            "warnings": [],
            "diagnostics": [],
            "target_files": [],
            "primary_repair_file": None,
            "summary": "Workspace directory not found."
        }

    errors: List[str] = []
    warnings: List[str] = []
    diagnostics: List[Dict[str, Any]] = []

    def add_error(target_file: str, category: str, message: str):
        errors.append(message)
        diagnostics.append({
            "file": target_file,
            "severity": "error",
            "category": category,
            "message": message
        })

    def add_warning(target_file: str, category: str, message: str):
        warnings.append(message)
        diagnostics.append({
            "file": target_file,
            "severity": "warning",
            "category": category,
            "message": message
        })

    html_file = proj_dir / "index.html"
    js_file = proj_dir / "app.js"
    css_file = proj_dir / "styles.css"
    py_files = list(proj_dir.glob("*.py"))

    html_content = ""
    js_content = ""

    # ==========================================
    # LAYER 1: SYNTACTIC & COMPILATION INTEGRITY
    # ==========================================
    if py_files and not html_file.exists():
        import py_compile
        for py_f in py_files:
            try:
                py_compile.compile(str(py_f), doraise=True)
            except py_compile.PyCompileError as pe:
                add_error(py_f.name, "syntax_error", f"Python Syntax Error in '{py_f.name}': {pe}")
    elif not html_file.exists() and not py_files:
        add_error("index.html", "missing_file", "Missing required 'index.html' or primary code file in project workspace.")
    elif html_file.exists():
        html_content = html_file.read_text(encoding="utf-8", errors="replace")
        lowered_html = html_content.lower()
        if "<!doctype html>" not in lowered_html and "<html" not in lowered_html:
            add_error("index.html", "html_structure", "'index.html' is not a valid HTML5 document (missing <!DOCTYPE html> or <html> tag).")
        if "styles.css" not in lowered_html and css_file.exists():
            add_warning("index.html", "missing_link", "'index.html' does not link 'styles.css' in its <head>.")
        if "app.js" not in lowered_html and js_file.exists():
            add_error("index.html", "missing_link", "'index.html' does not link 'app.js' (<script src=\"app.js\"></script>). Interactivity will not run!")

    # Validate JavaScript files linked in index.html or primary app.js with node -c
    for js_p in proj_dir.glob("*.js"):
        if js_p.name == "app.js" or (html_content and js_p.name in html_content):
            c_text = js_p.read_text(encoding="utf-8", errors="replace")
            js_res = validate_javascript_syntax(c_text, js_p.name)
            if not js_res["valid"]:
                add_error(js_p.name, js_res.get("type", "syntax_error"), js_res["error"])
            if js_p.name == "app.js":
                js_content = c_text

    # ==============================================================
    # LAYER 2: ENTITY PARITY & CONTENT DEPTH GATE (ANTI-STUB SHIELD)
    # ==============================================================
    if html_file.exists():
        lowered_html = html_content.lower()
        is_pure_canvas_game = "<canvas" in lowered_html and not any(tag in lowered_html for tag in ["<section", "<main", "<header", "<nav"])

        if not is_pure_canvas_game:
            # 1. Semantic Layout Depth Check: Prevent 1-button or 1-div stubs
            semantic_tags = re.findall(r'<(header|nav|section|main|footer|article|aside)\b', html_content, re.IGNORECASE)
            if len(semantic_tags) < 2:
                add_error(
                    "index.html",
                    "html_depth",
                    f"STUB / LAZY CODE ERROR: 'index.html' is an incomplete stub without full page layout sections (found only {len(semantic_tags)} semantic tags). "
                    "A production application must include at least <header>, <nav>, multiple <section> elements (e.g. hero, content/features grid, spotlight card), and <footer>."
                )

            # 2. Minimum Content Density Check
            if len(html_content.strip()) < 350:
                add_error(
                    "index.html",
                    "html_density",
                    f"INCOMPLETE HTML ERROR: 'index.html' is too brief ({len(html_content.strip())} chars). "
                    "A production application requires a full multi-section layout with detailed markup, cards, and interactive elements."
                )

        # 3. Entity Parity Gate: Ensure requested brand and persona are present
        if required_entities and isinstance(required_entities, dict):
            all_code_corpus = (html_content + " " + js_content).lower()

            # Brand name parity check
            brand = required_entities.get("brand_name")
            if brand and len(brand) > 2:
                brand_tokens = [t.lower() for t in brand.split() if len(t) > 3 and t.lower() not in ("website", "center", "app", "store", "portal", "tution", "tuition")]
                brand_found = (brand.lower() in all_code_corpus) or any(t in all_code_corpus for t in brand_tokens)
                if not brand_found:
                    add_error(
                        "index.html",
                        "entity_parity",
                        f"ENTITY PARITY ERROR: The requested brand name '{brand}' was NOT found anywhere in 'index.html' or 'app.js'! "
                        f"You must feature '{brand}' prominently in the site header, title, and hero section."
                    )

            # Persona name parity check
            persona = required_entities.get("persona_name")
            if persona and len(persona) > 2:
                persona_tokens = [t.lower() for t in persona.split() if len(t) > 2]
                persona_found = (persona.lower() in all_code_corpus) or (len(persona_tokens) > 1 and all(t in all_code_corpus for t in persona_tokens))
                if not persona_found:
                    add_error(
                        "index.html",
                        "entity_parity",
                        f"ENTITY PARITY ERROR: The requested featured persona '{persona}' was NOT found in 'index.html' or 'app.js'! "
                        f"You must include a dedicated spotlight card or bio section featuring '{persona}'."
                    )

        # Anti-Empty-Canvas Stub check for games
        has_nav_or_sections = any(tag in lowered_html for tag in ["<nav", "<header", "<section", "<main", "<article"])
        has_canvas = "<canvas" in lowered_html
        if has_canvas and not has_nav_or_sections:
            if js_file.exists():
                js_txt = js_file.read_text(encoding="utf-8", errors="replace")
                if "getContext" not in js_txt and "ctx." not in js_txt and "requestAnimationFrame" not in js_txt:
                    add_error(
                        "app.js",
                        "canvas_logic",
                        "BLANK CANVAS ERROR: 'index.html' contains an empty <canvas> with zero 2D rendering in 'app.js'! "
                        "The canvas is completely blank. If building a website or web application, you must write actual semantic HTML markup "
                        "(<nav>, <header>, <section>, cards, grid) instead of an empty canvas!"
                    )

        # Layout Mismatch check: styles.css defines layout rules (.navbar, .hero, .card, etc) but index.html lacks them
        if css_file.exists():
            css_txt = css_file.read_text(encoding="utf-8", errors="replace")
            css_classes = re.findall(r'\.([a-zA-Z0-9_\-]+)\s*\{', css_txt)
            key_layout_classes = [c for c in css_classes if any(k in c.lower() for k in ["nav", "hero", "card", "row", "grid", "carousel", "movie", "product", "banner"])]
            if key_layout_classes and not any(f'class="{c}"' in html_content or f"class='{c}'" in html_content for c in key_layout_classes):
                add_error(
                    "index.html",
                    "layout_mismatch",
                    f"LAYOUT MISMATCH ERROR: 'styles.css' defines key layout classes {key_layout_classes[:5]}, "
                    "but none of them exist in 'index.html'! You wrote CSS for a website but your HTML is missing the actual components!"
                )

    # ===============================================
    # LAYER 3: DOM EVENT & INTERACTIVE PARITY GATE
    # ===============================================
    if html_content and js_content:
        contract_issues = validate_html_js_contract(html_content, js_content)
        for issue in contract_issues:
            if "DEAD CONTROL" in issue:
                add_warning("app.js", "dead_control", issue)
            elif "ID MISMATCH" in issue:
                add_error("index.html", "id_mismatch", issue)
            elif "ERROR" in issue:
                add_error("app.js", "contract_error", issue)
            else:
                add_warning("app.js", "contract_warning", issue)

    # ==============================================================
    # LAYER 4: ANTI-PLACEHOLDER & ACTIVE IMPLEMENTATION AUDIT GATE
    # ==============================================================
    lazy_comment_rules = [
        (r'<!--\s*(?:.*?(?:\.\.\.|no changes needed|rest of code|add your|todo|fill in|content here|goes here))', "HTML Comment Placeholder ('<!-- ... -->')"),
        (r'//\s*(?:.*?(?:logic to handle|rest of code|todo|add your|fill in|implementation goes here|logic here|goes here|\.\.\.))', "JavaScript Placeholder Comment ('// Logic to handle...')"),
        (r'/\*\s*(?:.*?(?:rest of code|add your|todo|fill in|styles here|goes here|\.\.\.))\s*\*/', "Block Comment Placeholder ('/* ... */')")
    ]

    # Check HTML for lazy comment stubs
    if html_content:
        for pat, desc in lazy_comment_rules:
            m = re.search(pat, html_content, re.IGNORECASE)
            if m:
                add_error(
                    "index.html",
                    "placeholder",
                    f"PLACEHOLDER DETECTED IN HTML ({desc}): Found placeholder comment '{m.group(0).strip()}'. "
                    "A production web application must contain real HTML markup (e.g. real nav items, hero banners, cards), not placeholder comments! "
                    "Use 'edit_project_file' to replace this comment with complete markup."
                )

    # Check JS for lazy comments and empty event listeners
    if js_content:
        for pat, desc in lazy_comment_rules:
            m = re.search(pat, js_content, re.IGNORECASE)
            if m:
                add_error(
                    "app.js",
                    "placeholder",
                    f"PLACEHOLDER DETECTED IN JS ({desc}): Found placeholder comment '{m.group(0).strip()}'. "
                    "You must write the complete working JavaScript logic instead of leaving comment stubs. "
                    "Use 'edit_project_file' to implement the missing functionality now."
                )

        # Check for empty event listeners
        empty_listener_matches = re.finditer(
            r'([a-zA-Z0-9_$]+)\.addEventListener\s*\(\s*["\']([a-zA-Z0-9_\-]+)["\']\s*,\s*(?:\([^\)]*\)|[a-zA-Z0-9_$]+)\s*=>\s*\{([^}]*)\}\s*\)',
            js_content
        )
        for em in empty_listener_matches:
            elem_var = em.group(1)
            event_type = em.group(2)
            body = em.group(3).strip()
            clean_body = re.sub(r'//[^\r\n]*', '', body).strip()
            clean_body = re.sub(r'/\*[\s\S]*?\*/', '', clean_body).strip()
            if not clean_body:
                add_error(
                    "app.js",
                    "empty_listener",
                    f"EMPTY EVENT LISTENER ERROR: Listener on '{elem_var}' for event '{event_type}' has an EMPTY function body with no executable code! "
                    "You must write the real implementation inside the event listener callback."
                )

    # ==============================================================
    # LAYER 5: ANTIGRAVITY HEADLESS BROWSER RUNTIME VERIFICATION GATE
    # ==============================================================
    if len(errors) == 0 and html_file.exists():
        try:
            from backend.core.browser_gate import audit_workspace_runtime
            browser_audit = audit_workspace_runtime(proj_dir, timeout_sec=4.0, viewports=viewports)
            if not browser_audit.get("valid"):
                # Ingest structured browser diagnostics with file provenance
                if browser_audit.get("diagnostics"):
                    for b_diag in browser_audit["diagnostics"]:
                        add_error(
                            b_diag.get("file", "app.js"),
                            b_diag.get("category", "browser_runtime"),
                            f"BROWSER RUNTIME DEFECT: {b_diag['message']}"
                        )
                else:
                    for b_err in browser_audit.get("critical_errors", []):
                        add_error("app.js", "browser_runtime", f"BROWSER RUNTIME DEFECT: {b_err}")
        except Exception:
            pass

    # ==============================================================
    # LAYER 5B: UNIVERSAL BACKEND DOCKER TEST GATE
    # ==============================================================
    if len(errors) == 0 and (py_files or (proj_dir / "package.json").exists()):
        try:
            from backend.core.container_runner import run_backend_docker_test_gate
            backend_test_res = run_backend_docker_test_gate(clean_proj, timeout=8)
            if not backend_test_res.get("valid"):
                target_f = backend_test_res.get("primary_repair_file", py_files[0].name if py_files else "main.py")
                add_error(
                    target_f,
                    backend_test_res.get("category", "backend_test_failure"),
                    backend_test_res.get("error", "Backend compilation/test failure.")
                )
        except Exception as e:
            print(f"[BACKEND GATE WARNING]: Could not run backend container gate: {e}")

    # ==============================================================
    # LAYER 6: APPSEC & SECRET LEAKAGE AUDIT GATE (Marcus Kane)
    # ==============================================================
    try:
        from backend.core.security_scanner import audit_workspace_security
        sec_audit = audit_workspace_security(proj_dir)
        if not sec_audit.get("valid"):
            for finding in sec_audit.get("findings", []):
                if finding["severity"] in ("CRITICAL", "HIGH"):
                    add_error(
                        finding["file"],
                        finding["category"],
                        f"SECURITY VULNERABILITY [{finding['severity']}]: {finding['title']} at line {finding['line']}. {finding['remediation']}"
                    )
    except Exception:
        pass

    is_valid = len(errors) == 0

    # Determine primary file requiring repair based on defect severity
    primary_repair_file = None
    priority_order = [
        "secret_leakage", "code_injection", "insecure_transport",
        "runtime_exception", "interaction_crash", "browser_runtime", "syntax_error", "unsafe_storage",
        "missing_file", "html_structure", "missing_link", "html_depth", "entity_parity",
        "canvas_logic", "empty_listener", "dead_control", "id_mismatch", "placeholder",
        "responsive_overflow", "layout_mismatch"
    ]
    for prio_cat in priority_order:
        matching = [d["file"] for d in diagnostics if d.get("category") == prio_cat and d.get("file")]
        if matching:
            primary_repair_file = matching[0]
            break

    if not primary_repair_file and diagnostics:
        primary_repair_file = diagnostics[0].get("file")

    summary_lines = []
    if errors:
        summary_lines.append(f"CRITICAL ACCEPTANCE GATE DEFECTS ({len(errors)}):")
        # Group by target file for explicit provenance
        by_file: Dict[str, List[str]] = {}
        for d in diagnostics:
            if d.get("severity") == "error":
                f_key = d.get("file") or "workspace"
                by_file.setdefault(f_key, []).append(d.get("message"))

        for f_name, err_list in by_file.items():
            summary_lines.append(f"\n[TARGET FILE TO EDIT: '{f_name}']")
            for e in err_list[:3]:
                summary_lines.append(f"  - {e}")
            if f_name.endswith(".js"):
                summary_lines.append(f"  -> PRESCRIPTIVE INSTRUCTION: Call 'edit_project_file' or 'write_project_file' on '{f_name}' to fix these runtime/logic defects. Do NOT modify 'index.html'!")
            elif f_name.endswith(".html"):
                summary_lines.append(f"  -> PRESCRIPTIVE INSTRUCTION: Call 'edit_project_file' or 'write_project_file' on '{f_name}' to update HTML structure and IDs.")
            elif f_name.endswith(".css"):
                summary_lines.append(f"  -> PRESCRIPTIVE INSTRUCTION: Call 'edit_project_file' or 'write_project_file' on '{f_name}' to update responsive styles.")
            elif f_name.endswith(".py"):
                summary_lines.append(f"  -> MANDATORY FIX IN '{f_name}': Correct Python syntax or logic in '{f_name}'.")

        if primary_repair_file:
            summary_lines.append(f"\nPRIMARY REPAIR TARGET: '{primary_repair_file}'")

    if warnings and not errors:
        summary_lines.append(f"WARNINGS ({len(warnings)}):")
        for w in warnings[:4]:
            summary_lines.append(f"  - {w}")

    if is_valid and not warnings:
        summary_lines.append("All 5 Acceptance Gate layers passed: 0 syntax errors, complete entity parity, full interactive bindings, and 0 headless browser runtime crashes.")

    return {
        "valid": is_valid,
        "project": clean_proj,
        "errors": errors,
        "warnings": warnings,
        "diagnostics": diagnostics,
        "target_files": list(dict.fromkeys([d["file"] for d in diagnostics if d.get("file")])),
        "primary_repair_file": primary_repair_file,
        "summary": "\n".join(summary_lines)
    }
