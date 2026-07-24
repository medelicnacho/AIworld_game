// Floating damage numbers — the cheapest, biggest hit-feedback juice there is.
//
// Same projected-DOM trick as the health bars: a pool of spans, each parked at a world point,
// floating up and fading over its life. Pooled and capped, because a fire-ring on a crowd can
// spawn a dozen at once and the screen must not fill with text.

import * as THREE from "three";

const MAX = 40;
const LIFE = 0.8;      // seconds a number lives
const RISE = 1.3;      // world units it floats upward over its life

export class DamageText {
  constructor(el, camera) {
    this.el = el;
    this.camera = camera;
    this.v = new THREE.Vector3();
    this.pool = [];
    for (let i = 0; i < MAX; i++) {
      const d = document.createElement("div");
      d.className = "dmgnum";
      d.style.display = "none";
      el.appendChild(d);
      this.pool.push({ el: d, active: false, x: 0, y: 0, z: 0, t: 0 });
    }
    this.i = 0;
  }

  spawn(x, y, z, amount, big = false) {
    const s = this.pool[this.i = (this.i + 1) % this.pool.length];
    s.active = true;
    s.x = x; s.y = y; s.z = z; s.t = LIFE;
    s.el.textContent = String(amount);
    s.el.className = big ? "dmgnum crit" : "dmgnum";
    s.el.style.display = "block";
  }

  draw(dt) {
    const w = window.innerWidth, h = window.innerHeight;
    for (const s of this.pool) {
      if (!s.active) continue;
      s.t -= dt;
      if (s.t <= 0) { s.active = false; s.el.style.display = "none"; continue; }
      const f = s.t / LIFE;                     // 1 → 0
      this.v.set(s.x, s.y + (1 - f) * RISE, s.z);
      this.v.project(this.camera);
      if (this.v.z > 1) { s.el.style.display = "none"; continue; }
      s.el.style.display = "block";
      s.el.style.left = `${(this.v.x * 0.5 + 0.5) * w}px`;
      s.el.style.top = `${(-this.v.y * 0.5 + 0.5) * h}px`;
      s.el.style.opacity = String(Math.min(1, f * 1.6));
    }
  }
}
