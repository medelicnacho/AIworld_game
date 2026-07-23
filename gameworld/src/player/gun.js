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
    this.owned = new Set(["rifle"]);     // guns you can switch between
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
  }

  get canFire() {
    return this.cooldown <= 0 && this.reloading <= 0 && this.mag > 0;
  }

  /** Own a weapon (from a purchase) and switch to it. */
  acquire(id) {
    if (!WEAPONS[id]) return;
    this.owned.add(id);
    this.equip(id);
  }

  /** Switch to an owned weapon, resetting the magazine and any in-progress reload. */
  equip(id) {
    if (!this.owned.has(id) || !WEAPONS[id]) return;
    this.weapon = WEAPONS[id];
    this.mag = this.weapon.magSize;
    this.reloading = 0;
    this.cooldown = 0;
    this.triggerReady = true;
  }

  /** Mouse-wheel cycling through owned weapons, in WEAPONS declaration order. */
  cycle(dir = 1) {
    const order = Object.keys(WEAPONS).filter((id) => this.owned.has(id));
    if (order.length < 2) return;
    const i = order.indexOf(this.weapon.id);
    this.equip(order[(i + dir + order.length) % order.length]);
  }

  reload() {
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
  tryFire(aiming, rng, targets = [], held = true) {
    if (!held) { this.triggerReady = true; return null; }
    if (this.reloading > 0) return null;
    if (this.mag <= 0) { this.reload(); return null; }
    if (this.cooldown > 0) return null;
    // Semi-autos and pumps fire once per pull: you must let go before the next round.
    if (!this.weapon.auto && !this.triggerReady) return null;
    this.triggerReady = false;

    const w = this.weapon;
    this.cooldown = 1 / (w.fireRate * (player.hasteFire || 1));
    this.mag--;
    this.shots++;

    const o = this.camera.position;
    const fwd = new THREE.Vector3();
    this.camera.getWorldDirection(fwd);
    const spread = aiming ? w.spreadAim : w.spreadHip;
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

  update(dt) {
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
