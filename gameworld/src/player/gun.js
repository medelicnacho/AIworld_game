// D6/D5 — the hitscan weapon family.
//
// One ray, fired FROM THE CAMERA THROUGH THE CROSSHAIR in every camera state. That is the
// whole reason camera.js sets orientation from yaw/pitch instead of lookAt(): the crosshair
// ray is exactly camera-forward, so what the reticle covers is what the bullet hits, and
// third-person and first-person share one shooting path rather than two.
//
// The gun holds a WEAPON (a config from WEAPONS) and nothing about a specific one — a shotgun
// is nine of the same ray with a wide cone, a sniper is one ray that reaches the horizon, an
// MG is the rifle with a bigger belt and a faster clock. Swap `this.weapon` and it all
// follows. tryFire returns the list of targets its pellets struck (with per-pellet damage),
// so MAIN applies damage the same way for one pellet or nine.

import * as THREE from "three";
import { WEAPONS } from "../config.js";
import { player } from "../state.js";
import { raycastVoxel } from "../world/raycast.js";
import { solidAt, groundY } from "../world/gen.js";
import { sfx } from "../audio/sfx.js";

/** Ray-vs-sphere, nearest hit closer than `maxT`. Returns {id, t, tag} or null. */
function nearestTarget(o, dir, targets, maxT) {
  let best = null;
  for (const s of targets) {
    const ox = o.x - s.x, oy = o.y - s.y, oz = o.z - s.z;
    const b = ox * dir.x + oy * dir.y + oz * dir.z;
    const c = ox * ox + oy * oy + oz * oz - s.r * s.r;
    const disc = b * b - c;
    if (disc < 0) continue;
    const sq = Math.sqrt(disc);
    let t = -b - sq;
    if (t < 0) t = -b + sq;          // origin inside the sphere: point-blank still counts
    if (t < 0 || t >= maxT) continue;
    if (!best || t < best.t) best = { id: s.id, t, tag: s.tag };
  }
  return best;
}

const TRACER_LIFE = 0.055;
const IMPACT_LIFE = 2.5;
const IMPACT_POOL = 24;
const TRACER_POOL = 9;            // enough for the widest pellet count

export class Gun {
  constructor(scene, camera) {
    this.scene = scene;
    this.camera = camera;
    this.weapon = WEAPONS.rifle;         // the starter
    this.owned = new Set(["rifle"]);     // every weapon you have ever bought
    // THE LOADOUT: the two you actually CARRY. Owning five weapons and wheeling through all
    // of them made the wheel a roulette — mid-fight you spun past three wrong answers to
    // reach the right one, and no purchase ever cost you anything. Two carried weapons makes
    // the wheel a fast TOGGLE between tools you chose, and makes "which two" a real decision
    // — the same opportunity-cost rule the factions run on. The rest wait in the bag.
    this.loadout = ["rifle"];
    this.mag = this.weapon.magSize;
    this.cooldown = 0;
    this.reloading = 0;
    this.recoil = 0;          // pitch kick still owed back
    this.shots = 0;
    this.triggerReady = true; // semi-autos must release between shots; this is the latch
    this.pumpT = 0;           // countdown to the pump/bolt rack sound after a pump-weapon shot

    // A pool of tracers, so a shotgun can draw all nine pellet lines at once.
    this.tracers = [];
    for (let i = 0; i < TRACER_POOL; i++) {
      const line = new THREE.Line(
        new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]),
        new THREE.LineBasicMaterial({ color: 0xffe6a8, transparent: true, opacity: 0 }),
      );
      line.frustumCulled = false;
      scene.add(line);
      this.tracers.push({ line, t: 0 });
    }

    this.flash = new THREE.PointLight(0xffd9a0, 0, 14);
    scene.add(this.flash);

    // Impact marks are pooled and recycled — allocating a mesh per shot would sawtooth the
    // GC right when the frame budget matters most.
    this.impacts = [];
    const geo = new THREE.PlaneGeometry(0.28, 0.28);
    for (let i = 0; i < IMPACT_POOL; i++) {
      const m = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({
        color: 0x1a1a1a, transparent: true, opacity: 0, depthWrite: false,
      }));
      m.visible = false;
      scene.add(m);
      this.impacts.push({ mesh: m, t: 0 });
    }
    this.impactI = 0;

    // --- faction weapons ------------------------------------------------------------
    // THE SWING. An arc drawn in front of you rather than a tracer, because a melee hit has
    // no travel to show — what needs showing is the SHAPE of what you just hit, so the cone
    // you see is the cone that connected.
    //
    // The geometry is AUTHORED FACING THE WAY THE CHARACTER FACES (−Z at yaw 0, same as the
    // body and the camera), so drawing it is `rotation.y = player.yaw` — the identical
    // rotation the body mesh uses, which makes disagreement impossible. The first version
    // was authored along +X and then rotated by a NEGATED yaw: ninety degrees off AND
    // turning the wrong way as you turned, so the arc wandered behind and beside you —
    // a drawn hitbox that lies is worse than none at all.
    this.swingFx = 0;
    this.swingArc = (() => {
      const w = WEAPONS.cleaver;
      const half = (w.coneDeg * Math.PI / 180) / 2;      // the drawn arc IS the config cone
      const g = new THREE.RingGeometry(0.8, w.range, 26, 1, Math.PI / 2 - half, half * 2);
      g.rotateX(-Math.PI / 2);
      const m = new THREE.Mesh(g, new THREE.MeshBasicMaterial({
        color: 0xdfe8ff, transparent: true, opacity: 0, side: THREE.DoubleSide, depthWrite: false,
      }));
      m.visible = false;
      scene.add(m);
      return m;
    })();

    // THE SHELLS. Pooled like every other projectile in the game — allocating a mesh per shot
    // is the GC sawtooth that ruins frame time exactly when you are firing a lot. Big and
    // glowing: a cannon shell should read as a heavy thing in the air, not a pea.
    this.shells = [];
    const shellGeo = new THREE.IcosahedronGeometry(0.55, 0);
    const shellMat = new THREE.MeshBasicMaterial({ color: 0xff7a1e });
    for (let i = 0; i < 8; i++) {
      const mesh = new THREE.Mesh(shellGeo, shellMat);
      mesh.visible = false;
      scene.add(mesh);
      this.shells.push({ mesh, active: false, x: 0, y: 0, z: 0, vx: 0, vy: 0, vz: 0, t: 0 });
    }
    this.shellLight = new THREE.PointLight(0xff8a2e, 0, 20);
    scene.add(this.shellLight);

    // THE BURST. The cannon had no explosion visual at all — only a sound and invisible
    // damage — so a huge blast landed with nothing to see. A pool of shells can put a couple
    // of bursts up at once, so these are pooled too: an expanding ring on the ground and a
    // bright shell of light, both scaled to the actual blast radius so what you SEE is the
    // area that was hit.
    this.bursts = [];
    const ringGeo = new THREE.RingGeometry(0.35, 1, 40);
    ringGeo.rotateX(-Math.PI / 2);
    const flashGeo = new THREE.IcosahedronGeometry(1, 2);
    for (let i = 0; i < 6; i++) {
      const ring = new THREE.Mesh(ringGeo, new THREE.MeshBasicMaterial({
        color: 0xffb046, transparent: true, opacity: 0, side: THREE.DoubleSide,
        depthWrite: false, blending: THREE.AdditiveBlending,
      }));
      const flash = new THREE.Mesh(flashGeo, new THREE.MeshBasicMaterial({
        color: 0xff8a2e, transparent: true, opacity: 0, depthWrite: false,
        blending: THREE.AdditiveBlending,
      }));
      ring.visible = false; flash.visible = false;
      scene.add(ring); scene.add(flash);
      this.bursts.push({ ring, flash, t: 0, r: 1, x: 0, y: 0, z: 0 });
    }
    this.burstLight = new THREE.PointLight(0xffa040, 0, 40);
    scene.add(this.burstLight);
    this.burstI = 0;

    // THE BEAM. A one-pixel line reads as a debug overlay, not a weapon — WebGL cannot
    // widen lines, so thickness has to be geometry. Two coaxial shafts: a hot core inside a
    // translucent sheath that breathes while it burns. Authored along Y with unit height, so
    // drawing it is position at the midpoint, scale to the length, rotate Y onto the ray.
    this.beamOn = false;
    this.beamEnd = new THREE.Vector3();
    this.heat = 0;
    this.overheated = 0;
    const shaft = (radius, color, opacity) => {
      const m = new THREE.Mesh(
        new THREE.CylinderGeometry(radius, radius, 1, 10, 1, true),
        new THREE.MeshBasicMaterial({
          color, transparent: true, opacity: 0, depthWrite: false,
          blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
        }),
      );
      m.visible = false;
      m.userData.maxOpacity = opacity;
      scene.add(m);
      return m;
    };
    this.beamCore = shaft(0.11, 0xffd9a8, 0.95);
    this.beamGlow = shaft(0.32, 0xff5a1e, 0.4);
    this._beamDir = new THREE.Vector3();
    this._beamQuat = new THREE.Quaternion();
    this._up = new THREE.Vector3(0, 1, 0);
    this.beamLight = new THREE.PointLight(0xff6a2a, 0, 18);
    scene.add(this.beamLight);
  }

  get canFire() {
    return this.cooldown <= 0 && this.reloading <= 0 && this.mag > 0;
  }

  /** Weapons with no magazine (the cleaver, the lance) never reload and never run dry. */
  get usesAmmo() { return (this.weapon.magSize || 0) > 0; }

  /**
   * A faction weapon is DEAD in the hands of anyone not sworn to that faction. You can own it
   * and carry it forever — leaving a faction does not confiscate its kit — but it will not
   * fire unless you wear the colours. The weapon IS the allegiance; wielding one you have
   * renounced would make the choice mean nothing.
   */
  lockedFor(faction) {
    return !!this.weapon.faction && this.weapon.faction !== faction;
  }

  /**
   * MELEE — a cone in front of you, not a ray.
   *
   * The test is angle-then-distance against the same target spheres a bullet uses, so the
   * melee weapon needs no knowledge of what a mob is and main applies the damage exactly as
   * it does for a hitscan shot. Everything inside the arc is struck, which is what makes this
   * the crowd-facing half of Iron's kit.
   */
  swing(fwd, targets) {
    const w = this.weapon;
    const cosH = Math.cos((w.coneDeg * 0.5) * Math.PI / 180);
    const vertHalf = ((w.coneVertDeg ?? 90) * 0.5) * Math.PI / 180;
    // The two axes of a swing are DIFFERENT questions, so they are tested separately.
    // Sideways: a fixed arc around where you face — a swing is wide, that is its nature.
    // Vertically: a band CENTRED ON YOUR PITCH, so looking up cuts high and looking down
    // cuts low. The first version used one rigid cone tilted whole by the camera, which did
    // the opposite of aiming: looking down at things crowding your feet pointed the cone
    // into the ground and whiffed straight through them.
    const fh = Math.hypot(fwd.x, fwd.z) || 1e-6;
    const fx = fwd.x / fh, fz = fwd.z / fh;      // facing, flattened
    const aimEl = Math.atan2(fwd.y, fh);         // how far up or down you are looking
    // Reach is measured from the PLAYER, not the camera. In third person the camera floats
    // ~4 units behind you, so a camera-origin cone would end roughly where your own body
    // begins — every swing whiffing at things plainly in front of you.
    const ox = player.x, oy = player.y + 1.1, oz = player.z;
    const struck = [];
    const seen = new Set();
    for (const s of targets) {
      if (seen.has(s.id)) continue;              // flyers list two spheres; one hit each
      const dx = s.x - ox, dy = s.y - oy, dz = s.z - oz;
      const d = Math.hypot(dx, dy, dz);
      if (d > w.range + s.r) continue;
      // Point-blank grace only for something genuinely ON you — bodies touch at about 0.9,
      // so this is overlap, not proximity. Any looser and the swing quietly clips things
      // standing behind your shoulder, which reads as the cone not being where it is drawn.
      if (d > 1.0) {
        const dh = Math.hypot(dx, dz);
        if (dh > 1e-6 && (dx * fx + dz * fz) / dh < cosH) continue;      // outside the arc
        if (Math.abs(Math.atan2(dy, dh) - aimEl) > vertHalf) continue;   // outside the band
      }
      seen.add(s.id);
      struck.push({ id: s.id, tag: s.tag });
    }
    return struck;
  }

  /**
   * BEAM — one ray that does NOT stop at the first thing it touches.
   *
   * The difference from a bullet is the whole weapon: a bullet asks "what is under the
   * crosshair", a beam asks "what is in this LINE". Terrain still stops it, so a wall is
   * still cover.
   */
  pierce(o, dir, targets, maxT) {
    const out = [];
    const seen = new Set();
    for (const s of targets) {
      if (seen.has(s.id)) continue;
      const ox = o.x - s.x, oy = o.y - s.y, oz = o.z - s.z;
      const b = ox * dir.x + oy * dir.y + oz * dir.z;
      const c = ox * ox + oy * oy + oz * oz - (s.r + this.weapon.beamRadius) ** 2;
      const disc = b * b - c;
      if (disc < 0) continue;
      const sq = Math.sqrt(disc);
      let t = -b - sq;
      if (t < 0) t = -b + sq;
      if (t < 0 || t >= maxT) continue;
      seen.add(s.id);
      out.push({ id: s.id, tag: s.tag, t });
    }
    return out.sort((a, b2) => a.t - b2.t);
  }

  /** Own a weapon (from a purchase), take it in hand. */
  acquire(id) {
    if (!WEAPONS[id]) return;
    this.owned.add(id);
    this.carry(id);
  }

  /**
   * Take an owned weapon into your hands. If both carry slots are full, it replaces the one
   * you are HOLDING — swapping what is in your hands is the intuitive read, and it means the
   * holstered weapon (the one you deliberately kept) is never silently discarded.
   */
  carry(id) {
    if (!this.owned.has(id) || !WEAPONS[id]) return;
    if (!this.loadout.includes(id)) {
      if (this.loadout.length < 2) this.loadout.push(id);
      else this.loadout[Math.max(0, this.loadout.indexOf(this.weapon.id))] = id;
    }
    this.equip(id);
  }

  /** Restore a saved loadout, keeping only weapons actually owned. */
  setLoadout(ids) {
    const clean = [...new Set(ids)].filter((x) => this.owned.has(x) && WEAPONS[x]).slice(0, 2);
    if (clean.length) this.loadout = clean;
  }

  /** Switch to a CARRIED weapon, resetting the magazine and any in-progress reload. */
  equip(id) {
    if (!this.loadout.includes(id) || !WEAPONS[id]) return;
    this.weapon = WEAPONS[id];
    this.mag = this.weapon.magSize;
    this.reloading = 0;
    this.cooldown = 0;
    this.triggerReady = true;
    // Heat belongs to the weapon, not to the player — switching away and back should not
    // launder a redlined lance into a cool one, but nor should another gun inherit its heat.
    this.beamOn = false;
  }

  /** The wheel swaps hands: with two carried weapons it is a toggle, not a carousel. */
  cycle() {
    if (this.loadout.length < 2) return;
    const other = this.loadout.find((id) => id !== this.weapon.id);
    if (other) this.equip(other);
  }

  reload() {
    if (!this.usesAmmo) return;              // the cleaver and the lance have no magazine
    if (this.reloading > 0 || this.mag === this.weapon.magSize) return;
    // Never zero. A zero-duration reload fails the `> 0` test in update() and therefore
    // never completes — the magazine stays empty forever and the gun is bricked. Whatever
    // the multipliers say, a reload takes SOME time.
    this.reloading = Math.max(0.05, this.weapon.reloadTime * (player.reloadMult ?? 1));
  }

  /**
   * @param {boolean} aiming - tightens the cone.
   * @param {Array<{id,x,y,z,r,tag}>} targets
   * @param {boolean} held - is the trigger down THIS frame (semi-autos latch on release)
   * @returns {{fired:true, damage:number, targets:Array<{id,tag}>}|null}
   */
  tryFire(aiming, rng, targets = [], held = true, dt = 1 / 60) {
    const w = this.weapon;

    // --- BEAM: continuous, so it is not a "shot" at all ------------------------------
    // It bills by the SECOND rather than by the trigger pull, and its limit is heat rather
    // than a magazine. Handled first because almost none of the shot bookkeeping applies.
    if (w.mode === "beam") {
      if (this.overheated > 0 || !held) { this.beamOn = false; return null; }
      this.beamOn = true;
      const o = this.camera.position;
      const fwd = new THREE.Vector3();
      this.camera.getWorldDirection(fwd);
      const hit = raycastVoxel(o.x, o.y, o.z, fwd.x, fwd.y, fwd.z, w.range);
      const struck = this.pierce(o, fwd, targets, hit.dist);
      const end = Math.min(hit.dist, w.range);
      this.beamEnd.set(o.x + fwd.x * end, o.y + fwd.y * end, o.z + fwd.z * end);
      // Damage is per second, so the caller multiplies nothing — dt is already in here.
      const dmg = w.dps * (aiming ? w.aimMult : 1) * dt;
      return { fired: true, beam: true, damage: dmg, targets: struck };
    }

    if (!held) { this.triggerReady = true; return null; }
    if (this.reloading > 0) return null;
    if (this.usesAmmo && this.mag <= 0) { this.reload(); return null; }
    if (this.cooldown > 0) return null;
    // Semi-autos and pumps fire once per pull: you must let go before the next round.
    if (!this.weapon.auto && !this.triggerReady) return null;
    this.triggerReady = false;

    this.cooldown = 1 / (w.fireRate * (player.hasteFire || 1));
    if (this.usesAmmo) this.mag--;
    this.shots++;

    const o = this.camera.position;
    const fwd = new THREE.Vector3();
    this.camera.getWorldDirection(fwd);
    const spread = aiming ? w.spreadAim : w.spreadHip;

    // --- MELEE: no bullet, no tracer, no travel. Just a wide arc and a shove. --------
    if (w.mode === "melee") {
      const struck = this.swing(fwd, targets);
      sfx.cleave(struck.length > 0);
      this.swingFx = 0.18;
      player.pitch += w.recoil;
      this.recoil += w.recoil * w.recoilRecover;
      return { fired: true, melee: true, damage: w.damage, knock: w.knock, targets: struck };
    }

    // --- PROJECTILE: a shell that has to GET there ----------------------------------
    if (w.mode === "projectile") {
      const dir = fwd.clone();
      if (spread > 0) {
        const up2 = new THREE.Vector3(0, 1, 0);
        const r2 = new THREE.Vector3().crossVectors(fwd, up2).normalize();
        const u2 = new THREE.Vector3().crossVectors(r2, fwd).normalize();
        const a = rng() * Math.PI * 2, rr = Math.sqrt(rng()) * spread;
        dir.addScaledVector(r2, Math.cos(a) * rr).addScaledVector(u2, Math.sin(a) * rr).normalize();
      }
      const slot = this.shells.find((s) => !s.active);
      if (slot) {
        slot.active = true;
        slot.x = player.x + dir.x * 0.7; slot.y = player.y + 1.35; slot.z = player.z + dir.z * 0.7;
        slot.vx = dir.x * w.speed; slot.vz = dir.z * w.speed;
        // A small upward launch on top of the aim so the shell ARCS rather than sagging — it
        // rises a touch, then the drop curves it back down as it travels.
        slot.vy = dir.y * w.speed + w.speed * (w.upBias || 0);
        slot.t = 4;
        slot.mesh.visible = true;
        slot.mesh.position.set(slot.x, slot.y, slot.z);
      }
      sfx.lob();
      player.pitch += w.recoil;
      this.recoil += w.recoil * w.recoilRecover;
      if (this.mag === 0) this.reload();
      return { fired: true, projectile: true, damage: 0, targets: [] };
    }
    const up = new THREE.Vector3(0, 1, 0);
    const right = new THREE.Vector3().crossVectors(fwd, up).normalize();
    const trueUp = new THREE.Vector3().crossVectors(right, fwd).normalize();

    const mx = player.x + fwd.x * 0.6, my = player.y + 1.35, mz = player.z + fwd.z * 0.6;
    const struck = [];
    const pellets = w.pellets || 1;

    for (let p = 0; p < pellets; p++) {
      const dir = fwd.clone();
      if (spread > 0) {
        // Uniform-ish disc jitter, seeded (D14) — never Math.random().
        const a = rng() * Math.PI * 2;
        const r = Math.sqrt(rng()) * spread;
        dir.addScaledVector(right, Math.cos(a) * r).addScaledVector(trueUp, Math.sin(a) * r).normalize();
      }
      const hit = raycastVoxel(o.x, o.y, o.z, dir.x, dir.y, dir.z, w.range);
      const target = nearestTarget(o, dir, targets, hit.dist);
      if (target) {
        struck.push({ id: target.id, tag: target.tag });
        const px = o.x + dir.x * target.t, py = o.y + dir.y * target.t, pz = o.z + dir.z * target.t;
        this.showTracer(p, mx, my, mz, px, py, pz);
        this.mark(px, py, pz, -dir.x, -dir.y, -dir.z);
      } else {
        this.showTracer(p, mx, my, mz, hit.px, hit.py, hit.pz);
        if (hit.hit) this.mark(hit.px, hit.py, hit.pz, hit.nx, hit.ny, hit.nz);
      }
    }

    this.flash.position.set(mx, my, mz);
    this.flash.intensity = w.pellets > 1 ? 8 : 5;
    // Each weapon has its own voice: the shotgun booms, the sniper cracks, the rest report.
    if (w.sound === "shotgun") sfx.shotgunBlast();
    else if (w.sound === "sniper") sfx.sniperCrack();
    else sfx.gunshot();
    // Pump/bolt weapons rack a beat after the shot — the satisfying "ka-chunk" that follows
    // the bang. Scheduled in update() so it lands late rather than on top of the report.
    if (w.pump) this.pumpT = 0.2;

    player.pitch += w.recoil;
    this.recoil += w.recoil * w.recoilRecover;

    if (this.mag === 0) this.reload();
    return { fired: true, damage: w.damage, targets: struck };
  }

  showTracer(i, x0, y0, z0, x1, y1, z1) {
    const slot = this.tracers[i % this.tracers.length];
    const pos = slot.line.geometry.attributes.position;
    pos.setXYZ(0, x0, y0, z0);
    pos.setXYZ(1, x1, y1, z1);
    pos.needsUpdate = true;
    slot.t = TRACER_LIFE;
  }

  mark(px, py, pz, nx, ny, nz) {
    const slot = this.impacts[this.impactI = (this.impactI + 1) % this.impacts.length];
    // Nudge off the surface so it doesn't z-fight with the block face it sits on.
    slot.mesh.position.set(px + nx * 0.01, py + ny * 0.01, pz + nz * 0.01);
    slot.mesh.lookAt(px + nx, py + ny, pz + nz);
    slot.mesh.visible = true;
    slot.t = IMPACT_LIFE;
  }

  /**
   * Fly the shells. They call back with a position when they land; MAIN decides what an
   * explosion touches, exactly as it does for grenades — this file still knows nothing about
   * what a mob is.
   */
  /** Kick off a burst flash at the impact, sized to the blast radius it represents. */
  spawnBurst(x, y, z, radius) {
    const b = this.bursts[this.burstI = (this.burstI + 1) % this.bursts.length];
    Object.assign(b, { t: 0.45, r: radius, x, y, z });
    b.ring.position.set(x, groundY(x, z) + 0.1, z);
    b.flash.position.set(x, y, z);
    b.ring.visible = true;
    b.flash.visible = true;
  }

  updateShells(dt, onBurst) {
    const w = WEAPONS.lobber;
    let lit = null;
    for (const s of this.shells) {
      if (!s.active) continue;
      s.t -= dt;
      s.vy += w.drop * dt;                 // arcs a little: flat enough to aim, slow enough to lead
      s.mesh.rotation.x += dt * 7; s.mesh.rotation.y += dt * 5;
      const nx = s.x + s.vx * dt, ny = s.y + s.vy * dt, nz = s.z + s.vz * dt;
      if (s.t <= 0 || solidAt(nx, ny, nz) || ny <= groundY(nx, nz)) {
        this.spawnBurst(s.x, s.y, s.z, w.blastRadius);
        onBurst?.(s.x, s.y, s.z);
        s.active = false;
        s.mesh.visible = false;
        continue;
      }
      s.x = nx; s.y = ny; s.z = nz;
      s.mesh.position.set(nx, ny, nz);
      lit = s;
    }
    if (lit) { this.shellLight.position.set(lit.x, lit.y, lit.z); this.shellLight.intensity = 12; }
    else this.shellLight.intensity = 0;

    // The bursts: the ring races out to the full blast radius while the light-shell flares
    // and fades, so the animation genuinely fills the area the damage covered.
    let litBurst = null;
    for (const b of this.bursts) {
      if (b.t <= 0) continue;
      b.t -= dt;
      const f = 1 - Math.max(0, b.t) / 0.45;       // 0 -> 1
      b.ring.scale.setScalar(0.4 + f * b.r);
      b.ring.material.opacity = (1 - f) * 0.85;
      b.flash.scale.setScalar(b.r * (0.35 + f * 0.5));
      b.flash.material.opacity = (1 - f) * 0.7;
      if (b.t <= 0) { b.ring.visible = false; b.flash.visible = false; }
      else litBurst = b;
    }
    if (litBurst) { this.burstLight.position.set(litBurst.x, litBurst.y + 1, litBurst.z); this.burstLight.intensity = 26 * (litBurst.t / 0.45); }
    else this.burstLight.intensity = 0;
  }

  /** Heat only exists for the lance. Everything else ignores it entirely. */
  updateHeat(dt) {
    const w = this.weapon;
    if (w.mode !== "beam") { this.heat = 0; this.overheated = 0; this.beamOn = false; return; }
    if (this.overheated > 0) {
      this.overheated -= dt;
      this.heat = Math.max(0, this.heat - w.heatDown * dt);
      return;
    }
    if (this.beamOn) {
      this.heat += w.heatUp * dt;
      // Redline. A hard cut rather than a fade, so the moment you lost the beam is a moment
      // you can point at rather than something that crept up on you.
      if (this.heat >= 1) { this.heat = 1; this.overheated = w.overheatLock; this.beamOn = false; }
    } else {
      this.heat = Math.max(0, this.heat - w.heatDown * dt);
    }
  }

  update(dt) {
    this.updateHeat(dt);

    // The beam is drawn only while it is actually burning; the swing arc fades out fast.
    if (this.beamOn && this.weapon.mode === "beam") {
      const mx = player.x, my = player.y + 1.35, mz = player.z;
      this._beamDir.set(this.beamEnd.x - mx, this.beamEnd.y - my, this.beamEnd.z - mz);
      const len = Math.max(0.01, this._beamDir.length());
      this._beamDir.normalize();
      this._beamQuat.setFromUnitVectors(this._up, this._beamDir);
      // The sheath breathes and the core flickers — a beam that holds one width reads as a
      // frozen frame rather than as energy passing through the air.
      const pulse = 1 + 0.22 * Math.sin(performance.now() * 0.02);
      for (const [m, sc] of [[this.beamCore, 1], [this.beamGlow, pulse]]) {
        m.visible = true;
        m.position.set((mx + this.beamEnd.x) / 2, (my + this.beamEnd.y) / 2, (mz + this.beamEnd.z) / 2);
        m.quaternion.copy(this._beamQuat);
        m.scale.set(sc, len, sc);
        m.material.opacity = m.userData.maxOpacity * (0.85 + 0.15 * Math.sin(performance.now() * 0.045));
      }
      this.beamLight.position.copy(this.beamEnd);
      this.beamLight.intensity = 16;
    } else if (this.beamCore.visible) {
      this.beamCore.visible = false;
      this.beamGlow.visible = false;
      this.beamLight.intensity = 0;
    }

    if (this.swingFx > 0) {
      this.swingFx -= dt;
      const f = Math.max(0, this.swingFx / 0.18);
      this.swingArc.visible = true;
      // Anchored at the same height the hit test measures from, and TILTED WITH YOUR AIM —
      // yaw and pitch together, in the same rotation recipe the camera uses. The hit cone
      // always followed the camera up and down; the drawn arc used to lie flat on the
      // ground, which taught the eye that the swing could not reach up a slope or down at
      // the small ones when it could all along. The picture and the test now share both
      // numbers, so they cannot disagree on either axis.
      this.swingArc.position.set(player.x, player.y + 1.1, player.z);
      this.swingArc.rotation.set(player.pitch, player.yaw, 0, "YXZ");
      this.swingArc.material.opacity = f * 0.5;
      this.swingArc.scale.setScalar(1 + (1 - f) * 0.15);
      if (this.swingFx <= 0) this.swingArc.visible = false;
    }

    if (this.cooldown > 0) this.cooldown -= dt;

    // The delayed pump/bolt rack: fires once when the timer crosses zero.
    if (this.pumpT > 0) {
      this.pumpT -= dt;
      if (this.pumpT <= 0) sfx.rack();
    }

    if (this.reloading > 0) {
      this.reloading -= dt;
      if (this.reloading <= 0) { this.reloading = 0; this.mag = this.weapon.magSize; }
    }

    // Recoil drifts back down — the shot kicks instantly, recovery is gradual, and the
    // fraction that never returns is what makes sustained fire climb.
    if (this.recoil > 0) {
      const back = Math.min(this.recoil, dt * 0.9);
      player.pitch -= back;
      this.recoil -= back;
    }

    for (const slot of this.tracers) {
      if (slot.t > 0) {
        slot.t -= dt;
        slot.line.material.opacity = Math.max(0, slot.t / TRACER_LIFE);
      }
    }
    if (this.flash.intensity > 0) this.flash.intensity = Math.max(0, this.flash.intensity - dt * 90);

    for (const s of this.impacts) {
      if (s.t <= 0) continue;
      s.t -= dt;
      s.mesh.material.opacity = Math.min(0.75, s.t / IMPACT_LIFE);
      if (s.t <= 0) s.mesh.visible = false;
    }
  }
}
