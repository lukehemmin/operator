from __future__ import annotations

from pathlib import Path
import shutil
import os
from typing import Dict, Any


def _resolve_in_workspace(path: str, workspace_root: Path) -> Path:
    p = (workspace_root / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
    if workspace_root not in p.parents and p != workspace_root:
        raise PermissionError("Path escapes workspace root")
    return p


def read_file(path: str, workspace_root: Path, max_bytes: int = 200_000) -> Dict[str, Any]:
    p = _resolve_in_workspace(path, workspace_root)
    data = p.read_bytes()
    truncated = False
    if len(data) > max_bytes:
        data = data[:max_bytes]
        truncated = True
    try:
        content = data.decode("utf-8")
    except Exception:
        content = data.decode("utf-8", errors="ignore")
    return {"path": str(p), "bytes": len(data), "truncated": truncated, "content": content}


def write_file(
    path: str,
    content: str,
    workspace_root: Path,
    append: bool = False,
    make_dirs: bool = True,
) -> Dict[str, Any]:
    p = _resolve_in_workspace(path, workspace_root)
    if make_dirs:
        p.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    with p.open(mode, encoding="utf-8") as f:
        f.write(content)
    return {"path": str(p), "written": len(content), "append": append}


def list_dir(path: str, workspace_root: Path) -> Dict[str, Any]:
    p = _resolve_in_workspace(path, workspace_root)
    if not p.exists():
        return {"path": str(p), "exists": False, "entries": []}
    entries = []
    for child in p.iterdir():
        entries.append({
            "name": child.name,
            "is_dir": child.is_dir(),
            "size": child.stat().st_size if child.is_file() else None,
        })
    return {"path": str(p), "exists": True, "entries": entries}


def delete_path(path: str, workspace_root: Path, recursive: bool = False) -> Dict[str, Any]:
    p = _resolve_in_workspace(path, workspace_root)
    if not p.exists():
        return {"path": str(p), "deleted": False, "reason": "not found"}
    if p.is_dir():
        if recursive:
            shutil.rmtree(p)
            return {"path": str(p), "deleted": True, "type": "dir", "recursive": True}
        else:
            try:
                os.rmdir(p)
                return {"path": str(p), "deleted": True, "type": "dir", "recursive": False}
            except OSError as e:
                return {"path": str(p), "deleted": False, "error": str(e)}
    else:
        p.unlink()
        return {"path": str(p), "deleted": True, "type": "file"}


def move_path(src: str, dst: str, workspace_root: Path, overwrite: bool = False) -> Dict[str, Any]:
    sp = _resolve_in_workspace(src, workspace_root)
    dp = _resolve_in_workspace(dst, workspace_root)
    if dp.exists() and not overwrite:
        return {"src": str(sp), "dst": str(dp), "moved": False, "error": "destination exists"}
    dp.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(sp), str(dp))
    return {"src": str(sp), "dst": str(dp), "moved": True}


def copy_path(src: str, dst: str, workspace_root: Path, overwrite: bool = False) -> Dict[str, Any]:
    sp = _resolve_in_workspace(src, workspace_root)
    dp = _resolve_in_workspace(dst, workspace_root)
    if dp.exists() and not overwrite:
        return {"src": str(sp), "dst": str(dp), "copied": False, "error": "destination exists"}
    dp.parent.mkdir(parents=True, exist_ok=True)
    if sp.is_dir():
        if dp.exists():
            shutil.rmtree(dp)
        shutil.copytree(sp, dp)
    else:
        shutil.copy2(sp, dp)
    return {"src": str(sp), "dst": str(dp), "copied": True}


def make_dir(path: str, workspace_root: Path, exist_ok: bool = True) -> Dict[str, Any]:
    p = _resolve_in_workspace(path, workspace_root)
    p.mkdir(parents=True, exist_ok=exist_ok)
    return {"path": str(p), "created": True}


def replace_in_file(path: str, find: str, replace: str, workspace_root: Path, count: int | None = None, regex: bool = False) -> Dict[str, Any]:
    import re
    p = _resolve_in_workspace(path, workspace_root)
    text = p.read_text(encoding="utf-8")
    if regex:
        new_text, n = re.subn(find, replace, text, count=0 if count is None else count)
    else:
        if count is None:
            n = text.count(find)
            new_text = text.replace(find, replace)
        else:
            new_text = text.replace(find, replace, count)
            n = count
    p.write_text(new_text, encoding="utf-8")
    return {"path": str(p), "replaced": n}
