from __future__ import annotations

import json
import urllib.request
from typing import List, Dict, Any

from .base import Message


class OllamaProvider:
    def __init__(self, base_url: str = "http://localhost:11434") -> None:
        self.base_url = base_url.rstrip("/")

    def generate(
        self,
        messages: List[Message],
        model: str,
        request_timeout: int = 120,
        reasoning: None | bool = None,
        reasoning_effort: None | str = None,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/api/chat"
        body = {
            "model": model,
            "messages": messages,
            "stream": False,
        }
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=request_timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        content = ""
        try:
            content = payload["message"]["content"] or ""
        except Exception:
            content = json.dumps(payload)
        return {"content": content, "reasoning": None, "raw": payload}

    def generate_stream(
        self,
        messages: List[Message],
        model: str,
        request_timeout: int = 120,
        reasoning: None | bool = None,
        reasoning_effort: None | str = None,
    ):
        import time
        url = f"{self.base_url}/api/chat"
        body = {
            "model": model,
            "messages": messages,
            "stream": True,
        }
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        content_acc = []
        raw_last = None
        try:
            with urllib.request.urlopen(req, timeout=request_timeout) as resp:
                # Ollama streams JSON objects separated by newlines
                while True:
                    line = resp.readline()
                    if not line:
                        break
                    try:
                        evt = json.loads(line.decode("utf-8"))
                        raw_last = evt
                    except Exception:
                        continue
                    msg = evt.get("message") or {}
                    if msg.get("content"):
                        text = msg.get("content")
                        content_acc.append(text)
                        yield {"event": "delta", "text": text}
                    if evt.get("done"):
                        break
        except Exception:
            pass
        final_text = "".join(content_acc)
        yield {"event": "final", "content": final_text, "reasoning": None, "raw": raw_last}
