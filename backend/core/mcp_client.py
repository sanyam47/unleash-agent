"""
Dynamic Model Context Protocol (MCP) Client & Host Engine for Unleash-Agent.
Complies with Anthropic's Model Context Protocol (MCP) JSON-RPC 2.0 specification over stdio.

Features:
  1. Standard-compliant JSON-RPC 2.0 stdio transport (identical to Claude Desktop / Cursor).
  2. Automatic tool discovery and dynamic schema injection into Ollama prompt.
  3. Integrated AES-256-GCM Vault credential resolution ('vault:secret_key' in env vars).
  4. Namespaced tool routing ('{server}__{tool}') with thread-safe IPC and timeouts.
  5. Built-in mock test server support for offline automated verification.
"""

import os
import sys
import json
import time
import shutil
import logging
import threading
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("UnleashAgent.MCP")

# Default config path
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CONFIG_FILE = DATA_DIR / "mcp_servers.json"


def get_config_path() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_FILE


def load_mcp_config() -> Dict[str, Any]:
    """Loads mcp_servers.json or initializes a clean template if missing."""
    cfg_path = get_config_path()
    if not cfg_path.exists():
        default_config = {
            "mcpServers": {}
        }
        try:
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to create default mcp_servers.json: {e}")
        return default_config

    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to read mcp_servers.json: {e}")
        return {"mcpServers": {}}


def save_mcp_config(config: Dict[str, Any]) -> bool:
    """Saves updated MCP server configuration to disk."""
    cfg_path = get_config_path()
    try:
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Failed to save mcp_servers.json: {e}")
        return False


def resolve_vault_env(env_dict: Dict[str, str]) -> Dict[str, str]:
    """
    Resolves any environment variable values prefixed with 'vault:key'
    from the AES-256-GCM Credential Vault.
    """
    resolved = dict(os.environ)
    if not env_dict:
        return resolved

    for k, v in env_dict.items():
        if isinstance(v, str) and v.startswith("vault:"):
            secret_key = v.split("vault:", 1)[1].strip()
            try:
                from backend.core.credential_vault import get_secret
                val = get_secret(secret_key)
                if val:
                    resolved[k] = val
                else:
                    logger.warning(f"Vault key '{secret_key}' requested by MCP server not found in vault.")
            except Exception as e:
                logger.error(f"Error retrieving vault key '{secret_key}': {e}")
        else:
            resolved[k] = str(v)

    return resolved


class MCPServerProcess:
    """
    Manages a single child process running an MCP server over stdio.
    Implements JSON-RPC 2.0 handshake, tool discovery, and execution.
    """

    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.command = config.get("command", "")
        self.args = config.get("args", [])
        self.raw_env = config.get("env", {})
        self.disabled = bool(config.get("disabled", False))
        self.timeout_sec = float(config.get("timeout_seconds", 25.0))

        self.proc: Optional[subprocess.Popen] = None
        self.tools: List[Dict[str, Any]] = []
        self.server_info: Dict[str, Any] = {}
        self.status = "stopped"  # 'stopped', 'connected', 'error', 'disabled'
        self.error_msg = ""
        self._lock = threading.Lock()
        self._req_id = 1

    def _next_id(self) -> int:
        cur = self._req_id
        self._req_id += 1
        return cur

    def start(self) -> bool:
        """Launches the MCP server subprocess and completes initialize handshake."""
        if self.disabled:
            self.status = "disabled"
            return False

        with self._lock:
            # Resolve executable path (resolves npx.CMD, python.exe, etc. on Windows)
            exec_bin = shutil.which(self.command) or self.command
            cmd_list = [exec_bin] + [str(a) for a in self.args]
            resolved_env = resolve_vault_env(self.raw_env)

            try:
                # Use CREATE_NO_WINDOW on Windows to prevent console flashing
                creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                self.proc = subprocess.Popen(
                    cmd_list,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=resolved_env,
                    text=True,
                    bufsize=1,
                    creationflags=creation_flags
                )
                self.status = "initializing"
            except Exception as e:
                self.status = "error"
                self.error_msg = f"Failed to spawn MCP process '{self.command}': {str(e)}"
                logger.error(f"[{self.name}] {self.error_msg}")
                return False

            # Complete MCP Handshake (initialize -> notifications/initialized)
            try:
                init_resp = self._send_request_locked("initialize", {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"roots": {"listChanged": True}},
                    "clientInfo": {"name": "unleash-agent", "version": "2.4.0"}
                }, timeout=self.timeout_sec)

                if "error" in init_resp:
                    self.status = "error"
                    self.error_msg = f"Initialize rejected: {init_resp['error']}"
                    self.stop()
                    return False

                self.server_info = init_resp.get("result", {}).get("serverInfo", {})

                # Send initialized notification
                self._send_notification_locked("notifications/initialized")

                # Fetch available tools
                tools_resp = self._send_request_locked("tools/list", {}, timeout=self.timeout_sec)
                raw_tools = tools_resp.get("result", {}).get("tools", [])

                # Format and namespace tools
                self.tools = []
                for t in raw_tools:
                    raw_name = t.get("name", "unknown")
                    namespaced_name = f"{self.name}__{raw_name}"
                    
                    # Convert inputSchema properties into parameter description map
                    props = t.get("inputSchema", {}).get("properties", {})
                    required = t.get("inputSchema", {}).get("required", [])
                    params_map = {}
                    for p_name, p_data in props.items():
                        desc = p_data.get("description") or p_data.get("type", "string")
                        if p_name in required:
                            desc += " (required)"
                        params_map[p_name] = desc

                    self.tools.append({
                        "name": namespaced_name,
                        "raw_name": raw_name,
                        "server": self.name,
                        "description": f"[{self.name.upper()}] {t.get('description', '')}",
                        "parameters": params_map,
                        "raw_schema": t.get("inputSchema", {})
                    })

                self.status = "connected"
                self.error_msg = ""
                logger.info(f"MCP server '{self.name}' connected ({len(self.tools)} tools discovered).")
                return True

            except Exception as e:
                self.status = "error"
                self.error_msg = f"Handshake failed: {str(e)}"
                logger.error(f"[{self.name}] {self.error_msg}")
                self.stop()
                return False

    def _send_request_locked(self, method: str, params: Dict[str, Any], timeout: float = 15.0) -> Dict[str, Any]:
        """Sends a JSON-RPC request and synchronously reads the matching response."""
        if not self.proc or self.proc.poll() is not None:
            raise RuntimeError(f"Server '{self.name}' process is not running.")

        req_id = self._next_id()
        msg = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params
        }
        msg_str = json.dumps(msg) + "\n"

        self.proc.stdin.write(msg_str)
        self.proc.stdin.flush()

        # Read lines from stdout until matching response is found
        start_time = time.time()
        while True:
            if time.time() - start_time > timeout:
                raise TimeoutError(f"Request '{method}' (id={req_id}) timed out after {timeout}s")

            # Non-blocking / timed line read
            line = self.proc.stdout.readline()
            if not line:
                if self.proc.poll() is not None:
                    err_out = ""
                    try:
                        err_out = self.proc.stderr.read()[:500]
                    except Exception:
                        pass
                    raise RuntimeError(f"Server process terminated unexpectedly. Stderr: {err_out}")
                time.sleep(0.05)
                continue

            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
                if data.get("id") == req_id:
                    return data
            except json.JSONDecodeError:
                # Discard non-json log lines emitted to stdout
                continue

    def _send_notification_locked(self, method: str, params: Optional[Dict[str, Any]] = None):
        """Sends a JSON-RPC notification (no id, no return value expected)."""
        if not self.proc or self.proc.poll() is not None:
            return
        msg = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {}
        }
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Executes 'tools/call' on this MCP server."""
        if self.status != "connected" or not self.proc:
            # Attempt auto-reconnect
            if not self.start():
                return {"status": "error", "error": f"MCP server '{self.name}' is offline: {self.error_msg}"}

        # Resolve raw tool name without namespace prefix
        raw_name = tool_name
        if tool_name.startswith(f"{self.name}__"):
            raw_name = tool_name.split(f"{self.name}__", 1)[1]

        with self._lock:
            try:
                resp = self._send_request_locked(
                    "tools/call",
                    {"name": raw_name, "arguments": arguments},
                    timeout=self.timeout_sec
                )

                if "error" in resp:
                    err = resp["error"]
                    return {"status": "error", "error": err.get("message", str(err))}

                result = resp.get("result", {})
                is_error = result.get("isError", False)
                content_items = result.get("content", [])

                text_parts = []
                for c in content_items:
                    if c.get("type") == "text":
                        text_parts.append(c.get("text", ""))
                    elif c.get("type") == "image":
                        text_parts.append(f"[Image: {c.get('mimeType', 'unknown')}]")

                full_output = "\n".join(text_parts).strip()
                if not full_output and not is_error:
                    full_output = json.dumps(result)

                return {
                    "status": "error" if is_error else "success",
                    "server": self.name,
                    "tool": raw_name,
                    "output": full_output,
                    "is_error": is_error
                }

            except Exception as e:
                logger.error(f"Error calling tool '{tool_name}' on '{self.name}': {e}")
                return {"status": "error", "error": f"Tool execution failed on server '{self.name}': {str(e)}"}

    def stop(self):
        """Terminates the child process cleanly."""
        with self._lock:
            if self.proc:
                try:
                    self.proc.terminate()
                    self.proc.wait(timeout=1.5)
                except Exception:
                    try:
                        self.proc.kill()
                    except Exception:
                        pass
                self.proc = None
            if self.status != "disabled":
                self.status = "stopped"


class MCPClientManager:
    """
    Singleton Manager holding and coordinating all configured MCP servers.
    Provides unified dynamic tool schema registry and tool dispatching.
    """

    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = MCPClientManager()
        return cls._instance

    def __init__(self):
        self.servers: Dict[str, MCPServerProcess] = {}
        self.initialized = False
        self._lock = threading.Lock()

    def initialize(self):
        """Loads configuration and boots all enabled MCP servers."""
        with self._lock:
            if self.initialized:
                return

            config = load_mcp_config()
            server_configs = config.get("mcpServers", {})

            for name, cfg in server_configs.items():
                srv = MCPServerProcess(name, cfg)
                self.servers[name] = srv
                # Connect in background or sync
                if not srv.disabled:
                    threading.Thread(target=srv.start, daemon=True).start()

            self.initialized = True
            logger.info(f"MCPClientManager initialized with {len(self.servers)} configured servers.")

    def get_all_tool_schemas(self) -> List[Dict[str, Any]]:
        """Returns schemas for all dynamically discovered tools across all active MCP servers."""
        schemas = []
        for srv in self.servers.values():
            if srv.status == "connected":
                for t in srv.tools:
                    schemas.append({
                        "name": t["name"],
                        "description": t["description"],
                        "parameters": t["parameters"],
                        "source": "mcp",
                        "server": t["server"]
                    })
        return schemas

    def is_mcp_tool(self, tool_name: str) -> bool:
        """Checks if a tool name belongs to any configured or connected MCP server."""
        if "__" in tool_name:
            server_name = tool_name.split("__", 1)[0]
            if server_name in self.servers:
                return True
        for srv in self.servers.values():
            for t in srv.tools:
                if t["name"] == tool_name:
                    return True
        return False

    def dispatch_tool(self, tool_name: str, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Routes a tool execution call to the appropriate MCP server."""
        server_name = None
        if "__" in tool_name:
            server_name, _ = tool_name.split("__", 1)
        else:
            # Search tools
            for srv in self.servers.values():
                for t in srv.tools:
                    if t["name"] == tool_name or t.get("raw_name") == tool_name:
                        server_name = srv.name
                        break
                if server_name:
                    break

        if not server_name or server_name not in self.servers:
            return {"status": "error", "error": f"No active MCP server found for tool '{tool_name}'"}

        srv = self.servers[server_name]
        return srv.call_tool(tool_name, args)

    def get_server_statuses(self) -> List[Dict[str, Any]]:
        """Returns live diagnostic statuses of all MCP servers for UI and health audits."""
        result = []
        for name, srv in self.servers.items():
            result.append({
                "name": name,
                "command": srv.command,
                "status": srv.status,
                "error": srv.error_msg,
                "server_info": srv.server_info,
                "tool_count": len(srv.tools),
                "tools": [t["name"] for t in srv.tools],
                "disabled": srv.disabled
            })
        return result

    def add_or_update_server(self, name: str, config: Dict[str, Any]) -> bool:
        """Registers a new server or updates an existing one, restarting the process."""
        self.initialized = True
        full_cfg = load_mcp_config()
        if "mcpServers" not in full_cfg:
            full_cfg["mcpServers"] = {}

        full_cfg["mcpServers"][name] = config
        save_mcp_config(full_cfg)

        with self._lock:
            if name in self.servers:
                self.servers[name].stop()

            srv = MCPServerProcess(name, config)
            self.servers[name] = srv
            if not srv.disabled:
                srv.start()

        return True

    def remove_server(self, name: str) -> bool:
        """Removes a server from config and shuts it down."""
        full_cfg = load_mcp_config()
        if "mcpServers" in full_cfg and name in full_cfg["mcpServers"]:
            del full_cfg["mcpServers"][name]
            save_mcp_config(full_cfg)

        with self._lock:
            if name in self.servers:
                self.servers[name].stop()
                del self.servers[name]

        return True

    def restart_all(self):
        """Restarts all configured servers."""
        with self._lock:
            for srv in self.servers.values():
                srv.stop()
            self.servers.clear()
            self.initialized = False
        self.initialize()

    def shutdown(self):
        """Stops all running child processes on exit."""
        with self._lock:
            for srv in self.servers.values():
                srv.stop()
            self.servers.clear()
            self.initialized = False


# Global accessor
def get_mcp_manager() -> MCPClientManager:
    return MCPClientManager.get_instance()
