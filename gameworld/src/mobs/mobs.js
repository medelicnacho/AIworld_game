// D7 — the mob layer. Soulless, but not player-centric.
//
// The shape is borrowed from the lab's `world/sim.py _drift_positions()`: bodies are held
// by their own PLACE and their own KIN, not by the player. A mob belongs to a pack with a
// home; it mills, flocks and BREEDS there. You are an interruption, not the centre of its
// world — it notices you at short range, or when you hurt one of its own, and it goes home
// when you leave. That is the difference between creatures living in a world and a spawner
// orbiting the camera.
//
// Sockets 2 and 3 in practice: every mob's SIM record lives in state.js (plain data,
// region-bucketed); the meshes here only READ those records. At Stage 3 a settlement soul
// drives this same locomotion layer with a substrate brain, and none of it has to change.

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
    this.packs = new Map();           // packId -> {x, z}
    this.nextPack = 1;
    this.spawnTimer = 0;
    this.geo = new THREE.ConeGeometry(MOB.radius, 1.6, 5);
    this.geo.translate(0, 0.8, 0);    // pivot at the feet, so ground-snapping is exact
    this.killed = 0;
    this.born = 0;
  }

  /** Roll one mob's stats from the tier it stands in (D8). */
  rollStats(x, z) {
    const ring = tierAt(x, z);
    const elite = this.rng() < MOB.eliteChance + MOB.eliteChancePerRing * ring;
    const eliteHp = MOB.eliteHp + MOB.eliteHpPerRing * ring;
    const hp = MOB.hp * (1 + MOB.hpPerRing * ring) * (elite ? eliteHp : 1);
    return {
      ring, elite, maxHp: hp, hp,
      damage: MOB.damage * (1 + MOB.damagePerRing * ring) * (elite ? MOB.eliteDamage : 1),
      speed: MOB.speed * (1 + MOB.speedPerRing * ring),
    };
  }

  /** Population budget where the player is standing — denser the further out you are. */
  budget() {
    const tier = tierAt(player.x, player.z);
    return {
      alive: Math.min(MOB.maxAliveCap, MOB.maxAlive + MOB.maxAlivePerTier * tier),
      packs: Math.min(MOB.maxPacksCap, MOB.maxPacks + MOB.maxPacksPerTier * tier),
    };
  }

  breedDelay() {
    const [lo, hi] = MOB.breedEvery;
    return lo + this.rng() * (hi - lo);
  }

  spawnOne(x, z, packId, homeX, homeZ) {
    const s = this.rollStats(x, z);
    const e = addEntity({
      kind: "mob", x, y: groundY(x, z), z,
      ...s,
      pack: packId, homeX, homeZ,
      aggro: false, aggroT: 0,
      atkCd: this.rng() * MOB.attackCd,
      lungeT: 0, hurtT: 0,
      bias: this.rng() < 0.5 ? -1 : 1,
      // A stable angular slot on the ring around a target, so a pack fans out to surround
      // rather than queueing behind whoever arrived first.
      slot: (this.rng() - 0.5) * MOB.slotSpread,
      heading: this.rng() * Math.PI * 2,
      wobble: this.rng() * Math.PI * 2,
      bold: false,
      breedCd: this.breedDelay(),
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

  /** A camp: several mobs sharing a home they return to and breed at. */
  spawnPack() {
    const a = this.rng() * Math.PI * 2;
    const d = MOB.spawnMin + this.rng() * (MOB.spawnMax - MOB.spawnMin);
    const hx = player.x + Math.cos(a) * d;
    const hz = player.z + Math.sin(a) * d;
    const id = this.nextPack++;
    this.packs.set(id, { x: hx, z: hz });

    const [lo, hi] = MOB.packSize;
    const n = lo + Math.floor(this.rng() * (hi - lo + 1));
    for (let i = 0; i < n; i++) {
      const ang = this.rng() * Math.PI * 2;
      const r = this.rng() * MOB.homeWander;
      this.spawnOne(hx + Math.cos(ang) * r, hz + Math.sin(ang) * r, id, hx, hz);
    }
    return id;
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

  *entities() {
    for (const e of world.entities.values()) if (e.kind === "mob") yield e;
  }

  targets() {
    const out = [];
    for (const e of this.entities()) {
      out.push({ id: e.id, x: e.x, y: e.y + 0.8, z: e.z,
                 r: MOB.radius * (e.elite ? MOB.eliteScale : 1) });
    }
    return out;
  }

  packCount(id) {
    let n = 0;
    for (const e of this.entities()) if (e.pack === id) n++;
    return n;
  }

  /**
   * Something happened to this one, and the neighbourhood notices. Kin come from further
   * (they were watching each other anyway); strangers react only if they're close.
   *
   * Deliberately ONE HOP — the alerted don't re-alert. Chaining would cascade a single
   * opening shot across every camp in earshot, which is a stampede, not a reaction.
   */
  alert(e) {
    for (const o of nearby(e.x, e.z, MOB.alertRadius)) {
      if (o.kind !== "mob" || o === e) continue;
      const reach = o.pack === e.pack ? MOB.alertRadius : MOB.alertOthers;
      if (Math.hypot(o.x - e.x, o.z - e.z) > reach) continue;
      o.aggro = true;
      o.aggroT = MOB.loseInterest;
    }
  }

  hit(id, amount) {
    const e = world.entities.get(id);
    if (!e) return null;
    e.hp -= amount;
    e.hurtT = HURT_FLASH;
    e.aggro = true;
    e.aggroT = MOB.loseInterest;
    this.alert(e);                    // being shot at is a pack-wide event
    if (e.hp <= 0) {
      const out = { killed: true, elite: e.elite, ring: e.ring };
      this.despawn(id);
      this.killed++;
      return out;
    }
    return { killed: false, elite: e.elite, ring: e.ring };
  }

  neighbours(e) {
    const out = [];
    for (const o of nearby(e.x, e.z, MOB.neighborRadius)) {
      if (o === e || o.kind !== "mob") continue;
      const d = Math.hypot(o.x - e.x, o.z - e.z);
      if (d < MOB.neighborRadius) out.push({ o, d });
    }
    return out;
  }

  /**
   * Terrain-aware move. A heightfield has no obstacles except STEEPNESS, so "pathing" here
   * means refusing to walk up a cliff and veering along it — which reads as following
   * contours and funnelling through passes, with no navmesh existing anywhere.
   */
  tryMove(e, vx, vz, dt) {
    if (Math.hypot(vx, vz) < 1e-4) return;
    const here = groundY(e.x, e.z);
    for (const turn of [0, MOB.avoidArc * 0.5, -MOB.avoidArc * 0.5, MOB.avoidArc,
                        -MOB.avoidArc, MOB.avoidArc * 1.6, -MOB.avoidArc * 1.6]) {
      const c = Math.cos(turn), s = Math.sin(turn);
      const dx = (vx * c - vz * s) * dt;
      const dz = (vx * s + vz * c) * dt;
      if (groundY(e.x + dx, e.z + dz) - here <= MOB.maxClimb) {
        e.x += dx; e.z += dz;
        e.heading = Math.atan2(dx, dz);
        return;
      }
    }
    // Walled in on every heading — hold rather than climb.
  }

  update(dt, onPlayerHit) {
    let alive = 0;
    for (const _ of this.entities()) alive++;   // eslint-disable-line no-unused-vars

    const cap = this.budget();
    this.spawnTimer -= dt;
    if (alive < cap.alive && this.packs.size < cap.packs && this.spawnTimer <= 0) {
      this.spawnTimer = MOB.spawnInterval;
      this.spawnPack();
    }

    const lunged = [];
    const babies = [];
    const seenPacks = new Set();

    for (const e of nearby(player.x, player.z, MOB.despawn)) {
      if (e.kind !== "mob") continue;
      seenPacks.add(e.pack);

      const dx = player.x - e.x, dz = player.z - e.z;
      const dist = Math.hypot(dx, dz) || 1;
      if (dist > MOB.despawn) { this.despawn(e.id); continue; }

      if (e.hurtT > 0) e.hurtT -= dt;
      if (e.atkCd > 0) e.atkCd -= dt;

      const ux = dx / dist, uz = dz / dist;
      const homeD = Math.hypot(e.x - e.homeX, e.z - e.homeZ) || 0.001;

      // --- attention: do you matter to this creature right now? --------------------
      if (e.aggro) {
        e.aggroT -= dt;
        if (dist < MOB.noticeRange) e.aggroT = MOB.loseInterest;   // contact refreshes it
        // The leash is on HOME, not on you. Run far enough and they turn back — they have
        // somewhere to be, and it isn't wherever you happen to be standing.
        if (homeD > MOB.leashRange || e.aggroT <= 0) e.aggro = false;
      } else if (dist < MOB.noticeRange) {
        e.aggro = true;
        e.aggroT = MOB.loseInterest;
        this.alert(e);
      }

      // --- the lunge is committed and unsteered ------------------------------------
      if (e.lungeT > 0) {
        e.lungeT -= dt;
        e.x += e.lx * MOB.lungeSpeed * dt;
        e.z += e.lz * MOB.lungeSpeed * dt;
        if (dist < MOB.attackRange && player.iframes <= 0) {
          e.lungeT = 0;
          onPlayerHit?.(e);
        }
        e.y = groundY(e.x, e.z);
        reindex(e);
        this.sync(e, ux, uz);
        continue;
      }

      // --- flocking, which applies whether hunting or at home -----------------------
      const near = this.neighbours(e);
      let sepX = 0, sepZ = 0, aliX = 0, aliZ = 0, cohX = 0, cohZ = 0;
      for (const { o, d } of near) {
        if (d < MOB.separation) {
          const w = (MOB.separation - d) / MOB.separation;
          sepX += ((e.x - o.x) / (d || 1)) * w;
          sepZ += ((e.z - o.z) / (d || 1)) * w;
        }
        if (o.heading !== undefined) { aliX += Math.cos(o.heading); aliZ += Math.sin(o.heading); }
        cohX += o.x - e.x;
        cohZ += o.z - e.z;
      }
      if (near.length) {
        aliX /= near.length; aliZ /= near.length;
        cohX /= near.length * 12; cohZ /= near.length * 12;
      }

      let vx = 0, vz = 0;

      if (e.aggro) {
        e.bold = near.length + 1 >= MOB.packCourage;

        // Steer to a SLOT on a ring around you rather than at your feet: a pack fans out
        // and surrounds. Timid ones hold further back and circle instead of closing.
        const ang = Math.atan2(-dz, -dx) + e.slot + (e.bold ? 0 : e.bias * 0.35);
        const standoff = e.bold ? MOB.ringRadius : MOB.timidStandoff;
        const tx = player.x + Math.cos(ang) * standoff;
        const tz = player.z + Math.sin(ang) * standoff;
        const rd = Math.hypot(tx - e.x, tz - e.z) || 1;
        vx += ((tx - e.x) / rd) * MOB.ringForce;
        vz += ((tz - e.z) / rd) * MOB.ringForce;

        if (e.bold && dist > MOB.attackRange * 1.4) { vx += ux * 0.9; vz += uz * 0.9; }

        if (e.bold && dist <= MOB.attackRange * 1.7 && e.atkCd <= 0) {
          e.lungeT = MOB.lungeTime;
          e.lx = ux; e.lz = uz;
          e.atkCd = MOB.attackCd;
          lunged.push(e);
        } else if (dist <= MOB.attackRange * 1.7) {
          vx += -uz * e.bias * 0.9;
          vz += ux * e.bias * 0.9;
        }
      } else {
        // --- at home: their own lives ---------------------------------------------
        e.bold = false;
        if (homeD > MOB.homeWander) {
          vx += ((e.homeX - e.x) / homeD) * MOB.homePull;
          vz += ((e.homeZ - e.z) / homeD) * MOB.homePull;
        }
        e.wobble += dt * 0.5;
        vx += Math.cos(e.wobble) * 0.55;
        vz += Math.sin(e.wobble) * 0.55;

        // BREEDING, mirroring the lab's _breed(): only in peace, only with kin nearby, and
        // only while the camp has room. Leave a pack alone and you'll come back to a bigger
        // one — which gives clearing a camp a shelf life.
        e.breedCd -= dt;
        if (e.breedCd <= 0) {
          e.breedCd = this.breedDelay();
          const kin = near.filter(({ o }) => o.pack === e.pack).length;
          if (kin >= 1 && this.packCount(e.pack) < MOB.packCap
              && alive + babies.length < cap.alive) {
            babies.push(e);
          }
        }
      }

      vx += sepX * MOB.sepForce + aliX * MOB.alignForce + cohX * MOB.cohesionForce;
      vz += sepZ * MOB.sepForce + aliZ * MOB.alignForce + cohZ * MOB.cohesionForce;

      // Normalise so the forces set DIRECTION, not pace. Idling is a stroll; hunting isn't.
      const m = Math.hypot(vx, vz);
      if (m > 1e-4) {
        const pace = e.aggro ? e.speed : e.speed * 0.42;
        vx = (vx / m) * pace;
        vz = (vz / m) * pace;
      }

      this.tryMove(e, vx, vz, dt);
      e.y = groundY(e.x, e.z);
      reindex(e);
      this.sync(e, ux, uz);
    }

    // AGGRESSION CONTAGION: one committing pulls its neighbours in behind it, so a pack
    // attacks in ragged waves rather than on independent timers. Nothing scripts the wave.
    for (const e of lunged) {
      for (const { o } of this.neighbours(e)) {
        if (o.lungeT <= 0 && o.atkCd > 0.3 && this.rng() < MOB.contagion) {
          o.atkCd = 0.15 + this.rng() * 0.3;
        }
      }
    }

    for (const parent of babies) {
      const ang = this.rng() * Math.PI * 2;
      this.spawnOne(parent.x + Math.cos(ang) * 1.6, parent.z + Math.sin(ang) * 1.6,
                    parent.pack, parent.homeX, parent.homeZ);
      this.born++;
    }

    // Forget packs that are wiped out or left behind, so new camps can form.
    for (const id of [...this.packs.keys()]) {
      if (!seenPacks.has(id) && this.packCount(id) === 0) this.packs.delete(id);
    }
  }

  sync(e, ux, uz) {
    const mesh = this.meshes.get(e.id);
    if (!mesh) return;
    mesh.position.set(e.x, e.y, e.z);
    mesh.rotation.y = e.aggro ? Math.atan2(ux, uz) : e.heading;
    mesh.material.emissive.setHex(e.hurtT > 0 ? 0xff5544 : 0x000000);
  }
}
