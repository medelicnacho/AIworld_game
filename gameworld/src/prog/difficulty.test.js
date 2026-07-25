// Difficulty is three multipliers read at three choke points. These pin the DIRECTION of each
// (easy is kinder in every dimension, hard is the untouched baseline) and the ONE rule that
// makes it safe: nothing here may change the world, only how hard it hits and how it hits back.

import { test } from "node:test";
import assert from "node:assert/strict";
import { DIFFICULTY, DEFAULT_DIFFICULTY } from "../config.js";
import { setDifficulty, difficultyId, diff } from "./difficulty.js";
import { applyLevelStats, loseLevel } from "./xp.js";
import { player } from "../state.js";

test("hard hits twice as hard, but only its incoming — dealing and death stay baseline", () => {
  const h = DIFFICULTY.hard;
  assert.equal(h.incoming, 2.0, "hard takes DOUBLE damage — the sting is the whole point of hard");
  assert.equal(h.playerDmg, 1.0, "hard deals baseline damage — it does not touch what you hit for");
  assert.equal(h.deathLoss, 1.0, "hard loses a level on death");
  assert.equal(DEFAULT_DIFFICULTY, "hard", "the default is the real game");
});

test("easy is kinder in EVERY direction — never harsher than hard anywhere", () => {
  const e = DIFFICULTY.easy, h = DIFFICULTY.hard;
  assert.ok(e.incoming < h.incoming, "easy takes less damage");
  assert.ok(e.playerDmg > h.playerDmg, "easy hits harder");
  assert.ok(e.deathLoss < h.deathLoss, "easy costs less on death");
  assert.ok(e.grace >= h.grace, "easy's mercy window is at least as long");
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

  // Death penalty: hard loses a level, easy loses nothing.
  setDifficulty("hard"); reset(); player.xp = 0;
  assert.equal(loseLevel(), true, "hard death costs a level");
  assert.equal(player.level, 9);

  setDifficulty("easy"); reset(); player.xp = 0;
  assert.equal(loseLevel(), false, "easy death costs no level");
  assert.equal(player.level, 10, "the level is untouched on easy");
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
