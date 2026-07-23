// Pure-math tripwires for the stat formulas. These are the numbers silently load-bearing
// under every fight — the kind of thing "it compiles and runs" never checks. Run: npm test.

import { test } from "node:test";
import assert from "node:assert/strict";
import { ratingPct, armorDR, maxHpFor } from "./stats.js";
import { STATS } from "../config.js";

test("ratingPct: zero and negative ratings give no bonus", () => {
  assert.equal(ratingPct(0, 150), 0);
  assert.equal(ratingPct(-50, 150), 0);
  assert.equal(ratingPct(undefined, 150), 0);
});

test("ratingPct: rating equal to K is exactly 50%", () => {
  assert.equal(ratingPct(150, 150), 0.5);
});

test("ratingPct: diminishing — always climbs, never reaches 1", () => {
  let prev = 0;
  for (let r = 1; r <= 10000; r += 50) {
    const p = ratingPct(r, 150);
    assert.ok(p > prev, `should be monotonic increasing at ${r}`);
    assert.ok(p < 1, `must never reach 100% (was ${p} at ${r})`);
    prev = p;
  }
});

test("armorDR: zero armour is zero mitigation", () => {
  assert.equal(armorDR(0, 0), 0);
  assert.equal(armorDR(0, 5), 0);
});

test("armorDR: matches the WoW curve armor/(armor+K+perTier*tier)", () => {
  const a = 300, tier = 0;
  assert.equal(armorDR(a, tier), a / (a + STATS.armorK + STATS.armorPerTier * tier));
});

test("armorDR: same armour is worth LESS against a deeper attacker", () => {
  assert.ok(armorDR(300, 0) > armorDR(300, 3), "deeper tier must reduce mitigation");
  assert.ok(armorDR(300, 3) > armorDR(300, 8));
});

test("armorDR: never exceeds the sanity cap", () => {
  assert.ok(armorDR(1e9, 0) <= STATS.armorDRCap);
});

test("maxHpFor: base at zero stamina, +stamHp per point", () => {
  assert.equal(maxHpFor(0), STATS.baseHp);
  assert.equal(maxHpFor(undefined), STATS.baseHp);
  assert.equal(maxHpFor(10), STATS.baseHp + STATS.stamHp * 10);
});
