from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Optional
import subprocess


class JsonRpcError(Exception):
    pass


class MCPStdIOClient:
    def __init__(self, command: list[str], cwd: Optional[str] = None, env: Optional[dict] = None, startup_timeout: int = 10, io_timeout: int = 30) -> None:
        self.command = command
        self.cwd = cwd
        self.env = env or {}
        self.startup_timeout = startup_timeout
        self.io_timeout = io_timeout
        self.proc: Optional[subprocess.Popen] = None
        self._next_id = 1

    def _write_message(self, obj: Dict[str, Any]) -> None:
        if not self.proc or not self.proc.stdin:
            raise RuntimeError("process not running")
        data = json.dumps(obj).encode("utf-8")
        header = f"Content-Length: {len(data)}\r\n\r\n".encode("ascii")
        self.proc.stdin.write(header + data)
        self.proc.stdin.flush()

    def _read_message(self) -> Dict[str, Any]:
        if not self.proc or not self.proc.stdout:
            raise RuntimeError("process not running")
        # Read headers
        deadline = time.time() + self.io_timeout
        def read_line() -> bytes:
            while True:
                if time.time() > deadline:
                    raise TimeoutError("timeout waiting for header line")
                line = self.proc.stdout.readline()
                if line:
                    return line
        content_length = None
        while True:
            line = read_line()
            if line in (b"\r\n", b"\n", b""):
                break
            lower = line.decode("ascii", errors="ignore").strip().lower()
            if lower.startswith("content-length:"):
                try:
                    content_length = int(lower.split(":", 1)[1].strip())
                except Exception:
                    pass
        if content_length is None:
            raise JsonRpcError("missing Content-Length header")
        # Read body
        body = b""
        while len(body) < content_length:
            if time.time() > deadline:
                raise TimeoutError("timeout waiting for body")
            chunk = self.proc.stdout.read(content_length - len(body))
            if not chunk:
                time.sleep(0.01)
                continue
            body += chunk
        try:
            return json.loads(body.decode("utf-8"))
        except Exception as e:
            raise JsonRpcError(f"invalid json: {e}")

    def _request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        msg_id = self._next_id
        self._next_id += 1
        req = {"jsonrpc": "2.0", "id": msg_id, "method": method}
        if params is not None:
            req["params"] = params
        self._write_message(req)
        # Read until our response id arrives
        while True:
            msg = self._read_message()
            if msg.get("id") == msg_id:
                if "error" in msg:
                    raise JsonRpcError(str(msg["error"]))
                return msg.get("result")
            # Ignore notifications or responses to other ids.

    def open(self) -> None:
        env = os.environ.copy()
        env.update(self.env)
        self.proc = subprocess.Popen(
            self.command,
            cwd=self.cwd,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        # Basic initialize handshake per MCP
        try:
            self._request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"list": True, "call": True},
                },
                "clientInfo": {"name": "agentic-cli", "version": "0.1.0"},
            })
        except Exception:
            # Some servers may not require/implement initialize; ignore failures
            pass

    def list_tools(self) -> Dict[str, Any]:
        return self._request("tools/list", {})

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("tools/call", {"name": name, "arguments": arguments})

    def close(self) -> None:
        if self.proc and self.proc.poll() is None:
            try:
                self._request("shutdown", {})
            except Exception:
                pass
            try:
                self.proc.terminate()
            except Exception:
                pass

