// The loot model — gear pieces, their rarity, and how a random drop is rolled and named.
//
// A piece is a plain object: { uid, slot, name, rarity, color, armor, stats:{...} }. `stats`
// holds EVERY bonus including armour, so summing a worn set is one loop over one shape. Two
// sources make pieces:
//   - the smith, which sells FIXED pieces (config ARMOR) — a known, buyable baseline
//   - enemy DROPS, rolled here with random stats that scale per ring
//
// Rarity is the WoW/Diablo colour ladder, and it controls HOW MANY bonus stats a drop carries
// on top of its armour:
//   gray  Common    — armour only, drops constantly
//   green Uncommon  — armour + a couple of stats
//   blue  Rare      — armour + a fistful of stats
//
// Names are procedural, like WoW's "Vest of the Tiger": the base noun is the slot, the suffix
// is chosen from whichever stat the roll favoured (or a balanced one when nothing dominates).

import { ARMOR_SLOT_ORDER } from "../config.js";

export const RARITY = {
  common: { key: "common", label: "Common", color: "#b9c0cc", nStats: 0 },
  uncommon: { key: "uncommon", label: "Uncommon", color: "#5fd66a", nStats: 2 },
  rare: { key: "rare", label: "Rare", color: "#5b9dff", nStats: 4 },
};

const SLOT_NOUN = { helm: "Helm", shoulders: "Guards", vest: "Vest", pants: "Legs", boots: "Boots" };

// Stats a DROP can roll on top of armour, and their base magnitude at ring 0. dmg buckets are
// fractions (a +% multiplier); the rest are flat integers. Everything scales up with ring.
const ROLL_STATS = ["stamina", "str", "agi", "dmgGlobal", "dmgGun", "dmgSpell", "dmgGrenade", "rHaste", "rAtkSpeed", "rReload"];
const STAT_BASE = {
  stamina: 6, str: 3, agi: 3,
  dmgGlobal: 0.02, dmgGun: 0.03, dmgSpell: 0.03, dmgGrenade: 0.03,
  rHaste: 20, rAtkSpeed: 20, rReload: 20,
};

// The "of the X" suffix per dominant stat — flavour that also tells you what the piece is FOR.
const SUFFIX = {
  stamina: "of the Bear", str: "of the Tiger", agi: "of the Monkey",
  dmgGlobal: "of Fury", dmgGun: "of the Marksman", dmgSpell: "of the Magus",
  dmgGrenade: "of the Demolisher", rHaste: "of Alacrity", rAtkSpeed: "of the Swift",
  rReload: "of the Quartermaster",
};
const BALANCED_SUFFIX = "of the Wilds";     // when no single stat dominates
const COMMON_PREFIX = ["Worn", "Crude", "Plain", "Rough"];

let _uid = 0;                                // instance ids; deterministic, no Math.random

/** Which rolled stat "leads" the piece, comparing magnitudes normalised by their base. */
function dominant(stats, rolled) {
  if (!rolled.length) return null;
  const ranked = rolled.map((k) => ({ k, w: stats[k] / STAT_BASE[k] })).sort((a, b) => b.w - a.w);
  // If the runner-up is within 70% of the leader, nothing really dominates — call it balanced.
  if (ranked[1] && ranked[1].w > ranked[0].w * 0.7) return "_balanced";
  return ranked[0].k;
}

/** Name a piece from its slot and what its roll favoured — "Vest of the Tiger", etc. */
export function gearName(slot, stats, rolled, rng) {
  const noun = SLOT_NOUN[slot] || "Piece";
  if (!rolled.length) return `${COMMON_PREFIX[Math.floor(rng() * COMMON_PREFIX.length)]} ${noun}`;
  const dom = dominant(stats, rolled);
  const suffix = dom === "_balanced" ? BALANCED_SUFFIX : (SUFFIX[dom] || BALANCED_SUFFIX);
  return `${noun} ${suffix}`;
}

/**
 * Roll a random dropped piece for a kill in `ring`, using the seeded rng. Common is the
 * common case; deeper rings roll bigger numbers and, slightly, better rarity.
 */
export function rollGear(ring, rng) {
  const r = rng() + ring * 0.015;           // depth nudges the rarity table, gently
  const rarity = r < 0.60 ? RARITY.common : r < 0.88 ? RARITY.uncommon : RARITY.rare;
  const slot = ARMOR_SLOT_ORDER[Math.floor(rng() * ARMOR_SLOT_ORDER.length)];
  const rarMult = rarity.key === "rare" ? 1.5 : rarity.key === "uncommon" ? 1.18 : 1.0;
  const ringScale = 1 + ring * 0.5;

  const stats = { armor: Math.max(1, Math.round((20 + ring * 13) * rarMult)) };
  const pool = [...ROLL_STATS];
  const rolled = [];
  for (let i = 0; i < rarity.nStats && pool.length; i++) {
    const key = pool.splice(Math.floor(rng() * pool.length), 1)[0];
    const mag = STAT_BASE[key] * ringScale * rarMult * (0.7 + rng() * 0.6);
    stats[key] = key.startsWith("dmg") ? +mag.toFixed(3) : Math.max(1, Math.round(mag));
    rolled.push(key);
  }

  return {
    uid: `drop_${_uid++}`,
    slot, rarity: rarity.key, color: rarity.color,
    armor: stats.armor, stats,
    name: gearName(slot, stats, rolled, rng),
  };
}

/** Turn a FIXED config piece (smith stock) into an owned instance. Vendor gear is green. */
export function vendorPiece(cfg) {
  return {
    uid: cfg.id, slot: cfg.slot, rarity: "uncommon", color: RARITY.uncommon.color,
    armor: cfg.armor, stats: cfg.stats, name: cfg.name,
  };
}
