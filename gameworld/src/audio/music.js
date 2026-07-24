// Layered, place-aware soundtrack. Every channel is its own looping <audio> that streams the
// whole time; crossing the city gate only changes VOLUMES, so nothing restarts from the top.
//
//   BED (everywhere) — war 1, war 2 and radio all play AT THE SAME TIME, each on its own loop.
//                      Always audible, city and frontier alike. Radio is mixed down; it was
//                      drowning the war tracks.
//   OUTSIDE, on top  — donkey beats, looping, over the war bed on the frontier.
//   IN CITY, on top  — chillax, the town track we had.
//
// Each track carries its own gain (0..1) so the layers balance; the master VOLUME sits under it.
// (To change the mix, edit the lists below.)

const BED_TRACKS = [
  { src: "/audio/warsound.mp3", gain: 1.0 },   // war 1
  { src: "/audio/warsound2.mp3", gain: 1.0 },  // war 2
  { src: "/audio/radio.mp3", gain: 0.4 },      // radio — quieter, it was too loud
];
const OUTSIDE_TRACK = { src: "/audio/donkeybeats.mp3", gain: 0.85 };  // frontier track
const TOWN_TRACK = { src: "/audio/chillax.mp3", gain: 1.0 };          // the city track we had

const VOLUME = 0.24;       // master, kept low so the layers don't clip
const CROSS_MS = 1100;     // gate-crossing fade

export class Music {
  constructor(volume = VOLUME) {
    this.volume = volume;
    this.muted = false;
    this.started = false;
    this.where = "world";

    // The war/radio bed: three independent forever-loops, always on.
    this.bed = BED_TRACKS.map((t) => this.makeLoop(t));

    // Two place layers, each a single loop faded in only in its own place.
    this.town = this.makeLoop(TOWN_TRACK);   // inside the city
    this.out = this.makeLoop(OUTSIDE_TRACK);  // out on the frontier
  }

  makeLoop({ src, gain }) {
    const el = new Audio(src);
    el.loop = true;
    el.volume = 0;
    el._gain = gain;   // per-track balance, multiplied into the master below
    return el;
  }

  els() { return [...this.bed, this.town, this.out]; }

  /** Make sure every channel is STREAMING. Volume decides what's heard; playing them all keeps
   *  the layers in the mix. */
  ensurePlaying() {
    if (!this.started || this.muted) return;
    for (const el of this.els()) {
      if (el.paused) el.play().catch((e) => console.warn("[music] play blocked:", e?.name || e));
    }
  }

  /** Call from a user gesture (pointer lock, or any click/key). Idempotent. */
  start() {
    if (!this.started) this.started = true;
    this.ensurePlaying();
    this.applyVolumes(0);
  }

  setPlace(where) {
    if (where === this.where) return;
    this.where = where;
    this.applyVolumes();
  }

  /** Fade each channel toward the volume its place deserves. The bed is on everywhere; the town
   *  track and the outside track are each faded in only in their own place. */
  applyVolumes(ms = CROSS_MS) {
    const live = this.started && !this.muted;
    for (const el of this.bed) this.fade(el, live ? this.volume * el._gain : 0, ms);
    this.fade(this.town, live && this.where === "town" ? this.volume * this.town._gain : 0, ms);
    this.fade(this.out, live && this.where === "world" ? this.volume * this.out._gain : 0, ms);
  }

  setPaused(paused) {
    if (!this.started) return;
    if (paused) { for (const el of this.els()) el.pause(); }
    else { this.ensurePlaying(); this.applyVolumes(0); }
  }

  /** Explicit pause/resume for the death screen. */
  pause() { for (const el of this.els()) el.pause(); }
  resume() { this.ensurePlaying(); this.applyVolumes(0); }

  toggle() {
    this.muted = !this.muted;
    if (this.muted) { for (const el of this.els()) el.pause(); }
    else { this.started = true; this.ensurePlaying(); this.applyVolumes(0); }
    return !this.muted;
  }

  fade(el, target, ms) {
    const from = el.volume;
    const t0 = performance.now();
    clearInterval(el._fade);
    if (ms <= 0) { el.volume = target; return; }
    el._fade = setInterval(() => {
      const t = Math.min(1, (performance.now() - t0) / ms);
      el.volume = Math.max(0, Math.min(1, from + (target - from) * t));
      if (t >= 1) clearInterval(el._fade);
    }, 33);
  }
}
