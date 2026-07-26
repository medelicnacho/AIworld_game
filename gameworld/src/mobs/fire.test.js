// The burner's fire patch is a FLOOR hazard.
//
// It was tested as a horizontal circle with no height at all, so it burned you at the top of
// a jump and while you stood on a ledge above it. That went unnoticed while the world was
// flat and nobody had a reason to leave the ground; RELIEF gave the world ledges and the
// bug became the first thing anyone noticed.

import test from "node:test";
import assert from "node:assert";
import { inFireSlab } from "./mobs.js";
import { MOB, PLAYER } from "../config.js";

const GROUND = 40;                       // the patch is burning on this floor

test("standing in it burns", () => {
  assert.ok(inFireSlab(GROUND, GROUND));
});

test("a ledge above it does not", () => {
  assert.ok(!inFireSlab(GROUND + 2, GROUND), "two blocks up is clear ground");
  assert.ok(!inFireSlab(GROUND + 6, GROUND), "a spire top is obviously clear");
});

// The whole point: a jump gets you 1.36 blocks, and the flames stand 1.2, so clearing a
// patch mid-stride is a real option rather than a coin flip.
test("the top of a jump clears it", () => {
  const apex = GROUND + PLAYER.jumpSpeed ** 2 / (2 * -PLAYER.gravity);
  assert.ok(apex > GROUND + MOB.fireHeight, "test assumes a jump out-reaches the flames");
  assert.ok(!inFireSlab(apex, GROUND));
});

test("but leaving the ground is not instant immunity", () => {
  assert.ok(inFireSlab(GROUND + 0.6, GROUND), "mid-jump, still in the flames");
});

// The same overlap test, for free: a chasm floor below the patch is out of it too.
test("below it does not burn either", () => {
  assert.ok(!inFireSlab(GROUND - 4, GROUND));
});
