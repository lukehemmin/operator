from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional


def extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    # Try code block first
    code_blocks = re.findall(r"```(?:json)?\n([\s\S]*?)\n```", text, flags=re.MULTILINE)
    candidates = []
    if code_blocks:
        candidates.extend(code_blocks)
    # Fallback: first {...} block
    if not candidates:
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            candidates.append(m.group(0))
    for c in candidates:
        try:
            obj = json.loads(c)
            if isinstance(obj, dict):
                return obj
        except Exception:
            continue
    return None


def summarize(text: str, limit: int = 2000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "...<truncated>"

