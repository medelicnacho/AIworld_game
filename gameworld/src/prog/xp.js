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

import { XP, PLAYER, HASTE, DODGE, STATS, GRACE } from "../config.js";
import { player } from "../state.js";
import { maxHpFor, ratingPct } from "./stats.js";

/**
 * XP to go from `level` to `level + 1`, on the three-phase curve. Each phase is a power curve
 * anchored to where the previous one ended, so the whole thing is CONTINUOUS but the growth
 * rate steps up at each break: fast to break1, a climb to break2, a grind beyond.
 */
export function xpToNext(level) {
  const { xpBase: a, xpEarlyExp: p1, xpMidExp: p2, xpLateExp: p3, xpBreak1: b1, xpBreak2: b2 } = XP;
  const atB1 = a * Math.pow(b1, p1);              // cost at the phase-1→2 seam
  const atB2 = atB1 * Math.pow(b2 / b1, p2);      // cost at the phase-2→3 seam
  if (level < b1) return Math.floor(a * Math.pow(level, p1));
  if (level < b2) return Math.floor(atB1 * Math.pow(level / b1, p2));
  return Math.floor(atB2 * Math.pow(level / b2, p3));
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
  player.levelMult = Math.pow(XP.damageGrowth, n);
  // Damage = level × (1 + GLOBAL). Global is Strength (STATS.strDmg per point) plus any
  // Global-Damage gear. The gun/spell/grenade BUCKETS are per-source and applied at the use
  // sites (they can't be uniform here). gearDmg is 0 now that Sharpen is gone, kept for safety.
  player.dmgMult = player.levelMult
    * (1 + (player.gearDmg || 0) + STATS.strDmg * (player.str || 0) + (player.dmgGlobal || 0));

  // Early-game grace: large at level 1, linear to nothing by GRACE.levels. It makes a fresh,
  // gearless character hit hard and take less, so levels 1-3 are easy and the difficulty ramps
  // up as you level and gear rather than all at once. graceMitigation is read in damagePlayer.
  const grace = Math.max(0, 1 - (player.level - 1) / GRACE.levels);
  player.dmgMult *= 1 + grace * GRACE.dmgBonus;
  player.graceMitigation = grace * GRACE.mitigation;
  // Speed used to be a raw exponential with no ceiling, so a high-level geared build ran 3-5x
  // base and only got faster -- unreadable, and it made the world feel small. Now the raw
  // intent (levels x gear) is the INPUT to a diminishing-returns curve: tanh is ~linear for
  // the first ~20 levels, so early game is unchanged, then bends and approaches a soft ceiling
  // of +speedSoftCap. You keep gaining forever, each gain worth less than the last, and you
  // can never outrun the game. (The dash reads speedMult too, so it tames in step.)
  // Agility feeds the speed input alongside Lighten (STATS.agiSpeed per point).
  const speedGear = (player.gearSpeed || 0) + STATS.agiSpeed * (player.agi || 0);
  const rawSpeedBonus = Math.pow(XP.speedGrowth, n) * (1 + speedGear) - 1;
  player.speedMult = 1 + XP.speedSoftCap * Math.tanh(rawSpeedBonus / XP.speedSoftCap);
  player.jumpMult = Math.pow(XP.jumpGrowth, n);
  player.maxJumps = PLAYER.jumps + Math.floor(player.level / XP.jumpsPerLevels);
  // GEAR.md G1: max HP is now Stamina-driven (MMO health). Bare stamina is 0, so this is the
  // old flat 100 until gear rolls Stamina in G2 — a foundation laid without a behaviour
  // change. Armour is no longer a precomputed multiplier: its mitigation depends on the
  // ATTACKER's tier, so it is resolved at the damage choke point instead (see damagePlayer).
  const before = player.maxHp;
  player.maxHp = maxHpFor(player.stamina);
  // If gear just raised your ceiling, ride the gain up rather than leaving a gap under a
  // fuller bar; never top you off from a mere re-derive (level-up does that deliberately).
  if (player.maxHp > before) player.hp += player.maxHp - before;
  player.hp = Math.min(player.hp, player.maxHp);

  // NO CEILINGS. Stacking without limit is the point of a stat game, so nothing is clamped
  // here — the safety lives at the USE SITES instead, where a value can actually do damage:
  // the reload has a hard minimum duration, and movement is substepped so no speed can step
  // over a wall. Bounding the number would have limited the fantasy; bounding what the
  // number is allowed to BREAK does not.
  // Reload speed: the old Quick Loader term × the gear Reload rating (diminishing).
  player.reloadMult = (1 - (player.gearReload || 0)) * (1 - ratingPct(player.rReload, STATS.reloadK));

  // The dodge grows with your speed, the old Vault stat, AND Agility — each on a sqrt curve
  // so it keeps climbing but never linearly. Derived here like every other stat.
  const speedExcess = Math.max(0, player.speedMult - 1);
  player.dashMult = 1
    + DODGE.speedGain * Math.sqrt(speedExcess)
    + DODGE.dashStatGain * Math.sqrt(player.dashRank || 0)
    + STATS.agiDash * Math.sqrt(player.agi || 0);

  // Haste family: the old integer Haste stat × the gear ratings (Haste → cooldowns & cast,
  // Attack Speed → fire rate), each rating on the diminishing rating/(rating+K) curve.
  const h = player.haste || 0;
  const hasteR = ratingPct(player.rHaste, STATS.hasteK);
  const atkR = ratingPct(player.rAtkSpeed, STATS.attackSpeedK);
  player.hasteFire = Math.pow(HASTE.fire, h) * (1 + atkR);
  player.hasteCd = Math.pow(HASTE.cooldown, h) * (1 - hasteR);
  // The channel keeps its floor: this one is a DESIGN limit, not a safety one. Standing
  // still is the cost of Mend, and an instant channel would quietly make it a second potion.
  player.hasteCast = Math.max(HASTE.castFloor, Math.pow(HASTE.cast, h) * (1 - hasteR));
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
