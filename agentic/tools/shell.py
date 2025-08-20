from __future__ import annotations

import shlex
import subprocess
from typing import Dict, Any, List


DESTRUCTIVE_KEYWORDS = {
    "mkfs", ":(){:|:&};:", "dd", "wipefs", "fdisk", "parted",
}

NETWORK_CMDS = {"apt", "apt-get", "curl", "wget", "pip", "npm", "pnpm", "composer", "go", "cargo", "git"}
WRITE_CMDS = {"rm", "mv", "cp", "chmod", "chown", "tee", "truncate", "sed", "awk", "touch", "mkdir", "rmdir", "ln", "systemctl", "service", "docker", "podman", "kubectl"}


def classify_command_risk(cmd: str) -> str:
    tokens: List[str] = shlex.split(cmd)
    if not tokens:
        return "safe"
    first = tokens[0]
    lower = cmd.lower()
    if "sudo" in tokens:
        return "destructive"
    if any(kw in lower for kw in DESTRUCTIVE_KEYWORDS):
        return "destructive"
    if first in NETWORK_CMDS or "http" in lower:
        return "network"
    if first in WRITE_CMDS or any(x in tokens for x in ["--write", "--save"]):
        return "write"
    return "safe"


def run_shell(cmd: str, timeout: int, cwd: str | None = None, env: Dict[str, str] | None = None) -> Dict[str, Any]:
    args = shlex.split(cmd)
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            timeout=timeout,
            cwd=cwd,
            env=env,
            shell=False,
            text=True,
        )
        return {
            "cmd": cmd,
            "returncode": proc.returncode,
            "stdout": proc.stdout[-50_000:],
            "stderr": proc.stderr[-50_000:],
        }
    except subprocess.TimeoutExpired as e:
        return {"cmd": cmd, "error": f"timeout after {timeout}s"}
    except FileNotFoundError:
        return {"cmd": cmd, "error": "command not found"}
    except Exception as e:
        return {"cmd": cmd, "error": str(e)}

