from __future__ import annotations

from typing import List, Dict, Any, Protocol, Optional


Message = Dict[str, str]  # {role: system|user|assistant, content: str}


class Provider(Protocol):
    def generate(
        self,
        messages: List[Message],
        model: str,
        request_timeout: int = 120,
        reasoning: Optional[bool] = None,
        reasoning_effort: Optional[str] = None,
    ) -> Any:
        ...

    # Optional streaming interface; yields dict events with keys:
    # {"event":"delta", "text":"...", "reasoning":"..."}
    # and a final event: {"event":"final", "content":"...", "reasoning": "...", "raw": ...}
    def generate_stream(
        self,
        messages: List[Message],
        model: str,
        request_timeout: int = 120,
        reasoning: Optional[bool] = None,
        reasoning_effort: Optional[str] = None,
    ) -> Any:
        ...
