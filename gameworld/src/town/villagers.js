// Villagers: the people who live inside a sanctuary and trade with you.
//
// Unlike the nomads, these are BOUND to their refuge — they never leave the walls. That is
// what makes a sanctuary a destination rather than a wall you hide behind: gold you take
// off the frontier is only worth anything where someone will take it.
//
// Same scope discipline as the folk: bodies, roles and a trade table. No speech, no memory,
// no bonds. When the substrate arrives at Stage 3, THESE are the souls — a walled settlement
// with residents is exactly the shape a town needs, and the seam is already the right one.

import * as THREE from "three";
import { VILLAGE } from "../config.js";
import { player } from "../state.js";
import { groundY } from "../world/gen.js";
import { sanctuariesNear } from "../world/sanctuary.js";
import { mulberry32 } from "../rng.js";

// Who lives here. What they actually SELL is a table in ui/shop.js (GOODS), keyed by these
// role keys — stock is data, so adding wares never touches this file or the game loop.
export const ROLES = [
  { key: "herbalist", name: "Herbalist", color: 0x63d1a0 },
  { key: "smith", name: "Smith", color: 0xd8b06a },
  { key: "adept", name: "Adept", color: 0x14141c },   // black: the one who sells abilities
  { key: "keeper", name: "Keeper", color: 0x8fa6c4 },
];

export class Villagers {
  constructor(scene, seed = 0x71DE) {
    this.rng = mulberry32(seed);
    this.built = new Map();     // sanctuary id -> [villager]
    this.list = [];             // flat, for proximity checks

    this.geo = new THREE.ConeGeometry(0.5, 1.6, 6);
    this.geo.translate(0, 0.8, 0);
    this.mesh = new THREE.InstancedMesh(
      this.geo, new THREE.MeshLambertMaterial({}), VILLAGE.maxRendered);
    this.mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    this.mesh.frustumCulled = false;
    this.mesh.count = 0;
    scene.add(this.mesh);

    this._m = new THREE.Matrix4();
    this._q = new THREE.Quaternion();
    this._p = new THREE.Vector3();
    this._s = new THREE.Vector3(1, 1, 1);
    this._up = new THREE.Vector3(0, 1, 0);
    this._colors = ROLES.map((r) => new THREE.Color(r.color));
  }

  populate(s) {
    const rng = mulberry32(Number(s.id.split(",").reduce((a, b) => a * 31 + Number(b), 7)) >>> 0);
    const folk = [];
    // Every refuge has a herbalist, a smith and an adept — a sanctuary you can't resupply
    // or re-arm at is just scenery — plus keepers so it reads as a place people live.
    const roles = ["herbalist", "smith", "adept"];
    // A city is bigger, so it holds more people AND a second set of traders — walking a
    // city to find the one adept would be a chore rather than a place.
    if (s.city) roles.push("herbalist", "smith", "adept");
    const want = Math.round(VILLAGE.perSanctuary * (s.r / 46));
    while (roles.length < want) roles.push("keeper");
    for (const key of roles) {
      const ri = ROLES.findIndex((r) => r.key === key);
      folk.push({
        role: ROLES[ri], ri, s,
        ang: rng() * Math.PI * 2,
        rad: 4 + rng() * Math.max(4, s.rMin - 9),   // inside even the nearest wall
        spd: (rng() < 0.5 ? -1 : 1) * (0.02 + rng() * 0.05),   // slower: a bigger circuit
        bob: rng() * Math.PI * 2,
        x: s.x, z: s.z, y: 0,
      });
    }
    this.built.set(s.id, folk);
  }

  update(dt) {
    const want = new Set();
    for (const s of sanctuariesNear(player.x, player.z, VILLAGE.keepRange)) {
      want.add(s.id);
      if (!this.built.has(s.id)) this.populate(s);
    }
    for (const id of [...this.built.keys()]) if (!want.has(id)) this.built.delete(id);

    this.list = [];
    for (const folk of this.built.values()) {
      for (const v of folk) {
        // A slow circuit of the enclosure. They have somewhere to be, and it is here.
        v.ang += v.spd * dt;
        v.bob += dt * 1.8;
        v.x = v.s.x + Math.cos(v.ang) * v.rad;
        v.z = v.s.z + Math.sin(v.ang) * v.rad;
        v.y = groundY(v.x, v.z) + Math.sin(v.bob) * 0.04;
        this.list.push(v);
      }
    }
    this.render();
  }

  /** The villager you're standing next to, if any — what the trade prompt reads. */
  nearest() {
    let best = null, bd = VILLAGE.talkRange;
    for (const v of this.list) {
      const d = Math.hypot(v.x - player.x, v.z - player.z);
      if (d < bd) { bd = d; best = v; }
    }
    return best;
  }

  render() {
    let i = 0;
    const cap = this.mesh.instanceMatrix.count;
    for (const v of this.list) {
      if (i >= cap) break;
      this._q.setFromAxisAngle(this._up, -v.ang);
      this._m.compose(this._p.set(v.x, v.y, v.z), this._q, this._s);
      this.mesh.setMatrixAt(i, this._m);
      this.mesh.setColorAt(i, this._colors[v.ri]);
      i++;
    }
    this.mesh.count = i;
    this.mesh.instanceMatrix.needsUpdate = true;
    if (this.mesh.instanceColor) this.mesh.instanceColor.needsUpdate = true;
  }
}


