from __future__ import annotations

from typing import Dict, Any
from .web import web_get
from .shell import run_shell


def headless_browse(url: str, engine: str | None = None, timeout: int = 60) -> Dict[str, Any]:
    # Try chromium-based first if requested or auto
    engines = []
    if engine in (None, "auto", "chromium"):
        engines.extend(["chromium", "chromium-browser", "google-chrome", "chrome"])
    if engine and engine not in ("auto", "chromium"):
        engines = [engine]

    for binname in engines:
        cmd = f"{binname} --headless=new --disable-gpu --dump-dom {url}"
        res = run_shell(cmd, timeout=timeout)
        if res.get("returncode") == 0 and res.get("stdout"):
            return {"engine": binname, "status": "ok", "dom": res.get("stdout")[:200_000], "truncated": len(res.get("stdout", "")) > 200_000}
    # Fallback to simple HTTP GET
    simple = web_get(url, max_bytes=200_000, timeout=timeout)
    simple["engine"] = "urllib"
    return simple

