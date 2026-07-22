// The green folk: nomad bands that roam, bunch, and breed.
//
// SCOPE, deliberately: movement only. No speech, no memory, no bonds, no opinions. The
// brain is being built separately in the lab, and this is the BODY layer it will drive —
// so everything here is locomotion and population, and nothing here pretends to be a mind.
//
// The movement is the same force model the lab's `_drift_positions()` uses and that mobs
// already run: separation so they never stack, alignment so a band travels as one body,
// cohesion so stragglers rejoin. What makes them nomads rather than campers is that their
// centre MOVES — a band picks a destination, walks there over a minute or two, and picks
// another. Bands grow by breeding and SPLIT when they get too big, which is the whole
// population loop: wander, swell, divide, wander.

import * as THREE from "three";
import { FOLK } from "../config.js";
import { player } from "../state.js";
import { addEntity, removeEntity, reindex, world, nearby } from "../state.js";
import { groundY } from "../world/gen.js";
import { sanctuariesNear, sanctuaryOf } from "../world/sanctuary.js";
import { mulberry32 } from "../rng.js";

export class Folk {
  constructor(scene, seed = 0xF01C) {
    this.rng = mulberry32(seed);
    this.bands = new Map();      // bandId -> {tx, tz, retarget}
    this.nextBand = 1;
    this.spawnTimer = 0;
    this.born = 0;

    this.geo = new THREE.ConeGeometry(0.5, 1.5, 5);
    this.geo.translate(0, 0.75, 0);
    this.mesh = new THREE.InstancedMesh(
      this.geo, new THREE.MeshLambertMaterial({}), FOLK.maxAlive + 24);
    this.mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    this.mesh.frustumCulled = false;
    this.mesh.count = 0;
    scene.add(this.mesh);

    this._m = new THREE.Matrix4();
    this._q = new THREE.Quaternion();
    this._p = new THREE.Vector3();
    this._s = new THREE.Vector3(1, 1, 1);
    this._up = new THREE.Vector3(0, 1, 0);
    this.COL = new THREE.Color(0x4fbf6a);
    this.COL_YOUNG = new THREE.Color(0x9ae6a8);   // the newly born are paler
  }

  *entities() {
    for (const e of world.entities.values()) if (e.kind === "folk") yield e;
  }

  count(band) {
    let n = 0;
    for (const e of this.entities()) if (e.band === band) n++;
    return n;
  }

  /** Somewhere to be heading. Bands drift toward refuges more often than not. */
  pickTarget(x, z) {
    const refuges = sanctuariesNear(x, z, FOLK.roam * 1.5);
    if (refuges.length && this.rng() < FOLK.refugeBias) {
      const s = refuges[Math.floor(this.rng() * refuges.length)];
      return { tx: s.x, tz: s.z };
    }
    const a = this.rng() * Math.PI * 2;
    const d = FOLK.roam * (0.4 + this.rng() * 0.6);
    return { tx: x + Math.cos(a) * d, tz: z + Math.sin(a) * d };
  }

  spawnOne(x, z, band, young = false) {
    return addEntity({
      kind: "folk", band,
      x, y: groundY(x, z), z,
      speed: FOLK.speed * (0.9 + this.rng() * 0.25),
      heading: this.rng() * Math.PI * 2,
      wobble: this.rng() * Math.PI * 2,
      breedCd: FOLK.breedEvery[0] + this.rng() * (FOLK.breedEvery[1] - FOLK.breedEvery[0]),
      age: young ? 0 : FOLK.maturity,
    });
  }

  spawnBand() {
    const a = this.rng() * Math.PI * 2;
    const d = FOLK.spawnMin + this.rng() * (FOLK.spawnMax - FOLK.spawnMin);
    const bx = player.x + Math.cos(a) * d;
    const bz = player.z + Math.sin(a) * d;
    const id = this.nextBand++;
    this.bands.set(id, { ...this.pickTarget(bx, bz), retarget: FOLK.retarget[0] });
    const [lo, hi] = FOLK.bandSize;
    const n = lo + Math.floor(this.rng() * (hi - lo + 1));
    for (let i = 0; i < n; i++) {
      const ang = this.rng() * Math.PI * 2;
      const r = this.rng() * 5;
      this.spawnOne(bx + Math.cos(ang) * r, bz + Math.sin(ang) * r, id);
    }
  }

  update(dt) {
    let alive = 0;
    for (const _ of this.entities()) alive++;   // eslint-disable-line no-unused-vars

    this.spawnTimer -= dt;
    if (alive < FOLK.maxAlive && this.bands.size < FOLK.maxBands && this.spawnTimer <= 0) {
      this.spawnTimer = FOLK.spawnInterval;
      this.spawnBand();
    }

    // Bands wander: each picks a destination and walks to it, then picks another.
    for (const [id, b] of this.bands) {
      b.retarget -= dt;
      if (b.retarget <= 0) {
        const n = this.count(id);
        if (n === 0) { this.bands.delete(id); continue; }
        // Aim from where the band actually IS, not from where it was born.
        let cx = 0, cz = 0;
        for (const e of this.entities()) if (e.band === id) { cx += e.x; cz += e.z; }
        Object.assign(b, this.pickTarget(cx / n, cz / n));
        b.retarget = FOLK.retarget[0] + this.rng() * (FOLK.retarget[1] - FOLK.retarget[0]);
      }
    }

    const babies = [];
    const splits = [];

    for (const e of nearby(player.x, player.z, FOLK.despawn)) {
      if (e.kind !== "folk") continue;
      const band = this.bands.get(e.band);
      if (!band) { removeEntity(e.id); continue; }
      if (Math.hypot(player.x - e.x, player.z - e.z) > FOLK.despawn) { removeEntity(e.id); continue; }

      e.age += dt;

      // Flocking — identical in shape to the mob steering and to _drift_positions().
      let sepX = 0, sepZ = 0, aliX = 0, aliZ = 0, cohX = 0, cohZ = 0, kin = 0;
      for (const o of nearby(e.x, e.z, FOLK.neighborRadius)) {
        if (o === e || o.kind !== "folk") continue;
        const d = Math.hypot(o.x - e.x, o.z - e.z);
        if (d > FOLK.neighborRadius) continue;
        if (d < FOLK.separation) {
          const w = (FOLK.separation - d) / FOLK.separation;
          sepX += ((e.x - o.x) / (d || 1)) * w;
          sepZ += ((e.z - o.z) / (d || 1)) * w;
        }
        aliX += Math.cos(o.heading); aliZ += Math.sin(o.heading);
        if (o.band === e.band) { cohX += o.x - e.x; cohZ += o.z - e.z; kin++; }
      }
      if (kin) { cohX /= kin * 10; cohZ /= kin * 10; }

      // Toward the band's destination — the nomad part.
      const tdx = band.tx - e.x, tdz = band.tz - e.z;
      const td = Math.hypot(tdx, tdz) || 1;
      let vx = (tdx / td) * FOLK.travel;
      let vz = (tdz / td) * FOLK.travel;

      // Give hostiles a wide berth. Not fear as a feeling — just a repulsion force, which
      // is all a body needs until there's a mind to be afraid with.
      for (const o of nearby(e.x, e.z, FOLK.wary)) {
        if (o.kind !== "mob") continue;
        const d = Math.hypot(o.x - e.x, o.z - e.z);
        if (d > FOLK.wary) continue;
        const w = (FOLK.wary - d) / FOLK.wary;
        vx += ((e.x - o.x) / (d || 1)) * w * FOLK.flee;
        vz += ((e.z - o.z) / (d || 1)) * w * FOLK.flee;
      }

      e.wobble += dt * 0.5;
      vx += Math.cos(e.wobble) * 0.25 + sepX * FOLK.sepForce + aliX * FOLK.alignForce + cohX * FOLK.cohesionForce;
      vz += Math.sin(e.wobble) * 0.25 + sepZ * FOLK.sepForce + aliZ * FOLK.alignForce + cohZ * FOLK.cohesionForce;

      // BREEDING: kin nearby, band under cap, grown. Bands swell as they travel.
      e.breedCd -= dt;
      if (e.breedCd <= 0) {
        e.breedCd = FOLK.breedEvery[0] + this.rng() * (FOLK.breedEvery[1] - FOLK.breedEvery[0]);
        const n = this.count(e.band);
        if (kin >= 1 && e.age >= FOLK.maturity && n < FOLK.bandCap
            && alive + babies.length < FOLK.maxAlive) {
          babies.push(e);
          if (n + 1 >= FOLK.splitAt) splits.push(e.band);
        }
      }

      const m = Math.hypot(vx, vz);
      if (m > 1e-4) {
        const step = (vx / m) * e.speed * dt;
        const stepZ = (vz / m) * e.speed * dt;
        const here = groundY(e.x, e.z);
        if (groundY(e.x + step, e.z + stepZ) - here <= FOLK.maxClimb) {
          e.x += step; e.z += stepZ;
          e.heading = Math.atan2(step, stepZ);
        }
      }
      e.y = groundY(e.x, e.z);
      reindex(e);
    }

    for (const parent of babies) {
      const a = this.rng() * Math.PI * 2;
      this.spawnOne(parent.x + Math.cos(a) * 1.4, parent.z + Math.sin(a) * 1.4, parent.band, true);
      this.born++;
    }

    // A band that outgrows itself DIVIDES: half wander off under a new heading. Wander,
    // swell, divide, wander — the whole nomad loop, and the reason they spread over time.
    for (const bandId of new Set(splits)) {
      const members = [...this.entities()].filter((e) => e.band === bandId);
      if (members.length < FOLK.splitAt) continue;
      const id = this.nextBand++;
      const half = members.slice(0, Math.floor(members.length / 2));
      const cx = half.reduce((a, e) => a + e.x, 0) / half.length;
      const cz = half.reduce((a, e) => a + e.z, 0) / half.length;
      this.bands.set(id, { ...this.pickTarget(cx, cz), retarget: FOLK.retarget[0] });
      for (const e of half) e.band = id;
    }

    this.render();
  }

  render() {
    let i = 0;
    const cap = this.mesh.instanceMatrix.count;
    for (const e of this.entities()) {
      if (i >= cap) break;
      const young = e.age < FOLK.maturity;
      const sc = young ? 0.62 : 1;
      this._q.setFromAxisAngle(this._up, e.heading);
      this._m.compose(this._p.set(e.x, e.y, e.z), this._q, this._s.set(sc, sc, sc));
      this.mesh.setMatrixAt(i, this._m);
      this.mesh.setColorAt(i, young ? this.COL_YOUNG : this.COL);
      i++;
    }
    this.mesh.count = i;
    this.mesh.instanceMatrix.needsUpdate = true;
    if (this.mesh.instanceColor) this.mesh.instanceColor.needsUpdate = true;
  }

  /** True when the player is standing inside a refuge — used for the HUD. */
  static inRefuge() { return sanctuaryOf(player.x, player.z, 0) !== null; }
}
