from __future__ import annotations

import shlex
import subprocess
from pathlib import Path
from typing import Dict, Any


def classify_git_risk(args: str) -> str:
    lower = args.lower()
    if any(k in lower for k in ["clone", "fetch", "pull", "submodule update", "remote add", "lfs"]):
        return "network"
    if any(k in lower for k in ["push", "commit", "merge", "rebase", "reset", "checkout", "apply", "cherry-pick", "revert"]):
        return "write"
    return "safe"


def run_git(args: str, cwd: str | None = None, timeout: int = 120) -> Dict[str, Any]:
    argv = ["git"] + shlex.split(args)
    try:
        p = subprocess.run(argv, capture_output=True, text=True, cwd=cwd, timeout=timeout)
        return {
            "returncode": p.returncode,
            "stdout": p.stdout[-50_000:],
            "stderr": p.stderr[-50_000:],
        }
    except FileNotFoundError:
        return {"error": "git not found"}
    except subprocess.TimeoutExpired:
        return {"error": f"timeout after {timeout}s"}
    except Exception as e:
        return {"error": str(e)}

