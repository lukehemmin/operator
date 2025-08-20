from __future__ import annotations

import json
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import Tuple, Union

from .events import EventRecorder
from .orchestrator import Orchestrator


INDEX_HTML = """
<!doctype html>
<html><head>
  <meta charset=\"utf-8\" />
  <title>Agentic Web</title>
  <style>
    :root { --bg:#f8f9fb; --fg:#0f172a; --muted:#64748b; --panel:#ffffff; --border:#e2e8f0; --accent:#2563eb; }
    .dark { --bg:#0b1220; --fg:#e5e7eb; --muted:#9aa4b2; --panel:#0f172a; --border:#1f2a44; --accent:#60a5fa; }
    *{box-sizing:border-box}
    body{margin:0;background:var(--bg);color:var(--fg);font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Noto Sans KR,Helvetica,Arial}
    .wrap{max-width:980px;margin:0 auto;padding:24px}
    .topbar{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px}
    .brand{font-weight:700;letter-spacing:-.02em}
    .controls{display:flex;gap:8px;align-items:center;color:var(--muted)}
    .btn{border:1px solid var(--border);background:var(--panel);color:var(--fg);padding:6px 10px;border-radius:8px;cursor:pointer}
    .btn:hover{border-color:var(--accent)}
    .badge{padding:2px 8px;border:1px solid var(--border);border-radius:999px;font-size:12px;color:var(--muted)}
    #log{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:16px;height:60vh;overflow:auto;font-family:ui-monospace,Menlo,Consolas,monospace}
    .line{display:grid;grid-template-columns:120px 1fr;gap:10px;align-items:start;padding:6px 4px;border-radius:6px}
    .line .label{color:var(--muted);text-transform:lowercase;letter-spacing:.2px}
    .line .content{white-space:pre-wrap}
    .evt.tool .content{color:#0f5132}
    .evt.res .content{color:#334155}
    .approval{background:color-mix(in oklab,var(--panel) 92%,var(--accent));border:1px dashed var(--accent);border-radius:10px;padding:10px;margin-top:8px}
    details{margin:6px 0}
    pre{margin:6px 0 0;background:transparent;border:1px solid var(--border);border-radius:8px;padding:8px;overflow:auto}
    .composer{display:grid;grid-template-columns:1fr auto;gap:10px;margin-top:14px}
    .input{width:100%;padding:10px 12px;border:1px solid var(--border);border-radius:10px;background:var(--panel);color:var(--fg)}
    .primary{background:var(--accent);color:#fff;border:1px solid var(--accent)}
    .primary:hover{filter:brightness(1.05)}
  </style>
</head>
<body>
  <div class=\"wrap\">
    <div class=\"topbar\">
      <div class=\"brand\">Agentic</div>
      <div class=\"controls\">
        <span class=\"badge\" id=\"auto\">auto-approve: ...</span>
        <button class=\"btn\" onclick=\"toggleAuto()\">Toggle Auto</button>
        <button class=\"btn\" onclick=\"toggleTheme()\">Theme</button>
      </div>
    </div>
    <div id=\"log\"></div>
    <div id=\"tools\" style=\"margin-top:12px\"></div>
    <div id=\"reasoning\" style=\"margin-top:12px\"></div>
    <div class=\"composer\">
      <input class=\"input\" id=\"input\" placeholder=\"메시지를 입력하고 Enter\" />
      <button class=\"btn primary\" onclick=\"send()\">Send</button>
    </div>
  </div>
  <script>
    const log = document.getElementById('log');
    const tools = document.getElementById('tools');
    const reasoningBox = document.getElementById('reasoning');
    const input = document.getElementById('input');
    input.addEventListener('keydown', (e)=>{ if(e.key==='Enter'){ send(); }});
    function append(line, cls){
      const div=document.createElement('div'); div.className='line evt '+(cls||'');
      const lab=document.createElement('span'); lab.className='label';
      const cont=document.createElement('span'); cont.className='content';
      const idx=line.indexOf('> ');
      if(idx>0){ lab.textContent=line.slice(0, idx+1); cont.textContent=line.slice(idx+2); }
      else { lab.textContent=''; cont.textContent=line; }
      div.appendChild(lab); div.appendChild(cont); log.appendChild(div); log.scrollTop=log.scrollHeight;
    }
    function appendTool(line){
      const div=document.createElement('div'); div.className='line evt tool';
      const lab=document.createElement('span'); lab.className='label'; lab.textContent='tool>';
      const cont=document.createElement('span'); cont.className='content'; cont.textContent=line;
      div.appendChild(lab); div.appendChild(cont); tools.appendChild(div); tools.scrollTop=tools.scrollHeight;
    }
    function appendApproval(ev){
      const card=document.createElement('div'); card.className='approval';
      const head=document.createElement('div'); head.style.display='flex'; head.style.justifyContent='space-between'; head.style.alignItems='center';
      const title=document.createElement('div'); title.textContent='Approval required'; head.appendChild(title);
      const actions=document.createElement('div');
      const yes=document.createElement('button'); yes.className='btn primary'; yes.textContent='Approve'; yes.onclick=()=>approve(ev.token,true,card);
      const no=document.createElement('button'); no.className='btn'; no.style.marginLeft='6px'; no.textContent='Deny'; no.onclick=()=>approve(ev.token,false,card);
      actions.appendChild(yes); actions.appendChild(no); head.appendChild(actions);
      const meta=document.createElement('div'); meta.style.marginTop='6px'; meta.textContent=`tool=${ev.tool} reason=${ev.reason}`;
      const pre=document.createElement('pre'); pre.textContent=JSON.stringify(ev.args, null, 2);
      card.appendChild(head); card.appendChild(meta); card.appendChild(pre);
      tools.appendChild(card); tools.scrollTop=tools.scrollHeight;
    }
    async function approve(token, ok, holder){
      holder.textContent = holder.textContent + ` => sending decision...`;
      const resp = await fetch('/api/approve', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({token, approve: ok})});
      const data = await resp.json();
      renderEvents(data.events||[]);
    }
    function appendDetails(title, obj){
      const d=document.createElement('details');
      const s=document.createElement('summary'); s.textContent=title; d.appendChild(s);
      const pre=document.createElement('pre'); pre.textContent=JSON.stringify(obj, null, 2);
      d.appendChild(pre); tools.appendChild(d); tools.scrollTop=tools.scrollHeight;
    }
    // Streaming session state and helpers
    let sess = null;
    function beginSession(){ sess = {assistantEl:null, reasoningEl:null, raw:null, reasoningBuf:''}; }
    function ensureAssistantEl(){ if(!sess.assistantEl){ const div=document.createElement('div'); div.className='line evt'; const lab=document.createElement('span'); lab.className='label'; lab.textContent='assistant>'; const cont=document.createElement('span'); cont.className='content'; div.appendChild(lab); div.appendChild(cont); log.appendChild(div); sess.assistantEl=cont; } return sess.assistantEl; }
    function ensureReasoningEl(){ if(!sess.reasoningEl){ const div=document.createElement('div'); div.className='line evt'; const lab=document.createElement('span'); lab.className='label'; lab.textContent='reasoning>'; const cont=document.createElement('span'); cont.className='content'; div.appendChild(lab); div.appendChild(cont); reasoningBox.appendChild(div); sess.reasoningEl=cont; } return sess.reasoningEl; }
    function collapseReasoning(){
      if(!sess || !sess.reasoningEl) return;
      const text = sess.reasoningBuf || (sess.reasoningEl.textContent||'').replace(/^reasoning>\s*/, '');
      const container = sess.reasoningEl.parentElement;
      const row=document.createElement('div'); row.className='line evt';
      const lab=document.createElement('span'); lab.className='label'; lab.textContent='reasoning>';
      const body=document.createElement('div');
      const det=document.createElement('details'); det.open = false; const sum=document.createElement('summary'); sum.textContent='reasoning (click to expand)'; const pre=document.createElement('pre'); pre.textContent=text; det.appendChild(sum); det.appendChild(pre);
      body.appendChild(det); row.appendChild(lab); row.appendChild(body);
      if (container && container.parentElement) {
        container.parentElement.replaceChild(row, container);
      } else {
        reasoningBox.appendChild(row);
      }
      sess.reasoningEl = null;
    }
    function endSession(){ if(sess && sess.raw){ appendDetails('raw payload', sess.raw); } sess=null; }
    function renderEvents(events){
      events.forEach(ev=>{
        if(ev.type==='assistant_raw') append('assistant(raw)> '+(ev.text||''));
        if(ev.type==='reasoning') append('reasoning> '+(ev.text||''));
        if(ev.type==='tool_call') append(`[tool] ${ev.tool} ${JSON.stringify(ev.args)} ${ev.note||''}`, 'tool');
        if(ev.type==='tool_result') append(`[result] ${JSON.stringify(ev.result).slice(0,1000)}`, 'res');
        if(ev.type==='raw') appendDetails('raw payload', ev.data);
        if(ev.type==='approval') { if(ev.auto){ append(`[approval auto] ${ev.tool}`,'tool'); } else { appendApproval(ev); } }
        if(ev.type==='final') append('final> '+(ev.content||''), 'final');
      });
    }
    async function refreshAuto(){
      const resp = await fetch('/api/auto_approve');
      const data = await resp.json();
      document.getElementById('auto').textContent = 'auto-approve: '+(data.auto_approve?'ON':'OFF');
    }
    async function toggleAuto(){
      const resp = await fetch('/api/auto_approve', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({auto_approve: true})});
      const cur = await resp.json();
      const newVal = !cur.auto_approve;
      const resp2 = await fetch('/api/auto_approve', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({auto_approve: newVal})});
      await refreshAuto();
    }
    async function send(){
      const text = input.value.trim(); if(!text) return; input.value=''; append('you> '+text);
      // Open SSE stream
      beginSession();
      const src = new EventSource('/api/chat_stream?q='+encodeURIComponent(text));
      src.addEventListener('assistant_delta', e=>{
        const d = JSON.parse(e.data); const el = ensureAssistantEl(); el.textContent += d.text;
      });
      src.addEventListener('reasoning_delta', e=>{
        const d = JSON.parse(e.data); const el = ensureReasoningEl(); el.textContent += d.text; if(sess){ sess.reasoningBuf += d.text; }
      });
      // Buffer raw payload; show after final
      src.addEventListener('raw', e=>{ const d=JSON.parse(e.data); if(sess){ sess.raw = d; } });
      src.addEventListener('tool_call', e=>{ const d=JSON.parse(e.data); appendTool(`${d.tool} ${JSON.stringify(d.args)} ${d.note||''}`); });
      src.addEventListener('tool_result', e=>{ const d=JSON.parse(e.data); appendTool(`result ${JSON.stringify(d.result).slice(0,1000)}`); });
      src.addEventListener('approval', e=>{ const d=JSON.parse(e.data); appendApproval(d); });
      src.addEventListener('reasoning', e=>{ const d=JSON.parse(e.data); const el=ensureReasoningEl(); el.textContent = 'reasoning> '+(d.text||''); if(sess){ sess.reasoningBuf = d.text||''; } });
      src.addEventListener('final', e=>{ const d=JSON.parse(e.data); collapseReasoning(); append('assistant> '+(d.content||''), 'final'); endSession(); });
      src.addEventListener('done', e=>{ src.close(); });
    }
    refreshAuto();
  </script>
</body></html>
"""


class Handler(BaseHTTPRequestHandler):
    orch: Orchestrator = None  # type: ignore
    auto_approve: bool = False

    def _send(self, code: int, body: Union[str, bytes], content_type: str = "text/html; charset=utf-8") -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        if isinstance(body, str):
            data = body.encode("utf-8")
        else:
            data = body
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/" or self.path.startswith("/index"):
            self._send(200, INDEX_HTML)
            return
        if self.path.startswith("/api/chat_stream"):
            # Parse query parameter q
            try:
                from urllib.parse import urlparse, parse_qs
                qs = parse_qs(urlparse(self.path).query)
                text = (qs.get("q") or [""])[0]
            except Exception:
                text = ""
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()

            def send_event(name: str, obj):
                try:
                    data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
                    self.wfile.write(f"event: {name}\n".encode("utf-8"))
                    self.wfile.write(b"data: ")
                    self.wfile.write(data)
                    self.wfile.write(b"\n\n")
                    self.wfile.flush()
                except Exception:
                    pass

            class SSESink(EventRecorder):
                def __init__(self):
                    super().__init__()
                    self._sent_reasoning = False
                def on_stream_text(self, t: str):
                    send_event('assistant_delta', {"text": t})
                def on_stream_reasoning(self, t: str):
                    self._sent_reasoning = True
                    send_event('reasoning_delta', {"text": t})
                def on_assistant_raw(self, t: str):
                    send_event('assistant_raw', {"text": t})
                def on_reasoning(self, txt: str | None):
                    if txt:
                        self._sent_reasoning = True
                        send_event('reasoning', {"text": txt})
                def on_tool_call(self, tool, tool_id, args, note=None):
                    send_event('tool_call', {"tool": tool, "id": tool_id, "args": args, "note": note})
                def on_tool_result(self, tool_id, result):
                    send_event('tool_result', {"id": tool_id, "result": result})
                def on_approval_required(self, tool, tool_id, reason, args, token=None):
                    send_event('approval', {"tool": tool, "id": tool_id, "reason": reason, "args": args, "token": token})
                    from agentic.events import APPROVAL_DEFER
                    return APPROVAL_DEFER
                def on_final(self, content: str):
                    send_event('final', {"content": content})
                def on_raw(self, data):
                    # Forward raw payload and attempt to extract reasoning if missing
                    send_event('raw', data)
                    try:
                        obj = data if isinstance(data, dict) else {}
                        if not self._sent_reasoning:
                            # OpenAI/OpenRouter/LM Studio style
                            ch = (obj.get('choices') or [{}])[0]
                            msg = ch.get('message') or {}
                            r = msg.get('reasoning') or ch.get('reasoning')
                            if isinstance(r, str) and r.strip():
                                self._sent_reasoning = True
                                send_event('reasoning', {"text": r})
                    except Exception:
                        pass

            sink = SSESink()
            Handler.orch.chat_stream(text, sink=sink)
            send_event('done', {})
            return
        if self.path.startswith("/api/auto_approve"):
            body = json.dumps({"auto_approve": Handler.auto_approve}).encode("utf-8")
            self._send(200, body, "application/json")
            return
        self._send(404, b"Not Found")

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/api/chat":
            length = int(self.headers.get("Content-Length", "0"))
            data = self.rfile.read(length)
            try:
                payload = json.loads(data.decode("utf-8"))
            except Exception:
                self._send(400, b"Bad JSON", "text/plain")
                return
            text = str(payload.get("input", ""))
            class WebSink(EventRecorder):
                def __init__(self, auto_approve: bool) -> None:
                    super().__init__()
                    self.auto_approve = auto_approve
                def on_approval_required(self, tool, tool_id, reason, args, token=None):
                    if self.auto_approve:
                        self.events.append({"type": "approval", "tool": tool, "id": tool_id, "reason": reason, "args": args, "token": token, "auto": True})
                        return True
                    return super().on_approval_required(tool, tool_id, reason, args, token)

            sink = WebSink(Handler.auto_approve)
            Handler.orch.chat_once(text, sink=sink)
            pending = Handler.orch.get_pending_info()
            body = json.dumps({"events": sink.events, "pending": pending}).encode("utf-8")
            self._send(200, body, "application/json")
            return
        if self.path == "/api/approve":
            length = int(self.headers.get("Content-Length", "0"))
            data = self.rfile.read(length)
            try:
                payload = json.loads(data.decode("utf-8"))
            except Exception:
                self._send(400, b"Bad JSON", "text/plain")
                return
            token = str(payload.get("token", ""))
            approve = bool(payload.get("approve", False))
            sink = EventRecorder()
            result = Handler.orch.resolve_approval(token, approve, sink=sink)
            # If approved, continue one loop of reasoning
            if result.get("approved"):
                Handler.orch.chat_once("", sink=sink)
            body = json.dumps({"result": result, "events": sink.events, "pending": Handler.orch.get_pending_info()}).encode("utf-8")
            self._send(200, body, "application/json")
            return
        if self.path == "/api/auto_approve":
            length = int(self.headers.get("Content-Length", "0"))
            data = self.rfile.read(length)
            try:
                payload = json.loads(data.decode("utf-8"))
            except Exception:
                self._send(400, b"Bad JSON", "text/plain")
                return
            val = payload.get("auto_approve")
            if isinstance(val, bool):
                Handler.auto_approve = val
            body = json.dumps({"auto_approve": Handler.auto_approve}).encode("utf-8")
            self._send(200, body, "application/json")
            return
        self._send(404, b"Not Found")


def serve(orch: Orchestrator, port: int = 8080) -> int:
    Handler.orch = orch
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Serving web UI on http://0.0.0.0:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        server.server_close()
    return 0
