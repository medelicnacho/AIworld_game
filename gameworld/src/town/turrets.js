// Turrets flanking every town gate.
//
// A gateway with a camp parked outside it is a door you cannot use, and "wait inside until
// they wander off" is not gameplay. Two guns cover the approach so LEAVING is survivable.
//
// The important half is the DEAD ZONE: no points and no experience are awarded anywhere
// near a turret. Without it the optimal strategy is to stand behind the guns and let the
// town farm the frontier on your behalf — which is both boring and unbeatable, the two
// qualities that make an exploit worth closing before anyone finds it.

import * as THREE from "three";
import { TURRET } from "../config.js";
import { player } from "../state.js";
import { groundY, tierAt } from "../world/gen.js";
import { sanctuariesNear, boundaryAt, gateArc } from "../world/sanctuary.js";
import { sfx } from "../audio/sfx.js";

const KEEP = 260;      // build turrets for towns within this range

export class Turrets {
  constructor(scene) {
    this.scene = scene;
    this.built = new Map();      // sanctuary id -> [{x, y, z, cd, mesh}]
    this.geo = new THREE.CylinderGeometry(0.55, 0.9, TURRET.height, 7);
    this.geo.translate(0, TURRET.height / 2, 0);
    this.mat = new THREE.MeshLambertMaterial({ color: 0x8fa3bf });
    this.headGeo = new THREE.BoxGeometry(0.5, 0.5, 1.5);
    this.headMat = new THREE.MeshLambertMaterial({ color: 0x4a5a75 });

    // Shared tracer, like the gun's — turrets never fire in the same millisecond.
    this.tracer = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]),
      new THREE.LineBasicMaterial({ color: 0x9fe8ff, transparent: true, opacity: 0 }),
    );
    this.tracer.frustumCulled = false;
    scene.add(this.tracer);
    this.tracerT = 0;
  }

  build(s) {
    const guns = [];
    const gateR = boundaryAt(s, s.gate);
    const arc = gateArc(gateR);
    for (let i = 0; i < TURRET.count; i++) {
      // One to each side of the gateway, just outside the wall line.
      const side = i === 0 ? 1 : -1;
      const a = s.gate + side * (arc + TURRET.offset / gateR);
      const r = boundaryAt(s, a) + 2.2;
      const x = s.x + Math.cos(a) * r;
      const z = s.z + Math.sin(a) * r;
      const y = groundY(x, z);
      const g = new THREE.Group();
      const body = new THREE.Mesh(this.geo, this.mat);
      const head = new THREE.Mesh(this.headGeo, this.headMat);
      head.position.y = TURRET.height;
      g.add(body, head);
      g.position.set(x, y, z);
      this.scene.add(g);
      guns.push({ x, y: y + TURRET.height, z, cd: i * 0.3, group: g, head });
    }
    this.built.set(s.id, guns);
  }

  drop(id) {
    const guns = this.built.get(id);
    if (!guns) return;
    for (const g of guns) this.scene.remove(g.group);
    this.built.delete(id);
  }

  /** True if the player is close enough to a turret that kills should not pay. */
  inDeadZone() {
    for (const guns of this.built.values()) {
      for (const g of guns) {
        if (Math.hypot(player.x - g.x, player.z - g.z) < TURRET.deadZone) return true;
      }
    }
    return false;
  }

  update(dt, mobs, onKill) {
    const want = new Set();
    for (const s of sanctuariesNear(player.x, player.z, KEEP)) {
      want.add(s.id);
      if (!this.built.has(s.id)) this.build(s);
    }
    for (const id of [...this.built.keys()]) if (!want.has(id)) this.drop(id);

    if (this.tracerT > 0) {
      this.tracerT -= dt;
      this.tracer.material.opacity = Math.max(0, this.tracerT / 0.07);
    }

    const dmg = TURRET.damage * (1 + TURRET.damagePerTier * tierAt(player.x, player.z));

    for (const guns of this.built.values()) {
      for (const g of guns) {
        g.cd -= dt;
        if (g.cd > 0) continue;

        // Nearest hostile in range. Turrets are not clever — they shoot what is closest,
        // which is also what is most likely to reach the gate.
        let best = null, bd = TURRET.range;
        for (const e of mobs.entities()) {
          const d = Math.hypot(e.x - g.x, e.z - g.z);
          if (d < bd) { bd = d; best = e; }
        }
        if (!best) continue;

        g.cd = 1 / TURRET.fireRate;
        g.head.lookAt(best.x, best.y + 0.8, best.z);
        const p = this.tracer.geometry.attributes.position;
        p.setXYZ(0, g.x, g.y, g.z);
        p.setXYZ(1, best.x, best.y + 0.8, best.z);
        p.needsUpdate = true;
        this.tracerT = 0.07;
        sfx.gunshot();

        const res = mobs.hit(best.id, dmg);
        // The kill is reported so the world stays consistent (corpses, affix deaths), but
        // main decides whether it pays — and near a turret it never does.
        if (res?.killed) onKill?.(res);
      }
    }
  }
}
