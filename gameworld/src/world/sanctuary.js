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
import { WORLD_SEED, RING_SIZE } from "../config.js";
import { hash2, rand2, mulberry32 } from "../rng.js";
import { groundY } from "./gen.js";

export const CELL = 620;          // one candidate sanctuary per cell of this size
export const CHANCE = 0.62;       // ...but not every cell has one
export const RADIUS = 46;         // a town you walk around inside, not a pen
export const WALL_T = 1.7;        // wall thickness
export const WALL_H = 10;         // far above any jump height, at any level
export const GATE_WIDTH = 9;      // the opening, in WORLD UNITS — see gateArc()
export const CORNERS = [5, 9];    // a town has this many corners
const SEG_W = 1.5;                // width of one wall block
const KEEP = 2;                   // cells around the player kept built

/**
 * The gate as an ANGLE, derived from a fixed width. Specifying the arc directly meant the
 * opening grew with the town — at r=46 the old 0.42rad would have been a 19-unit hole in
 * the wall. A gateway should be a doorway at any size.
 */
export const gateArc = (r) => GATE_WIDTH / r;

/**
 * A town's outline: corners at jittered angles and radii, sorted by angle.
 *
 * Sorting by angle makes the polygon STAR-SHAPED about its centre by construction, which
 * is what lets the boundary be answered as "how far is the wall along this bearing" — one
 * ray-segment solve, no point-in-polygon scan, and collision that cannot disagree with the
 * mesh because both read the same function.
 */
function makeShape(rng) {
  const n = CORNERS[0] + Math.floor(rng() * (CORNERS[1] - CORNERS[0] + 1));
  const corners = [];
  for (let i = 0; i < n; i++) {
    // Even spacing plus jitter: irregular, but never two corners on top of each other.
    const ang = (i / n) * Math.PI * 2 + (rng() - 0.5) * (Math.PI * 2 / n) * 0.6;
    const r = RADIUS * (0.68 + rng() * 0.58);
    corners.push({ ang, r, x: Math.cos(ang) * r, z: Math.sin(ang) * r });
  }
  corners.sort((a, b) => a.ang - b.ang);
  return corners;
}

/** Distance from the centre to the wall along a bearing — the polygon's radius function. */
export function boundaryAt(s, theta) {
  const c = s.corners, n = c.length;
  let t = theta;
  while (t < c[0].ang) t += Math.PI * 2;
  while (t >= c[0].ang + Math.PI * 2) t -= Math.PI * 2;
  let i = 0;
  for (let k = 0; k < n; k++) {
    const a0 = c[k].ang, a1 = k + 1 < n ? c[k + 1].ang : c[0].ang + Math.PI * 2;
    if (t >= a0 && t < a1) { i = k; break; }
  }
  const A = c[i], B = c[(i + 1) % n];
  // Ray from the centre meets the edge A->B. Straight edges, so towns have real corners
  // rather than a wobbly circle.
  const ex = B.x - A.x, ez = B.z - A.z;
  const dx = Math.cos(t), dz = Math.sin(t);
  const den = dx * ez - dz * ex;
  if (Math.abs(den) < 1e-9) return A.r;
  const hit = (A.x * ez - A.z * ex) / den;
  return hit > 0 ? hit : A.r;
}

/**
 * One guaranteed town per tier, placed at a random bearing somewhere inside that tier's
 * band. The grid towns are scattered by luck, which means a whole ring can come up empty —
 * and a tier with nowhere to resupply is a tier you cannot push into. This makes "there is
 * always somewhere out there" a rule rather than a probability.
 */
export function tierSanctuary(tier) {
  if (tier < 1) return null;             // tier 0 is the spawn town, forced below
  const key = `t${tier}`;
  if (_cache.has(key)) return _cache.get(key);
  const rng = mulberry32(hash2(WORLD_SEED ^ 0x7139, tier, 0));
  const ang = rng() * Math.PI * 2;
  // Kept off the band edges so it clearly belongs to this tier and not the next one.
  const r = RING_SIZE * (tier + 0.25 + rng() * 0.5);
  const corners = makeShape(rng);
  const v = {
    id: key,
    x: Math.cos(ang) * r, z: Math.sin(ang) * r,
    r: RADIUS, corners,
    rMin: Math.min(...corners.map((c) => c.r)),
    rMax: Math.max(...corners.map((c) => c.r)),
    gate: rng() * Math.PI * 2,
  };
  _cache.set(key, v);
  return v;
}

const _cache = new Map();

/** The sanctuary for a grid cell, or null. Deterministic, and memoised because the mob
 *  steering asks about sanctuaries thousands of times a frame. */
export function sanctuaryAt(cx, cz) {
  const key = `${cx},${cz}`;
  if (_cache.has(key)) return _cache.get(key);
  const v = _build(cx, cz);
  _cache.set(key, v);
  return v;
}

function _build(cx, cz) {
  // Spawn always has one: you should never have to find your first refuge.
  const forced = cx === 0 && cz === 0;
  if (!forced && rand2(WORLD_SEED ^ 0x5A1E, cx, cz) > CHANCE) return null;
  const jx = rand2(WORLD_SEED ^ 0x11, cx, cz);
  const jz = rand2(WORLD_SEED ^ 0x22, cx, cz);
  const x = forced ? 96 : cx * CELL + 60 + jx * (CELL - 120);
  const z = forced ? 34 : cz * CELL + 60 + jz * (CELL - 120);
  const corners = makeShape(mulberry32(hash2(WORLD_SEED ^ 0x54A9E, cx, cz)));
  return {
    id: `${cx},${cz}`,
    x, z, r: RADIUS, corners,
    rMin: Math.min(...corners.map((c) => c.r)),
    rMax: Math.max(...corners.map((c) => c.r)),
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
  // Plus the guaranteed per-tier towns. Only the bands this query actually reaches are
  // considered, so this stays a handful of checks however far out you are.
  const d = Math.hypot(x, z);
  const tLo = Math.max(1, Math.floor((d - range) / RING_SIZE));
  const tHi = Math.floor((d + range) / RING_SIZE);
  for (let t = tLo; t <= tHi; t++) {
    const s = tierSanctuary(t);
    if (s && Math.hypot(s.x - x, s.z - z) <= range) out.push(s);
  }
  return out;
}

/** The sanctuary containing this point (within `margin` of its wall), or null. */
export function sanctuaryOf(x, z, margin = 0) {
  for (const s of sanctuariesNear(x, z, CELL)) {
    const dx = x - s.x, dz = z - s.z;
    const d = Math.hypot(dx, dz);
    if (d > s.rMax + margin) continue;                 // cheap reject before the real test
    if (d <= boundaryAt(s, Math.atan2(dz, dx)) + margin) return s;
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
    const dx = x - s.x, dz = z - s.z;
    const d = Math.hypot(dx, dz);
    if (d < s.rMin - WALL_T || d > s.rMax + WALL_T) continue;
    const ang = Math.atan2(dz, dx);
    const R = boundaryAt(s, ang);
    if (d < R - WALL_T || d > R + WALL_T) continue;
    if (angDiff(ang, s.gate) < gateArc(R)) continue;   // the gate
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
    this.wallGeo = new THREE.BoxGeometry(SEG_W, WALL_H, WALL_T * 2);
    this.wallMat = new THREE.MeshLambertMaterial({ color: 0x9aa7b4 });
    this.rng = mulberry32(0x5A17);
  }

  build(s) {
    const group = new THREE.Group();

    // Walk the polygon EDGE BY EDGE, laying blocks along each straight run and turning at
    // the corners. Blocks overlap slightly (0.9 spacing on a 1.5 block) so no seam opens up,
    // least of all at a corner where two runs meet at an angle.
    const perim = s.corners.reduce((acc, c, i) => {
      const nx = s.corners[(i + 1) % s.corners.length];
      return acc + Math.hypot(nx.x - c.x, nx.z - c.z);
    }, 0);
    const wall = new THREE.InstancedMesh(
      this.wallGeo, this.wallMat, Math.ceil(perim / (SEG_W * 0.9)) + s.corners.length + 8);
    const m = new THREE.Matrix4(), q = new THREE.Quaternion(), up = new THREE.Vector3(0, 1, 0);
    const pos = new THREE.Vector3(), one = new THREE.Vector3(1, 1, 1);
    let n = 0;
    for (let i = 0; i < s.corners.length; i++) {
      const A = s.corners[i], B = s.corners[(i + 1) % s.corners.length];
      const ex = B.x - A.x, ez = B.z - A.z;
      const len = Math.hypot(ex, ez);
      const steps = Math.max(1, Math.ceil(len / (SEG_W * 0.9)));
      const yaw = -Math.atan2(ez, ex);        // lay the block's width along the edge
      for (let k = 0; k <= steps; k++) {
        const f = k / steps;
        const lx = A.x + ex * f, lz = A.z + ez * f;
        if (angDiff(Math.atan2(lz, lx), s.gate) < gateArc(Math.hypot(lx, lz))) continue;
        const wx = s.x + lx, wz = s.z + lz;
        q.setFromAxisAngle(up, yaw);
        // BoxGeometry is centred, so the box is raised by half its height or the wall sinks
        // into the ground — which is why it read as knee-high before.
        m.compose(pos.set(wx, groundY(wx, wz) + WALL_H / 2 - 0.6, wz), q, one);
        if (n < wall.instanceMatrix.count) wall.setMatrixAt(n++, m);
      }
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
