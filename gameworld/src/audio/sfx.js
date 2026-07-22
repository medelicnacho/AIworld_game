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
  }

  /** Must be called from a user gesture — browsers refuse audio before one. */
  unlock() {
    if (this.ctx) { if (this.ctx.state === "suspended") this.ctx.resume(); return; }
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    this.ctx = new AC();
    this.master = this.ctx.createGain();
    this.master.gain.value = 0.9;
    this.master.connect(this.ctx.destination);

    // One second of white noise, reused by every noise-based sound. Seeded like everything
    // else (D14) — an exception you have to remember is worse than a one-line fix.
    const n = this.ctx.sampleRate;
    this.noiseBuf = this.ctx.createBuffer(1, n, n);
    const d = this.noiseBuf.getChannelData(0);
    const rnd = mulberry32(0x1103E);
    for (let i = 0; i < n; i++) d[i] = rnd() * 2 - 1;
  }

  get on() { return this.ctx && !this.muted; }

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

  /** Your gun. Non-positional and quiet — it fires 7.5×/sec and must not fatigue. */
  gunshot() {
    if (!this.on) return;
    const t = this.t, dur = 0.12;
    const { input } = this.place();

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
    if (!this.on) return;
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

  /** Meteor impacts and grenades. `size` scales the length and the low thump. */
  explosion(x, z, size = 1) {
    if (!this.on) return;
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
  async playClip(arrayBuffer, x, z, volume = 1) {
    if (!this.on || !arrayBuffer) return 0;
    let buf;
    try {
      buf = await this.ctx.decodeAudioData(arrayBuffer.slice(0));
    } catch {
      return 0;
    }
    const src = this.ctx.createBufferSource();
    src.buffer = buf;
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
    if (!this.on) return;
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

  /** Grenade throw. */
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
