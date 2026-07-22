// Worldgen. The world is a PURE FUNCTION of (seed, coords) — D1. Nothing about terrain is
// ever saved, because it can always be re-derived.
//
// D15's hedge lives here: chunk fill writes into a 3D OCCUPANCY GRID via blockAt(), and the
// mesher meshes that grid. Today blockAt is `y <= height(x,z)`. Adding caves later means
// adding 3D noise to THIS ONE FUNCTION — the mesher, the streamer and collision never change.

import { fbm } from "../rng.js";
import {
  WORLD_SEED, CHUNK_X, CHUNK_Y, CHUNK_Z, SEA_LEVEL, BASE_HEIGHT,
  CONTINENT_SCALE, CONTINENT_AMP, HILL_SCALE, HILL_AMP, RING_SIZE, RING_WIDEN, RINGS,
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

/** The land as the noise wrote it, before anything flattens it. */
export function rawHeight(wx, wz) {
  const continent = fbm(WORLD_SEED, wx * CONTINENT_SCALE, wz * CONTINENT_SCALE, 4);
  const hills = fbm(WORLD_SEED + 7717, wx * HILL_SCALE, wz * HILL_SCALE, 3);
  const h = BASE_HEIGHT + continent * CONTINENT_AMP + hills * HILL_AMP;
  return Math.max(1, Math.min(CHUNK_Y - 2, Math.floor(h)));
}

// Cities flatten the ground they stand on. gen.js cannot import sanctuary.js (sanctuary
// needs groundY from here), so the city list is INJECTED — one small indirection that keeps
// the dependency pointing one way instead of in a circle.
let _cityLookup = null;
export function setCityLookup(fn) { _cityLookup = fn; }

/**
 * Terrain height, with city plateaus levelled in. A city sits on flat ground and the land
 * eases into it over the surrounding margin, so you get a buildable plain rather than
 * streets running up a hillside — and no cliff at the boundary either.
 */
export function heightAt(wx, wz) {
  const h = rawHeight(wx, wz);
  if (!_cityLookup) return h;
  const c = _cityLookup(wx, wz);
  if (!c) return h;
  const d = Math.hypot(wx - c.x, wz - c.z);
  if (d >= c.flatR) return h;
  const inner = c.r;
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

/** The NAME and colour of that band — capped, because we only wrote six names. */
export function ringAt(wx, wz) {
  return Math.min(RINGS.length - 1, tierAt(wx, wz));
}

/** THE FILL FUNCTION (D15). Everything else in the engine reads the world through here. */
export function blockAt(wx, wy, wz, h = heightAt(wx, wz)) {
  if (wy < 0 || wy >= CHUNK_Y || wy > h) return AIR;
  if (wy === h) {
    if (h <= SEA_LEVEL + 1) return SAND;
    if (h > 52) return SNOW;
    return GRASS;
  }
  if (wy > h - 4) return DIRT;
  return STONE;
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
      heights[z * CHUNK_X + x] = h;
      for (let y = 0; y <= h; y++) blocks[idx(x, y, z)] = blockAt(ox + x, y, oz + z, h);
    }
  }
  return { blocks, heights, cx, cz, ox, oz };
}
