// D7 — the mob layer. Soulless on purpose: stats, a three-state brain, and nothing else.
//
// This is where sockets 2 and 3 stop being theoretical. Every mob's SIM record lives in
// state.js (plain data, region-bucketed); the meshes here are a separate layer that only
// READS those records. At M3 a settlement soul plugs into the same body interface with a
// substrate brain instead of `think()` — and none of the rendering below has to change.

import * as THREE from "three";
import { MOB } from "../config.js";
import { player } from "../state.js";
import { addEntity, removeEntity, reindex, world, nearby } from "../state.js";
import { groundY, tierAt } from "../world/gen.js";
import { mulberry32 } from "../rng.js";

const HURT_FLASH = 0.12;

export class Mobs {
  constructor(scene, seed = 0x5EED) {
    this.scene = scene;
    this.rng = mulberry32(seed);
    this.meshes = new Map();          // entity id -> THREE.Mesh
    this.spawnTimer = 0;
    this.geo = new THREE.ConeGeometry(MOB.radius, 1.6, 5);
    this.geo.translate(0, 0.8, 0);    // pivot at the feet, so ground-snapping is exact
    this.killed = 0;
  }

  /** Roll one mob's stats from the ring it stands in (D8). */
  rollStats(x, z) {
    const ring = tierAt(x, z);
    const elite = this.rng() < MOB.eliteChance + MOB.eliteChancePerRing * ring;
    const eliteHp = MOB.eliteHp + MOB.eliteHpPerRing * ring;
    const hp = MOB.hp * (1 + MOB.hpPerRing * ring) * (elite ? eliteHp : 1);
    return {
      ring,
      elite,
      maxHp: hp,
      hp,
      damage: MOB.damage * (1 + MOB.damagePerRing * ring) * (elite ? MOB.eliteDamage : 1),
      speed: MOB.speed * (1 + MOB.speedPerRing * ring),
    };
  }

  spawn() {
    const a = this.rng() * Math.PI * 2;
    const d = MOB.spawnMin + this.rng() * (MOB.spawnMax - MOB.spawnMin);
    const x = player.x + Math.cos(a) * d;
    const z = player.z + Math.sin(a) * d;
    const s = this.rollStats(x, z);

    const e = addEntity({
      kind: "mob", x, y: groundY(x, z), z,
      ...s,
      state: "chase",
      atkCd: this.rng() * MOB.attackCd,
      lungeT: 0,
      hurtT: 0,
      // A per-mob strafe bias keeps a pack from collapsing into one stacked column.
      bias: this.rng() < 0.5 ? -1 : 1,
      wobble: this.rng() * Math.PI * 2,
    });

    const mesh = new THREE.Mesh(this.geo, new THREE.MeshLambertMaterial({
      color: s.elite ? 0xe8c14a : 0x8d4d63,
      emissive: 0x000000,
    }));
    if (s.elite) mesh.scale.setScalar(MOB.eliteScale);
    mesh.position.set(x, e.y, z);
    this.scene.add(mesh);
    this.meshes.set(e.id, mesh);
    return e;
  }

  despawn(id) {
    const mesh = this.meshes.get(id);
    if (mesh) {
      this.scene.remove(mesh);
      mesh.material.dispose();
      this.meshes.delete(id);
    }
    removeEntity(id);
  }

  /** Live mob records — read-only consumers like the minimap iterate this. */
  *entities() {
    for (const e of world.entities.values()) if (e.kind === "mob") yield e;
  }

  /** Ray-hittable targets for the gun. Kept generic so gun.js never imports mobs. */
  targets() {
    const out = [];
    for (const e of world.entities.values()) {
      if (e.kind !== "mob") continue;
      out.push({ id: e.id, x: e.x, y: e.y + 0.8, z: e.z, r: MOB.radius * (e.elite ? MOB.eliteScale : 1) });
    }
    return out;
  }

  /** @returns {{killed:boolean, elite:boolean, ring:number}|null} */
  hit(id, amount) {
    const e = world.entities.get(id);
    if (!e) return null;
    e.hp -= amount;
    e.hurtT = HURT_FLASH;
    if (e.hp <= 0) {
      const out = { killed: true, elite: e.elite, ring: e.ring };
      this.despawn(id);
      this.killed++;
      return out;
    }
    return { killed: false, elite: e.elite, ring: e.ring };
  }

  update(dt, onPlayerHit) {
    // --- population --------------------------------------------------------------
    let alive = 0;
    for (const e of world.entities.values()) if (e.kind === "mob") alive++;

    this.spawnTimer -= dt;
    if (alive < MOB.maxAlive && this.spawnTimer <= 0) {
      this.spawnTimer = MOB.spawnInterval;
      this.spawn();
    }

    // --- brains ------------------------------------------------------------------
    // Region-bucketed iteration (socket 3): only mobs in regions near the player are
    // considered. At M1 scale that's the whole set, but the shape is what matters —
    // it's the same traversal a settlement Worker will use at M3.
    for (const e of nearby(player.x, player.z, MOB.despawn)) {
      if (e.kind !== "mob") continue;

      const dx = player.x - e.x, dz = player.z - e.z;
      const dist = Math.hypot(dx, dz) || 1;

      if (dist > MOB.despawn) { this.despawn(e.id); continue; }

      if (e.hurtT > 0) e.hurtT -= dt;
      if (e.atkCd > 0) e.atkCd -= dt;

      const ux = dx / dist, uz = dz / dist;
      let vx = 0, vz = 0;

      if (e.lungeT > 0) {
        // LUNGE — committed, like the player's dodge. It can't course-correct mid-lunge,
        // which is precisely what makes dodging one feel like a read rather than a coin flip.
        e.lungeT -= dt;
        vx = e.lx * MOB.lungeSpeed;
        vz = e.lz * MOB.lungeSpeed;

        if (dist < MOB.attackRange && player.iframes <= 0) {
          e.lungeT = 0;
          onPlayerHit?.(e);
        }
      } else if (dist > MOB.aggroRange) {
        // IDLE — drift, unaware.
        e.wobble += dt * 0.6;
        vx = Math.cos(e.wobble) * 0.5;
        vz = Math.sin(e.wobble) * 0.5;
      } else if (dist > MOB.attackRange * 1.6) {
        // CHASE — close, with a sideways bias so a pack arrives as a spread, not a stack.
        vx = (ux + -uz * 0.35 * e.bias) * e.speed;
        vz = (uz + ux * 0.35 * e.bias) * e.speed;
      } else if (e.atkCd <= 0) {
        e.lungeT = MOB.lungeTime;
        e.lx = ux; e.lz = uz;
        e.atkCd = MOB.attackCd;
        e.state = "lunge";
      } else {
        // STRAFE — circle while the attack cools. This is the window the player shoots into.
        vx = -uz * e.bias * e.speed * 0.75;
        vz = ux * e.bias * e.speed * 0.75;
      }

      e.x += vx * dt;
      e.z += vz * dt;
      // Ground-snap rather than pathfind: mobs walk the heightfield. Cheap and robust; real
      // navigation arrives with yuka at M3, when souls need to path around each other.
      e.y = groundY(e.x, e.z);
      reindex(e);

      const mesh = this.meshes.get(e.id);
      if (mesh) {
        mesh.position.set(e.x, e.y, e.z);
        mesh.rotation.y = Math.atan2(ux, uz);
        mesh.material.emissive.setHex(e.hurtT > 0 ? 0xff5544 : 0x000000);
      }
    }
  }
}
