from __future__ import annotations

import subprocess
from typing import Dict, Any


ALLOWED_ACTIONS = {"start", "stop", "restart", "reload", "enable", "disable", "status"}


def manage_service(unit: str, action: str, user: bool = False, timeout: int = 60) -> Dict[str, Any]:
    action = action.lower()
    if action not in ALLOWED_ACTIONS:
        return {"error": f"unsupported action {action}"}
    base = ["systemctl"]
    if user:
        base.append("--user")
    args = base + [action, unit, "--no-pager"]
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return {"unit": unit, "action": action, "returncode": p.returncode, "stdout": p.stdout, "stderr": p.stderr}
    except Exception as e:
        return {"unit": unit, "action": action, "error": str(e)}

