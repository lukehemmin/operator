from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class AppConfig:
    provider: str = "ollama"  # ollama|openai|anthropic
    model: str = "llama3.1:latest"
    approval_policy: str = "on-request"  # never|on-request|always
    safe_mode: str = "extended"  # safe|extended|unrestricted
    workspace_root: Path = Path.cwd()
    max_steps: int = 12
    request_timeout: int = 120  # seconds for LLM HTTP
    tool_timeout: int = 180  # seconds for tools (shell etc.)
    verbose: bool = False
    log_dir: Path = Path("logs")
    config_dir: Path = Path(".agentic")
    mcp_registry_file: Path = Path(".agentic/mcp_registry.json")
    serve_port: int = 8080
    reasoning_mode: str = "auto"  # off|on|auto
    reasoning_effort: str = "medium"  # low|medium|high
    stream: bool = True

    # Provider-specific
    openai_api_key: Optional[str] = None
    openai_base_url: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    anthropic_base_url: Optional[str] = None
    ollama_base_url: str = "http://localhost:11434"
    openrouter_api_key: Optional[str] = None
    openrouter_base_url: Optional[str] = None
    openrouter_referer: Optional[str] = None
    openrouter_app_name: Optional[str] = None
    lmstudio_base_url: str = "http://localhost:1234"


def getenv(key: str, default: Optional[str] = None) -> Optional[str]:
    val = os.getenv(key)
    return val if val is not None else default


def load_from_env(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    approval_policy: Optional[str] = None,
    safe_mode: Optional[str] = None,
    workspace_root: Optional[str] = None,
    config_dir: Optional[str] = None,
    max_steps: Optional[int] = None,
    verbose: Optional[bool] = None,
    request_timeout: Optional[int] = None,
    tool_timeout: Optional[int] = None,
    ollama_base_url: Optional[str] = None,
    serve_port: Optional[int] = None,
    lmstudio_base_url: Optional[str] = None,
    reasoning_mode: Optional[str] = None,
    reasoning_effort: Optional[str] = None,
    stream: Optional[bool] = None,
) -> AppConfig:
    cfg = AppConfig()
    if provider:
        cfg.provider = provider
    else:
        cfg.provider = getenv("AGENT_PROVIDER", cfg.provider)

    if model:
        cfg.model = model
    else:
        cfg.model = getenv("AGENT_MODEL", cfg.model)

    if approval_policy:
        cfg.approval_policy = approval_policy
    else:
        cfg.approval_policy = getenv("AGENT_APPROVAL", cfg.approval_policy)

    if safe_mode:
        cfg.safe_mode = safe_mode
    else:
        cfg.safe_mode = getenv("AGENT_SAFE_MODE", cfg.safe_mode)

    if workspace_root:
        cfg.workspace_root = Path(workspace_root).resolve()
    else:
        cfg.workspace_root = Path(getenv("AGENT_WORKSPACE", str(cfg.workspace_root))).resolve()

    if config_dir:
        cfg.config_dir = Path(config_dir)
    else:
        cfg.config_dir = Path(getenv("AGENT_CONFIG_DIR", str(cfg.config_dir)))
    if not cfg.config_dir.is_absolute():
        cfg.config_dir = (cfg.workspace_root / cfg.config_dir).resolve()
    cfg.mcp_registry_file = (cfg.config_dir / "mcp_registry.json").resolve()

    if max_steps is not None:
        cfg.max_steps = max_steps
    else:
        cfg.max_steps = int(getenv("AGENT_MAX_STEPS", str(cfg.max_steps)))

    if request_timeout is not None:
        cfg.request_timeout = request_timeout
    else:
        cfg.request_timeout = int(getenv("AGENT_REQUEST_TIMEOUT", str(cfg.request_timeout)))

    if tool_timeout is not None:
        cfg.tool_timeout = tool_timeout
    else:
        cfg.tool_timeout = int(getenv("AGENT_TOOL_TIMEOUT", str(cfg.tool_timeout)))

    if serve_port is not None:
        cfg.serve_port = serve_port
    else:
        cfg.serve_port = int(getenv("AGENT_SERVE_PORT", str(cfg.serve_port)))
    if reasoning_mode:
        cfg.reasoning_mode = reasoning_mode
    else:
        cfg.reasoning_mode = getenv("AGENT_REASONING", cfg.reasoning_mode)
    if reasoning_effort:
        cfg.reasoning_effort = reasoning_effort
    else:
        cfg.reasoning_effort = getenv("AGENT_REASONING_EFFORT", cfg.reasoning_effort)
    if stream is not None:
        cfg.stream = stream
    else:
        cfg.stream = getenv("AGENT_STREAM", "true").lower() in {"1", "true", "yes", "on"}

    if verbose is not None:
        cfg.verbose = verbose
    else:
        cfg.verbose = getenv("AGENT_VERBOSE", "false").lower() in {"1", "true", "yes", "on"}

    cfg.log_dir = Path(getenv("AGENT_LOG_DIR", str(cfg.log_dir))).resolve()

    cfg.openai_api_key = getenv("OPENAI_API_KEY")
    cfg.openai_base_url = getenv("OPENAI_BASE_URL")
    cfg.anthropic_api_key = getenv("ANTHROPIC_API_KEY")
    cfg.anthropic_base_url = getenv("ANTHROPIC_BASE_URL")
    cfg.ollama_base_url = ollama_base_url or getenv("OLLAMA_BASE_URL", cfg.ollama_base_url)
    cfg.openrouter_api_key = getenv("OPENROUTER_API_KEY")
    cfg.openrouter_base_url = getenv("OPENROUTER_BASE_URL")
    cfg.openrouter_referer = getenv("OPENROUTER_REFERER")
    cfg.openrouter_app_name = getenv("OPENROUTER_APP_NAME")
    cfg.lmstudio_base_url = lmstudio_base_url or getenv("LMSTUDIO_BASE_URL", cfg.lmstudio_base_url)

    return cfg
