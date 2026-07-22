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

import { XP, PLAYER } from "../config.js";
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
  player.dmgMult = Math.pow(XP.damageGrowth, n);
  player.speedMult = Math.pow(XP.speedGrowth, n);
  player.jumpMult = Math.pow(XP.jumpGrowth, n);
  player.maxJumps = PLAYER.jumps + Math.floor(player.level / XP.jumpsPerLevels);
}

/** Fraction of the way to the next level, for the HUD bar. */
export function levelProgress() {
  return Math.max(0, Math.min(1, player.xp / xpToNext(player.level)));
}

/** D9's death penalty: lose the top level, and land just short of regaining it. */
export function loseLevel() {
  if (player.level <= 1) { player.xp = 0; return false; }
  player.level--;
  applyLevelStats();
  player.xp = Math.floor(xpToNext(player.level) * 0.5);
  return true;
}
