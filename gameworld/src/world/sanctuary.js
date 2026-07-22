// Sanctuaries: walled green refuges scattered through the world.
//
// Placement is a PURE FUNCTION of the world seed (D1), like the terrain — every sanctuary
// is where it is because of its coordinates, so nothing about them is stored and they are
// in the same place every session. A coarse grid with a per-cell roll gives spacing that
// varies naturally instead of a lattice you can feel.
//
// The wall is not terrain. Terrain is read-only, so a sanctuary is an analytic shape: a
// ring with a gate arc, tested by maths rather than by voxels. That costs nothing, needs no
// re-meshing, and means the collision can never disagree with what's drawn.
//
// These are also where Stage 3's town goes: a safe ring with residents in it is exactly the
// shape a settlement needs, so the green wanderers here are placeholders for souls.

import * as THREE from "three";
import { WORLD_SEED } from "../config.js";
import { rand2, mulberry32 } from "../rng.js";
import { groundY } from "./gen.js";

export const CELL = 460;          // one candidate sanctuary per cell of this size
export const CHANCE = 0.62;       // ...but not every cell has one
export const RADIUS = 16;
export const WALL_T = 1.6;        // wall thickness
export const WALL_H = 3.6;
export const GATE_ARC = 0.42;     // radians of opening — wide enough to run through
const KEEP = 3;                   // cells around the player kept built

/** The sanctuary for a grid cell, or null. Deterministic. */
export function sanctuaryAt(cx, cz) {
  // Spawn always has one: you should never have to find your first refuge.
  const forced = cx === 0 && cz === 0;
  if (!forced && rand2(WORLD_SEED ^ 0x5A1E, cx, cz) > CHANCE) return null;
  const jx = rand2(WORLD_SEED ^ 0x11, cx, cz);
  const jz = rand2(WORLD_SEED ^ 0x22, cx, cz);
  const x = forced ? 96 : cx * CELL + 60 + jx * (CELL - 120);
  const z = forced ? 34 : cz * CELL + 60 + jz * (CELL - 120);
  return {
    id: `${cx},${cz}`,
    x, z, r: RADIUS,
    gate: rand2(WORLD_SEED ^ 0x33, cx, cz) * Math.PI * 2,
  };
}

/** Every sanctuary whose centre lies within `range` of a point. */
export function sanctuariesNear(x, z, range = CELL) {
  const out = [];
  const c0 = Math.floor((x - range) / CELL), c1 = Math.floor((x + range) / CELL);
  const d0 = Math.floor((z - range) / CELL), d1 = Math.floor((z + range) / CELL);
  for (let cz = d0; cz <= d1; cz++) {
    for (let cx = c0; cx <= c1; cx++) {
      const s = sanctuaryAt(cx, cz);
      if (s && Math.hypot(s.x - x, s.z - z) <= range) out.push(s);
    }
  }
  return out;
}

/** The sanctuary containing this point (within `margin` of its wall), or null. */
export function sanctuaryOf(x, z, margin = 0) {
  for (const s of sanctuariesNear(x, z, CELL)) {
    if (Math.hypot(s.x - x, s.z - z) <= s.r + margin) return s;
  }
  return null;
}

const angDiff = (a, b) => Math.abs(((a - b + Math.PI * 3) % (Math.PI * 2)) - Math.PI);

/**
 * Does the wall block this point? The gateway is a gap in the ring, so the player walks in
 * and out freely — the wall is what makes the refuge FEEL like one, not what enforces it.
 */
export function wallBlocks(x, z) {
  for (const s of sanctuariesNear(x, z, CELL)) {
    const d = Math.hypot(x - s.x, z - s.z);
    if (d < s.r - WALL_T || d > s.r + WALL_T) continue;
    if (angDiff(Math.atan2(z - s.z, x - s.x), s.gate) < GATE_ARC) continue;   // the gate
    return true;
  }
  return false;
}

/**
 * Builds and tears down sanctuary meshes around the player, and walks their residents.
 * Same streaming discipline as chunks: only what's near you exists as geometry.
 */
export class Sanctuaries {
  constructor(scene) {
    this.scene = scene;
    this.built = new Map();     // id -> {group, folk:[{mesh, ang, r, spd}]}
    this.wallGeo = new THREE.BoxGeometry(1.5, WALL_H, WALL_T * 2);
    this.wallMat = new THREE.MeshLambertMaterial({ color: 0x9aa7b4 });
    this.rng = mulberry32(0x5A17);
  }

  build(s) {
    const group = new THREE.Group();

    // The ring, snapped to the ground it stands on, with the gate left open.
    const segs = 46;
    const wall = new THREE.InstancedMesh(this.wallGeo, this.wallMat, segs);
    const m = new THREE.Matrix4(), q = new THREE.Quaternion(), up = new THREE.Vector3(0, 1, 0);
    const pos = new THREE.Vector3(), one = new THREE.Vector3(1, 1, 1);
    let n = 0;
    for (let i = 0; i < segs; i++) {
      const a = (i / segs) * Math.PI * 2;
      if (angDiff(a, s.gate) < GATE_ARC) continue;
      const wx = s.x + Math.cos(a) * s.r;
      const wz = s.z + Math.sin(a) * s.r;
      q.setFromAxisAngle(up, -a);
      m.compose(pos.set(wx, groundY(wx, wz) - 0.4, wz), q, one);
      wall.setMatrixAt(n++, m);
    }
    wall.count = n;
    wall.instanceMatrix.needsUpdate = true;
    group.add(wall);

    this.scene.add(group);
    this.built.set(s.id, { s, group, wall });
  }

  drop(id) {
    const b = this.built.get(id);
    if (!b) return;
    this.scene.remove(b.group);
    b.wall.dispose();
    this.built.delete(id);
  }

  update(dt, px, pz) {
    const want = new Set();
    for (const s of sanctuariesNear(px, pz, CELL * KEEP)) {
      want.add(s.id);
      if (!this.built.has(s.id)) this.build(s);
    }
    for (const id of [...this.built.keys()]) if (!want.has(id)) this.drop(id);

  }
}
