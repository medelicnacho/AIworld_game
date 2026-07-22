// Thrown grenades: ballistic arc, detonate on contact with the world.
//
// Like gun.js, this knows nothing about mobs or bosses. Detonation calls back out with a
// position and a radius, and MAIN decides what that damages. Keeping the blast generic is
// what will let a soul, a boss, or a barrel take the same explosion later without this file
// learning any of their names.

import * as THREE from "three";
import { GRENADE } from "../config.js";
import { player } from "../state.js";
import { solidAt, groundY } from "../world/gen.js";
import { sfx } from "../audio/sfx.js";

const POOL = 6;
const BLAST_LIFE = 0.38;

export class Grenades {
  constructor(scene) {
    this.scene = scene;
    this.live = [];

    const geo = new THREE.IcosahedronGeometry(0.22, 0);
    for (let i = 0; i < POOL; i++) {
      const mesh = new THREE.Mesh(geo, new THREE.MeshLambertMaterial({
        color: 0x2f3a2a, emissive: 0x224400, emissiveIntensity: 0.5,
      }));
      mesh.visible = false;
      scene.add(mesh);
      this.live.push({ mesh, active: false, x: 0, y: 0, z: 0, vx: 0, vy: 0, vz: 0, fuse: 0 });
    }

    // One shared blast flash — two grenades never land in the same frame in practice.
    this.blast = new THREE.Mesh(
      new THREE.IcosahedronGeometry(1, 2),
      new THREE.MeshBasicMaterial({ color: 0xffb457, transparent: true, opacity: 0 }),
    );
    this.blast.visible = false;
    scene.add(this.blast);
    this.blastT = 0;
    this.light = new THREE.PointLight(0xffa040, 0, 30);
    scene.add(this.light);
  }

  /** Throw along the camera's aim ray with an upward bias so it arcs. Ability 1 owns the
   *  cooldown now, so this only needs a free projectile slot. */
  throwFrom(camera) {
    const slot = this.live.find((g) => !g.active);
    if (!slot) return false;

    const dir = new THREE.Vector3();
    camera.getWorldDirection(dir);

    slot.active = true;
    slot.x = player.x;
    slot.y = player.y + 1.4;
    slot.z = player.z;
    slot.vx = dir.x * GRENADE.throwSpeed;
    slot.vy = dir.y * GRENADE.throwSpeed + GRENADE.throwSpeed * GRENADE.upBias;
    slot.vz = dir.z * GRENADE.throwSpeed;
    slot.fuse = GRENADE.maxFuse;
    slot.mesh.visible = true;
    slot.mesh.position.set(slot.x, slot.y, slot.z);

    sfx.whoosh();
    return true;
  }

  /** @param {(x:number,y:number,z:number)=>void} onDetonate */
  update(dt, onDetonate) {
    for (const g of this.live) {
      if (!g.active) continue;

      g.vy += GRENADE.gravity * dt;
      const nx = g.x + g.vx * dt;
      const ny = g.y + g.vy * dt;
      const nz = g.z + g.vz * dt;
      g.fuse -= dt;

      // Contact test against the same world function collision uses — no separate collider,
      // and it can't disagree with the terrain the player is standing on.
      const hitWorld = solidAt(nx, ny, nz) || ny <= groundY(nx, nz) - 1;
      if (hitWorld || g.fuse <= 0) {
        // Detonate at the last free spot so the blast isn't buried inside a block.
        const bx = hitWorld ? g.x : nx;
        const by = hitWorld ? g.y : ny;
        const bz = hitWorld ? g.z : nz;
        this.detonate(bx, by, bz, onDetonate);
        g.active = false;
        g.mesh.visible = false;
        continue;
      }

      g.x = nx; g.y = ny; g.z = nz;
      g.mesh.position.set(nx, ny, nz);
      g.mesh.rotation.x += dt * 7;
      g.mesh.rotation.y += dt * 5;
    }

    if (this.blastT > 0) {
      this.blastT -= dt;
      const f = Math.max(0, this.blastT / BLAST_LIFE);
      this.blast.scale.setScalar(GRENADE.radius * (1.15 - f * 0.85));
      this.blast.material.opacity = f * 0.8;
      this.light.intensity = f * 24;
      if (this.blastT <= 0) { this.blast.visible = false; this.light.intensity = 0; }
    }
  }

  detonate(x, y, z, onDetonate) {
    this.blast.position.set(x, y, z);
    this.blast.visible = true;
    this.blastT = BLAST_LIFE;
    this.light.position.set(x, y + 1, z);
    sfx.explosion(x, z, 1.15);
    onDetonate?.(x, y, z);
  }
}
