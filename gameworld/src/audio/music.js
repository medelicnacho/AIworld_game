// Layered, place-aware soundtrack. Every channel is its own <audio> that streams the whole
// time; crossing the city gate only changes VOLUMES, so nothing restarts from the top.
//
//   BED (everywhere) — war 1, war 2 and radio all play AT THE SAME TIME, each on its own loop.
//                      Always audible, city and frontier alike. Radio is mixed down; it was
//                      drowning the war tracks.
//   OUTSIDE, on top  — two melodic songs (killer space tuna, donkey beats) played one after
//                      another on loop — a proper frontier soundtrack over the war bed.
//   IN CITY, on top  — chillax, the town track we had.
//
// Each track carries its own gain (0..1) so the layers balance; the master VOLUME sits under it.
// (To change the mix, edit the three lists below.)

const BED_TRACKS = [
  { src: "/audio/warsound.mp3", gain: 1.0 },   // war 1
  { src: "/audio/warsound2.mp3", gain: 1.0 },  // war 2
  { src: "/audio/radio.mp3", gain: 0.4 },      // radio — quieter, it was too loud
];
const OUTSIDE_PLAYLIST = [
  { src: "/audio/killerspacetuna.mp3", gain: 0.85 },
  { src: "/audio/donkeybeats.mp3", gain: 0.85 },
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

    // The war/radio bed: three independent forever-loops, always on.
    this.bed = BED_TRACKS.map((t) => this.makeLoop(t));

    // The town track: a single loop, faded in only inside the city.
    this.town = this.makeLoop(TOWN_TRACK);

    // The outside soundtrack: ONE element cycling the two melodic songs one after another. It
    // streams and advances the whole time; its volume is only up when you're on the frontier.
    this.outIdx = 0;
    this.out = new Audio(OUTSIDE_PLAYLIST[0].src);
    this.out._gain = OUTSIDE_PLAYLIST[0].gain;
    this.out.volume = 0;
    this.out.addEventListener("ended", () => this.advanceOut());
  }

  makeLoop({ src, gain }) {
    const el = new Audio(src);
    el.loop = true;
    el.volume = 0;
    el._gain = gain;   // per-track balance, multiplied into the master below
    return el;
  }

  advanceOut() {
    this.outIdx = (this.outIdx + 1) % OUTSIDE_PLAYLIST.length;
    const t = OUTSIDE_PLAYLIST[this.outIdx];
    this.out.src = t.src;
    this.out._gain = t.gain;
    this.out.load();
    if (this.started && !this.muted) {
      this.out.play().catch(() => {});
      this.applyVolumes(0);
    }
  }

  els() { return [...this.bed, this.town, this.out]; }

  /** Make sure every channel is STREAMING. Volume decides what's heard; playing them all keeps
   *  the layers in the mix and the outside playlist advancing. */
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
   *  track and the outside playlist are each faded in only in their own place. */
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
