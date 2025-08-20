from __future__ import annotations

import json
import urllib.request
from typing import List, Optional, Dict, Any

from .base import Message


class LMStudioProvider:
    """Uses LM Studio's OpenAI-compatible local API (default http://localhost:1234).

    No API key required. Expects /v1/chat/completions.
    """

    def __init__(self, base_url: Optional[str] = None) -> None:
        self.base_url = (base_url or "http://localhost:1234").rstrip("/")

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
            # Heuristic: if model name hints at reasoning support
            use_reasoning = any(x in (model or "").lower() for x in ["o3", "o4", "reason", "think"])
        if use_reasoning:
            body["reasoning"] = {"effort": (reasoning_effort or "medium")}
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
        reasoning_text = None
        try:
            msg = payload["choices"][0]["message"]
            content = msg.get("content") or ""
            # LM Studio may include a "reasoning" string
            if isinstance(msg.get("reasoning"), str):
                reasoning_text = msg.get("reasoning")
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
            use_reasoning = any(x in (model or "").lower() for x in ["o3", "o4", "reason", "think"])
        if use_reasoning:
            body["reasoning"] = {"effort": (reasoning_effort or "medium")}
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        content_acc = []
        reasoning_acc = []
        raw_last = None
        final_reasoning = None
        last_reasoning_len = 0
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
                            # If LM Studio emits full message in stream
                            msg = choice.get("message") or {}
                            if msg:
                                txt = msg.get("content") or ""
                                if txt:
                                    content_acc.append(txt)
                                if isinstance(msg.get("reasoning"), str):
                                    final_reasoning = msg.get("reasoning")
                                # do not emit content as delta here to avoid duplication; let final handle
                            d = choice.get("delta") or {}
                            if d.get("content"):
                                text = d.get("content")
                                content_acc.append(text)
                                yield {"event": "delta", "text": text}
                            # Some servers may stream reasoning as a field
                            if isinstance(d.get("reasoning"), str):
                                r = d.get("reasoning")
                                full_reasoning = "".join(reasoning_acc)
                                if r.startswith(full_reasoning):
                                    new_reasoning = r[len(full_reasoning):]
                                    if new_reasoning:
                                        reasoning_acc.append(new_reasoning)
                                        yield {"event": "delta", "reasoning": new_reasoning}
                                else:
                                    reasoning_acc.append(r)
                                    yield {"event": "delta", "reasoning": r}
                        except Exception:
                            continue
        except Exception:
            pass
        final_text = "".join(content_acc)
        if final_reasoning is None and reasoning_acc:
            final_reasoning = "".join(reasoning_acc)
        yield {"event": "final", "content": final_text, "reasoning": final_reasoning, "raw": raw_last}
