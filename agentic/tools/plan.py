from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Any, List, Optional


PLANS_DIR = "plans"


@dataclass
class Plan:
    id: str
    title: str
    steps: List[Dict[str, Any]]  # {text, status}


def _dir(config_dir: Path) -> Path:
    d = (config_dir / PLANS_DIR)
    d.mkdir(parents=True, exist_ok=True)
    return d


def plan_create(config_dir: Path, title: str, steps: Optional[List[str]] = None) -> Dict[str, Any]:
    pid = str(uuid.uuid4())
    plan = Plan(id=pid, title=title, steps=[{"text": s, "status": "pending"} for s in (steps or [])])
    path = _dir(config_dir) / f"{pid}.json"
    path.write_text(json.dumps(asdict(plan), ensure_ascii=False, indent=2), encoding="utf-8")
    return {"id": pid, "title": title, "steps": plan.steps}


def plan_get(config_dir: Path, plan_id: str) -> Dict[str, Any]:
    path = _dir(config_dir) / f"{plan_id}.json"
    if not path.exists():
        return {"error": "not found"}
    return json.loads(path.read_text(encoding="utf-8"))


def plan_list(config_dir: Path) -> Dict[str, Any]:
    out = []
    for p in _dir(config_dir).glob("*.json"):
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
            out.append({"id": obj.get("id"), "title": obj.get("title"), "steps": obj.get("steps")})
        except Exception:
            continue
    return {"plans": out}


def plan_delete(config_dir: Path, plan_id: str) -> Dict[str, Any]:
    path = _dir(config_dir) / f"{plan_id}.json"
    if not path.exists():
        return {"deleted": False, "reason": "not found"}
    path.unlink()
    return {"deleted": True, "id": plan_id}


def plan_add_step(config_dir: Path, plan_id: str, text: str) -> Dict[str, Any]:
    obj = plan_get(config_dir, plan_id)
    if "error" in obj:
        return obj
    obj.setdefault("steps", []).append({"text": text, "status": "pending"})
    path = _dir(config_dir) / f"{plan_id}.json"
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"updated": True, "steps": obj["steps"]}


def plan_update_step(config_dir: Path, plan_id: str, index: int, status: str) -> Dict[str, Any]:
    obj = plan_get(config_dir, plan_id)
    if "error" in obj:
        return obj
    steps = obj.get("steps") or []
    if index < 0 or index >= len(steps):
        return {"error": "index out of range"}
    steps[index]["status"] = status
    path = _dir(config_dir) / f"{plan_id}.json"
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"updated": True, "steps": steps}

