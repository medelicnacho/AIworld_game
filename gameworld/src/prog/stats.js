// GEAR.md G1 — the stat spine.
//
// The whole redesign rests on one idea from WoW Classic: gear shows plain ADDITIVE integers,
// and the diminishing returns live in the FORMULAS here, not in the stats. A player reads
// "+45 Armor", adds it up across their gear, and the curve below decides what that is worth.
// No stat needs a hand-tuned ceiling because the formula IS the ceiling.
//
// This module is pure maths, no state — every function takes numbers and returns numbers, so
// it can be called from a derive step, a damage choke point, or a tooltip identically.

import { STATS } from "../config.js";

/**
 * Secondary-stat rating -> fraction, WoW's `rating / (rating + K)` shape. The first points
 * are strong, every later point is worth less, and it asymptotes below 1.0 so it can never
 * reach 100%. One function serves Haste, Attack Speed, Reload and Move Speed — the analogue
 * of ringPressure() serving the whole difficulty ramp.
 */
export function ratingPct(rating, k) {
  if (!rating || rating <= 0) return 0;
  return rating / (rating + k);
}

/**
 * Armour -> damage reduction, WoW's `armor / (armor + K + perTier*attackerTier)`. Two things
 * fall out for free: diminishing returns (doubling armour never doubles mitigation), and the
 * same armour number being worth LESS against deeper enemies — which is half the anti-grind
 * engine, since ring-1 armour cannot carry you to ring 8 no matter how much you stack.
 */
export function armorDR(armor, attackerTier = 0) {
  if (!armor || armor <= 0) return 0;
  const dr = armor / (armor + STATS.armorK + STATS.armorPerTier * attackerTier);
  return Math.min(STATS.armorDRCap, dr);   // a sanity rail; the formula rarely reaches it
}

/** Stamina -> max health. Flat and linear, the MMO way: bulk is a gear decision now. */
export function maxHpFor(stamina) {
  return STATS.baseHp + STATS.stamHp * (stamina || 0);
}
