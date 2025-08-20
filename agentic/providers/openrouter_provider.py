from __future__ import annotations

import json
import urllib.request
from typing import List, Dict, Optional, Any

from .base import Message


class OpenRouterProvider:
    def __init__(self, api_key: str, base_url: Optional[str] = None, referer: Optional[str] = None, app_name: Optional[str] = None) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/") if base_url else "https://openrouter.ai/api"
        self.referer = referer
        self.app_name = app_name

    def generate(
        self,
        messages: List[Message],
        model: str,
        request_timeout: int = 120,
        reasoning: Optional[bool] = None,
        reasoning_effort: Optional[str] = None,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/v1/chat/completions"
        body = {
            "model": model,
            "messages": messages,
            "temperature": 0,
        }
        use_reasoning = False
        if reasoning is True:
            use_reasoning = True
        elif reasoning is None:
            use_reasoning = any(x in (model or "").lower() for x in ["o3", "o4", "reason"])
        if use_reasoning:
            body["reasoning"] = {"effort": (reasoning_effort or "medium")}
        data = json.dumps(body).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.referer:
            headers["HTTP-Referer"] = self.referer
        if self.app_name:
            headers["X-Title"] = self.app_name
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=request_timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        content = ""
        reasoning_text = None
        try:
            choice = payload.get("choices", [{}])[0]
            msg = (choice.get("message") or {})
            content = msg.get("content") or ""
            rc = msg.get("reasoning") or msg.get("reasoning_content") or choice.get("reasoning_content")
            if isinstance(rc, list):
                reasoning_text = "\n".join([x.get("text", "") for x in rc if isinstance(x, dict)])
            elif isinstance(rc, str):
                reasoning_text = rc
        except Exception:
            content = json.dumps(payload)
        return {"content": content, "reasoning": reasoning_text, "raw": payload}

    def generate_stream(
        self,
        messages: List[Message],
        model: str,
        request_timeout: int = 120,
        reasoning: Optional[bool] = None,
        reasoning_effort: Optional[str] = None,
    ):
        url = f"{self.base_url}/v1/chat/completions"
        body = {
            "model": model,
            "messages": messages,
            "temperature": 0,
            "stream": True,
        }
        use_reasoning = False
        if reasoning is True:
            use_reasoning = True
        elif reasoning is None:
            use_reasoning = any(x in (model or "").lower() for x in ["o3", "o4", "reason"])
        if use_reasoning:
            body["reasoning"] = {"effort": (reasoning_effort or "medium")}
        data = json.dumps(body).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.referer:
            headers["HTTP-Referer"] = self.referer
        if self.app_name:
            headers["X-Title"] = self.app_name
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        content_acc = []
        reasoning_acc = []
        raw_last = None
        try:
            with urllib.request.urlopen(req, timeout=request_timeout) as resp:
                while True:
                    line = resp.readline()
                    if not line:
                        break
                    if line.startswith(b"data: "):
                        payload_line = line[len(b"data: "):].strip()
                        if payload_line == b"[DONE]":
                            break
                        try:
                            delta = json.loads(payload_line.decode("utf-8"))
                            raw_last = delta
                            choice = (delta.get("choices") or [{}])[0]
                            d = choice.get("delta") or {}
                            if d.get("content"):
                                text = d.get("content")
                                content_acc.append(text)
                                yield {"event": "delta", "text": text}
                            if isinstance(d.get("reasoning"), str):
                                r = d.get("reasoning")
                                reasoning_acc.append(r)
                                yield {"event": "delta", "reasoning": r}
                            rc = choice.get("reasoning_content")
                            if isinstance(rc, list) and rc:
                                r = "".join([x.get("text", "") for x in rc if isinstance(x, dict)])
                                if r:
                                    reasoning_acc.append(r)
                                    yield {"event": "delta", "reasoning": r}
                        except Exception:
                            continue
        except Exception:
            pass
        final_text = "".join(content_acc)
        final_reasoning = "".join(reasoning_acc) if reasoning_acc else None
        yield {"event": "final", "content": final_text, "reasoning": final_reasoning, "raw": raw_last}
