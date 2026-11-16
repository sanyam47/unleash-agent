import os

# Find the absolute root of the project (ai-trainer)
# This file is in backend/core/paths.py
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MODELS_DIR = os.path.join(BASE_DIR, "models")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
LAB_SESSIONS_DIR = os.path.join(BASE_DIR, "lab_sessions")

# Ensure all critical directories exist
for d in [MODELS_DIR, FRONTEND_DIR, UPLOADS_DIR, LAB_SESSIONS_DIR]:
    os.makedirs(d, exist_ok=True)


def get_ollama_base_url() -> str:
    return os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")

