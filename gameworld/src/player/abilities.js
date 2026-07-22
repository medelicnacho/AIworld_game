// The ability bar: four slots on 1–4, each with its own cooldown.
//
// The shape is the MOBA one because it's the one everybody already reads: fixed slots,
// no ammo, no inventory, cost is time. That also removes the grenade's charge economy —
// a resource you had to buy is worse than a cooldown you have to respect, because the
// cooldown is legible at a glance and never sends you back to town for stock.
//
// Each ability is data: a name, a cooldown, and a run(). Adding a fifth is a table entry.

import * as THREE from "three";
import { ABILITY } from "../config.js";
import { player } from "../state.js";
import { sfx } from "../audio/sfx.js";

export const ABILITIES = [
  {
    id: "bomb", key: "1", name: "Firebomb", cd: ABILITY.bombCd,
    desc: "Lobbed explosive, detonates on impact.",
    run: (ctx) => ctx.grenades.throwFrom(ctx.camera),
  },
  {
    id: "mend", key: "2", name: "Mend", cd: ABILITY.mendCd,
    desc: "Channel to heal. Breaks if you move or are hit.",
    run: (ctx) => ctx.heal.start(),
  },
  {
    id: "surge", key: "3", name: "Surge", cd: ABILITY.surgeCd,
    desc: "Burst of speed, briefly untouchable.",
    run: () => {
      player.surgeT = ABILITY.surgeTime;
      player.iframes = Math.max(player.iframes, ABILITY.surgeIframes);
      sfx.healCast(0.4);
      return true;
    },
  },
  {
    id: "quake", key: "4", name: "Cataclysm", cd: ABILITY.quakeCd,
    desc: "Shockwave: heavy damage to everything around you.",
    run: (ctx) => {
      ctx.quake(player.x, player.y + 1, player.z);
      return true;
    },
  },
];

export class Abilities {
  constructor(scene, ctx) {
    this.ctx = ctx;
    this.cd = ABILITIES.map(() => 0);

    // One shared shockwave ring, reused. Cataclysm is on a long cooldown, so a second one
    // can never overlap the first.
    const geo = new THREE.RingGeometry(0.6, 1.0, 40);
    geo.rotateX(-Math.PI / 2);
    this.wave = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({
      color: 0xffc46b, transparent: true, opacity: 0, side: THREE.DoubleSide, depthWrite: false,
    }));
    this.wave.visible = false;
    scene.add(this.wave);
    this.waveT = 0;
  }

  ready(i) { return this.cd[i] <= 0; }

  /** @returns {string} a line for the HUD when it couldn't be used. */
  use(i) {
    const a = ABILITIES[i];
    if (!a) return "";
    if (this.cd[i] > 0) return `${a.name} — ${this.cd[i].toFixed(1)}s`;
    // run() returning false means the ability declined (already healing, no slot free), so
    // the cooldown is NOT spent. A cooldown burned on a no-op feels like a bug.
    if (a.run(this.ctx) === false) return "";
    this.cd[i] = a.cd;
    return "";
  }

  update(dt) {
    for (let i = 0; i < this.cd.length; i++) if (this.cd[i] > 0) this.cd[i] -= dt;

    if (player.surgeT > 0) player.surgeT -= dt;

    if (this.waveT > 0) {
      this.waveT -= dt;
      const f = 1 - this.waveT / ABILITY.quakeFlash;
      this.wave.scale.setScalar(1 + f * ABILITY.quakeRadius);
      this.wave.material.opacity = (1 - f) * 0.75;
      if (this.waveT <= 0) this.wave.visible = false;
    }
  }

  showWave(x, y, z) {
    this.wave.position.set(x, y - 0.4, z);
    this.wave.visible = true;
    this.waveT = ABILITY.quakeFlash;
    sfx.explosion(x, z, 1.5);
  }
}
