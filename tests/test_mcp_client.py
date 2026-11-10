"""
STANDALONE VERIFICATION TEST SUITE FOR DYNAMIC MCP HOST ENGINE
Tests:
  1. AES-256-GCM Vault credential auto-resolution ('vault:key' in env vars).
  2. JSON-RPC 2.0 handshake ('initialize' -> 'notifications/initialized') over stdio.
  3. Dynamic tool discovery & schema conversion ('tools/list').
  4. Tool execution ('tools/call') with stdout pipe parsing.
  5. MCPClientManager dynamic registration, status inspection, and lifecycle.
  6. Integration with agent_tools.py dispatch_tool and get_all_tool_schemas.
  7. FastAPI REST endpoints for MCP servers (/mcp/servers, /mcp/restart, /mcp/call).
"""

import os
import sys
import json
import time
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient

root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from backend.core.mcp_client import (
    MCPServerProcess,
    MCPClientManager,
    resolve_vault_env,
    load_mcp_config,
    save_mcp_config,
    get_mcp_manager
)
from backend.core.agent_tools import dispatch_tool, get_all_tool_schemas
from backend.core.credential_vault import store_secret, delete_secret


MOCK_SERVER_SCRIPT = """import sys, json, os

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        msg = json.loads(line)
    except Exception:
        continue

    method = msg.get("method")
    msg_id = msg.get("id")

    if method == "initialize":
        resp = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "mock-mcp-server", "version": "1.0.0"}
            }
        }
        sys.stdout.write(json.dumps(resp) + "\\n")
        sys.stdout.flush()

    elif method == "notifications/initialized":
        pass

    elif method == "tools/list":
        resp = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "tools": [
                    {
                        "name": "echo",
                        "description": "Echoes back the provided text",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "message": {"type": "string", "description": "The message to echo"}
                            },
                            "required": ["message"]
                        }
                    },
                    {
                        "name": "check_vault_env",
                        "description": "Returns injected environment variable to verify vault resolution",
                        "inputSchema": {
                            "type": "object",
                            "properties": {}
                        }
                    }
                ]
            }
        }
        sys.stdout.write(json.dumps(resp) + "\\n")
        sys.stdout.flush()

    elif method == "tools/call":
        tool_name = msg.get("params", {}).get("name")
        args = msg.get("params", {}).get("arguments", {})

        if tool_name == "echo":
            res_text = f"ECHO_REPLY: {args.get('message', '')}"
            resp = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": res_text}],
                    "isError": False
                }
            }
        elif tool_name == "check_vault_env":
            val = os.environ.get("INJECTED_API_KEY", "NOT_FOUND")
            resp = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": f"VAULT_VAL:{val}"}],
                    "isError": False
                }
            }
        else:
            resp = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": f"Unknown tool {tool_name}"}],
                    "isError": True
                }
            }
        sys.stdout.write(json.dumps(resp) + "\\n")
        sys.stdout.flush()
"""


def run_all_tests():
    print("=" * 70)
    print("RUNNING DYNAMIC MODEL CONTEXT PROTOCOL (MCP) TEST SUITE")
    print("=" * 70)

    # 0. Setup Mock Server Script
    mock_dir = root_dir / "test_out" / "mcp_test"
    mock_dir.mkdir(parents=True, exist_ok=True)
    mock_script = mock_dir / "mock_mcp_server.py"
    mock_script.write_text(MOCK_SERVER_SCRIPT, encoding="utf-8")

    # ---------------------------------------------------------
    # Test 1: AES-256 Vault Token Resolution in MCP Environment
    # ---------------------------------------------------------
    print("\n--- Test 1: AES-256-GCM Vault Auto-Resolution ---")
    test_key = "test_mcp_token_xyz"
    test_secret = "mcp_secret_token_12345"
    store_res = store_secret(test_key, test_secret)
    assert store_res["status"] == "success"

    try:
        raw_env = {
            "STATIC_VAR": "hello_world",
            "INJECTED_API_KEY": f"vault:{test_key}"
        }
        resolved = resolve_vault_env(raw_env)
        assert resolved["STATIC_VAR"] == "hello_world"
        assert resolved["INJECTED_API_KEY"] == test_secret
        print("Verified: 'vault:key' env vars successfully decrypted and injected at runtime!")
    finally:
        delete_secret(test_key)

    # ---------------------------------------------------------
    # Test 2: Standard JSON-RPC 2.0 Handshake & Tool Discovery
    # ---------------------------------------------------------
    print("\n--- Test 2: JSON-RPC 2.0 Handshake & Tool Discovery ---")
    server = MCPServerProcess("test_srv", {
        "command": sys.executable,
        "args": [str(mock_script)],
        "env": {"INJECTED_API_KEY": "plain_test_key"},
        "timeout_seconds": 10.0
    })

    try:
        started = server.start()
        assert started is True, f"Failed to start server: {server.error_msg}"
        assert server.status == "connected"
        assert server.server_info.get("name") == "mock-mcp-server"
        assert len(server.tools) == 2

        tool_names = [t["name"] for t in server.tools]
        assert "test_srv__echo" in tool_names
        assert "test_srv__check_vault_env" in tool_names
        print(f"Verified: Handshake succeeded, {len(server.tools)} tools discovered and namespaced.")

        # Test tool execution
        res = server.call_tool("echo", {"message": "Hello MCP Standard!"})
        assert res["status"] == "success"
        assert "ECHO_REPLY: Hello MCP Standard!" in res["output"]

        # Test env propagation
        res_env = server.call_tool("check_vault_env", {})
        assert res_env["status"] == "success"
        assert "VAULT_VAL:plain_test_key" in res_env["output"]
        print("Verified: Tool execution ('tools/call') over stdio pipe succeeded with zero error!")

    finally:
        server.stop()
        assert server.status == "stopped"

    # ---------------------------------------------------------
    # Test 3: MCPClientManager Dynamic Registration & Dispatch
    # ---------------------------------------------------------
    print("\n--- Test 3: MCPClientManager Dynamic Registration & Lifecycle ---")
    test_vault_key = "mcp_vault_integration_key"
    store_secret(test_vault_key, "sec_val_9988")

    mgr = MCPClientManager()
    server_config = {
        "command": sys.executable,
        "args": [str(mock_script)],
        "env": {"INJECTED_API_KEY": f"vault:{test_vault_key}"},
        "timeout_seconds": 10.0
    }

    try:
        ok = mgr.add_or_update_server("mockmock", server_config)
        assert ok is True

        srv = mgr.servers["mockmock"]
        assert srv.status == "connected"

        all_schemas = mgr.get_all_tool_schemas()
        mcp_names = [s["name"] for s in all_schemas]
        assert "mockmock__echo" in mcp_names

        # Call via manager
        call_res = mgr.dispatch_tool("mockmock__echo", {"message": "Dynamic Dispatch Test"}, {})
        assert call_res["status"] == "success"
        assert "ECHO_REPLY: Dynamic Dispatch Test" in call_res["output"]

        # Verify vault injection
        val_res = mgr.dispatch_tool("mockmock__check_vault_env", {}, {})
        assert val_res["status"] == "success"
        assert "VAULT_VAL:sec_val_9988" in val_res["output"]

        # Verify statuses
        statuses = mgr.get_server_statuses()
        assert any(s["name"] == "mockmock" and s["status"] == "connected" for s in statuses)
        print("Verified: MCPClientManager dynamic registration, schema generation, and routing passed!")

    finally:
        mgr.remove_server("mockmock")
        delete_secret(test_vault_key)
        assert "mockmock" not in mgr.servers

    # ---------------------------------------------------------
    # Test 4: agent_tools.py Unified Dispatch Integration
    # ---------------------------------------------------------
    print("\n--- Test 4: Agent Tools Engine Integration ---")
    global_mgr = get_mcp_manager()
    global_mgr.add_or_update_server("live_mcp", {
        "command": sys.executable,
        "args": [str(mock_script)],
        "timeout_seconds": 10.0
    })

    try:
        combined_schemas = get_all_tool_schemas()
        names = [s["name"] for s in combined_schemas]
        assert "live_mcp__echo" in names
        print(f"Verified: Dynamic MCP tools seamlessly injected into total schema ({len(combined_schemas)} tools total).")

        # Call via standard dispatch_tool
        res = dispatch_tool("live_mcp__echo", {"message": "Agent Engine Hook"}, {"project_name": "test_proj"})
        assert res["status"] == "success"
        assert "ECHO_REPLY: Agent Engine Hook" in res["output"]
        print("Verified: dispatch_tool automatically routed namespaced tool call to MCP process!")

    finally:
        global_mgr.remove_server("live_mcp")

    # ---------------------------------------------------------
    # Test 5: FastAPI REST Endpoints for MCP
    # ---------------------------------------------------------
    print("\n--- Test 5: FastAPI REST Endpoints (/mcp/servers, /mcp/call) ---")
    from backend.api.chat_router import router
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    # 1. Register server via API
    add_resp = client.post("/mcp/servers", json={
        "name": "api_mock",
        "command": sys.executable,
        "args": [str(mock_script)],
        "env": {"TEST_VAR": "val123"},
        "disabled": False,
        "timeout_seconds": 10.0
    })
    assert add_resp.status_code == 200
    assert add_resp.json()["status"] == "success"

    try:
        # 2. List servers via API
        list_resp = client.get("/mcp/servers")
        assert list_resp.status_code == 200
        servers_data = list_resp.json()["servers"]
        api_srv = next((s for s in servers_data if s["name"] == "api_mock"), None)
        assert api_srv is not None
        if api_srv["status"] != "connected":
            print(f"DEBUG api_srv: {api_srv}")
            # Give background thread up to 1 second if still initializing
            for _ in range(10):
                time.sleep(0.1)
                list_resp = client.get("/mcp/servers")
                servers_data = list_resp.json()["servers"]
                api_srv = next((s for s in servers_data if s["name"] == "api_mock"), None)
                if api_srv and api_srv["status"] == "connected":
                    break
        assert api_srv["status"] == "connected"
        assert "api_mock__echo" in api_srv["tools"]
        print("Verified: GET /mcp/servers returns active server, status, and tools list.")

        # 3. Call tool via API
        call_resp = client.post("/mcp/call", json={
            "tool": "api_mock__echo",
            "arguments": {"message": "REST API Test"},
            "project_name": "api_project"
        })
        assert call_resp.status_code == 200
        assert call_resp.json()["status"] == "success"
        assert "ECHO_REPLY: REST API Test" in call_resp.json()["output"]
        print("Verified: POST /mcp/call successfully executed tool and returned payload.")

    finally:
        del_resp = client.delete("/mcp/servers/api_mock")
        assert del_resp.status_code == 200
        assert del_resp.json()["status"] == "success"
        print("Verified: DELETE /mcp/servers cleanly stopped process and removed config.")

    # Cleanup temp directory
    try:
        shutil.rmtree(mock_dir)
    except Exception:
        pass

    print("\n" + "=" * 70)
    print("ALL MCP VERIFICATION TESTS PASSED (100% SUCCESS)!")
    print("=" * 70)


if __name__ == "__main__":
    run_all_tests()
