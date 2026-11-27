"""
Verification Test Suite for Risk-Based Lazy On-Demand Docker Isolation:
1. Default `auto_start_docker` is False (`sandbox_config.json` absent or False).
2. `startup_event()` skips Docker launch when `auto_start_docker` is False, and triggers it only when True.
3. LOW-risk Python executes in `WindowsJobManager` without booting Docker Desktop.
4. HIGH-risk / dangerous scripts (`subprocess`, `pwntools`, `ctypes`) set `requires_docker=True`, invoke lazy `ensure_docker_ready()`, and FAIL CLOSED if Docker stays offline.
5. `CRITICAL` destructive commands stay blocked before execution.
6. `/api/chat/sandbox/docker/status` & `/api/chat/sandbox/docker/auto_start` REST contracts work cleanly.
"""

import sys
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_default_auto_start_and_startup_gate():
    print("\n[1/5] Testing startup_event() skips Docker when auto_start_docker is False...")
    from backend.core import sandbox
    from backend.api import main as api_main

    had_cfg = sandbox.SANDBOX_CONFIG_FILE.exists()
    prev_cfg = sandbox.SANDBOX_CONFIG_FILE.read_text(encoding="utf-8") if had_cfg else None
    try:
        if sandbox.SANDBOX_CONFIG_FILE.exists():
            sandbox.SANDBOX_CONFIG_FILE.unlink()
        assert sandbox.get_docker_auto_start() is False, "Default auto_start_docker must be False"

        # Verify startup_event does NOT call ensure_docker_daemon_async when OFF
        with patch.object(sandbox, "ensure_docker_daemon_async") as mock_docker, \
             patch("backend.api.chat_router.ensure_ollama_daemon"), \
             patch("backend.core.task_daemon.start_proactive_watchdog_loop"):
            api_main.startup_event()
            assert not mock_docker.called, "Docker must NOT launch on startup when auto_start_docker is False"

        # Enable auto_start_docker and confirm startup_event DOES launch it
        sandbox.set_docker_auto_start(True)
        with patch.object(sandbox, "ensure_docker_daemon_async") as mock_docker, \
             patch("backend.api.chat_router.ensure_ollama_daemon"), \
             patch("backend.core.task_daemon.start_proactive_watchdog_loop"):
            api_main.startup_event()
            assert mock_docker.called, "Docker should launch on startup when user explicitly enabled auto_start_docker"
        print("PASS: Unleash startup cleanly gates Docker behind auto_start_docker setting.")
    finally:
        if had_cfg and prev_cfg is not None:
            sandbox.SANDBOX_CONFIG_FILE.write_text(prev_cfg, encoding="utf-8")
        elif sandbox.SANDBOX_CONFIG_FILE.exists():
            sandbox.SANDBOX_CONFIG_FILE.unlink()


def test_low_risk_runs_without_docker():
    print("\n[2/5] Testing LOW-risk Python runs locally without booting Docker...")
    from backend.core import sandbox

    with patch.object(sandbox, "is_docker_available", return_value=False), \
         patch.object(sandbox, "ensure_docker_ready") as mock_lazy:
        res = sandbox.execute_in_sandbox("print(2 + 40)", language="python")
        assert res["status"] == "success", f"Expected success, got {res}"
        assert "42" in res["stdout"]
        assert not mock_lazy.called, "LOW-risk Python must NOT trigger Docker startup"
        assert res["engine"] in ("windows_job_object", "process_jail")
    print(f"PASS: LOW-risk script ran via {res['engine']} with zero Docker calls.")


def test_high_risk_lazy_docker_and_fail_closed():
    print("\n[3/5] Testing HIGH-risk script triggers lazy Docker & fails closed if unavailable...")
    from backend.core import sandbox

    risky_code = "import subprocess\nprint(subprocess.run(['whoami'], capture_output=True))"
    safety = sandbox.inspect_code_safety(risky_code, "python")
    assert safety["safe_to_execute"] is True
    assert safety["risk_level"] == "HIGH"
    assert safety["requires_docker"] is True

    # Offline & cannot boot -> MUST fail closed (never fall through to Windows host!)
    with patch.object(sandbox, "is_docker_available", return_value=False), \
         patch.object(sandbox, "ensure_docker_ready", return_value=False) as mock_lazy:
        res_blocked = sandbox.execute_in_sandbox(risky_code, language="python")
        assert mock_lazy.called, "HIGH-risk script MUST call ensure_docker_ready()"
        assert res_blocked["status"] == "blocked", f"Expected fail-closed block, got {res_blocked}"
        assert "Docker container isolation" in res_blocked["stderr"]

    # Comes online lazily -> executes inside mocked Docker path
    with patch.object(sandbox, "is_docker_available", return_value=False), \
         patch.object(sandbox, "ensure_docker_ready", return_value=True), \
         patch.object(sandbox, "execute_in_docker", return_value={
             "status": "success",
             "exit_code": 0,
             "stdout": "nobody\n",
             "stderr": "",
             "duration_ms": 12.0,
             "engine": "docker",
             "engine_detail": "Docker Linux Container",
         }) as mock_exec:
        res_ok = sandbox.execute_in_sandbox(risky_code, language="python")
        assert mock_exec.called and res_ok["engine"] == "docker"
    print("PASS: HIGH-risk lazy Docker start and fail-closed isolation verified.")


def test_critical_blocked_immediately():
    print("\n[4/5] Testing CRITICAL destructive commands remain blocked before execution...")
    from backend.core import sandbox

    with patch.object(sandbox, "ensure_docker_ready") as mock_lazy:
        res = sandbox.execute_in_sandbox("import os; os.system('shutdown /s /t 0')", language="python")
        assert res["status"] == "blocked"
        assert res["risk_level"] == "CRITICAL"
        assert not mock_lazy.called, "CRITICAL commands must block before touching Docker"
    print("PASS: CRITICAL destructive commands blocked immediately at AST/Policy gate.")


def test_docker_auto_start_rest_endpoints():
    print("\n[5/5] Testing /api/chat/sandbox/docker/auto_start & status endpoints...")
    from starlette.testclient import TestClient
    from backend.api.main import app
    from backend.core import sandbox

    had_cfg = sandbox.SANDBOX_CONFIG_FILE.exists()
    prev_cfg = sandbox.SANDBOX_CONFIG_FILE.read_text(encoding="utf-8") if had_cfg else None
    client = TestClient(app)
    try:
        r_on = client.post("/api/chat/sandbox/docker/auto_start", json={"enabled": True})
        assert r_on.status_code == 200 and r_on.json()["enabled"] is True

        r_get = client.get("/api/chat/sandbox/docker/auto_start")
        assert r_get.status_code == 200 and r_get.json()["enabled"] is True

        r_stat = client.get("/api/chat/sandbox/docker/status")
        assert r_stat.status_code == 200 and r_stat.json()["auto_start"] is True

        r_off = client.post("/api/chat/sandbox/docker/auto_start", json={"enabled": False})
        assert r_off.status_code == 200 and r_off.json()["enabled"] is False

        # Verify /api/daemon/app/shutdown stops Ollama & Docker cleanly
        import subprocess
        import threading
        with patch.object(subprocess, "run") as mock_run, \
             patch.object(threading, "Timer") as mock_timer:
            mock_timer.return_value.start.return_value = None
            r_app_off = client.post("/api/daemon/app/shutdown")
            assert r_app_off.status_code == 200 and r_app_off.json()["status"] == "success"
            cmds = [" ".join(c.args[0]) for c in mock_run.call_args_list if c.args]
            assert any("ollama.exe" in c for c in cmds), f"Expected ollama.exe teardown in {cmds}"
            assert any("Docker Desktop.exe" in c for c in cmds), f"Expected Docker Desktop.exe teardown in {cmds}"
            assert mock_timer.called

        # Verify FastAPI shutdown_event() (Ctrl+C in VS Code) triggers full cleanup too
        from backend.api import main as api_main
        with patch("backend.api.daemon_router.cleanup_all_runtime_processes") as mock_clean:
            api_main.shutdown_event()
            assert mock_clean.called, "Ctrl+C shutdown_event must invoke cleanup_all_runtime_processes()"
        print("PASS: Docker auto_start REST toggle, /app/shutdown, & Ctrl+C shutdown_event verified.")
    finally:
        if had_cfg and prev_cfg is not None:
            sandbox.SANDBOX_CONFIG_FILE.write_text(prev_cfg, encoding="utf-8")
        elif sandbox.SANDBOX_CONFIG_FILE.exists():
            sandbox.SANDBOX_CONFIG_FILE.unlink()


if __name__ == "__main__":
    print("=" * 64)
    print("UNLEASH-AGENT LAZY ON-DEMAND DOCKER VERIFICATION SUITE")
    print("=" * 64)
    test_default_auto_start_and_startup_gate()
    test_low_risk_runs_without_docker()
    test_high_risk_lazy_docker_and_fail_closed()
    test_critical_blocked_immediately()
    test_docker_auto_start_rest_endpoints()
    print("\nALL 5 LAZY DOCKER VERIFICATION SUITES PASSED.")
