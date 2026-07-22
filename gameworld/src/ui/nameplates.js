// Floating names over the traders.
//
// DOM labels projected to screen rather than sprites in the scene: they stay crisp at any
// distance, need no texture atlas or font baking, and cost nothing to change. That only
// works because the count is TINY — the handful of vendors near you, never the 340 mobs.
//
// Elements are pooled and reused; building DOM per frame for something that moves every
// frame is the classic way to make a smooth game stutter.

import * as THREE from "three";

const MAX = 24;
const RANGE = 46;          // beyond this a plate is unreadable anyway

export class Nameplates {
  constructor(el, camera) {
    this.el = el;
    this.camera = camera;
    this.pool = [];
    this.v = new THREE.Vector3();
    for (let i = 0; i < MAX; i++) {
      const d = document.createElement("div");
      d.className = "plate";
      d.style.display = "none";
      el.appendChild(d);
      this.pool.push(d);
    }
  }

  /** @param {Array<{x,y,z,label,sub}>} items */
  draw(items) {
    const w = window.innerWidth, h = window.innerHeight;
    let n = 0;
    for (const it of items) {
      if (n >= MAX) break;
      this.v.set(it.x, it.y, it.z);
      const dist = this.v.distanceTo(this.camera.position);
      if (dist > RANGE) continue;
      this.v.project(this.camera);
      // Behind the camera projects to a valid-looking point in front of it — z > 1 is the
      // only thing that catches it, and without this every plate behind you appears mirrored.
      if (this.v.z > 1) continue;

      const d = this.pool[n++];
      d.style.display = "block";
      d.style.left = `${(this.v.x * 0.5 + 0.5) * w}px`;
      d.style.top = `${(-this.v.y * 0.5 + 0.5) * h}px`;
      d.style.opacity = String(Math.max(0.25, 1 - dist / RANGE));
      const html = `${it.label}${it.sub ? `<span>${it.sub}</span>` : ""}`;
      if (d.dataset.html !== html) { d.innerHTML = html; d.dataset.html = html; }
    }
    for (let i = n; i < MAX; i++) {
      if (this.pool[i].style.display !== "none") this.pool[i].style.display = "none";
    }
  }
}
