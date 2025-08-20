from __future__ import annotations

import argparse
import sys
from typing import Optional

from .config import load_from_env
from .orchestrator import Orchestrator
from .providers.openai_provider import OpenAIProvider
from .providers.anthropic_provider import AnthropicProvider
from .providers.ollama_provider import OllamaProvider
from .providers.openrouter_provider import OpenRouterProvider
from .providers.lmstudio_provider import LMStudioProvider


def build_provider(cfg):
    if cfg.provider == "openai":
        if not cfg.openai_api_key:
            print("OPENAI_API_KEY is required for OpenAI provider", file=sys.stderr)
            sys.exit(2)
        return OpenAIProvider(api_key=cfg.openai_api_key, base_url=cfg.openai_base_url)
    if cfg.provider == "anthropic":
        if not cfg.anthropic_api_key:
            print("ANTHROPIC_API_KEY is required for Anthropic provider", file=sys.stderr)
            sys.exit(2)
        return AnthropicProvider(api_key=cfg.anthropic_api_key, base_url=cfg.anthropic_base_url)
    if cfg.provider == "ollama":
        return OllamaProvider(base_url=cfg.ollama_base_url)
    if cfg.provider == "openrouter":
        if not cfg.openrouter_api_key:
            print("OPENROUTER_API_KEY is required for OpenRouter provider", file=sys.stderr)
            sys.exit(2)
        return OpenRouterProvider(
            api_key=cfg.openrouter_api_key,
            base_url=cfg.openrouter_base_url,
            referer=cfg.openrouter_referer,
            app_name=cfg.openrouter_app_name,
        )
    if cfg.provider == "lmstudio":
        return LMStudioProvider(base_url=cfg.lmstudio_base_url)
    print(f"Unknown provider: {cfg.provider}", file=sys.stderr)
    sys.exit(2)


def parse_args(argv: Optional[list] = None):
    p = argparse.ArgumentParser(description="Minimal agentic CLI (multi-provider)")
    p.add_argument("task", nargs="?", help="하고 싶은 작업 자연어 설명")
    p.add_argument("--provider", choices=["ollama", "openai", "anthropic", "openrouter", "lmstudio"], default=None)
    p.add_argument("--model", default=None)
    p.add_argument("--approval", choices=["never", "on-request", "always"], default=None)
    p.add_argument("--safe-mode", choices=["safe", "extended", "unrestricted"], default=None)
    p.add_argument("--ollama-url", default=None, help="Ollama base URL (e.g., http://otherhost:11434)")
    p.add_argument("--lmstudio-url", default=None, help="LM Studio base URL (e.g., http://localhost:1234)")
    p.add_argument("--workspace", default=None, help="작업 루트 디렉터리")
    p.add_argument("--config-dir", default=None, help="설정 디렉터리(기본: <workspace>/.agentic)")
    p.add_argument("--max-steps", type=int, default=None)
    p.add_argument("--request-timeout", type=int, default=None)
    p.add_argument("--tool-timeout", type=int, default=None)
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--reasoning", choices=["off", "on", "auto"], default=None, help="추론(reasoning) 사용 여부")
    p.add_argument("--reasoning-effort", choices=["low", "medium", "high"], default=None, help="추론 강도")
    p.add_argument("--stream", dest="stream", action="store_true", help="스트리밍 출력 사용")
    p.add_argument("--no-stream", dest="stream", action="store_false", help="스트리밍 끔")
    p.set_defaults(stream=None)
    p.add_argument("--chat", action="store_true", help="대화형 모드")
    p.add_argument("--serve", action="store_true", help="웹 UI 서버 실행")
    p.add_argument("--port", type=int, default=None, help="웹 서버 포트(기본: AGENT_SERVE_PORT 또는 8080)")
    return p.parse_args(argv)


def main(argv: Optional[list] = None) -> int:
    args = parse_args(argv)
    cfg = load_from_env(
        provider=args.provider,
        model=args.model,
        approval_policy=args.approval,
        safe_mode=args.safe_mode,
        workspace_root=args.workspace,
        config_dir=args.config_dir,
        max_steps=args.max_steps,
        verbose=bool(args.verbose),
        request_timeout=args.request_timeout,
        tool_timeout=args.tool_timeout,
        ollama_base_url=args.ollama_url,
        reasoning_mode=args.reasoning,
        reasoning_effort=args.reasoning_effort,
        lmstudio_base_url=args.lmstudio_url,
        stream=args.stream,
    )
    provider = build_provider(cfg)
    orch = Orchestrator(provider, cfg)
    if args.serve:
        from .webserver import serve
        return serve(orch, port=(args.port if args.port is not None else cfg.serve_port))
    if args.chat:
        from .events import CLISink
        sink = CLISink(show_raw=args.verbose)
        print("Entering chat mode. Type 'exit' to quit.")
        while True:
            try:
                line = input("you> ")
            except EOFError:
                break
            if not line or line.strip().lower() in {"exit", "quit"}:
                break
            if line.strip().lower().startswith("/auto"):
                parts = line.strip().split()
                if len(parts) == 1 or parts[1].lower() == "toggle":
                    sink.auto_approve = not sink.auto_approve
                elif parts[1].lower() in {"on", "true", "1"}:
                    sink.auto_approve = True
                elif parts[1].lower() in {"off", "false", "0"}:
                    sink.auto_approve = False
                print(f"[auto] auto-approve set to {sink.auto_approve}")
                continue
            if cfg.stream:
                orch.chat_stream(line, sink=sink)
            else:
                orch.chat_once(line, sink=sink)
        return 0
    if args.task:
        from .events import CLISink
        sink = CLISink(show_raw=args.verbose)
        result = orch.run(args.task, sink=sink)
        if result:
            print(result)
        return 0
    else:
        print("Either provide a task, or use --chat or --serve", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
