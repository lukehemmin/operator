from __future__ import annotations

import json
import shlex
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Any, List, Optional


@dataclass
class MCPServer:
    name: str
    transport: str = "stdio"  # only stdio supported here
    command: List[str] = None  # executable + args
    cwd: Optional[str] = None
    env: Dict[str, str] = None
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "MCPServer":
        return MCPServer(
            name=d["name"],
            transport=d.get("transport", "stdio"),
            command=list(d.get("command") or []),
            cwd=d.get("cwd"),
            env=dict(d.get("env") or {}),
            enabled=bool(d.get("enabled", True)),
        )


def load_registry(path: Path) -> Dict[str, MCPServer]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        servers = {}
        for item in data.get("servers", []):
            srv = MCPServer.from_dict(item)
            servers[srv.name] = srv
        return servers
    except Exception:
        return {}


def save_registry(path: Path, servers: Dict[str, MCPServer]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"servers": [srv.to_dict() for srv in servers.values()]}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_command(command: Any) -> List[str]:
    if isinstance(command, list):
        return [str(x) for x in command]
    if isinstance(command, str):
        return shlex.split(command)
    raise ValueError("command must be list or string")

