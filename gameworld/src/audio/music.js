// The soundtrack: a continuous PLAYLIST of three streamed tracks — war1, war2, radio — that
// plays on a loop the whole session. Each finishes and the next begins; when the last ends it
// wraps to the first. Streamed through one <audio> element rather than decoded into WebAudio,
// because they're multi-megabyte files and this starts playback immediately.

// The full soundtrack, played on a loop: each track finishes and the next begins, wrapping
// forever. So you hear ALL of them over time, not just the first — war 1, then Killer Space
// Tuna, then war 2, then the radio, then back to war 1.
const PLAYLIST = [
  "/audio/warsound.mp3",         // war 1 — the battle song
  "/audio/killerspacetuna.mp3",  // Killer Space Tuna
  "/audio/warsound2.mp3",        // war 2
  "/audio/radio.mp3",            // the radio
];
const VOLUME = 0.3;        // background, under the sound effects

export class Music {
  constructor(volume = VOLUME) {
    this.volume = volume;
    this.muted = false;
    this.started = false;
    this.idx = 0;
    this.el = new Audio(PLAYLIST[0]);
    this.el.preload = "auto";
    this.el.volume = this.volume;
    // When one track finishes, roll straight into the next — the whole point of a playlist.
    this.el.addEventListener("ended", () => this.advance());
    // A bad/slow track shouldn't kill the whole soundtrack — skip to the next.
    this.el.addEventListener("error", () => { if (this.started) this.advance(); });
  }

  advance() {
    this.idx = (this.idx + 1) % PLAYLIST.length;
    this.el.src = PLAYLIST[this.idx];
    this.el.load();          // fetch the new track before we ask it to play
    this.play();
  }

  /** The one place a real play() happens — only when it SHOULD be sounding, so redundant
   *  callers can't abort each other's promise and leave the track playing silently. */
  play() {
    if (!this.started || this.muted) return;
    this.el.volume = this.volume;         // set DIRECTLY, never via a promise that may abort
    if (this.el.paused) {
      this.el.play().catch((e) => console.warn("[music] play blocked:", e?.name || e));
    }
  }

  /** Call from a user gesture (pointer lock). Safe to call repeatedly. */
  start() {
    if (this.started) return;
    this.started = true;
    this.play();
  }

  /** Kept for the caller's sake — the playlist plays the same everywhere now. */
  setPlace() {}

  setPaused(paused) {
    if (!this.started) return;
    if (paused) this.el.pause();
    else this.play();
  }

  /** Explicit pause/resume for the death screen. */
  pause() { this.el.pause(); }
  resume() { this.play(); }

  toggle() {
    this.muted = !this.muted;
    if (this.muted) this.el.pause();
    else if (this.started) this.play();
    else this.start();
    return !this.muted;
  }
}
