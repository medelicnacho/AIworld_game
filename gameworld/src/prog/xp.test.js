// Pure-math tripwires for the derived player stats. THIS is where the session's nastiest bugs
// lived: reload driven to zero, speed running away, the grace curve, NaN from a missing gear
// field. applyLevelStats mutates the shared `player`, so each test resets it to a clean slate.

import { test } from "node:test";
import assert from "node:assert/strict";
import { applyLevelStats, xpToNext, respawnTierFor } from "./xp.js";
import { player } from "../state.js";
import { GRACE, XP, STATS } from "../config.js";

/** Reset every input applyLevelStats reads, at a given level; then derive. */
function derive(level, gear = {}) {
  Object.assign(player, {
    level,
    gearDmg: 0, str: 0, agi: 0, stamina: 0,
    dmgGlobal: 0, dmgGun: 0, dmgSpell: 0, dmgGrenade: 0,
    gearSpeed: 0, gearReload: 0, dashRank: 0, haste: 0,
    rHaste: 0, rAtkSpeed: 0, rReload: 0,
    hp: 100, maxHp: 100,
    ...gear,
  });
  applyLevelStats();
}

const finite = (x, name) => assert.ok(Number.isFinite(x), `${name} must be finite, was ${x}`);

test("xpToNext: three-phase curve — always climbing, continuous, steepening", () => {
  // Fast early: L1→2 is cheap.
  assert.equal(xpToNext(1), Math.floor(XP.xpBase));
  // Monotonic across the whole range.
  let prev = 0;
  for (let l = 1; l <= 100; l++) {
    const x = xpToNext(l);
    assert.ok(x > prev, `cost must rise at level ${l}`);
    prev = x;
  }
  // Continuous at the seams: no jump-discontinuity as a phase changes.
  const jump = (l) => xpToNext(l) / xpToNext(l - 1);
  assert.ok(jump(XP.xpBreak1) < 1.6, "no cliff at break1");
  assert.ok(jump(XP.xpBreak2) < 1.6, "no cliff at break2");
  // Steepening (convexity): the ABSOLUTE xp added per level is far larger in the grind phase
  // than in the early phase — one level at 30 costs many early levels' worth.
  const stepEarly = xpToNext(5) - xpToNext(4);
  const stepLate = xpToNext(30) - xpToNext(29);
  assert.ok(stepLate > stepEarly * 5, "a grind-phase level must cost far more xp than an early one");
  // And the phases are ordered: reaching 20 costs more total than reaching 10, a lot more.
  assert.ok(xpToNext(20) > xpToNext(10) * 3, "phase 3 entry dwarfs phase 2 entry");
});

test("respawnTierFor: floored, never negative, non-decreasing", () => {
  assert.equal(respawnTierFor(1), 0);
  assert.equal(respawnTierFor(5), 0);
  assert.equal(respawnTierFor(10), 1);
  assert.equal(respawnTierFor(30), 5);
  let prev = 0;
  for (let l = 1; l <= 100; l++) {
    const t = respawnTierFor(l);
    assert.ok(t >= 0 && t >= prev, `tier at level ${l}`);
    prev = t;
  }
});

test("grace: full at level 1, gone by GRACE.levels+1, monotonically fading", () => {
  derive(1);
  assert.ok(Math.abs(player.graceMitigation - GRACE.mitigation) < 1e-9, "full mitigation at L1");
  // dmgMult at L1 = level(1) * (1+0) * (1 + full dmgBonus).
  assert.ok(Math.abs(player.dmgMult - (1 + GRACE.dmgBonus)) < 1e-9, "full damage bonus at L1");

  derive(GRACE.levels + 1);
  assert.equal(player.graceMitigation, 0, "grace fully gone");
  assert.ok(Math.abs(player.dmgMult - Math.pow(XP.damageGrowth, GRACE.levels)) < 1e-6,
    "no grace left in dmgMult");

  let prev = Infinity;
  for (let l = 1; l <= GRACE.levels + 1; l++) {
    derive(l);
    assert.ok(player.graceMitigation <= prev, `mitigation should not rise at level ${l}`);
    prev = player.graceMitigation;
  }
});

test("maxHp: driven by Stamina, and hp rides a raised ceiling up", () => {
  derive(5, { stamina: 20, hp: 100, maxHp: 100 });
  assert.equal(player.maxHp, STATS.baseHp + STATS.stamHp * 20);
  assert.ok(player.hp <= player.maxHp, "hp never exceeds max");
});

test("reloadMult: floored above zero even with absurd reload rating (the bricked-gun bug)", () => {
  derive(10, { gearReload: 0.6, rReload: 100000 });
  finite(player.reloadMult, "reloadMult");
  assert.ok(player.reloadMult > 0, "reload multiplier must stay positive so the gun can reload");
  assert.ok(player.reloadMult < 1, "and it should be a real reduction");
});

test("speed: soft-capped — cannot run away no matter the level or gear (the runaway bug)", () => {
  derive(999, { gearSpeed: 50, agi: 9999 });
  finite(player.speedMult, "speedMult");
  assert.ok(player.speedMult <= 1 + XP.speedSoftCap + 1e-9, "speed converges to the soft cap");
  assert.ok(player.speedMult > 1, "but still above base");
});

test("no NaN anywhere with a bare, gearless character", () => {
  derive(1);
  for (const k of ["dmgMult", "speedMult", "jumpMult", "maxHp", "reloadMult",
    "dashMult", "hasteFire", "hasteCd", "hasteCast", "graceMitigation"]) {
    finite(player[k], k);
  }
});

test("gear stats actually move the derived numbers", () => {
  derive(10);
  const bare = { dmg: player.dmgMult, dash: player.dashMult, fire: player.hasteFire };
  derive(10, { str: 100, dmgGlobal: 0.5, agi: 200, rAtkSpeed: 300 });
  assert.ok(player.dmgMult > bare.dmg, "Strength + Global raise damage");
  assert.ok(player.dashMult > bare.dash, "Agility lengthens the dash");
  assert.ok(player.hasteFire > bare.fire, "Attack Speed raises fire rate");
});
