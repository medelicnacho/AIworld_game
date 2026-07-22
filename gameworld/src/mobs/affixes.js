// The affix engine (CONTENT.md C1).
//
// Affixes multiply content where new enemies only add it: Diablo 3 built decades of variety
// from ~25 composable modifiers on one roster. Each affix here is ONE RULE and ONE COLOUR,
// they roll independently, and deep tiers roll several at once — so ten affixes is a
// hundred-odd distinct encounters rather than ten.
//
// An affix is pure data plus optional lifecycle hooks. Nothing in mobs.js knows what any
// individual affix does; it only knows when to run the hooks. That is the whole point —
// adding an affix must never mean editing the mob loop.
//
//   onSpawn(e, ctx)          once, after stats are rolled — mutate the entity
//   onTick(e, dt, ctx)       every frame while it is near the player
//   onHitPlayer(e, ctx)      it landed a hit on you
//   onDeath(e, ctx)          it died — position is still valid here
//   hidden(e)                true = untargetable this instant (Phasing)
//
// ctx carries the few world verbs an affix may need: { blast, mobs, player }.

export const AFFIXES = {
  // Each affix is ONE RULE, self-contained: its numbers live beside its behaviour, so the
  // whole thing can be read — and judged — in one place.

  /** Kill it, then LEAVE. Punishes standing on a corpse to finish the next one. */
  burst: {
    id: "burst",
    name: "Dying Burst",
    color: 0xff2f2f,
    minTier: 1,
    weight: 1,
    desc: "Explodes when it dies. The ground is marked first.",
    onDeath: (e, ctx) => ctx.mobs.queueBurst(e.x, e.z, e.damage * 3.2, 7.5),
  },

  /** Stop fighting where it has been. Turns the floor into terrain you have to read. */
  burning: {
    id: "burning",
    name: "Burning",
    color: 0xff8c1a,
    minTier: 1,
    weight: 1,
    desc: "Leaves fire burning wherever it walks.",
    onTick: (e, dt, ctx) => {
      e.burnT = (e.burnT || 0) - dt;
      if (e.burnT > 0) return;
      e.burnT = 0.3;
      ctx.mobs.dropFire(e, e.damage * 1.6, 2.8, 5.0);
    },
  },

  /** The kill is not the end. Punishes spending a big cooldown on the wrong target. */
  splitting: {
    id: "splitting",
    name: "Splitting",
    color: 0xa45cff,
    minTier: 1,
    weight: 1,
    desc: "Breaks into three fast spawn when killed.",
    onDeath: (e, ctx) => ctx.mobs.spawnSplit(e, 3),
  },

  /** The C1 pipeline prover. Kept: pure speed is a real, readable modifier. */
  frenzied: {
    id: "frenzied",
    name: "Frenzied",
    color: 0x35d6c8,
    minTier: 1,
    weight: 1,
    desc: "Moves far faster than it should.",
    onSpawn: (e) => { e.speed *= 1.45; },
  },
};

/** How many affixes a mob at this tier may carry. */
export function affixCountFor(tier) {
  if (tier >= 6) return 3;
  if (tier >= 3) return 2;
  if (tier >= 1) return 1;
  return 0;
}

/**
 * Pick affixes for a mob. `force` (from the admin panel) bypasses tier gates entirely —
 * testing a tier-6 combination must never require walking to tier 6.
 */
export function rollAffixes(tier, rng, force = null) {
  if (force) return force.filter((id) => AFFIXES[id]);

  const n = affixCountFor(tier);
  if (n <= 0) return [];

  const pool = Object.values(AFFIXES).filter((a) => (a.minTier || 0) <= tier);
  const out = [];
  for (let k = 0; k < n && pool.length; k++) {
    const total = pool.reduce((sum, a) => sum + (a.weight || 1), 0);
    let r = rng() * total;
    let pick = pool[pool.length - 1];
    for (const a of pool) {
      r -= a.weight || 1;
      if (r <= 0) { pick = a; break; }
    }
    out.push(pick.id);
    pool.splice(pool.indexOf(pick), 1);   // no duplicates on one body
  }
  return out;
}

const _broken = new Set();

/**
 * Run a lifecycle hook across every affix on an entity.
 *
 * Wrapped, because a hook that throws runs again next frame and every frame after — which
 * starves the main thread, and a starved main thread makes WebAudio scream. One bad affix
 * should switch ITSELF off and leave the game running, and say so once rather than a
 * thousand times.
 */
export function runAffix(e, hook, ...args) {
  const list = e.affixes;
  if (!list || !list.length) return;
  for (const id of list) {
    if (_broken.has(id)) continue;
    const fn = AFFIXES[id]?.[hook];
    if (!fn) continue;
    try {
      fn(e, ...args);
    } catch (err) {
      _broken.add(id);
      console.error(`[affix] "${id}" disabled — ${hook} threw:`, err);
    }
  }
}

/** Is this entity untargetable right now? */
export function affixHidden(e) {
  const list = e.affixes;
  if (!list || !list.length) return false;
  return list.some((id) => AFFIXES[id]?.hidden?.(e));
}

export function affixNames(e) {
  return (e.affixes || []).map((id) => AFFIXES[id]?.name).filter(Boolean);
}

/** Lower-case, hyphenated, for the kill feed: "burning-splitting". */
export function affixLabel(e) {
  return affixNames(e).join("-").toLowerCase();
}

export const affixList = () => Object.values(AFFIXES);

/** Affixes that threw and switched themselves off. Surfaced in the HUD: silent
 *  self-disabling is worse than a crash, because nothing tells you it happened. */
export const brokenAffixes = () => [..._broken];
