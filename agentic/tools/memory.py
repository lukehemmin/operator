from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import hashlib
import math


MEM_FILE = "memory.jsonl"
DIM = 256


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mem_path(config_dir: Path) -> Path:
    config_dir.mkdir(parents=True, exist_ok=True)
    return (config_dir / MEM_FILE).resolve()


def _tokenize(text: str) -> List[str]:
    return [t.lower() for t in text.split() if t.strip()]


def _token_id(tok: str) -> int:
    h = hashlib.sha1(tok.encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big")


def _embed_local(text: str, dim: int = DIM) -> List[float]:
    vec = [0.0] * dim
    for tok in _tokenize(text):
        idx = _token_id(tok) % dim
        vec[idx] += 1.0
    # l2 norm
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def _cos(a: List[float], b: List[float]) -> float:
    return float(sum(x * y for x, y in zip(a, b)))


def memory_add(config_dir: Path, text: str, tags: Optional[List[str]] = None, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    path = _mem_path(config_dir)
    entry = {
        "id": str(uuid.uuid4()),
        "ts": _ts(),
        "text": text,
        "tags": tags or [],
        "meta": meta or {},
    }
    entry["vec"] = _embed_local(text)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return {"id": entry["id"], "ts": entry["ts"], "tags": entry["tags"]}


def _load_entries(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    entries = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                entries.append(obj)
            except Exception:
                continue
    return entries


def memory_list(config_dir: Path, limit: int = 50, tag: Optional[str] = None) -> Dict[str, Any]:
    path = _mem_path(config_dir)
    entries = _load_entries(path)
    if tag:
        entries = [e for e in entries if tag in (e.get("tags") or [])]
    entries = entries[-limit:]
    return {"count": len(entries), "items": [{k: e[k] for k in ("id", "ts", "tags", "text")} for e in entries]}


def memory_delete(config_dir: Path, entry_id: str) -> Dict[str, Any]:
    path = _mem_path(config_dir)
    entries = _load_entries(path)
    new_entries = [e for e in entries if e.get("id") != entry_id]
    if len(new_entries) == len(entries):
        return {"deleted": False, "reason": "not found"}
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for e in new_entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    tmp.replace(path)
    return {"deleted": True, "id": entry_id}


def memory_search(config_dir: Path, query: str, top_k: int = 5, tag: Optional[str] = None) -> Dict[str, Any]:
    path = _mem_path(config_dir)
    entries = _load_entries(path)
    if tag:
        entries = [e for e in entries if tag in (e.get("tags") or [])]
    if not entries:
        return {"results": []}
    q = _embed_local(query)
    scored = []
    for e in entries:
        v = e.get("vec")
        if not isinstance(v, list):
            e["vec"] = _embed_local(e.get("text", ""))
            v = e["vec"]
        s = _cos(q, v)
        scored.append((s, e))
    scored.sort(key=lambda x: x[0], reverse=True)
    out = []
    for s, e in scored[:top_k]:
        out.append({"id": e.get("id"), "score": float(s), "ts": e.get("ts"), "tags": e.get("tags"), "text": e.get("text")})
    return {"results": out}


def memory_update(config_dir: Path, entry_id: str, text: Optional[str] = None, tags: Optional[List[str]] = None, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    path = _mem_path(config_dir)
    entries = _load_entries(path)
    found = False
    for e in entries:
        if e.get("id") == entry_id:
            if text is not None:
                e["text"] = text
                e["vec"] = _embed_local(text)
            if tags is not None:
                e["tags"] = tags
            if meta is not None:
                e["meta"] = meta
            found = True
            break
    if not found:
        return {"updated": False, "reason": "not found"}
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    tmp.replace(path)
    return {"updated": True, "id": entry_id}

