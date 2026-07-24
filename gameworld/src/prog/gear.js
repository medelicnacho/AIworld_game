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
  // EPIC IS BOSS-ONLY. Nothing you kill in the field can roll it, and that restriction is the
  // entire point: a colour that can turn up anywhere is only a rarer number, while a colour
  // that can only come from the hardest fight in the ring is a trophy. When purple appears on
  // the ground, it means something died that was worth telling someone about.
  // Deep purple, and the only rarity that GLOWS on the ground — it carries its own light, so
  // an epic lying in a field announces itself from across the ring instead of being one more
  // coloured cube you might walk past. Six stats against blue's four, and the biggest numbers
  // on the ladder. Colour is the genre's purple rather than a truly dark one because it also
  // has to stay legible as text on a dark panel; the DARKNESS lives in the glow, not the label.
  epic: { key: "epic", label: "Epic", color: "#a335ee", glow: 0x7a1fd0, nStats: 6 },
};

/** Worst to best. Used to floor a roll at a guaranteed minimum (boss drops). */
const LADDER = ["common", "uncommon", "rare", "epic"];

const SLOT_NOUN = { helm: "Helm", shoulders: "Guards", vest: "Vest", pants: "Legs", boots: "Boots" };

// Stats a DROP can roll on top of armour, and their base magnitude at ring 0. dmg buckets are
// fractions (a +% multiplier); the rest are flat integers. Everything scales up with ring.
const ROLL_STATS = ["stamina", "str", "agi", "moveSpeed", "dmgGlobal", "dmgGun", "dmgSpell", "dmgGrenade", "rHaste", "rAtkSpeed", "rReload"];
const STAT_BASE = {
  stamina: 6, str: 3, agi: 3, moveSpeed: 0.03,
  dmgGlobal: 0.02, dmgGun: 0.03, dmgSpell: 0.03, dmgGrenade: 0.03,
  rHaste: 20, rAtkSpeed: 20, rReload: 20,
};

// The "of the X" suffix per dominant stat — flavour that also tells you what the piece is FOR.
const SUFFIX = {
  stamina: "of the Bear", str: "of the Tiger", agi: "of the Monkey",
  dmgGlobal: "of Fury", dmgGun: "of the Marksman", dmgSpell: "of the Magus",
  dmgGrenade: "of the Demolisher", rHaste: "of Alacrity", rAtkSpeed: "of the Swift",
  rReload: "of the Quartermaster", moveSpeed: "of the Cheetah",
};
const BALANCED_SUFFIX = "of the Wilds";     // when no single stat dominates
const COMMON_PREFIX = ["Worn", "Crude", "Plain", "Rough"];

let _uid = 0;                                // instance ids; deterministic, no Math.random

/**
 * Step the name counter past a number. A loaded game brings pieces whose names were handed out
 * in an earlier session, while this counter starts again from zero with the page — so without
 * this the first piece you picked up after loading would be born sharing a name with something
 * already in your bag, and every action that finds a piece BY name (equip, sell, drop) would
 * hit whichever it met first. Called once on load, with the highest name it saw.
 */
export function bumpUid(n) {
  if (Number.isFinite(n) && n > _uid) _uid = n;
}

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
export function rollGear(ring, rng, { minRarity = null, epicChance = 0 } = {}) {
  // Gray is the constant common drop; green and blue are genuine finds. ~86% / ~11% / ~3% at
  // the surface, with depth nudging a little toward the good stuff. Field kills pass no
  // options, so this is exactly the table it always was — epic can never appear here.
  const r = rng() + ring * 0.01;
  let rarity = r < 0.86 ? RARITY.common : r < 0.97 ? RARITY.uncommon : RARITY.rare;
  // A boss rolls on the same table but with a FLOOR and a shot at purple. Rolling-then-flooring
  // rather than using a separate table means one distribution to reason about, and a boss that
  // gets lucky on the ordinary roll still benefits from it.
  if (epicChance > 0 && rng() < epicChance) rarity = RARITY.epic;
  if (minRarity && LADDER.indexOf(rarity.key) < LADDER.indexOf(minRarity)) {
    rarity = RARITY[minRarity];
  }
  const slot = ARMOR_SLOT_ORDER[Math.floor(rng() * ARMOR_SLOT_ORDER.length)];
  const rarMult = rarity.key === "epic" ? 1.95 : rarity.key === "rare" ? 1.5
    : rarity.key === "uncommon" ? 1.18 : 1.0;
  const ringScale = 1 + ring * 0.5;

  // Armour VARIES piece to piece (±25%), so two greys of the same slot are rarely identical
  // and there's always a slightly-better one worth grabbing.
  const stats = { armor: Math.max(1, Math.round((20 + ring * 13) * rarMult * (0.75 + rng() * 0.5))) };
  const pool = [...ROLL_STATS];
  const rolled = [];
  for (let i = 0; i < rarity.nStats && pool.length; i++) {
    const key = pool.splice(Math.floor(rng() * pool.length), 1)[0];
    const mag = STAT_BASE[key] * ringScale * rarMult * (0.7 + rng() * 0.6);
    stats[key] = (key.startsWith("dmg") || key === "moveSpeed") ? +mag.toFixed(3) : Math.max(1, Math.round(mag));
    rolled.push(key);
  }

  return {
    uid: `drop_${_uid++}`,
    slot, rarity: rarity.key, color: rarity.color,
    // WHERE IT CAME FROM. Rarity says how MANY stats a piece carries; tier says how BIG they
    // are, and the two are independent — a blue out of the Commons and a blue out of the Deep
    // look identical in a bag while one has roughly four times the numbers. Without this the
    // player cannot compare their own loot, which quietly makes every upgrade a guess.
    tier: ring,
    glow: rarity.glow || 0,
    armor: stats.armor, stats,
    name: gearName(slot, stats, rolled, rng),
  };
}

/** What a piece sells back for — armour plus a rarity bonus, rounded. */
export function sellValue(piece) {
  const bonus = piece.rarity === "epic" ? 160 : piece.rarity === "rare" ? 60
    : piece.rarity === "uncommon" ? 25 : 8;
  return Math.max(1, Math.round((piece.armor || 0) * 0.4 + bonus));
}

/** Turn a FIXED config piece (smith stock) into an owned instance. Vendor gear is green. */
export function vendorPiece(cfg) {
  return {
    // A unique name per purchase. Sharing the config's id meant two of the same bought piece
    // were literally the same item as far as every by-name lookup was concerned: equipping the
    // second silently destroyed the first, and selling a spare out of your bag unequipped the
    // one you were wearing.
    uid: `buy_${cfg.id}_${_uid++}`,
    slot: cfg.slot, rarity: "uncommon", color: RARITY.uncommon.color,
    tier: cfg.minTier || 0,
    glow: 0,
    armor: cfg.armor,
    // A COPY. Sharing the config object meant every instance of a bought piece pointed at the
    // one table entry, so anything that ever wrote to a piece's stats would edit the shop's
    // stock for the rest of the session.
    stats: { ...cfg.stats },
    name: cfg.name,
  };
}
