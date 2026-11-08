import os

chat_router_path = r"c:\coding\ai-trainer\backend\api\chat_router.py"
with open(chat_router_path, "r", encoding="utf-8") as f:
    text = f.read()

normalized = text.replace("\r\n", "\n")

target = """@router.get("/agent/projects/{project_name}/file")
def get_project_single_file_endpoint(project_name: str, file_path: str):
    \"\"\"Reads a specific file from an agent project safely.\"\"\"
    from backend.core.agent_tools import read_project_file
    return read_project_file(project_name, file_path)"""

replacement = r'''@router.get("/agent/projects/{project_name}/file")
def get_project_single_file_endpoint(project_name: str, file_path: str):
    """Reads a specific file from an agent project safely."""
    from backend.core.agent_tools import read_project_file
    return read_project_file(project_name, file_path)


@router.get("/agent/projects/{project_name}/preview/{file_path:path}")
def preview_project_file_endpoint(project_name: str, file_path: str):
    """Serves static project files (HTML, CSS, JS, images) directly for live browser preview."""
    import mimetypes
    from fastapi.responses import FileResponse
    from backend.core.agent_tools import resolve_safe_project_path

    safe_path = resolve_safe_project_path(project_name, file_path)
    if not safe_path.exists() or not safe_path.is_file():
        raise HTTPException(status_code=404, detail=f"File '{file_path}' not found in project.")

    mime_type, _ = mimetypes.guess_type(str(safe_path))
    if safe_path.suffix == ".css":
        mime_type = "text/css"
    elif safe_path.suffix == ".js":
        mime_type = "application/javascript"
    elif safe_path.suffix == ".html":
        mime_type = "text/html"

    return FileResponse(path=safe_path, media_type=mime_type or "application/octet-stream")


@router.get("/agent/projects/{project_name}/preview")
def preview_project_root_endpoint(project_name: str):
    """Serves the root index.html file for live browser rendering."""
    return preview_project_file_endpoint(project_name, "index.html")


@router.post("/agent/projects/{project_name}/open_vscode")
def open_project_vscode_endpoint(project_name: str):
    """Launches VS Code directly opening the generated workspace project directory."""
    import subprocess
    import shutil
    from backend.core.agent_tools import PROJECTS_ROOT, sanitize_project_name

    clean_proj = sanitize_project_name(project_name)
    proj_dir = (PROJECTS_ROOT / clean_proj).resolve()
    if not proj_dir.exists():
        raise HTTPException(status_code=404, detail=f"Project workspace '{clean_proj}' does not exist.")

    code_bin = shutil.which("code") or r"C:\Users\asopa\AppData\Local\Programs\Microsoft VS Code\bin\code.cmd"
    try:
        subprocess.Popen(f'"{code_bin}" "{str(proj_dir)}"', shell=True)
        return {
            "status": "success",
            "message": f"Opened workspace '{clean_proj}' in VS Code!",
            "path": str(proj_dir),
            "vscode_url": f"vscode://file/{str(proj_dir).replace('\\', '/')}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to launch VS Code: {str(e)}")


@router.post("/agent/projects/{project_name}/open_folder")
def open_project_folder_endpoint(project_name: str):
    """Opens the project directory in Windows Explorer."""
    import subprocess
    from backend.core.agent_tools import PROJECTS_ROOT, sanitize_project_name

    clean_proj = sanitize_project_name(project_name)
    proj_dir = (PROJECTS_ROOT / clean_proj).resolve()
    if not proj_dir.exists():
        raise HTTPException(status_code=404, detail=f"Project workspace '{clean_proj}' does not exist.")

    subprocess.Popen(f'explorer "{str(proj_dir)}"', shell=True)
    return {"status": "success", "path": str(proj_dir)}'''

if target in normalized:
    normalized = normalized.replace(target, replacement, 1)
    with open(chat_router_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(normalized)
    print("SUCCESS: chat_router.py updated with Live Preview & Open in VS Code endpoints.")
else:
    print("ERROR: Target not found in chat_router.py")
