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
  // C1 ships exactly one affix, and a deliberately boring one: it proves the whole
  // pipeline (roll -> colour -> hook -> kill feed -> admin spawn) without introducing any
  // new system that could mask an engine bug. The interesting ones are C2.
  frenzied: {
    id: "frenzied",
    name: "Frenzied",
    color: 0xff7a1e,
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

/** Run a lifecycle hook across every affix on an entity. */
export function runAffix(e, hook, ...args) {
  const list = e.affixes;
  if (!list || !list.length) return;
  for (const id of list) AFFIXES[id]?.[hook]?.(e, ...args);
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
