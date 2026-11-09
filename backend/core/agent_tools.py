import os
import re
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

# Root directory for default agent-generated projects
PROJECTS_ROOT = Path(__file__).resolve().parent.parent / "data" / "projects"
PROJECTS_ROOT.mkdir(parents=True, exist_ok=True)

# Persistent registry mapping project_name -> custom workspace directory (Path)
_CUSTOM_WORKSPACE_REGISTRY: Dict[str, Path] = {}

def get_workspace_registry_file() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "workspace_registry.json"

def _load_workspace_registry():
    global _CUSTOM_WORKSPACE_REGISTRY
    reg_file = get_workspace_registry_file()
    if reg_file.exists():
        try:
            with open(reg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k, v in data.items():
                    _CUSTOM_WORKSPACE_REGISTRY[k] = Path(v).resolve()
        except Exception:
            pass

def register_custom_workspace(project_name: str, custom_dir: Path):
    """Registers a persistent custom OS directory for a project/chat session."""
    global _CUSTOM_WORKSPACE_REGISTRY
    clean_proj = sanitize_project_name(project_name)
    resolved = Path(custom_dir).resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    _CUSTOM_WORKSPACE_REGISTRY[clean_proj] = resolved
    
    # Persist to disk so it remembers across restarts
    reg_file = get_workspace_registry_file()
    try:
        data = {}
        if reg_file.exists():
            with open(reg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        data[clean_proj] = str(resolved)
        with open(reg_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[Workspace Registry Error]: {e}")

def get_project_dir(project_name: str) -> Path:
    """Returns the effective directory for a project (custom directory if registered, else PROJECTS_ROOT)."""
    clean_proj = sanitize_project_name(project_name)
    if not _CUSTOM_WORKSPACE_REGISTRY:
        _load_workspace_registry()
    if clean_proj in _CUSTOM_WORKSPACE_REGISTRY:
        custom_path = _CUSTOM_WORKSPACE_REGISTRY[clean_proj]
        custom_path.mkdir(parents=True, exist_ok=True)
        return custom_path
    proj_dir = (PROJECTS_ROOT / clean_proj).resolve()
    proj_dir.mkdir(parents=True, exist_ok=True)
    return proj_dir

def extract_workspace_path_from_prompt(text: str) -> Optional[Path]:
    """Extracts a Windows filesystem path if the user explicitly specifies one in their prompt."""
    if not text:
        return None
    # 1. Quoted path: "C:\path with spaces" or 'C:/path'
    m_quoted = re.search(r'(?:at|in|to|into|path|folder|directory)\s+["\'`]([a-zA-Z]:[\\/][^"\'`\r\n]+)["\'`]', text, re.IGNORECASE)
    if m_quoted:
        p = Path(m_quoted.group(1).strip().rstrip('\\/')).resolve()
        return _validate_safe_os_path(p)

    # 2. Unquoted path: at C:\coding\my_project
    m_unquoted = re.search(r'(?:at|in|to|into|path|folder|directory)\s+([a-zA-Z]:[\\/][^\s"\'`<>]+)', text, re.IGNORECASE)
    if m_unquoted:
        p = Path(m_unquoted.group(1).strip().rstrip('.,;:!\\/')).resolve()
        return _validate_safe_os_path(p)
    return None

def _validate_safe_os_path(p: Path) -> Optional[Path]:
    """Safety guard: prevents pointing workspace to dangerous OS roots or system folders."""
    str_p = str(p).lower().replace('/', '\\')
    disallowed = [
        r"c:\windows",
        r"c:\program files",
        r"c:\program files (x86)",
        r"c:\system volume information",
        r"c:\recovery",
        r"c:\boot",
        r"c:\users\default"
    ]
    # Block raw drive roots like C:\ or D:\
    if re.match(r'^[a-zA-Z]:[\\/]?$', str_p):
        return None
    for dis in disallowed:
        if str_p.startswith(dis):
            return None
    return p

MAX_READ_BYTES = 64 * 1024  # 64 KB safety limit for reading files


def sanitize_project_name(name: Optional[str]) -> str:
    """Sanitizes project name to prevent directory traversal and invalid characters."""
    if not name or not name.strip():
        return "project_default"
    cleaned = re.sub(r'[^a-zA-Z0-9_\-]', '_', name.strip())
    return cleaned[:48] or "project_default"


def resolve_safe_project_path(project_name: str, file_path: str) -> Path:
    """
    Resolves file_path within the project directory jail.
    Guarantees strict containment: blocks any traversal outside the project directory.
    Supports default sandbox under PROJECTS_ROOT or custom user-specified OS workspace.
    """
    clean_proj = sanitize_project_name(project_name)
    proj_dir = get_project_dir(clean_proj)

    # Clean requested file path
    clean_file = file_path.replace("\\", "/").strip().lstrip("/")
    # Disallow absolute drives like C:/
    clean_file = re.sub(r'^[a-zA-Z]:[/]', '', clean_file)

    target_path = (proj_dir / clean_file).resolve()

    # Enforce jail containment check
    try:
        target_path.relative_to(proj_dir)
    except ValueError:
        raise PermissionError(f"Security Alert: Path '{file_path}' attempts to escape project workspace '{proj_dir}'")

    return target_path


# ============================================================================
# AGENT TOOL IMPLEMENTATIONS
# ============================================================================

def write_project_file(project_name: str, file_path: str, content: str) -> Dict[str, Any]:
    """Writes a text or code file safely inside the project directory."""
    try:
        # Normalize truncated HTML filenames
        if file_path.lower().strip() in ("dex.html", "ndex.html", "index.htm"):
            file_path = "index.html"

        # Anti-stub validation: reject lazy comment placeholders and empty ellipsis
        lowered = content.lower().strip()
        if lowered in ("...", "/* ... */", "// ...", "<!-- ... -->") or (len(lowered) < 5 and not lowered.isalnum()):
            return {
                "status": "error",
                "file_path": file_path,
                "error": f"REJECTED: File content for '{file_path}' cannot be an ellipsis placeholder ('...'). You must write complete, working code!"
            }

        is_web_file = any(file_path.lower().endswith(ext) for ext in [".html", ".htm", ".css", ".js"])
        
        lazy_markers = [
            "add your custom styles here",
            "add your javascript logic here",
            "add your code here",
            "add your logic here",
            "todo: implement",
            "todo: add",
            "/* rest of styles */",
            "// rest of code"
        ]
        
        has_lazy_regex = bool(
            re.search(r"<!--\s*(?:add\s+(?:the|your)|todo\b)", lowered) or
            re.search(r"/\*\s*(?:add\s+(?:the|your)|todo\b)", lowered) or
            re.search(r"//\s*(?:add\s+(?:the|your)|todo\b)", lowered)
        )
        
        warning_note = None

        if is_web_file:
            found_lazy = [m for m in lazy_markers if m in lowered]
            if found_lazy or has_lazy_regex:
                warning_note = (
                    f"File '{file_path}' was saved, BUT contains placeholder comments. "
                    "Make sure to flesh out complete, functional elements and avoid placeholder comments."
                )

        if file_path.lower() in ("index.html", "index.htm"):
            # Auto-heal missing doctype or wrapper tags
            if "<html" not in lowered and "<!doctype" not in lowered:
                content = (
                    "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n"
                    "    <meta charset=\"UTF-8\">\n"
                    "    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n"
                    "    <title>Web Application</title>\n"
                    "    <link rel=\"stylesheet\" href=\"styles.css\">\n"
                    "</head>\n<body>\n"
                    f"{content}\n"
                    "    <script src=\"app.js\"></script>\n"
                    "</body>\n</html>"
                )
                lowered = content.lower().strip()

            # Ensure styles.css is linked
            if "styles.css" not in lowered:
                if "</head>" in content:
                    content = content.replace("</head>", '    <link rel="stylesheet" href="styles.css">\n</head>')
                elif "<body" in content:
                    content = re.sub(r'(<body[^>]*>)', r'<link rel="stylesheet" href="styles.css">\n\1', content, count=1, flags=re.I)
                else:
                    content = '<link rel="stylesheet" href="styles.css">\n' + content

            # Ensure app.js is linked
            if "app.js" not in lowered:
                if "</body>" in content:
                    content = content.replace("</body>", '    <script src="app.js"></script>\n</body>')
                else:
                    content = content + '\n<script src="app.js"></script>'

        if file_path.lower().endswith(".js"):
            from backend.core.workspace_validator import validate_javascript_syntax
            js_val = validate_javascript_syntax(content, file_path)
            if not js_val.get("valid"):
                warning_note = (
                    f"JavaScript validation note for '{file_path}':\n"
                    f"{js_val.get('error')}\n"
                    "Please self-repair syntax or unsafe storage calls."
                )

        target = resolve_safe_project_path(project_name, file_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        
        target.write_text(content, encoding="utf-8")
        size_bytes = target.stat().st_size

        res = {
            "status": "success",
            "project": sanitize_project_name(project_name),
            "file": file_path,
            "bytes_written": size_bytes,
            "message": f"Successfully wrote {size_bytes} bytes to '{file_path}'"
        }
        if warning_note:
            res["warning"] = warning_note
        return res
    except Exception as e:
        return {"status": "error", "error": f"Failed to write file '{file_path}': {str(e)}"}


def start_chunked_file(project_name: str, file_path: str, content: str, total_chunks: Optional[int] = None) -> Dict[str, Any]:
    """Initializes a new chunked file with its header / first block for multi-thousand line generation."""
    try:
        from backend.core.chunked_writer import start_chunked_file as scf
        return scf(project_name, file_path, content, total_chunks)
    except Exception as e:
        return {"status": "error", "error": f"Failed to start chunked file '{file_path}': {str(e)}"}


def append_project_file(project_name: str, file_path: str, content: str, is_final: bool = False) -> Dict[str, Any]:
    """Appends content to an existing file in the project directory, enabling chunked multi-thousand line generation."""
    try:
        from backend.core.chunked_writer import append_chunk_to_file as acf
        return acf(project_name, file_path, content, is_final)
    except Exception as e:
        return {"status": "error", "error": f"Failed to append to '{file_path}': {str(e)}"}


def read_project_file(project_name: str, file_path: str) -> Dict[str, Any]:
    """Reads a file from the project directory (capped at 64KB for safe context)."""
    try:
        target = resolve_safe_project_path(project_name, file_path)
        if not target.exists() or not target.is_file():
            return {"status": "error", "error": f"File '{file_path}' does not exist in project '{project_name}'"}

        text = target.read_text(encoding="utf-8", errors="replace")[:MAX_READ_BYTES]
        return {
            "status": "success",
            "file": file_path,
            "content": text,
            "bytes_read": len(text)
        }
    except Exception as e:
        return {"status": "error", "error": f"Failed to read file '{file_path}': {str(e)}"}


def list_project_files(project_name: str) -> Dict[str, Any]:
    """Lists all files in the project directory."""
    try:
        clean_proj = sanitize_project_name(project_name)
        proj_dir = get_project_dir(clean_proj)
        if not proj_dir.exists():
            return {"status": "success", "project": clean_proj, "files": []}

        files = []
        for p in proj_dir.rglob("*"):
            if p.is_file():
                rel = p.relative_to(proj_dir).as_posix()
                files.append({
                    "path": rel,
                    "size_bytes": p.stat().st_size,
                    "modified": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(p.stat().st_mtime))
                })

        return {"status": "success", "project": clean_proj, "total_files": len(files), "files": files}
    except Exception as e:
        return {"status": "error", "error": f"Failed to list files: {str(e)}"}


def run_in_sandbox(code: str, language: str = "python", stdin_input: Optional[str] = None) -> Dict[str, Any]:
    """
    Executes code in the isolated Docker / kernel job sandbox with:
    - Pre-execution AST check for host destruction
    - --network none air-gap
    - 256MB RAM limit and 4s process timeout
    """
    try:
        from backend.core.sandbox import execute_in_sandbox
        result = execute_in_sandbox(
            code=code,
            language=language or "python",
            timeout_seconds=4.0,
            stdin_input=stdin_input
        )
        return result
    except Exception as e:
        return {"status": "error", "error": f"Sandbox execution error: {str(e)}"}


def search_knowledge_vault(query: str, model_scope: Optional[str] = None) -> Dict[str, Any]:
    """Searches the model-scoped cybersecurity and engineering RAG vector database."""
    try:
        from backend.core.cyber_rag import search_knowledge
        results = search_knowledge(query, top_k=3, model_scope=model_scope)
        formatted = []
        for r in results:
            formatted.append({
                "title": r.get("title"),
                "external_id": r.get("external_id"),
                "summary": r.get("content", "")[:280] + ("..." if len(r.get("content", "")) > 280 else ""),
                "mitigation": r.get("mitigation"),
                "score": r.get("score")
            })
        return {"status": "success", "query": query, "results": formatted}
    except Exception as e:
        return {"status": "error", "error": f"Knowledge vault query error: {str(e)}"}


def search_internet_dataset(query: str) -> Dict[str, Any]:
    """
    Searches the internet and Hugging Face Datasets Hub for real-world datasets,
    technical documentation, schemas, and specifications matching the query.
    """
    import urllib.request
    import urllib.parse
    clean_q = (query or "").strip()
    if not clean_q:
        return {"status": "error", "error": "Query cannot be empty"}

    results = []

    # 1. Search Hugging Face Datasets API
    search_terms = [clean_q]
    words = clean_q.split()
    if len(words) > 2:
        search_terms.append(" ".join(words[:2]))
        if len(words) > 3:
            search_terms.append(words[0])

    for st in search_terms:
        if results:
            break
        try:
            url = f"https://huggingface.co/api/datasets?search={urllib.parse.quote(st)}&limit=5&full=true"
            req = urllib.request.Request(url, headers={"User-Agent": "AITrainer-Agent/1.0"})
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
                for item in data[:4]:
                    ds_id = item.get("id")
                    desc = item.get("description", "") or ""
                    desc_clean = re.sub(r'[\r\n\t]+', ' ', desc).strip()
                    if len(desc_clean) > 240:
                        desc_clean = desc_clean[:240] + "..."
                    tags = [t for t in item.get("tags", []) if isinstance(t, str) and not t.startswith("region:")][:4]
                    results.append({
                        "source": "Hugging Face Datasets",
                        "dataset_id": ds_id,
                        "description": desc_clean or f"Authoritative dataset for {st}",
                        "tags": tags,
                        "downloads": item.get("downloads", 0)
                    })
        except Exception as e:
            print(f"[DATASET SEARCH WARNING]: HF search error for '{st}': {e}")

    # 2. Local Gateway Grounded Datasets Fallback
    try:
        from backend.core.knowledge_gateway import reload_gateway_datasets
        gw_datasets = reload_gateway_datasets()
        lowered = clean_q.lower()
        for ds in gw_datasets:
            kws = [k.lower() for k in ds.get("keywords", [])]
            if any(k in lowered or lowered in k for k in kws):
                results.append({
                    "source": "Local Grounded Dataset",
                    "dataset_id": ds.get("id"),
                    "name": ds.get("name"),
                    "description": ds.get("description", ""),
                    "archetype": ds.get("architecture", {}).get("archetype", "")
                })
    except Exception:
        pass

    return {
        "status": "success",
        "query": clean_q,
        "datasets_found": len(results),
        "results": results
    }


def run_terminal_command(project_name: str, command: str) -> Dict[str, Any]:
    """Executes a terminal or test command inside the isolated Docker container or project sandbox."""
    try:
        from backend.core.container_runner import execute_in_isolated_container
        return execute_in_isolated_container(project_name, command)
    except Exception as e:
        return {"status": "error", "error": f"Terminal runner error: {str(e)}"}


# ============================================================================
# TOOL REGISTRY & DISPATCHER
# ============================================================================

def edit_project_file(project_name: str, file_path: str, target: str, replacement: str) -> Dict[str, Any]:
    """Surgically replaces a specific code snippet or block within an existing file without wiping the rest."""
    try:
        target_path = resolve_safe_project_path(project_name, file_path)
        if not target_path.exists() or not target_path.is_file():
            return {"status": "error", "error": f"File '{file_path}' does not exist in project '{project_name}'. Cannot edit."}

        original_content = target_path.read_text(encoding="utf-8", errors="replace")
        if target not in original_content:
            normalized_orig = original_content.replace("\r\n", "\n")
            normalized_target = target.replace("\r\n", "\n")
            if normalized_target in normalized_orig:
                new_content = normalized_orig.replace(normalized_target, replacement.replace("\r\n", "\n"), 1)
            else:
                return {
                    "status": "error",
                    "error": f"Target string not found in '{file_path}'. Ensure 'target' matches exact existing characters and whitespace.",
                    "hint": "Inspect the file first with 'read_project_file' to copy the exact lines to replace."
                }
        else:
            new_content = original_content.replace(target, replacement, 1)

        # Validate syntax if JS
        if file_path.lower().endswith(".js"):
            from backend.core.workspace_validator import validate_javascript_syntax
            js_val = validate_javascript_syntax(new_content, file_path)
            if not js_val.get("valid"):
                return {
                    "status": "error",
                    "error": f"Syntax validation failed after edit in '{file_path}': {js_val.get('error')}"
                }

        target_path.write_text(new_content, encoding="utf-8")
        return {
            "status": "success",
            "file": file_path,
            "bytes_written": len(new_content),
            "message": f"Successfully applied surgical edit to '{file_path}'"
        }
    except Exception as e:
        return {"status": "error", "error": f"Failed to edit file '{file_path}': {str(e)}"}


def get_project_tree(project_name: str) -> Dict[str, Any]:
    """Generates a hierarchical workspace tree with file sizes and structure."""
    try:
        clean_proj = sanitize_project_name(project_name)
        proj_dir = get_project_dir(clean_proj)
        from backend.core.symbol_extractor import get_workspace_tree
        tree_text = get_workspace_tree(proj_dir)
        return {
            "status": "success",
            "project": clean_proj,
            "tree": tree_text
        }
    except Exception as e:
        return {"status": "error", "error": f"Failed to get workspace tree: {str(e)}"}


AGENT_TOOLS_SCHEMA = [
    {
        "name": "edit_project_file",
        "description": "Surgically edit an existing file by replacing an exact code snippet or function block without wiping or rewriting the entire file. Use 'read_project_file' first to find the exact target string.",
        "parameters": {
            "file_path": "Relative path to file (e.g. 'index.html', 'app.js', 'styles.css')",
            "target": "Exact existing code string to be replaced (must match whitespace exactly)",
            "replacement": "New code string to replace the target with"
        }
    },
    {
        "name": "get_project_tree",
        "description": "Get a visual hierarchical tree of all files and folders in the workspace with sizes.",
        "parameters": {}
    },
    {
        "name": "write_project_file",
        "description": "Create or overwrite a file in the project workspace (e.g. index.html, styles.css, app.py, exploit.py).",
        "parameters": {
            "file_path": "Relative path to file (e.g. 'index.html', 'src/app.js')",
            "content": "Full content of the file to write"
        }
    },
    {
        "name": "append_project_file",
        "description": "Append code or text to an existing file in the project workspace, enabling chunked multi-thousand line generation without truncation.",
        "parameters": {
            "file_path": "Relative path to file (e.g. 'index.html', 'styles.css', 'app.js')",
            "content": "Code or text content to append"
        }
    },
    {
        "name": "read_project_file",
        "description": "Read the contents of an existing file in the project workspace.",
        "parameters": {
            "file_path": "Relative path to file (e.g. 'index.html')"
        }
    },
    {
        "name": "list_project_files",
        "description": "List all files currently created in this project.",
        "parameters": {}
    },
    {
        "name": "run_terminal_command",
        "description": "Execute a terminal, script, or test command inside the isolated project workspace (e.g. 'python test.py', 'pytest', 'node -c app.js'). Runs inside an air-gapped Docker container (--network none) or secure sandbox.",
        "parameters": {
            "command": "The terminal command to execute inside the project workspace"
        }
    },
    {
        "name": "run_in_sandbox",
        "description": "Execute code safely in the air-gapped Docker / kernel sandbox to test, lint, or run scripts. Output and errors are returned.",
        "parameters": {
            "code": "The code string to execute",
            "language": "python, javascript, powershell, or batch"
        }
    },
    {
        "name": "search_knowledge_vault",
        "description": "Query the verified RAG knowledge vault for CVEs, MITRE ATT&CK techniques, and technical documentation.",
        "parameters": {
            "query": "Search query or keyword"
        }
    },
    {
        "name": "search_internet_dataset",
        "description": "Search the internet and Hugging Face Hub for real-world datasets, technical specifications, and API schemas relevant to the user prompt.",
        "parameters": {
            "query": "Keywords or topic to search (e.g. 'snake game', 'crypto price tracker', 'flower taxonomy')"
        }
    },
    {
        "name": "verify_workspace_integrity",
        "description": "Automated code compiler and contract verification. Checks JavaScript syntax compilation, HTML links, and event listeners to ensure all buttons and features work properly without crashing.",
        "parameters": {}
    }
]


def dispatch_tool(tool_name: str, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatches a parsed tool call to its safe execution handler."""
    project_name = context.get("project_name", "default_project")
    model_scope = context.get("model", "global")

    tool_name = tool_name.strip()

    if tool_name == "write_project_file":
        path = args.get("file_path") or args.get("path") or args.get("filename")
        content = args.get("content", "")
        if not path:
            return {"status": "error", "error": "Missing 'file_path' argument for write_project_file"}
        return write_project_file(project_name, str(path), str(content))

    elif tool_name in ("start_chunked_file", "start_file_chunk", "init_chunked_file"):
        path = args.get("file_path") or args.get("path") or args.get("filename")
        content = args.get("content", "")
        total = args.get("total_chunks")
        if not path:
            return {"status": "error", "error": "Missing 'file_path' argument for start_chunked_file"}
        return start_chunked_file(project_name, str(path), str(content), total)

    elif tool_name in ("append_project_file", "append_to_file", "append_file", "append_chunk_to_file", "append_chunk"):
        path = args.get("file_path") or args.get("path") or args.get("filename")
        content = args.get("content", "")
        is_final = bool(args.get("is_final", False))
        if not path:
            return {"status": "error", "error": "Missing 'file_path' argument for append_project_file"}
        return append_project_file(project_name, str(path), str(content), is_final)

    elif tool_name in ("edit_project_file", "patch_project_file", "edit_file"):
        path = args.get("file_path") or args.get("path") or args.get("filename")
        tgt = args.get("target") or args.get("target_code") or ""
        rep = args.get("replacement") or args.get("replacement_code") or ""
        if not path or not tgt:
            return {"status": "error", "error": "Missing 'file_path' or 'target' for edit_project_file"}
        return edit_project_file(project_name, str(path), str(tgt), str(rep))

    elif tool_name in ("get_project_tree", "workspace_tree", "tree"):
        return get_project_tree(project_name)

    elif tool_name == "read_project_file":
        path = args.get("file_path") or args.get("path") or args.get("filename")
        if not path:
            return {"status": "error", "error": "Missing 'file_path' argument for read_project_file"}
        return read_project_file(project_name, str(path))

    elif tool_name == "list_project_files":
        return list_project_files(project_name)

    elif tool_name in ("run_terminal_command", "execute_command", "terminal"):
        cmd = args.get("command") or args.get("cmd") or ""
        if not cmd:
            return {"status": "error", "error": "Missing 'command' argument for run_terminal_command"}
        return run_terminal_command(project_name, str(cmd))

    elif tool_name == "run_in_sandbox":
        code = args.get("code") or args.get("script") or ""
        lang = args.get("language") or args.get("lang") or "python"
        stdin_val = args.get("stdin_input")
        if not code:
            return {"status": "error", "error": "Missing 'code' argument for run_in_sandbox"}
        return run_in_sandbox(str(code), str(lang), stdin_val)

    elif tool_name == "search_knowledge_vault":
        q = args.get("query") or args.get("q") or ""
        if not q:
            return {"status": "error", "error": "Missing 'query' argument for search_knowledge_vault"}
        return search_knowledge_vault(str(q), model_scope=model_scope)

    elif tool_name in ("search_internet_dataset", "search_dataset", "internet_dataset"):
        q = args.get("query") or args.get("q") or ""
        if not q:
            return {"status": "error", "error": "Missing 'query' argument for search_internet_dataset"}
        return search_internet_dataset(str(q))

    elif tool_name in ("verify_workspace_integrity", "verify_workspace", "check_integrity", "lint_workspace"):
        from backend.core.workspace_validator import validate_workspace
        return validate_workspace(project_name)

    else:
        return {"status": "error", "error": f"Unknown tool '{tool_name}'. Available: {[t['name'] for t in AGENT_TOOLS_SCHEMA]}"}
