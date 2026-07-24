// Layered soundtrack. Every track is its own looping <audio> element that streams the whole
// time; crossing the city gate only changes VOLUMES, so nothing ever restarts from the top.
//
//   EVERYWHERE      — war 1, war 2 and radio all play AT THE SAME TIME, each on its own loop.
//                     No playlist, no hand-off: the three are simply layered together and never
//                     stop, so radio is always in the mix instead of waiting its turn.
//   INSIDE the city — the chill town track fades in ON TOP of those three; stepping outside just
//                     drops that one layer and leaves the war/radio bed rolling.
//
// (To change the mix, edit WORLD_TRACKS / TOWN_TRACK below.)

// Each track carries its OWN gain (0..1) so the layers can be balanced against each other —
// radio was drowning the war tracks, so it's mixed down here.
const WORLD_TRACKS = [
  { src: "/audio/warsound.mp3", gain: 1.0 },   // war 1
  { src: "/audio/warsound2.mp3", gain: 1.0 },  // war 2
  { src: "/audio/radio.mp3", gain: 0.4 },      // radio — quieter, it was too loud
];
const TOWN_TRACK = { src: "/audio/chillax.mp3", gain: 1.0 };   // the city track we had

const VOLUME = 0.24;       // master, kept low so the layers don't clip
const CROSS_MS = 1100;     // gate-crossing fade

export class Music {
  constructor(volume = VOLUME) {
    this.volume = volume;
    this.muted = false;
    this.started = false;
    this.where = "world";

    // Three action tracks, each an independent forever-loop. Same simple shape as the town
    // track that already works — no src swapping, no 'ended' handoff to go wrong.
    this.world = WORLD_TRACKS.map((t) => this.makeLoop(t));
    this.town = this.makeLoop(TOWN_TRACK);
  }

  makeLoop({ src, gain }) {
    const el = new Audio(src);
    el.loop = true;
    el.volume = 0;
    el._gain = gain;   // per-track balance, multiplied into the master below
    return el;
  }

  els() { return [...this.world, this.town]; }

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

  /** Fade each channel toward the volume its place deserves. The three war/radio tracks are on
   *  everywhere; the town track is layered on top only when you're inside the city. */
  applyVolumes(ms = CROSS_MS) {
    const live = this.started && !this.muted;
    for (const el of this.world) this.fade(el, live ? this.volume * el._gain : 0, ms);
    this.fade(this.town, live && this.where === "town" ? this.volume * this.town._gain : 0, ms);
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
