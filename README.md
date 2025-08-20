# Agentic Server (Minimal, Multi‑Provider)

개요
- 우분투 서버에서 로컬/클라우드 LLM(OpenAI/Anthropic/Ollama)을 선택해 작업을 계획하고 도구(run shell, 파일 IO, 간단 웹 요청)를 실행하는 최소 에이전트입니다.
- 안전장치: 승인 정책(on-request/never/always), 셸 명령 위험도 분류(안전/쓰기/네트워크/파괴적), 작업 디렉터리 격리, 타임아웃, 로그.

빠른 시작
1) 파이썬 3.10+ 준비 후 환경 변수 설정
   - 프로바이더별 예시를 복사: 
     - OpenAI: `cp .env.openai.example .env`
     - Anthropic: `cp .env.anthropic.example .env`
     - Ollama: `cp .env.ollama.example .env`
     - OpenRouter: `cp .env.openrouter.example .env`
     - LM Studio: `cp .env.lmstudio.example .env`
2) 각 예시에 주석된 값 채우기(키/모델명/엔드포인트 등)
3) 실행(단일 작업): `python -m agentic.cli "<하고 싶은 작업 설명>"`
   - 기본 프로바이더/모델/포트는 `.env`의 `AGENT_PROVIDER`/`AGENT_MODEL`/`AGENT_SERVE_PORT`를 사용합니다.
4) 대화형 모드: `python -m agentic.cli --chat --provider openrouter --model openrouter/anthropic/claude-3.5-sonnet`
5) 웹 UI: `python -m agentic.cli --serve` (포트/프로바이더는 .env 기본값 사용)

설치/의존성
- 표준 라이브러리만 사용합니다(urllib). 별도 설치 없이 동작합니다.
- 네트워크가 제한된 환경에서는 모델 호출이 실패할 수 있습니다. 이 경우 로컬 Ollama 사용을 권장합니다.

프로바이더
- OpenAI: 환경변수 `OPENAI_API_KEY`, 기본 모델 예: `gpt-4o-mini`
- Anthropic: `ANTHROPIC_API_KEY`, 기본 모델 예: `claude-3-5-sonnet-20240620`
- Ollama: 기본 `http://localhost:11434` (예: `qwen2.5:latest`, `llama3.1:latest`). 원격 서버 사용 시 `--ollama-url http://<host>:11434` 또는 `OLLAMA_BASE_URL` 설정
- OpenRouter: `OPENROUTER_API_KEY` 필요. `OPENROUTER_BASE_URL`(선택), `OPENROUTER_REFERER`/`OPENROUTER_APP_NAME`(선택)
 - LM Studio: 로컬 OpenAI 호환 서버(기본 `http://localhost:1234`). `--lmstudio-url` 또는 `LMSTUDIO_BASE_URL`로 변경 가능

CLI 사용 예시
- 안전 모드(on-request 승인):
  `python -m agentic.cli "nginx 설치하고 포트 80 열어줘" --approval on-request`
- 완전 허용(주의):
  `python -m agentic.cli "리포 정리하고 docker compose 올려" --approval never --safe-mode unrestricted`
 - 원격 Ollama 사용:
  `python -m agentic.cli "현재 폴더 파일 목록" --ollama-url http://10.0.0.12:11434`
 - tmux 세션 제어(모델이 호출하는 예):
  1) 세션 생성: `{ "type":"tool", "tool":"tmux", "id":"t1", "args": {"action":"ensure", "name":"agent", "cwd":"/home/ubuntu"} }`
  2) 명령 전송: `{ "type":"tool", "tool":"tmux", "id":"t2", "args": {"action":"send", "name":"agent", "command":"htop"} }`
  3) 화면 캡처: `{ "type":"tool", "tool":"tmux", "id":"t3", "args": {"action":"capture", "name":"agent", "last_lines":200} }`
 - 대화형 모드: `python -m agentic.cli --chat --provider anthropic --model claude-3-5-sonnet-20240620`
 - 웹 UI: `python -m agentic.cli --serve --provider ollama --port 8080` 후 브라우저 접속
 - LM Studio 사용: `python -m agentic.cli --chat --provider lmstudio --model <lmstudio의 모델 이름>`
 - Reasoning 활성화: `python -m agentic.cli --chat --provider openrouter --model openrouter/openai/o3-mini --reasoning on --reasoning-effort medium`

대화형/웹 UI
- CLI 대화형: 도구 호출/결과/승인 요청을 즉시 출력합니다. `--verbose`로 모델의 원문(JSON)도 표시됩니다.
- 웹 UI: 단일 HTML 페이지(표준 라이브러리 서버)에서 이벤트 로그를 순차 출력합니다.
- 승인 대화: 웹 UI에서 승인 카드가 뜨면 Approve/Deny 버튼으로 응답합니다. 자동 승인 토글 버튼으로 ON/OFF 설정 가능합니다.
- CLI 승인 토글: 승인 프롬프트에서 Shift+Tab 또는 `/auto`(on/off/toggle)로 자동 승인 모드를 전환할 수 있습니다.
- 설정 기본값: `.env`에 `AGENT_PROVIDER`, `AGENT_MODEL`, `AGENT_APPROVAL`, `AGENT_SAFE_MODE`, `AGENT_SERVE_PORT` 등을 지정하면 CLI 옵션 없이도 동작합니다.
 - Reasoning 표시: reasoning 지원 모델 사용 시 추론 메시지가 `[reasoning]`(CLI) 또는 `reasoning>`(웹)로 별도 표시됩니다.

승인 정책
- never: 자동 실행(위험). 
- on-request: 위험/네트워크/쓰기 명령만 대화형 승인.
- always: 모든 도구 호출 시 승인.

도구 목록
- run_shell: 셸 명령 실행(shlex 분해, shell=False). 타임아웃/작업 폴더 지원.
- read_file / write_file / list_dir: 파일 읽기/쓰기/디렉터리 나열(작업 루트 하위 제한).
- web_get: 간단 GET(네트워크 제한 환경에서는 실패 가능).
- web_search: DuckDuckGo 기반 간단 검색(query→title/url 리스트).
- tmux: 터미널 세션 제어(ensure|send|capture|list).
- manage_service: systemctl 관리(시스템/유저) start/stop/restart/status 등.
- git: 제한된 Git 명령 실행(`args` 문자열, `cwd` 지정 가능).
- browser_headless: Chromium 헤드리스 DOM 덤프, 실패 시 web_get으로 대체.
- mcp: MCP 서버 레지스트리/호출(`stdio` JSON-RPC 미니 클라이언트 내장)
  - 등록: `{ "type":"tool","tool":"mcp","id":"t1","args":{ "action":"register", "name":"my-mcp", "command":["uvx","my-mcp-server"], "cwd":"/home/ubuntu" } }`
  - 서버 목록: `{ "type":"tool","tool":"mcp","id":"t2","args":{ "action":"list_servers" } }`
  - 도구 목록: `{ "type":"tool","tool":"mcp","id":"t3","args":{ "action":"list_tools", "name":"my-mcp" } }`
  - 도구 호출: `{ "type":"tool","tool":"mcp","id":"t4","args":{ "action":"call_tool", "name":"my-mcp", "tool":"search", "arguments": {"q":"nginx"} } }`
  - 설정 읽기/쓰기: `get_config` / `set_config` (전체 레지스트리 JSON 교체)
- 파일 관리: `delete_path`, `move_path`, `copy_path`, `make_dir`, `replace_in_file`
  - 예: `{ "type":"tool","tool":"delete_path","id":"t1","args":{"path":"./tmp","recursive":true} }`
  - 예: `{ "type":"tool","tool":"replace_in_file","id":"t2","args":{"path":"app.py","find":"DEBUG=True","replace":"DEBUG=False"} }`
- 메모리: `memory_add`, `memory_search`, `memory_list`, `memory_update`, `memory_delete` (.agentic/memory.jsonl, 로컬 임베딩 기반 유사도)
  - 추가: `{ "type":"tool","tool":"memory_add","id":"m1","args":{"text":"nginx 설정 완료","tags":["ops","nginx"]} }`
  - 검색: `{ "type":"tool","tool":"memory_search","id":"m2","args":{"query":"nginx", "top_k":5} }`
- 계획: `plan`(create|get|list|delete|add_step|update_step) → .agentic/plans/<id>.json 저장
  - 생성: `{ "type":"tool","tool":"plan","id":"p1","args":{"action":"create","title":"웹 배포","steps":["이미지 빌드","컨테이너 실행","헬스체크"]} }`

모델 출력 프로토콜(중요)
- 모델은 반드시 JSON만 출력합니다. 두 형태 중 하나:
  1) 도구 호출: `{ "type":"tool", "id":"t1", "tool":"run_shell", "args":{...}, "note":"짧은 이유(optional)" }`
  2) 최종 응답: `{ "type":"final", "content":"...사용자에게 보여줄 결과..." }`
- 여러 개의 도구 호출이 필요한 경우 에이전트가 결과를 다시 컨텍스트로 제공하므로 한 번에 하나씩 요청하세요.

보안/격리
- 작업 루트 디렉터리(기본: 현재 디렉터리) 밖의 파일 접근은 차단됩니다.
- 명령 위험도 분류: sudo/apt/pip/docker/systemctl/rm 등은 위험 또는 네트워크/쓰기/파괴적 분류로 승인 필요 또는 차단.
- on-request 모드에서 승인 필요: tmux(send), manage_service, git(write/network), web_get/web_search/browser_headless, 파일 쓰기/삭제/이동/디렉터리 생성/치환, run_shell의 위험 명령.
- mcp: register/unregister/set_config/call_tool은 승인 필요(도구 정의에 따라 외부 호출 가능성 존재).

제한 사항
- 네트워크 제한/프록시 환경에서 OpenAI/Anthropic 호출 실패 가능.
- LLM이 JSON 이외 형식으로 응답하면 파서가 재시도를 유도합니다.
- MCP: 내장 클라이언트는 stdio + JSON-RPC 최소 메서드(initialize/tools.list/tools.call)만 지원합니다. 특정 서버는 확장 핸드셰이크나 추가 메서드를 요구할 수 있습니다.
 - Reasoning: 공급자/모델별 필드가 상이합니다. OpenAI/OpenRouter는 reasoning_content를, Anthropic은 thinking 블록을 활용할 수 있습니다. 미지원 모델은 reasoning이 표시되지 않습니다.

개발 메모
- 최소 의존성, 모듈 구조 간결화. 필요 시 http 클라이언트 교체만으로 확장 가능.
