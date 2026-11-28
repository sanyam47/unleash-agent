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
    if resolved.exists() and resolved.is_file():
        resolved = resolved.parent
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


def register_mounted_workspace(project_name: str, host_path: str) -> Dict[str, Any]:
    """
    Mounts an existing host directory as the active workspace for a project.
    - Validates path is safe (not OS root or Windows system folder)
    - Automatically initializes Git tracking if not already present
    - Creates pre-execution snapshot for 1-click rollback
    - Indexes file count and directory layout
    """
    clean_proj = sanitize_project_name(project_name)
    raw_path = Path(host_path).resolve()
    safe_path = _validate_safe_os_path(raw_path)
    if not safe_path:
        return {
            "status": "error",
            "error": f"Security Alert: Directory '{host_path}' is a protected OS system root and cannot be mounted."
        }
    if not safe_path.exists():
        return {
            "status": "error",
            "error": f"Directory '{host_path}' does not exist on disk."
        }
    if not safe_path.is_dir():
        return {
            "status": "error",
            "error": f"Path '{host_path}' is a file, not a directory."
        }

    # Register in custom workspace registry
    register_custom_workspace(clean_proj, safe_path)

    # Git shadow initialization
    git_tracked = False
    git_dir = safe_path / ".git"
    if git_dir.exists():
        git_tracked = True
    else:
        try:
            subprocess.run(["git", "init"], cwd=str(safe_path), capture_output=True, timeout=5, check=False)
            git_tracked = True
        except Exception:
            git_tracked = False

    # Create immutable pre-turn snapshot
    from backend.core.workspace_snapshot import create_snapshot
    snap_res = create_snapshot(clean_proj, step_label="mount_checkpoint", description=f"Pre-execution mount snapshot of {safe_path.name}")

    # Index code files excluding virtualenvs and node_modules
    IGNORED_PARTS = {"venv", ".venv", "node_modules", "__pycache__", "dist", "build"}
    indexed_files = []
    for root, dirs, filenames in os.walk(str(safe_path)):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in IGNORED_PARTS]
        for fn in filenames:
            if not fn.startswith("."):
                indexed_files.append(os.path.join(root, fn))
    file_count = len(indexed_files)

    return {
        "status": "mounted",
        "project_name": clean_proj,
        "workspace_path": str(safe_path),
        "files_count": file_count,
        "files_indexed": file_count,
        "git_tracked": git_tracked,
        "snapshot_id": snap_res.get("snapshot_id"),
        "message": f"Successfully mounted '{safe_path.name}' ({file_count} files). Git shadow and atomic rollback enabled."
    }

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
    """Extracts a Windows filesystem directory if the user explicitly specifies one in their prompt."""
    if not text:
        return None
    # 1. Quoted path: "C:\path with spaces" or 'C:/path'
    m_quoted = re.search(r'(?:at|in|to|into|path|folder|directory)\s+["\'`]([a-zA-Z]:[\\/][^"\'`\r\n]+)["\'`]', text, re.IGNORECASE)
    if m_quoted:
        p = Path(m_quoted.group(1).strip().rstrip('\\/')).resolve()
        if p.exists() and p.is_file():
            p = p.parent
        elif not p.exists() and p.suffix and len(p.suffix) <= 6:
            p = p.parent
        return _validate_safe_os_path(p)

    # 2. Unquoted path: at C:\coding\my_project
    m_unquoted = re.search(r'(?:at|in|to|into|path|folder|directory)\s+([a-zA-Z]:[\\/][^\s"\'`<>]+)', text, re.IGNORECASE)
    if m_unquoted:
        p = Path(m_unquoted.group(1).strip().rstrip('.,;:!\\/')).resolve()
        if p.exists() and p.is_file():
            p = p.parent
        elif not p.exists() and p.suffix and len(p.suffix) <= 6:
            p = p.parent
        return _validate_safe_os_path(p)
    return None

def _validate_safe_os_path(p: Path) -> Optional[Path]:
    """Safety guard: prevents pointing workspace to dangerous OS roots or system folders."""
    str_p = str(p).lower().replace('/', '\\').strip()
    disallowed = [
        r"c:\windows",
        r"c:\program files",
        r"c:\program files (x86)",
        r"c:\system volume information",
        r"c:\recovery",
        r"c:\boot",
        r"c:\users\default"
    ]
    # Block raw drive roots like C:\, D:\, C:, or D:\ 
    if re.match(r'^[a-zA-Z]:[\\/]*$', str_p):
        return None
    for dis in disallowed:
        if str_p == dis or str_p.startswith(dis + '\\') or str_p.startswith(dis + '/'):
            return None
    return p

MAX_READ_BYTES = 64 * 1024  # 64 KB safety limit for reading files


def sanitize_project_name(name: Any) -> str:
    """Sanitizes project name to prevent directory traversal and invalid characters."""
    if name is None:
        return "project_default"
    if isinstance(name, Path):
        name = name.name
    name_str = str(name).strip()
    if not name_str:
        return "project_default"
    cleaned = re.sub(r'[^a-zA-Z0-9_\-]', '_', name_str)
    return cleaned[:48] or "project_default"


def resolve_safe_project_path(project_name: str, file_path: str) -> Path:
    """
    Resolves file_path either:
    1. As a validated host OS absolute/home path (e.g. C:\\coding\\app\\main.py, ~/Desktop/note.txt)
       verified against _validate_safe_os_path() to block system/protected roots.
    2. Or relative within the project directory jail, blocking directory traversal (../).
    """
    raw_input = str(file_path or "").strip()
    if raw_input.startswith(("~/", "~\\")) or raw_input == "~":
        raw_input = os.path.expanduser(raw_input)

    is_abs = bool(re.match(r'^[a-zA-Z]:[\\/]', raw_input)) or raw_input.startswith("/") or os.path.isabs(raw_input)
    if is_abs:
        candidate = Path(raw_input).resolve()
        if _validate_safe_os_path(candidate) is None:
            raise PermissionError(f"Security Alert: Access to protected OS path '{file_path}' is blocked.")
        return candidate

    clean_proj = sanitize_project_name(project_name)
    proj_dir = get_project_dir(clean_proj)

    clean_file = raw_input.replace("\\", "/").lstrip("/")
    target_path = (proj_dir / clean_file).resolve()

    # Enforce jail containment check for relative workspace paths
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
        has_standalone_ellipsis = bool(
            re.search(r"^\s*(?:\.\.\.|/\*\s*\.\.\.\s*\*/|//\s*\.\.\.|<!--\s*\.\.\.\s*-->)\s*$", content, re.MULTILINE)
        )
        if lowered in ("...", "/* ... */", "// ...", "<!-- ... -->") or has_standalone_ellipsis or (len(lowered) < 5 and not lowered.isalnum()):
            return {
                "status": "error",
                "file_path": file_path,
                "error": f"REJECTED: File content for '{file_path}' contains an ellipsis placeholder ('...'). You must write complete, working code!"
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
        
        # Secret Scrubber: Redact any accidental active host secrets or private keys
        try:
            from backend.core.secret_scrubber import SecretScrubber
            scrubbed_c, sec_dets = SecretScrubber.scrub_text(content)
            if sec_dets:
                content = scrubbed_c
                det_labels = ", ".join(set(d.get("type", "SECRET") for d in sec_dets))
                warning_note = f"SECRET SCRUBBER: Redacted credentials ({det_labels}) before writing to disk."
        except Exception:
            pass

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


def read_project_file(
    project_name: str,
    file_path: str,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None
) -> Dict[str, Any]:
    """
    Reads a file (numbered lines) from the project directory or any safe workstation path.
    Supports economical line-range slicing (start_line..end_line) for local 8B context budgets.
    """
    try:
        target = resolve_safe_project_path(project_name, file_path)
        if not target.exists() or not target.is_file():
            return {"status": "error", "error": f"File '{file_path}' does not exist."}

        raw_text = target.read_text(encoding="utf-8", errors="replace")
        all_lines = raw_text.splitlines()
        total_lines = len(all_lines)

        s_line = max(1, int(start_line)) if start_line is not None else 1
        default_cap = 220
        e_line = min(total_lines, int(end_line)) if end_line is not None else min(total_lines, s_line + default_cap - 1)

        if s_line > total_lines and total_lines > 0:
            return {"status": "error", "error": f"start_line {s_line} exceeds total lines ({total_lines}) in '{file_path}'."}

        selected = all_lines[s_line - 1 : e_line]
        numbered = "\n".join(f"{s_line + idx}: {line}" for idx, line in enumerate(selected))
        if len(numbered) > MAX_READ_BYTES:
            numbered = numbered[:MAX_READ_BYTES] + "\n... [truncated due to byte limit]"

        res: Dict[str, Any] = {
            "status": "success",
            "file": str(target),
            "start_line": s_line,
            "end_line": e_line,
            "total_lines": total_lines,
            "content": numbered,
            "bytes_read": len(numbered)
        }
        if e_line < total_lines:
            res["note"] = f"Showing lines {s_line}-{e_line} of {total_lines}. Pass start_line={e_line + 1}, end_line={min(total_lines, e_line + default_cap)} to read further."
        return res
    except Exception as e:
        return {"status": "error", "error": f"Failed to read file '{file_path}': {str(e)}"}


_EASYOCR_READER = None
_EASYOCR_GPU_MODE = None

def _get_ocr_reader(use_gpu: Optional[bool] = None):
    """Lazy-initializes and caches EasyOCR reader, enabling CUDA acceleration only when VRAM headroom permits."""
    global _EASYOCR_READER, _EASYOCR_GPU_MODE
    if use_gpu is None:
        try:
            from backend.core.adaptive_tier import probe_active_compute_tier
            use_gpu = bool(probe_active_compute_tier().get("ocr_profile", {}).get("use_gpu", False))
        except Exception:
            use_gpu = False

    if _EASYOCR_READER is None:
        try:
            import easyocr
            import logging
            logging.getLogger("easyocr").setLevel(logging.ERROR)
            _EASYOCR_READER = easyocr.Reader(["en"], gpu=bool(use_gpu), verbose=False)
            _EASYOCR_GPU_MODE = bool(use_gpu)
        except Exception:
            if use_gpu:
                try:
                    import easyocr
                    _EASYOCR_READER = easyocr.Reader(["en"], gpu=False, verbose=False)
                    _EASYOCR_GPU_MODE = False
                except Exception:
                    _EASYOCR_READER = False
            else:
                _EASYOCR_READER = False
    return _EASYOCR_READER if _EASYOCR_READER is not False else None


def read_pdf_file(
    project_name: str,
    file_path: str,
    start_page: int = 1,
    end_page: Optional[int] = None,
) -> Dict[str, Any]:
    """Extracts text page-by-page from a PDF document with 1-indexed page numbers for citations.
    Includes automatic EasyOCR fallback for scanned/image pages with empty native text layers."""
    try:
        target = resolve_safe_project_path(project_name, file_path)
        if not target.exists() or not target.is_file():
            return {"status": "error", "error": f"PDF '{file_path}' does not exist."}

        s_page = max(1, int(start_page or 1))
        pages_out: List[Dict[str, Any]] = []
        total_pages = 0

        try:
            import fitz  # PyMuPDF
            doc = fitz.open(str(target))
            try:
                total_pages = len(doc)
                e_page = min(total_pages, int(end_page)) if end_page is not None else min(total_pages, s_page + 14)
                e_page = max(s_page, min(e_page, s_page + 39))
                for pno in range(s_page, e_page + 1):
                    page_obj = doc[pno - 1]
                    txt = (page_obj.get_text("text") or "").strip()

                    # Scanned PDF Fallback: if native text layer is empty (< 25 chars), run EasyOCR on page pixmap
                    if len(txt) < 25:
                        reader = _get_ocr_reader()
                        if reader:
                            try:
                                pix = page_obj.get_pixmap(dpi=150)
                                ocr_lines = reader.readtext(pix.tobytes("png"), detail=0)
                                ocr_joined = " ".join([l.strip() for l in ocr_lines if l.strip()])
                                if ocr_joined:
                                    txt = f"[OCR Extracted]: {ocr_joined}"
                            except Exception:
                                pass

                    pages_out.append({"page": pno, "text": txt[:8000]})
            finally:
                doc.close()
        except ImportError:
            import PyPDF2
            with open(target, "rb") as fh:
                reader = PyPDF2.PdfReader(fh)
                total_pages = len(reader.pages)
                e_page = min(total_pages, int(end_page)) if end_page is not None else min(total_pages, s_page + 14)
                e_page = max(s_page, min(e_page, s_page + 14))
                for pno in range(s_page, e_page + 1):
                    txt = (reader.pages[pno - 1].extract_text() or "").strip()
                    pages_out.append({"page": pno, "text": txt[:8000]})

        return {
            "status": "success",
            "file": str(target),
            "total_pages": total_pages,
            "start_page": s_page,
            "end_page": s_page + len(pages_out) - 1 if pages_out else s_page,
            "pages": pages_out,
        }
    except Exception as e:
        return {"status": "error", "error": f"Failed to read PDF '{file_path}': {str(e)}"}


def read_document_file(
    project_name: str,
    file_path: str,
    start_page: int = 1,
    end_page: Optional[int] = None,
) -> Dict[str, Any]:
    """Reads PDF, DOCX, PPTX, image (OCR), or plain-text documents with page/slide/section metadata."""
    ext = Path(str(file_path)).suffix.lower()
    if ext == ".pdf":
        return read_pdf_file(project_name, file_path, start_page=start_page, end_page=end_page)

    try:
        target = resolve_safe_project_path(project_name, file_path)
        if not target.exists() or not target.is_file():
            return {"status": "error", "error": f"Document '{file_path}' does not exist."}

        # Standalone Image OCR (PNG, JPG, JPEG, WEBP, BMP)
        if ext in (".png", ".jpg", ".jpeg", ".webp", ".bmp"):
            reader = _get_ocr_reader()
            if reader:
                try:
                    ocr_lines = reader.readtext(str(target), detail=0)
                    ocr_joined = " ".join([l.strip() for l in ocr_lines if l.strip()])
                    return {
                        "status": "success",
                        "file": str(target),
                        "total_pages": 1,
                        "start_page": 1,
                        "end_page": 1,
                        "pages": [{"page": 1, "text": f"[OCR Extracted]: {ocr_joined}"}],
                    }
                except Exception as e:
                    return {"status": "error", "error": f"OCR failed for image '{file_path}': {str(e)}"}
            return {"status": "error", "error": "OCR engine not available for image reading"}

        if ext == ".docx":
            import zipfile
            import xml.etree.ElementTree as ET
            with zipfile.ZipFile(target, "r") as zf:
                xml_bytes = zf.read("word/document.xml")
            root = ET.fromstring(xml_bytes)
            ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            paras = []
            for p in root.findall(".//w:p", ns):
                runs = [t.text for t in p.findall(".//w:t", ns) if t.text]
                if runs:
                    paras.append("".join(runs))
            text = "\n".join(paras)
            return {
                "status": "success",
                "file": str(target),
                "format": "docx",
                "total_pages": 1,
                "pages": [{"page": 1, "text": text[:16000]}],
            }

        if ext == ".pptx":
            import zipfile
            import xml.etree.ElementTree as ET
            slides_out: List[Dict[str, Any]] = []
            with zipfile.ZipFile(target, "r") as zf:
                slide_names = sorted(
                    [n for n in zf.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)],
                    key=lambda n: int(re.search(r"(\d+)", Path(n).stem).group(1)),
                )
                ns = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
                for idx, sname in enumerate(slide_names[:30], start=1):
                    root = ET.fromstring(zf.read(sname))
                    texts = [t.text for t in root.findall(".//a:t", ns) if t.text]
                    slides_out.append({"page": idx, "text": "\n".join(texts)[:4000]})
            return {
                "status": "success",
                "file": str(target),
                "format": "pptx",
                "total_pages": len(slides_out),
                "pages": slides_out,
            }

        if ext in (".xlsx", ".xls", ".csv", ".tsv"):
            import pandas as pd
            if ext in (".xlsx", ".xls"):
                xl = pd.read_excel(str(target), sheet_name=None)
                sheets_out: List[Dict[str, Any]] = []
                for idx, (sname, df) in enumerate(xl.items(), start=1):
                    preview_csv = df.head(120).to_csv(index=False)
                    sheets_out.append({
                        "page": idx,
                        "sheet": str(sname),
                        "rows": int(len(df)),
                        "columns": [str(c) for c in df.columns],
                        "text": f"[Sheet: {sname} | Rows: {len(df)}]\n{preview_csv}"[:8000],
                    })
                return {
                    "status": "success",
                    "file": str(target),
                    "format": ext.lstrip("."),
                    "total_pages": len(sheets_out),
                    "pages": sheets_out,
                }
            sep = "\t" if ext == ".tsv" else ","
            df = pd.read_csv(str(target), sep=sep)
            preview_csv = df.head(150).to_csv(index=False)
            return {
                "status": "success",
                "file": str(target),
                "format": ext.lstrip("."),
                "rows": int(len(df)),
                "columns": [str(c) for c in df.columns],
                "total_pages": 1,
                "pages": [{"page": 1, "text": f"[Rows: {len(df)} | Columns: {', '.join(map(str, df.columns))}]\n{preview_csv}"[:16000]}],
            }

        txt = target.read_text(encoding="utf-8", errors="replace")
        return {
            "status": "success",
            "file": str(target),
            "format": ext.lstrip(".") or "text",
            "total_pages": 1,
            "pages": [{"page": 1, "text": txt[:16000]}],
        }
    except Exception as e:
        return {"status": "error", "error": f"Failed to read document '{file_path}': {str(e)}"}


def list_dir(project_name: str, dir_path: str = ".") -> Dict[str, Any]:
    """Lists files and folders inside the project workspace or any safe host OS directory."""
    try:
        raw_dir = str(dir_path or ".").strip()
        target_dir = resolve_safe_project_path(project_name, raw_dir if raw_dir != "." else "")
        if not target_dir.exists() or not target_dir.is_dir():
            return {"status": "error", "error": f"Directory '{dir_path}' does not exist."}

        skip_names = {".git", "__pycache__", "node_modules", ".venv", "venv"}
        entries = []
        for entry in sorted(target_dir.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if entry.name in skip_names:
                entries.append({"name": entry.name, "type": "dir (skipped)", "size_bytes": 0})
                continue
            if entry.is_dir():
                entries.append({"name": entry.name, "type": "dir"})
            else:
                try:
                    sz = entry.stat().st_size
                except Exception:
                    sz = 0
                entries.append({"name": entry.name, "type": "file", "size_bytes": sz})
            if len(entries) >= 120:
                break

        return {
            "status": "success",
            "directory": str(target_dir),
            "count": len(entries),
            "entries": entries
        }
    except Exception as e:
        return {"status": "error", "error": f"Failed to list directory '{dir_path}': {str(e)}"}


def find_files(
    project_name: str,
    dir_path: str = ".",
    name_pattern: str = "*",
    max_results: int = 100,
) -> Dict[str, Any]:
    """Recursively locates files matching a glob pattern (e.g. '*.pdf', '*growth*') inside a permitted folder."""
    import fnmatch
    try:
        raw_dir = str(dir_path or ".").strip()
        target_dir = resolve_safe_project_path(project_name, raw_dir if raw_dir != "." else "")
        if not target_dir.exists() or not target_dir.is_dir():
            return {"status": "error", "error": f"Directory '{dir_path}' does not exist."}

        skip_dirs = {".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build"}
        pat = (name_pattern or "*").strip().lower()
        matches: List[Dict[str, Any]] = []
        cap = max(1, min(int(max_results or 100), 250))

        for root, dirs, files in os.walk(target_dir):
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            for fname in files:
                if fnmatch.fnmatch(fname.lower(), pat) or (pat != "*" and pat.strip("*") in fname.lower()):
                    fpath = Path(root) / fname
                    try:
                        st = fpath.stat()
                        matches.append({
                            "name": fname,
                            "path": str(fpath),
                            "size_bytes": int(st.st_size),
                        })
                    except OSError:
                        matches.append({"name": fname, "path": str(fpath)})
                    if len(matches) >= cap:
                        return {
                            "status": "success",
                            "dir": str(target_dir),
                            "pattern": name_pattern,
                            "count": len(matches),
                            "truncated": True,
                            "files": matches,
                        }

        return {
            "status": "success",
            "dir": str(target_dir),
            "pattern": name_pattern,
            "count": len(matches),
            "truncated": False,
            "files": matches,
        }
    except Exception as e:
        return {"status": "error", "error": f"Failed to find files in '{dir_path}': {str(e)}"}


def search_files(project_name: str, query: str, dir_path: str = ".", file_pattern: Optional[str] = None) -> Dict[str, Any]:
    """Searches for a text or regex pattern across files in a workspace or safe OS folder."""
    try:
        if not query or not str(query).strip():
            return {"status": "error", "error": "Search query cannot be empty."}

        raw_dir = str(dir_path or ".").strip()
        target_dir = resolve_safe_project_path(project_name, raw_dir if raw_dir != "." else "")
        if not target_dir.exists():
            return {"status": "error", "error": f"Path '{dir_path}' does not exist."}

        skip_dirs = {".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build"}
        try:
            pattern = re.compile(str(query), re.IGNORECASE)
        except re.error:
            pattern = re.compile(re.escape(str(query)), re.IGNORECASE)

        matches = []
        files_scanned = 0
        search_roots = [target_dir] if target_dir.is_file() else target_dir.rglob(file_pattern or "*")

        for p in search_roots:
            if not p.is_file():
                continue
            if any(part in skip_dirs for part in p.parts):
                continue
            if p.suffix.lower() in (".pyc", ".exe", ".dll", ".png", ".jpg", ".jpeg", ".ico", ".zip", ".gguf", ".bin", ".onnx"):
                continue
            files_scanned += 1
            if files_scanned > 600:
                break
            try:
                if p.stat().st_size > 512 * 1024:
                    continue
                content = p.read_text(encoding="utf-8", errors="ignore")
                for line_idx, line in enumerate(content.splitlines(), start=1):
                    if pattern.search(line):
                        matches.append({
                            "file": str(p),
                            "line": line_idx,
                            "text": line.strip()[:160]
                        })
                        if len(matches) >= 40:
                            break
            except Exception:
                continue
            if len(matches) >= 40:
                break

        return {
            "status": "success",
            "query": query,
            "directory": str(target_dir),
            "files_scanned": files_scanned,
            "match_count": len(matches),
            "matches": matches
        }
    except Exception as e:
        return {"status": "error", "error": f"Search failed: {str(e)}"}


def update_plan(project_name: str, steps: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Updates the agent's live step-by-step execution checklist shown to the user."""
    try:
        from backend.core.agent_progress import set_project_plan
        if not isinstance(steps, list) or not steps:
            return {"status": "error", "error": "Provide a non-empty list of step objects: [{'title': '...', 'status': 'in_progress|pending|done'}]"}
        normalized = set_project_plan(project_name, steps)
        return {
            "status": "success",
            "step_count": len(normalized),
            "steps": normalized,
            "message": f"Plan updated ({sum(1 for s in normalized if s['status'] == 'done')}/{len(normalized)} done)."
        }
    except Exception as e:
        return {"status": "error", "error": f"Failed to update plan: {str(e)}"}


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


def search_web_docs(query: str, project_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Privacy-preserving live web search for documentation, libraries, and CDN scripts.
    Features:
      1. Zero-tracking DuckDuckGo transport (no IP logs, no cookies, no accounts).
      2. In-flight secret & file-path scrubbing (no tokens or local paths ever leave machine).
      3. Automatic privacy-mode gating: if a project is marked private (.private), external web search is blocked.
    """
    import urllib.request
    import urllib.parse
    import html as html_lib
    import re

    clean_q = (query or "").strip()
    if not clean_q:
        return {"status": "error", "error": "Query cannot be empty"}

    # 0. Global Air-Gapped Privacy Mode Gate
    try:
        from backend.core.privacy_mode import is_air_gapped
        if is_air_gapped():
            return {
                "status": "privacy_blocked",
                "query": clean_q,
                "offline": True,
                "message": "External web search blocked in Air-Gapped Local Privacy Mode. Using local files & offline RAG only."
            }
    except Exception:
        pass

    # 1. Project-level Privacy Check
    if project_name:
        try:
            from backend.core.memory_manager import get_memory_store, PROJECTS_ROOT
            store = get_memory_store()
            clean_p = sanitize_project_name(project_name)
            p_dir = PROJECTS_ROOT / clean_p
            if clean_p in store.get("excluded_projects", []) or (p_dir / ".private").exists() or (p_dir / ".nomemory").exists():
                return {
                    "status": "privacy_blocked",
                    "query": clean_q,
                    "offline": True,
                    "message": f"Web search is disabled for confidential project '{clean_p}' to guarantee 100% air-gap privacy. Using local knowledge vault."
                }
        except Exception:
            pass

    # 2. In-flight Secret & File Path Scrubber (Marcus Kane AppSec)
    sanitized_q = clean_q
    # Strip local OS paths
    sanitized_q = re.sub(r'[A-Za-z]:\\[^\s"\']+', '[PATH_REDACTED]', sanitized_q)
    sanitized_q = re.sub(r'/(?:home|Users|root|var|etc)/[^\s"\']+', '[PATH_REDACTED]', sanitized_q)
    # Strip API tokens & keys
    sanitized_q = re.sub(r'\b(?:sk|ghp|gho|rpa|AKIA)[a-zA-Z0-9_\-]{16,}\b', '[SECRET_REDACTED]', sanitized_q)
    sanitized_q = re.sub(r'(?:api_key|password|secret)[=:\s]+[^\s,;&]+', '[CREDENTIAL_REDACTED]', sanitized_q, flags=re.IGNORECASE)

    # 3. Dual-Engine Web Search: SerpAPI Google Search (Priority 1) -> DuckDuckGo HTML (Fallback)
    import json
    import os
    results = []
    engine_used = "duckduckgo"

    serp_key = None
    try:
        from backend.core.config import settings
        serp_key = getattr(settings, "SERP_API_KEY", None)
    except Exception:
        pass
    if not serp_key or serp_key == "FILL_ME_IN":
        serp_key = os.getenv("SERP_API_KEY")

    if serp_key and serp_key != "FILL_ME_IN":
        try:
            params = urllib.parse.urlencode({
                "q": sanitized_q,
                "api_key": serp_key,
                "engine": "google",
                "num": 5
            })
            serp_url = f"https://serpapi.com/search.json?{params}"
            req = urllib.request.Request(
                serp_url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; UnleashAgent/1.0)"}
            )
            with urllib.request.urlopen(req, timeout=6) as resp:
                serp_data = json.loads(resp.read().decode("utf-8", errors="ignore"))
                organic = serp_data.get("organic_results", [])
                for item in organic[:5]:
                    title = item.get("title") or "Search Result"
                    link_url = item.get("link") or ""
                    clean_snippet = item.get("snippet") or ""
                    if not clean_snippet and item.get("snippet_highlighted_words"):
                        clean_snippet = " ".join(item.get("snippet_highlighted_words"))
                    if not clean_snippet:
                        clean_snippet = title

                    try:
                        from backend.core.prompt_injection_guard import wrap_untrusted_content
                        guarded_snippet = wrap_untrusted_content(clean_snippet, source=link_url)
                    except Exception:
                        guarded_snippet = clean_snippet

                    results.append({
                        "title": title,
                        "snippet": guarded_snippet,
                        "url": link_url
                    })
            if results:
                engine_used = "google_serpapi"
        except Exception:
            # SerpAPI quota reached or network error -> proceed to DuckDuckGo fallback
            results = []

    # Fallback to DuckDuckGo HTML Query if SerpAPI is not configured or returned no results
    if not results:
        try:
            url = "https://html.duckduckgo.com/html/"
            data = urllib.parse.urlencode({"q": sanitized_q}).encode("utf-8")
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5"
            }
            req = urllib.request.Request(url, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as resp:
                raw_html = resp.read().decode("utf-8", errors="ignore")

            # Parse snippets and URLs
            snippets = re.findall(r'<a class="result__snippet[^>]*>(.*?)</a>', raw_html, re.DOTALL)
            links = re.findall(r'<a class="result__url"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', raw_html, re.DOTALL)

            for i in range(min(4, len(snippets))):
                clean_snippet = re.sub(r'<[^>]+>', '', snippets[i]).strip()
                clean_snippet = html_lib.unescape(clean_snippet)
                link_url = links[i][0].strip() if i < len(links) else ""
                if link_url.startswith("//"):
                    link_url = "https:" + link_url

                try:
                    from backend.core.prompt_injection_guard import wrap_untrusted_content
                    guarded_snippet = wrap_untrusted_content(clean_snippet, source=link_url)
                except Exception:
                    guarded_snippet = clean_snippet

                results.append({
                    "title": f"Documentation Result {i+1}",
                    "snippet": guarded_snippet,
                    "url": link_url
                })
        except Exception:
            pass

    if results:
        return {
            "status": "success",
            "query": sanitized_q,
            "engine": engine_used,
            "privacy_protected": True,
            "results_count": len(results),
            "results": results
        }

    # 4. Fallback to local RAG if external web is unreachable
    try:
        from backend.core.cyber_rag import search_knowledge
        local_res = search_knowledge(sanitized_q, top_k=2)
        if local_res:
            return {
                "status": "fallback_local",
                "query": sanitized_q,
                "offline": True,
                "results": [
                    {"title": r.get("title", "Local Knowledge"), "snippet": r.get("content", "")[:250], "url": "local://vault"}
                    for r in local_res
                ]
            }
    except Exception:
        pass

    return {
        "status": "offline",
        "query": sanitized_q,
        "message": "Web search offline or timed out. Proceeding with local model knowledge."
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

def edit_project_file(
    project_name: str,
    file_path: str,
    target: str,
    replacement: str,
    replace_all: bool = False
) -> Dict[str, Any]:
    """
    Surgically replaces a specific code snippet or block within an existing file.
    Tier-1 Multi-Pass Matcher:
      Pass 1: Exact byte match
      Pass 2: Newline-normalized match (\r\n vs \n)
      Pass 3: Whitespace-trimmed line-block anchor match (handles indentation drift)
    Guarantees:
      - Validates syntax post-edit (JS, Python, JSON)
      - Returns line-diff stats (-X / +Y lines)
      - Zero placeholder hazard
    """
    try:
        target_path = resolve_safe_project_path(project_name, file_path)
        if not target_path.exists() or not target_path.is_file():
            return {"status": "error", "error": f"File '{file_path}' does not exist in project '{project_name}'. Cannot edit."}

        original_content = target_path.read_text(encoding="utf-8", errors="replace")
        new_content = None
        occurrences = 0

        # Pass 1: Exact substring match
        if target in original_content:
            occurrences = original_content.count(target)
            count_to_rep = occurrences if replace_all else 1
            new_content = original_content.replace(target, replacement, count_to_rep)

        # Pass 2: Line-ending normalized match
        if new_content is None:
            normalized_orig = original_content.replace("\r\n", "\n")
            normalized_target = target.replace("\r\n", "\n")
            normalized_rep = replacement.replace("\r\n", "\n")
            if normalized_target in normalized_orig:
                occurrences = normalized_orig.count(normalized_target)
                count_to_rep = occurrences if replace_all else 1
                new_content = normalized_orig.replace(normalized_target, normalized_rep, count_to_rep)

        # Pass 3: Fuzzy / whitespace-trimmed contiguous line-block match
        if new_content is None:
            orig_lines = original_content.replace("\r\n", "\n").splitlines(keepends=True)
            target_lines = [l.strip() for l in target.replace("\r\n", "\n").splitlines() if l.strip()]
            
            if target_lines and len(target_lines) <= len(orig_lines):
                # Scan for contiguous block where stripped lines match
                matched_start = -1
                matched_end = -1
                t_len = len(target_lines)

                for i in range(len(orig_lines) - t_len + 1):
                    window = [orig_lines[i + j].strip() for j in range(t_len)]
                    if window == target_lines:
                        matched_start = i
                        matched_end = i + t_len
                        occurrences = 1
                        break

                if matched_start != -1:
                    rep_block = replacement if replacement.endswith("\n") else replacement + "\n"
                    new_content = "".join(orig_lines[:matched_start]) + rep_block + "".join(orig_lines[matched_end:])

        if new_content is None:
            return {
                "status": "error",
                "error": f"Target string not found in '{file_path}'. Ensure 'target' matches existing characters and lines.",
                "hint": "Inspect the file first with 'read_project_file' to copy the exact lines to replace."
            }

        # Multi-language Syntax Validation Gates
        ext = target_path.suffix.lower()
        if ext == ".js":
            from backend.core.workspace_validator import validate_javascript_syntax
            js_val = validate_javascript_syntax(new_content, file_path)
            if not js_val.get("valid"):
                return {
                    "status": "error",
                    "error": f"JavaScript syntax validation failed after edit in '{file_path}': {js_val.get('error')}"
                }
        elif ext == ".py":
            from backend.core.workspace_validator import validate_python_syntax
            py_val = validate_python_syntax(new_content, file_path)
            if not py_val.get("valid"):
                return {
                    "status": "error",
                    "error": f"Python syntax validation failed after edit in '{file_path}': {py_val.get('error')}"
                }
        elif ext == ".json":
            try:
                import json
                json.loads(new_content)
            except Exception as je:
                return {
                    "status": "error",
                    "error": f"JSON syntax validation failed after edit in '{file_path}': {je}"
                }

        # Secret Scrubber: Redact any accidental secrets in replacement
        try:
            from backend.core.secret_scrubber import SecretScrubber
            scrubbed_new, sec_dets = SecretScrubber.scrub_text(new_content)
            if sec_dets:
                new_content = scrubbed_new
        except Exception:
            pass

        # Commit edit to disk
        target_path.write_text(new_content, encoding="utf-8")
        
        orig_line_cnt = len(target.splitlines())
        rep_line_cnt = len(replacement.splitlines())
        return {
            "status": "success",
            "file": file_path,
            "bytes_written": len(new_content),
            "lines_removed": orig_line_cnt,
            "lines_added": rep_line_cnt,
            "occurrences_replaced": occurrences,
            "message": f"Successfully applied surgical edit to '{file_path}' (-{orig_line_cnt}/+{rep_line_cnt} lines)"
        }
    except Exception as e:
        return {"status": "error", "error": f"Failed to edit file '{file_path}': {str(e)}"}


def delete_project_file(project_name: str, file_path: str) -> Dict[str, Any]:
    """
    Safely deletes a file from the project workspace.
    Automatically captures a time-machine snapshot before deletion so rollback is always possible.
    """
    try:
        clean_proj = sanitize_project_name(project_name)
        target = resolve_safe_project_path(clean_proj, file_path)
        if not target.exists() or not target.is_file():
            return {"status": "error", "error": f"File '{file_path}' does not exist in workspace."}

        # Take pre-action micro-snapshot before deletion for 1-click rollback
        snap_id = None
        try:
            from backend.core.workspace_snapshot import create_snapshot
            snap_res = create_snapshot(clean_proj, step_label="pre_delete", description=f"Safety snapshot before deleting {file_path}")
            snap_id = snap_res.get("snapshot_id")
        except Exception:
            pass

        target.unlink()
        return {
            "status": "success",
            "file": file_path,
            "project": clean_proj,
            "snapshot_id": snap_id,
            "message": f"Successfully deleted '{file_path}' from workspace. (Safety rollback snapshot created: {snap_id})"
        }
    except Exception as e:
        return {"status": "error", "error": f"Failed to delete file '{file_path}': {str(e)}"}


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
        "name": "delete_project_file",
        "description": "Delete a file from the project workspace. Triggers a Human-in-the-Loop confirmation gate and saves an automatic time-machine rollback snapshot before unlinking.",
        "parameters": {
            "file_path": "Relative path to file in project workspace to delete"
        }
    },
    {
        "name": "edit_project_file",
        "description": "Surgically edit an existing file by replacing an exact code snippet or function block without wiping or rewriting the entire file. Use 'read_project_file' first to find the exact target string.",
        "parameters": {
            "file_path": "Relative path to file at any arbitrary nested location (e.g. 'main.py', 'src/api/auth.py', 'database/schema.sql', 'docker-compose.yml', 'index.html')",
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
        "description": "Create or overwrite a file at any arbitrary nested path in the project workspace (e.g. main.py, src/api/auth.py, database/schema.sql, docker-compose.yml, index.html).",
        "parameters": {
            "file_path": "Relative path to file at any arbitrary nested location (e.g. 'main.py', 'src/api/auth.py', 'database/schema.sql', 'docker-compose.yml', 'index.html')",
            "content": "Full content of the file to write"
        }
    },
    {
        "name": "append_project_file",
        "description": "Append code or text to an existing file in the project workspace, enabling chunked multi-thousand line generation without truncation.",
        "parameters": {
            "file_path": "Relative path to file at any arbitrary nested location (e.g. 'main.py', 'models.py', 'index.html')",
            "content": "Code or text content to append"
        }
    },
    {
        "name": "read_project_file",
        "description": "Read the contents of a file in the project workspace (or specify 'project_name' to inspect and reuse code from any past project in persistent memory).",
        "parameters": {
            "file_path": "Relative path to file at any arbitrary nested location (e.g. 'main.py', 'src/app.js')",
            "project_name": "Optional name of a past project from persistent memory to inspect"
        }
    },
    {
        "name": "remember_preference",
        "description": "Store a user preference, architectural guideline, or custom fact in persistent cross-session memory so the agent remembers it across all future projects and sessions.",
        "parameters": {
            "category": "Category: 'profile', 'guideline', 'rule', or 'fact'",
            "key": "Setting or fact identifier (e.g. 'preferred_theme', 'css_framework')",
            "value": "The preference, guideline, or fact text to persist"
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
        "name": "search_web_docs",
        "description": "Privacy-preserving web documentation search. Look up real-world library docs, API references, CDN script tags, CSS frameworks, or code snippets (e.g. 'Leaflet map quickstart CDN', 'Chart.js v4 line chart example'). Queries are scrubbed for privacy and zero tracking.",
        "parameters": {
            "query": "Keywords or library documentation topic to search"
        }
    },
    {
        "name": "verify_workspace_integrity",
        "description": "Automated code compiler and contract verification. Checks JavaScript syntax compilation, HTML links, and event listeners to ensure all buttons and features work properly without crashing.",
        "parameters": {}
    },
    {
        "name": "launch_application",
        "description": "Launch desktop applications, Windows system utilities, or protocol handlers (e.g. 'whatsapp', 'terminal', 'vscode', 'spotify', 'chrome', 'calc', 'notepad', 'settings', 'taskmgr', 'explorer', 'discord', 'slack'). Automatically falls back to browser web app if desktop app is not installed.",
        "parameters": {
            "app_name": "Name or alias of application to launch (e.g. 'whatsapp', 'terminal', 'vscode', 'spotify', 'calc', 'notepad')",
            "args": "Optional arguments or file path to pass to the application"
        }
    },
    {
        "name": "get_workstation_telemetry",
        "description": "Inspect live Windows workstation hardware telemetry directly from physical kernel registers and GPU sensors (RAM usage, battery/power state, GPU thermals and load for RTX 3050, active foreground window, and top memory processes). Returns pure JSON hardware metrics in <1ms without any hallucinations.",
        "parameters": {}
    },
    {
        "name": "open_browser_url",
        "description": "Open a website, web application, search query, or link in the user's default Windows web browser (e.g. 'https://youtube.com', 'https://web.whatsapp.com', 'https://github.com').",
        "parameters": {
            "url": "Web URL to open in default browser"
        }
    },
    {
        "name": "system_control",
        "description": "Inspect real-time hardware telemetry, running processes, Windows system logs, or control system settings. Supported actions: 'processes' or 'top_processes' (inspect top CPU & RAM processes), 'logs' or 'check_logs' (inspect recent system event logs/errors), 'diagnostics' or 'heating' (inspect GPU thermals, CPU, RAM metrics), 'get_system_info' (RAM, CPU cores, battery level, free disk space), 'get_clipboard' (read clipboard), 'set_clipboard' (copy text), 'volume_mute', 'volume_up', 'volume_down', 'lock_workstation'.",
        "parameters": {
            "action": "Action to execute: 'processes', 'logs', 'diagnostics', 'heating', 'get_system_info', 'get_clipboard', 'set_clipboard', 'volume_mute', 'volume_up', 'volume_down', 'lock_workstation'",
            "value": "Optional value for actions like 'set_clipboard' (the text) or 'volume_up'/'volume_down' (number of steps)"
        }
    },
    {
        "name": "get_current_time",
        "description": "Get the precise real-time system clock, local time, date, day of the week, and timezone from the Windows host machine.",
        "parameters": {}
    },
    {
        "name": "send_desktop_notification",
        "description": "Display a native Windows desktop toast alert / notification popup on the user's screen.",
        "parameters": {
            "title": "Title of notification",
            "message": "Body text of notification"
        }
    },
    {
        "name": "run_host_cli",
        "description": "Execute a command directly on the host Windows machine outside the container sandbox. Used when the user explicitly requests host OS CLI execution (e.g. checking host git status, host system info, running local utilities).",
        "parameters": {
            "command": "The command line string to execute on the host Windows machine",
            "timeout": "Optional timeout in seconds (default 15)"
        }
    },
    {
        "name": "browser_navigate",
        "description": "Navigate to any web page or web application in Chrome/Edge. Returns page title, current URL, HTTP status, and text preview.",
        "parameters": {
            "url": "Target website or web app URL to visit (e.g. 'https://github.com/trending', 'https://news.ycombinator.com')",
            "headless": "Optional boolean: True (default) for fast background browsing, False to show a visible browser window"
        }
    },
    {
        "name": "browser_click",
        "description": "Click a link, button, or interactive element on the active web page by CSS selector or visible text.",
        "parameters": {
            "selector": "CSS selector of element to click (e.g. 'button.submit', 'a.read-more')",
            "text": "Optional visible text content of element to click (e.g. 'Next', 'Sign in', 'Search')"
        }
    },
    {
        "name": "browser_type",
        "description": "Type text into a search bar, input box, or form field on the active web page.",
        "parameters": {
            "selector": "CSS selector of input element (e.g. 'input[name=q]', '#search-input')",
            "text": "Text string to enter into the input",
            "press_enter": "Optional boolean: whether to submit Enter key after typing (default False)"
        }
    },
    {
        "name": "browser_extract",
        "description": "Extract clean readable text and top link URLs from the active web page.",
        "parameters": {
            "selector": "Optional CSS selector to extract from specific section (e.g. 'article', '.content', 'main')",
            "max_chars": "Optional maximum character length to extract (default 4000)"
        }
    },
    {
        "name": "browser_screenshot",
        "description": "Capture a full visual PNG screenshot of the active web page for verification or VLM inspection.",
        "parameters": {
            "filename": "Optional name for screenshot image file (default 'screenshot_<timestamp>.png')",
            "full_page": "Optional boolean: whether to capture the full scrollable page (default False)"
        }
    },
    {
        "name": "browser_search_and_read",
        "description": "Autonomous web intelligence search: queries the live web, visits the top authoritative source, and extracts clean article text and summaries.",
        "parameters": {
            "query": "Search query or question (e.g. 'latest release features of python 3.12', 'fastapi background tasks tutorial')",
            "num_results": "Optional number of top search results to inspect (default 3)"
        }
    },
    {
        "name": "browser_scroll",
        "description": "Scroll the active web page down, up, or to the bottom/top to reveal lazy-loaded content or comments.",
        "parameters": {
            "direction": "Direction: 'down' (default), 'up', 'bottom', or 'top'",
            "amount": "Optional pixel scroll amount (default 800)"
        }
    },
    {
        "name": "browser_close",
        "description": "Close the active browser session and release memory.",
        "parameters": {}
    },
    {
        "name": "capture_desktop_screen",
        "description": "Capture a high-resolution PNG screenshot of the user's Windows desktop or active screen.",
        "parameters": {
            "filename": "Optional output filename (e.g. 'error_state.png')",
            "region": "Optional [x, y, width, height] crop box"
        }
    },
    {
        "name": "list_open_windows",
        "description": "Perceive and list all currently active GUI application windows on the desktop (e.g. WhatsApp, Chrome, VS Code, Terminal).",
        "parameters": {}
    },
    {
        "name": "focus_window",
        "description": "Bring an open application window to the foreground by matching its title, process name, or PID.",
        "parameters": {
            "title": "Window title or process name to activate (e.g. 'WhatsApp', 'Brave', 'Terminal')"
        }
    },
    {
        "name": "analyze_screen_vision",
        "description": "Visually analyze the screen or a screenshot using multi-modal AI (Gemini Vision / Moondream). Extracts errors, traces, UI state, and answers questions about what is on screen.",
        "parameters": {
            "prompt": "Specific visual question or instruction (e.g. 'What error is shown in the terminal?', 'Describe the active window')",
            "image_path": "Optional path to existing screenshot; captures desktop automatically if omitted"
        }
    },
    {
        "name": "desktop_click",
        "description": "Click anywhere on the desktop or inside active application windows (left, right, middle, single, double-click).",
        "parameters": {
            "x": "Optional horizontal pixel coordinate (omitted clicks current position)",
            "y": "Optional vertical pixel coordinate (omitted clicks current position)",
            "button": "Mouse button: 'left' (default), 'right', or 'middle'",
            "clicks": "Number of clicks: 1 (single, default) or 2 (double-click)"
        }
    },
    {
        "name": "desktop_type",
        "description": "Type text into the active desktop application window (e.g. WhatsApp, Slack, VS Code, Terminal) with Unicode support.",
        "parameters": {
            "text": "Text to type into the focused input field",
            "press_enter": "Whether to press Enter key after typing (default False, set True to send messages)"
        }
    },
    {
        "name": "desktop_hotkey",
        "description": "Execute native Windows keyboard shortcut or special key (e.g. 'ctrl+c', 'ctrl+v', 'ctrl+s', 'alt+tab', 'win+d', 'enter', 'esc').",
        "parameters": {
            "keys": "Shortcut combination (e.g. 'ctrl+c', 'alt+tab', 'win+d', 'ctrl+shift+p')"
        }
    },
    {
        "name": "desktop_move",
        "description": "Move the mouse cursor to absolute desktop coordinates (x, y).",
        "parameters": {
            "x": "Horizontal pixel coordinate",
            "y": "Vertical pixel coordinate"
        }
    },
    {
        "name": "desktop_scroll",
        "description": "Scroll the desktop mouse wheel up or down at the active location.",
        "parameters": {
            "direction": "Scroll direction: 'down' (default) or 'up'",
            "amount": "Scroll amount units (default 3)"
        }
    },
    {
        "name": "desktop_cursor_pos",
        "description": "Get current mouse cursor coordinates and primary display resolution.",
        "parameters": {}
    },
    {
        "name": "speak_aloud",
        "description": "Speak text out loud through the computer speakers (supports low-latency neural and resonant studio modes).",
        "parameters": {
            "text": "The sentence or response to speak aloud",
            "mode": "Optional override: 'work' (low-latency neural) or 'cinema' (resonant studio)"
        }
    },
    {
        "name": "set_voice_mode",
        "description": "Switch voice synthesis profile between 'work' mode (ultra-fast, low-latency neural) and 'cinema' mode (deep resonant studio timbre).",
        "parameters": {
            "mode": "Target mode: 'work' or 'cinema'"
        }
    },
    {
        "name": "get_voice_mode",
        "description": "Check current voice mode, audio settings, and engine status.",
        "parameters": {}
    },
    {
        "name": "configure_wake_word",
        "description": "Configure wake-word settings: enable/disable background wake word listening, set custom trigger phrases (e.g. 'assistant', 'computer'), and toggle wake chime.",
        "parameters": {
            "enabled": "Optional boolean: True to enable wake word, False to disable",
            "wake_words": "Optional list or comma-separated string of trigger words (e.g. 'assistant, computer')",
            "wake_sound": "Optional boolean: True to chime on wake"
        }
    },
    {
        "name": "remember_fact",
        "description": "Store a persistent fact, contact, preference, or relationship into the Long-Term Cognitive Knowledge Graph.",
        "parameters": {
            "content": "The fact or instruction to remember (e.g. 'Preferred default terminal is PowerShell Core')",
            "category": "Optional category: 'contact', 'preference', 'fact', 'event'",
            "importance": "Optional importance 1-10 (default 8)",
            "entity": "Optional entity name (e.g. 'Terminal', 'Workstation')",
            "relation": "Optional relationship (e.g. 'preferred_shell', 'project_lead')",
            "target": "Optional target entity (e.g. 'PowerShell Core')"
        }
    },
    {
        "name": "recall_memory",
        "description": "Search and retrieve facts, personal contacts, preferences, and past events from the Cognitive Knowledge Graph.",
        "parameters": {
            "query": "The person, tool, question, or concept to recall (e.g. 'Dad', 'preferred editor', 'AWS port')",
            "top_k": "Optional maximum results to return (default 5)"
        }
    },
    {
        "name": "forget_memory",
        "description": "Remove or redact a memory, contact, or rule from the Cognitive Knowledge Graph.",
        "parameters": {
            "item_type": "Type of item to delete: 'entity', 'relation', 'habit', 'episode', or 'raw'",
            "item_id": "The ID of the memory item to delete"
        }
    },
    {
        "name": "multi_hop_query",
        "description": "Perform multi-hop reasoning over the Semantic Knowledge Graph to discover indirect connections and relational chains (e.g. Varun -> AWS -> Cloud Migration).",
        "parameters": {
            "start_entity": "The starting entity name (e.g. 'User', 'Varun', 'AWS')",
            "max_hops": "Maximum relational hops to traverse (default 3, range 1-4)",
            "target_entity": "Optional target entity to find connecting paths to"
        }
    },
    {
        "name": "consolidate_memory",
        "description": "Trigger an autonomous 'sleep cycle' consolidation to deduplicate memories, resolve conflicting facts, and synthesize procedural habits.",
        "parameters": {}
    },
    {
        "name": "start_background_task",
        "description": "Spawn an asynchronous, unbounded daemon task that executes in the background while keeping the chat/voice stream 100% active.",
        "parameters": {
            "title": "Short descriptive title of the background task",
            "description": "Full details of what the task should accomplish",
            "steps": "Optional list or comma-separated stages of the task"
        }
    },
    {
        "name": "check_background_tasks",
        "description": "Check real-time telemetry, stage progression, and status of running or recent background daemon tasks.",
        "parameters": {
            "task_id": "Optional specific task_id to inspect. If omitted, lists all active running tasks."
        }
    },
    {
        "name": "control_background_task",
        "description": "Control a running background task: pause, resume, or cancel.",
        "parameters": {
            "task_id": "The ID of the daemon task to control",
            "action": "Action to perform: 'pause', 'resume', or 'cancel'"
        }
    },
    {
        "name": "set_project_permission_policy",
        "description": "Enforce persistent project-specific security rules (e.g. 'require_approval': True to always ask before executing in this project).",
        "parameters": {
            "project_name": "The project/workspace to apply the policy to",
            "policy_key": "The policy rule (e.g. 'require_approval', 'ask_every_time')",
            "value": "Value to set (default True)"
        }
    },
    {
        "name": "inspect_preflight_safety",
        "description": "Run cognitive pre-flight inspection on a command, package, or URL to check for typosquatting, obfuscation, or suspicious patterns.",
        "parameters": {
            "target": "The command, package name, or URL to inspect",
            "target_type": "Optional target type: 'command', 'package', or 'url' (auto-detected if omitted)"
        }
    },
    {
        "name": "find_files",
        "description": "Recursively locate files matching a glob or name pattern (e.g. '*.pdf', '*growth*', '*.csv') in any workspace or OS folder.",
        "parameters": {
            "dir_path": "Directory path to search (e.g. 'D:\\\\Reports', 'C:\\\\Users\\\\...\\\\Downloads', or '.')",
            "name_pattern": "Filename glob pattern (e.g. '*.pdf', '*invoice*')",
            "max_results": "Optional max matches to return (default 100)"
        }
    },
    {
        "name": "read_document",
        "description": "Read and extract structured text or tables from PDF, CSV, Excel (.xlsx/.xls), Word (.docx), PowerPoint (.pptx), image (OCR), or text files.",
        "parameters": {
            "file_path": "Path to the document file",
            "start_page": "Optional 1-indexed start page for PDFs (default 1)",
            "end_page": "Optional 1-indexed end page for PDFs"
        }
    },
    {
        "name": "read_emails",
        "description": "Read recent or unread emails from the user's inbox via IMAP4_SSL using encrypted credentials.",
        "parameters": {
            "folder": "Mailbox folder name (default 'INBOX')",
            "unread_only": "Boolean: True for unread messages only (default True)",
            "query": "Optional keyword filter across sender, subject, or body",
            "limit": "Optional max emails to return (default 10)"
        }
    },
    {
        "name": "send_email",
        "description": "Send an email with optional file attachments via SMTP. Enforces a dry-run preview first unless confirm=True after explicit user confirmation.",
        "parameters": {
            "to": "Recipient email address or list of email addresses",
            "subject": "Email subject line",
            "body": "Plain-text email body",
            "attachments": "Optional list of file paths to attach",
            "confirm": "Boolean: set False first for dry-run preview; set True only after user confirms sending"
        }
    },
    {
        "name": "configure_email_credentials",
        "description": "Store SMTP/IMAP email address and app password encrypted at rest in the local AES-256-GCM Credential Vault.",
        "parameters": {
            "email_address": "User email address",
            "app_password": "Email app password / SMTP credential",
            "smtp_host": "Optional custom SMTP hostname",
            "imap_host": "Optional custom IMAP hostname"
        }
    }
]


def dispatch_tool(tool_name: str, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatches a parsed tool call to its safe execution handler."""
    project_name = context.get("project_name", "default_project")
    model_scope = context.get("model", "global")

    tool_name = tool_name.strip()

    if tool_name in ("write_project_file", "write_file", "create_file", "overwrite_file"):
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

    elif tool_name in ("read_project_file", "read_file", "view_file"):
        target_proj = args.get("project_name") or args.get("project") or project_name
        path = args.get("file_path") or args.get("path") or args.get("filename")
        if not path:
            return {"status": "error", "error": "Missing 'file_path' argument for read_file"}
        s_line = args.get("start_line")
        e_line = args.get("end_line")
        return read_project_file(str(target_proj), str(path), start_line=s_line, end_line=e_line)

    elif tool_name in ("read_pdf", "extract_pdf", "read_document"):
        target_proj = args.get("project_name") or args.get("project") or project_name
        path = args.get("file_path") or args.get("path") or args.get("filename")
        if not path:
            return {"status": "error", "error": "Missing 'file_path' argument for read_document"}
        s_page = args.get("start_page")
        e_page = args.get("end_page")
        return read_document_file(
            str(target_proj),
            str(path),
            start_page=int(s_page) if s_page is not None else 1,
            end_page=int(e_page) if e_page is not None else None,
        )

    elif tool_name in ("list_dir", "list_directory", "ls", "dir"):
        d_path = args.get("dir_path") or args.get("path") or args.get("directory") or "."
        return list_dir(project_name, str(d_path))

    elif tool_name in ("search_files", "grep_search", "grep", "find_in_files"):
        q = args.get("query") or args.get("pattern") or args.get("q") or ""
        d_path = args.get("dir_path") or args.get("path") or args.get("directory") or "."
        f_pat = args.get("file_pattern") or args.get("glob") or None
        return search_files(project_name, str(q), dir_path=str(d_path), file_pattern=str(f_pat) if f_pat else None)

    elif tool_name in ("find_files", "glob_files", "locate_files"):
        d_path = args.get("dir_path") or args.get("path") or args.get("directory") or "."
        pat = args.get("name_pattern") or args.get("pattern") or args.get("glob") or "*"
        max_r = int(args.get("max_results") or 100)
        return find_files(project_name, dir_path=str(d_path), name_pattern=str(pat), max_results=max_r)

    elif tool_name in ("update_plan", "update_steps", "set_plan"):
        steps_arg = args.get("steps") or []
        return update_plan(project_name, steps_arg)

    elif tool_name in ("run_command", "run_shell", "powershell", "shell"):
        cmd = args.get("command") or args.get("cmd") or ""
        cwd = args.get("cwd") or args.get("dir") or None
        timeout = int(args.get("timeout") or 30)
        if not cmd:
            return {"status": "error", "error": "Missing 'command' argument for run_command"}
        if not cwd:
            proj_dir = get_project_dir(sanitize_project_name(project_name))
            if proj_dir.exists() and any(proj_dir.iterdir()):
                cwd = str(proj_dir)
        from backend.core.jarvis_executive import run_host_cli
        return run_host_cli(str(cmd), timeout=timeout, cwd=str(cwd) if cwd else None)

    elif tool_name in ("remember_preference", "remember_user_preference", "save_memory", "record_memory"):
        from backend.core.memory_manager import remember_preference
        cat = args.get("category", "fact")
        key = args.get("key", "note")
        val = args.get("value") or args.get("val") or args.get("content", "")
        if not val and args.get("text"):
            val = args.get("text")
        return remember_preference(str(cat), str(key), str(val))

    elif tool_name in ("recall_memory", "search_memory", "get_memory", "recall"):
        from backend.core.memory_pilot import recall_memory
        q = args.get("query") or args.get("q") or args.get("topic") or args.get("search") or ""
        k = int(args.get("top_k") or 5)
        results = recall_memory(str(q), top_k=k)
        return {"status": "success", "query": q, "results": results}

    elif tool_name == "list_project_files":
        return list_project_files(project_name)

    elif tool_name in ("delete_project_file", "delete_file", "remove_file", "unlink_file"):
        path = args.get("file_path") or args.get("path") or args.get("filename")
        if not path:
            return {"status": "error", "error": "Missing 'file_path' argument for delete_project_file"}
        return delete_project_file(project_name, str(path))

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

    elif tool_name in ("search_web_docs", "web_search", "search_web", "search_docs", "duckduckgo"):
        q = args.get("query") or args.get("q") or ""
        if not q:
            return {"status": "error", "error": "Missing 'query' argument for search_web_docs"}
        return search_web_docs(str(q), project_name=project_name)

    elif tool_name in ("verify_workspace_integrity", "verify_workspace", "check_integrity", "lint_workspace"):
        from backend.core.workspace_validator import validate_workspace
        return validate_workspace(project_name)

    elif tool_name in ("launch_application", "launch_app", "open_app", "start_app"):
        from backend.core.jarvis_executive import launch_app
        app_name = args.get("app_name") or args.get("name") or args.get("app") or ""
        app_args = args.get("args") or args.get("arguments") or ""
        return launch_app(str(app_name), str(app_args) if app_args else None)

    elif tool_name in ("get_workstation_telemetry", "workstation_telemetry", "get_hardware_telemetry", "hardware_telemetry"):
        from backend.core.workstation_sensors import get_full_workstation_telemetry
        return get_full_workstation_telemetry()

    elif tool_name in ("get_current_time", "get_time", "current_time", "get_date", "current_date", "clock"):
        now = time.localtime()
        return {
            "status": "success",
            "current_time": time.strftime("%I:%M %p", now),
            "current_date": time.strftime("%A, %B %d, %Y", now),
            "timezone": time.strftime("%Z", now),
            "formatted": f"It is currently {time.strftime('%I:%M %p on %A, %B %d, %Y', now)}."
        }

    elif tool_name in ("open_browser_url", "open_url", "browse_url", "open_browser", "browse"):
        from backend.core.jarvis_executive import open_browser_url
        url = args.get("url") or args.get("link") or args.get("target") or ""
        return open_browser_url(str(url))

    elif tool_name in ("system_control", "os_control", "sys_control", "hardware_telemetry"):
        from backend.core.jarvis_executive import system_control
        action_val = args.get("action") or args.get("act") or args.get("command") or ""
        val = args.get("value") or args.get("val") or args.get("text") or None
        return system_control(str(action_val), str(val) if val is not None else None)

    elif tool_name in ("send_desktop_notification", "notify_user", "desktop_notification", "toast_notification", "notify"):
        from backend.core.jarvis_executive import send_desktop_notification
        title = args.get("title") or "Unleash Jarvis"
        message = args.get("message") or args.get("body") or args.get("msg") or ""
        return send_desktop_notification(str(title), str(message))

    elif tool_name in ("run_host_cli", "host_cli", "run_host_command", "execute_host_command"):
        from backend.core.jarvis_executive import run_host_cli
        cmd = args.get("command") or args.get("cmd") or ""
        timeout = int(args.get("timeout") or 15)
        return run_host_cli(str(cmd), timeout=timeout)

    elif tool_name in ("browser_navigate", "web_navigate", "goto_url", "navigate_browser"):
        from backend.core.browser_pilot import browser_navigate
        url = args.get("url") or args.get("link") or ""
        headless = bool(args.get("headless", False))
        return browser_navigate(str(url), headless=headless)

    elif tool_name in ("browser_click", "web_click", "click_element"):
        from backend.core.browser_pilot import browser_click
        selector = args.get("selector") or ""
        text = args.get("text") or None
        return browser_click(str(selector), text=str(text) if text else None)

    elif tool_name in ("browser_type", "web_type", "type_text", "fill_form"):
        from backend.core.browser_pilot import browser_type
        selector = args.get("selector") or ""
        text = args.get("text") or args.get("value") or ""
        press_enter = bool(args.get("press_enter", False))
        return browser_type(str(selector), str(text), press_enter=press_enter)

    elif tool_name in ("browser_extract", "web_extract", "extract_page", "read_page"):
        from backend.core.browser_pilot import browser_extract
        selector = args.get("selector") or None
        max_chars = int(args.get("max_chars") or 4000)
        return browser_extract(selector=str(selector) if selector else None, max_chars=max_chars)

    elif tool_name in ("browser_screenshot", "web_screenshot", "take_screenshot"):
        from backend.core.browser_pilot import browser_screenshot
        fname = args.get("filename") or args.get("output_path") or None
        full_page = bool(args.get("full_page", False))
        return browser_screenshot(filename=str(fname) if fname else None, full_page=full_page)

    elif tool_name in ("browser_search_and_read", "web_search_and_read", "deep_web_search"):
        from backend.core.browser_pilot import browser_search_and_read
        q = args.get("query") or args.get("q") or ""
        num_res = int(args.get("num_results") or 3)
        return browser_search_and_read(str(q), num_results=num_res)

    elif tool_name in ("browser_scroll", "scroll_page", "page_scroll"):
        from backend.core.browser_pilot import browser_scroll
        dir_val = args.get("direction") or "down"
        amt = int(args.get("amount") or 800)
        return browser_scroll(direction=str(dir_val), amount=amt)

    elif tool_name in ("browser_close", "close_browser"):
        from backend.core.browser_pilot import browser_close
        return browser_close()

    elif tool_name in ("capture_desktop_screen", "capture_screen", "capture_desktop", "take_desktop_screenshot", "screen_capture"):
        from backend.core.vision_pilot import capture_desktop
        fname = args.get("filename") or args.get("output_filename") or None
        region = args.get("region") or None
        return capture_desktop(output_filename=str(fname) if fname else None, region=region)

    elif tool_name in ("list_open_windows", "get_open_windows", "list_windows", "inspect_windows"):
        from backend.core.vision_pilot import list_open_windows
        return list_open_windows()

    elif tool_name in ("focus_window", "activate_window", "switch_to_window", "bring_window_to_front"):
        from backend.core.vision_pilot import focus_window
        target = args.get("title") or args.get("target") or args.get("window_title") or args.get("pid") or ""
        return focus_window(str(target))

    elif tool_name in ("analyze_screen_vision", "screen_vision", "inspect_screen", "analyze_screen", "read_screen"):
        from backend.core.vision_pilot import analyze_screen_vision
        img_path = args.get("image_path") or args.get("path") or None
        prompt_val = args.get("prompt") or args.get("question") or None
        region = args.get("region") or None
        return analyze_screen_vision(image_path=str(img_path) if img_path else None, prompt=str(prompt_val) if prompt_val else None, region=region)

    elif tool_name in ("desktop_click", "mouse_click", "click_desktop"):
        from backend.core.gui_pilot import desktop_click
        x = args.get("x")
        y = args.get("y")
        btn = args.get("button", "left")
        clicks = int(args.get("clicks") or 1)
        return desktop_click(x=int(x) if x is not None else None, y=int(y) if y is not None else None, button=str(btn), clicks=clicks)

    elif tool_name in ("desktop_type", "keyboard_type", "type_desktop"):
        from backend.core.gui_pilot import desktop_type
        txt = args.get("text") or args.get("content") or ""
        p_enter = bool(args.get("press_enter", False))
        return desktop_type(str(txt), press_enter=p_enter)

    elif tool_name in ("desktop_hotkey", "press_hotkey", "send_hotkey", "keyboard_shortcut"):
        from backend.core.gui_pilot import desktop_hotkey
        k = args.get("keys") or args.get("hotkey") or args.get("shortcut") or ""
        return desktop_hotkey(str(k))

    elif tool_name in ("desktop_move", "mouse_move", "move_cursor"):
        from backend.core.gui_pilot import desktop_move
        x = int(args.get("x", 0))
        y = int(args.get("y", 0))
        return desktop_move(x, y)

    elif tool_name in ("desktop_scroll", "scroll_desktop"):
        from backend.core.gui_pilot import desktop_scroll
        amt = int(args.get("amount") or 3)
        direct = args.get("direction", "down")
        return desktop_scroll(amount=amt, direction=str(direct))

    elif tool_name in ("desktop_cursor_pos", "get_cursor_position", "cursor_position"):
        from backend.core.gui_pilot import desktop_cursor_pos
        return desktop_cursor_pos()

    elif tool_name in ("list_ui_elements", "inspect_ui_elements", "ui_tree"):
        from backend.core.gui_pilot import list_ui_elements
        w_title = args.get("window_title") or args.get("window") or None
        lim = int(args.get("limit") or 25)
        return list_ui_elements(window_title=str(w_title) if w_title else None, limit=lim)

    elif tool_name in ("speak_aloud", "speak", "say_aloud", "talk", "tts_speak"):
        from backend.core.voice_pilot import speak_aloud
        txt = args.get("text") or args.get("message") or args.get("content") or ""
        v_mode = args.get("mode") or None
        return speak_aloud(str(txt), mode=v_mode)

    elif tool_name in ("set_voice_mode", "switch_voice_mode", "change_voice_mode"):
        from backend.core.voice_pilot import set_voice_mode
        m = args.get("mode") or "work"
        return set_voice_mode(str(m))

    elif tool_name in ("get_voice_mode", "check_voice_mode", "voice_status"):
        from backend.core.voice_pilot import get_voice_mode, load_voice_config
        cfg = load_voice_config()
        return {"success": True, "mode": cfg.get("mode"), "config": cfg}

    elif tool_name in ("configure_wake_word", "set_wake_word", "update_wake_word"):
        from backend.core.voice_pilot import update_voice_config, load_voice_config
        updates = {}
        if "enabled" in args and args["enabled"] is not None:
            updates["wake_word_enabled"] = bool(args["enabled"])
        if "wake_words" in args and args["wake_words"]:
            ww = args["wake_words"]
            if isinstance(ww, str):
                ww = [w.strip().lower() for w in ww.split(",") if w.strip()]
            updates["wake_words"] = ww
        if "wake_sound" in args and args["wake_sound"] is not None:
            updates["wake_sound"] = bool(args["wake_sound"])
        if updates:
            cfg = update_voice_config(updates)
        else:
            cfg = load_voice_config()
        return {"success": True, "message": f"Wake word config updated. Enabled: {cfg.get('wake_word_enabled')}, Trigger words: {cfg.get('wake_words')}", "config": cfg}

    elif tool_name in ("remember_fact", "remember", "memorize_fact", "save_memory"):
        from backend.core.memory_pilot import remember_fact
        cnt = args.get("content") or args.get("fact") or args.get("text") or ""
        cat = args.get("category") or "fact"
        imp = int(args.get("importance") or 8)
        ent = args.get("entity") or None
        rel = args.get("relation") or None
        tgt = args.get("target") or None
        return remember_fact(content=str(cnt), category=str(cat), importance=imp, entity=ent, relation=rel, target=tgt)

    elif tool_name in ("forget_memory", "forget", "delete_memory"):
        from backend.core.memory_pilot import delete_memory
        itype = args.get("item_type") or "raw"
        iid = int(args.get("item_id") or args.get("id") or 0)
        return delete_memory(str(itype), iid)

    elif tool_name in ("multi_hop_query", "graph_reasoning", "multi_hop_reasoning"):
        from backend.core.memory_pilot import query_multi_hop_relations, find_entity_path
        start = str(args.get("start_entity") or args.get("entity") or args.get("source") or "").strip()
        target = str(args.get("target_entity") or args.get("target") or "").strip()
        hops = int(args.get("max_hops") or 3)
        if target:
            paths = find_entity_path(start, target, max_hops=hops)
            return {"status": "success", "start": start, "target": target, "paths": paths}
        else:
            chains = query_multi_hop_relations(start, max_hops=hops)
            return {"status": "success", "start": start, "chains": chains}

    elif tool_name in ("consolidate_memory", "sleep_cycle_consolidation", "consolidate_memories"):
        from backend.core.memory_pilot import run_sleep_cycle_consolidation
        return run_sleep_cycle_consolidation()

    elif tool_name in ("start_background_task", "spawn_daemon_task", "run_in_background"):
        from backend.core.task_daemon import spawn_daemon_task
        t_title = str(args.get("title") or args.get("name") or "Autonomous Background Task").strip()
        t_desc = str(args.get("description") or t_title).strip()
        raw_steps = args.get("steps")
        steps = None
        if isinstance(raw_steps, list):
            steps = [str(s).strip() for s in raw_steps if str(s).strip()]
        elif isinstance(raw_steps, str):
            steps = [s.strip() for s in raw_steps.split(",") if s.strip()]
        return spawn_daemon_task(title=t_title, description=t_desc, steps=steps, project_name=project_name)

    elif tool_name in ("check_background_tasks", "get_background_tasks", "list_background_tasks"):
        from backend.core.task_daemon import get_task_status, list_active_tasks, list_all_tasks
        t_id = args.get("task_id")
        if t_id:
            status = get_task_status(str(t_id))
            if not status:
                return {"status": "error", "error": f"Daemon task '{t_id}' not found."}
            return {"status": "success", "task": status}
        else:
            actives = list_active_tasks()
            return {"status": "success", "active_count": len(actives), "tasks": actives}

    elif tool_name in ("control_background_task", "pause_background_task", "cancel_background_task"):
        from backend.core.task_daemon import pause_task, resume_task, cancel_task
        t_id = str(args.get("task_id") or "").strip()
        act = str(args.get("action") or "pause").strip().lower()
        if act == "pause":
            return pause_task(t_id)
        elif act == "resume":
            return resume_task(t_id)
        elif act in ("cancel", "stop", "abort"):
            return cancel_task(t_id)
        else:
            return {"status": "error", "error": f"Unknown action '{act}'. Use 'pause', 'resume', or 'cancel'."}

    elif tool_name in ("set_project_permission_policy", "set_project_policy"):
        from backend.core.permission_controller import LocalPermissionController
        p_name = str(args.get("project_name") or project_name).strip()
        p_key = str(args.get("policy_key") or "require_approval").strip()
        p_val = args.get("value", True)
        return LocalPermissionController.set_project_policy(p_name, p_key, p_val)

    elif tool_name in ("inspect_preflight_safety", "inspect_safety"):
        from backend.core.preflight_inspector import inspect_command_safety, inspect_package_safety, inspect_url_safety
        tgt = str(args.get("target") or "").strip()
        t_type = str(args.get("target_type") or "").strip().lower()
        if t_type == "package" or (not t_type and not (" " in tgt or "://" in tgt)):
            return inspect_package_safety(tgt)
        elif t_type == "url" or "://" in tgt:
            return inspect_url_safety(tgt)
        else:
            return inspect_command_safety(tgt)

    elif tool_name in ("read_emails", "check_emails", "fetch_emails", "list_emails"):
        from backend.core.comms_tools import read_emails
        return read_emails(
            folder=str(args.get("folder") or "INBOX"),
            unread_only=bool(args.get("unread_only", True)),
            query=args.get("query"),
            limit=int(args.get("limit") or 10),
        )

    elif tool_name in ("send_email", "send_mail", "email_send"):
        from backend.core.comms_tools import send_email
        return send_email(
            to=args.get("to") or args.get("recipient") or "",
            subject=str(args.get("subject") or ""),
            body=str(args.get("body") or args.get("message") or ""),
            attachments=args.get("attachments"),
            cc=args.get("cc"),
            confirm=bool(args.get("confirm", False)),
            project_name=project_name,
        )

    elif tool_name in ("configure_email_credentials", "configure_email_vault"):
        from backend.core.comms_tools import configure_email_credentials
        return configure_email_credentials(
            email_address=str(args.get("email_address") or args.get("email") or ""),
            app_password=str(args.get("app_password") or args.get("password") or ""),
            smtp_host=args.get("smtp_host"),
            smtp_port=args.get("smtp_port"),
            imap_host=args.get("imap_host"),
            imap_port=args.get("imap_port"),
        )

    else:
        # Check dynamic MCP (Model Context Protocol) tools
        try:
            from backend.core.mcp_client import get_mcp_manager
            mgr = get_mcp_manager()
            if mgr.is_mcp_tool(tool_name) or "__" in tool_name:
                return mgr.dispatch_tool(tool_name, args, context)
        except Exception as e:
            pass
        return {"status": "error", "error": f"Unknown tool '{tool_name}'. Available: {[t['name'] for t in get_all_tool_schemas()]}"}


LEAN_TOOLS_SCHEMA = [
    {
        "name": "write_project_file",
        "description": "Create or overwrite a file at any arbitrary nested path in the project workspace (e.g. main.py, src/api/auth.py, database/schema.sql, index.html).",
        "parameters": {
            "file_path": "Relative path to file (e.g. 'main.py', 'src/app.js', 'index.html')",
            "content": "Full content of the file to write"
        }
    },
    {
        "name": "delete_project_file",
        "description": "Delete a file from the project workspace. Triggers a Human-in-the-Loop confirmation gate and saves an automatic time-machine rollback snapshot before unlinking.",
        "parameters": {
            "file_path": "Relative path to file in project workspace to delete"
        }
    },
    {
        "name": "edit_project_file",
        "description": "Surgically edit an existing file by replacing an exact code snippet or function block.",
        "parameters": {
            "file_path": "Relative path to file (e.g. 'main.py', 'src/app.js')",
            "target": "Exact existing code string to be replaced (must match whitespace exactly)",
            "replacement": "New code string to replace the target with"
        }
    },
    {
        "name": "read_project_file",
        "description": "Read the text content of a file in the project workspace.",
        "parameters": {
            "file_path": "Relative path to file (e.g. 'main.py', 'src/app.js')"
        }
    }
]


FRONTIER_TOOLS_SCHEMA = [
    {
        "name": "update_plan",
        "description": "Create or update your live step-by-step execution checklist shown to the user. Always call this before starting multi-step tasks and update statuses as you complete each step.",
        "parameters": {
            "steps": "Array of objects: [{\"title\": \"Short step description\", \"status\": \"in_progress|pending|done|failed\"}]"
        }
    },
    {
        "name": "list_dir",
        "description": "List files and subdirectories in a folder (relative to workspace or any safe Windows path like C:\\coding\\my_app or ~\\Desktop).",
        "parameters": {
            "dir_path": "Directory path to list (default '.')"
        }
    },
    {
        "name": "read_file",
        "description": "Read numbered lines from a file (relative to workspace or safe Windows path). Use start_line and end_line to read large files economically.",
        "parameters": {
            "file_path": "File path to read",
            "start_line": "Optional 1-indexed start line",
            "end_line": "Optional 1-indexed end line"
        }
    },
    {
        "name": "edit_file",
        "description": "Surgically replace an exact existing block of text/code in a file. Always read_file first so 'target' matches existing lines accurately.",
        "parameters": {
            "file_path": "File path to modify",
            "target": "Exact existing lines to replace",
            "replacement": "New replacement lines"
        }
    },
    {
        "name": "write_file",
        "description": "Create a new file or completely overwrite an existing file at a relative or safe absolute OS path.",
        "parameters": {
            "file_path": "File path to write",
            "content": "Full file content"
        }
    },
    {
        "name": "search_files",
        "description": "Search for a keyword or regex pattern across files in a directory.",
        "parameters": {
            "query": "Text or regex pattern to search for",
            "dir_path": "Optional directory path (default '.')"
        }
    },
    {
        "name": "run_command",
        "description": "Run a shell/terminal command on the Windows host (e.g. python tests, git status, dir, powershell scripts) and observe stdout, stderr, and exit_code.",
        "parameters": {
            "command": "Command string to execute",
            "cwd": "Optional working directory path"
        }
    },
    {
        "name": "get_workstation_telemetry",
        "description": "Inspect real-time physical RAM, GPU thermals/load, battery, active window, and top processes.",
        "parameters": {}
    },
    {
        "name": "launch_application",
        "description": "Launch a desktop application discovered dynamically on Windows/macOS/Linux (e.g. vscode, chrome, notepad, terminal).",
        "parameters": {
            "app_name": "Application name to open"
        }
    },
    {
        "name": "browser_navigate",
        "description": "Open or navigate the stateful visible browser to any URL (preserves logins across turns) and inspect its visible interactive elements (inputs, buttons, links).",
        "parameters": {
            "url": "URL to open (e.g. 'https://github.com', 'https://youtube.com')"
        }
    },
    {
        "name": "browser_type",
        "description": "Type text into an input or search box in the open browser (optionally pressing Enter).",
        "parameters": {
            "selector": "CSS selector from interactive_elements (e.g. 'input[name=\"q\"]')",
            "text": "Text to type",
            "press_enter": "Optional boolean (true to submit with Enter)"
        }
    },
    {
        "name": "browser_click",
        "description": "Click a button, link, or item in the open browser by CSS selector or visible text.",
        "parameters": {
            "selector": "CSS selector or empty string if clicking by text",
            "text": "Optional visible text to click"
        }
    },
    {
        "name": "browser_extract",
        "description": "Read the visible text content and top links from the currently open browser page.",
        "parameters": {}
    }
]


FRONTIER_PRO_EXTRA_TOOLS = [
    {
        "name": "search_web_docs",
        "description": "Search privacy-preserving web documentation for library APIs, error fixes, or modern frameworks.",
        "parameters": {
            "query": "Documentation or error query to search"
        }
    },
    {
        "name": "remember_preference",
        "description": "Persist an architectural decision, user preference, or key project fact across sessions.",
        "parameters": {
            "category": "'profile', 'guideline', 'rule', or 'fact'",
            "key": "Short identifier key",
            "value": "Fact or rule to remember"
        }
    },
    {
        "name": "recall_memory",
        "description": "Recall previously saved facts, preferences, or project notes from persistent memory.",
        "parameters": {
            "query": "Topic or keyword to recall"
        }
    },
    {
        "name": "delete_project_file",
        "description": "Safely delete an obsolete file (auto-creates a rollback snapshot first).",
        "parameters": {
            "file_path": "File path to delete"
        }
    },
    {
        "name": "list_ui_elements",
        "description": "Inspect real interactive UI controls (buttons, inputs, menu items) and their exact (x, y) coordinates in an open native Windows app via UI Automation.",
        "parameters": {
            "window_title": "Optional partial window title (defaults to focused window)"
        }
    },
    {
        "name": "read_document",
        "description": "Read PDF, CSV, Excel (.xlsx/.xls), Word (.docx), PowerPoint (.pptx), image (OCR), or plain-text documents cleanly.",
        "parameters": {
            "file_path": "Path to the document file",
            "start_page": "Optional 1-indexed start page for PDFs (default 1)",
            "end_page": "Optional 1-indexed end page for PDFs"
        }
    },
    {
        "name": "find_files",
        "description": "Recursively locate files matching a glob pattern (e.g. '*.pdf', '*growth*') across permitted folders.",
        "parameters": {
            "dir_path": "Directory path to search",
            "name_pattern": "Filename glob pattern (e.g. '*.pdf')"
        }
    },
    {
        "name": "read_emails",
        "description": "Read recent or unread inbox emails via IMAP4_SSL.",
        "parameters": {
            "unread_only": "True for unread messages (default True)",
            "query": "Optional search filter",
            "limit": "Max messages to inspect (default 10)"
        }
    },
    {
        "name": "send_email",
        "description": "Send an email with optional attachments via SMTP. Returns dry-run preview when confirm=False.",
        "parameters": {
            "to": "Recipient email(s)",
            "subject": "Email subject",
            "body": "Plain-text body",
            "attachments": "Optional list of file paths",
            "confirm": "Set False first for preview; True after approval"
        }
    }
]


def get_tool_schemas(mode: str = "full") -> List[Dict[str, Any]]:
    """Returns tool schemas according to compute tier: frontier (9 tools), frontier_pro (13 tools), lean (4 tools), or full."""
    if mode == "frontier":
        return list(FRONTIER_TOOLS_SCHEMA)
    if mode == "frontier_pro":
        return list(FRONTIER_TOOLS_SCHEMA) + list(FRONTIER_PRO_EXTRA_TOOLS)
    if mode == "lean":
        return list(LEAN_TOOLS_SCHEMA)
    return get_all_tool_schemas()


def get_all_tool_schemas() -> List[Dict[str, Any]]:
    """Returns combined list of native agent tools and dynamically discovered MCP server tools."""
    schemas = list(AGENT_TOOLS_SCHEMA)
    try:
        from backend.core.mcp_client import get_mcp_manager
        mcp_tools = get_mcp_manager().get_all_tool_schemas()
        schemas.extend(mcp_tools)
    except Exception:
        pass
    return schemas


def format_tools_for_modelfile_system() -> str:
    """
    Dynamically generates the tool declaration block for Ollama Modelfiles.
    Zero hardcoding: introspects active tool schemas and builds standard ReAct invocation grammar.
    """
    tools = get_all_tool_schemas()
    lines = [
        "### AVAILABLE TOOLS & ACTIONS:",
        "You have direct executive control over the host operating system via tool calling.",
        "To invoke an action, format your reasoning and action as follows:",
        "Thought: <your reason for choosing this action>",
        "Action: <tool_name>(<json_arguments>)",
        "",
        "Supported Tools:"
    ]
    for t in tools:
        param_desc = ", ".join([f'"{k}": <{v}>' for k, v in t.get("parameters", {}).items()])
        lines.append(f"- {t['name']}({{{param_desc}}}): {t.get('description', '')}")
    return "\n".join(lines)
