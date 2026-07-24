// The soundtrack: a continuous PLAYLIST of three streamed tracks — war1, war2, radio — that
// plays on a loop the whole session. Each finishes and the next begins; when the last ends it
// wraps to the first. Streamed through one <audio> element rather than decoded into WebAudio,
// because they're multi-megabyte files and this starts playback immediately.

// The battle song and Killer Space Tuna, played BACK AND FORTH: one ends, the other begins,
// then back again, forever. (warsound2 and radio are still in public/audio if you want them
// added to the rotation later — just drop them in this list.)
const PLAYLIST = [
  "/audio/warsound.mp3",         // the battle song
  "/audio/killerspacetuna.mp3",  // and back to Killer Space Tuna
];
const VOLUME = 0.3;        // background, under the sound effects
const FADE_MS = 1200;

export class Music {
  constructor(volume = VOLUME) {
    this.volume = volume;
    this.muted = false;
    this.started = false;
    this.idx = 0;
    this.el = new Audio(PLAYLIST[0]);
    this.el.preload = "auto";
    this.el.volume = 0;
    // When one track finishes, roll straight into the next — the whole point of a playlist.
    this.el.addEventListener("ended", () => this.advance());
    this._fade = null;
  }

  advance() {
    this.idx = (this.idx + 1) % PLAYLIST.length;
    this.el.src = PLAYLIST[this.idx];
    if (this.started && !this.muted) this.el.play().catch(() => {});
  }

  /** Call from a user gesture (pointer lock). Safe to call repeatedly. */
  start() {
    if (this.started || this.muted) return;
    this.started = true;
    this.el.play().then(() => this.fade(this.volume, FADE_MS)).catch(() => { this.started = false; });
  }

  /** Kept for the caller's sake — the playlist plays the same everywhere now. */
  setPlace() {}

  setPaused(paused) {
    if (!this.started) return;
    if (paused) this.el.pause();
    else if (!this.muted) this.el.play().catch(() => {});
  }

  /** Explicit pause/resume for the death screen. */
  pause() { this.el.pause(); }
  resume() { if (this.started && !this.muted) this.el.play().catch(() => {}); }

  toggle() {
    this.muted = !this.muted;
    if (this.muted) this.el.pause();
    else if (this.started) this.el.play().catch(() => {});
    else this.start();
    return !this.muted;
  }

  fade(target, ms = FADE_MS) {
    const from = this.el.volume;
    const t0 = performance.now();
    clearInterval(this._fade);
    this._fade = setInterval(() => {
      const t = Math.min(1, (performance.now() - t0) / ms);
      this.el.volume = Math.max(0, Math.min(1, from + (target - from) * t));
      if (t >= 1) clearInterval(this._fade);
    }, 33);
  }
}
