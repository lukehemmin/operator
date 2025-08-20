from __future__ import annotations

import json
import urllib.request
from typing import List, Dict, Optional, Any

from .base import Message


class AnthropicProvider:
    def __init__(self, api_key: str, base_url: Optional[str] = None) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/") if base_url else "https://api.anthropic.com"

    def _convert_messages(self, messages: List[Message]):
        # Anthropic expects no explicit system message in the list; it has a separate field.
        system = None
        converted = []
        for m in messages:
            if m["role"] == "system":
                system = (system + "\n" if system else "") + m["content"]
            else:
                converted.append({"role": m["role"], "content": m["content"]})
        return system, converted

    def generate(
        self,
        messages: List[Message],
        model: str,
        request_timeout: int = 120,
        reasoning: Optional[bool] = None,
        reasoning_effort: Optional[str] = None,
    ) -> Dict[str, Any]:
        system, msgs = self._convert_messages(messages)
        url = f"{self.base_url}/v1/messages"
        body = {
            "model": model,
            "max_tokens": 2048,
            "messages": msgs,
        }
        # Anthropic 'thinking' models may return thinking blocks automatically; no explicit flag here.
        if system:
            body["system"] = system
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=request_timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        content = ""
        reasoning_texts: List[str] = []
        try:
            blocks = payload.get("content") or []
            for b in blocks:
                if b.get("type") == "text":
                    content += b.get("text", "")
                if b.get("type") in {"thinking", "reasoning"}:
                    reasoning_texts.append(b.get("text", ""))
        except Exception:
            content = json.dumps(payload)
        return {"content": content, "reasoning": "\n".join(reasoning_texts) if reasoning_texts else None, "raw": payload}
