#!/usr/bin/env bash
set -e

echo "====================================================================="
echo "  Unleash-Agent Studio (Air-Gapped Autonomous Runtime - macOS/Linux)"
echo "====================================================================="
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
export PYTHONPATH="$SCRIPT_DIR"

# 1. Pick Python interpreter (prefer active/local venv if present)
PYTHON_BIN="python3"
if [ -x "$SCRIPT_DIR/venv/bin/python" ]; then
    PYTHON_BIN="$SCRIPT_DIR/venv/bin/python"
elif ! command -v python3 >/dev/null 2>&1; then
    if command -v python >/dev/null 2>&1; then
        PYTHON_BIN="python"
    else
        echo "[ERROR] Python 3.10+ is not installed or not in PATH."
        exit 1
    fi
fi
echo "[*] Using Python: $($PYTHON_BIN --version)"

# 2. Check / start Ollama background daemon
if command -v ollama >/dev/null 2>&1; then
    if pgrep -x "ollama" >/dev/null 2>&1 || curl -s http://127.0.0.1:11434/api/version >/dev/null 2>&1; then
        echo "[OK] Ollama background daemon is active."
    else
        echo "[*] Launching Ollama daemon in background..."
        nohup ollama serve >/dev/null 2>&1 &
        sleep 2
    fi
else
    echo "[WARN] Ollama not found in PATH. Install from https://ollama.com for local models."
fi

# 3. Free stale port 8001 if occupied
if command -v lsof >/dev/null 2>&1; then
    STALE_PIDS=$(lsof -ti:8001 || true)
    if [ -n "$STALE_PIDS" ]; then
        echo "[*] Freeing port 8001 (terminating stale PID: $STALE_PIDS)..."
        kill -9 $STALE_PIDS >/dev/null 2>&1 || true
    fi
fi

# 4. Open browser cleanly (macOS: open, Linux: xdg-open)
echo "[*] Launching Unleash-Agent Studio UI at http://localhost:8001 ..."
if command -v open >/dev/null 2>&1; then
    (sleep 2 && open "http://localhost:8001") >/dev/null 2>&1 &
elif command -v xdg-open >/dev/null 2>&1; then
    (sleep 2 && xdg-open "http://localhost:8001") >/dev/null 2>&1 &
fi

# 5. Boot FastAPI Server
echo "[*] Booting Air-Gapped Executive API & Sensory Telemetry Engine..."
echo "====================================================================="
exec "$PYTHON_BIN" -m uvicorn backend.api.main:app --port 8001 --reload
