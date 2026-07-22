// Two tracks, crossfaded: one for the frontier, one for inside the walls.
//
// Both stream through <audio> elements rather than decoding into WebAudio buffers — they're
// multi-megabyte files, so this starts playback immediately instead of after a full
// download-and-decode, and costs no heap.
//
// The important behaviour is that BOTH keep running the whole time and only their volumes
// move. Stopping the outside track and starting the town one would restart it from the
// beginning every time you stepped through a gate, and a track that always replays its first
// eight bars becomes maddening fast. Here each one keeps its own position and simply fades.

const TRACKS = {
  world: "/audio/donkeybeats.mp3",
  town: "/audio/chillax.mp3",
};
const VOLUME = 0.22;        // background, not foreground — it sits under footsteps
const FADE_MS = 1400;       // first fade-in
const CROSS_MS = 1100;      // gate crossings: long enough to feel deliberate

export class Music {
  constructor(volume = VOLUME) {
    this.volume = volume;
    this.muted = false;
    this.started = false;
    this.where = "world";
    this.els = {};
    for (const [key, src] of Object.entries(TRACKS)) {
      const el = new Audio(src);
      el.loop = true;
      el.preload = "auto";
      el.volume = 0;
      this.els[key] = el;
    }
    this._fades = {};
  }

  /** Call from a user gesture (pointer lock). Safe to call repeatedly. */
  start() {
    if (this.started || this.muted) return;
    this.started = true;
    // Both play from the outset, one of them silent — so switching later is only a volume
    // change, and the town track is already warm when you first walk through a gate.
    for (const [key, el] of Object.entries(this.els)) {
      el.play().then(() => {
        this.fade(key, key === this.where ? this.volume : 0, FADE_MS);
      }).catch(() => { this.started = false; });
    }
  }

  /** 'world' | 'town' — crossfade if it changed. */
  setPlace(where) {
    if (where === this.where) return;
    this.where = where;
    if (!this.started || this.muted) return;
    for (const key of Object.keys(this.els)) {
      this.fade(key, key === where ? this.volume : 0, CROSS_MS);
    }
  }

  setPaused(paused) {
    if (!this.started) return;
    for (const el of Object.values(this.els)) {
      if (paused) el.pause();
      else if (!this.muted) el.play().catch(() => {});
    }
  }

  toggle() {
    this.muted = !this.muted;
    if (this.muted) {
      for (const key of Object.keys(this.els)) this.fade(key, 0, 300);
    } else if (this.started) {
      for (const key of Object.keys(this.els)) {
        this.fade(key, key === this.where ? this.volume : 0, 300);
      }
    } else {
      this.start();
    }
    return !this.muted;
  }

  fade(key, target, ms = CROSS_MS) {
    const el = this.els[key];
    const from = el.volume;
    const t0 = performance.now();
    clearInterval(this._fades[key]);
    this._fades[key] = setInterval(() => {
      const t = Math.min(1, (performance.now() - t0) / ms);
      el.volume = Math.max(0, Math.min(1, from + (target - from) * t));
      if (t >= 1) clearInterval(this._fades[key]);
    }, 33);
  }
}
