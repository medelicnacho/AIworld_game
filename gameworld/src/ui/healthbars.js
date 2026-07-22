// Little health bars over enemies.
//
// Same projected-DOM trick as the nameplates, and the same hard constraint: there are up to
// 340 mobs alive and there can never be 340 bars. Two filters keep the count sane and the
// screen readable:
//
//   1. Only enemies you have actually HURT (or stars, which are worth tracking from full).
//   2. Only within a short range, sorted by distance, capped at MAX.
//
// A bar over every distant unhurt mob would be visual noise that tells you nothing — the
// information you want is "how close is THIS one to dying", and that only exists once you
// have started.

import * as THREE from "three";

const MAX = 28;
const RANGE = 34;

export class HealthBars {
  constructor(el, camera) {
    this.el = el;
    this.camera = camera;
    this.v = new THREE.Vector3();
    this.pool = [];
    for (let i = 0; i < MAX; i++) {
      const d = document.createElement("div");
      d.className = "hpbar";
      d.innerHTML = "<i></i>";
      d.style.display = "none";
      el.appendChild(d);
      this.pool.push({ el: d, fill: d.firstChild });
    }
  }

  /** @param {Iterable<{x,y,z,hp,maxHp,elite}>} mobs */
  draw(mobs) {
    const w = window.innerWidth, h = window.innerHeight;
    const cam = this.camera.position;
    const near = [];

    for (const e of mobs) {
      if (e.hp >= e.maxHp && !e.elite) continue;          // unhurt and unremarkable
      const d = Math.hypot(e.x - cam.x, e.z - cam.z);
      if (d > RANGE) continue;
      near.push({ e, d });
    }
    // Closest first, so the cap drops the ones you care least about.
    near.sort((a, b) => a.d - b.d);

    let n = 0;
    for (const { e, d } of near) {
      if (n >= MAX) break;
      this.v.set(e.x, e.y + (e.flies ? -1.9 : 2.0), e.z);
      this.v.project(this.camera);
      if (this.v.z > 1) continue;                          // behind the camera

      const slot = this.pool[n++];
      slot.el.style.display = "block";
      slot.el.style.left = `${(this.v.x * 0.5 + 0.5) * w}px`;
      slot.el.style.top = `${(-this.v.y * 0.5 + 0.5) * h}px`;
      slot.el.style.opacity = String(Math.max(0.3, 1 - d / RANGE));
      slot.el.classList.toggle("elite", !!e.elite);
      slot.fill.style.width = `${Math.max(0, Math.min(1, e.hp / e.maxHp)) * 100}%`;
    }
    for (let i = n; i < MAX; i++) {
      if (this.pool[i].el.style.display !== "none") this.pool[i].el.style.display = "none";
    }
  }
}
