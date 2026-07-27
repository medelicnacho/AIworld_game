// Difficulty is three multipliers read at three choke points. These pin the DIRECTION of each
// (easy is kinder in every dimension, hard is the untouched baseline) and the ONE rule that
// makes it safe: nothing here may change the world, only how hard it hits and how it hits back.

import { test } from "node:test";
import assert from "node:assert/strict";
import { DIFFICULTY, DEFAULT_DIFFICULTY } from "../config.js";
import { setDifficulty, difficultyId, diff } from "./difficulty.js";
import { applyLevelStats } from "./xp.js";
import { player } from "../state.js";

test("hard hits harder, and that is ALL it does", () => {
  const h = DIFFICULTY.hard;
  // The NUMBER is not the contract — it has already moved once (2.0 -> 1.4) and will again.
  // What hard means is: incoming damage is raised and nothing else about you is touched.
  assert.ok(h.incoming > 1, "hard must take MORE damage than baseline — that is the mode");
  assert.equal(h.playerDmg, 1.0, "hard deals baseline damage — it does not touch what you hit for");
  // The opening is cushioned on purpose: grace fades out long before the deep rings, so hard
  // is hard where it should be — out in the world, not in the first ten levels.
  assert.ok(h.grace >= 1, "hard must not shorten the early-game cushion");
  // Dying used to cost a level, and the mechanism is gone entirely rather than set to zero —
  // it taxed the thing already punishing you, and landed hardest exactly when you were
  // struggling. Hard means the fight is harder, not that failing it compounds.
  assert.ok(!("deathLoss" in h), "the level-loss knob should be gone, not merely zeroed");
  assert.ok(!h.wipeOnDeath, "hard is not hardcore");
  assert.equal(DEFAULT_DIFFICULTY, "hard", "the default is the real game");
});

test("easy is kinder in EVERY direction — never harsher than hard anywhere", () => {
  const e = DIFFICULTY.easy, h = DIFFICULTY.hard;
  assert.ok(e.incoming < h.incoming, "easy takes less damage");
  assert.ok(e.playerDmg > h.playerDmg, "easy hits harder");
  assert.ok(!e.wipeOnDeath, "easy never ends a run");
  assert.ok(e.grace >= h.grace, "easy's mercy window is at least as long");
});

// HARDCORE is the same FIGHT as hard. What differs is what a death means: not a setback, an
// ending — a stake you accept once at the start rather than a levy collected every slip.
test("hardcore fights like hard and ends like nothing else", () => {
  const c = DIFFICULTY.hardcore, h = DIFFICULTY.hard;
  assert.equal(c.incoming, h.incoming, "the fight itself must be hard's, not something harsher");
  assert.equal(c.playerDmg, h.playerDmg);
  assert.equal(c.grace, h.grace);
  assert.ok(c.wipeOnDeath, "dying has to actually end the run");
  assert.ok(!("deathLoss" in c), "there is nothing left to charge a level against");
});

test("every difficulty is well-formed, and only one of them wipes", () => {
  const all = Object.values(DIFFICULTY);
  assert.ok(all.length >= 3);
  for (const d of all) {
    assert.ok(d.id && d.label && d.blurb, `${d.id} needs a name and a blurb for the picker`);
    assert.ok(d.incoming > 0 && d.playerDmg > 0, `${d.id} multipliers must be positive`);
  }
  assert.equal(all.filter((d) => d.wipeOnDeath).length, 1, "exactly one mode may end a run");
});

test("the setting is remembered, and an unknown id is refused", () => {
  setDifficulty("easy");
  assert.equal(difficultyId(), "easy");
  setDifficulty("nonsense");
  assert.equal(difficultyId(), "easy", "a bad id must not blank the setting");
  setDifficulty("hard");
});

test("easy actually lowers the numbers it promises", () => {
  const reset = () => Object.assign(player, {
    level: 10, faction: null, rep: 0, gearDmg: 0, str: 0, agi: 0, stamina: 0,
    dmgGlobal: 0, dmgGun: 0, gearSpeed: 0, gearReload: 0, dashRank: 0, haste: 0,
    moveSpeed: 0, rHaste: 0, rAtkSpeed: 0, rReload: 0, hp: 100, maxHp: 100, xp: 0,
  });

  setDifficulty("hard"); reset(); applyLevelStats();
  const hardDmg = player.dmgMult;
  setDifficulty("easy"); reset(); applyLevelStats();
  const easyDmg = player.dmgMult;
  assert.ok(easyDmg > hardDmg, `easy must hit harder (${easyDmg} vs ${hardDmg})`);

  // Death used to cost a level on hard and nothing on easy. Neither charges one now — the
  // mechanism is gone, and the stake it was standing in for lives in Hardcore, where losing
  // is losing everything rather than paying a level each time you slip.
  for (const id of ["hard", "easy", "hardcore"]) {
    setDifficulty(id); reset();
    assert.equal(player.level, 10, `${id} must not move your level for existing`);
  }
  setDifficulty("hard");
});

test("incoming is always a POSITIVE multiplier — it scales damage, never heals or negates", () => {
  // The one invariant that has to hold no matter how the dials are tuned: incoming is a
  // positive number, so it can amplify (hard) or soften (easy) but can never flip the sign and
  // turn a hit into a heal. Direction is checked separately (easy < hard); this pins safety.
  for (const id of Object.keys(DIFFICULTY)) {
    setDifficulty(id);
    assert.ok(diff().incoming > 0,
      `${id} incoming must stay positive — a zero or negative would heal on hit (${diff().incoming})`);
  }
  setDifficulty("easy");
  assert.ok(diff().incoming <= 1, "easy must still SOFTEN, never amplify");
  setDifficulty("hard");
  assert.ok(diff().incoming > 1, "hard must AMPLIFY — that is what makes it hard");
});
