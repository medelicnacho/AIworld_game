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
import { MOB, PLAYER } from "../config.js";
import { player } from "../state.js";
import { addEntity, removeEntity, reindex, world, nearby } from "../state.js";
import { groundY, solidAt, tierAt } from "../world/gen.js";
import { sfx } from "../audio/sfx.js";
import { sanctuaryOf } from "../world/sanctuary.js";
import { mulberry32 } from "../rng.js";

const HURT_FLASH = 0.12;

export class Mobs {
  constructor(scene, seed = 0x5EED) {
    this.scene = scene;
    this.rng = mulberry32(seed);
    this.packs = new Map();           // packId -> {x, z}
    this.nextPack = 1;
    this.spawnTimer = 0;
    this.killed = 0;
    this.born = 0;

    // ONE draw call for every mob alive. Individual meshes cost a draw call each, and this
    // machine has no discrete GPU — at 200 bodies that overhead is the whole frame budget.
    // Instancing makes population a simulation question rather than a rendering one.
    this.geo = new THREE.ConeGeometry(MOB.radius, 1.6, 5);
    this.geo.translate(0, 0.8, 0);    // pivot at the feet, so ground-snapping is exact
    this.mesh = new THREE.InstancedMesh(
      this.geo, new THREE.MeshLambertMaterial({}), MOB.maxAliveCap + 32);
    this.mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    this.mesh.frustumCulled = false;  // instances move every frame; the bounds would lie
    this.mesh.count = 0;
    scene.add(this.mesh);

    // Scratch objects, reused every frame — allocating per mob per frame is exactly the
    // GC sawtooth that ruins frame times at these counts.
    this._m = new THREE.Matrix4();
    this._q = new THREE.Quaternion();
    this._p = new THREE.Vector3();
    this._s = new THREE.Vector3();
    this._c = new THREE.Color();
    this._up = new THREE.Vector3(0, 1, 0);
    this._flip = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), Math.PI);
    this.COL_MOB = new THREE.Color(0x8d4d63);
    this.COL_ELITE = new THREE.Color(0xe8c14a);
    this.COL_CASTER = new THREE.Color(0xd11f1f);   // red: airborne ranged
    this.COL_GROUNDCASTER = new THREE.Color(0x8a3fd1);   // violet: ranged, but grounded
    this.COL_CHARGING = new THREE.Color(0xff8a3c);  // hot while winding up — the telegraph
    this.COL_HURT = new THREE.Color(0xff6655);

    // Fireballs, pooled. Slow and straight, so they're a movement problem, not a DPS race.
    this.ballGeo = new THREE.IcosahedronGeometry(0.42, 1);
    this.ballMat = new THREE.MeshBasicMaterial({ color: 0xff7326 });
    this.balls = [];
    for (let i = 0; i < MOB.ballPool; i++) {
      const mesh = new THREE.Mesh(this.ballGeo, this.ballMat);
      mesh.visible = false;
      scene.add(mesh);
      this.balls.push({ mesh, active: false, x: 0, y: 0, z: 0, vx: 0, vy: 0, vz: 0, t: 0, dmg: 0 });
    }
  }

  /** Write every live mob into the instance buffer. One pass, one draw call. */
  render() {
    let i = 0;
    const cap = this.mesh.instanceMatrix.count;
    for (const e of this.entities()) {
      if (i >= cap) break;
      const sc = e.elite ? MOB.eliteScale : 1;
      this._q.setFromAxisAngle(this._up, e.facing ?? e.heading ?? 0);
      // Flyers hang point-down, so a threat in the air is a different silhouette from a
      // threat on the ground even before you read its colour.
      if (e.flies) this._q.multiply(this._flip);
      this._m.compose(this._p.set(e.x, e.y, e.z), this._q, this._s.set(sc, sc, sc));
      this.mesh.setMatrixAt(i, this._m);
      this.mesh.setColorAt(i,
        e.hurtT > 0 ? this.COL_HURT
          : e.castT > 0 ? this.COL_CHARGING
            : e.flies ? this.COL_CASTER
              : e.caster ? this.COL_GROUNDCASTER
                : e.elite ? this.COL_ELITE : this.COL_MOB);
      i++;
    }
    this.mesh.count = i;
    this.mesh.instanceMatrix.needsUpdate = true;
    if (this.mesh.instanceColor) this.mesh.instanceColor.needsUpdate = true;
  }

  /** Roll one mob's stats from the tier it stands in (D8). */
  rollStats(x, z) {
    const ring = tierAt(x, z);
    const elite = this.rng() < MOB.eliteChance + MOB.eliteChancePerRing * ring;
    const eliteHp = MOB.eliteHp + MOB.eliteHpPerRing * ring;
    const hp = MOB.hp * Math.pow(MOB.hpGrowth, ring) * (elite ? eliteHp : 1);
    // Ranged comes in two flavours. Elite casters FLY (red, point-down); ordinary ones
    // hold their ground (violet). Same standoff brain, entirely different problem: one you
    // must look up for, the other closes the horizontal gap with you.
    let caster = false, flies = false;
    if (elite) {
      caster = this.rng() < MOB.casterChance;
      if (caster) flies = this.rng() < MOB.flyChance;
    } else {
      caster = this.rng() < MOB.groundCasterChance;
    }
    return {
      ring, elite, caster, flies,
      maxHp: hp, hp,
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

  /** Where this body sits vertically: on the ground, or hovering above it. */
  restY(e) {
    const g = groundY(e.x, e.z);
    return e.flies ? g + MOB.flyHeight + Math.sin(e.wobble * 1.6) * MOB.flyBob : g;
  }

  breedDelay() {
    const [lo, hi] = MOB.breedEvery;
    return lo + this.rng() * (hi - lo);
  }

  spawnOne(x, z, packId, homeX, homeZ) {
    const s = this.rollStats(x, z);
    const e = addEntity({
      kind: "mob", x, z,
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
      facing: 0,
      kx: 0, kz: 0, kT: 0,
      castT: 0, castCd: 1.5 + this.rng() * MOB.castCd,
      breedCd: this.breedDelay(),
      y: 0,
    });
    e.y = this.restY(e);
    return e;
  }

  /** A camp: several mobs sharing a home they return to and breed at. */
  spawnPack() {
    const a = this.rng() * Math.PI * 2;
    const d = MOB.spawnMin + this.rng() * (MOB.spawnMax - MOB.spawnMin);
    const hx = player.x + Math.cos(a) * d;
    const hz = player.z + Math.sin(a) * d;
    // Never make camp on holy ground — a refuge you have to clear isn't a refuge.
    if (sanctuaryOf(hx, hz, MOB.homeWander + 14)) return null;
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
    removeEntity(id);   // the instance buffer is rebuilt each frame; nothing to free
  }

  *entities() {
    for (const e of world.entities.values()) if (e.kind === "mob") yield e;
  }

  targets() {
    const out = [];
    for (const e of this.entities()) {
      const sc = e.elite ? MOB.eliteScale : 1;
      if (e.flies) {
        // Flyers hang POINT-DOWN, so their body occupies the space BELOW the entity origin
        // — the old sphere at +0.8 sat in empty air above the model, which is why shots
        // that visibly connected did nothing. Two spheres cover the hanging body properly,
        // and they're generous, because hitting a small drifting target while it shoots at
        // you is meant to be the challenge, not reading its exact silhouette.
        const r = MOB.radius * sc * MOB.flyHitScale;
        out.push({ id: e.id, x: e.x, y: e.y - 0.35, z: e.z, r });
        out.push({ id: e.id, x: e.x, y: e.y - 1.25, z: e.z, r: r * 0.85 });
      } else {
        out.push({ id: e.id, x: e.x, y: e.y + 0.8, z: e.z, r: MOB.radius * sc });
      }
    }
    return out;
  }

  /** Is anything actively hunting the player within `range`? Regen reads this. */
  anyHunting(range = 55) {
    for (const e of nearby(player.x, player.z, range)) {
      if (e.kind !== "mob" || !e.aggro) continue;
      if (Math.hypot(e.x - player.x, e.z - player.z) < range) return true;
    }
    return false;
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

  /** Shove a mob outward from a point. Survivors get thrown; the dead do not care. */
  push(e, fromX, fromZ, force) {
    const dx = e.x - fromX, dz = e.z - fromZ;
    const d = Math.hypot(dx, dz) || 1;
    e.kx = (dx / d) * force;
    e.kz = (dz / d) * force;
    e.kT = MOB.knockTime;
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
    // Hostiles cannot enter a sanctuary AT ALL — not blocked by the wall, barred from the
    // ground. The wall makes it read as a refuge; this makes it be one. A safe zone that
    // leaks through the gateway would be worse than none, because you'd stop trusting it.
    const ward = sanctuaryOf(e.x, e.z, 2) ? null : true;
    for (const turn of [0, MOB.avoidArc * 0.5, -MOB.avoidArc * 0.5, MOB.avoidArc,
                        -MOB.avoidArc, MOB.avoidArc * 1.6, -MOB.avoidArc * 1.6]) {
      const c = Math.cos(turn), s = Math.sin(turn);
      const dx = (vx * c - vz * s) * dt;
      const dz = (vx * s + vz * c) * dt;
      if (groundY(e.x + dx, e.z + dz) - here <= MOB.maxClimb
          && !(ward && sanctuaryOf(e.x + dx, e.z + dz, 1.5))) {
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
    // Standing on holy ground ends the hunt. Computed once: sanctuaryOf() is memoised but
    // it is still a per-frame question, not a per-mob one.
    const playerSafe = sanctuaryOf(player.x, player.z, 0) !== null;

    for (const e of nearby(player.x, player.z, MOB.despawn)) {
      if (e.kind !== "mob") continue;
      seenPacks.add(e.pack);

      const dx = player.x - e.x, dz = player.z - e.z;
      const dist = Math.hypot(dx, dz) || 1;
      if (dist > MOB.despawn) { this.despawn(e.id); continue; }

      if (e.hurtT > 0) e.hurtT -= dt;
      if (e.atkCd > 0) e.atkCd -= dt;
      if (e.flies) e.wobble += dt;       // the hover bob, independent of any wandering

      const ux = dx / dist, uz = dz / dist;
      const homeD = Math.hypot(e.x - e.homeX, e.z - e.homeZ) || 0.001;

      // If one is somehow inside anyway — a shape changed under it, a knockback, a bug I
      // haven't found — evict it rather than leaving a hostile loose in a safe zone. The
      // polygon is star-shaped, so straight out from the centre always leaves.
      const inside = sanctuaryOf(e.x, e.z, 0);
      if (inside) {
        const ox = e.x - inside.x, oz = e.z - inside.z;
        const od = Math.hypot(ox, oz) || 1;
        e.x += (ox / od) * MOB.speed * 2.5 * dt;
        e.z += (oz / od) * MOB.speed * 2.5 * dt;
        e.y = this.restY(e);
        e.aggro = false;
        e.lungeT = 0;
        reindex(e);
        this.sync(e, ux, uz);
        continue;
      }

      // --- attention: do you matter to this creature right now? --------------------
      // A refuge is a refuge. They give up at the threshold and go home rather than
      // loitering at the gate waiting for you to step out.
      if (playerSafe) { e.aggro = false; e.aggroT = 0; e.lungeT = 0; }

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

      // Being thrown overrides everything: no steering, no lunging, just flying.
      if (e.kT > 0) {
        e.kT -= dt;
        const f = Math.max(0, e.kT / MOB.knockTime);
        e.x += e.kx * f * dt;
        e.z += e.kz * f * dt;
        e.lungeT = 0;
        e.y = this.restY(e);
        reindex(e);
        this.sync(e, ux, uz);
        continue;
      }

      // --- the lunge is committed and unsteered ------------------------------------
      if (e.lungeT > 0) {
        e.lungeT -= dt;
        // The lunge writes position DIRECTLY — it deliberately skips steering so it can't
        // course-correct. That also meant it skipped the sanctuary ward, which is how mobs
        // were getting inside: they committed from outside and flew straight through.
        const lx = e.x + e.lx * MOB.lungeSpeed * dt;
        const lz = e.z + e.lz * MOB.lungeSpeed * dt;
        if (sanctuaryOf(lx, lz, 1.5)) {
          e.lungeT = 0;                       // stopped at the wall
        } else {
          e.x = lx;
          e.z = lz;
        }
        if (dist < MOB.attackRange && player.iframes <= 0) {
          e.lungeT = 0;
          onPlayerHit?.(e);
        }
        e.y = this.restY(e);
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

      if (e.aggro && e.caster) {
        // CASTER: hold the middle distance and throw. Never lunges, never brawls.
        e.bold = false;
        if (e.castT > 0) {
          // Winding up: rooted and glowing. Standing still IS the tell.
          e.castT -= dt;
          if (e.castT <= 0) {
            this.fire(e);
            e.castCd = MOB.castCd;
          }
        } else {
          if (e.castCd > 0) e.castCd -= dt;
          if (e.castCd <= 0 && dist > MOB.castMin && dist < MOB.castMax) e.castT = MOB.castWindup;

          // Keep the range band: back off when crowded, close when you've drifted too far.
          const want = dist < MOB.castMin ? -1 : dist > MOB.castMax * 0.75 ? 1 : 0;
          vx += ux * want * 1.4;
          vz += uz * want * 1.4;
          vx += -uz * e.bias * 0.6;      // and drift sideways so they're not static targets
          vz += ux * e.bias * 0.6;
        }
      } else if (e.aggro) {
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

      if (e.castT > 0) { vx = 0; vz = 0; }    // rooted mid-cast

      vx += sepX * MOB.sepForce + aliX * MOB.alignForce + cohX * MOB.cohesionForce;
      vz += sepZ * MOB.sepForce + aliZ * MOB.alignForce + cohZ * MOB.cohesionForce;

      // Normalise so the forces set DIRECTION, not pace. Idling is a stroll; hunting isn't.
      const m = Math.hypot(vx, vz);
      if (m > 1e-4) {
        const pace = e.aggro ? e.speed : e.speed * 0.42;
        vx = (vx / m) * pace;
        vz = (vz / m) * pace;
      }

      if (e.flies) {
        // Flight ignores terrain entirely — that IS the advantage. Sanctuaries still hold.
        const nx = e.x + vx * dt, nz = e.z + vz * dt;
        if (!sanctuaryOf(nx, nz, 1.5)) {
          e.x = nx; e.z = nz;
          if (Math.hypot(vx, vz) > 1e-4) e.heading = Math.atan2(vx * dt, vz * dt);
        }
      } else {
        this.tryMove(e, vx, vz, dt);
      }
      e.y = this.restY(e);
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

    this.updateBalls(dt, onPlayerHit);
    this.render();
  }

  /** Release a fireball at where the player is RIGHT NOW — no homing, so it's dodgeable. */
  fire(e) {
    const slot = this.balls.find((b) => !b.active);
    if (!slot) return;
    const sx = e.x, sy = e.y + (e.flies ? -0.6 : 1.1), sz = e.z;
    const dx = player.x - sx, dy = (player.y + 0.9) - sy, dz = player.z - sz;
    const d = Math.hypot(dx, dy, dz) || 1;
    slot.active = true;
    slot.x = sx; slot.y = sy; slot.z = sz;
    slot.vx = (dx / d) * MOB.ballSpeed;
    slot.vy = (dy / d) * MOB.ballSpeed;
    slot.vz = (dz / d) * MOB.ballSpeed;
    slot.t = MOB.ballLife;
    // Scales with tier like everything else, but off the BALL's base rather than the
    // caster's melee damage — a fireball is its own attack, not a reskinned bite.
    slot.dmg = MOB.ballDamage * (1 + MOB.damagePerRing * e.ring);
    slot.mesh.visible = true;
    slot.mesh.position.set(sx, sy, sz);
    sfx.cast(sx, sz);
  }

  updateBalls(dt, onPlayerHit) {
    for (const b of this.balls) {
      if (!b.active) continue;
      b.t -= dt;
      b.x += b.vx * dt; b.y += b.vy * dt; b.z += b.vz * dt;

      const hitPlayer = Math.hypot(player.x - b.x, (player.y + 0.9) - b.y, player.z - b.z)
        < MOB.ballRadius + PLAYER.radius;
      if (hitPlayer && player.iframes <= 0) {
        onPlayerHit?.({ damage: b.dmg, x: b.x, z: b.z });
        sfx.explosion(b.x, b.z, 0.4);
        b.active = false; b.mesh.visible = false;
        continue;
      }
      if (b.t <= 0 || solidAt(b.x, b.y, b.z) || sanctuaryOf(b.x, b.z, 0)) {
        if (b.t > 0) sfx.explosion(b.x, b.z, 0.35);
        b.active = false; b.mesh.visible = false;
        continue;
      }
      b.mesh.position.set(b.x, b.y, b.z);
      b.mesh.rotation.y += dt * 5;
    }
  }

  /** Face the player when hunting, face your heading when going about your business. */
  sync(e, ux, uz) {
    e.facing = e.aggro ? Math.atan2(ux, uz) : e.heading;
  }
}
