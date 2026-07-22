// Boss drops: rolled relics you walk over to claim.
//
// A relic is a BUNDLE of the same upgrades the vendors sell — two or three of them at once,
// several purchases deep. That is deliberate: it makes a boss kill worth more than the
// points it pays, and it hands you a build you did not choose, which is the part a shop can
// never do. Buying is deliberate; a drop is fate.
//
// Everything a relic grants routes through the SAME player fields the shop writes, so a
// relic can never grant something armour or haste do not already understand — and
// applyLevelStats() derives the result either way.

import { RELIC } from "../config.js";
import { player } from "../state.js";

/**
 * The pool. `stat` is the player field, `each` the size of one "purchase" of it, and
 * `weight` how often it turns up. Keeping these identical to shop increments means a relic
 * reads as "three plates and two boots" rather than as a separate power system.
 */
export const RELIC_STATS = [
  { id: "armor", label: "Plating", stat: "armor", each: 1, weight: 1.1,
    fmt: (n) => `-${Math.round((1 - Math.pow(0.90, n)) * 100)}% damage taken` },
  { id: "haste", label: "Haste", stat: "haste", each: 1, weight: 1.0,
    fmt: (n) => `+${Math.round((Math.pow(1.07, n) - 1) * 100)}% fire rate, faster cooldowns` },
  { id: "dmg", label: "Edge", stat: "gearDmg", each: 0.08, weight: 1.0,
    fmt: (n) => `+${Math.round(n * 8)}% damage` },
  { id: "speed", label: "Swiftness", stat: "gearSpeed", each: 0.04, weight: 0.9,
    fmt: (n) => `+${Math.round(n * 4)}% movement speed` },
  { id: "reload", label: "Loading", stat: "gearReload", each: 0.08, weight: 0.7,
    fmt: (n) => `-${Math.round(n * 8)}% reload time` },
];

// Names are assembled from the rolled parts, so a relic's title tells you what it does
// before you read the line under it.
const PREFIX = ["Worn", "Etched", "Blackened", "Gilded", "Cracked", "Humming", "Sunken"];
const NOUN = ["Sigil", "Ward", "Charm", "Coil", "Reliquary", "Totem", "Fetish"];

/**
 * Roll a relic for a boss of this tier. Deeper bosses roll more stats and more purchases
 * of each, so the drop scales with the fight rather than with a table you have to maintain.
 */
export function rollRelic(tier, rng) {
  const kinds = RELIC.minStats
    + Math.floor(rng() * (RELIC.maxStats - RELIC.minStats + 1))
    + (tier >= RELIC.thirdStatTier ? 1 : 0);

  const pool = [...RELIC_STATS];
  const parts = [];
  for (let k = 0; k < kinds && pool.length; k++) {
    const total = pool.reduce((sum, p) => sum + p.weight, 0);
    let r = rng() * total;
    let pick = pool[pool.length - 1];
    for (const p of pool) {
      r -= p.weight;
      if (r <= 0) { pick = p; break; }
    }
    pool.splice(pool.indexOf(pick), 1);

    // How many "purchases" worth. Grows with tier, jittered so two relics from the same
    // boss are never the same relic.
    const base = RELIC.stacksBase + tier * RELIC.stacksPerTier;
    const n = Math.max(1, Math.round(base * (0.65 + rng() * 0.7)));
    parts.push({ ...pick, n });
  }

  return {
    name: `${PREFIX[Math.floor(rng() * PREFIX.length)]} `
      + `${NOUN[Math.floor(rng() * NOUN.length)]}`,
    tier,
    parts,
    lines: parts.map((p) => p.fmt(p.n)),
  };
}

/** Claim it. Writes the same fields the shop writes; nothing here is a special case. */
export function applyRelic(relic) {
  for (const p of relic.parts) player[p.stat] += p.each * p.n;
}
