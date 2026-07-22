// D6/D5 — the hitscan gun.
//
// One ray, fired FROM THE CAMERA THROUGH THE CROSSHAIR in every camera state. That is the
// whole reason camera.js sets orientation from yaw/pitch instead of lookAt(): the crosshair
// ray is exactly camera-forward, so what the reticle covers is what the bullet hits, and
// third-person and first-person share one shooting path rather than two.
//
// The tracer is drawn from the muzzle for looks; the hit is decided by the camera ray.

import * as THREE from "three";
import { GUN } from "../config.js";
import { player } from "../state.js";
import { raycastVoxel } from "../world/raycast.js";
import { sfx } from "../audio/sfx.js";

/** Ray-vs-sphere, nearest hit closer than `maxT`. Returns {id, t} or null. */
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

export class Gun {
  constructor(scene, camera) {
    this.scene = scene;
    this.camera = camera;
    this.mag = GUN.magSize;
    this.cooldown = 0;
    this.reloading = 0;
    this.recoil = 0;          // pitch kick still owed back
    this.shots = 0;

    this.tracer = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]),
      new THREE.LineBasicMaterial({ color: 0xffe6a8, transparent: true, opacity: 0 }),
    );
    this.tracer.frustumCulled = false;
    scene.add(this.tracer);
    this.tracerT = 0;

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

  reload() {
    if (this.reloading > 0 || this.mag === GUN.magSize) return;
    this.reloading = GUN.reloadTime;
  }

  /**
   * @param {boolean} aiming - tightens the cone; see GUN.spreadAim.
   * @param {Array<{id:number,x:number,y:number,z:number,r:number}>} targets
   */
  tryFire(aiming, rng, targets = []) {
    if (this.reloading > 0) return null;
    if (this.mag <= 0) { this.reload(); return null; }
    if (this.cooldown > 0) return null;

    this.cooldown = 1 / GUN.fireRate;
    this.mag--;
    this.shots++;

    // Aim ray = camera forward, jittered by the spread cone.
    const dir = new THREE.Vector3();
    this.camera.getWorldDirection(dir);
    const spread = aiming ? GUN.spreadAim : GUN.spreadHip;
    if (spread > 0) {
      // Uniform-ish disc jitter, seeded (D14) — never Math.random().
      const a = rng() * Math.PI * 2;
      const r = Math.sqrt(rng()) * spread;
      const up = new THREE.Vector3(0, 1, 0);
      const right = new THREE.Vector3().crossVectors(dir, up).normalize();
      const trueUp = new THREE.Vector3().crossVectors(right, dir).normalize();
      dir.addScaledVector(right, Math.cos(a) * r).addScaledVector(trueUp, Math.sin(a) * r).normalize();
    }

    const o = this.camera.position;
    const hit = raycastVoxel(o.x, o.y, o.z, dir.x, dir.y, dir.z, GUN.range);

    // Targets are plain {id,x,y,z,r} spheres passed in by the caller — the gun never learns
    // what a mob is. A closer target wins over terrain; a target behind a wall does not.
    const target = nearestTarget(o, dir, targets, hit.dist);
    if (target) {
      hit.hit = true;
      hit.targetId = target.id;
      hit.targetTag = target.tag;     // 'boss' | 'bossWeak' | undefined for plain mobs
      hit.dist = target.t;
      hit.px = o.x + dir.x * target.t;
      hit.py = o.y + dir.y * target.t;
      hit.pz = o.z + dir.z * target.t;
      hit.nx = -dir.x; hit.ny = -dir.y; hit.nz = -dir.z;
    }

    // Muzzle sits at the body, not the camera, so the tracer reads as coming from you.
    const mx = player.x + dir.x * 0.6;
    const my = player.y + 1.35;
    const mz = player.z + dir.z * 0.6;
    this.showTracer(mx, my, mz, hit.px, hit.py, hit.pz);
    this.flash.position.set(mx, my, mz);
    this.flash.intensity = 5;

    if (hit.hit) this.mark(hit);
    sfx.gunshot();

    player.pitch += GUN.recoil;
    this.recoil += GUN.recoil * GUN.recoilRecover;

    if (this.mag === 0) this.reload();
    return hit;
  }

  showTracer(x0, y0, z0, x1, y1, z1) {
    const p = this.tracer.geometry.attributes.position;
    p.setXYZ(0, x0, y0, z0);
    p.setXYZ(1, x1, y1, z1);
    p.needsUpdate = true;
    this.tracerT = TRACER_LIFE;
  }

  mark(hit) {
    const slot = this.impacts[this.impactI = (this.impactI + 1) % this.impacts.length];
    // Nudge off the surface so it doesn't z-fight with the block face it sits on.
    slot.mesh.position.set(hit.px + hit.nx * 0.01, hit.py + hit.ny * 0.01, hit.pz + hit.nz * 0.01);
    slot.mesh.lookAt(hit.px + hit.nx, hit.py + hit.ny, hit.pz + hit.nz);
    slot.mesh.visible = true;
    slot.t = IMPACT_LIFE;
  }

  update(dt) {
    if (this.cooldown > 0) this.cooldown -= dt;

    if (this.reloading > 0) {
      this.reloading -= dt;
      if (this.reloading <= 0) { this.reloading = 0; this.mag = GUN.magSize; }
    }

    // Recoil drifts back down — the shot kicks instantly, recovery is gradual, and the
    // fraction that never returns is what makes sustained fire climb.
    if (this.recoil > 0) {
      const back = Math.min(this.recoil, dt * 0.9);
      player.pitch -= back;
      this.recoil -= back;
    }

    if (this.tracerT > 0) {
      this.tracerT -= dt;
      this.tracer.material.opacity = Math.max(0, this.tracerT / TRACER_LIFE);
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
