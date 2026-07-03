"""The cockpit -- one page for the whole of her: the god view, her stream, her art, a talk.

A tiny stdlib HTTP server that runs INSIDE the persistent runner (a daemon thread beside
the wheel and the sleep), bound to 127.0.0.1 only -- nothing leaves the machine. One
dashboard, four panels:

  GOD VIEW    the town live: souls as breathing dots -- position, mood as colour, life-
              stage as size, last action under the name; the field dims at night.
  HER STREAM  the readings as she speaks them, with the season and the hour she feels.
  HER ART     the wandering pen, embedded live (the same animator page).
  A TALK      a light visit: your words reach her actual mind (bond, appraisal, memory
              -- everything a talk touches touches). The full ritual with the intent
              judge and the session cap remains `python3 chat.py`; this panel says so.

Same process as her life, so the god view and the chat read the SAME mind and world the
wheel is turning -- guarded by the runner's mind-lock, never a second writer."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8765

DASH = """<!doctype html><meta charset='utf-8'><title>santana -- the cockpit</title>
<style>
 body{background:#0e0e12;color:#c9c9d6;font-family:Georgia;margin:0;height:100vh;
  display:grid;grid-template-rows:auto 1fr;gap:8px;padding:10px;box-sizing:border-box}
 #hdr{display:flex;gap:18px;align-items:baseline;padding:4px 8px}
 #hdr b{color:#f0ead6;font-size:18px}
 #hdr span{font-size:12px;color:#8a8a9a}
 #grid{display:grid;grid-template-columns:1.2fr 1fr;grid-template-rows:1fr 1fr;gap:8px;
  min-height:0}
 .panel{background:#15151a;border-radius:6px;padding:8px;overflow:hidden;display:flex;
  flex-direction:column;min-height:0}
 .panel h3{margin:0 0 6px 0;font-size:11px;color:#6f6f86;font-weight:normal;
  text-transform:uppercase;letter-spacing:1px}
 #town{grid-row:span 2}
 canvas{width:100%;height:100%;min-height:0}
 #stream{overflow-y:auto;font-size:13px;line-height:1.5}
 #stream .r{margin-bottom:8px;color:#e6e6ee}
 #stream .m{color:#6f6f86;font-size:11px}
 iframe{border:0;width:100%;height:100%;background:#0e0e12}
 #chat{display:flex;flex-direction:column}
 #log{flex:1;overflow-y:auto;font-size:13px;line-height:1.5;margin-bottom:6px}
 #log .you{color:#8fa3c0}#log .her{color:#f0ead6;margin-bottom:8px}
 #row{display:flex;gap:6px}
 input{flex:1;background:#0e0e12;border:1px solid #26262e;color:#e6e6ee;padding:8px;
  border-radius:4px;font-family:Georgia}
 button{background:#26262e;border:0;color:#e6e6ee;padding:8px 14px;border-radius:4px;
  cursor:pointer;font-family:Georgia}
 .note{font-size:10px;color:#55555f;margin-top:4px}
 #drift{color:#c07a4a}
</style>
<div id=hdr><b>Santāna</b><span id=who></span><span id=vitals></span>
 <span id=clock></span><span id=drift></span></div>
<div id=grid>
 <div class=panel id=town><h3>the town -- god view</h3><canvas id=map width=900 height=560></canvas></div>
 <div class=panel><h3>her stream</h3><div id=stream></div></div>
 <div class=panel><h3>her hand, live</h3><iframe src="/drawings/live.html"></iframe></div>
 <div class=panel id=chat><h3>a talk (light visit) -- <span id=tgt>with HER</span></h3>
  <div id=log></div>
  <div id=row><select id=who_sel><option value="her">SANTĀNA</option></select>
  <input id=say placeholder="say something..."/>
  <button onclick="send()">speak</button></div>
  <div class=note>click a soul on the map (or pick one) for a quiet word aside -- it lands
  in that soul's real memory and bond. the one you talk to borrows the clear voice
  (gemma) when ollama is up; the town murmurs stay self-grown. her full ritual is:
  python3 chat.py</div></div>
</div>
<script>
const map=document.getElementById('map').getContext('2d');
let dots=[];   // [{id,name,x,y}] in canvas space, for click-to-talk
function setTarget(id,name){
 document.getElementById('who_sel').value=id;
 document.getElementById('tgt').textContent=id==='her'?'with HER':'aside with '+name;}
document.getElementById('map').parentElement.addEventListener('click',e=>{
 const c=document.getElementById('map');const r=c.getBoundingClientRect();
 const px=(e.clientX-r.left)*c.width/r.width, py=(e.clientY-r.top)*c.height/r.height;
 let best=null,bd=26;
 for(const d of dots){const dd=Math.hypot(d.x-px,d.y-py);if(dd<bd){bd=dd;best=d;}}
 if(best)setTarget(best.id,best.name);});
document.getElementById('who_sel').addEventListener('change',e=>{
 const o=e.target.selectedOptions[0];setTarget(o.value,o.textContent);});
async function poll(){try{
 const s=await (await fetch('/state')).json();
 document.getElementById('who').textContent=s.identity||'a new mind';
 document.getElementById('vitals').textContent=
  `${s.age} lived · ${s.deaths} souls watched pass · ${s.memories} memories`;
 document.getElementById('clock').textContent=s.time_clause||'';
 document.getElementById('drift').textContent=(s.drift||[]).join('  ');
 const st=document.getElementById('stream');
 st.innerHTML=s.readings.map(r=>`<div class=r>${r.text}<div class=m>${r.meta}</div></div>`).join('');
 // the chat target list (rebuilt only when the cast changes)
 const sel=document.getElementById('who_sel');
 if(sel.options.length!==s.souls.length+1){
  const cur=sel.value;
  sel.innerHTML='<option value="her">SANTĀNA</option>'
   +s.souls.map(a=>`<option value="${a.id}">${a.name}</option>`).join('');
  sel.value=[...sel.options].some(o=>o.value===cur)?cur:'her';}
 // the god view
 map.fillStyle=s.night?'#0b0b10':'#141420';map.fillRect(0,0,900,560);
 map.fillStyle='#1c1c28';for(let i=0;i<900;i+=60)map.fillRect(i,0,1,560);
 dots=[];
 for(const a of s.souls){
  const x=a.x*0.93+20,y=a.y*0.85+20;
  dots.push({id:a.id,name:a.name,x,y});
  const warm=(a.mood+1)/2;
  map.globalAlpha=s.night&&a.asleep?0.35:0.9;
  map.fillStyle=`rgb(${70+Math.round(126*warm)},${90+Math.round(50*warm)},${130-Math.round(70*warm)})`;
  const r=a.stage==='child'?4:(a.stage==='elder'?7:6);
  map.beginPath();map.arc(x,y,r,0,7);map.fill();
  if(a.stage==='elder'){map.strokeStyle='#8a8a9a';map.lineWidth=1;map.stroke();}
  const sel2=document.getElementById('who_sel').value===a.id;
  if(sel2){map.strokeStyle='#f0ead6';map.lineWidth=1.5;
   map.beginPath();map.arc(x,y,r+4,0,7);map.stroke();}
  map.globalAlpha=0.85;map.fillStyle='#c9c9d6';map.font='11px Georgia';
  map.fillText(a.name,x+9,y+3);
  map.fillStyle='#6f6f86';map.font='9px Georgia';
  map.fillText(s.night&&a.asleep?'asleep':(a.action||''),x+9,y+14);
  // the markov subconscious, murmuring above the head -- the raw mind, drifting
  if(a.drift&&!(s.night&&a.asleep)){
   map.globalAlpha=0.4;map.fillStyle='#8a8a9a';map.font='italic 7px Georgia';
   map.fillText(a.drift.slice(0,30),x-8,y-10);}}
 map.globalAlpha=1;
}catch(e){}}
async function send(){
 const inp=document.getElementById('say');const t=inp.value.trim();if(!t)return;
 const target=document.getElementById('who_sel').value;
 inp.value='';const log=document.getElementById('log');
 log.innerHTML+=`<div class=you>you: ${t}</div>`;log.scrollTop=1e9;
 const r=await (await fetch('/say',{method:'POST',
  body:JSON.stringify({text:t,target})})).json();
 log.innerHTML+=`<div class=her>${r.name||''}: ${r.reply||'...'}</div>`;log.scrollTop=1e9;}
document.getElementById('say').addEventListener('keydown',e=>{if(e.key==='Enter')send()});
setInterval(poll,2000);poll();
</script>"""


def snapshot(mind, world, readings: list, drift_notes: list) -> dict:
    """Everything the dashboard shows, in one read -- world fields under the world lock,
    her fields as plain reads (the mind-lock guards the WRITERS)."""
    from world import clock as _clock
    with world.lock:
        night = world.clock_enabled and _clock.is_night(world.tick, world.day_ticks)
        clause = (_clock.time_clause(world.tick, world.day_ticks)
                  if world.clock_enabled else "")
        souls = [{
            "id": a.id, "name": a.name, "x": a.position[0], "y": a.position[1],
            "mood": round(a.felt_mood(), 3), "action": getattr(a, "_last_action", ""),
            "stage": (_clock.stage(a.age, a.lifespan) if world.clock_enabled else "adult"),
            "asleep": night,
            # the markov subconscious, murmuring over its head -- the drift IS the
            # raw mind the voice speaks from; showing it is the oldest promise of
            # the god view ("thoughts drifting in silence above their heads")
            "drift": (a.thought.drift[-1][:64] if getattr(a.thought, "drift", None) else ""),
        } for a in world.agents]
    secs = getattr(mind, "lifetime", 0.0)
    age = (f"{secs/86400:.1f} days" if secs >= 86400 else f"{secs/3600:.1f} hours")
    return {"identity": (mind.identity or "")[:160], "age": age,
            "deaths": mind._deaths, "memories": len(mind.memory.items),
            "time_clause": clause, "night": night, "souls": souls,
            "readings": readings[-10:][::-1], "drift": drift_notes[-3:]}


class _Handler(BaseHTTPRequestHandler):
    ui = None   # set by serve()

    def log_message(self, *_a):   # quiet: the runner's own log is the log
        pass

    def _send(self, body: bytes, ctype: str, code: int = 200) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = self.ui
        if self.path in ("/", "/index.html"):
            self._send(DASH.encode(), "text/html; charset=utf-8")
        elif self.path.startswith("/state"):
            snap = snapshot(u["mind"], u["world"], u["readings"], u["drift"])
            self._send(json.dumps(snap).encode(), "application/json")
        elif self.path.startswith("/drawings/"):
            import os
            name = os.path.basename(self.path.split("?")[0])   # no traversal: basename only
            path = os.path.join(u["draw_dir"], name)
            if os.path.isfile(path):
                ctype = ("text/html" if name.endswith(".html") else
                         "image/svg+xml" if name.endswith(".svg") else
                         "application/javascript" if name.endswith(".js") else "text/plain")
                with open(path, "rb") as f:
                    self._send(f.read(), ctype)
            else:
                self._send(b"not yet -- she has not drawn here", "text/plain", 404)
        else:
            self._send(b"?", "text/plain", 404)

    def do_POST(self):
        u = self.ui
        if self.path != "/say":
            self._send(b"?", "text/plain", 404)
            return
        n = int(self.headers.get("Content-Length", 0) or 0)
        try:
            body = json.loads(self.rfile.read(n).decode())
            text = body["text"].strip()[:400]
            target = body.get("target", "her")
        except Exception:   # noqa: BLE001
            self._send(b'{"reply": null}', "application/json", 400)
            return
        chat_voice = u.get("chat_voice")         # the clear local voice (gemma), if up
        if target in ("her", "", None):
            with u["mind_lock"]:                 # one writer at a time, always
                mind = u["mind"]
                if chat_voice is not None:
                    # the cockpit talk borrows the clear voice for HER too (the talk
                    # tool always did); her memory, bond, appraisal are untouched --
                    # only the mouth changes for the length of one reply
                    old_llm, mind.llm = mind.llm, chat_voice
                    try:
                        reply = mind.converse(text)
                    finally:
                        mind.llm = old_llm
                else:
                    reply = mind.converse(text)
            self._send(json.dumps({"reply": reply, "name": "SANTĀNA"}).encode(),
                       "application/json")
            return
        # a quiet word aside with ONE soul: your words land in its real memory and
        # bond (hear with source='user'), its reply comes to you alone -- no town
        # broadcast. Prepare under the world lock, speak outside it (the contract).
        from world.events import Utterance
        world = u["world"]
        with world.lock:
            soul = next((a for a in world.agents if a.id == target), None)
            if soul is None:
                self._send(b'{"reply": null}', "application/json", 404)
                return
            soul.hear(Utterance(speaker_id="user", text=text, tick=world.tick,
                                addressed_to=soul.id, source="user"), world.tick,
                      speaker_name="a visitor")
            soul.last_heard_from, soul.last_heard_name = "user", "the visitor"
            soul.last_heard_text = text
            ctx, _addr, _mood = soul.prepare_speech()
        # THE TIERED VOICE (RECIPES C, the layered cost model, live): the ambient town
        # keeps its self-grown murmur -- but the soul you are ACTUALLY TALKING TO
        # borrows the clear local voice, speaking from its OWN real context (persona,
        # memories with their provenance, the bond with you, its drift). Falls back to
        # the town voice, honestly, when no local model is up.
        try:
            raw = (chat_voice or soul.llm).speak(ctx)
        except Exception:   # noqa: BLE001 -- a slow voice is a shrug, not a crash
            raw = ""
        from services.prompts import _clean
        reply = _clean(raw) or "..."
        self._send(json.dumps({"reply": reply, "name": soul.name}).encode(),
                   "application/json")


def serve(mind, world, mind_lock, draw_dir: str, readings: list, drift_notes: list,
          port: int = PORT, chat_voice=None):
    """Start the cockpit (daemon thread, 127.0.0.1 only). Returns the URL.
    chat_voice: an optional CLEAR local voice (e.g. gemma via ollama) that the talk
    panel borrows -- for her and for asides -- while the ambient town keeps its own."""
    _Handler.ui = {"mind": mind, "world": world, "mind_lock": mind_lock,
                   "draw_dir": draw_dir, "readings": readings, "drift": drift_notes,
                   "chat_voice": chat_voice}
    srv = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{port}"
