// Place-based soundtrack: two channels that both stream the whole time, and only their VOLUMES
// crossfade as you cross a gate — so neither restarts from the top when you step in or out.
//
//   OUTSIDE the city — a PLAYLIST of the action tracks (war 1, war 2, radio) played one after
//                      another and looped, so the frontier has a rotating score.
//   INSIDE the city  — the one chill town track, looped.
//
// (To change which songs go where, edit WORLD_PLAYLIST / TOWN_TRACK below.)

const WORLD_PLAYLIST = [
  "/audio/warsound.mp3",   // war 1
  "/audio/warsound2.mp3",  // war 2
  "/audio/radio.mp3",      // radio
];
const TOWN_TRACK = "/audio/chillax.mp3";   // the city track we had

const VOLUME = 0.3;        // background, under the sound effects
const CROSS_MS = 1100;     // gate crossings

export class Music {
  constructor(volume = VOLUME) {
    this.volume = volume;
    this.muted = false;
    this.started = false;
    this.where = "world";
    this.idx = 0;

    // The frontier channel is a playlist: advance on end, wrap forever.
    this.world = new Audio(WORLD_PLAYLIST[0]);
    this.world.volume = 0;
    this.world.addEventListener("ended", () => this.advanceWorld());
    this.world.addEventListener("error", () => { if (this.started) this.advanceWorld(); });

    // The city channel is a single looping track.
    this.town = new Audio(TOWN_TRACK);
    this.town.loop = true;
    this.town.volume = 0;
  }

  advanceWorld() {
    this.idx = (this.idx + 1) % WORLD_PLAYLIST.length;
    this.world.src = WORLD_PLAYLIST[this.idx];
    this.world.load();
    if (this.started && !this.muted) this.world.play().catch(() => {});
  }

  /** Make sure both channels are STREAMING when they should be. Volume decides what's heard;
   *  playing both keeps their positions warm and lets the world playlist keep advancing. */
  ensurePlaying() {
    if (!this.started || this.muted) return;
    for (const el of [this.world, this.town]) {
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

  /** Fade each channel toward the volume its place deserves right now. */
  applyVolumes(ms = CROSS_MS) {
    const live = this.started && !this.muted;
    this.fade(this.world, live && this.where === "world" ? this.volume : 0, ms);
    this.fade(this.town, live && this.where === "town" ? this.volume : 0, ms);
  }

  setPaused(paused) {
    if (!this.started) return;
    if (paused) { this.world.pause(); this.town.pause(); }
    else { this.ensurePlaying(); this.applyVolumes(0); }
  }

  /** Explicit pause/resume for the death screen. */
  pause() { this.world.pause(); this.town.pause(); }
  resume() { this.ensurePlaying(); this.applyVolumes(0); }

  toggle() {
    this.muted = !this.muted;
    if (this.muted) { this.world.pause(); this.town.pause(); }
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
