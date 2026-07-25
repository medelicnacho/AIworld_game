// Procedural sound effects — synthesized in WebAudio, no asset files anywhere.
//
// Explosions and monster roars are the easiest sounds to fake convincingly: they're noise
// and envelopes, not melody. Synthesizing them means no downloads, no licences, no
// megabytes in git forever, and every parameter is a number you can tune from here.
//
// Everything is POSITIONAL: gain falls off with distance and pans by the angle relative to
// where you're facing. With six meteors in the air, hearing which side they're on is not a
// luxury — it's the difference between reading the volley and being surprised by it.

import { player } from "../state.js";
import { mulberry32 } from "../rng.js";

const MAX_DIST = 110;

export class Sfx {
  constructor() {
    this.ctx = null;
    this.master = null;
    this.noiseBuf = null;
    this.muted = false;
    this.volume = 1;               // the global fader (set from the pause screen)
    // Seeded (D14), like every other random number in the game — used to rough up the
    // crackle so repeated pops never land in an identical pattern.
    this.rng = mulberry32(0xC4AC1E);
  }

  /** Must be called from a user gesture — browsers refuse audio before one. */
  unlock() {
    if (this.ctx) { if (this.ctx.state === "suspended") this.ctx.resume(); return; }
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    this.ctx = new AC();
    this.master = this.ctx.createGain();
    this.master.gain.value = 0.9 * this.volume;
    // A limiter on the way out. Twenty overlapping explosions sum well past 1.0 and clip
    // into a scream; this squashes the peaks instead of letting the hardware do it badly.
    const limiter = this.ctx.createDynamicsCompressor();
    limiter.threshold.value = -10;
    limiter.knee.value = 6;
    limiter.ratio.value = 14;
    limiter.attack.value = 0.002;
    limiter.release.value = 0.16;
    this.master.connect(limiter);
    limiter.connect(this.ctx.destination);
    this.voices = 0;

    // One second of white noise, reused by every noise-based sound. Seeded like everything
    // else (D14) — an exception you have to remember is worse than a one-line fix.
    const n = this.ctx.sampleRate;
    this.noiseBuf = this.ctx.createBuffer(1, n, n);
    const d = this.noiseBuf.getChannelData(0);
    const rnd = mulberry32(0x1103E);
    for (let i = 0; i < n; i++) d[i] = rnd() * 2 - 1;
  }

  get on() { return this.ctx && !this.muted; }

  /** The one global fader for every effect and every voice — they all route through the
   *  master. 0.9 is the mix's headroom; the player's dial scales it. */
  setVolume(v) {
    this.volume = Math.max(0, Math.min(1, v));
    if (this.master) this.master.gain.value = 0.9 * this.volume;
  }

  /**
   * A budget for loud, overlapping sounds. A wiped elite pack can ask for a dozen
   * explosions in one frame; past a point they stop being distinguishable and only add
   * clipping, so the extras are simply not played.
   */
  budget(cost = 1, ms = 220) {
    if (this.voices >= 10) return false;
    this.voices += cost;
    setTimeout(() => { this.voices = Math.max(0, this.voices - cost); }, ms);
    return true;
  }

  /** Suspending the context stops everything mid-flight — including a half-spoken line. */
  setPaused(paused) {
    if (!this.ctx) return;
    if (paused && this.ctx.state === "running") this.ctx.suspend();
    else if (!paused && this.ctx.state === "suspended") this.ctx.resume();
  }

  get t() { return this.ctx.currentTime; }

  noise() {
    const s = this.ctx.createBufferSource();
    s.buffer = this.noiseBuf;
    s.loop = true;
    return s;
  }

  /** Distance gain + stereo pan for a world position, chained into the master bus. */
  place(x, z, reach = MAX_DIST) {
    const g = this.ctx.createGain();
    const pan = this.ctx.createStereoPanner();
    if (x === undefined) {                    // non-positional (your own gun)
      g.connect(this.master);
      return { input: g, gain: 1 };
    }
    const dx = x - player.x, dz = z - player.z;
    const dist = Math.hypot(dx, dz);
    const falloff = Math.max(0, 1 - dist / reach) ** 2;
    // Right vector for the current yaw — the same basis camera.js uses.
    const rx = Math.cos(player.yaw), rz = -Math.sin(player.yaw);
    const inv = 1 / (dist || 1);
    pan.pan.value = Math.max(-1, Math.min(1, (dx * inv) * rx + (dz * inv) * rz));
    g.connect(pan);
    pan.connect(this.master);
    return { input: g, gain: falloff };
  }

  /**
   * A MOVING sound source. place() takes a snapshot of where something is, which is right
   * for a bang and wrong for anything that travels: a charger crosses most of the ground
   * between you while it is charging, so a fixed pan would keep insisting it is where it
   * started — at exactly the moment you are sidestepping, looking elsewhere, and trusting
   * your ears. Returns a handle whose distance and pan can be re-aimed every frame.
   */
  tracker(reach = MAX_DIST) {
    const dist = this.ctx.createGain();
    const pan = this.ctx.createStereoPanner();
    dist.connect(pan);
    pan.connect(this.master);
    const set = (x, z) => {
      const dx = x - player.x, dz = z - player.z;
      const d = Math.hypot(dx, dz);
      const rx = Math.cos(player.yaw), rz = -Math.sin(player.yaw);
      const inv = 1 / (d || 1);
      pan.pan.value = Math.max(-1, Math.min(1, dx * inv * rx + dz * inv * rz));
      const g = Math.max(0, 1 - d / reach) ** 2;
      dist.gain.value = g;
      return g;
    };
    return { input: dist, set };
  }

  /**
   * CRACKLE — a run of short, sharp noise pops rather than a continuous hiss.
   *
   * The difference matters more than it sounds. Sustained filtered noise is a *whoosh*, and a
   * whoosh under a rising tone is what makes a wind-up read as a wasp: irritating, thin, and
   * tiring after the tenth time you hear it. Crackle is transient — fire catching, gravel
   * under weight, ice going — and the ear reads transients as MATERIAL rather than as noise,
   * which is most of what makes a sound feel physical instead of synthesised.
   *
   * When `accelerate` is on, the gaps shrink toward the end. That is not decoration: it puts
   * the timing INSIDE the texture, so you can hear how long you have from the rate alone and
   * the cue never needs a rising pitch to do that job.
   *
   * One noise source with an automated gain, not one source per pop — a couple of dozen
   * buffer sources per charge would be real cost for a sound that happens constantly.
   */
  crackle(t, dur, dest, { n = 20, peak = 0.5, freq = 700, q = 0.7, decay = 0.045, accelerate = true } = {}) {
    const src = this.noise();
    const bp = this.ctx.createBiquadFilter();
    bp.type = "bandpass";
    bp.frequency.value = freq;
    bp.Q.value = q;
    const g = this.ctx.createGain();
    g.gain.setValueAtTime(0.0001, t);
    for (let i = 0; i < n; i++) {
      // Clustered toward the END when accelerating, evenly spread when not.
      const f = i / n;
      const at = t + dur * (accelerate ? 1 - (1 - f) ** 1.8 : f);
      // Uneven heights, or twenty identical pops read as a machine rather than as a thing.
      const amp = peak * (0.45 + this.rng() * 0.55);
      g.gain.setValueAtTime(0.0001, at);
      g.gain.linearRampToValueAtTime(amp, at + 0.003);
      g.gain.exponentialRampToValueAtTime(0.0001, at + decay);
    }
    src.connect(bp); bp.connect(g); g.connect(dest);
    src.start(t); src.stop(t + dur + decay + 0.05);
    return src;
  }

  /** Soft-clip curve — what makes a roar sound like a throat instead of a sine. */
  distortion(amount = 40) {
    const ws = this.ctx.createWaveShaper();
    const n = 1024, curve = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      const x = (i * 2) / n - 1;
      curve[i] = ((1 + amount) * x) / (1 + amount * Math.abs(x));
    }
    ws.curve = curve;
    return ws;
  }

  // --- the sounds ---------------------------------------------------------------

  /**
   * A gun. Yours is non-positional and quiet — it fires 7.5×/sec and must not fatigue.
   * Guards pass their position and a low `vol`: four of them firing beside a town has to
   * sit UNDER the mix, or the safest place in the world becomes the loudest.
   */
  gunshot(x, z, vol = 1) {
    if (!this.on) return;
    const t = this.t, dur = 0.12;
    const { input, gain } = x === undefined ? this.place() : this.place(x, z, 90);
    if (vol !== 1 && gain?.gain) gain.gain.value *= vol;   // non-positional returns 1, not a node

    const src = this.noise();
    const lp = this.ctx.createBiquadFilter();
    lp.type = "lowpass";
    lp.frequency.setValueAtTime(7000, t);
    lp.frequency.exponentialRampToValueAtTime(700, t + dur);
    const hp = this.ctx.createBiquadFilter();
    hp.type = "highpass";
    hp.frequency.value = 350;

    const g = this.ctx.createGain();
    g.gain.setValueAtTime(0.22, t);
    g.gain.exponentialRampToValueAtTime(0.0008, t + dur);

    src.connect(hp); hp.connect(lp); lp.connect(g); g.connect(input);
    src.start(t); src.stop(t + dur + 0.02);

    // A little low body so it thumps rather than hisses.
    const body = this.ctx.createOscillator();
    body.type = "triangle";
    body.frequency.setValueAtTime(150, t);
    body.frequency.exponentialRampToValueAtTime(60, t + 0.09);
    const bg = this.ctx.createGain();
    bg.gain.setValueAtTime(0.16, t);
    bg.gain.exponentialRampToValueAtTime(0.001, t + 0.1);
    body.connect(bg); bg.connect(input);
    body.start(t); body.stop(t + 0.12);
  }

  /** The boss. `big` is the spawn/phase-change roar; the quiet one is ambient dread. */
  roar(x, z, big = false) {
    if (!this.on || !this.budget(2, 1200)) return;
    const t = this.t;
    const dur = big ? 1.9 : 1.25;
    const { input, gain } = this.place(x, z, 200);
    if (gain <= 0.001) return;

    const dist = this.distortion(big ? 60 : 35);
    const lp = this.ctx.createBiquadFilter();
    lp.type = "lowpass";
    lp.frequency.setValueAtTime(900, t);
    lp.frequency.exponentialRampToValueAtTime(320, t + dur);

    const out = this.ctx.createGain();
    out.gain.setValueAtTime(0.0001, t);
    out.gain.exponentialRampToValueAtTime(gain * (big ? 1.0 : 0.5), t + 0.12);
    out.gain.exponentialRampToValueAtTime(0.0001, t + dur);

    dist.connect(lp); lp.connect(out); out.connect(input);

    // Detuned stack sliding down — the pitch fall is what reads as "huge".
    const base = big ? 62 : 78;
    for (const mult of [1, 1.5, 2.02]) {
      const o = this.ctx.createOscillator();
      o.type = "sawtooth";
      o.frequency.setValueAtTime(base * mult, t);
      o.frequency.exponentialRampToValueAtTime(base * mult * 0.55, t + dur);
      const og = this.ctx.createGain();
      og.gain.value = 0.35 / mult;
      o.connect(og); og.connect(dist);
      o.start(t); o.stop(t + dur + 0.05);

      // Growl: a slow wobble on the detune so it never sounds like a clean synth tone.
      const lfo = this.ctx.createOscillator();
      lfo.frequency.value = 18 + mult * 7;
      const lg = this.ctx.createGain();
      lg.gain.value = 22;
      lfo.connect(lg); lg.connect(o.detune);
      lfo.start(t); lfo.stop(t + dur + 0.05);
    }

    // Breath.
    const air = this.noise();
    const bp = this.ctx.createBiquadFilter();
    bp.type = "bandpass";
    bp.frequency.setValueAtTime(1100, t);
    bp.frequency.exponentialRampToValueAtTime(380, t + dur);
    bp.Q.value = 1.2;
    const ag = this.ctx.createGain();
    ag.gain.setValueAtTime(gain * 0.22, t);
    ag.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    air.connect(bp); bp.connect(ag); ag.connect(input);
    air.start(t); air.stop(t + dur + 0.05);
  }

  /**
   * The volley wind-up: a rising, accelerating alarm. This is a GAMEPLAY signal, not
   * decoration — it tells you rocks are coming before the ground markers appear, so the
   * fight is readable even when you're looking the other way.
   */
  charge(x, z, dur = 1.2) {
    if (!this.on) return;
    const t = this.t;
    const { input, gain } = this.place(x, z, 170);
    if (gain <= 0.001) return;

    const out = this.ctx.createGain();
    out.gain.setValueAtTime(0.0001, t);
    out.gain.exponentialRampToValueAtTime(gain * 0.7, t + dur * 0.85);
    out.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    out.connect(input);

    // Pulse rate accelerates toward the strike — the "it's about to happen" cue.
    const trem = this.ctx.createGain();
    trem.gain.value = 1;
    const lfo = this.ctx.createOscillator();
    lfo.type = "square";
    lfo.frequency.setValueAtTime(6, t);
    lfo.frequency.exponentialRampToValueAtTime(22, t + dur);
    const lg = this.ctx.createGain();
    lg.gain.value = 0.45;
    lfo.connect(lg); lg.connect(trem.gain);
    lfo.start(t); lfo.stop(t + dur);
    trem.connect(out);

    for (const [type, f0, f1, g] of [["sawtooth", 90, 520, 0.3], ["square", 180, 1040, 0.12]]) {
      const o = this.ctx.createOscillator();
      o.type = type;
      o.frequency.setValueAtTime(f0, t);
      o.frequency.exponentialRampToValueAtTime(f1, t + dur);
      const og = this.ctx.createGain();
      og.gain.value = g;
      o.connect(og); og.connect(trem);
      o.start(t); o.stop(t + dur);
    }

    const air = this.noise();
    const bp = this.ctx.createBiquadFilter();
    bp.type = "bandpass";
    bp.frequency.setValueAtTime(600, t);
    bp.frequency.exponentialRampToValueAtTime(3200, t + dur);
    bp.Q.value = 3;
    const ag = this.ctx.createGain();
    ag.gain.setValueAtTime(0.0001, t);
    ag.gain.exponentialRampToValueAtTime(0.25, t + dur * 0.9);
    air.connect(bp); bp.connect(ag); ag.connect(trem);
    air.start(t); air.stop(t + dur);
  }

  /**
   * A charger COILING — the wind-up, while it is rooted and glowing.
   *
   * This is the fairness cue for the one attack in the game that can kill you from off
   * screen. It has to answer two questions at once: something is about to commit, and it is
   * over THERE. Everything else follows from that.
   *
   * Deliberately NOT built from the same parts as the boss's volley cue. That one is a
   * machine alarm — high, thin, accelerating — and it means "get off this ground". This one
   * means "get out of this line", which is a completely different answer, so it is a throat
   * and a pair of feet instead: low, gritty, no tremolo. Two warnings that demand different
   * reactions must never share a timbre, or players learn the wrong response to one of them.
   *
   * It SWELLS to peak at the instant of release, so you can hear how long you have rather
   * than merely that danger exists. A warning with no timing in it is only half a warning.
   */
  chargeWind(x, z, dur = 0.75) {
    if (!this.on || !this.budget(1, 400)) return;
    const t = this.t;
    const { input, gain } = this.place(x, z, 95);
    if (gain <= 0.001) return;                 // too far to matter; don't clutter the mix

    const out = this.ctx.createGain();
    out.gain.setValueAtTime(0.0001, t);
    out.gain.exponentialRampToValueAtTime(gain * 0.85, t + dur * 0.95);
    out.gain.exponentialRampToValueAtTime(0.0001, t + dur + 0.06);
    // THE LOAD: everything rolls off the top as it coils, so the sound gets thicker and
    // closer rather than merely louder. A wind-up that only gains volume feels like someone
    // turning a knob; one that darkens feels like something gathering itself.
    const lp = this.ctx.createBiquadFilter();
    lp.type = "lowpass";
    lp.frequency.setValueAtTime(2600, t);
    lp.frequency.exponentialRampToValueAtTime(900, t + dur);
    out.connect(lp);
    lp.connect(input);

    // The WEIGHT: sub sines, barely climbing. Sines, not sawtooths, and no real distortion —
    // a rising distorted saw is a wasp, and a wasp you hear a hundred times an hour is the
    // fastest way to make someone turn the sound off. Depth comes from being LOW, not from
    // being harsh. The climb is small on purpose: it should feel like a spring loading, not
    // like an engine revving.
    for (const [f0, f1, g, type] of [[36, 52, 0.5, "sine"], [54, 78, 0.22, "triangle"]]) {
      const o = this.ctx.createOscillator();
      o.type = type;
      o.frequency.setValueAtTime(f0, t);
      o.frequency.exponentialRampToValueAtTime(f1, t + dur);
      const og = this.ctx.createGain();
      og.gain.value = g;
      // A whisper of saturation for warmth and a little body — nowhere near enough to rasp.
      const warm = this.distortion(6);
      o.connect(warm); warm.connect(og); og.connect(out);
      o.start(t); o.stop(t + dur + 0.12);
    }

    // The CRACKLE, accelerating into the release. This carries the timing now, so the pitch
    // does not have to — you hear the rate tighten and you know it is about to go. Low and
    // dry rather than bright: hooves splitting the ground, not static.
    this.crackle(t, dur, out, { n: 22, peak: 0.55, freq: 430, q: 0.6, decay: 0.05 });
    // A second, sparser layer an octave up, so it has some grain to it and does not read as
    // one repeated click.
    this.crackle(t, dur, out, { n: 11, peak: 0.24, freq: 1150, q: 1.1, decay: 0.03 });
  }

  /**
   * A charger COMMITTED — the sustained rumble while it actually runs at you.
   *
   * The warning already happened; this sound has a different job. You will be looking away
   * and moving, so its only purpose is to keep answering WHERE, continuously, until the
   * threat is over. Hence the tracker: it follows the body rather than marking the spot the
   * body left.
   *
   * Returns a handle that MUST be stopped when the charge ends. A rumble that outlives the
   * thing making it is worse than no sound at all — it is the game lying about where danger
   * is, and a player who stops trusting the audio has lost the cue entirely.
   */
  chargeRush(x, z, maxDur = 3) {
    if (!this.on) return null;
    // A hard cap on how many can sound at once. In a deep pack several may commit together,
    // and past a few overlapping rumbles you cannot tell them apart anyway — at which point
    // they stop being information and become mud.
    this._rushVoices = this._rushVoices || 0;
    if (this._rushVoices >= 4) return null;
    this._rushVoices++;

    const t = this.t;
    const trk = this.tracker(95);
    trk.set(x, z);

    const out = this.ctx.createGain();
    out.gain.setValueAtTime(0.0001, t);
    out.gain.exponentialRampToValueAtTime(0.5, t + 0.05);   // no fade-in: it is already going
    out.connect(trk.input);

    const parts = [];
    // MASS. Two sub tones a fifth apart, detuned just enough to beat slowly against each
    // other — that slow throb is what a big thing moving sounds like, and it is doing the
    // work the old distorted saws were trying to do by being loud.
    for (const [f, g, type] of [[31, 0.55, "sine"], [46.5, 0.26, "triangle"], [47.4, 0.16, "triangle"]]) {
      const o = this.ctx.createOscillator();
      o.type = type;
      o.frequency.value = f;
      const og = this.ctx.createGain();
      og.gain.value = g;
      const warm = this.distortion(9);
      o.connect(warm); warm.connect(og); og.connect(out);
      o.start(t);
      parts.push(o);
    }
    // GRAVEL. A steady run of low pops for the whole run — ground breaking up under
    // something heavy. Not accelerating: the charge is committed, so nothing about it is
    // counting down any more, and a cue that keeps building would be lying about that.
    parts.push(this.crackle(t, maxDur, out,
      { n: Math.round(maxDur * 34), peak: 0.34, freq: 330, q: 0.5, decay: 0.035, accelerate: false }));
    // A little air under it so it travels rather than idling in place — well below the crackle
    // so it never becomes hiss.
    const air = this.noise();
    const lp = this.ctx.createBiquadFilter();
    lp.type = "lowpass";
    lp.frequency.value = 420;
    const ag = this.ctx.createGain();
    ag.gain.value = 0.34;
    air.connect(lp); lp.connect(ag); ag.connect(out);
    air.start(t);
    parts.push(air);

    let done = false;
    const stop = () => {
      if (done) return;                       // idempotent: the caller may stop it twice
      done = true;
      this._rushVoices = Math.max(0, this._rushVoices - 1);
      const n = this.t;
      out.gain.cancelScheduledValues(n);
      out.gain.setValueAtTime(Math.max(0.0001, out.gain.value), n);
      out.gain.exponentialRampToValueAtTime(0.0001, n + 0.09);
      for (const o of parts) { try { o.stop(n + 0.12); } catch { /* already stopped */ } }
    };
    // A backstop, in case the body carrying this is removed by a path that forgets to stop
    // it. Better a rumble that ends early than one that never ends.
    setTimeout(stop, maxDur * 1000);

    return { move: (nx, nz) => trk.set(nx, nz), stop };
  }

  /** Meteor impacts and grenades. `size` scales the length and the low thump. */
  explosion(x, z, size = 1) {
    if (!this.on || !this.budget()) return;
    const t = this.t;
    const dur = 0.75 * size;
    const { input, gain } = this.place(x, z, 150);
    if (gain <= 0.001) return;

    const src = this.noise();
    const lp = this.ctx.createBiquadFilter();
    lp.type = "lowpass";
    lp.frequency.setValueAtTime(2600, t);
    lp.frequency.exponentialRampToValueAtTime(70, t + dur);
    const dist = this.distortion(25);
    const g = this.ctx.createGain();
    g.gain.setValueAtTime(gain * 0.85, t);
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    src.connect(lp); lp.connect(dist); dist.connect(g); g.connect(input);
    src.start(t); src.stop(t + dur + 0.05);

    // The thump you feel rather than hear.
    const sub = this.ctx.createOscillator();
    sub.type = "sine";
    sub.frequency.setValueAtTime(85 / size, t);
    sub.frequency.exponentialRampToValueAtTime(28, t + 0.45 * size);
    const sg = this.ctx.createGain();
    sg.gain.setValueAtTime(gain * 0.9, t);
    sg.gain.exponentialRampToValueAtTime(0.0001, t + 0.5 * size);
    sub.connect(sg); sg.connect(input);
    sub.start(t); sub.stop(t + 0.55 * size);
  }

  /**
   * The heal channel: a rising shimmer that resolves only if you hold still. Returns a
   * handle so an interrupt can cut it mid-note — the sound stopping early IS the feedback
   * that you broke it, which is faster to read than any HUD text.
   */
  healCast(dur = 1.5) {
    if (!this.on) return null;
    const t = this.t;
    const { input } = this.place();
    const out = this.ctx.createGain();
    out.gain.setValueAtTime(0.0001, t);
    out.gain.exponentialRampToValueAtTime(0.13, t + dur * 0.8);
    out.connect(input);

    const oscs = [];
    for (const [mult, g] of [[1, 0.5], [1.5, 0.28], [2, 0.16]]) {
      const o = this.ctx.createOscillator();
      o.type = "triangle";
      o.frequency.setValueAtTime(220 * mult, t);
      o.frequency.exponentialRampToValueAtTime(440 * mult, t + dur);
      const og = this.ctx.createGain();
      og.gain.value = g;
      o.connect(og); og.connect(out);
      o.start(t); o.stop(t + dur + 0.1);
      oscs.push(o);
    }

    return {
      stop: () => {
        const n = this.t;
        out.gain.cancelScheduledValues(n);
        out.gain.setValueAtTime(Math.max(0.0001, out.gain.value), n);
        out.gain.exponentialRampToValueAtTime(0.0001, n + 0.08);
        for (const o of oscs) { try { o.stop(n + 0.1); } catch { /* already stopped */ } }
      },
    };
  }

  /** Heal landed — a bright, clean resolution. */
  healDone() {
    if (!this.on) return;
    const t = this.t;
    const { input } = this.place();
    for (const [f, delay, g] of [[660, 0, 0.18], [880, 0.06, 0.14], [1320, 0.12, 0.08]]) {
      const o = this.ctx.createOscillator();
      o.type = "sine";
      o.frequency.value = f;
      const og = this.ctx.createGain();
      og.gain.setValueAtTime(0.0001, t + delay);
      og.gain.exponentialRampToValueAtTime(g, t + delay + 0.02);
      og.gain.exponentialRampToValueAtTime(0.0001, t + delay + 0.55);
      o.connect(og); og.connect(input);
      o.start(t + delay); o.stop(t + delay + 0.6);
    }
  }

  /** Channel broken — a short downward blip, so failure is audible too. */
  healBreak() {
    if (!this.on) return;
    const t = this.t;
    const { input } = this.place();
    const o = this.ctx.createOscillator();
    o.type = "triangle";
    o.frequency.setValueAtTime(400, t);
    o.frequency.exponentialRampToValueAtTime(120, t + 0.18);
    const g = this.ctx.createGain();
    g.gain.setValueAtTime(0.12, t);
    g.gain.exponentialRampToValueAtTime(0.0001, t + 0.2);
    o.connect(g); g.connect(input);
    o.start(t); o.stop(t + 0.22);
  }

  /**
   * Play a wav that arrived from the bridge (speech), positioned in the world.
   *
   * decodeAudioData is asynchronous and decodes off the main thread, which is why speech
   * can arrive mid-fight without costing frame time — the thing Stage 1's gate checks.
   * @returns {Promise<number>} duration in seconds, or 0 if it couldn't be played.
   */
  /** `rate` shifts pitch and speed together after synthesis — the cheap monster-maker:
   *  0.85 turns a narrator into a growl, 1.12 into something quick and sharp. */
  async playClip(arrayBuffer, x, z, volume = 1, rate = 1) {
    if (!this.on || !arrayBuffer) return 0;
    let buf;
    try {
      buf = await this.ctx.decodeAudioData(arrayBuffer.slice(0));
    } catch {
      return 0;
    }
    const src = this.ctx.createBufferSource();
    src.buffer = buf;
    src.playbackRate.value = rate;
    const { input, gain } = this.place(x, z, 200);
    const g = this.ctx.createGain();
    g.gain.value = (gain ?? 1) * volume;
    src.connect(g);
    g.connect(input);
    src.start();
    return buf.duration;
  }

  /** A fireball leaving a caster's hands — short, bright, positional. */
  cast(x, z) {
    if (!this.on || !this.budget(1, 160)) return;
    const t = this.t, dur = 0.34;
    const { input, gain } = this.place(x, z, 120);
    if (gain <= 0.001) return;

    const o = this.ctx.createOscillator();
    o.type = "sawtooth";
    o.frequency.setValueAtTime(180, t);
    o.frequency.exponentialRampToValueAtTime(760, t + dur);
    const og = this.ctx.createGain();
    og.gain.setValueAtTime(gain * 0.28, t);
    og.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.connect(og); og.connect(input);
    o.start(t); o.stop(t + dur + 0.02);

    const air = this.noise();
    const bp = this.ctx.createBiquadFilter();
    bp.type = "bandpass";
    bp.frequency.setValueAtTime(900, t);
    bp.frequency.exponentialRampToValueAtTime(2600, t + dur);
    bp.Q.value = 2.5;
    const ag = this.ctx.createGain();
    ag.gain.setValueAtTime(gain * 0.22, t);
    ag.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    air.connect(bp); bp.connect(ag); ag.connect(input);
    air.start(t); air.stop(t + dur + 0.02);
  }

  /**
   * The beam, while it burns. A sustained scorching hum rather than a one-shot: the sound
   * IS the warning that it is still hunting you, so it has to last as long as the threat.
   * Returns a handle so it can be cut short if the boss dies mid-sweep.
   */
  beam(x, z, dur) {
    if (!this.on) return null;
    const t = this.t;
    const { input, gain } = this.place(x, z, 170);
    if (gain <= 0.001) return null;

    const out = this.ctx.createGain();
    out.gain.setValueAtTime(0.0001, t);
    out.gain.exponentialRampToValueAtTime(gain * 0.5, t + 0.25);
    out.gain.setValueAtTime(gain * 0.5, t + dur - 0.3);
    out.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    out.connect(input);

    const stop = [];
    // Two detuned saws grinding against each other, low and mean.
    for (const [f, g] of [[86, 0.3], [129, 0.16]]) {
      const o = this.ctx.createOscillator();
      o.type = "sawtooth";
      o.frequency.value = f;
      const og = this.ctx.createGain();
      og.gain.value = g;
      const dist = this.distortion(30);
      o.connect(dist); dist.connect(og); og.connect(out);
      o.start(t); o.stop(t + dur + 0.1);
      stop.push(o);
    }
    // Scorching air on top, so it reads as heat rather than as an engine.
    const air = this.noise();
    const bp = this.ctx.createBiquadFilter();
    bp.type = "bandpass";
    bp.frequency.value = 2200;
    bp.Q.value = 0.9;
    const ag = this.ctx.createGain();
    ag.gain.value = 0.22;
    air.connect(bp); bp.connect(ag); ag.connect(out);
    air.start(t); air.stop(t + dur + 0.1);
    stop.push(air);

    return {
      stop: () => {
        const n = this.t;
        out.gain.cancelScheduledValues(n);
        out.gain.setValueAtTime(Math.max(0.0001, out.gain.value), n);
        out.gain.exponentialRampToValueAtTime(0.0001, n + 0.12);
        for (const o of stop) { try { o.stop(n + 0.15); } catch { /* already done */ } }
      },
    };
  }

  /** Grenade throw. */
  /** Selling — a bright two-note coin chime, the little "cha-ching" of a sale. */
  sell() {
    if (!this.on || !this.budget(0.7, 160)) return;
    const t = this.t;
    const { input } = this.place();
    const notes = [880, 1320];
    for (let i = 0; i < notes.length; i++) {
      const ct = t + i * 0.05;
      const o = this.ctx.createOscillator();
      o.type = "triangle";
      o.frequency.value = notes[i];
      const g = this.ctx.createGain();
      g.gain.setValueAtTime(0.0001, ct);
      g.gain.exponentialRampToValueAtTime(0.17, ct + 0.01);
      g.gain.exponentialRampToValueAtTime(0.0001, ct + 0.18);
      o.connect(g); g.connect(input);
      o.start(ct); o.stop(ct + 0.2);
    }
  }

  /** Level up — a triumphant rising arpeggio with a shimmer on top. The "do-da-ba-da". */
  levelUp() {
    if (!this.on || !this.budget(1.2, 400)) return;
    const t = this.t;
    const { input } = this.place();
    const notes = [523, 659, 784, 1047, 1319];   // C E G C E — ascending, bright
    for (let i = 0; i < notes.length; i++) {
      const ct = t + i * 0.075;
      const o = this.ctx.createOscillator();
      o.type = "triangle";
      o.frequency.value = notes[i];
      const g = this.ctx.createGain();
      g.gain.setValueAtTime(0.0001, ct);
      g.gain.exponentialRampToValueAtTime(0.19, ct + 0.015);
      g.gain.exponentialRampToValueAtTime(0.0001, ct + 0.38);
      o.connect(g); g.connect(input);
      o.start(ct); o.stop(ct + 0.42);
    }
    // A high sine sparkle riding over the top note for the "shiny" feel.
    const shimmer = this.ctx.createOscillator();
    shimmer.type = "sine";
    shimmer.frequency.setValueAtTime(2093, t + 0.3);
    shimmer.frequency.exponentialRampToValueAtTime(3136, t + 0.55);
    const sg = this.ctx.createGain();
    sg.gain.setValueAtTime(0.0001, t + 0.3);
    sg.gain.exponentialRampToValueAtTime(0.1, t + 0.34);
    sg.gain.exponentialRampToValueAtTime(0.0001, t + 0.62);
    shimmer.connect(sg); sg.connect(input);
    shimmer.start(t + 0.3); shimmer.stop(t + 0.65);
  }

  /** Picking a drop off the ground — a light rising blip, quick and clean. */
  pickup() {
    if (!this.on || !this.budget(0.5, 120)) return;
    const t = this.t;
    const { input } = this.place();
    const o = this.ctx.createOscillator();
    o.type = "triangle";
    o.frequency.setValueAtTime(520, t);
    o.frequency.exponentialRampToValueAtTime(900, t + 0.09);
    const g = this.ctx.createGain();
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(0.2, t + 0.02);
    g.gain.exponentialRampToValueAtTime(0.0001, t + 0.16);
    o.connect(g); g.connect(input);
    o.start(t); o.stop(t + 0.18);
  }

  /**
   * Equipping a piece — a donning THUNK for every tier, then a chime that grows with rarity:
   * common is just the thunk, uncommon adds a two-note lift, rare a full rising arpeggio. So
   * a blue upgrade sounds like an event and a grey one like putting on socks.
   */
  equip(rarity = "common") {
    if (!this.on || !this.budget(1, 220)) return;
    const t = this.t;
    const { input } = this.place();
    // The thunk of the piece settling on — all tiers get it.
    const thunk = this.ctx.createOscillator();
    thunk.type = "sine";
    thunk.frequency.setValueAtTime(190, t);
    thunk.frequency.exponentialRampToValueAtTime(72, t + 0.12);
    const tg = this.ctx.createGain();
    tg.gain.setValueAtTime(0.5, t);
    tg.gain.exponentialRampToValueAtTime(0.0001, t + 0.16);
    thunk.connect(tg); tg.connect(input);
    thunk.start(t); thunk.stop(t + 0.18);
    // The reward chime, by rarity.
    const notes = rarity === "rare" ? [523, 659, 784, 1047]
      : rarity === "uncommon" ? [523, 784] : [];
    for (let i = 0; i < notes.length; i++) {
      const ct = t + 0.05 + i * 0.06;
      const o = this.ctx.createOscillator();
      o.type = "triangle";
      o.frequency.value = notes[i];
      const g = this.ctx.createGain();
      g.gain.setValueAtTime(0.0001, ct);
      g.gain.exponentialRampToValueAtTime(0.15, ct + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, ct + 0.3);
      o.connect(g); g.connect(input);
      o.start(ct); o.stop(ct + 0.33);
    }
  }

  /** Shotgun: a deep, wide BOOM — noise swept down through a lowpass with a fat sub thump. */
  shotgunBlast() {
    if (!this.on || !this.budget()) return;
    const t = this.t, dur = 0.3;
    const { input } = this.place();
    const src = this.noise();
    const lp = this.ctx.createBiquadFilter();
    lp.type = "lowpass";
    lp.frequency.setValueAtTime(3200, t);
    lp.frequency.exponentialRampToValueAtTime(120, t + dur);
    const dist = this.distortion(30);
    const g = this.ctx.createGain();
    g.gain.setValueAtTime(0.95, t);
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    src.connect(lp); lp.connect(dist); dist.connect(g); g.connect(input);
    src.start(t); src.stop(t + dur + 0.05);

    const sub = this.ctx.createOscillator();
    sub.type = "sine";
    sub.frequency.setValueAtTime(115, t);
    sub.frequency.exponentialRampToValueAtTime(42, t + 0.2);
    const sg = this.ctx.createGain();
    sg.gain.setValueAtTime(0.85, t);
    sg.gain.exponentialRampToValueAtTime(0.0001, t + 0.22);
    sub.connect(sg); sg.connect(input);
    sub.start(t); sub.stop(t + 0.25);
  }

  /** Sniper: a sharp CRACK over a rolling low boom — the loudest, most deliberate shot. */
  sniperCrack() {
    if (!this.on || !this.budget()) return;
    const t = this.t;
    const { input } = this.place();
    // The crack: a brief burst of high, distorted noise.
    const crackSrc = this.noise();
    const hp = this.ctx.createBiquadFilter();
    hp.type = "highpass"; hp.frequency.value = 1700;
    const dist = this.distortion(55);
    const cg = this.ctx.createGain();
    cg.gain.setValueAtTime(1.0, t);
    cg.gain.exponentialRampToValueAtTime(0.0001, t + 0.09);
    crackSrc.connect(hp); hp.connect(dist); dist.connect(cg); cg.connect(input);
    crackSrc.start(t); crackSrc.stop(t + 0.11);
    // The boom that rolls out behind it.
    const boomSrc = this.noise();
    const lp = this.ctx.createBiquadFilter();
    lp.type = "lowpass";
    lp.frequency.setValueAtTime(1400, t);
    lp.frequency.exponentialRampToValueAtTime(90, t + 0.5);
    const bg = this.ctx.createGain();
    bg.gain.setValueAtTime(0.7, t);
    bg.gain.exponentialRampToValueAtTime(0.0001, t + 0.5);
    boomSrc.connect(lp); lp.connect(bg); bg.connect(input);
    boomSrc.start(t); boomSrc.stop(t + 0.55);
    const sub = this.ctx.createOscillator();
    sub.type = "sine";
    sub.frequency.setValueAtTime(85, t);
    sub.frequency.exponentialRampToValueAtTime(35, t + 0.3);
    const sg = this.ctx.createGain();
    sg.gain.setValueAtTime(0.7, t);
    sg.gain.exponentialRampToValueAtTime(0.0001, t + 0.33);
    sub.connect(sg); sg.connect(input);
    sub.start(t); sub.stop(t + 0.36);
  }

  /** The pump/bolt rack — two crisp mechanical clicks. The other half of "bam ka-chunk". */
  rack() {
    if (!this.on || !this.budget(0.5, 200)) return;
    const t = this.t;
    const { input } = this.place();
    for (let i = 0; i < 2; i++) {
      const ct = t + i * 0.11;
      const src = this.noise();
      const bp = this.ctx.createBiquadFilter();
      bp.type = "bandpass";
      bp.frequency.value = 2100 + i * 700;
      bp.Q.value = 3.5;
      const g = this.ctx.createGain();
      g.gain.setValueAtTime(0.32, ct);
      g.gain.exponentialRampToValueAtTime(0.0001, ct + 0.05);
      src.connect(bp); bp.connect(g); g.connect(input);
      src.start(ct); src.stop(ct + 0.06);
    }
  }

  // --- the faction weapons -----------------------------------------------------------
  // All three are YOUR weapon, so like the gunshot they are non-positional and mixed low —
  // a sound you make hundreds of times an hour must inform without fatiguing.

  /**
   * The cleaver swing. Air first, and — only when something was actually in the arc — a
   * meaty thunk on top. The miss and the hit MUST sound different: melee has no tracer and
   * no impact mark, so the ear is the only place a whiff can be told from a connect.
   */
  cleave(hit = false) {
    if (!this.on || !this.budget(0.5, 120)) return;
    const t = this.t;
    // The air: noise swept downward through a bandpass — a heavy thing moving fast.
    const air = this.noise();
    const bp = this.ctx.createBiquadFilter();
    bp.type = "bandpass";
    bp.frequency.setValueAtTime(2400, t);
    bp.frequency.exponentialRampToValueAtTime(500, t + 0.16);
    bp.Q.value = 1.1;
    const ag = this.ctx.createGain();
    ag.gain.setValueAtTime(0.28, t);
    ag.gain.exponentialRampToValueAtTime(0.0001, t + 0.18);
    air.connect(bp); bp.connect(ag); ag.connect(this.master);
    air.start(t); air.stop(t + 0.2);

    if (!hit) return;
    // The connect: a low body-blow, pitched down fast through soft clip.
    const o = this.ctx.createOscillator();
    o.type = "triangle";
    o.frequency.setValueAtTime(180, t + 0.03);
    o.frequency.exponentialRampToValueAtTime(55, t + 0.14);
    const og = this.ctx.createGain();
    og.gain.setValueAtTime(0.5, t + 0.03);
    og.gain.exponentialRampToValueAtTime(0.0001, t + 0.16);
    const warm = this.distortion(18);
    o.connect(warm); warm.connect(og); og.connect(this.master);
    o.start(t + 0.03); o.stop(t + 0.18);
  }

  /** The lobber's report: a hollow THOOMP, the mortar-tube cousin of a gunshot. */
  lob() {
    if (!this.on || !this.budget(0.5, 150)) return;
    const t = this.t;
    const o = this.ctx.createOscillator();
    o.type = "sine";
    o.frequency.setValueAtTime(210, t);
    o.frequency.exponentialRampToValueAtTime(70, t + 0.12);
    const og = this.ctx.createGain();
    og.gain.setValueAtTime(0.5, t);
    og.gain.exponentialRampToValueAtTime(0.0001, t + 0.16);
    o.connect(og); og.connect(this.master);
    o.start(t); o.stop(t + 0.18);
    // A breath of air out of the barrel, so it reads as launched rather than as a beep.
    const puff = this.noise();
    const lp = this.ctx.createBiquadFilter();
    lp.type = "lowpass";
    lp.frequency.value = 900;
    const pg = this.ctx.createGain();
    pg.gain.setValueAtTime(0.18, t);
    pg.gain.exponentialRampToValueAtTime(0.0001, t + 0.1);
    puff.connect(lp); lp.connect(pg); pg.connect(this.master);
    puff.start(t); puff.stop(t + 0.12);
  }

  /**
   * The lance while it burns — a sustained sizzle with a stop handle, like the heal channel
   * and the boss beam. Continuous because the THREAT is continuous: the sound stopping is
   * how you know the trigger slipped or the heat cut you off, without looking at a bar.
   */
  lanceHum() {
    if (!this.on) return null;
    const t = this.t;
    const out = this.ctx.createGain();
    out.gain.setValueAtTime(0.0001, t);
    out.gain.exponentialRampToValueAtTime(0.16, t + 0.08);
    out.connect(this.master);

    const parts = [];
    // Two close tones beating against each other: energy held, not released.
    for (const [f, g] of [[164, 0.5], [166.5, 0.35]]) {
      const o = this.ctx.createOscillator();
      o.type = "sawtooth";
      o.frequency.value = f;
      const og = this.ctx.createGain();
      og.gain.value = g;
      const warm = this.distortion(10);
      o.connect(warm); warm.connect(og); og.connect(out);
      o.start(t);
      parts.push(o);
    }
    // Frying air on top — the sizzle that says heat rather than engine.
    const air = this.noise();
    const bp = this.ctx.createBiquadFilter();
    bp.type = "bandpass";
    bp.frequency.value = 3400;
    bp.Q.value = 0.8;
    const ag = this.ctx.createGain();
    ag.gain.value = 0.3;
    air.connect(bp); bp.connect(ag); ag.connect(out);
    air.start(t);
    parts.push(air);

    let done = false;
    return {
      stop: () => {
        if (done) return;
        done = true;
        const n = this.t;
        out.gain.cancelScheduledValues(n);
        out.gain.setValueAtTime(Math.max(0.0001, out.gain.value), n);
        out.gain.exponentialRampToValueAtTime(0.0001, n + 0.08);
        for (const o of parts) { try { o.stop(n + 0.1); } catch { /* already stopped */ } }
      },
    };
  }

  /** The lance redlining: a dead CLUNK and a hiss of escaping heat. Failure must be audible. */
  overheat() {
    if (!this.on) return;
    const t = this.t;
    const o = this.ctx.createOscillator();
    o.type = "square";
    o.frequency.setValueAtTime(140, t);
    o.frequency.exponentialRampToValueAtTime(60, t + 0.08);
    const og = this.ctx.createGain();
    og.gain.setValueAtTime(0.4, t);
    og.gain.exponentialRampToValueAtTime(0.0001, t + 0.1);
    o.connect(og); og.connect(this.master);
    o.start(t); o.stop(t + 0.12);
    const hiss = this.noise();
    const hp = this.ctx.createBiquadFilter();
    hp.type = "highpass";
    hp.frequency.value = 2600;
    const hg = this.ctx.createGain();
    hg.gain.setValueAtTime(0.22, t + 0.05);
    hg.gain.exponentialRampToValueAtTime(0.0001, t + 0.65);
    hiss.connect(hp); hp.connect(hg); hg.connect(this.master);
    hiss.start(t + 0.05); hiss.stop(t + 0.7);
  }

  /**
   * Hit confirmation — the single cheapest "feels good" multiplier a shooter has, and the
   * one this game was missing entirely. A short filtered-noise TICK with a tiny pitched
   * body: enough to tell your ear the shot LANDED without fatiguing at the gun's fire rate.
   * `weak` (a headshot / weak-point) sharpens and brightens it so aim gets an audible reward.
   */
  hitConfirm(x, z, weak = false) {
    if (!this.on || !this.budget(0.5, 90)) return;
    const t = this.t;
    const { input, gain } = this.place(x, z, 130);
    if (gain <= 0.001) return;

    const src = this.noise();
    const bp = this.ctx.createBiquadFilter();
    bp.type = "bandpass";
    bp.frequency.value = weak ? 2600 : 1500;
    bp.Q.value = 0.9;
    const g = this.ctx.createGain();
    const vol = gain * (weak ? 0.5 : 0.32);
    g.gain.setValueAtTime(vol, t);
    g.gain.exponentialRampToValueAtTime(0.0001, t + (weak ? 0.09 : 0.06));
    src.connect(bp); bp.connect(g); g.connect(input);
    src.start(t); src.stop(t + 0.12);

    // A tiny pitched click gives it a body, so it reads as an impact rather than static.
    const o = this.ctx.createOscillator();
    o.type = "square";
    o.frequency.setValueAtTime(weak ? 440 : 300, t);
    o.frequency.exponentialRampToValueAtTime(weak ? 180 : 120, t + 0.05);
    const og = this.ctx.createGain();
    og.gain.setValueAtTime(vol * 0.6, t);
    og.gain.exponentialRampToValueAtTime(0.0001, t + 0.05);
    o.connect(og); og.connect(input);
    o.start(t); o.stop(t + 0.07);
  }

  /**
   * Death — the reward note. A short descending thud with a noise crunch: heavier than a
   * hit, so a kill is unmistakable from a graze even with your eyes on something else. An
   * elite gets a lower, longer version, because a star going down should feel earned.
   */
  killThud(x, z, big = false) {
    if (!this.on || !this.budget(1, 130)) return;
    const t = this.t;
    const dur = big ? 0.34 : 0.2;
    const { input, gain } = this.place(x, z, 150);
    if (gain <= 0.001) return;

    const o = this.ctx.createOscillator();
    o.type = "triangle";
    o.frequency.setValueAtTime(big ? 230 : 320, t);
    o.frequency.exponentialRampToValueAtTime(big ? 46 : 70, t + dur);
    const og = this.ctx.createGain();
    og.gain.setValueAtTime(gain * (big ? 0.6 : 0.42), t);
    og.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.connect(og); og.connect(input);
    o.start(t); o.stop(t + dur + 0.03);

    const src = this.noise();
    const lp = this.ctx.createBiquadFilter();
    lp.type = "lowpass";
    lp.frequency.setValueAtTime(1800, t);
    lp.frequency.exponentialRampToValueAtTime(200, t + dur * 0.7);
    const g = this.ctx.createGain();
    g.gain.setValueAtTime(gain * (big ? 0.4 : 0.28), t);
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur * 0.7);
    src.connect(lp); lp.connect(g); g.connect(input);
    src.start(t); src.stop(t + dur);
  }

  whoosh() {
    if (!this.on) return;
    const t = this.t, dur = 0.26;
    const { input } = this.place();
    const src = this.noise();
    const bp = this.ctx.createBiquadFilter();
    bp.type = "bandpass";
    bp.frequency.setValueAtTime(400, t);
    bp.frequency.exponentialRampToValueAtTime(1600, t + dur);
    bp.Q.value = 2;
    const g = this.ctx.createGain();
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(0.16, t + 0.06);
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    src.connect(bp); bp.connect(g); g.connect(input);
    src.start(t); src.stop(t + dur + 0.02);
  }
}

export const sfx = new Sfx();
