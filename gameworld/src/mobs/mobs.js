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
import { MOB, PLAYER, RAID, WARCRY, DUNGEON } from "../config.js";
import { player } from "../state.js";
import { addEntity, removeEntity, reindex, world, nearby, gridKey, REGION_SIZE } from "../state.js";
import { groundY, solidAt, tierAt, ringPressure, surfaceNear, islandTopsAt } from "../world/gen.js";
import { terrainClear } from "../world/raycast.js";
import { dungeonSpawnPoint, dungeonFaction, dungeonGarrisonLeft,
         noteDungeonKill, clampToRoom } from "../world/dungeon.js";
import { sfx } from "../audio/sfx.js";
import { sanctuaryOf, sanctuaryOfIn, boundaryAt, gateArc, sanctuaryUnder,
         wallBlocksIn, sanctuariesNear, WALL_H } from "../world/sanctuary.js";
import { mulberry32 } from "../rng.js";
import { AFFIXES, rollAffixes, runAffix, affixHidden, affixLabel } from "./affixes.js";
import { isMyAlly, isHostileSanctuary, territoryColorAt } from "../prog/factions.js";

const HURT_FLASH = 0.12;

/**
 * Is the player standing IN a floor hazard sitting at height `fy`?
 *
 * A SLAB, not a column. The fire patch used to be a horizontal circle of infinite height, so
 * it burned you on a ledge three blocks above it and at the top of every jump. That was
 * harmless while the world was flat and nobody jumped; the moment the terrain had ledges in
 * it, a floor hazard reaching the sky was absurd.
 *
 * Your feet must be below the top of the flames and your head above the bottom of them — a
 * plain 1D overlap, which is why it also stops burning you from a chasm BELOW the fire
 * rather than only fixing the case above it.
 */
export function inFireSlab(py, fy, height = MOB.fireHeight) {
  return py < fy + height && py + PLAYER.height > fy;
}

/**
 * THE DISTANCE TICK: how often this body gets to think, in frames (see the MOB.farTick
 * essay). 1 means every frame. A pure function of the body and its distance so the rule can
 * be tested without a world around it.
 *
 * Committed states are promises — a lunge mid-air, a charge mid-run, a wind-up mid-glow —
 * and a promise kept at half rate is a body teleporting through the most-watched moment of
 * its life. They always think at full rate, as does anything hurt moments ago: the thing
 * you just shot is the thing you are looking at.
 */
export function tickStride(e, lodD, stampede = false) {
  if (e.leapT > 0 || e.lungeT > 0 || e.windT > 0 || e.rushT > 0 || e.recoverT > 0
      || e.castT > 0 || (e.burstLeft || 0) > 0 || (e.playerHurtT || 0) > 0) return 1;
  // THE STAMPEDE. The distance rules below all keep a floor of full-rate thinking near
  // the player — and in a HUGE fight that floor exempts nearly everyone, which is why
  // the biggest battles stayed the most expensive (the black box read 17-21ms of mob
  // brains a frame with the audio starving in lockstep). When the processed crowd passes
  // MOB.stampede, the floors give way: a crowd too big to watch individuals is a crowd
  // where nobody can tell who is thinking. What NEVER strides — committed attacks and
  // the just-shot above, and bodies hunting YOU below — is exactly what you can tell.
  if (stampede) {
    if (!e.aggro) return MOB.calmStride;
    if (e.warFoeId) return MOB.stampedeStride;
    // Even a body hunting YOU strides in a stampede — but only past arm's reach. A chaser
    // at fifteen paces deciding at half rate is invisible; the moment it reaches you, its
    // attack is a committed state and the exemptions above snap it to frame-perfect. The
    // knife range itself never strides: what is close enough to touch you is close enough
    // to watch.
    if (lodD > MOB.warTick) return MOB.farStride;
    return 1;
  }
  if (!e.aggro && lodD > MOB.calmTick) return MOB.calmStride;
  if (lodD > MOB.farTick) return MOB.farStride;
  // THE WAR IS THEATRE, even up close. A body whose target is another MOB is a fight you
  // watch, not a fight you are in — its blows land on its own clock either way, and past
  // arm's length nobody can tell a brawl deciding at half rate from one deciding at full.
  // The moment it turns on you (warFoeId cleared, or you touch it) it is frame-perfect
  // again — the two exemptions above outrank this line by construction.
  if (e.warFoeId && lodD > MOB.warTick) return MOB.farStride;
  return 1;
}

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
    // neighbours() answers into these SAME slots every ask. It runs for every body every
    // frame, and a fresh array of fresh {o, d} pairs per ask was ~4000 small objects a
    // frame in a big fight — cost that never shows on a profile line because it is paid
    // later, all at once, as a collector pause. Exactly the "smooth then hitches" shape.
    // Safe because every caller consumes the answer before asking again.
    this._nbrOut = [];
    this._nbrPool = Array.from({ length: MOB.maxNeighbours }, () => ({ o: null, d: 0 }));
    this.killed = 0;
    this.born = 0;

    // ONE draw call for every mob alive. Individual meshes cost a draw call each, and this
    // machine has no discrete GPU — at 200 bodies that overhead is the whole frame budget.
    // Instancing makes population a simulation question rather than a rendering one.
    // Each mob TYPE is a distinct SILHOUETTE now, so you read WHAT a creature is from its
    // outline — and COLOUR is freed up to say WHOSE side it's on (its faction). One
    // InstancedMesh per shape, one draw call each; the type read costs nothing at runtime.
    const feet = (g, h) => { g.translate(0, h, 0); return g; };
    this.shapes = {
      plain: feet(new THREE.ConeGeometry(MOB.radius, 1.6, 5), 0.8),        // the rank and file
      charger: feet(new THREE.BoxGeometry(0.95, 1.3, 0.95), 0.65),         // a bulky bruiser
      caster: feet(new THREE.CylinderGeometry(0.34, 0.34, 1.95, 8), 0.98), // tall and thin
      flyer: new THREE.OctahedronGeometry(0.72),                           // a floating diamond
      swarm: feet(new THREE.TetrahedronGeometry(0.52), 0.3),               // tiny and spiky
    };
    this.meshes = {};
    for (const [k, g] of Object.entries(this.shapes)) {
      const m = new THREE.InstancedMesh(g, new THREE.MeshLambertMaterial({}), MOB.maxAliveCap + 32);
      m.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
      m.frustumCulled = false;   // instances move every frame; the bounds would lie
      m.count = 0;
      scene.add(m);
      this.meshes[k] = m;
    }

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
    // Faction body colours — the tell for which side a camp is on, so the three armies read
    // as three armies. Black / blue / green, matching the three player factions (Iron / Ash /
    // Vale): the colour you see is the side you would be helping or hunting.
    this.factionCols = [
      new THREE.Color(0x26262c),   // 0: black — Iron
      new THREE.Color(0x3f6fd1),   // 1: blue  — Ash
      new THREE.Color(0x4fae5a),   // 2: green — Vale
      new THREE.Color(0xcf7a2a),   // 3: amber (if factions > 3)
    ];
    // ELITE bodies, chosen by eye rather than derived. The old rule was "lerp the faction
    // colour 40% toward white", which brightens a HUE perfectly well and destroys a faction
    // that hasn't got one: Iron is deliberately achromatic, so #26262c came out #7d7d80 —
    // neutral grey, which names no side at all. Every flying mob is an elite (only elites
    // can fly) and elites are the big ones, so that single line turned every large or
    // airborne Iron body into a colourless blob.
    //
    // Each of these is picked to stay unmistakably its own faction while reading as brighter
    // than the rank and file. Iron's keeps a cool violet cast so it is never neutral, and
    // stays the darkest of the three, because "Iron is the dark one" is the whole tell.
    this.factionElites = [
      new THREE.Color(0x5b5b78),   // 0: Iron  — lit steel, still darkest, never grey
      new THREE.Color(0x86b0ff),   // 1: Ash
      new THREE.Color(0x8fe09b),   // 2: Vale
      new THREE.Color(0xf0a860),   // 3: amber
    ];
    this.COL_CASTER = new THREE.Color(0xd11f1f);   // red: airborne ranged
    this.COL_GROUNDCASTER = new THREE.Color(0x8a3fd1);   // violet: ranged, but grounded
    // (The wind-up telegraph is a JUDDER now, not a colour — see render(). This is left as a
    // named colour in case a future tell wants it, but nothing reads it today.)
    this.COL_CHARGER = new THREE.Color(0x6b4a2a);   // heavy brown: it comes at you
    this.COL_SWARM = new THREE.Color(0xc3d94a);     // pale: many, small, brief
    this.COL_HURT = new THREE.Color(0xff6655);
    // Raid champions wear their TRADE colours (see colorOf): the same green/black/red the
    // player already knows from friendly towns' herbalist, adept, and (red) quartermaster.
    this.champCols = {
      herbalist: new THREE.Color(0x63d1a0),
      adept: new THREE.Color(0x14141c),
      qm: new THREE.Color(0xd23c3c),
    };
    this._affixCol = new THREE.Color();

    this._affixCache = new Map();     // affix id -> THREE.Color, built once

    // Dying bursts: a telegraph ring, then a bang. Pooled — a wiped elite pack can put
    // several in the air in the same second.
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
      this.fires.push({ mesh, active: false, x: 0, y: 0, z: 0, t: 0, life: 1, dps: 0, r: 1, friendly: false });
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

    // Death POPS — a quick expanding shell + shards when anything dies. Pure juice; pooled,
    // because a battle can kill a dozen things in a second.
    const popGeo = new THREE.IcosahedronGeometry(0.6, 0);
    this.pops = [];
    for (let i = 0; i < 30; i++) {
      const mesh = new THREE.Mesh(popGeo, new THREE.MeshBasicMaterial({
        color: 0xffffff, transparent: true, opacity: 0, depthWrite: false,
        blending: THREE.AdditiveBlending,
      }));
      mesh.visible = false;
      scene.add(mesh);
      this.pops.push({ mesh, active: false, t: 0 });
    }
    this.popI = 0;

    // Damage numbers to float above whatever you hit — read by the UI layer each frame, then
    // cleared. Only the PLAYER's hits fill this (see hit()); mob-vs-mob would be pure noise.
    this.hitEvents = [];
  }

  /** A cosmetic death burst at a point, tinted to the side that fell. */
  deathPop(x, y, z, color) {
    const p = this.pops[this.popI = (this.popI + 1) % this.pops.length];
    p.active = true;
    p.t = 0.34;
    p.mesh.position.set(x, y + 0.6, z);
    p.mesh.material.color.set(color);
    p.mesh.scale.setScalar(0.4);
    p.mesh.visible = true;
  }

  updatePops(dt) {
    for (const p of this.pops) {
      if (!p.active) continue;
      p.t -= dt;
      const f = Math.max(0, p.t / 0.34);       // 1 → 0
      p.mesh.scale.setScalar(0.4 + (1 - f) * 2.4);   // expands as it fades
      p.mesh.material.opacity = f * 0.9;
      p.mesh.rotation.x += dt * 9;
      p.mesh.rotation.y += dt * 7;
      if (p.t <= 0) { p.active = false; p.mesh.visible = false; }
    }
  }

  factionColor(e) { return this.factionCols[(e.faction || 0) % this.factionCols.length]; }

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
  colorOf(e) {
    if (e.hurtT > 0) return this.COL_HURT;
    // THE CHAMPIONS are people, not war-bodies, and they wear their TRADE colours — the same
    // ones their shopkeeper selves wear in a friendly town: green herbalist, black adept,
    // red quartermaster. This is what makes the raid's kill-order readable at a glance:
    // "kill the green one first" only works if the green one is green.
    if (e.champion) {
      const c = this.champCols[e.champion];
      if (c) return c;
    }
    // ONE BODY, ONE COLOUR, and the colour is the FACTION — full stop. Every scheme that
    // borrowed the body for a second message failed the same way in play: the cast-glow
    // made casters change colour, affix tints made stars wear a stranger's colours, and an
    // anchored affix *cycle* just read as a mob flashing through colours. Whose side it is
    // on is the one question the body answers, because it is the one question you ask at a
    // glance in a war of three colours. Everything else has its own channel: SHAPE says
    // what it is, the JUDDER says it's about to fire, SCALE and the brighter tint say it's
    // a star, and the kill feed names its affixes.
    const f = (e.faction || 0);
    if (e.elite) return this.factionElites[f % this.factionElites.length];
    return this.factionCols[f % this.factionCols.length];
  }

  /** Which silhouette this creature is drawn as. */
  shapeOf(e) {
    if (e.swarm) return "swarm";
    if (e.flies) return "flyer";
    if (e.caster) return "caster";
    if (e.charger) return "charger";
    return "plain";
  }

  /** Write every live mob into its SHAPE's instance buffer — one draw call per shape. */
  render() {
    const now = performance.now();
    const idx = { plain: 0, charger: 0, caster: 0, flyer: 0, swarm: 0 };
    for (const e of this.entities()) {
      const shape = this.shapeOf(e);
      const mesh = this.meshes[shape];
      const i = idx[shape];
      if (i >= mesh.instanceMatrix.count) continue;   // that shape's buffer is full
      const sc = (e.elite ? MOB.eliteScale : 1) * (e.scale || 1);
      this._q.setFromAxisAngle(this._up, e.facing ?? e.heading ?? 0);
      // THE WIND-UP TELEGRAPH: a fast side-to-side JUDDER while a caster is charging a shot or
      // a charger is coiling, instead of a colour change. A shake reads as "tense, about to
      // release" and keeps the body's colour intact. Perpendicular to its facing, at ~14Hz,
      // with a per-mob phase so a whole pack does not quiver in lockstep.
      let vx = e.x, vz = e.z;
      if (e.castT > 0 || e.windT > 0) {
        const shake = Math.sin(now * 0.09 + (e.wobble || 0) * 7) * 0.14;
        vx += Math.cos(e.facing ?? 0) * shake;      // sideways relative to where it faces
        vz += -Math.sin(e.facing ?? 0) * shake;
      }
      this._m.compose(this._p.set(vx, e.y, vz), this._q, this._s.set(sc, sc, sc));
      mesh.setMatrixAt(i, this._m);
      // COLOUR ONLY WHEN THE SLOT CHANGES HANDS. A body's colour is decided at birth —
      // faction, elite — and never again, but this wrote and re-uploaded every colour
      // every frame: a cost that grows with every body the world adds, for zero pixels
      // of difference ("it just infinitely makes more and more mobs" — and each one was
      // billing the GPU forever). Slots follow iteration order, which is stable between
      // frames except at spawn and death, so most frames now upload nothing at all.
      const slots = (this._slotIds ??= {})[shape] ??= [];
      if (slots[i] !== e.id) {
        mesh.setColorAt(i, this.colorOf(e));
        slots[i] = e.id;
        (this._colorDirty ??= {})[shape] = true;
      }
      idx[shape] = i + 1;
    }
    for (const k of Object.keys(this.meshes)) {
      const m = this.meshes[k];
      m.count = idx[k];
      m.instanceMatrix.needsUpdate = true;
      if (m.instanceColor && this._colorDirty?.[k]) {
        m.instanceColor.needsUpdate = true;
        this._colorDirty[k] = false;
      }
    }
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
      // The war-target clock starts at a RANDOM phase, not at zero. Born at zero, every
      // body in a pack came due on the same frame forever after — and profiling the worst
      // frame found exactly that: a thundering herd of simultaneous war rescans costing
      // thirty times the average frame's share. Stagger is free at birth and impossible
      // to retrofit later, because synchronized clocks re-synchronize every wave.
      warThink: this.rng() * 0.4,
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
      alive: Math.min(MOB.maxAliveCap,
        (MOB.maxAlive + MOB.maxAlivePerTier * crowd) * MOB.skyCrowd),
      packs: Math.min(MOB.maxPacksCap, MOB.maxPacks + MOB.maxPacksPerTier * crowd),
      interval: Math.max(MOB.spawnIntervalMin,
        MOB.spawnInterval * Math.pow(1 - MOB.spawnFasterPerTier, crowd)),
    };
  }

  /** Where this body sits vertically: on the ground, or hovering above it. */
  /**
   * WHICH FLOOR this body is on. A column can have several now — the land, the top of a sky
   * island, the floor under an overhang — and asking groundY on an island answers with the
   * ground far below, which walks the body off into the air.
   *
   * Gated on being noticeably off the land, because almost everything alive is standing on
   * it and for those the cheap answer is the correct one.
   */
  floorAt(e, x = e.x, z = e.z) {
    const g = groundY(x, z);
    return Math.abs(e.y - g) < MOB.floorSlack ? g : surfaceNear(x, z, e.y);
  }

  restY(e) {
    // MID-LEAP the ground is not the answer. Interpolating between the heights it left and
    // is heading for — rather than reading groundY under it — is what stops the body
    // snapping vertically the instant it crosses the cliff edge it is jumping over.
    if (e.leapT > 0) {
      const p = 1 - e.leapT / MOB.leapDur;
      return e.leapY0 + (e.leapY1 - e.leapY0) * p + Math.sin(p * Math.PI) * MOB.leapArc;
    }
    const g = this.floorAt(e);
    if (!e.flies) return g;
    const bob = Math.sin(e.wobble * 1.6) * MOB.flyBob;
    // Hovering over whatever floor is beneath it — UNLESS it is hunting you, in which case
    // it climbs to your height. Eased rather than snapped: this is a hover, so it is
    // smoothing, not physics, and it wants to look like a thing deciding to come up.
    let want = g + MOB.flyHeight;
    if (e.aggro) want = Math.max(want, player.y + MOB.flyChaseLift);
    return e.y + (want + bob - e.y) * MOB.flyClimb;
  }

  /**
   * Throw itself at something it cannot walk up.
   *
   * Called only when tryMove has failed on every heading, so this is the last resort before
   * standing still — which is what used to happen, and what made a two-block ledge an
   * unbeatable fortress. It looks a few strides ahead for somewhere it could land, takes the
   * furthest one that works, and commits: for leapDur seconds the body follows an arc and
   * nothing tests its footing.
   */
  tryLeap(e, vx, vz) {
    if (e.leapT > 0 || e.leapCd > 0 || !e.aggro || e.flies) return false;
    const d = Math.hypot(vx, vz) || 1;
    const ux = vx / d, uz = vz / d;
    const here = this.floorAt(e);
    // Furthest first: clearing a gap outright beats scrambling onto its near lip.
    for (let i = MOB.leapReach.length - 1; i >= 0; i--) {
      const reach = MOB.leapReach[i];
      const nx = e.x + ux * reach, nz = e.z + uz * reach;
      const there = this.floorAt(e, nx, nz);
      // Both ways: a spire is still a spire, and a leap off an island into open sky is not a
      // pursuit, it is a body throwing itself away.
      if (Math.abs(there - here) > MOB.leapClimb) continue;
      if (!this.wallOk(e, nx, nz)) continue;           // a wall is never leapt
      e.leapT = MOB.leapDur;
      e.leapCd = MOB.leapCd;
      e.leapX0 = e.x; e.leapZ0 = e.z; e.leapX1 = nx; e.leapZ1 = nz;
      e.leapY0 = here; e.leapY1 = there;
      e.heading = Math.atan2(ux, uz);
      return true;
    }
    return false;
  }

  /** Advance every body that is in the air. One pass, so no AI branch can forget to do it. */
  stepLeaps(dt) {
    for (const e of this.entities()) {
      if (e.leapCd > 0) e.leapCd -= dt;
      if (e.leapT <= 0) continue;
      e.leapT -= dt;
      const p = Math.max(0, Math.min(1, 1 - e.leapT / MOB.leapDur));
      e.x = e.leapX0 + (e.leapX1 - e.leapX0) * p;
      e.z = e.leapZ0 + (e.leapZ1 - e.leapZ0) * p;
      if (e.leapT <= 0) { e.leapT = 0; e.x = e.leapX1; e.z = e.leapZ1; }
      e.y = this.restY(e);
    }
  }

  /**
   * HOW FAR A BODY IS, with altitude weighted heavier than ground (MOB.despawnVScale).
   *
   * Every distance a mob measured used to be flat, which was exact while the world was a
   * surface. It is what kept the ground population alive and budget-hogging while you stood
   * on an island above them — see MOB.despawnVScale for the whole argument.
   */
  farFrom(x, y, z) {
    return Math.hypot(x - player.x, z - player.z, (y - player.y) * MOB.despawnVScale);
  }

  /**
   * EVERYTHING GOES. Called when the world itself is swapped — stepping into an instance or
   * back out of it. The sweep is a distance test and cannot help here: the bodies you leave
   * behind are not far away, they are in a DIFFERENT WORLD at the same coordinates, and
   * defenders are exempt from distance sweeps entirely.
   */
  clearAll() {
    for (const e of [...this.entities()]) this.despawn(e.id);
    this.packs.clear();
  }

  breedDelay() {
    const [lo, hi] = MOB.breedEvery;
    return lo + this.rng() * (hi - lo);
  }

  /**
   * WHICH FLOOR a new camp stands on. Every floor over the column competes — the land, and
   * one perch per deck — weighted by how near it is to the player's own altitude, with the
   * sky carrying a standing multiplier (MOB.skyWeight). This is what fills the level you are
   * actually on, rather than arguing about what fraction of the world should be airborne.
   */
  pickFloor(x, z) {
    const floors = [groundY(x, z), ...islandTopsAt(x, z)];
    let total = 0;
    const w = floors.map((fy, i) => {
      const v = (i === 0 ? 1 : MOB.skyWeight) / (1 + Math.abs(fy - player.y) / MOB.skyAffinity);
      total += v;
      return v;
    });
    let r = this.rng() * total, pick = 0;
    while (pick < floors.length - 1 && (r -= w[pick]) > 0) pick++;
    return floors[pick];
  }

  /** The floor at this column nearest a height its camp already chose — so a body on the rim
   *  of a small island stands on THAT island rather than whatever is directly below it. */
  floorNearest(x, z, wantY) {
    const floors = [groundY(x, z), ...islandTopsAt(x, z)];
    let best = floors[0], bd = Infinity;
    for (const fy of floors) {
      const d = Math.abs(fy - wantY);
      if (d < bd) { bd = d; best = fy; }
    }
    return best;
  }

  spawnOne(x, z, packId, homeX, homeZ, forceAffixes = null, faction = 0, wantY = null) {
    const s = this.rollStats(x, z);
    const e = addEntity({
      kind: "mob", x, z,
      ...s,
      pack: packId, homeX, homeZ, faction,
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
      windT: 0, rushT: 0, recoverT: 0, rushX: 0, rushZ: 0, rushVoice: null,
      // Mid-leap state. leapT counts DOWN, so 0 means "on the ground" everywhere.
      leapT: 0, leapCd: 0, leapX0: 0, leapZ0: 0, leapX1: 0, leapZ1: 0, leapY0: 0, leapY1: 0,
      // Cached sight line and the clock that refreshes it — see MOB.losCheck.
      los: true, losT: 0,
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
    // ISLANDS GET GARRISONS. Some of what spawns over a column with sky above it is put UP
    // there rather than on the land beneath — islands with nothing on them are scenery, and
    // the whole argument for putting them in the world is that taking one should be a fight.
    // restY decides which floor a body is on by reading e.y, so seeding it here is what makes
    // the choice stick for the rest of that body's life.
    // A CAMP SHARES A FLOOR. Choosing per BODY scattered a pack of a dozen across a dozen
    // different levels — one here, one two hundred blocks up — so every level looked empty
    // even though the world was full of them. A camp is a camp: it picks its ground once and
    // its bodies stand on it, and what you find is twelve of them rather than one.
    e.y = wantY === null ? this.pickFloor(x, z) : this.floorNearest(x, z, wantY);
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
    this.packs.set(id, { x: hx, z: hz, y: player.y });
    const count = kind === "swarm" ? 18 : n;
    const faction = Math.floor(this.rng() * MOB.factions);
    for (let i = 0; i < count; i++) {
      const ang = this.rng() * Math.PI * 2;
      const e = this.spawnOne(hx + Math.cos(ang) * 5, hz + Math.sin(ang) * 5, id, hx, hz, [], faction);
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
    this.packs.set(id, { x: hx, z: hz, y: player.y });
    for (let i = 0; i < n; i++) {
      const ang = this.rng() * Math.PI * 2;
      const e = this.spawnOne(hx + Math.cos(ang) * 4, hz + Math.sin(ang) * 4,
                              id, hx, hz, affixIds, Math.floor(this.rng() * MOB.factions));
      e.elite = true;                    // affixes ride on stars, so force the tell too
    }
    return true;
  }

  /** A camp: several mobs sharing a home they return to and breed at. */
  /**
   * @param {number} instAlive  how many of an INSTANCE's own defenders are standing. The
   *   world's total population is deliberately not a parameter: the caller checks that
   *   against the budget before it ever gets here, and a second copy of the number in this
   *   signature was one more thing that could disagree with it.
   */
  spawnPack(instAlive = 0) {
    // A GARRISON IS FINITE. Outside, this is Infinity and nothing changes; inside an instance
    // it counts down as you kill, and when it reaches zero the room stops producing enemies
    // and stays cleared. Checked before anything else is rolled, so a spent dungeon costs
    // nothing per attempt. Counted against the INSTANCE's own bodies — see update().
    if (dungeonGarrisonLeft(instAlive) <= 0) return null;
    const a = this.rng() * Math.PI * 2;
    const d = MOB.spawnMin + this.rng() * (MOB.spawnMax - MOB.spawnMin);
    // A ROOM IS NOT OPEN GROUND. The ring below is the right shape for a frontier and the
    // wrong one for four walls — inside an instance it puts nine camps in ten out in the void
    // past the shell, where they are rejected and the dungeon stays empty. Ask the instance
    // where its floor actually is instead.
    const spot = dungeonSpawnPoint(this.rng, player);
    const hx = spot ? spot.x : player.x + Math.cos(a) * d;
    const hz = spot ? spot.z : player.z + Math.sin(a) * d;
    // THE CAMP'S GROUND FIRST, because whether this is holy ground depends on which FLOOR the
    // camp stands on. A sky town's walls do not sterilise the land two hundred blocks below
    // them — that is ordinary frontier and should be thick with camps — but its own platform
    // is a refuge like any other.
    const packY = this.pickFloor(hx, hz);
    // THERE HAS TO BE SOMETHING TO STAND ON. Outdoors this is free — groundY is defined as one
    // above the top solid block, so the block beneath it is solid by construction. Inside an
    // instance it is the whole question: the floor query answers with the room's floor height
    // for EVERY column, including the empty void outside the shell, so without this a camp
    // gets pitched in mid-air beyond the wall where nothing can reach anything.
    if (!solidAt(hx, packY - 1, hz)) return null;
    // NEVER MAKE CAMP ON HOLY GROUND — a refuge you have to clear isn't a refuge.
    //
    // TWO TESTS, because "is this spot in a town" has two different meanings and only asking
    // one of them is how camps kept appearing in the streets.
    //
    // The BAND test is about levels: it is what lets the frontier two hundred blocks beneath
    // a sky town stay ordinary hostile country instead of being sterilised by something
    // floating over it.
    //
    // The FOOTPRINT test is about the map, and it has no height at all — no camp is pitched
    // anywhere inside a settlement's walls, at any altitude. That is what was missing. A camp
    // whose chosen floor was a sky island cleared the band test easily (the city's band is
    // sixty blocks; the island was three hundred up) and was then free to scatter its members
    // across homeWander, and every member landing on a column with no island over it fell to
    // the floor below — the market square. It also stops the sky directly over a city being
    // the busiest airspace in the ring, which is the same problem one storey up.
    //
    // Rejecting the CAMP and not its members matters: an earlier version skipped individual
    // bodies, which left the camp registered but empty. The pack budget filled with hollow
    // camps, the alive count stayed low, and the spawner answered by making more of them.
    if (sanctuaryUnder(hx, packY, hz, MOB.homeWander + 14)) return null;
    if (sanctuaryOf(hx, hz, MOB.homeWander + 14)) return null;
    const id = this.nextPack++;
    // WITH ITS FLOOR. A camp on an island and a camp on the land beneath it are not the
    // same camp, and the sweep below cannot tell them apart without this.
    this.packs.set(id, { x: hx, z: hz, y: packY });

    // A camp is either ordinary or a SWARM — mixing them would blur the silhouette read,
    // and reading the camp before you engage it is the whole point of having breeds.
    const inst = dungeonFaction() !== null;
    // Inside, knots are small and the total is what matters — see DUNGEON.garrison. A frontier
    // camp of eighteen would empty half a dungeon's roster in one spawn.
    const isSwarm = !inst && this.rng() < MOB.swarmPackChance;
    const [lo, hi] = inst ? DUNGEON.garrisonPack : (isSwarm ? MOB.swarmSize : MOB.packSize);
    let n = lo + Math.floor(this.rng() * (hi - lo + 1));
    if (inst) n = Math.min(n, dungeonGarrisonLeft(instAlive));
    // The whole camp shares one faction — a camp is a side in the war. WHOSE side is the
    // land's to say: inside a town's claim the camp flies that town's colour, so the bodies
    // outside a gate are the same army as the bodies inside it. Only unclaimed ground rolls.
    // The roll is drawn either way so the RNG stream does not depend on where you are standing.
    const roll = Math.floor(this.rng() * MOB.factions);
    const held = territoryColorAt(hx, hz);
    // A stronghold belongs to ONE side. Territory colour is a question about the map, and
    // inside an instance the map is not where you are.
    const faction = inst ? dungeonFaction() : (held >= 0 ? held : roll);
    for (let i = 0; i < n; i++) {
      const ang = this.rng() * Math.PI * 2;
      const r = this.rng() * MOB.homeWander * (isSwarm ? 0.5 : 1);
      // Inside four walls the scatter has to stay inside them — see clampToRoom.
      const at = clampToRoom(hx + Math.cos(ang) * r, hz + Math.sin(ang) * r);
      const e = this.spawnOne(at.x, at.z, id, hx, hz, null, faction, packY);
      // THE SKY PUTS DOWN THE BOW (MOB.skyCasterKeep): a wild camp on a sky floor arrives
      // mostly melee — an island garrison exists to make TAKING the island a fight, not to
      // lean artillery over the rim into a war below that it isn't part of. Dungeons are
      // exempt (`inst`): their garrison is a designed encounter on its own floor. Fliers
      // are exempt: the red diamond at your altitude is the sky's honest ranged threat.
      // The roll is drawn unconditionally so the RNG stream doesn't depend on the floor.
      const bowRoll = this.rng();
      if (!inst && e.caster && !e.flies
          && e.y - groundY(at.x, at.z) > MOB.castVert
          && bowRoll >= MOB.skyCasterKeep) e.caster = false;
      // Marks it as one of THIS instance's defenders, so the garrison counts itself and
      // nothing out in the world can be mistaken for part of it.
      if (inst) e.inst = true;
      if (isSwarm) this.makeSwarm(e);
    }
    return id;
  }

  /**
   * Nearest LIVE mob of a different faction within range — the enemy this creature will
   * brawl. Bucketed query, so it only touches what's actually nearby.
   */
  enemyMobNear(e, range) {
    if (!MOB.factionWar) return null;
    // Hand-walked buckets, squared distances — same treatment as neighbours(), same
    // profiled reason: several hundred war rethinks a second in a giant fight, and a
    // nearest-search never needs a single square root, only a winner.
    let best = null, bd2 = range * range;
    const gx0 = Math.floor((e.x - range) / REGION_SIZE), gx1 = Math.floor((e.x + range) / REGION_SIZE);
    const gz0 = Math.floor((e.z - range) / REGION_SIZE), gz1 = Math.floor((e.z + range) / REGION_SIZE);
    for (let gz = gz0; gz <= gz1; gz++) for (let gx = gx0; gx <= gx1; gx++) {
      const ids = world.regions.get(gridKey(gx, gz));
      if (!ids) continue;
      for (const id of ids) {
        const o = world.entities.get(id);
        // o.defender: town fighters are out of the war (see the attention block) — a garrison
        // the field could whittle down is a garrison that is sometimes not there.
        if (!o || o === e || o.kind !== "mob" || o.hp <= 0 || o.faction === e.faction || o.defender) continue;
        const dx = o.x - e.x, dz = o.z - e.z;
        const d2 = dx * dx + dz * dz;
        if (d2 < bd2) { bd2 = d2; best = o; }
      }
    }
    return best;
  }

  /** Damage from ANOTHER mob (the war). No player reward; the victim fights back and, if it
   *  dies, still runs its death affix — a burst star killed in the melee still explodes. */
  hitMob(target, amount) {
    target.hp -= amount;
    target.hurtT = HURT_FLASH;
    target.aggro = true;
    target.aggroT = MOB.loseInterest;
    if (target.hp <= 0) {
      runAffix(target, "onDeath", this.fx);
      // A defender that falls in the WAR still counts toward the sack: if a rival camp
      // whittles a garrison and you deal the finishing blows, the town fell and you took
      // it — using the war as a weapon is play, not an exploit.
      if (target.defender) this.onDefenderKill?.(target);
      this.deathPop(target.x, target.y, target.z, this.factionColor(target));
      this.despawn(target.id);
    }
  }

  despawn(id) {
    // Kill any sound the body was still making. Shooting a charger out of the air mid-run is
    // the most satisfying thing you can do to one, and it has to be silent the instant it
    // dies — a rumble still rolling from something that is no longer there would send you
    // dodging away from nothing. Every removal path funnels through here, so this is the one
    // place that has to remember: dying, despawning, and wandering off are all covered.
    const e = world.entities.get(id);
    if (e?.rushVoice) { e.rushVoice.stop(); e.rushVoice = null; }
    removeEntity(id);   // the instance buffer is rebuilt each frame; nothing to free
  }

  *entities() {
    for (const e of world.entities.values()) if (e.kind === "mob") yield e;
  }

  targets() {
    const out = [];
    for (const e of this.entities()) {
      if (affixHidden(e)) continue;      // Phasing and anything like it
      if (isMyAlly(e.faction)) continue; // your own army: your shots pass right through them
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

  /** Break a charge dead — wind-up, rush, or recovery — and kill its sound. Any hard crowd
   *  control (a knockback, a root) calls this: a charge is a COMMITTED attack, and the whole
   *  point of committing is that it can be PUNISHED. A charger you knock back or freeze mid-run
   *  should stop, not shrug it off and keep coming — that is the answer the telegraph promises. */
  breakCharge(e) {
    if (e.windT <= 0 && e.rushT <= 0 && e.recoverT <= 0) return;
    e.windT = 0; e.rushT = 0; e.recoverT = 0;
    if (e.rushVoice) { e.rushVoice.stop(); e.rushVoice = null; }
  }

  /** Shove a mob outward from a point. Survivors get thrown; the dead do not care. A shove
   *  also STOPS a charge — you cannot both be flung backward and still be barreling forward. */
  push(e, fromX, fromZ, force) {
    // NOT YOUR OWN ARMY. hit() has refused to damage an ally since factions landed, but the
    // SHOVE and the SLOW were never given the same rule — so every spin, nova, ring of fire
    // and cleaver swing scattered the soldiers fighting beside you and froze them in place.
    // Worse than useless: the one moment you most want your side pressing forward is the
    // moment you are throwing everything you have, which is exactly when you were knocking
    // them out of the fight. Every caller of this is one of YOUR effects (see main), so the
    // rule belongs here rather than at five call sites that would drift apart.
    if (isMyAlly(e.faction)) return;
    const dx = e.x - fromX, dz = e.z - fromZ;
    const d = Math.hypot(dx, dz) || 1;
    e.kx = (dx / d) * force;
    e.kz = (dz / d) * force;
    e.kT = MOB.knockTime;
    this.breakCharge(e);
  }

  // --- the world verbs affixes call through ctx.mobs ---------------------------
  // These are the whole reason affixes need a context at all. They were referenced by
  // affixes.js before they existed here, which is why Dying Burst threw on the first kill
  // and Burning silently did nothing at all.


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
    // THE FLOOR THIS BURNER IS ACTUALLY ON, not the land. groundY answers "how tall is the
    // terrain in this column", which was the whole truth when there was one floor — with
    // islands over it, a burner walking a platform two hundred blocks up laid its trail on
    // the ground far below, burning nothing and warning nobody. floorAt asks which of the
    // floors over this column the BODY is standing on, which is the question being asked.
    //
    // Remembered rather than recomputed, because the damage test needs to know what "on the
    // ground" means HERE, and asking again every frame would answer for wherever YOU are.
    const fy = this.floorAt(e);
    // WHOSE FIRE IT IS, in colour. A burning patch is read at a glance while you are already
    // moving, and until now every one of them was the same orange whether it was laid by the
    // thing hunting you or by the army you swore to — so the only way to find out was to walk
    // into it. Your side burns blue.
    //
    // It still HURTS. Blue does not mean safe, it means "this one is not evidence that
    // something is hunting you" — which is the thing you actually misread in a crowded fight,
    // and the reason you flinch away from ground you could have held.
    const friendly = isMyAlly(e.faction);
    f.mesh.material.color.setHex(friendly ? 0x3fa9ff : 0xff7a1e);
    Object.assign(f, { active: true, x: e.x, y: fy, z: e.z, dps, r: radius, t: life, life, friendly });
    f.mesh.position.set(e.x, fy + 0.05, e.z);
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
      if (isMyAlly(e.faction)) continue;          // your own side is never frozen — see push()
      if (Math.hypot(e.x - x, e.z - z) > radius) continue;
      if (slowT > e.slowT) { e.slowT = slowT; e.slowMul = slowMul; }
      if (rootT > e.rootT) {
        e.rootT = rootT;
        // A ROOT stops a charge dead, same as a knockback — pinning something in place while
        // it charges through you would make the freeze useless against the one attack you
        // most need to freeze. The charger block owns the body and never checks rootT on its
        // own, so the break has to happen HERE, where the root is applied.
        this.breakCharge(e);
      }
    }
  }

  /** Splitting: the kill is not the end. */
  spawnSplit(parent, n) {
    for (let i = 0; i < n; i++) {
      const a = (i / n) * Math.PI * 2 + this.rng();
      // forceAffixes = [] means "roll nothing": a spawnling that could itself split would
      // be an infinite fight, and one that could roll a star would lie about its size.
      const e = this.spawnOne(parent.x + Math.cos(a) * 1.5, parent.z + Math.sin(a) * 1.5,
                              parent.pack, parent.homeX, parent.homeZ, [], parent.faction, parent.y);
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
    // Your own army cannot be harmed BY you — one guard at the one place all player damage
    // lands (gun, blast, spell, beam all funnel here), so nothing needs to know about allies
    // except this line. It fights alongside you; friendly fire would just be a betrayal button.
    if (isMyAlly(e.faction)) return null;
    e.hp -= amount;
    e.hurtT = HURT_FLASH;
    // The distance tick's exemption, and specifically YOURS. hurtT alone can't carry it:
    // war blows set hurtT too, so in a giant brawl everything is perpetually "just hurt"
    // and the whole battle would exempt itself from the stride — the bigger the fight, the
    // less the stride would do, which is backwards. This timer only ever means "the player
    // touched this", so the thing you shot thinks frame-perfect and the war doesn't get to
    // buy your full attention by flashing itself red.
    e.playerHurtT = HURT_FLASH;
    e.aggro = true;
    e.aggroT = MOB.loseInterest;
    this.alert(e);                    // being shot at is a pack-wide event
    // Floating damage number for the player's hit (weak-point hits pop bigger/brighter).
    this.hitEvents.push({ x: e.x, y: e.y + 1.4, z: e.z, amount: Math.round(amount), weak });
    if (e.hp <= 0) {
      // Death hook runs BEFORE despawn, while the entity still has a position to explode at.
      runAffix(e, "onDeath", this.fx);
      // A town defender fell to the PLAYER (this choke point is player+guard damage, and
      // guards never target defenders) — the raid layer counts these toward the sack.
      if (e.defender) this.onDefenderKill?.(e);
      sfx.killThud(e.x, e.z, e.elite);     // the reward note — heavier for a star
      this.deathPop(e.x, e.y, e.z, this.factionColor(e));
      // faction rides along so the reward path can tell whether this was the colour your
      // side is sworn against — the kill site is the only place that still knows.
      const out = { killed: true, elite: e.elite, ring: e.ring, faction: e.faction, affixes: affixLabel(e) };
      // One fewer defender. No-op outdoors; inside, this is the only thing that makes clearing
      // a dungeon a real state rather than a lull between spawns.
      noteDungeonKill();
      this.despawn(id);
      this.killed++;
      return out;
    }
    sfx.hitConfirm(e.x, e.z, weak);        // your shot LANDED — the confirm the game lacked
    return { killed: false, elite: e.elite, ring: e.ring, faction: e.faction, affixes: affixLabel(e) };
  }

  // THE HOTTEST QUESTION IN THE GAME — profiled, not presumed: in a staged 700-body war
  // this one scan was 45% of the whole sim frame. So it walks its buckets by hand instead
  // of through nearby()'s generator: the bounding BOX of the radius touches four buckets
  // where the generator's centred square touched nine, candidates are rejected on SQUARED
  // distance (no root until a body is actually kept, and it keeps at most eight), and with
  // numeric bucket keys the whole ask allocates nothing but its answer.
  neighbours(e) {
    const out = this._nbrOut;
    out.length = 0;
    const R = MOB.neighborRadius, R2 = R * R;
    const gx0 = Math.floor((e.x - R) / REGION_SIZE), gx1 = Math.floor((e.x + R) / REGION_SIZE);
    const gz0 = Math.floor((e.z - R) / REGION_SIZE), gz1 = Math.floor((e.z + R) / REGION_SIZE);
    for (let gz = gz0; gz <= gz1; gz++) for (let gx = gx0; gx <= gx1; gx++) {
      const ids = world.regions.get(gridKey(gx, gz));
      if (!ids) continue;
      for (const id of ids) {
        const o = world.entities.get(id);
        if (!o || o === e || o.kind !== "mob") continue;
        const dx = o.x - e.x, dz = o.z - e.z;
        const d2 = dx * dx + dz * dz;
        if (d2 < R2) {
          const slot = this._nbrPool[out.length];
          slot.o = o;
          slot.d = Math.sqrt(d2);
          out.push(slot);
          if (out.length >= MOB.maxNeighbours) return out;  // a sample is enough
        }
      }
    }
    return out;
  }

  /**
   * THE WALL IS REAL FOR EVERY BODY, on every path a body can take — walking, lunging,
   * charging, being THROWN. May this creature end up at (nx, nz)?
   *
   *   wild mobs    may never end up inside a sanctuary (leaving one is always allowed —
   *                blocking the way OUT would trap a body that got in by bug or knockback).
   *   defenders    own their town's interior, but the boundary is crossed at the GATE or
   *                not at all, in either direction. They used to be simply exempt, which
   *                let a garrison chase you straight through the masonry — and a wall one
   *                side respects and the other phases through isn't a wall, it's a picture
   *                of one.
   *
   * One function, called by every mover, because the moment two copies of "can I stand
   * there" exist they will disagree — that is exactly how the knockback and the lunge came
   * to punch through walls the walk respected.
   */
  wallOk(e, nx, nz) {
    // THE WILD IS THE COMMON CASE — profiled: walls were a fifth of the whole sim, and
    // almost every ask came from a body nowhere near a town, re-deriving "no wall for
    // miles" from ring maths seven candidate headings a frame. So each body REMEMBERS
    // which settlements could possibly concern it, and re-asks only once it has strayed a
    // few strides from where it last looked. Settlement placement is a pure function of
    // the seed — the memory can never go stale by the world changing, only by the body
    // moving, and the refresh distance (4) plus the biggest single step a body takes sits
    // well inside the gather radius (10). In the open field the list is empty and the
    // whole wall question costs a length check.
    const wdx = e.x - (e._wallX ?? 1e9), wdz = e.z - (e._wallZ ?? 1e9);
    if (wdx * wdx + wdz * wdz > 16) {
      e._walls = sanctuariesNear(e.x, e.z, 10);
      e._wallX = e.x; e._wallZ = e.z;
    }
    if (e._walls.length === 0) return true;
    // NOT INSIDE THE STONE. This asked only which side of a boundary a body was on, which is
    // the right question for "may it enter the town" and no question at all about the wall
    // ITSELF — a wall is a band of solid roughly WALL_T either side of that boundary, and
    // nothing stopped a shove parking a body in the middle of it. You could watch a mob
    // standing waist-deep in masonry. A body already inside one is let out (a knockback or a
    // shape change can strand one there, and refusing every move would weld it in place).
    const w = wallBlocksIn(e._walls, nx, nz);
    if (w && Math.abs(e.y - (w.plateau + 1)) < WALL_H && !wallBlocksIn(e._walls, e.x, e.z)) return false;
    const from = sanctuaryOfIn(e._walls, e.x, e.z, 1.5);
    const to = sanctuaryOfIn(e._walls, nx, nz, 1.5);
    if (to === from) return true;                 // no boundary crossed
    if (!e.defender) return !to;                  // wild: out fine, in never
    const s = to || from;                         // whichever wall is being crossed
    // Through the gateway only: bearing from the town's centre, against the gate's arc. A
    // shade generous (×1.6) so a defender squeezing out after you never snags on the jamb.
    const d = Math.abs(((Math.atan2(nz - s.z, nx - s.x) - s.gate + Math.PI * 3) % (Math.PI * 2)) - Math.PI);
    return d < gateArc(boundaryAt(s, s.gate)) * 1.6;
  }

  /**
   * Terrain-aware move. A heightfield has no obstacles except STEEPNESS, so "pathing" here
   * means refusing to walk up a cliff and veering along it — which reads as following
   * contours and funnelling through passes, with no navmesh existing anywhere.
   */
  tryMove(e, vx, vz, dt) {
    if (e.leapT > 0) return;              // committed: stepLeaps owns the body until it lands
    if (Math.hypot(vx, vz) < 1e-4) return;
    const here = this.floorAt(e);
    for (const turn of [0, MOB.avoidArc * 0.5, -MOB.avoidArc * 0.5, MOB.avoidArc,
                        -MOB.avoidArc, MOB.avoidArc * 1.6, -MOB.avoidArc * 1.6]) {
      const c = Math.cos(turn), s = Math.sin(turn);
      const dx = (vx * c - vz * s) * dt;
      const dz = (vx * s + vz * c) * dt;
      // A step has a FLOOR as well as a ceiling now. Without the drop limit every body on a
      // sky island strolled off the edge within seconds: a fall is a negative climb, and a
      // test with only an upper bound waves it straight through.
      const rise = this.floorAt(e, e.x + dx, e.z + dz) - here;
      if (rise <= MOB.maxClimb && rise >= -MOB.maxDrop
          && this.wallOk(e, e.x + dx, e.z + dz)) {
        e.x += dx; e.z += dz;
        e.heading = Math.atan2(dx, dz);
        return;
      }
    }
    // Walled in on every heading. Jump it, or hold — but no longer just hold.
    this.tryLeap(e, vx, vz);
  }

  // `frameDt`, not `dt`: inside the per-mob loop below, `dt` is the PER-BODY step — the
  // frame's time plus whatever the distance tick skipped for this body — so that a striding
  // body moves and cools down at exactly the speed a full-rate one does. Everything outside
  // the loop runs on the raw frame time.
  update(frameDt, onPlayerHit) {
    this.frameNo = (this.frameNo | 0) + 1;
    this.warScans = 0;                 // this frame's war-rescan allowance — see the budget
    // Last frame's crowd decides THIS frame's stampede state (see tickStride) — reading
    // the count mid-loop would flip the rule partway through and tick half the crowd on
    // each side of it. One frame of lag on a threshold is invisible; a split brain isn't.
    this.stampede = (this._crowd || 0) > MOB.stampede;
    this._crowd = 0;
    // Bodies in the air move first, before any AI branch gets a chance to forget them.
    this.stepLeaps(frameDt);
    // Sweep anything you've walked away from FIRST. The nearby() loop below only sees mobs
    // within despawn range, so its `dist > despawn` cleanup never fires for mobs abandoned in
    // a ring you've left — they'd persist frozen far behind you and, because the alive budget
    // counts EVERY mob, eat the whole spawn allowance. That is why the outer rings were empty:
    // ring-0 stragglers were still holding the budget. Despawn far mobs, and drop the pack
    // homes with them so packs.size reflects only what's actually around you.
    for (const e of [...this.entities()]) {
      // DEFENDERS ARE NEVER SWEPT BY DISTANCE. A garrison lives and dies as a TOWN'S —
      // town/raid.js despawns it whole when its town leaves range, in one stroke. Sweeping
      // individuals here (even on a long leash) is how towns ended up HALF-manned: a few
      // bodies slipped past whatever cutoff was chosen, the bookkeeping saw "some alive"
      // and did nothing, and the first kill collapsed the stale state into a full re-muster
      // — the recurring "two champions, then everyone appears" glitch. The only ways a
      // defender leaves the world are dying and its whole town standing down.
      if (e.defender) continue;
      if (this.farFrom(e.x, e.y, e.z) > MOB.despawn) this.despawn(e.id);
    }
    // EMPTY CAMPS GO WITH THEIR BODIES, by the same 3D measure. Judging a camp home flat
    // while sweeping its members in 3D is the worst of both: climb to a perch, every mob on
    // the land below is swept, and their now-empty camps stay registered because they are
    // still directly underneath you. packs.size pins itself to the cap, and the spawn gate
    // (`this.packs.size < cap.packs`) then refuses to open AT ALL. The sky was not short of
    // room — it was short of permission.
    for (const [id, p] of this.packs) {
      if (this.packCount(id) === 0 && this.farFrom(p.x, p.y ?? player.y, p.z) > MOB.despawn) {
        this.packs.delete(id);
      }
    }

    // TWO COUNTS, because two different questions are being asked. `alive` is the world's
    // population, for the world's budget. `instAlive` is how many of an instance's OWN
    // defenders are on their feet — and only they may be counted against its garrison.
    //
    // Passing the global count was why walking into a dungeon left it empty: town defenders
    // are never swept by distance (they belong to their town, and raid.js keeps mustering them
    // out in the world while you are underground), so a couple of dozen of them sat in the
    // total and the room read as already full. Reloading looked like it "fixed" it only
    // because a fresh page has no leftovers at all.
    let alive = 0, instAlive = 0;
    for (const e of this.entities()) { alive++; if (e.inst) instAlive++; }

    const cap = this.budget();
    this.spawnTimer -= frameDt;
    if (alive < cap.alive && this.packs.size < cap.packs && this.spawnTimer <= 0) {
      this.spawnTimer = cap.interval;
      this.spawnPack(instAlive);
    }

    const lunged = [];
    const babies = [];
    const seenPacks = new Set();
    // Standing on holy ground ends the hunt — but a RIVAL faction's town is not holy ground
    // for you (isHostileSanctuary): its defenders hunt an intruder inside their own walls.
    // Wild mobs still can't follow you in (the ward in tryMove bars them from the ground),
    // so a rival town is a refuge from the frontier — just never from its owners.
    const inSanct = sanctuaryUnder(player.x, player.y, player.z, 0);
    const playerSafe = inSanct !== null && !isHostileSanctuary(inSanct);

    for (const e of nearby(player.x, player.z, MOB.despawn)) {
      if (e.kind !== "mob") continue;
      seenPacks.add(e.pack);

      const dx = player.x - e.x, dz = player.z - e.z;
      const dist = Math.hypot(dx, dz) || 1;
      // ...and how far up. `dist` is FLAT, which is right for spatial bookkeeping and wrong
      // for every question about fighting you: a body on the ground under an island reads as
      // being at flat distance zero, so it bit, shot and charged from two hundred blocks
      // below where you could neither see nor answer it. That is the invisible damage.
      // For MELEE that question is now answered per body: within its own head-height
      // (meleeClearY) for anything on the ground — feet above its head and it cannot touch
      // you, the same physical rule the charge enforces. A FLYER hunts at your altitude
      // (restY eases it to player.y + flyChaseLift), so its gate is DERIVED from the hover it
      // actually keeps, bob included; a second constant would be the hover written down twice,
      // and a flat gate of 1.3 would have made flyers unable to land a hit at all — their
      // resting attack height is 3.2 above you by design.
      const meleeReach = Math.abs(player.y - e.y)
        <= (e.flies ? MOB.flyChaseLift + MOB.flyBob + 0.8 : MOB.meleeClearY);
      // THE BUG THAT WORE FIVE DISGUISES. This is a DUPLICATE of the distance sweep at the
      // top of update() — and for days it was the only one of the two that still culled
      // DEFENDERS. The garrison musters when you are ~150-208 from a town's centre; walking
      // in, every defender passes through the (105, ~132] band where nearby()'s buckets
      // still yield it but this line deleted it. Spawned, then silently unspawned as you
      // approached — leaving 1-2 arbitrary survivors at the gate, and killing those
      // collapsed the stale raid state into a full next-frame re-muster: "the town only
      // has two mobs and killing them spawns everything". No death fired, so no counter
      // moved, and reloading AT a town (the only way anyone ever verified) hid it, because
      // a reload musters with every body already inside 105. Defenders leave the world by
      // DYING or by their town's atomic eviction (raid.js) — never by this line.
      // farFrom, not `dist` — `dist` is the FLAT distance every range check below rides on
      // (chase, melee, ranged) and must stay flat. Only the sweep counts altitude.
      if (this.farFrom(e.x, e.y, e.z) > MOB.despawn) { if (!e.defender) this.despawn(e.id); continue; }

      // THE DISTANCE TICK (see MOB.farTick). A far body thinks on a stride, and each think
      // covers the skipped time exactly — `dt` from here down is the per-body step. On a
      // skipped frame the body still falls, hovers and stays findable (restY + reindex);
      // it just doesn't decide anything.
      this._crowd++;
      const dt = frameDt + (e.tickDebt || 0);
      const stride = tickStride(e, dist + Math.abs(player.y - e.y) * 2, this.stampede);
      if (stride > 1 && (e.id + this.frameNo) % stride !== 0) {
        // A SKIPPED FRAME NOW COSTS NOTHING AT ALL. It used to keep restY + reindex +
        // sync "so the body still falls, hovers and stays findable" — but hovering was
        // the FLIERS (gone), falling mid-leap is stepLeaps' own pass, and a body that
        // did not move cannot have changed buckets or facing. Paying upkeep on a body
        // between thoughts was a third of the crowd's whole bill for literally no
        // observable difference.
        e.tickDebt = dt;
        continue;
      }
      e.tickDebt = 0;

      if (e.hurtT > 0) e.hurtT -= dt;
      if (e.playerHurtT > 0) e.playerHurtT -= dt;
      if (e.atkCd > 0) e.atkCd -= dt;

      // THE HERBALIST'S PULSE: while the fight is on, every few seconds the whole garrison
      // gets a slice of its health back. This is what makes the healer the PRIORITY target —
      // ignore them and the town never actually gets closer to falling.
      if (e.champion === "herbalist") {
        e.healCd = (e.healCd ?? RAID.healEvery) - dt;
        if (e.healCd <= 0 && e.aggro) {
          e.healCd = RAID.healEvery;
          let healed = false;
          for (const o of nearby(e.x, e.z, RAID.healRadius)) {
            if (o.kind !== "mob" || o.faction !== e.faction || o.hp <= 0 || o.hp >= o.maxHp) continue;
            o.hp = Math.min(o.maxHp, o.hp + o.maxHp * RAID.healFrac);
            healed = true;
          }
          if (healed) {
            this.deathPop(e.x, e.y + 1.2, e.z, 0x5fd66a);   // a green burst: the tell you learn
            sfx.cast(e.x, e.z);
          }
        }
      }
      if (e.slowT > 0) e.slowT -= dt;
      if (e.rootT > 0) e.rootT -= dt;
      if (e.flies) e.wobble += dt;       // the hover bob, independent of any wandering
      // ONE INVARIANT, checked in one place: a charge sound belongs to a charge in progress.
      // A run can be broken off by a dozen things — knockback, a root, losing you at the
      // sanctuary line, being leashed home — and most of them skip the charger branch below
      // entirely. Rather than remembering to stop the sound in every one of those, state the
      // rule once here and let every interruption obey it for free.
      if (e.rushVoice && e.rushT <= 0) { e.rushVoice.stop(); e.rushVoice = null; }
      if (e.affixes.length) runAffix(e, "onTick", dt, this.fx);

      const ux = dx / dist, uz = dz / dist;
      const homeD = Math.hypot(e.x - e.homeX, e.z - e.homeZ) || 0.001;

      // If one is somehow inside anyway — a shape changed under it, a knockback, a bug I
      // haven't found — evict it rather than leaving a hostile loose in a safe zone. The
      // polygon is star-shaped, so straight out from the centre always leaves.
      // DEFENDERS are exempt: inside the walls is their post, not an accident. (This evictor
      // was silently marching the whole garrison out of town, aggro cleared, brain skipped —
      // which is why raided towns stood there politely not fighting back.)
      const inside = e.defender ? null : sanctuaryOf(e.x, e.z, 0);
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

      // The target that OVERRIDES you — the war: the nearest enemy-faction mob. You still
      // win priority when you're the closest threat and have been noticed, so walking into
      // a melee pulls them onto you; otherwise the two camps fight each other.
      //
      // TOWN FIGHTERS ARE OUT OF THE WAR, both directions (see enemyMobNear for the other
      // half). A garrison that brawled passing camps was a garrison that could be DEAD —
      // worn away by the frontier before you ever arrived, so towns stood empty and the
      // "always manned" promise quietly broke. Guards exist for exactly one fight: yours.
      // The field war is fought by the field.
      //
      // (The old hitscan gate guards are gone from the game entirely — a town's only
      // fighters are its garrison, and its only fight is with you.)
      //
      // The war target is the expensive part (a spatial scan), so it's THROTTLED: recompute
      // the nearest enemy only every ~0.2s (staggered per mob), and between recomputes just
      // re-validate the cached one. Combat doesn't need frame-perfect target picking, and this
      // is what keeps a big battle from scanning n² enemies every frame.
      let warFoe = null;
      if (MOB.factionWar && !e.defender) {
        e.warThink = (e.warThink || 0) - dt;
        if (e.warThink <= 0) {
          // THE SCAN BUDGET — the other half of the birth-stagger above. Stagger spreads
          // the herd; the budget is the guarantee: however the clocks drift back into
          // step, a frame never runs more than its allowance of full-radius searches.
          // A body over budget just asks again in a few frames — against a 0.2s rethink
          // cadence, nobody can tell a war target acquired 50ms late.
          if (this.warScans >= MOB.warScanBudget) {
            e.warThink = 0.05;
          } else {
            this.warScans++;
            e.warThink = 0.2 + this.rng() * 0.2;
            const found = this.enemyMobNear(e, MOB.warRange);
            e.warFoeId = found ? found.id : 0;
          }
        }
        if (e.warFoeId) {
          const c = world.entities.get(e.warFoeId);
          warFoe = (c && c.hp > 0 && c.faction !== e.faction
            && Math.hypot(c.x - e.x, c.z - e.z) < MOB.warRange * 1.4) ? c : null;
        }
      }
      if (warFoe && !playerSafe && dist < MOB.noticeRange
          && dist < Math.hypot(warFoe.x - e.x, warFoe.z - e.z)) {
        warFoe = null;
        // ...and the cached war target goes with it. The distance tick reads warFoeId as
        // "this body's fight is not with the player" — a body that just chose YOU over the
        // war must not keep striding on the strength of a foe it abandoned.
        e.warFoeId = 0;
      }
      const foe = warFoe;
      const foeMob = warFoe;                                  // the override is always an enemy MOB now
      if (foe) { e.aggro = true; e.aggroT = MOB.loseInterest; }

      // YOUR OWN ARMY does not fight you. It still wars with enemy camps (foeMob above), but
      // the player is invisible to it as a target: with no enemy in reach it simply stands
      // down and goes about its business, and it never notices YOU. One flag; every
      // player-directed attack below is already gated on aggro or on `!foe`.
      const alliedToPlayer = isMyAlly(e.faction);
      if (alliedToPlayer && !foe) e.aggro = false;
      // YOUR OWN COLOURS KNOW YOU. Walk up to an allied soldier and he may hail you —
      // "Hail, soldier" — once, then holds his peace a long while. The battlefield-wide
      // courtesy budget lives in warcry.js; this is only the per-man memory of having
      // already said hello.
      if (e.hailT > 0) e.hailT -= dt;
      if (alliedToPlayer && dist < WARCRY.hailRange && !(e.hailT > 0)) {
        // ONLY A GREETING THAT HAPPENED COSTS THE COOLDOWN. This used to burn the full
        // 150s the moment it ASKED — so a refusal (the chance roll, the battlefield gap,
        // or an empty cache while the arsenal was still baking) silenced that soldier for
        // two and a half minutes having said nothing. Early on the cache is always empty,
        // so every ally near you spent their one attempt on nothing and the friendly half
        // of the war was mute while the fighting half — on a 3.5s retry — sounded fine.
        // That asymmetry was the whole bug.
        const spoke = this.onWarcry?.(e, "hail");
        e.hailT = spoke ? WARCRY.hailMobCd : 3;
      }

      // THE FIGHT KEEPS TALKING. One cry when a pack notices you was an opening line and
      // then silence for the whole scrap; these are the voices in the middle of it. Two
      // sources, one per-mob clock so nobody becomes a parrot:
      //   hunting YOU and close enough to matter  -> "fight"
      //   brawling ANOTHER CLAN within earshot    -> "war", the faction war made audible
      // Budgets live in warcry.js; this only decides who is in a position to speak.
      if (e.cryT > 0) e.cryT -= dt;
      if (!(e.cryT > 0)) {
        // Same rule as the hail: a refused line retries soon rather than muting the
        // speaker for its full turn.
        if (e.aggro && !alliedToPlayer && dist < MOB.noticeRange * 1.4) {
          e.cryT = this.onWarcry?.(e, "fight") ? WARCRY.fightMobCd : 0.8;
        } else if (warFoe && dist < WARCRY.warHearRange) {
          e.cryT = this.onWarcry?.(e, "war") ? WARCRY.warMobCd : 1.2;
        }
      }

      // Defenders watch further than a wild mob (e.notice): a garrison that only reacts when
      // you brush against it isn't defending anything.
      const noticeR = e.notice || MOB.noticeRange;
      if (e.aggro) {
        e.aggroT -= dt;
        if (dist < noticeR) e.aggroT = MOB.loseInterest;   // contact refreshes it
        // The leash is on HOME, not on you. Run far enough and they turn back — they have
        // somewhere to be, and it isn't wherever you happen to be standing.
        if (homeD > MOB.leashRange || e.aggroT <= 0) e.aggro = false;
      } else if (!alliedToPlayer && !e.noAggroPlayer && dist < noticeR) {
        // noAggroPlayer: the garrison of a town that is not YOUR enemy (a neutral visitor,
        // or before you have picked a side) watches you pass. It still fights the war.
        e.aggro = true;
        e.aggroT = MOB.loseInterest;
        this.alert(e);
        this.onWarcry?.(e, "aggro");     // sometimes the pack ANNOUNCES you (warcry.js)
      }

      // Being thrown overrides everything: no steering, no lunging, just flying. But not
      // through masonry — this was the one mover with NO wall check at all, so a shove at
      // the right angle would put a wild mob inside the walls (and the evictor would then
      // march it politely back out, which is two bugs wearing one trenchcoat).
      if (e.kT > 0) {
        e.kT -= dt;
        const f = Math.max(0, e.kT / MOB.knockTime);
        const knx = e.x + e.kx * f * dt;
        const knz = e.z + e.kz * f * dt;
        if (this.wallOk(e, knx, knz)) { e.x = knx; e.z = knz; }
        else e.kT = 0;                            // splat: the wall keeps the momentum
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
        // wallOk: defenders lunge freely inside their own walls, wild mobs can't commit
        // their way through a gateway, and NOBODY lunges through masonry.
        if (!this.wallOk(e, lx, lz)) {
          e.lungeT = 0;                       // stopped at the wall
        } else {
          e.x = lx;
          e.z = lz;
        }
        if (dist < MOB.attackRange && meleeReach && player.iframes <= 0) {
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
          // wallOk: the garrison's chargers rush freely inside their own town (the QM's
          // signature attack), wild chargers stop at the walls, nobody rushes THROUGH one.
          if (this.wallOk(e, nx, nz)) { e.x = nx; e.z = nz; }
          // Re-aim the rumble at the BODY every step. It crosses most of the gap between you
          // while it runs, and the whole point of the sound is to answer "where is it now"
          // while you are turned away mid-dodge.
          e.rushVoice?.move(e.x, e.z);
          // JUMP IT. Not `reach` — that is the global 18-block allowance, which for a charge
          // meant a hitbox taller than anything you could ever jump. A charge connects only if
          // you are within its own height of it, so clearing its head sends it under you and
          // straight into the 1.7 helpless seconds it pays for missing.
          if (dist < MOB.attackRange * 1.3 && Math.abs(player.y - e.y) <= MOB.meleeClearY
              && player.iframes <= 0) {
            onPlayerHit?.({ damage: e.damage * MOB.chargeDamage, x: e.x, z: e.z });
            runAffix(e, "onHitPlayer", this.fx);
            e.rushT = 0;
          }
          // Covers BOTH endings — running out of momentum and connecting with you. The sound
          // has to die with the threat; one that lingers is the game lying about where danger
          // is, and that costs more than having no cue at all.
          if (e.rushT <= 0) {
            e.recoverT = MOB.chargeRecover;
            e.rushVoice?.stop();
            e.rushVoice = null;
          }
        } else {
          e.windT -= dt;                        // rooted, glowing
          e.rushX = ux; e.rushZ = uz;           // aim updates until the instant it goes
          if (e.windT <= 0) {
            e.rushT = MOB.chargeTime;
            e.rushVoice = sfx.chargeRush(e.x, e.z, MOB.chargeTime + 0.5);
          }
        }
        e.y = this.restY(e);
        reindex(e);
        this.sync(e, ux, uz);
        continue;
      }

      if (e.aggro && e.caster) {
        // CASTER: hold the middle distance and throw — at its war target if it has one, at
        // you otherwise. Never lunges, never brawls.
        e.bold = false;
        const ctx = foeMob ? foeMob.x : player.x, ctz = foeMob ? foeMob.z : player.z;
        const cty = foeMob ? foeMob.y + 0.6 : player.y + 0.9;
        const cdx = ctx - e.x, cdz = ctz - e.z;
        const cdist = Math.hypot(cdx, cdz) || 1;
        const cux = cdx / cdist, cuz = cdz / cdist;
        // ITS FIGHT IS ON ITS OWN FLOOR (MOB.castVert). A target too far above or below is
        // not a target — the wind-up can't be read across floors and the band means nothing
        // vertically — so a ground-bound caster drops the hunt and goes about its business
        // rather than holding a range band forever against something it will never reach.
        // Fliers are exempt: closing that gap is what a flier IS. If the pack re-alerts it
        // next frame this clears again — the net is a body that wanders instead of churns,
        // and the moment you come back to its floor, it fights.
        if (!e.flies && Math.abs(cty - (e.y + 1.1)) > MOB.castVert) {
          e.aggro = false; e.aggroT = 0; e.burstLeft = 0;
          e.y = this.restY(e);
          reindex(e);
          this.sync(e, ux, uz);
          continue;
        }
        // CAN IT SEE YOU? Asked on its own slow, jittered clock rather than every frame.
        e.losT -= dt;
        if (e.losT <= 0) {
          e.los = terrainClear(e.x, e.y + 1.1, e.z, ctx, cty, ctz);
          e.losT = MOB.losCheck * (0.7 + this.rng() * 0.6);
        }
        // THE ADEPT'S BARRAGE: after the opening shot, the remaining fireballs stream out on
        // a short clock. Each aims at where you are NOW — five balls you dodge by MOVING,
        // and the answer the barrage teaches is line of sight, not luck.
        if (e.burstLeft > 0) {
          e.burstT -= dt;
          if (e.burstT <= 0) { this.fire(e); e.burstLeft--; e.burstT = RAID.burstGap; }
        }
        if (e.castT > 0) {
          // Winding up: rooted and glowing. Standing still IS the tell.
          e.castT -= dt;
          if (e.castT <= 0) {
            this.fire(e, foeMob);
            e.castCd = MOB.castCd;
            if (e.champion === "adept") { e.burstLeft = RAID.burst - 1; e.burstT = RAID.burstGap; }
          }
        } else {
          if (e.castCd > 0) e.castCd -= dt;
          // IT HAS TO BE ABLE TO SEE YOU. Range alone meant a caster wound up and fired
          // into the back of a mesa, over and over — the shot died on the rock so cover
          // "worked", but it looked witless and it was the source of the knocking that took
          // over the mix. Checked once, at the moment it decides to wind up, not every
          // frame: the wind-up is the tell, and breaking line of sight DURING it is meant to
          // be a dodge you earned rather than a shot that never happened.
          // TRUE distance for the shot, not the flat one. A caster may absolutely fire upward
          // at something on a ledge — that is what makes ledges contested — but a target two
          // hundred blocks overhead is out of range, and only a 3D measure knows that.
          const cdist3 = Math.hypot(cdx, cdz, cty - (e.y + 1.1));
          if (e.castCd <= 0 && cdist3 > MOB.castMin && cdist3 < MOB.castMax && e.los) {
            e.castT = MOB.castWindup;
          }

          // Keep the range band: back off when crowded, close when you've drifted too far.
          // UNLESS it cannot see you — then the band is worthless and the only thing worth
          // doing is closing, because coming around the rock is what restores the shot. This
          // is the half that stops cover being a fortress: break line of sight and the
          // casters stop shooting AND start walking at you. Cover buys a breath, not a win.
          const want = !e.los ? 1
            : cdist < MOB.castMin ? -1 : cdist > MOB.castMax * 0.75 ? 1 : 0;
          vx += cux * want * 1.4;
          vz += cuz * want * 1.4;
          vx += -cuz * e.bias * 0.6;      // and drift sideways so they're not static targets
          vz += cux * e.bias * 0.6;
        }
      } else if (e.aggro) {
        // Against an enemy mob a creature COMMITS — it closes and brawls rather than circling.
        e.bold = foeMob ? true : near.length + 1 >= MOB.packCourage;

        // Steer to a SLOT on a ring around you rather than at your feet: a pack fans out
        // and surrounds. Timid ones hold further back and circle instead of closing.
        // Everything below aims at `foe` when a guard or enemy mob has taken priority, and at
        // you otherwise — one piece of pack logic serving all three.
        const aX = foe ? foe.x : player.x, aZ = foe ? foe.z : player.z;
        const adx = aX - e.x, adz = aZ - e.z;
        const adist = Math.hypot(adx, adz) || 1;
        const aux = adx / adist, auz = adz / adist;

        const ang = Math.atan2(-adz, -adx) + e.slot + (e.bold ? 0 : e.bias * 0.35);
        // Close to attack range on an enemy mob (a brawl), surround at ring range on you/guard.
        const standoff = foeMob ? MOB.attackRange : (e.bold ? MOB.ringRadius : MOB.timidStandoff);

        // The brawl: trade blows with the enemy mob when in reach. No lunge — that's for you.
        if (foeMob && adist <= MOB.attackRange * 1.5 && e.atkCd <= 0) {
          e.atkCd = MOB.attackCd;
          this.hitMob(foeMob, e.damage * MOB.factionDamage);
        }
        const tx = aX + Math.cos(ang) * standoff;
        const tz = aZ + Math.sin(ang) * standoff;
        const rd = Math.hypot(tx - e.x, tz - e.z) || 1;
        vx += ((tx - e.x) / rd) * MOB.ringForce;
        vz += ((tz - e.z) / rd) * MOB.ringForce;

        if (e.bold && adist > MOB.attackRange * 1.4) { vx += aux * 0.9; vz += auz * 0.9; }

        // Begin a charge from mid range — too close and there is no room to read it.
        // ...and only at something roughly on its level. Flat distance alone had it committing
        // its whole 3.6s cycle, telegraph and all, at targets on decks it could never reach.
        if (!foe && e.charger && e.atkCd <= 0 && dist > MOB.attackRange * 2.5 && dist < MOB.chargeRange
            && Math.abs(player.y - e.y) <= MOB.chargeStartY) {
          e.windT = MOB.chargeWind;
          e.atkCd = MOB.attackCd * 2.2;
          this.onWarcry?.(e, "charge");  // the scream IS the telegraph (warcry.js)
          // The wind-up is the only warning you get before the one attack that can reach you
          // from off screen. The glow only works if you happen to be looking at it; the sound
          // works wherever you are facing, which is the whole reason it exists.
          sfx.chargeWind(e.x, e.z, MOB.chargeWind);
        } else if (!foe && e.bold && dist <= MOB.attackRange * 1.7 && e.atkCd <= 0
            // ...and only at someone it could actually reach. Flat distance alone had every
            // mob under every ledge committing its lunge at the air below your feet — worse
            // than wasted, because the hop is exactly what sells "you are about to be hit",
            // fired by things that could not hit you. Flyers gate on the same hover-derived
            // reach as the connect test; the grounded use lungeStartY, looser than their
            // connect gate because the ground between resolves as the lunge travels.
            && (e.flies ? meleeReach : Math.abs(player.y - e.y) <= MOB.lungeStartY)) {
          // The lunge is for YOU alone — never mid-brawl (!foe): a lunge writes position
          // directly, and aimed at another mob it would shove the fight across the field.
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
        // Flight ignores terrain entirely — that IS the advantage. Sanctuaries still hold:
        // the wall (10 high) out-tops the flight lane (8.5), so wallOk is the truth here too.
        const nx = e.x + vx * dt, nz = e.z + vz * dt;
        if (this.wallOk(e, nx, nz)) {
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
      const kid = this.spawnOne(parent.x + Math.cos(ang) * 1.6, parent.z + Math.sin(ang) * 1.6,
                    parent.pack, parent.homeX, parent.homeZ, null, parent.faction, parent.y);
      // Sky camps breed like they spawn — mostly without the bow (see spawnPack) — or an
      // island garrison quietly re-arms its artillery one birth at a time.
      const bowRoll = this.rng();
      if (kid.caster && !kid.flies && kid.y - groundY(kid.x, kid.z) > MOB.castVert
          && bowRoll >= MOB.skyCasterKeep) kid.caster = false;
      this.born++;
    }

    // Forget packs that are wiped out or left behind, so new camps can form.
    for (const id of [...this.packs.keys()]) {
      if (!seenPacks.has(id) && this.packCount(id) === 0) this.packs.delete(id);
    }

    this.updateBalls(frameDt, onPlayerHit);
    this.updateGround(frameDt);
    this.updatePops(frameDt);
    this.render();
  }

  /** Release a fireball at where the player is RIGHT NOW — no homing, so it's dodgeable. */
  fire(e, target = null) {
    const slot = this.balls.find((b) => !b.active);
    if (!slot) return;
    const sx = e.x, sy = e.y + (e.flies ? -0.6 : 1.1), sz = e.z;
    // Aim at the war target if there is one (an enemy mob), otherwise at you.
    const tx = target ? target.x : player.x;
    const ty = target ? (target.y + 0.6) : (player.y + 0.9);
    const tz = target ? target.z : player.z;
    const dx = tx - sx, dy = ty - sy, dz = tz - sz;
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
    slot.war = !!target;          // a war shot hits enemy mobs; a normal shot hits you
    slot.faction = e.faction;
    slot.defender = !!e.defender; // a garrison's fireball flies INSIDE the walls
    slot.mesh.visible = true;
    slot.mesh.position.set(sx, sy, sz);
    // A shot fired AT YOU is news. A shot fired at some other faction two hundred metres away
    // is weather — half the level and barely half the range, so the war is a texture you hear
    // around you rather than a drum kit playing over your own fight.
    sfx.cast(sx, sz, target ? 0.4 : 1, target ? 65 : 120);
  }

  /** Dying bursts and burning ground. Both hurt the PLAYER only — a mob's own affix
   *  killing its packmates would read as a bug rather than as friendly fire. */
  updateGround(dt) {
    const hurt = this.fx.damagePlayer;

    for (const f of this.fires) {
      if (!f.active) continue;
      f.t -= dt;
      f.mesh.material.opacity = 0.25 + Math.max(0, f.t / f.life) * 0.5;
      if (f.t <= 0) { f.active = false; f.mesh.visible = false; continue; }
      if (!inFireSlab(player.y, f.y) || Math.hypot(player.x - f.x, player.z - f.z) >= f.r) continue;
      if (f.friendly) {
        // YOUR SIDE'S FIRE MENDS YOU (MOB.allyFireHeal). No iframes check: a heal is not a
        // hit, and skipping it during the moment after you were struck would withhold help at
        // exactly the point you needed it most.
        player.hp = Math.min(player.maxHp, player.hp + player.maxHp * MOB.allyFireHeal * dt);
      } else if (player.iframes <= 0) {
        hurt?.(f.dps * dt, f.x, f.z, 0);                 // no knockback: it is a floor
      }
    }
  }

  updateBalls(dt, onPlayerHit) {
    for (const b of this.balls) {
      if (!b.active) continue;
      b.t -= dt;
      b.x += b.vx * dt; b.y += b.vy * dt; b.z += b.vz * dt;

      // A fireball hits whatever it touches that ISN'T on its shooter's side: YOU (always —
      // walk into a firefight and you eat the stray shots), or any enemy-faction mob. So a war
      // shot can catch you in the crossfire, and a shot aimed at you can hit a mob in the path.
      if (player.iframes <= 0
          && Math.hypot(player.x - b.x, (player.y + 0.9) - b.y, player.z - b.z) < MOB.ballRadius + PLAYER.radius) {
        onPlayerHit?.({ damage: b.dmg, x: b.x, z: b.z });
        sfx.explosion(b.x, b.z, 0.4);
        b.active = false; b.mesh.visible = false;
        continue;
      }
      let hitMobTarget = null;
      for (const o of nearby(b.x, b.z, MOB.ballRadius + MOB.radius)) {
        if (o.kind !== "mob" || o.hp <= 0 || o.faction === b.faction) continue;
        if (Math.hypot(o.x - b.x, (o.y + 0.6) - b.y, o.z - b.z) < MOB.ballRadius + MOB.radius) { hitMobTarget = o; break; }
      }
      if (hitMobTarget) {
        this.hitMob(hitMobTarget, b.dmg);
        // Same rule: someone else being hit carries far less far than you being hit.
        sfx.explosion(b.x, b.z, b.war ? 0.26 : 0.4, b.war ? 80 : 150);
        b.active = false; b.mesh.visible = false;
        continue;
      }
      // Sanctuary ground snuffs fireballs — except a DEFENDER's, whose whole battlefield is
      // the town. (The adept champion's barrage died on the spot it was cast from without
      // this, which is why hostile towns read as safe.)
      if (b.t <= 0 || solidAt(b.x, b.y, b.z) || (!b.defender && sanctuaryOf(b.x, b.z, 0))) {
        // A MISS. This is the knocking that took over the mix, and the terrain is why: on flat
        // ground a stray shot flew until it timed out, which is silent. RELIEF filled the world
        // with terraces and spires, so now every stray war shot slams into rock and every one
        // of those was as loud as a hit landing on a body. It is the least important sound in
        // the game — a dull nearby thud, or nothing.
        if (b.t > 0) sfx.explosion(b.x, b.z, 0.16, 55);
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
