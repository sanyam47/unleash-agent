import os
import re
import time
from pathlib import Path
from typing import Dict, Any, List

def format_file_size(size_bytes: int) -> str:
    """Format bytes to human readable string."""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{round(size_bytes / 1024, 1)}KB"
    return f"{round(size_bytes / (1024 * 1024), 1)}MB"

def get_workspace_tree(project_dir: Path) -> str:
    """
    Generates a clean, hierarchical ASCII directory tree of the workspace
    with file sizes and modification times.
    """
    if not project_dir.exists():
        return "Workspace is empty (0 files)."

    lines = []
    items = sorted(list(project_dir.rglob("*")))
    files = [i for i in items if i.is_file() and not i.name.startswith(".")]

    if not files:
        return "Workspace is empty (0 files)."

    lines.append(f"{project_dir.name}/")
    for idx, f in enumerate(files):
        rel = f.relative_to(project_dir).as_posix()
        size_str = format_file_size(f.stat().st_size)
        is_last = (idx == len(files) - 1)
        prefix = "|-- " if is_last else "|-- "
        lines.append(f"{prefix}{rel} ({size_str})")

    return "\n".join(lines)


def extract_workspace_symbols(project_dir: Path) -> Dict[str, Any]:
    """
    Extracts a lean (< 200 tokens) interface and symbol table from existing workspace files.
    Gives the local model precise interface contracts without context bloat.
    """
    symbols = {
        "html_ids": [],
        "html_classes": [],
        "css_variables": [],
        "css_classes": [],
        "js_functions": [],
        "js_state_vars": [],
        "python_functions": [],
        "python_classes": []
    }

    if not project_dir.exists():
        return symbols

    for file_path in project_dir.glob("*"):
        if not file_path.is_file():
            continue
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        ext = file_path.suffix.lower()

        # HTML Extraction
        if ext in (".html", ".htm"):
            ids = re.findall(r'\bid=["\']([a-zA-Z0-9_\-]+)["\']', content)
            for i in ids:
                if i not in symbols["html_ids"] and len(i) < 40:
                    symbols["html_ids"].append(i)

            classes = re.findall(r'\bclass=["\']([^"\']+)["\']', content)
            for c_str in classes:
                for c in c_str.split():
                    c_clean = c.strip()
                    if c_clean and c_clean not in symbols["html_classes"] and len(c_clean) < 30:
                        symbols["html_classes"].append(c_clean)

        # CSS Extraction
        elif ext == ".css":
            vars_found = re.findall(r'(--[a-zA-Z0-9_\-]+)\s*:', content)
            for v in vars_found:
                if v not in symbols["css_variables"]:
                    symbols["css_variables"].append(v)

            css_cls = re.findall(r'\.([a-zA-Z0-9_\-]+)\s*\{', content)
            for c in css_cls:
                if c not in symbols["css_classes"] and len(c) < 30:
                    symbols["css_classes"].append(c)

        # JavaScript Extraction
        elif ext in (".js", ".mjs"):
            # Functions
            funcs = re.findall(r'function\s+([a-zA-Z0-9_]+)\s*\(', content)
            funcs += re.findall(r'(?:const|let|var)\s+([a-zA-Z0-9_]+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>', content)
            funcs += re.findall(r'window\.([a-zA-Z0-9_]+)\s*=', content)
            for f in funcs:
                if f not in symbols["js_functions"] and len(f) < 40:
                    symbols["js_functions"].append(f)

            # State variables
            states = re.findall(r'(?:const|let)\s+([a-zA-Z0-9_]+)\s*=\s*(\[|\{)', content)
            for s_var, _ in states:
                if s_var not in symbols["js_state_vars"]:
                    symbols["js_state_vars"].append(s_var)

        # Python Extraction
        elif ext == ".py":
            classes = re.findall(r'class\s+([a-zA-Z0-9_]+)(?:\([^)]*\))?:', content)
            for cl in classes:
                if cl not in symbols["python_classes"]:
                    symbols["python_classes"].append(cl)

            funcs = re.findall(r'def\s+([a-zA-Z0-9_]+)\s*\(', content)
            for fn in funcs:
                if not fn.startswith("_") and fn not in symbols["python_functions"]:
                    symbols["python_functions"].append(fn)

    return symbols


def format_symbol_table_for_prompt(project_dir: Path) -> str:
    """Formats the symbol table into a compact markdown block for the LLM prompt."""
    sym = extract_workspace_symbols(project_dir)
    lines = []

    if sym["html_ids"]:
        ids_preview = ", ".join([f"#{i}" for i in sym["html_ids"][:15]])
        lines.append(f"- HTML IDs to bind/style: {ids_preview}")

    if sym["html_classes"]:
        cls_preview = ", ".join([f".{c}" for c in sym["html_classes"][:15]])
        lines.append(f"- HTML Structure Classes: {cls_preview}")

    if sym["css_variables"]:
        vars_preview = ", ".join(sym["css_variables"][:8])
        lines.append(f"- CSS Design Tokens: {vars_preview}")

    if sym["js_functions"]:
        funcs_preview = ", ".join([f"{fn}()" for fn in sym["js_functions"][:10]])
        lines.append(f"- JS Active Functions: {funcs_preview}")

    if sym["js_state_vars"]:
        state_preview = ", ".join(sym["js_state_vars"][:6])
        lines.append(f"- JS State Models: {state_preview}")

    if sym["python_classes"] or sym["python_functions"]:
        py_preview = ", ".join(sym["python_classes"][:5] + [f"{f}()" for f in sym["python_functions"][:8]])
        lines.append(f"- Python API & Services: {py_preview}")

    if not lines:
        return ""

    return (
        "\n=== LEAN WORKSPACE SYMBOL TABLE (Active Interfaces) ===\n"
        + "\n".join(lines) + "\n"
        + "MANDATE: Adhere strictly to these IDs, class names, and function contracts. Do not invent duplicate or mismatched IDs!\n"
    )
