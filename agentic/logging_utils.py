from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def log_jsonl(log_dir: Path, name: str, event: Dict[str, Any]) -> None:
    ensure_dir(log_dir)
    path = log_dir / f"{name}.jsonl"
    event_with_ts = {"ts": utc_now_iso(), **event}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event_with_ts, ensure_ascii=False) + "\n")

