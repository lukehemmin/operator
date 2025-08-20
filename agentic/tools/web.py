from __future__ import annotations

import urllib.request
from typing import Dict, Any


def web_get(url: str, max_bytes: int = 200_000, timeout: int = 30) -> Dict[str, Any]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            data = resp.read(max_bytes + 1)
            truncated = len(data) > max_bytes
            if truncated:
                data = data[:max_bytes]
            text = data.decode("utf-8", errors="replace")
            return {
                "url": url,
                "status": getattr(resp, "status", None),
                "truncated": truncated,
                "content": text,
            }
    except Exception as e:
        return {"url": url, "error": str(e)}

