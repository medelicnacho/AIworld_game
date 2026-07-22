// Socket 1 (PLAN.md M1): every random number in this game comes from here.
//
// Math.random() is unseedable, so a world built on it can never be replayed, and a sim
// that can't be replayed can't be falsified (PLAN.md §5, ROADMAP §2.1). mulberry32 is
// 4 lines, fast, and good enough for terrain and loot.

/** Seeded PRNG. Returns a function producing floats in [0, 1). */
export function mulberry32(seed) {
  let a = seed >>> 0;
  return function next() {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Stateless hash of (seed, x, y) -> uint32. The backbone of "the world is a pure
 *  function of its seed": any chunk, any soul, any loot roll is derivable from
 *  coordinates alone, so nothing has to be stored to be reproducible. */
export function hash2(seed, x, y) {
  let h = (seed ^ Math.imul(x | 0, 0x27d4eb2d) ^ Math.imul(y | 0, 0x165667b1)) >>> 0;
  h = Math.imul(h ^ (h >>> 15), 0x2c1b3c6d) >>> 0;
  h = Math.imul(h ^ (h >>> 13), 0x297a2d39) >>> 0;
  return (h ^ (h >>> 16)) >>> 0;
}

/** hash2 as a float in [0, 1). */
export function rand2(seed, x, y) {
  return hash2(seed, x, y) / 4294967296;
}

/** A PRNG stream seeded from a coordinate — for "roll this chunk's contents". */
export function rngAt(seed, x, y) {
  return mulberry32(hash2(seed, x, y));
}

const fade = (t) => t * t * (3 - 2 * t);
const lerp = (a, b, t) => a + (b - a) * t;

/** Smooth value noise in [-1, 1]. Cheap, deterministic, plenty for blocky terrain. */
export function noise2(seed, x, y) {
  const xi = Math.floor(x), yi = Math.floor(y);
  const xf = fade(x - xi), yf = fade(y - yi);
  const a = rand2(seed, xi, yi);
  const b = rand2(seed, xi + 1, yi);
  const c = rand2(seed, xi, yi + 1);
  const d = rand2(seed, xi + 1, yi + 1);
  return lerp(lerp(a, b, xf), lerp(c, d, xf), yf) * 2 - 1;
}

/** Fractal brownian motion — octaves of noise2. Returns roughly [-1, 1]. */
export function fbm(seed, x, y, octaves = 4, lacunarity = 2.0, gain = 0.5) {
  let amp = 1, freq = 1, sum = 0, norm = 0;
  for (let o = 0; o < octaves; o++) {
    sum += amp * noise2(seed + o * 1013, x * freq, y * freq);
    norm += amp;
    amp *= gain;
    freq *= lacunarity;
  }
  return sum / norm;
}
