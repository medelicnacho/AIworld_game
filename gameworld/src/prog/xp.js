// D9 — experience and endless levels.
//
// Two numbers do all the work: what a kill is worth (scales with RING) and what a level
// costs (scales with LEVEL, faster). Their ratio is the whole progression curve:
//
//   level 1   a trash mob is ~25% of a level        — everything you kill matters
//   level 10  a trash mob is ~2%, an elite ~17%     — elites carry, packs top up
//   level 20  a trash mob is <1%, an elite ~6%      — only the deep is worth your time
//
// Which is the intended pressure: to keep levelling you must walk further out, where mobs
// are worth more AND more of them are elites. Distance is the progression system.

import { XP, PLAYER, VILLAGE, HASTE, DODGE } from "../config.js";
import { player } from "../state.js";

/** XP needed to go from `level` to `level + 1`. */
export function xpToNext(level) {
  return Math.floor(XP.curveBase * Math.pow(level, XP.curveExp));
}

/** What one kill is worth, given where it died and whether it was starred. */
export function killValue(ring, elite) {
  return Math.round(XP.mobBase * (1 + XP.perRing * ring) * (elite ? XP.eliteMult : 1));
}

export function bossValue(ring) {
  return Math.round(XP.bossBase * (1 + XP.bossPerRing * ring));
}

/**
 * Award xp and resolve any number of level-ups (a boss can grant several at once).
 * @returns {number} levels gained
 */
export function award(amount) {
  player.xp += amount;
  let gained = 0;
  while (player.xp >= xpToNext(player.level)) {
    player.xp -= xpToNext(player.level);
    player.level++;
    gained++;
    applyLevelStats();
    // FULL heal on level. It doubles as a mid-fight comeback: grinding a pack while a boss
    // hunts you can top you off, which makes "one more kill" a real tactical option and
    // gives the 12s heal cooldown something to compete with.
    player.hp = player.maxHp;
  }
  return gained;
}

/**
 * Every level-scaled stat, DERIVED from level rather than accumulated. Incrementing on
 * level-up and decrementing on death drifts apart the moment either path changes; deriving
 * cannot. Max HP is deliberately absent — levels buy mobility, not bulk.
 */
export function applyLevelStats() {
  const n = player.level - 1;
  // Gear multiplies on top of levels, so the smith stays worth visiting at any level.
  player.dmgMult = Math.pow(XP.damageGrowth, n) * (1 + (player.gearDmg || 0));
  // Speed used to be a raw exponential with no ceiling, so a high-level geared build ran 3-5x
  // base and only got faster -- unreadable, and it made the world feel small. Now the raw
  // intent (levels x gear) is the INPUT to a diminishing-returns curve: tanh is ~linear for
  // the first ~20 levels, so early game is unchanged, then bends and approaches a soft ceiling
  // of +speedSoftCap. You keep gaining forever, each gain worth less than the last, and you
  // can never outrun the game. (The dash reads speedMult too, so it tames in step.)
  const rawSpeedBonus = Math.pow(XP.speedGrowth, n) * (1 + (player.gearSpeed || 0)) - 1;
  player.speedMult = 1 + XP.speedSoftCap * Math.tanh(rawSpeedBonus / XP.speedSoftCap);
  player.jumpMult = Math.pow(XP.jumpGrowth, n);
  player.maxJumps = PLAYER.jumps + Math.floor(player.level / XP.jumpsPerLevels);
  // Armour is the one stat that reduces rather than adds, so it lives here too — derived,
  // never accumulated, and therefore impossible to drift out of step on death.
  player.dmgTakenMult = Math.pow(VILLAGE.armorMult, player.armor || 0);

  // NO CEILINGS. Stacking without limit is the point of a stat game, so nothing is clamped
  // here — the safety lives at the USE SITES instead, where a value can actually do damage:
  // the reload has a hard minimum duration, and movement is substepped so no speed can step
  // over a wall. Bounding the number would have limited the fantasy; bounding what the
  // number is allowed to BREAK does not.
  player.reloadMult = 1 - (player.gearReload || 0);

  // The dodge grows with BOTH your general speed and a dedicated Vault stat, each on a sqrt
  // curve so it keeps climbing but never linearly — derived here like every other stat, so
  // it can never drift out of step on death. speedMult is already resolved above, so any
  // source of speed (levels, Lighten, Swiftness relics) feeds the dash for free.
  const speedExcess = Math.max(0, player.speedMult - 1);
  player.dashMult = 1
    + DODGE.speedGain * Math.sqrt(speedExcess)
    + DODGE.dashStatGain * Math.sqrt(player.dashRank || 0);

  const h = player.haste || 0;
  player.hasteFire = Math.pow(HASTE.fire, h);
  player.hasteCd = Math.pow(HASTE.cooldown, h);
  // The channel keeps its floor: this one is a DESIGN limit, not a safety one. Standing
  // still is the cost of Mend, and an instant channel would quietly make it a second potion.
  player.hasteCast = Math.max(HASTE.castFloor, Math.pow(HASTE.cast, h));
}

/** Fraction of the way to the next level, for the HUD bar. */
export function levelProgress() {
  return Math.max(0, Math.min(1, player.xp / xpToNext(player.level)));
}

/**
 * The deepest tier your level entitles you to WAKE in. Dying deep at a low level should not
 * hand you a free teleport past everything you skipped — you get carried back to where you
 * have actually earned a bed.
 *
 *   level  1-9   tier 0 (the Commons)
 *   level 10-14  tier 1
 *   level 15-19  tier 2 ... and one more tier every 5 levels after
 */
export function respawnTierFor(level) {
  return Math.max(0, Math.floor((level - 5) / 5));
}

/** The level a tier expects, for telling the player why they woke where they did. */
export function levelForTier(t) {
  return t <= 0 ? 1 : 5 + 5 * t;
}

/** D9's death penalty: lose the top level, and land just short of regaining it. */
export function loseLevel() {
  if (player.level <= 1) { player.xp = 0; return false; }
  player.level--;
  applyLevelStats();
  player.xp = Math.floor(xpToNext(player.level) * 0.5);
  return true;
}
