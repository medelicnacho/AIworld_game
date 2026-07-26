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
import { WORLD_SEED, SETTLE } from "../config.js";
import { hash2, mulberry32 } from "../rng.js";
import { groundY, rawHeight, tierStart, tierWidth, tierAt, setCityLookup } from "./gen.js";

export const RADIUS = 46;         // a town you walk around inside, not a pen
export const WALL_T = 1.7;        // wall thickness
export const WALL_H = 10;         // far above any jump height, at any level
export const GATE_WIDTH = 9;      // the opening, in WORLD UNITS — see gateArc()
export const CORNERS = [5, 9];    // a town has this many corners
const SEG_W = 1.5;                // width of one wall block
const KEEP_RANGE = 900;           // how far out settlements stay built as meshes

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
const SHAPE_MIN = 0.68, SHAPE_SPAN = 0.58;
/** The furthest a corner can ever reach, as a multiple of the nominal radius. Placement
 *  needs to know how much ground a settlement might claim BEFORE its shape is rolled, and
 *  a second hardcoded 1.26 that silently disagreed with makeShape would be a trap. */
export const SHAPE_MAX = SHAPE_MIN + SHAPE_SPAN;

function makeShape(rng, radius = RADIUS) {
  const n = CORNERS[0] + Math.floor(rng() * (CORNERS[1] - CORNERS[0] + 1));
  const corners = [];
  for (let i = 0; i < n; i++) {
    // Even spacing plus jitter: irregular, but never two corners on top of each other.
    const ang = (i / n) * Math.PI * 2 + (rng() - 0.5) * (Math.PI * 2 / n) * 0.6;
    const r = radius * (SHAPE_MIN + rng() * SHAPE_SPAN);
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

/** How big a city is in tier `t` — they grow as you go out. */
export function cityRadius(t) {
  return RADIUS * (SETTLE.cityScale + SETTLE.cityGrow * t);
}

/**
 * How much ground a settlement claims, worst case — used to keep them off each other.
 *
 * For a town that is just the furthest its wall can reach. For a city it is the greater of
 * the wall and the PLATEAU, because a city levels the land under itself: a town that merely
 * cleared the walls but stood on the flattened apron would be built half on a cliff edge,
 * which looks even more broken than the overlap it replaced.
 */
export function footprint(s) {
  const wall = s.r * SHAPE_MAX;
  return s.city ? Math.max(wall, s.r * SETTLE.flatten) : wall;
}

/** Open ground left between two settlements' footprints. Walls that merely fail to
 *  intersect still read as one lumpy compound from outside; you want to see daylight. */
const CITY_GAP = 40;
// Generous, because it costs nothing: this runs once per ring and the result is memoised
// for the session. At 32 the two innermost rings — nine towns in the narrowest band — ran
// out of tries and settled for 10 units of daylight; the room was there, blind sampling
// just kept missing it.
const CITY_TRIES = 256;

/** How many ordinary towns a tier holds: 9, 15, 21, 27... — always a multiple of three, so
 *  the faction colours (dealt round-robin in tierSettlements) come out even in every ring,
 *  and climbing steeply because the outer bands are wider and should feel MORE contested,
 *  not emptier. */
export function townCount(t) {
  return t === 0 ? SETTLE.townsBase : Math.min(SETTLE.townCap, 3 + 6 * t);
}

function build(key, x, z, radius, rng, city) {
  const corners = makeShape(rng, radius);
  return {
    id: key, x, z, r: radius, corners, city,
    // WHOSE TOWN THIS IS. Towns fly one of the three colours; cities are neutral ground where
    // all three keep a house, so wherever you stand there is one place that always serves
    // you. Derived from the same seeded roll as everything else, so a town's allegiance is a
    // fact about the world rather than something stored anywhere.
    faction: city ? null : Math.floor(rng() * 3),
    // NEUTRAL ground: nobody's colour flies here and all three keep a desk. Cities are neutral
    // by nature; the spawn town is neutral by decision, because it is where the game is taught
    // and showing a new player one option out of three is a bad way to introduce a choice.
    neutral: !!city,
    rMin: Math.min(...corners.map((c) => c.r)),
    rMax: Math.max(...corners.map((c) => c.r)),
    gate: rng() * Math.PI * 2,
    // Cities stand on levelled ground; the plateau is read from the RAW land so this can
    // never feed back into itself through heightAt().
    plateau: city ? rawHeight(x, z) : 0,
    flatR: city ? radius * SETTLE.flatten : 0,
  };
}

const _tiers = new Map();

/**
 * Every settlement in a tier: a doubling number of towns, plus one city from tier 1 out.
 * Placed on evenly-spread bearings with jitter, at radii inside the band, so a ring is
 * populated all the way round rather than clumping on one side.
 */
export function tierSettlements(t) {
  if (_tiers.has(t)) return _tiers.get(t);
  const rng = mulberry32(hash2(WORLD_SEED ^ 0x7139, t, 0));
  const out = [];

  if (t === 0) {
    // The one you wake next to. Fixed, close, and small — you should never have to search
    // for your first refuge.
    const home = build("t0-home", 96, 34, RADIUS, rng, false);
    home.neutral = true;      // home belongs to nobody; all three recruit here
    home.faction = null;
    out.push(home);
  } else {
    const lo = tierStart(t), w = tierWidth(t);
    const n = townCount(t);
    // Colours are DEALT, not rolled. A random roll can hand a whole ring to one faction,
    // and a player hunting their own colour finds nothing. Round-robin from a seeded start
    // guarantees every ring holds all three — the offset just stops faction 0 from always
    // sitting at the same bearing in every tier.
    const facOff = Math.floor(rng() * 3);
    for (let i = 0; i < n; i++) {
      const ang = (i / n) * Math.PI * 2 + (rng() - 0.5) * (Math.PI * 2 / n) * 0.7;
      const r = lo + w * (0.2 + rng() * 0.6);
      const town = build(`t${t}-${i}`, Math.cos(ang) * r, Math.sin(ang) * r, RADIUS, rng, false);
      town.faction = (i + facOff) % 3;
      out.push(town);
    }
    if (t >= SETTLE.cityFromTier) {
      // THE CITY HAS TO LOOK WHERE IT IS STANDING.
      //
      // Towns are dealt onto evenly-spread bearings, so they never collide with each other.
      // The city was added later and simply took a random bearing in the same band — which
      // put a town inside the city walls in eight of the first fourteen rings, once with the
      // town almost dead centre. Nothing downstream could cope: two sets of walls through
      // each other, two garrisons sharing ground, and a neutral market inside somebody's
      // territory.
      //
      // So it looks first. Seeded candidates, take the first with room; if the ring is
      // genuinely tight, take the roomiest seen rather than fail to place a city at all —
      // homeOfTier() is a respawn point and must always answer. The FIRST candidate is drawn
      // exactly as before, so every ring that was already fine keeps the city it had.
      const cr = cityRadius(t);
      const need = Math.max(cr * SHAPE_MAX, cr * SETTLE.flatten) + CITY_GAP;
      let best = null;
      for (let k = 0; k < CITY_TRIES; k++) {
        const ang = rng() * Math.PI * 2;
        const r = lo + w * (0.35 + rng() * 0.3);
        const x = Math.cos(ang) * r, z = Math.sin(ang) * r;
        let room = Infinity;
        for (const s of out) room = Math.min(room, Math.hypot(s.x - x, s.z - z) - footprint(s));
        if (!best || room > best.room) best = { x, z, room };
        if (room >= need) break;
      }
      out.push(build(`t${t}-city`, best.x, best.z, cr, rng, true));
    }
  }
  _tiers.set(t, out);
  return out;
}

/** The city of a tier, or null — tier 0 has none, so callers fall back to the spawn town. */
export function cityOfTier(t) {
  return tierSettlements(t).find((s) => s.city) || null;
}

/** The settlement a respawn should use for a tier: its city, else its first town. */
export function homeOfTier(t) {
  return cityOfTier(t) || tierSettlements(t)[0] || tierSettlements(0)[0];
}

/** Every settlement whose centre lies within `range` of a point. */
export function sanctuariesNear(x, z, range = 220) {
  const out = [];
  const d = Math.hypot(x, z);
  const tLo = Math.max(0, tierAt(Math.max(0, d - range), 0) - 1);
  const tHi = tierAt(d + range, 0) + 1;
  for (let t = tLo; t <= tHi; t++) {
    for (const s of tierSettlements(t)) {
      if (Math.hypot(s.x - x, s.z - z) <= range + s.rMax) out.push(s);
    }
  }
  return out;
}

/** The settlement containing this point (within `margin` of its wall), or null. */
export function sanctuaryOf(x, z, margin = 0) {
  for (const s of sanctuariesNear(x, z, 0)) {
    const dx = x - s.x, dz = z - s.z;
    const dd = Math.hypot(dx, dz);
    if (dd > s.rMax + margin) continue;
    if (dd <= boundaryAt(s, Math.atan2(dz, dx)) + margin) return s;
  }
  return null;
}

// Cities level the ground they stand on; gen.js asks through this hook (injected, so the
// dependency stays one-way).
setCityLookup((x, z) => {
  const d = Math.hypot(x, z);
  for (let t = Math.max(1, tierAt(d, 0) - 1); t <= tierAt(d, 0) + 1; t++) {
    for (const s of tierSettlements(t)) {
      if (!s.city) continue;
      if (Math.hypot(s.x - x, s.z - z) < s.flatR) return s;
    }
  }
  return null;
});

const angDiff = (a, b) => Math.abs(((a - b + Math.PI * 3) % (Math.PI * 2)) - Math.PI);

/**
 * Does the wall block this point? The gateway is a gap in the ring, so the player walks in
 * and out freely — the wall is what makes the refuge FEEL like one, not what enforces it.
 */
export function wallBlocks(x, z) {
  // Range 0: sanctuariesNear already pads by each settlement's own rMax, so a wall test
  // only needs the ones it could possibly be standing in.
  for (const s of sanctuariesNear(x, z, 0)) {
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
 * How far a ray travels before a sanctuary WALL stops it, up to `maxDist`. Walls are
 * collision-only geometry (wallBlocks) — invisible to the voxel raycast the gun uses — so
 * without this a shot passes clean through a town wall as if it were a curtain. Marched
 * rather than solved, because the boundary is a star polygon; the step is coarse (a wall is
 * WALL_T thick) so it stays cheap, and wallBlocks itself early-outs the instant you are not
 * near a settlement, so ordinary field shots pay almost nothing.
 */
export function wallRayDist(ox, oy, oz, dx, dy, dz, maxDist) {
  const STEP = 0.5;
  for (let t = STEP; t <= maxDist; t += STEP) {
    const x = ox + dx * t, y = oy + dy * t, z = oz + dz * t;
    // Above the parapet the shot clears the wall entirely — over the top is not through it.
    if (y > groundY(x, z) + WALL_H) continue;
    if (wallBlocks(x, z)) return t;
  }
  return maxDist;
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
    for (const s of sanctuariesNear(px, pz, KEEP_RANGE)) {
      want.add(s.id);
      if (!this.built.has(s.id)) this.build(s);
    }
    for (const id of [...this.built.keys()]) if (!want.has(id)) this.drop(id);

  }
}
