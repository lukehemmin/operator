from __future__ import annotations

from typing import Any, Dict, List, Optional, Union


# Sentinel to indicate that approval should be deferred to external UI
class _Defer:
    pass


APPROVAL_DEFER = _Defer()


class EventSink:
    def on_assistant_raw(self, text: str) -> None:
        pass

    def on_tool_call(self, tool: str, tool_id: str, args: Dict[str, Any], note: Optional[str] = None) -> None:
        pass

    def on_tool_result(self, tool_id: str, result: Dict[str, Any]) -> None:
        pass

    def on_approval_required(self, tool: str, tool_id: str, reason: str, args: Dict[str, Any], token: Optional[str] = None) -> Union[bool, _Defer]:
        return False

    def on_final(self, content: str) -> None:
        pass

    def on_reasoning(self, text: Optional[str]) -> None:
        pass

    def on_raw(self, data: Any) -> None:
        pass

    # Streaming deltas
    def on_stream_text(self, text: str) -> None:
        pass

    def on_stream_reasoning(self, text: str) -> None:
        pass

class NullSink(EventSink):
    pass


class CLISink(EventSink):
    def __init__(self, show_raw: bool = True) -> None:
        self.show_raw = show_raw
        self.auto_approve = False
        self._stream_started = False
        self._stream_reason_started = False

    def on_assistant_raw(self, text: str) -> None:
        if self.show_raw and text:
            print("[assistant]", text)

    def on_tool_call(self, tool: str, tool_id: str, args: Dict[str, Any], note: Optional[str] = None) -> None:
        line = f"[tool call] id={tool_id} tool={tool} args={args}"
        if note:
            line += f" note={note}"
        print(line)

    def on_tool_result(self, tool_id: str, result: Dict[str, Any]) -> None:
        print(f"[tool result] id={tool_id} -> {str(result)[:4000]}")

    def on_approval_required(self, tool: str, tool_id: str, reason: str, args: Dict[str, Any], token: Optional[str] = None) -> Union[bool, _Defer]:
        print(f"[approval] tool={tool} id={tool_id} reason={reason} args={args}")
        if self.auto_approve:
            print("[approval] auto-approve=ON -> approved")
            return True
        while True:
            yn = input("Approve? [y/N] (Shift+Tab to toggle auto-approve, or type '/auto'): ")
            if yn.strip().lower() in {"y", "yes"}:
                return True
            if yn.strip().lower() in {"n", "no", ""}:
                return False
            if yn.strip().lower().startswith("/auto"):
                # toggle or set explicitly
                parts = yn.strip().split()
                if len(parts) == 1 or parts[1].lower() == "toggle":
                    self.auto_approve = not self.auto_approve
                elif parts[1].lower() in {"on", "true", "1"}:
                    self.auto_approve = True
                elif parts[1].lower() in {"off", "false", "0"}:
                    self.auto_approve = False
                print(f"[approval] auto-approve set to {self.auto_approve}")
                if self.auto_approve:
                    return True
                continue
            # Some terminals pass Shift+Tab as ESC[Z
            if yn == "\x1b[Z":
                self.auto_approve = not self.auto_approve
                print(f"[approval] auto-approve toggled -> {self.auto_approve}")
                if self.auto_approve:
                    return True
                continue

    def on_final(self, content: str) -> None:
        print()  # ensure newline after streaming
        print("assistant>", content)

    def on_reasoning(self, text: Optional[str]) -> None:
        if text:
            # Show a generous amount for detailed summaries
            print("[reasoning]", text[:12000])

    def on_raw(self, data: Any) -> None:
        # Only show raw when verbose mode is on
        if not self.show_raw or data is None:
            return
        try:
            import json
            pretty = json.dumps(data, ensure_ascii=False, indent=2)
        except Exception:
            pretty = str(data)
        print("[raw]", pretty[:12000])

    def on_stream_text(self, text: str) -> None:
        import sys
        if not self._stream_started:
            sys.stdout.write("assistant> ")
            self._stream_started = True
        sys.stdout.write(text)
        sys.stdout.flush()

    def on_stream_reasoning(self, text: str) -> None:
        import sys
        if not self._stream_reason_started:
            sys.stdout.write("\nreasoning> ")
            self._stream_reason_started = True
        sys.stdout.write(text)
        sys.stdout.flush()


class EventRecorder(EventSink):
    def __init__(self) -> None:
        self.events: List[Dict[str, Any]] = []

    def on_assistant_raw(self, text: str) -> None:
        self.events.append({"type": "assistant_raw", "text": text})

    def on_tool_call(self, tool: str, tool_id: str, args: Dict[str, Any], note: Optional[str] = None) -> None:
        self.events.append({"type": "tool_call", "tool": tool, "id": tool_id, "args": args, "note": note})

    def on_tool_result(self, tool_id: str, result: Dict[str, Any]) -> None:
        self.events.append({"type": "tool_result", "id": tool_id, "result": result})

    def on_approval_required(self, tool: str, tool_id: str, reason: str, args: Dict[str, Any], token: Optional[str] = None) -> Union[bool, _Defer]:
        self.events.append({"type": "approval", "tool": tool, "id": tool_id, "reason": reason, "args": args, "token": token})
        # Defer to UI for decision
        return APPROVAL_DEFER

    def on_final(self, content: str) -> None:
        self.events.append({"type": "final", "content": content})

    def on_reasoning(self, text: Optional[str]) -> None:
        if text:
            self.events.append({"type": "reasoning", "text": text})

    def on_raw(self, data: Any) -> None:
        if data is not None:
            self.events.append({"type": "raw", "data": data})
