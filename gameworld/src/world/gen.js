// Worldgen. The world is a PURE FUNCTION of (seed, coords) — D1. Nothing about terrain is
// ever saved, because it can always be re-derived.
//
// D15's hedge lives here: chunk fill writes into a 3D OCCUPANCY GRID via blockAt(), and the
// mesher meshes that grid. Today blockAt is `y <= height(x,z)`. Adding caves later means
// adding 3D noise to THIS ONE FUNCTION — the mesher, the streamer and collision never change.

import { fbm } from "../rng.js";
import {
  WORLD_SEED, CHUNK_X, CHUNK_Y, CHUNK_Z, SEA_LEVEL, BASE_HEIGHT, TERRAIN_CAP,
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
  return Math.max(1, Math.min(TERRAIN_CAP, Math.floor(h)));
}

// Settlements flatten the ground they stand on. gen.js cannot import sanctuary.js (sanctuary
// needs groundY from here), so the settlement list is INJECTED — one small indirection that
// keeps the dependency pointing one way instead of in a circle.
let _flatten = null;
export function setFlattenLookup(fn) { _flatten = fn; clearColumnCache(); }
// Sky towns stand on a slab this module has to build but sanctuary.js has to decide — same
// one-way indirection as the flattening above, for the same reason.
let _skyPlatform = null;
export function setSkyPlatformLookup(fn) { _skyPlatform = fn; clearColumnCache(); }

/**
 * WHICH DECK of sky a height falls in. Deck 0 starts at the island layer's base and each is
 * RELIEF.deckH tall; below the base everything is deck 0, so the land's own sky is unchanged.
 * Negative decks would mean islands underground, which is what the hollows are for.
 */
export function deckOf(wy) {
  return Math.max(0, Math.floor((wy - RELIEF.island.baseY) / RELIEF.deckH));
}

/**
 * A COLUMN CACHE for the two expensive per-column answers.
 *
 * Both heightAt and featuresAt are pure functions of (x, z) that cost half a dozen noise
 * fields plus a settlement sweep, and the engine asks for the same column over and over: the
 * mesher re-derives every out-of-bounds neighbour once per Y level, collision samples a
 * capsule's worth of voxels several times per substep, and a sight line marches a column at a
 * time. Direct-mapped, fixed size, no allocation — a miss just recomputes.
 *
 * Only integer columns are cached. A fractional coordinate is not a column, and quietly
 * flooring one would change what callers got back rather than merely how fast they got it.
 */
const CACHE_BITS = 15, CACHE_N = 1 << CACHE_BITS, CACHE_MASK = CACHE_N - 1;
const cX = new Int32Array(CACHE_N).fill(0x7fffffff);
const cZ = new Int32Array(CACHE_N);
const cH = new Int16Array(CACHE_N);
const cF = new Array(CACHE_N);
const cD = new Int16Array(CACHE_N).fill(-1);   // which DECK the cached features belong to
const cHas = new Uint8Array(CACHE_N);
const slot = (x, z) => ((x * 73856093) ^ (z * 19349663)) & CACHE_MASK;

/** Dropped whenever the thing heightAt depends on changes — see setFlattenLookup. */
function clearColumnCache() { cHas.fill(0); cX.fill(0x7fffffff); cD.fill(-1); }

/**
 * Terrain height, with settlement plateaus levelled in. A settlement sits on flat ground and
 * the land eases into it over the surrounding margin, so you get a buildable plain rather
 * than streets running up a hillside — and no cliff at the boundary either.
 */
export function heightAt(wx, wz) {
  const int = (wx | 0) === wx && (wz | 0) === wz;
  let i = 0;
  if (int) {
    i = slot(wx, wz);
    if (cHas[i] && cX[i] === wx && cZ[i] === wz) return cH[i];
  }
  const out = heightRaw(wx, wz);
  if (int) { cX[i] = wx; cZ[i] = wz; cH[i] = out; cHas[i] = 1; cF[i] = undefined; }
  return out;
}

function heightRaw(wx, wz) {
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
export function featuresAt(wx, wz, h, deck = 0) {
  const int = (wx | 0) === wx && (wz | 0) === wz;
  let i = 0;
  if (int) {
    i = slot(wx, wz);
    // Only trust the features slot if it belongs to THIS column and has actually been filled.
    if (cHas[i] && cX[i] === wx && cZ[i] === wz && cD[i] === deck && cF[i] !== undefined) return cF[i];
  }
  const out = featuresRaw(wx, wz, h, deck);
  if (int) { cX[i] = wx; cZ[i] = wz; cH[i] = h; cHas[i] = 1; cF[i] = out; cD[i] = deck; }
  return out;
}

function featuresRaw(wx, wz, h, deck) {
  const grow = Math.min(1, tierAt(wx, wz) / RELIEF.fullTier);
  if (grow <= 0) return null;              // the Commons keeps a plain sky and solid ground

  const I = RELIEF.island, H = RELIEF.hollow;
  let out = null;

  // A SKY TOWN'S PLATFORM WINS over anything the noise wanted here. It is flat, it is exactly
  // where the town expects its ground to be, and nothing else may grow through it — an island
  // erupting inside the walls would be a spire in the market square.
  const town = _skyPlatform?.(wx, wz);
  if (town && deck === deckOf(town.plateau)) {
    return { iLo: town.plateau - RELIEF.skyPlatform, iHi: town.plateau };
  }

  if (tierAt(wx, wz) >= I.fromTier) {
    const P = RELIEF.pebble;
    // ONE DECK OF SKY. The same generator runs again every RELIEF.deckH blocks with the
    // coordinates shifted, so each deck is a different archipelago made the same way — and
    // there is no altitude at which islands stop. Climbing does not run out of world.
    const D = RELIEF.deckH;
    const deckBase = I.baseY + deck * D;
    // The shift is what stops deck 3 from being deck 0 again a few hundred blocks up.
    const sx = wx + deck * 811.7, sz = wz + deck * -523.3;

    // ALTITUDE FIRST, because it decides how CROWDED this piece of sky is. Both fields are
    // absolute rather than measured off the land — an island keyed to the ground beneath it
    // warps into a sheet draped over the hill instead of being a thing that broke off.
    const slow = fbm(WORLD_SEED + 9901, sx * I.levelSlowScale, sz * I.levelSlowScale, 2);
    const fast = fbm(WORLD_SEED + 5507, sx * I.levelScale, sz * I.levelScale, 2);
    const lift = Math.pow(slow * 0.5 + 0.5, I.levelBias) * (D * 0.72)
      + (fast * 0.5 + 0.5) * I.levelSpan;
    /** 0 at the bottom of THIS deck, 1 at its top — how much to relax a threshold by, plus a
     *  standing bonus per deck so the sky keeps thickening the higher you climb, for ever. */
    const stack = deck * RELIEF.deckThicken;
    const highness = (y) => stack + Math.min(1, Math.max(0, (y - deckBase) / D));

    // A PLATFORM first — somewhere with room to fight on.
    const platY = deckBase + lift;
    const thrI = I.thresh - highness(platY) * I.threshHigh;
    const im = fbm(WORLD_SEED + 3301, sx * I.scale, sz * I.scale, 3);
    const iStr = Math.min(1, Math.max(0, (im - thrI) / (I.peak - thrI)));
    // Thickness from the mask, so the middle of an island is deep and its rim is a lip.
    let half = iStr > 0 ? (I.minThick + (I.thick - I.minThick) * iStr) * 0.5 : 0;
    let cy = platY;
    if (half === 0) {
      // ...and where there is no platform, a STEPPING STONE. Only evaluated when the first
      // mask failed, which is most columns, so this costs one extra field on the common path
      // and nothing at all where an island already stands. It hangs below the platform layer
      // by its own amount, filling the lower air instead of adding one more shelf up top.
      const dn = fbm(WORLD_SEED + 8813, sx * P.dropScale, sz * P.dropScale, 2);
      const pebY = platY - (P.dropMin + (dn * 0.5 + 0.5) * P.dropSpan);
      const thrP = P.thresh - highness(pebY) * P.threshHigh;
      const pm = fbm(WORLD_SEED + 6607, sx * P.scale, sz * P.scale, 2);
      if (pm > thrP) { half = P.thick * 0.5; cy = pebY; }
      else {
        // ...and failing that, a MOTE: the smallest thing in the sky, scattered through the
        // whole height of it. Only reached when both larger tiers have already declined, so
        // it costs one field on the columns that would otherwise have had nothing at all.
        const M = RELIEF.mote;
        // A MOTE IS NOT HUNG OFF THE PLATFORM LAYER — it takes its own place anywhere in the
        // deck, top to bottom.
        //
        // Hanging them BELOW platY was what made the third level unreachable. Platforms only
        // reach about 72% of a deck's height (the spire and hill shaping eats the rest of the
        // headroom), motes only went further down from there, and so the top ~18 blocks of
        // every deck held nothing at all — a dead band exactly where the next deck's floor
        // begins. You could see the level above and there was no rung within reach of it.
        // Spreading motes across the WHOLE deck closes every boundary, which is the one place
        // a ladder cannot afford a missing rung.
        const mn = fbm(WORLD_SEED + 2711, sx * M.dropScale, sz * M.dropScale, 2);
        const u01 = Math.min(1, Math.max(0, ((mn * 0.5 + 0.5) - M.spread) / (1 - 2 * M.spread)));
        const moteY = deckBase + u01 * (D - M.thick);
        const thrM = M.thresh - highness(moteY) * M.threshHigh;
        if (fbm(WORLD_SEED + 3121, sx * M.scale, sz * M.scale, 2) > thrM) {
          // Returned RIGHT HERE, before any shaping. A mote is one block; running it through
          // the land's hills-and-spires pipeline turned footholds into towers and left only
          // 2% of them actually one block tall, which is the opposite of a foothold.
          if (moteY >= (deck === 0 ? h + I.gapMin : deckBase) && moteY + M.thick < deckBase + D) {
            out = out || {};
            out.iLo = moteY;
            out.iHi = moteY + M.thick;
          }
          return out;
        }
      }
    }
    if (half > 0) {
      // SHAPED LIKE THE LAND. A lens is a bubble; the world is stepped and rough, so the top
      // gets hill noise and then the same terrace quantisation the ground gets — which is
      // what makes an island read as a piece of the world rather than a placed platform. The
      // underside is roughened separately, because a torn bottom is the tell that it broke
      // off rather than being built.
      // Hills, then SPIRES, then terraces — the land's own three steps, in its own order.
      // The spires are what make it read as steep: ridged noise piles rock up in fingers,
      // and the terrace quantisation turns every slope it makes into a staircase of cliffs
      // instead of a ramp. Skipping them was why an island still looked like a lens with a
      // bumpy lid on it.
      let top = cy + half + fbm(WORLD_SEED + 2207, wx * HILL_SCALE, wz * HILL_SCALE, 3) * I.roughness;
      const rn = fbm(WORLD_SEED + 6113, wx * RELIEF.spireScale, wz * RELIEF.spireScale, 3);
      const ridge = Math.max(0, 1 - Math.abs(rn) / RELIEF.spireWidth);
      top += Math.pow(ridge, RELIEF.spireSharp) * I.spireAmp;
      const q = Math.round(top / RELIEF.terraceStep) * RELIEF.terraceStep;
      top += (q - top) * RELIEF.terraceMix;
      const under = cy - half
        - Math.abs(fbm(WORLD_SEED + 4409, wx * HILL_SCALE * 1.7, wz * HILL_SCALE * 1.7, 2))
          * I.underRough;
      // Deck 0 has to clear the LAND; every deck above only has to stay inside itself, so a
      // high deck is never suppressed by a mountain hundreds of blocks below it.
      const floorY = deck === 0 ? h + I.gapMin : deckBase;
      if (under >= floorY && top > under && top < deckBase + D) {
        out = { iLo: under, iHi: top };
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
export function blockAt(wx, wy, wz, h = heightAt(wx, wz), f = featuresAt(wx, wz, h, deckOf(wy))) {
  // No ceiling. The sky repeats upward for ever (RELIEF.deckH) and the loaded WINDOW is what
  // is bounded, not the world — a height test here would put a lid back on it.
  if (wy < 0) return AIR;
  // THE SKY comes first: an island is the only thing that can be solid above the land.
  if (f && f.iHi !== undefined && wy >= f.iLo && wy <= f.iHi) {
    // Layered exactly like the land is, so a high island wears snow and the ones down in the
    // warm air are green. Same rule, same numbers — one world, not two.
    const top = Math.floor(f.iHi);
    if (wy === top) return top > 52 ? SNOW : GRASS;
    return wy > top - 4 ? DIRT : STONE;
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

/** The top of the island over this column, or null — what a spawner needs to put a body up
 *  there rather than on the land far below it. */
/**
 * EVERY perch above this column, lowest first — one per deck that has an island here.
 *
 * islandTopAt only ever answered for the deck above the LAND, which was the whole sky when
 * there was one deck of it. With the archipelago repeating upward, that meant everything the
 * spawner put in the air went onto the bottom layer and the levels above it were empty
 * scenery. Allocates a small array, which is fine: this is asked when a body is born, not
 * every frame.
 */
export function islandTopsAt(wx, wz, maxY = CHUNK_Y - 1) {
  const x = Math.floor(wx), z = Math.floor(wz);
  const h = heightAt(x, z);
  const out = [];
  for (let d = 0; d <= deckOf(maxY); d++) {
    const f = featuresAt(x, z, h, d);
    if (f?.iHi !== undefined) out.push(Math.floor(f.iHi) + 1);
  }
  return out;
}

export function islandTopAt(wx, wz, near = RELIEF.island.baseY) {
  const x = Math.floor(wx), z = Math.floor(wz);
  const f = featuresAt(x, z, heightAt(x, z), deckOf(near));
  return f?.iHi !== undefined ? Math.floor(f.iHi) + 1 : null;
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
  // The deck you are STANDING IN — a body four hundred blocks up is asking about the sky
  // around it, not the deck above the land.
  const f = featuresAt(x, z, h, deckOf(yRef));
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
export function fillChunk(cx, cz, oy = 0) {
  const blocks = new Uint8Array(CHUNK_X * CHUNK_Y * CHUNK_Z);
  const heights = new Int16Array(CHUNK_X * CHUNK_Z);
  const ox = cx * CHUNK_X, oz = cz * CHUNK_Z;
  // The highest solid voxel written, tracked as we go. The mesher needs it, and scanning a
  // 512-tall chunk backwards to find it would cost more than building the chunk did.
  let yTop = 0;
  // Every deck the window can see into, not every deck below 256.
  const loDeck = deckOf(oy), topDeck = deckOf(oy + CHUNK_Y - 1);
  // Which Y layers have ANYTHING in them. A 512-tall chunk is overwhelmingly air, and the
  // mesher walking 256 voxels of a layer to discover it is empty is the single biggest cost
  // in building a chunk. Filling this as we go is free; using it skips those layers whole.
  const layers = new Uint8Array(CHUNK_Y);
  for (let z = 0; z < CHUNK_Z; z++) {
    for (let x = 0; x < CHUNK_X; x++) {
      const h = heightAt(ox + x, oz + z);
      const f = featuresAt(ox + x, oz + z, h, loDeck);
      heights[z * CHUNK_X + x] = h;
      // RUN PER SOLID THING, never a sweep of the column. The air between the land and the
      // sky — and between one deck and the next — is hundreds of voxels of guaranteed
      // nothing, and walking it to write zero into an array that is already zero costs more
      // than everything else here put together. Fill the land, then fill each deck's island,
      // and skip every gap.
      // Local Y is world Y minus the window's base — everything below or above simply is not
      // in this chunk, which is what lets the window sit anywhere without changing anything
      // downstream.
      const landHi = Math.min(CHUNK_Y - 1, h - oy);
      for (let y = Math.max(0, -oy); y <= landHi; y++) {
        blocks[idx(x, y, z)] = blockAt(ox + x, y + oy, oz + z, h, f);
        layers[y] = 1;
        if (y > yTop) yTop = y;
      }
      for (let d = loDeck; d <= topDeck; d++) {
        const fd = featuresAt(ox + x, oz + z, h, d);
        if (!fd || fd.iHi === undefined) continue;
        const lo = Math.max(0, Math.floor(fd.iLo) - oy);
        const hi = Math.min(CHUNK_Y - 1, Math.ceil(fd.iHi) - oy);
        for (let y = lo; y <= hi; y++) {
          blocks[idx(x, y, z)] = blockAt(ox + x, y + oy, oz + z, h, fd);
          layers[y] = 1;
          if (y > yTop) yTop = y;
        }
      }
    }
  }
  return { blocks, heights, cx, cz, ox, oy, oz, yTop, layers };
}
