"""The bridge: the game (browser) talks to this lab over localhost.

STAGES.md Stage 1. The browser becomes a VIEW of the Python substrate instead of a
reimplementation of it — which is what lets a validated town reach the game in weeks
rather than after a full TypeScript port (PLAN.md §9, the deferred-port decision).

Deliberately STDLIB ONLY, like the rest of this lab: SSE for server->browser (a plain
long-lived GET writing text/event-stream), POST for browser->server. No websocket
library, no FastAPI, nothing new in requirements.txt.

The contract that matters most is a NEGATIVE one: the game must run exactly as it does
today when this process is not running. The bridge is an enhancement, never a dependency.
Kill it mid-game and nothing should break; start it again and the game reconnects itself.

    python3 bridge.py                      # gemma3:1b (Stage 0's verdict), port 8777
    python3 bridge.py --model gemma3:4b    # slower, better; fine where nobody waits
    python3 bridge.py --no-llm             # TTS + stream only

Endpoints
    GET  /health              {ok, model, llm, tts, voices, world, uptime}
    GET  /stream              SSE @10Hz: {tick, souls:[], events:[]}   (souls arrive Stage 3)
    POST /say     {text}      the player speaks into the world         (stub until Stage 3)
    POST /speak   {text,voice}            -> audio/wav bytes
    POST /line    {prompt,voice,words}    -> {text, ms:{llm,tts}} + X-Audio-Id header
    GET  /audio/<id>.wav      the wav for a /line response
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from services.llm import OllamaLLM          # noqa: E402
from services.tts import PiperTTS, Voice    # noqa: E402

DEFAULT_MODEL = "gemma3:1b"    # Stage 0: 1.99s to speech vs 4.68s at 4b, on CPU
DEFAULT_VOICE = "en_US-lessac-medium.onnx"
ALLOW_ORIGIN = "http://localhost:5173"
STREAM_HZ = 10
AUDIO_TTL = 120.0              # seconds a generated wav stays fetchable

# Stage 0's design finding, enforced at the source rather than trusted to the prompt:
# a companion line that runs ten seconds is too long at ANY latency.
WORD_CAP = 34


class Hub:
    """Shared state. One instance, guarded where it needs to be."""

    def __init__(self, model: str, use_llm: bool = True) -> None:
        self.started = time.time()
        self.tick = 0
        self.world = None                 # Stage 3 puts a real World here
        self.events: list[dict] = []
        self.lock = threading.Lock()
        self.tts_lock = threading.Lock()  # piper is CPU-heavy; don't let requests thrash
        self.llm_lock = threading.Lock()

        self.tts = PiperTTS() if PiperTTS.available() else None
        self.llm = None
        if use_llm:
            llm = OllamaLLM(model=model)
            self.llm = llm if llm.available() else None
        self.model = model
        self.audio: dict[str, tuple[float, bytes]] = {}

        threading.Thread(target=self._clock, daemon=True).start()

    def _clock(self) -> None:
        """The heartbeat. Stage 3 replaces the body of this with world.advance()."""
        while True:
            time.sleep(1.0 / STREAM_HZ)
            with self.lock:
                self.tick += 1
                dead = [k for k, (t, _) in self.audio.items() if time.time() - t > AUDIO_TTL]
                for k in dead:
                    self.audio.pop(k, None)

    def snapshot(self) -> dict:
        with self.lock:
            evs, self.events = self.events, []
            return {"tick": self.tick, "t": round(time.time() - self.started, 2),
                    "souls": [], "events": evs}

    def push_event(self, kind: str, **data) -> None:
        with self.lock:
            self.events.append({"kind": kind, **data})

    # --- generation -----------------------------------------------------------

    def synth(self, text: str, voice: str) -> bytes:
        if not self.tts:
            raise RuntimeError("no piper voices -- run scripts/get_voices.sh")
        with self.tts_lock:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                path = f.name
            try:
                self.tts.synth_to(text, Voice(model=voice), path)
                return Path(path).read_bytes()
            finally:
                Path(path).unlink(missing_ok=True)

    def generate(self, prompt: str, words: int = 18) -> str:
        if not self.llm:
            raise RuntimeError("ollama unavailable")
        system = (f"Reply in ONE sentence of at most {words} words. "
                  "No preamble, no quotation marks, no stage directions.")
        with self.llm_lock:
            text = self.llm.generate(prompt, system=system,
                                     num_predict=int(words * 2.2)).strip()
        return self.trim(text, words)

    @staticmethod
    def trim(text: str, words: int) -> str:
        """Belt and braces on line length: a small model WILL run long when it feels
        like it, and Stage 0 showed length is the difference between a companion and a
        monologue. Cut to the first sentence, then hard-cap the words."""
        text = text.replace("\n", " ").strip().strip('"“”')
        m = re.search(r"^(.+?[.!?])(\s|$)", text)
        if m:
            text = m.group(1)
        parts = text.split()
        if len(parts) > words:
            text = " ".join(parts[:words]).rstrip(",;:") + "…"
        return text


class Handler(BaseHTTPRequestHandler):
    hub: Hub = None            # set on the server before serve_forever
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):     # quiet; SSE would spam a line per connect
        pass

    # --- plumbing --------------------------------------------------------------

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", ALLOW_ORIGIN)
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def _json(self, obj, code: int = 200, extra: dict | None = None) -> None:
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _bytes(self, data: bytes, ctype: str, extra: dict | None = None) -> None:
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self._cors()
        self.end_headers()
        self.wfile.write(data)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    # --- routes ----------------------------------------------------------------

    def do_GET(self):
        hub = self.hub
        if self.path.startswith("/health"):
            return self._json({
                "ok": True, "model": hub.model,
                "llm": hub.llm is not None, "tts": hub.tts is not None,
                "voices": sorted(p.name for p in (Path(__file__).parent / "data" / "voices")
                                 .glob("*.onnx")) if hub.tts else [],
                "world": hub.world is not None,
                "uptime": round(time.time() - hub.started, 1),
            })

        if self.path.startswith("/stream"):
            return self._stream()

        if self.path.startswith("/audio/"):
            key = self.path.rsplit("/", 1)[-1].removesuffix(".wav")
            entry = hub.audio.get(key)
            if not entry:
                return self._json({"error": "expired"}, 404)
            return self._bytes(entry[1], "audio/wav")

        return self._json({"error": "not found"}, 404)

    def _stream(self):
        """SSE. One thread per client (ThreadingHTTPServer), writing at STREAM_HZ.

        A dropped client raises on write -- that is the NORMAL way this ends (the player
        closed the tab, or the game reloaded), so it is caught and returned quietly rather
        than logged as an error.
        """
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self._cors()
        self.end_headers()
        try:
            while True:
                payload = json.dumps(self.hub.snapshot())
                self.wfile.write(f"data: {payload}\n\n".encode())
                self.wfile.flush()
                time.sleep(1.0 / STREAM_HZ)
        except (BrokenPipeError, ConnectionResetError, OSError):
            return

    def do_POST(self):
        hub, body = self.hub, self._body()

        if self.path.startswith("/say"):
            text = (body.get("text") or "").strip()
            if not text:
                return self._json({"error": "empty"}, 400)
            # Stage 3 replaces this with world.inject_user(text); until then it is
            # recorded so the round trip is testable end to end.
            hub.push_event("player_said", text=text)
            return self._json({"ok": True, "heard_by": 0, "world": hub.world is not None})

        if self.path.startswith("/speak"):
            text = (body.get("text") or "").strip()
            if not text:
                return self._json({"error": "empty"}, 400)
            try:
                t0 = time.perf_counter()
                wav = hub.synth(text, body.get("voice") or DEFAULT_VOICE)
            except Exception as e:                                  # noqa: BLE001
                return self._json({"error": str(e)}, 503)
            return self._bytes(wav, "audio/wav",
                               {"X-Synth-Ms": str(round((time.perf_counter() - t0) * 1000))})

        if self.path.startswith("/line"):
            prompt = (body.get("prompt") or "").strip()
            if not prompt:
                return self._json({"error": "empty"}, 400)
            words = min(int(body.get("words") or 18), WORD_CAP)
            try:
                t0 = time.perf_counter()
                text = hub.generate(prompt, words)
                t1 = time.perf_counter()
                wav = hub.synth(text, body.get("voice") or DEFAULT_VOICE)
                t2 = time.perf_counter()
            except Exception as e:                                  # noqa: BLE001
                return self._json({"error": str(e)}, 503)
            key = uuid.uuid4().hex[:12]
            with hub.lock:
                hub.audio[key] = (time.time(), wav)
            return self._json({"text": text, "audio": f"/audio/{key}.wav",
                               "ms": {"llm": round((t1 - t0) * 1000),
                                      "tts": round((t2 - t1) * 1000)}})

        return self._json({"error": "not found"}, 404)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8777)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--no-llm", action="store_true")
    args = ap.parse_args()

    hub = Hub(args.model, use_llm=not args.no_llm)
    Handler.hub = hub

    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    srv.daemon_threads = True
    print(f"[bridge] http://127.0.0.1:{args.port}  model={args.model} "
          f"llm={'ok' if hub.llm else 'OFF'} tts={'ok' if hub.tts else 'OFF'}")
    print("[bridge] the game runs fine without this. Ctrl-C to stop.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n[bridge] stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
