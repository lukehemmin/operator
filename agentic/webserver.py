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
  <title>Agentic Web Chat</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 2rem; }
    #log { white-space: pre-wrap; border: 1px solid #ccc; padding: 1rem; height: 60vh; overflow: auto; }
    #input { width: 80%; }
    .evt { margin-bottom: .5rem; }
    .tool { color: #064; }
    .res { color: #333; }
    .final { color: #047; font-weight: bold; }
    .approval { background: #fffbe6; padding: .5rem; border: 1px dashed #cc0; }
    details { margin: .25rem 0; }
    pre { background: #f7f7f7; padding: .5rem; overflow: auto; }
  </style>
</head>
<body>
  <h2>Agentic Web Chat</h2>
  <div style=\"margin-bottom: .5rem\">
    <span id=\"auto\">auto-approve: ...</span>
    <button onclick=\"toggleAuto()\">Toggle Auto</button>
  </div>
  <div id=\"log\"></div>
  <div style=\"margin-top:1rem\">
    <input id=\"input\" placeholder=\"메시지를 입력하고 Enter\" />
    <button onclick=\"send()\">Send</button>
  </div>
  <script>
    const log = document.getElementById('log');
    const input = document.getElementById('input');
    input.addEventListener('keydown', (e)=>{ if(e.key==='Enter'){ send(); }});
    function append(line, cls){ const div=document.createElement('div'); div.className='evt '+(cls||''); div.textContent=line; log.appendChild(div); log.scrollTop=log.scrollHeight; }
    function appendApproval(ev){
      const div=document.createElement('div'); div.className='evt approval';
      div.textContent=`[approval] ${ev.tool} ${JSON.stringify(ev.args)} reason=${ev.reason}`;
      const btnY=document.createElement('button'); btnY.textContent='Approve'; btnY.onclick=()=>approve(ev.token,true,div);
      const btnN=document.createElement('button'); btnN.textContent='Deny'; btnN.onclick=()=>approve(ev.token,false,div);
      div.appendChild(document.createElement('br'));
      div.appendChild(btnY); div.appendChild(btnN);
      log.appendChild(div); log.scrollTop=log.scrollHeight;
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
      d.appendChild(pre); log.appendChild(d); log.scrollTop=log.scrollHeight;
    }
    // Streaming session state and helpers
    let sess = null;
    function beginSession(){ sess = {assistantEl:null, reasoningEl:null, raw:null, reasoningBuf:''}; }
    function ensureAssistantEl(){ if(!sess.assistantEl){ const div=document.createElement('div'); div.className='evt'; div.textContent='assistant> '; log.appendChild(div); sess.assistantEl=div; } return sess.assistantEl; }
    function ensureReasoningEl(){ if(!sess.reasoningEl){ const div=document.createElement('div'); div.className='evt'; div.textContent='reasoning> '; log.appendChild(div); sess.reasoningEl=div; } return sess.reasoningEl; }
    function collapseReasoning(){
      if(!sess || !sess.reasoningEl) return;
      const text = sess.reasoningBuf || (sess.reasoningEl.textContent||'').replace(/^reasoning>\s*/, '');
      const details = document.createElement('details');
      details.className='evt';
      details.open = false;
      const sum = document.createElement('summary');
      sum.textContent = 'reasoning (click to expand)';
      const pre = document.createElement('pre');
      pre.textContent = text;
      details.appendChild(sum); details.appendChild(pre);
      log.replaceChild(details, sess.reasoningEl);
      sess.reasoningEl = details;
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
      src.addEventListener('tool_call', e=>{ const d=JSON.parse(e.data); append(`[tool] ${d.tool} ${JSON.stringify(d.args)} ${d.note||''}`, 'tool'); });
      src.addEventListener('tool_result', e=>{ const d=JSON.parse(e.data); append(`[result] ${JSON.stringify(d.result).slice(0,1000)}`, 'res'); });
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
                def on_stream_text(self, t: str):
                    send_event('assistant_delta', {"text": t})
                def on_stream_reasoning(self, t: str):
                    send_event('reasoning_delta', {"text": t})
                def on_assistant_raw(self, t: str):
                    send_event('assistant_raw', {"text": t})
                def on_reasoning(self, txt: str | None):
                    if txt:
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
                    send_event('raw', data)

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
