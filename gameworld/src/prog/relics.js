// Boss drops: rolled relics you walk over to claim.
//
// A relic is NOT its own power system. It is a bundle of VENDOR PURCHASES — "three platings
// and two hastes" — applied by calling the shop's own apply() functions, the same ones the
// buy button calls. That matters more than it sounds: relics used to write player fields
// directly, so they bypassed limits the shop enforced (Quick Loader caps reload reduction at
// 0.6; a relic did not), and a lucky drop could push a stat somewhere no amount of shopping
// could. Two paths meant two sets of rules and only one of them was tested.
//
// Now there is one path. Anything true of buying an item is true of finding it.

import { RELIC } from "../config.js";
import { GOODS } from "../ui/shop.js";

/** The vendor goods a relic can bundle, with the word it contributes to the name. */
export const RELIC_POOL = [
  { good: "plating", label: "Plating", weight: 1.1 },
  { good: "haste", label: "Haste", weight: 1.0 },
  { good: "lighten", label: "Swiftness", weight: 0.9 },
  { good: "quickload", label: "Loading", weight: 0.7 },
  { good: "vault", label: "Vault", weight: 0.8 },
];

/** Rarity decides how many kinds it bundles and how deep each one goes. */
export const RARITY = [
  { name: "Worn", parts: 2, mult: 1.0, weight: 5, color: "#cfd6e4" },
  { name: "Leather", parts: 2, mult: 1.6, weight: 3, color: "#9ad6a0" },
  { name: "Heavy", parts: 3, mult: 2.2, weight: 1.6, color: "#7fc4ff" },
  { name: "Runed", parts: 3, mult: 3.2, weight: 0.7, color: "#d99bff" },
];

const NOUN = ["Ward", "Sigil", "Charm", "Coil", "Reliquary", "Totem"];

function findGood(id) {
  for (const list of Object.values(GOODS)) {
    const g = list.find((x) => x.id === id);
    if (g) return g;
  }
  return null;
}

function pick(list, rng, key = "weight") {
  const total = list.reduce((s, o) => s + o[key], 0);
  let r = rng() * total;
  for (const o of list) {
    r -= o[key];
    if (r <= 0) return o;
  }
  return list[list.length - 1];
}

/**
 * Roll a relic for a boss of this tier. Deeper bosses roll rarer, and rarer means both more
 * kinds of upgrade and more purchases of each.
 */
export function rollRelic(tier, rng) {
  // Deep bosses tilt the rarity table rather than using a different one.
  const table = RARITY.map((r, i) => ({ ...r, weight: r.weight * (1 + i * tier * 0.14) }));
  const rarity = pick(table, rng);

  const pool = [...RELIC_POOL];
  const parts = [];
  for (let k = 0; k < rarity.parts && pool.length; k++) {
    const p = pick(pool, rng);
    pool.splice(pool.indexOf(p), 1);
    const base = RELIC.stacksBase + tier * RELIC.stacksPerTier;
    const n = Math.max(1, Math.round(base * rarity.mult * (0.75 + rng() * 0.5)));
    parts.push({ ...p, n });
  }

  return {
    rarity: rarity.name,
    color: rarity.color,
    name: `${rarity.name} ${NOUN[Math.floor(rng() * NOUN.length)]}`,
    tier,
    parts,
    lines: parts.map((p) => `${p.label} ×${p.n}`),
  };
}

/**
 * Claim it — by BUYING each part, free, through the shop's own apply(). Every cap, every
 * side effect and every future change to an item is inherited automatically.
 */
export function applyRelic(relic, ctx) {
  for (const p of relic.parts) {
    const good = findGood(p.good);
    if (!good) continue;
    for (let i = 0; i < p.n; i++) good.apply(ctx);
  }
}
