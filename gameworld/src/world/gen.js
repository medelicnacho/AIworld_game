// Worldgen. The world is a PURE FUNCTION of (seed, coords) — D1. Nothing about terrain is
// ever saved, because it can always be re-derived.
//
// D15's hedge lives here: chunk fill writes into a 3D OCCUPANCY GRID via blockAt(), and the
// mesher meshes that grid. Today blockAt is `y <= height(x,z)`. Adding caves later means
// adding 3D noise to THIS ONE FUNCTION — the mesher, the streamer and collision never change.

import { fbm } from "../rng.js";
import {
  WORLD_SEED, CHUNK_X, CHUNK_Y, CHUNK_Z, SEA_LEVEL, BASE_HEIGHT,
  CONTINENT_SCALE, CONTINENT_AMP, HILL_SCALE, HILL_AMP, RING_SIZE, RING_WIDEN, RINGS, RELIEF,
} from "../config.js";

export const AIR = 0, STONE = 1, DIRT = 2, GRASS = 3, SAND = 4, SNOW = 5;

// Flat-shaded palette — the low-poly Minecraft look comes from hard edges and per-face
// shading, not textures. No asset pipeline needed to ship M1.
export const BLOCK_COLOR = {
  [STONE]: [0.44, 0.45, 0.48],
  [DIRT]:  [0.42, 0.31, 0.21],
  [GRASS]: [0.35, 0.55, 0.27],
  [SAND]:  [0.80, 0.74, 0.51],
  [SNOW]:  [0.90, 0.92, 0.96],
};

/**
 * Terraces, spires and chasms — the part of the land you have to read. See RELIEF.
 *
 * Everything here is still ONE HEIGHT PER COLUMN, which is the whole reason it is affordable:
 * fillChunk evaluates 256 columns, not 20,480 voxels, and that is the difference between a
 * chunk building in about a millisecond and in eighty. Overhangs and arches need true 3D
 * noise and are a separate, more expensive conversation.
 */
function relief(wx, wz, h) {
  // Ramped by ring: the Commons is where movement is taught, so it stays walkable.
  const grow = Math.min(1, tierAt(wx, wz) / RELIEF.fullTier);
  if (grow <= 0) return h;

  // TERRACES — snap toward a step, turning a smooth slope into plateaus with edges.
  const q = Math.round(h / RELIEF.terraceStep) * RELIEF.terraceStep;
  let out = h + (q - h) * RELIEF.terraceMix * grow;

  // SPIRES — ridged noise. |noise| near zero is the crest, so inverting it gives ridges
  // rather than the blobs you get from plain fbm, and the power sharpens them into fingers.
  const rn = fbm(WORLD_SEED + 4441, wx * RELIEF.spireScale, wz * RELIEF.spireScale, 3);
  const ridge = Math.max(0, 1 - Math.abs(rn) / RELIEF.spireWidth);
  out += Math.pow(ridge, RELIEF.spireSharp) * RELIEF.spireAmp * grow;

  // CHASMS — the same trick, subtracted, at a much larger scale so the cuts run for a long
  // way instead of pocking the ground with holes.
  const cn = fbm(WORLD_SEED + 9137, wx * RELIEF.chasmScale, wz * RELIEF.chasmScale, 2);
  const cut = Math.max(0, 1 - Math.abs(cn) / RELIEF.chasmWidth);
  out -= cut * cut * RELIEF.chasmDepth * grow;

  return out;
}

/** The land as the noise wrote it, before anything flattens it. */
export function rawHeight(wx, wz) {
  const continent = fbm(WORLD_SEED, wx * CONTINENT_SCALE, wz * CONTINENT_SCALE, 4);
  const hills = fbm(WORLD_SEED + 7717, wx * HILL_SCALE, wz * HILL_SCALE, 3);
  const h = relief(wx, wz, BASE_HEIGHT + continent * CONTINENT_AMP + hills * HILL_AMP);
  return Math.max(1, Math.min(CHUNK_Y - 2, Math.floor(h)));
}

// Settlements flatten the ground they stand on. gen.js cannot import sanctuary.js (sanctuary
// needs groundY from here), so the settlement list is INJECTED — one small indirection that
// keeps the dependency pointing one way instead of in a circle.
let _flatten = null;
export function setFlattenLookup(fn) { _flatten = fn; }

/**
 * Terrain height, with settlement plateaus levelled in. A settlement sits on flat ground and
 * the land eases into it over the surrounding margin, so you get a buildable plain rather
 * than streets running up a hillside — and no cliff at the boundary either.
 */
export function heightAt(wx, wz) {
  const h = rawHeight(wx, wz);
  if (!_flatten) return h;
  const c = _flatten(wx, wz);
  if (!c) return h;
  const d = Math.hypot(wx - c.x, wz - c.z);
  if (d >= c.flatR) return h;
  // Flat all the way out to the FURTHEST wall corner, not to the nominal radius — the wall
  // reaches past r, and blending from r left its outermost corners standing on wild ground.
  const inner = c.flatInner;
  if (d <= inner) return c.plateau;
  // Smoothstep across the margin: flat inside the walls, blending back to the wild land.
  const t = (d - inner) / (c.flatR - inner);
  const e = t * t * (3 - 2 * t);
  return Math.round(c.plateau + (h - c.plateau) * e);
}

/**
 * D8: which difficulty band a column sits in — UNCAPPED. Stats, xp and elite rates read
 * this, so the world keeps getting harder forever. In an endless world with endless levels
 * (D9), capped difficulty means your power eventually outruns everything and the frontier
 * stops meaning anything.
 */
/** Distance from spawn at which tier `t` begins. Bands widen as you go out. */
export function tierStart(t) {
  return RING_SIZE * (t + RING_WIDEN * t * (t - 1) / 2);
}

export function tierWidth(t) {
  return RING_SIZE * (1 + RING_WIDEN * t);
}

export function tierAt(wx, wz) {
  const d = Math.sqrt(wx * wx + wz * wz);
  // Closed-form inverse of tierStart (a quadratic in t) — this is called thousands of
  // times a frame by mob steering, so it must not be a loop.
  const k = RING_WIDEN;
  if (k <= 0) return Math.floor(d / RING_SIZE);
  const b = 1 - k / 2;
  return Math.max(0, Math.floor((-b + Math.sqrt(b * b + 2 * k * d / RING_SIZE)) / k));
}

/**
 * Difficulty ACCELERATION, as an inflated "effective ring".
 *
 * The per-ring multipliers in config are a FLAT exponential, tuned to hold time-to-kill
 * roughly constant against a levelling player. This bends that curve: the first ring past
 * the Commons is barely harder, and each ring after bites much faster — "not much harder,
 * then way harder super fast". It grows QUADRATICALLY, and the `(ring - 1)` term is what
 * keeps ring 1 unchanged (it is zero there), so only DEPTH compounds. HP, damage and
 * crowding all read their pressure through here with their own `ramp`, so one shape governs
 * the whole gradient and there is a single place to make the deep meaner or kinder.
 */
export function ringPressure(ring, ramp) {
  if (ring <= 1) return ring;
  return ring + ramp * ring * (ring - 1);
}

/** The NAME and colour of that band — capped, because we only wrote six names. */
export function ringAt(wx, wz) {
  return Math.min(RINGS.length - 1, tierAt(wx, wz));
}

/**
 * What is in the SKY and what is missing UNDERNEATH at this column — the whole of the world's
 * third dimension, answered per column rather than per voxel.
 *
 * Both features are a 2D mask with a vertical profile: where the mask is strong there is a
 * lens (of stone in the air, of air in the stone), thickest at the middle and tapering to
 * nothing at the rim. That is the trick that makes this affordable at all — fillChunk keeps
 * ONE evaluation per column instead of one per voxel, which is the difference between a
 * chunk building in about a millisecond and in eighty.
 *
 * Returns null when the column is plain, which is most of them, so the common case costs a
 * comparison.
 */
export function featuresAt(wx, wz, h) {
  const grow = Math.min(1, tierAt(wx, wz) / RELIEF.fullTier);
  if (grow <= 0) return null;              // the Commons keeps a plain sky and solid ground

  const I = RELIEF.island, H = RELIEF.hollow;
  let out = null;

  if (tierAt(wx, wz) >= I.fromTier) {
    const im = fbm(WORLD_SEED + 3301, wx * I.scale, wz * I.scale, 3);
    const iStr = Math.min(1, Math.max(0, (im - I.thresh) / (I.peak - I.thresh)));
    if (iStr > 0) {
      // Thickness from the mask, so the middle of an island is deep and its rim is a lip.
      const half = (I.minThick + (I.thick - I.minThick) * iStr) * 0.5;
      // Altitude from its own slower field: neighbours sit at DIFFERENT levels, which is
      // what turns a scatter of platforms into something you climb by jumping between.
      const lv = fbm(WORLD_SEED + 5507, wx * I.levelScale, wz * I.levelScale, 2);
      const cy = I.baseY + (lv * 0.5 + 0.5) * I.spanY;
      // Flat, always: if the land has risen into where this one would sit, there is simply
      // no island here. Nudging it upward instead would warp it into a sheet draped over the
      // hill, which is the thing an island must never look like.
      if (cy - half >= h + I.gapMin && cy + half <= CHUNK_Y - 2) {
        out = { iLo: cy - half, iHi: cy + half };
      }
    }
  }

  const hm = fbm(WORLD_SEED + 7703, wx * H.scale, wz * H.scale, 3);
  const hStr = Math.max(0, (hm - H.thresh) / (1 - H.thresh)) * grow;
  if (hStr > 0.02) {
    const half = H.thick * hStr;
    const cy = h - H.lid - H.depth * hStr;
    out = out || {};
    out.hLo = cy - half;
    out.hHi = Math.min(cy + half, h - H.lid);   // the LID is never carved
  }
  return out;
}

/** THE FILL FUNCTION (D15). Everything else in the engine reads the world through here. */
export function blockAt(wx, wy, wz, h = heightAt(wx, wz), f = featuresAt(wx, wz, h)) {
  if (wy < 0 || wy >= CHUNK_Y) return AIR;
  // THE SKY comes first: an island is the only thing that can be solid above the land.
  if (f && f.iHi !== undefined && wy >= f.iLo && wy <= f.iHi) {
    return wy >= f.iHi - 1 ? GRASS : STONE;
  }
  if (wy > h) return AIR;
  // Bitten out from under the lid — an overhang you can walk beneath, never a hole in the
  // surface you walk on.
  if (f && f.hHi !== undefined && wy >= f.hLo && wy <= f.hHi) return AIR;
  if (wy === h) {
    if (h <= SEA_LEVEL + 1) return SAND;
    if (h > 52) return SNOW;
    return GRASS;
  }
  if (wy > h - 4) return DIRT;
  return STONE;
}

/**
 * WHICH GROUND? The question a world with more than one surface per column has to answer.
 *
 * groundY returns the land's own surface and always will — it is what spawning and the map
 * mean by "the ground here". But a body standing on an island, or under an overhang, is on a
 * DIFFERENT floor, and asking groundY where it should stand would walk it off into the air or
 * up through a roof. This returns the surface nearest the height it is already at.
 *
 * Computed from the column's structure rather than scanned voxel by voxel, so it costs the
 * same as asking for the height.
 */
export function surfaceNear(wx, wz, yRef) {
  const x = Math.floor(wx), z = Math.floor(wz);
  const h = heightAt(x, z);
  const f = featuresAt(x, z, h);
  if (!f) return h + 1;
  let best = h + 1, bestD = Math.abs(yRef - (h + 1));
  const consider = (y) => {
    const d = Math.abs(yRef - y);
    if (d < bestD) { best = y; bestD = d; }
  };
  if (f.iHi !== undefined) consider(Math.floor(f.iHi) + 1);     // the island's top
  // The floor of a hollow is only standable if there is actually rock under it.
  if (f.hLo !== undefined && f.hLo > 1) consider(Math.floor(f.hLo));
  return best;
}

export function solidAt(wx, wy, wz) {
  return blockAt(Math.floor(wx), Math.floor(wy), Math.floor(wz)) !== AIR;
}

/** Ground height a body standing at (x,z) rests on. */
export function groundY(wx, wz) {
  return heightAt(Math.floor(wx), Math.floor(wz)) + 1;
}

export const idx = (x, y, z) => (y * CHUNK_Z + z) * CHUNK_X + x;

/**
 * Fill one chunk's occupancy grid.
 * Heights are computed once per COLUMN (256 fbm evaluations), not per voxel (20,480) —
 * the difference between a chunk building in ~1ms and ~80ms.
 */
export function fillChunk(cx, cz) {
  const blocks = new Uint8Array(CHUNK_X * CHUNK_Y * CHUNK_Z);
  const heights = new Int16Array(CHUNK_X * CHUNK_Z);
  const ox = cx * CHUNK_X, oz = cz * CHUNK_Z;
  for (let z = 0; z < CHUNK_Z; z++) {
    for (let x = 0; x < CHUNK_X; x++) {
      const h = heightAt(ox + x, oz + z);
      const f = featuresAt(ox + x, oz + z, h);
      heights[z * CHUNK_X + x] = h;
      // Up to the LAND, or up to the island floating over it — whichever is higher. The
      // loop used to stop at h, which is exactly the assumption a sky full of rock breaks.
      const top = f && f.iHi !== undefined ? Math.min(CHUNK_Y - 1, Math.ceil(f.iHi)) : h;
      for (let y = 0; y <= top; y++) blocks[idx(x, y, z)] = blockAt(ox + x, y, oz + z, h, f);
    }
  }
  return { blocks, heights, cx, cz, ox, oz };
}
