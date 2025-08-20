from __future__ import annotations

import json
from typing import Dict, List, Any, Tuple

from .config import AppConfig
from .logging_utils import log_jsonl
from .providers.base import Message
from .tools import (
    read_file,
    write_file,
    list_dir,
    run_shell,
    classify_command_risk,
    web_get,
    web_search,
    tmux_ensure_session,
    tmux_send,
    tmux_capture,
    tmux_list_sessions,
    manage_service,
    run_git,
    classify_git_risk,
    headless_browse,
    delete_path,
    move_path,
    copy_path,
    make_dir,
    replace_in_file,
    memory_add,
    memory_search,
    memory_delete,
    memory_list,
    memory_update,
    plan_create,
    plan_get,
    plan_list,
    plan_delete,
    plan_add_step,
    plan_update_step,
)
from .mcp.registry import load_registry, save_registry, MCPServer, parse_command
from .mcp.client import MCPStdIOClient
from .events import EventSink, NullSink, APPROVAL_DEFER
import uuid
from .utils import extract_json_object, summarize


TOOL_SCHEMA = {
    "run_shell": {
        "args": {"cmd": "str", "timeout": "int(optional)", "cwd": "str(optional)"}
    },
    "read_file": {"args": {"path": "str", "max_bytes": "int(optional)"}},
    "write_file": {
        "args": {"path": "str", "content": "str", "append": "bool(optional)"}
    },
    "list_dir": {"args": {"path": "str"}},
    "web_get": {"args": {"url": "str", "max_bytes": "int(optional)"}},
    "web_search": {"args": {"query": "str", "max_results": "int(optional)"}},
    "tmux": {
        "args": {
            "action": "str(ensure|send|capture|list)",
            "name": "str(optional)",
            "cwd": "str(optional)",
            "command": "str(optional)",
            "last_lines": "int(optional)"
        }
    },
    "manage_service": {
        "args": {"unit": "str", "action": "str(start|stop|restart|reload|enable|disable|status)", "user": "bool(optional)"}
    },
    "git": {"args": {"args": "str", "cwd": "str(optional)"}},
    "browser_headless": {"args": {"url": "str", "engine": "str(optional)", "timeout": "int(optional)"}},
    "mcp": {
        "args": {
            "action": "str(register|unregister|list_servers|list_tools|call_tool|get_config|set_config)",
            "name": "str(optional)",
            "command": "str|list(optional)",
            "cwd": "str(optional)",
            "env": "object(optional)",
            "tool": "str(optional)",
            "arguments": "object(optional)",
            "config": "object(optional)"
        }
    },
    "delete_path": {"args": {"path": "str", "recursive": "bool(optional)"}},
    "move_path": {"args": {"src": "str", "dst": "str", "overwrite": "bool(optional)"}},
    "copy_path": {"args": {"src": "str", "dst": "str", "overwrite": "bool(optional)"}},
    "make_dir": {"args": {"path": "str"}},
    "replace_in_file": {"args": {"path": "str", "find": "str", "replace": "str", "count": "int(optional)", "regex": "bool(optional)"}},
    "memory_add": {"args": {"text": "str", "tags": "array(optional)", "meta": "object(optional)"}},
    "memory_search": {"args": {"query": "str", "top_k": "int(optional)", "tag": "str(optional)"}},
    "memory_delete": {"args": {"id": "str"}},
    "memory_list": {"args": {"limit": "int(optional)", "tag": "str(optional)"}},
    "memory_update": {"args": {"id": "str", "text": "str(optional)", "tags": "array(optional)", "meta": "object(optional)"}},
    "plan": {"args": {"action": "str(create|get|list|delete|add_step|update_step)", "id": "str(optional)", "title": "str(optional)", "steps": "array(optional)", "index": "int(optional)", "status": "str(optional)", "text": "str(optional)"}},
}


def system_prompt(config: AppConfig) -> str:
    return (
        "You are a capable, careful system agent for Ubuntu servers.\n"
        "Always respond with strict JSON in one of two forms.\n"
        "1) Tool call: {\"type\":\"tool\", \"id\":\"t1\", \"tool\":<tool_name>, \"args\":{...}, \"note\":\"short rationale(optional)\"}\n"
        "2) Final answer: {\"type\":\"final\", \"content\":\"...\"}\n"
        "Available tools and their args schema: "
        + json.dumps(TOOL_SCHEMA)
        + "\nRules: Use one tool call at a time. Keep arguments minimal. \n"
        "Rationales must be high-level and avoid sensitive chain-of-thought. Do not include extra summaries.\n"
        "Ask for clarification if requirements are ambiguous before running destructive actions."
    )


class Orchestrator:
    def __init__(self, provider, config: AppConfig) -> None:
        self.provider = provider
        self.config = config
        self.messages: List[Message] = [{"role": "system", "content": system_prompt(config)}]
        self._pending: Dict[str, Any] | None = None
        self._cancel_requested: bool = False

    def append_user(self, content: str) -> None:
        self.messages.append({"role": "user", "content": content})

    def append_assistant(self, content: str) -> None:
        self.messages.append({"role": "assistant", "content": content})

    def append_tool_result(self, tool_id: str, result: Dict[str, Any]) -> None:
        # Feed back as user message to keep provider compatibility
        summary = summarize(json.dumps(result, ensure_ascii=False), 5000)
        content = f"TOOL_RESULT[{tool_id}]: {summary}"
        self.messages.append({"role": "user", "content": content})

    def needs_approval(self, tool: str, args: Dict[str, Any]) -> Tuple[bool, str]:
        if self.config.approval_policy == "always":
            return True, "approval policy is 'always'"
        if tool == "run_shell":
            risk = classify_command_risk(args.get("cmd", ""))
            if risk in {"network", "write", "destructive"}:
                return self.config.approval_policy == "on-request", f"risk={risk}"
        if tool == "git":
            risk = classify_git_risk(args.get("args", ""))
            if risk in {"network", "write"}:
                return self.config.approval_policy == "on-request", f"risk={risk}"
        if tool == "tmux":
            action = (args.get("action") or "").lower()
            if action in {"send"}:
                return self.config.approval_policy == "on-request", f"tool=tmux action={action}"
        if tool == "mcp":
            action = (args.get("action") or "").lower()
            if action in {"register", "unregister", "set_config", "call_tool"}:
                return self.config.approval_policy == "on-request", f"tool=mcp action={action}"
        if tool in {"write_file", "web_get", "web_search", "browser_headless", "manage_service", "delete_path", "move_path", "copy_path", "make_dir", "replace_in_file"}:
            return self.config.approval_policy == "on-request", f"tool={tool}"
        return False, "safe"

    def execute_tool(self, tool: str, args: Dict[str, Any]) -> Dict[str, Any]:
        ws = self.config.workspace_root
        if tool == "run_shell":
            timeout = int(args.get("timeout", self.config.tool_timeout))
            cwd = args.get("cwd") or str(ws)
            return run_shell(args.get("cmd", ""), timeout=timeout, cwd=cwd)
        if tool == "read_file":
            return read_file(args["path"], workspace_root=ws, max_bytes=int(args.get("max_bytes", 200_000)))
        if tool == "write_file":
            return write_file(args["path"], args.get("content", ""), workspace_root=ws, append=bool(args.get("append", False)))
        if tool == "list_dir":
            return list_dir(args["path"], workspace_root=ws)
        if tool == "web_get":
            return web_get(args["url"], max_bytes=int(args.get("max_bytes", 200_000)))
        if tool == "tmux":
            action = (args.get("action") or "").lower()
            name = args.get("name") or "agent"
            if action == "ensure":
                return tmux_ensure_session(name=name, cwd=args.get("cwd"))
            if action == "send":
                return tmux_send(name=name, command=args.get("command", ""))
            if action == "capture":
                return tmux_capture(name=name, last_lines=int(args.get("last_lines", 500)))
            if action == "list":
                return tmux_list_sessions()
            return {"error": f"unknown tmux action {action}"}
        if tool == "manage_service":
            return manage_service(unit=args.get("unit", ""), action=args.get("action", "status"), user=bool(args.get("user", False)))
        if tool == "git":
            return run_git(args=args.get("args", ""), cwd=args.get("cwd") or str(ws))
        if tool == "browser_headless":
            return headless_browse(url=args.get("url", ""), engine=args.get("engine"), timeout=int(args.get("timeout", 60)))
        if tool == "mcp":
            return self._handle_mcp(args)
        if tool == "web_search":
            return web_search(args.get("query", ""), max_results=int(args.get("max_results", 5)))
        if tool == "delete_path":
            return delete_path(args.get("path", ""), workspace_root=ws, recursive=bool(args.get("recursive", False)))
        if tool == "move_path":
            return move_path(args.get("src", ""), args.get("dst", ""), workspace_root=ws, overwrite=bool(args.get("overwrite", False)))
        if tool == "copy_path":
            return copy_path(args.get("src", ""), args.get("dst", ""), workspace_root=ws, overwrite=bool(args.get("overwrite", False)))
        if tool == "make_dir":
            return make_dir(args.get("path", ""), workspace_root=ws)
        if tool == "replace_in_file":
            return replace_in_file(args.get("path", ""), args.get("find", ""), args.get("replace", ""), workspace_root=ws, count=args.get("count"), regex=bool(args.get("regex", False)))
        if tool == "memory_add":
            return memory_add(self.config.config_dir, text=args.get("text", ""), tags=args.get("tags"), meta=args.get("meta"))
        if tool == "memory_search":
            return memory_search(self.config.config_dir, query=args.get("query", ""), top_k=int(args.get("top_k", 5)), tag=args.get("tag"))
        if tool == "memory_delete":
            return memory_delete(self.config.config_dir, entry_id=args.get("id", ""))
        if tool == "memory_list":
            return memory_list(self.config.config_dir, limit=int(args.get("limit", 50)), tag=args.get("tag"))
        if tool == "memory_update":
            return memory_update(self.config.config_dir, entry_id=args.get("id", ""), text=args.get("text"), tags=args.get("tags"), meta=args.get("meta"))
        if tool == "plan":
            action = (args.get("action") or "").lower()
            if action == "create":
                return plan_create(self.config.config_dir, title=args.get("title", ""), steps=args.get("steps"))
            if action == "get":
                return plan_get(self.config.config_dir, plan_id=args.get("id", ""))
            if action == "list":
                return plan_list(self.config.config_dir)
            if action == "delete":
                return plan_delete(self.config.config_dir, plan_id=args.get("id", ""))
            if action == "add_step":
                return plan_add_step(self.config.config_dir, plan_id=args.get("id", ""), text=args.get("text", ""))
                
            if action == "update_step":
                return plan_update_step(self.config.config_dir, plan_id=args.get("id", ""), index=int(args.get("index", 0)), status=args.get("status", "pending"))
            return {"error": f"unknown plan action {action}"}
        return {"error": f"unknown tool {tool}"}

    def _handle_mcp(self, args: Dict[str, Any]) -> Dict[str, Any]:
        action = (args.get("action") or "").lower()
        reg_path = self.config.mcp_registry_file
        servers = load_registry(reg_path)
        if action == "list_servers":
            return {"path": str(reg_path), "servers": [s.to_dict() for s in servers.values()]}
        if action == "register":
            name = args.get("name")
            if not name:
                return {"error": "name is required"}
            command = parse_command(args.get("command") or [])
            srv = MCPServer(name=name, command=command, cwd=args.get("cwd"), env=args.get("env") or {}, enabled=True)
            servers[name] = srv
            save_registry(reg_path, servers)
            return {"saved": True, "server": srv.to_dict(), "path": str(reg_path)}
        if action == "unregister":
            name = args.get("name")
            if not name:
                return {"error": "name is required"}
            if name in servers:
                del servers[name]
                save_registry(reg_path, servers)
                return {"removed": True, "name": name}
            return {"removed": False, "error": "not found"}
        if action == "get_config":
            return {"path": str(reg_path), "config": {"servers": [s.to_dict() for s in servers.values()]}}
        if action == "set_config":
            cfg = args.get("config") or {}
            new_servers = {}
            for item in cfg.get("servers", []):
                srv = MCPServer.from_dict(item)
                new_servers[srv.name] = srv
            save_registry(reg_path, new_servers)
            return {"saved": True, "count": len(new_servers)}
        if action in {"list_tools", "call_tool"}:
            name = args.get("name")
            if not name:
                return {"error": "name is required"}
            srv = servers.get(name)
            if not srv:
                return {"error": f"server {name} not found"}
            if srv.transport != "stdio":
                return {"error": f"transport {srv.transport} not supported"}
            client = MCPStdIOClient(command=srv.command, cwd=srv.cwd, env=srv.env)
            try:
                client.open()
                if action == "list_tools":
                    return client.list_tools()
                if action == "call_tool":
                    tool = args.get("tool")
                    if not tool:
                        return {"error": "tool is required"}
                    return client.call_tool(tool, args.get("arguments") or {})
            except Exception as e:
                return {"error": str(e)}
            finally:
                try:
                    client.close()
                except Exception:
                    pass
        return {"error": f"unknown action {action}"}

    def run(self, task: str, sink: EventSink | None = None) -> str:
        return self.chat_once(f"Task: {task}", sink=sink)

    def chat_once(self, user_input: str, sink: EventSink | None = None) -> str:
        sink = sink or NullSink()
        self.append_user(user_input)
        final_output = ""
        for step in range(1, self.config.max_steps + 1):
            output = self.provider.generate(
                self.messages,
                model=self.config.model,
                request_timeout=self.config.request_timeout,
                reasoning=self.config.reasoning_mode != "off",
                reasoning_effort=self.config.reasoning_effort,
            )
            # Normalize
            if isinstance(output, dict):
                text = output.get("content", "")
                reasoning_text = output.get("reasoning")
                raw = output.get("raw")
            else:
                text = str(output or "")
                reasoning_text = None
                raw = None
            log_jsonl(self.config.log_dir, "llm", {"direction": "assistant", "text": text, "reasoning": reasoning_text, "raw": raw})
            sink.on_reasoning(reasoning_text)
            if raw is not None:
                sink.on_raw(raw)
            sink.on_assistant_raw(text or "")
            obj = extract_json_object(text or "")
            if not obj:
                # Ask model to correct to JSON
                self.append_user("Please respond with valid JSON per protocol.")
                continue
            if obj.get("type") == "final":
                final_output = str(obj.get("content", ""))
                sink.on_final(final_output)
                break
            if obj.get("type") == "tool":
                tool = obj.get("tool")
                tool_id = obj.get("id") or f"t{step}"
                args = obj.get("args") or {}
                note = obj.get("note")
                sink.on_tool_call(tool, tool_id, args, note)
                need, reason = self.needs_approval(tool, args)
                if need:
                    token = str(uuid.uuid4())
                    decision = sink.on_approval_required(tool, tool_id, reason, args, token=token)
                    if decision is APPROVAL_DEFER:
                        # Store pending approval and break to let UI handle it
                        self._pending = {"token": token, "tool": tool, "tool_id": tool_id, "args": args}
                        break
                    if not decision:
                        self.append_user(f"Tool {tool} was denied by user. Provide alternative or ask clarification.")
                        continue
                result = self.execute_tool(tool, args)
                log_jsonl(self.config.log_dir, "tool", {"tool": tool, "args": args, "result": result})
                sink.on_tool_result(tool_id, result)
                self.append_tool_result(tool_id, result)
                continue
            # Unknown type; ask to comply
            self.append_user("Invalid response. Use type=tool or type=final JSON.")
        return final_output

    def chat_stream(self, user_input: str, sink: EventSink | None = None) -> str:
        sink = sink or NullSink()
        self._cancel_requested = False  # reset cancel flag for this run
        self.append_user(user_input)
        final_output = ""
        for step in range(1, self.config.max_steps + 1):
            gen = None
            if hasattr(self.provider, "generate_stream"):
                gen = self.provider.generate_stream(
                    self.messages,
                    model=self.config.model,
                    request_timeout=self.config.request_timeout,
                    reasoning=self.config.reasoning_mode != "off",
                    reasoning_effort=self.config.reasoning_effort,
                )
            if gen is None:
                # Fallback to non-stream path for this step
                return self.chat_once(user_input if step == 1 else "", sink)

            full_text: List[str] = []
            full_reason: List[str] = []
            raw_last = None

            # Early cancel check
            if self._cancel_requested:
                try:
                    gen.close()
                except Exception:
                    pass
                return ""

            for ev in gen:
                # Mid-stream cancel check
                if self._cancel_requested:
                    try:
                        gen.close()
                    except Exception:
                        pass
                    return ""
                if not isinstance(ev, dict):
                    continue
                if ev.get("event") == "delta":
                    if ev.get("text"):
                        full_text.append(ev.get("text"))
                        # Don't stream assistant JSON body
                    if ev.get("reasoning"):
                        full_reason.append(ev.get("reasoning"))
                        sink.on_stream_reasoning(ev.get("reasoning"))
                if ev.get("event") == "final":
                    raw_last = ev.get("raw")
                    text = ev.get("content", "")
                    reasoning_text = ev.get("reasoning")
                    if not text:
                        text = "".join(full_text)
                    if reasoning_text is None and full_reason:
                        reasoning_text = "".join(full_reason)
                    log_jsonl(self.config.log_dir, "llm", {"direction": "assistant", "text": text, "reasoning": reasoning_text, "raw": raw_last})
                    sink.on_reasoning(reasoning_text)
                    if raw_last is not None:
                        sink.on_raw(raw_last)
                    sink.on_assistant_raw(text or "")
                    obj = extract_json_object(text or "")
                    if not obj:
                        self.append_user("Please respond with valid JSON per protocol.")
                        break
                    if obj.get("type") == "final":
                        final_output = str(obj.get("content", ""))
                        sink.on_final(final_output)
                        return final_output
                    if obj.get("type") == "tool":
                        tool = obj.get("tool")
                        tool_id = obj.get("id") or f"t{step}"
                        args = obj.get("args") or {}
                        note = obj.get("note")
                        sink.on_tool_call(tool, tool_id, args, note)
                        need, reason = self.needs_approval(tool, args)
                        if need:
                            token = str(uuid.uuid4())
                            decision = sink.on_approval_required(tool, tool_id, reason, args, token=token)
                            if decision is APPROVAL_DEFER:
                                self._pending = {"token": token, "tool": tool, "tool_id": tool_id, "args": args}
                                return ""
                            if not decision:
                                self.append_user(f"Tool {tool} was denied by user. Provide alternative or ask clarification.")
                                break
                        result = self.execute_tool(tool, args)
                        log_jsonl(self.config.log_dir, "tool", {"tool": tool, "args": args, "result": result})
                        sink.on_tool_result(tool_id, result)
                        self.append_tool_result(tool_id, result)
                        # Continue loop to next step with tool result in context
                        break
        return final_output

    def has_pending_approval(self) -> bool:
        return self._pending is not None

    def get_pending_info(self) -> Dict[str, Any] | None:
        if not self._pending:
            return None
        return {k: self._pending[k] for k in ("token", "tool", "tool_id", "args")}

    def resolve_approval(self, token: str, approve: bool, sink: EventSink | None = None) -> Dict[str, Any]:
        sink = sink or NullSink()
        if not self._pending or self._pending.get("token") != token:
            return {"error": "no matching pending approval"}
        pending = self._pending
        self._pending = None
        tool = pending["tool"]
        tool_id = pending["tool_id"]
        args = pending["args"]
        if not approve:
            self.append_user(f"Tool {tool} was denied by user. Provide alternative or ask clarification.")
            return {"approved": False}
        result = self.execute_tool(tool, args)
        log_jsonl(self.config.log_dir, "tool", {"tool": tool, "args": args, "result": result})
        sink.on_tool_result(tool_id, result)
        self.append_tool_result(tool_id, result)
        return {"approved": True, "result": result}

    def request_cancel(self) -> None:
        """Signal the current streaming operation to cancel asap."""
        self._cancel_requested = True
