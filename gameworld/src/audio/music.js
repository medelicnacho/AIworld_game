// Quiet looping soundtrack.
//
// Streamed through an <audio> element rather than decoded into a WebAudio buffer: the track
// is ~3MB, it starts playing immediately instead of after a full download+decode, and it
// costs no heap. Browsers block audio until a user gesture, so playback starts on pointer
// lock (the click that begins play) — never on page load, which would just throw.

const TRACK = "/audio/donkeybeats.mp3";
const VOLUME = 0.22;        // background, not foreground — it should sit under footsteps
const FADE_MS = 1400;

export class Music {
  constructor(src = TRACK, volume = VOLUME) {
    this.volume = volume;
    this.muted = false;
    this.started = false;
    this.el = new Audio(src);
    this.el.loop = true;
    this.el.preload = "auto";
    this.el.volume = 0;
  }

  /** Call from a user gesture (pointer lock). Safe to call repeatedly. */
  start() {
    if (this.started || this.muted) return;
    this.started = true;
    this.el.play().then(() => this.fadeTo(this.volume)).catch(() => {
      // Autoplay still refused — not fatal, the game is silent until the next gesture.
      this.started = false;
    });
  }

  toggle() {
    this.muted = !this.muted;
    if (this.muted) this.fadeTo(0, 300);
    else if (this.started) this.fadeTo(this.volume);
    else this.start();
    return !this.muted;
  }

  fadeTo(target, ms = FADE_MS) {
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
