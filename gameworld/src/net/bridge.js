// The browser half of the bridge (STAGES.md Stage 1).
//
// THE RULE THIS FILE EXISTS TO ENFORCE: the bridge is an enhancement, never a dependency.
// If the Python process is not running — or dies mid-session — the game must behave exactly
// as it did before any of this existed. So every call here fails SOFT: it returns null, it
// never throws into the frame loop, and it never blocks it. Reconnection is the client's
// job and it retries quietly on a backoff, forever, without spamming the console.
//
// Transport is deliberately boring: SSE down (a long-lived GET), POST up. No websockets,
// no library, nothing for the lab to install.

const DEFAULT_URL = "http://127.0.0.1:8777";
const BACKOFF = [1000, 2000, 4000, 8000, 15000];   // ms between reconnect attempts

export class Bridge {
  constructor(url = DEFAULT_URL) {
    this.url = url;
    this.state = "offline";        // offline | connecting | online
    this.info = null;              // /health payload
    this.tick = 0;
    this.lastMs = null;            // latency of the most recent /line
    this.attempt = 0;
    this.es = null;
    this._tickCbs = [];
    this._eventCbs = [];
    this._timer = null;
  }

  onTick(cb) { this._tickCbs.push(cb); }
  onEvent(cb) { this._eventCbs.push(cb); }

  connect() {
    if (this.state === "connecting" || this.es) return;
    this.state = "connecting";

    // EventSource retries on its own, but with no backoff control and a console error per
    // attempt. Owning the lifecycle keeps a missing bridge quiet, which matters because
    // NOT running it is a supported way to play.
    let es;
    try {
      es = new EventSource(`${this.url}/stream`);
    } catch {
      return this._retry();
    }
    this.es = es;

    es.onopen = () => {
      this.state = "online";
      this.attempt = 0;
      this._health();
    };

    es.onmessage = (ev) => {
      let data;
      try { data = JSON.parse(ev.data); } catch { return; }
      this.tick = data.tick;
      for (const cb of this._tickCbs) cb(data);
      for (const e of data.events || []) for (const cb of this._eventCbs) cb(e);
    };

    es.onerror = () => {
      es.close();
      this.es = null;
      this.state = "offline";
      this.info = null;
      this._retry();
    };
  }

  _retry() {
    if (this._timer) return;
    const wait = BACKOFF[Math.min(this.attempt++, BACKOFF.length - 1)];
    this._timer = setTimeout(() => {
      this._timer = null;
      this.state = "offline";
      this.connect();
    }, wait);
  }

  async _health() {
    const r = await this._get("/health");
    if (r) this.info = r;
  }

  async _get(path) {
    try {
      const res = await fetch(this.url + path);
      return res.ok ? await res.json() : null;
    } catch { return null; }
  }

  async _post(path, body) {
    try {
      const res = await fetch(this.url + path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      return res.ok ? res : null;
    } catch { return null; }
  }

  /** Player speech into the world. Returns null when offline — callers must cope. */
  async say(text) {
    const res = await this._post("/say", { text });
    return res ? res.json() : null;
  }

  /**
   * Generate a spoken line: prompt -> model -> voice.
   * @returns {Promise<{text:string, audio:ArrayBuffer|null, ms:object}|null>}
   */
  async line(prompt, { words = 18, voice } = {}) {
    const res = await this._post("/line", { prompt, words, voice });
    if (!res) return null;
    let data;
    try { data = await res.json(); } catch { return null; }
    if (data.error) return null;
    this.lastMs = (data.ms?.llm || 0) + (data.ms?.tts || 0);

    let audio = null;
    try {
      const a = await fetch(this.url + data.audio);
      if (a.ok) audio = await a.arrayBuffer();
    } catch { /* text without audio is still usable */ }
    return { text: data.text, audio, ms: data.ms };
  }

  /** Voice an exact string (no model involved). */
  async speak(text, voice) {
    const res = await this._post("/speak", { text, voice });
    if (!res) return null;
    try { return await res.arrayBuffer(); } catch { return null; }
  }

  get label() {
    if (this.state === "online") {
      const ms = this.lastMs ? `  ${this.lastMs}ms` : "";
      return `bridge online${this.info?.world ? " · world" : ""}${ms}`;
    }
    return this.state === "connecting" ? "bridge connecting…" : "bridge offline";
  }
}
