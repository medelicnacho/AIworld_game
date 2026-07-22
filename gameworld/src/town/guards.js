// The gate detachment.
//
// A camp parked outside a gateway made the door unusable, and "wait indoors until they
// wander off" is not gameplay. Guards solve that as a FIGHT rather than as a wall: they
// pull mobs off you, they can lose, and they make a town read as somewhere people are
// holding rather than somewhere the architecture is.
//
// The dead zone is the load-bearing part. No points and no experience anywhere near a
// guard — otherwise the optimal way to play is to stand behind the line and let the town
// farm the frontier for you, which is boring AND unbeatable.

import * as THREE from "three";
import { GUARD } from "../config.js";
import { player } from "../state.js";
import { groundY, tierAt } from "../world/gen.js";
import { sanctuariesNear, boundaryAt, gateArc } from "../world/sanctuary.js";
import { sfx } from "../audio/sfx.js";

const KEEP = 300;
let _live = [];        // flat list, for the mob layer to taunt against

/** The guard a mob at (x,z) should be fighting instead of the player, if any. */
export function guardNear(x, z, range = GUARD.taunt) {
  let best = null, bd = range;
  for (const g of _live) {
    if (g.down > 0) continue;
    const d = Math.hypot(g.x - x, g.z - z);
    if (d < bd) { bd = d; best = g; }
  }
  return best;
}

export class Guards {
  constructor(scene) {
    this.scene = scene;
    this.built = new Map();
    this.geo = new THREE.ConeGeometry(0.5, 1.7, 6);
    this.geo.translate(0, 0.85, 0);
    this.mat = new THREE.MeshLambertMaterial({ color: 0x6fa8dc });
    this.matDown = new THREE.MeshLambertMaterial({ color: 0x3a4455 });
    this.tracer = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]),
      new THREE.LineBasicMaterial({ color: 0x9fe8ff, transparent: true, opacity: 0 }),
    );
    this.tracer.frustumCulled = false;
    scene.add(this.tracer);
    this.tracerT = 0;
  }

  build(s) {
    const guards = [];
    const gateR = boundaryAt(s, s.gate);
    const arc = gateArc(gateR);
    for (let i = 0; i < GUARD.count; i++) {
      // Fanned across the approach, just outside the gateway.
      const t = (i / (GUARD.count - 1) - 0.5) * 2;
      const a = s.gate + t * (arc + GUARD.spread / gateR);
      const r = boundaryAt(s, a) + 4 + Math.abs(t) * 2;
      const x = s.x + Math.cos(a) * r;
      const z = s.z + Math.sin(a) * r;
      const mesh = new THREE.Mesh(this.geo, this.mat);
      mesh.position.set(x, groundY(x, z), z);
      this.scene.add(mesh);
      const tier = tierAt(x, z);
      const hp = GUARD.hp * (1 + GUARD.hpPerTier * tier);
      guards.push({ postX: x, postZ: z, x, z, mesh, cd: i * 0.4, hp, maxHp: hp, down: 0 });
    }
    this.built.set(s.id, guards);
  }

  drop(id) {
    const gs = this.built.get(id);
    if (!gs) return;
    for (const g of gs) this.scene.remove(g.mesh);
    this.built.delete(id);
  }

  /** True when the player is close enough to a guard that kills should not pay. */
  inDeadZone() {
    for (const g of _live) {
      if (Math.hypot(player.x - g.x, player.z - g.z) < GUARD.deadZone) return true;
    }
    return false;
  }

  update(dt, mobs) {
    const want = new Set();
    for (const s of sanctuariesNear(player.x, player.z, KEEP)) {
      want.add(s.id);
      if (!this.built.has(s.id)) this.build(s);
    }
    for (const id of [...this.built.keys()]) if (!want.has(id)) this.drop(id);

    _live = [];
    for (const gs of this.built.values()) for (const g of gs) _live.push(g);

    if (this.tracerT > 0) {
      this.tracerT -= dt;
      this.tracer.material.opacity = Math.max(0, this.tracerT / 0.06) * 0.8;
    }

    const tier = tierAt(player.x, player.z);
    const dmg = GUARD.damage * (1 + GUARD.damagePerTier * tier);

    for (const g of _live) {
      if (g.down > 0) {
        g.down -= dt;
        if (g.down <= 0) { g.hp = g.maxHp; g.mesh.material = this.mat; }
        continue;
      }

      // Anything in melee range is hitting them. Guards are worn down by numbers, which is
      // what makes a big camp at the gate a problem you still have to solve.
      let pressing = 0;
      let best = null, bd = GUARD.range;
      for (const e of mobs.entities()) {
        const d = Math.hypot(e.x - g.x, e.z - g.z);
        if (d < GUARD.meleeRange) pressing++;
        if (d < bd) { bd = d; best = e; }
      }
      if (pressing) g.hp -= pressing * 14 * dt;
      else g.hp = Math.min(g.maxHp, g.hp + GUARD.regen * dt);

      if (g.hp <= 0) {
        g.down = GUARD.respawn;
        g.mesh.material = this.matDown;
        continue;
      }

      // Hold the line: drift back toward the post rather than chasing off after a straggler.
      const dx = g.postX - g.x, dz = g.postZ - g.z;
      const pd = Math.hypot(dx, dz);
      if (pd > 0.4) {
        const step = Math.min(pd, 2.2 * dt);
        g.x += (dx / pd) * step;
        g.z += (dz / pd) * step;
      } else if (best && bd < GUARD.range) {
        const ax = best.x - g.x, az = best.z - g.z, ad = Math.hypot(ax, az) || 1;
        if (ad > GUARD.meleeRange * 1.5 && pd < GUARD.post) {
          g.x += (ax / ad) * 1.6 * dt;
          g.z += (az / ad) * 1.6 * dt;
        }
      }
      g.mesh.position.set(g.x, groundY(g.x, g.z), g.z);
      if (best) g.mesh.rotation.y = Math.atan2(best.x - g.x, best.z - g.z);

      g.cd -= dt;
      if (g.cd > 0 || !best) continue;
      g.cd = 1 / GUARD.fireRate;

      const p = this.tracer.geometry.attributes.position;
      p.setXYZ(0, g.x, groundY(g.x, g.z) + 1.4, g.z);
      p.setXYZ(1, best.x, best.y + 0.8, best.z);
      p.needsUpdate = true;
      this.tracerT = 0.06;
      // Positional, quiet, and SILENT past soundRange: a detachment defending a town you
      // are nowhere near should not be audible across the map. Four guards firing beside a
      // town are background at best; from a ridgeline away they are nothing.
      if (Math.hypot(player.x - g.x, player.z - g.z) < GUARD.soundRange) {
        sfx.gunshot(g.x, g.z, 0.22);
      }

      // A guard kill pays the player NOTHING, wherever the player is. The mob still dies
      // properly (death sound, affix hooks and despawn all happened inside mobs.hit) -- it
      // simply awards no points or xp, because the guard did the work, not you. onKill is
      // deliberately not called: routing it through reward() only paid when you happened to
      // be standing in the dead zone, so kills out on the frontier were quietly paying you.
      mobs.hit(best.id, dmg);
    }
  }
}
