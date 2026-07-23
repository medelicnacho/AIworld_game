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
import { groundY, solidAt, tierAt, ringPressure } from "../world/gen.js";
import { sfx } from "../audio/sfx.js";
import { sanctuaryOf } from "../world/sanctuary.js";
import { guardNear } from "../town/guards.js";
import { mulberry32 } from "../rng.js";
import { AFFIXES, rollAffixes, runAffix, affixHidden, affixLabel } from "./affixes.js";

const HURT_FLASH = 0.12;

export class Mobs {
  constructor(scene, seed = 0x5EED, fx = {}) {
    this.scene = scene;
    // The few world verbs an affix may need. Injected, so affixes can reach blast() without
    // mobs.js importing main's damage routing and creating a cycle.
    this.fx = { mobs: this, ...fx };
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
    this.COL_CHARGER = new THREE.Color(0x6b4a2a);   // heavy brown: it comes at you
    this.COL_SWARM = new THREE.Color(0xc3d94a);     // pale: many, small, brief
    this.COL_HURT = new THREE.Color(0xff6655);
    this._affixCol = new THREE.Color();
    this._affixCache = new Map();     // affix id -> THREE.Color, built once

    // Dying bursts: a telegraph ring, then a bang. Pooled — a wiped elite pack can put
    // several in the air in the same second.
    const burstGeo = new THREE.RingGeometry(0.55, 1.0, 28);
    burstGeo.rotateX(-Math.PI / 2);
    this.bursts = [];
    for (let i = 0; i < 12; i++) {
      const mesh = new THREE.Mesh(burstGeo, new THREE.MeshBasicMaterial({
        color: 0xff3b30, transparent: true, opacity: 0, depthWrite: false,
        side: THREE.DoubleSide,
      }));
      mesh.visible = false;
      scene.add(mesh);
      this.bursts.push({ mesh, active: false, x: 0, z: 0, t: 0, dmg: 0, r: 0 });
    }

    // Burning ground. A big pool: one burner walking for ten seconds lays a dozen patches.
    const fireGeo = new THREE.CircleGeometry(1, 16);
    fireGeo.rotateX(-Math.PI / 2);
    this.fires = [];
    for (let i = 0; i < 110; i++) {
      const mesh = new THREE.Mesh(fireGeo, new THREE.MeshBasicMaterial({
        color: 0xff7a1e, transparent: true, opacity: 0, depthWrite: false,
        side: THREE.DoubleSide,
      }));
      mesh.visible = false;
      scene.add(mesh);
      this.fires.push({ mesh, active: false, x: 0, z: 0, t: 0, life: 1, dps: 0, r: 1 });
    }

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

  affixColor(id) {
    let c = this._affixCache.get(id);
    if (!c) {
      c = new THREE.Color(AFFIXES[id]?.color ?? 0xffffff);
      this._affixCache.set(id, c);
    }
    return c;
  }

  /**
   * One body, one colour. Priority: being hurt, then charging a cast, then AFFIXES, then
   * the base kind. With several affixes the tint cycles slowly between their hues rather
   * than blending them — a blend of orange and blue is just grey, and grey names nothing.
   */
  colorOf(e, now) {
    if (e.hurtT > 0) return this.COL_HURT;
    // Winding up to charge uses the SAME hot tell as a caster's wind-up: one colour for
    // "something is about to happen", learned once and read everywhere.
    if (e.castT > 0 || e.windT > 0) return this.COL_CHARGING;
    const n = e.affixes?.length || 0;
    if (n === 1) return this.affixColor(e.affixes[0]);
    if (n > 1) {
      const span = 0.9;                       // seconds per affix in the cycle
      const t = (now / (span * 1000)) % n;
      const a = this.affixColor(e.affixes[Math.floor(t)]);
      const b = this.affixColor(e.affixes[(Math.floor(t) + 1) % n]);
      const f = t % 1;
      // Hold each colour, then snap across quickly: readable as "orange AND blue", not mud.
      return this._affixCol.copy(a).lerp(b, Math.max(0, Math.min(1, (f - 0.75) * 4)));
    }
    if (e.flies) return this.COL_CASTER;
    if (e.caster) return this.COL_GROUNDCASTER;
    if (e.charger) return this.COL_CHARGER;
    if (e.swarm) return this.COL_SWARM;
    return e.elite ? this.COL_ELITE : this.COL_MOB;
  }

  /** Write every live mob into the instance buffer. One pass, one draw call. */
  render() {
    const now = performance.now();
    let i = 0;
    const cap = this.mesh.instanceMatrix.count;
    for (const e of this.entities()) {
      if (i >= cap) break;
      const sc = (e.elite ? MOB.eliteScale : 1) * (e.scale || 1);
      this._q.setFromAxisAngle(this._up, e.facing ?? e.heading ?? 0);
      // Flyers hang point-down, so a threat in the air is a different silhouette from a
      // threat on the ground even before you read its colour.
      if (e.flies) this._q.multiply(this._flip);
      this._m.compose(this._p.set(e.x, e.y, e.z), this._q, this._s.set(sc, sc, sc));
      this.mesh.setMatrixAt(i, this._m);
      this.mesh.setColorAt(i, this.colorOf(e, now));
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
    // Depth is felt HERE: the effective ring accelerates, so HP outruns a levelling player
    // the further out you go. Elites multiply on top, as before.
    const hp = MOB.hp * Math.pow(MOB.hpGrowth, ringPressure(ring, MOB.ramp)) * (elite ? eliteHp : 1);
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
    // A charger is an ordinary body that fights differently — never a caster, since
    // "closes the gap violently" and "refuses to close the gap" are opposite answers.
    const charger = !caster && !elite && this.rng() < MOB.chargerChance;
    return {
      ring, elite, caster, flies, charger,
      maxHp: hp, hp,
      damage: MOB.damage * (1 + MOB.damagePerRing * ringPressure(ring, MOB.rampDamage))
        * (elite ? MOB.eliteDamage : 1),
      speed: MOB.speed * (1 + MOB.speedPerRing * ring),
    };
  }

  /** Population budget where the player is standing — denser the further out you are. */
  budget() {
    const tier = tierAt(player.x, player.z);
    // Crowding accelerates too: the deep is not just meaner, it fills up and repopulates
    // faster, so "tuns of mobs" arrives well before the flat caps would have delivered it.
    const crowd = ringPressure(tier, MOB.rampCrowd);
    return {
      alive: Math.min(MOB.maxAliveCap, MOB.maxAlive + MOB.maxAlivePerTier * crowd),
      packs: Math.min(MOB.maxPacksCap, MOB.maxPacks + MOB.maxPacksPerTier * crowd),
      interval: Math.max(MOB.spawnIntervalMin,
        MOB.spawnInterval * Math.pow(1 - MOB.spawnFasterPerTier, crowd)),
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

  spawnOne(x, z, packId, homeX, homeZ, forceAffixes = null) {
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
      scale: 1,
      swarm: false,
      windT: 0, rushT: 0, recoverT: 0, rushX: 0, rushZ: 0,
      kx: 0, kz: 0, kT: 0,
      castT: 0, castCd: 1.5 + this.rng() * MOB.castCd,
      slowT: 0, slowMul: 1, rootT: 0,     // crowd control from player spells
      breedCd: this.breedDelay(),
      y: 0,
      affixes: [],
    });
    // Only stars carry affixes — an ordinary mob with a modifier reads as noise, and the
    // gold/scale tell is what makes "that one is different" legible at a distance.
    if (s.elite || forceAffixes) {
      e.affixes = rollAffixes(s.ring, this.rng, forceAffixes);
      runAffix(e, "onSpawn", this.fx);
    }
    e.y = this.restY(e);
    return e;
  }

  /** Turn a body into one of the little ones. */
  makeSwarm(e) {
    e.swarm = true;
    e.elite = false;
    e.caster = false;
    e.flies = false;
    e.charger = false;
    e.affixes = [];
    e.scale = MOB.swarmScale;
    e.maxHp = e.hp = e.maxHp * MOB.swarmHp;
    e.speed *= MOB.swarmSpeed;
    e.damage *= MOB.swarmDamage;
    e.y = this.restY(e);
    return e;
  }

  /** Drop a pack of a specific BREED next to the player, for testing. */
  spawnBreed(kind, n = 6) {
    const a = this.rng() * Math.PI * 2;
    const hx = player.x + Math.cos(a) * 26;
    const hz = player.z + Math.sin(a) * 26;
    if (sanctuaryOf(hx, hz, 20)) return false;
    const id = this.nextPack++;
    this.packs.set(id, { x: hx, z: hz });
    const count = kind === "swarm" ? 18 : n;
    for (let i = 0; i < count; i++) {
      const ang = this.rng() * Math.PI * 2;
      const e = this.spawnOne(hx + Math.cos(ang) * 5, hz + Math.sin(ang) * 5, id, hx, hz, []);
      if (kind === "swarm") this.makeSwarm(e);
      if (kind === "charger") { e.charger = true; e.caster = false; e.flies = false; }
    }
    return true;
  }

  /** Drop a pack right next to the player with exactly these affixes, for testing. */
  spawnPackWith(affixIds, n = 4) {
    const a = this.rng() * Math.PI * 2;
    const hx = player.x + Math.cos(a) * 26;
    const hz = player.z + Math.sin(a) * 26;
    if (sanctuaryOf(hx, hz, 20)) return false;
    const id = this.nextPack++;
    this.packs.set(id, { x: hx, z: hz });
    for (let i = 0; i < n; i++) {
      const ang = this.rng() * Math.PI * 2;
      const e = this.spawnOne(hx + Math.cos(ang) * 4, hz + Math.sin(ang) * 4,
                              id, hx, hz, affixIds);
      e.elite = true;                    // affixes ride on stars, so force the tell too
    }
    return true;
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

    // A camp is either ordinary or a SWARM — mixing them would blur the silhouette read,
    // and reading the camp before you engage it is the whole point of having breeds.
    const isSwarm = this.rng() < MOB.swarmPackChance;
    const [lo, hi] = isSwarm ? MOB.swarmSize : MOB.packSize;
    const n = lo + Math.floor(this.rng() * (hi - lo + 1));
    for (let i = 0; i < n; i++) {
      const ang = this.rng() * Math.PI * 2;
      const r = this.rng() * MOB.homeWander * (isSwarm ? 0.5 : 1);
      const e = this.spawnOne(hx + Math.cos(ang) * r, hz + Math.sin(ang) * r, id, hx, hz);
      if (isSwarm) this.makeSwarm(e);
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
      if (affixHidden(e)) continue;      // Phasing and anything like it
      const sc = (e.elite ? MOB.eliteScale : 1) * (e.scale || 1);
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
        // A floor on the hitbox: a swarm body is half-size, and a target you cannot
        // reliably click is frustration rather than difficulty.
        out.push({ id: e.id, x: e.x, y: e.y + 0.8 * sc, z: e.z,
                   r: Math.max(0.52, MOB.radius * sc) });
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

  // --- the world verbs affixes call through ctx.mobs ---------------------------
  // These are the whole reason affixes need a context at all. They were referenced by
  // affixes.js before they existed here, which is why Dying Burst threw on the first kill
  // and Burning silently did nothing at all.

  /** Dying Burst: mark the ground, then detonate on it. */
  queueBurst(x, z, dmg, radius, delay = 0.8) {
    const b = this.bursts.find((o) => !o.active);
    if (!b) return;
    Object.assign(b, { active: true, x, z, dmg, r: radius, t: delay, delay });
    b.mesh.position.set(x, groundY(x, z) + 0.06, z);
    b.mesh.scale.setScalar(radius);
    b.mesh.visible = true;
  }

  /**
   * Burning: lay a patch of fire that hurts to stand in.
   *
   * Spacing is measured against THIS MOB'S last drop rather than against every patch on the
   * map — a global test would mean two burners walking together laid one shared trail, and
   * a burner circling you kept landing in its own fire and skipping.
   */
  dropFire(e, dps, radius, life) {
    if (e.fireX !== undefined
        && Math.hypot(e.fireX - e.x, e.fireZ - e.z) < radius * 0.5) return;
    const f = this.fires.find((o) => !o.active);
    if (!f) return;
    e.fireX = e.x;
    e.fireZ = e.z;
    Object.assign(f, { active: true, x: e.x, z: e.z, dps, r: radius, t: life, life });
    f.mesh.position.set(e.x, groundY(e.x, e.z) + 0.05, e.z);
    f.mesh.scale.setScalar(radius);
    f.mesh.visible = true;
  }

  /**
   * Crowd-control every mob within `radius` of a point — a player spell's slow and/or root.
   * slowMul < 1 for a slow (0.5 = half speed); rootT > 0 pins them in place. Longest wins,
   * so a re-application never shortens what's already on them.
   */
  chill(x, z, radius, { slowT = 0, slowMul = 1, rootT = 0 } = {}) {
    for (const e of this.entities()) {
      if (Math.hypot(e.x - x, e.z - z) > radius) continue;
      if (slowT > e.slowT) { e.slowT = slowT; e.slowMul = slowMul; }
      if (rootT > e.rootT) e.rootT = rootT;
    }
  }

  /** Splitting: the kill is not the end. */
  spawnSplit(parent, n) {
    for (let i = 0; i < n; i++) {
      const a = (i / n) * Math.PI * 2 + this.rng();
      // forceAffixes = [] means "roll nothing": a spawnling that could itself split would
      // be an infinite fight, and one that could roll a star would lie about its size.
      const e = this.spawnOne(parent.x + Math.cos(a) * 1.5, parent.z + Math.sin(a) * 1.5,
                              parent.pack, parent.homeX, parent.homeZ, []);
      e.elite = false;
      e.caster = false;
      e.flies = false;
      e.scale = 0.62;
      e.maxHp = e.hp = parent.maxHp * 0.16;
      e.speed = parent.speed * 1.4;
      e.damage = parent.damage * 0.55;
      e.aggro = true;                    // they burst out of something you just killed
      e.aggroT = MOB.loseInterest;
      e.y = this.restY(e);
    }
  }

  hit(id, amount, weak = false) {
    const e = world.entities.get(id);
    if (!e) return null;
    e.hp -= amount;
    e.hurtT = HURT_FLASH;
    e.aggro = true;
    e.aggroT = MOB.loseInterest;
    this.alert(e);                    // being shot at is a pack-wide event
    if (e.hp <= 0) {
      // Death hook runs BEFORE despawn, while the entity still has a position to explode at.
      runAffix(e, "onDeath", this.fx);
      sfx.killThud(e.x, e.z, e.elite);     // the reward note — heavier for a star
      const out = { killed: true, elite: e.elite, ring: e.ring, affixes: affixLabel(e) };
      this.despawn(id);
      this.killed++;
      return out;
    }
    sfx.hitConfirm(e.x, e.z, weak);        // your shot LANDED — the confirm the game lacked
    return { killed: false, elite: e.elite, ring: e.ring, affixes: affixLabel(e) };
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
    // Sweep anything you've walked away from FIRST. The nearby() loop below only sees mobs
    // within despawn range, so its `dist > despawn` cleanup never fires for mobs abandoned in
    // a ring you've left — they'd persist frozen far behind you and, because the alive budget
    // counts EVERY mob, eat the whole spawn allowance. That is why the outer rings were empty:
    // ring-0 stragglers were still holding the budget. Despawn far mobs, and drop the pack
    // homes with them so packs.size reflects only what's actually around you.
    for (const e of [...this.entities()]) {
      if (Math.hypot(e.x - player.x, e.z - player.z) > MOB.despawn) this.despawn(e.id);
    }
    for (const [id, p] of this.packs) {
      if (this.packCount(id) === 0
          && Math.hypot(p.x - player.x, p.z - player.z) > MOB.despawn) this.packs.delete(id);
    }

    let alive = 0;
    for (const _ of this.entities()) alive++;   // eslint-disable-line no-unused-vars

    const cap = this.budget();
    this.spawnTimer -= dt;
    if (alive < cap.alive && this.packs.size < cap.packs && this.spawnTimer <= 0) {
      this.spawnTimer = cap.interval;
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
      if (e.slowT > 0) e.slowT -= dt;
      if (e.rootT > 0) e.rootT -= dt;
      if (e.flies) e.wobble += dt;       // the hover bob, independent of any wandering
      if (e.affixes.length) runAffix(e, "onTick", dt, this.fx);

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

      // A gate guard within taunt range becomes the target INSTEAD of you. That is the
      // whole reason the detachment exists: it can only take pressure off you by being the
      // better thing to hit. It also holds while you are INSIDE the walls — which is what
      // makes a town read as a place under siege rather than a place with a fence.
      const foe = guardNear(e.x, e.z);
      if (foe) { e.aggro = true; e.aggroT = MOB.loseInterest; }

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
          runAffix(e, "onHitPlayer", this.fx);
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

      // CHARGER: wind up rooted, commit in a straight line, then be helpless. Handled
      // before every other movement rule because each phase OWNS the body completely —
      // a charge that could be steered would not be a charge.
      if (e.aggro && e.charger && (e.windT > 0 || e.rushT > 0 || e.recoverT > 0)) {
        if (e.recoverT > 0) {
          e.recoverT -= dt;                     // spent: standing still, free to shoot
        } else if (e.rushT > 0) {
          e.rushT -= dt;
          const nx = e.x + e.rushX * MOB.chargeSpeed * dt;
          const nz = e.z + e.rushZ * MOB.chargeSpeed * dt;
          if (!sanctuaryOf(nx, nz, 1.5)) { e.x = nx; e.z = nz; }
          if (dist < MOB.attackRange * 1.3 && player.iframes <= 0) {
            onPlayerHit?.({ damage: e.damage * MOB.chargeDamage, x: e.x, z: e.z });
            runAffix(e, "onHitPlayer", this.fx);
            e.rushT = 0;
          }
          if (e.rushT <= 0) e.recoverT = MOB.chargeRecover;
        } else {
          e.windT -= dt;                        // rooted, glowing
          e.rushX = ux; e.rushZ = uz;           // aim updates until the instant it goes
          if (e.windT <= 0) e.rushT = MOB.chargeTime;
        }
        e.y = this.restY(e);
        reindex(e);
        this.sync(e, ux, uz);
        continue;
      }

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
        // Everything below aims at `foe` when a guard has taunted this one, and at you
        // otherwise — one piece of pack logic serving both, so a pack surrounds a guard
        // exactly the way it surrounds you.
        const aX = foe ? foe.x : player.x, aZ = foe ? foe.z : player.z;
        const adx = aX - e.x, adz = aZ - e.z;
        const adist = Math.hypot(adx, adz) || 1;
        const aux = adx / adist, auz = adz / adist;

        const ang = Math.atan2(-adz, -adx) + e.slot + (e.bold ? 0 : e.bias * 0.35);
        const standoff = e.bold ? MOB.ringRadius : MOB.timidStandoff;
        const tx = aX + Math.cos(ang) * standoff;
        const tz = aZ + Math.sin(ang) * standoff;
        const rd = Math.hypot(tx - e.x, tz - e.z) || 1;
        vx += ((tx - e.x) / rd) * MOB.ringForce;
        vz += ((tz - e.z) / rd) * MOB.ringForce;

        if (e.bold && adist > MOB.attackRange * 1.4) { vx += aux * 0.9; vz += auz * 0.9; }

        // Begin a charge from mid range — too close and there is no room to read it.
        if (!foe && e.charger && e.atkCd <= 0 && dist > MOB.attackRange * 2.5 && dist < MOB.chargeRange) {
          e.windT = MOB.chargeWind;
          e.atkCd = MOB.attackCd * 2.2;
        } else if (!foe && e.bold && dist <= MOB.attackRange * 1.7 && e.atkCd <= 0) {
          // No lunge at a guard: a lunge writes position directly and would shove the mob
          // straight through the line. Damage to guards comes from PRESSING them — the
          // guard counts what is standing on it — so the brawl stays where it started.
          e.lungeT = MOB.lungeTime;
          e.lx = ux; e.lz = uz;
          e.atkCd = MOB.attackCd;
          lunged.push(e);
        } else if (adist <= MOB.attackRange * 1.7) {
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

      if (e.castT > 0 || e.rootT > 0) { vx = 0; vz = 0; }    // rooted mid-cast, or CC'd by a spell

      const coh = MOB.cohesionForce * (e.swarm ? MOB.swarmCohesion : 1);
      vx += sepX * MOB.sepForce + aliX * MOB.alignForce + cohX * coh;
      vz += sepZ * MOB.sepForce + aliZ * MOB.alignForce + cohZ * coh;

      // Normalise so the forces set DIRECTION, not pace. Idling is a stroll; hunting isn't.
      const m = Math.hypot(vx, vz);
      if (m > 1e-4) {
        const pace = (e.aggro ? e.speed : e.speed * 0.42) * (e.slowT > 0 ? e.slowMul : 1);
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
    this.updateGround(dt);
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

  /** Dying bursts and burning ground. Both hurt the PLAYER only — a mob's own affix
   *  killing its packmates would read as a bug rather than as friendly fire. */
  updateGround(dt) {
    const hurt = this.fx.damagePlayer;

    for (const b of this.bursts) {
      if (!b.active) continue;
      b.t -= dt;
      const f = 1 - Math.max(0, b.t) / b.delay;
      b.mesh.material.opacity = 0.2 + 0.55 * f * f;      // brightens as it closes
      b.mesh.scale.setScalar(b.r * (0.75 + 0.25 * f));
      if (b.t > 0) continue;
      if (Math.hypot(player.x - b.x, player.z - b.z) < b.r && player.iframes <= 0) {
        hurt?.(b.dmg, b.x, b.z, MOB.knockback * 1.6);
      }
      sfx.explosion(b.x, b.z, 0.8);
      b.active = false;
      b.mesh.visible = false;
    }

    for (const f of this.fires) {
      if (!f.active) continue;
      f.t -= dt;
      f.mesh.material.opacity = 0.25 + Math.max(0, f.t / f.life) * 0.5;
      if (f.t <= 0) { f.active = false; f.mesh.visible = false; continue; }
      if (Math.hypot(player.x - f.x, player.z - f.z) < f.r && player.iframes <= 0) {
        hurt?.(f.dps * dt, f.x, f.z, 0);                 // no knockback: it is a floor
      }
    }
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
