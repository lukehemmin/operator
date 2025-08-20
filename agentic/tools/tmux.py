from __future__ import annotations

import shlex
import subprocess
from typing import Dict, Any


def _run(args: list[str], timeout: int = 30) -> Dict[str, Any]:
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return {
            "args": args,
            "returncode": p.returncode,
            "stdout": p.stdout,
            "stderr": p.stderr,
        }
    except Exception as e:
        return {"args": args, "error": str(e)}


def tmux_ensure_session(name: str, cwd: str | None = None, timeout: int = 30) -> Dict[str, Any]:
    # check tmux binary
    chk = _run(["tmux", "-V"], timeout=timeout)
    if chk.get("returncode") not in (0, None):
        return {"error": "tmux not available", "detail": chk}

    # has-session
    has = subprocess.run(["tmux", "has-session", "-t", name], capture_output=True, text=True)
    if has.returncode == 0:
        return {"session": name, "created": False}
    # create detached session
    args = ["tmux", "new-session", "-d", "-s", name]
    if cwd:
        args += ["-c", cwd]
    res = _run(args, timeout=timeout)
    if res.get("returncode") == 0:
        return {"session": name, "created": True}
    return {"session": name, "error": res}


def tmux_send(name: str, command: str, enter: bool = True, timeout: int = 30) -> Dict[str, Any]:
    keys = command + (" C-m" if enter else "")
    args = ["tmux", "send-keys", "-t", name, command]
    if enter:
        args.append("Enter")
    return _run(args, timeout=timeout)


def tmux_capture(name: str, last_lines: int = 500, timeout: int = 30) -> Dict[str, Any]:
    # Capture last N lines from pane 0
    start = f"-{last_lines}"
    args = ["tmux", "capture-pane", "-t", name, "-p", "-S", start]
    res = _run(args, timeout=timeout)
    return {"session": name, "output": res.get("stdout", ""), "returncode": res.get("returncode")}


def tmux_list_sessions(timeout: int = 30) -> Dict[str, Any]:
    res = _run(["tmux", "list-sessions", "-F", "#{session_name}"], timeout=timeout)
    if res.get("returncode") != 0:
        return {"error": res}
    names = [line.strip() for line in res.get("stdout", "").splitlines() if line.strip()]
    return {"sessions": names}

