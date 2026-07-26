// HEIGHT PAYS — but only a little, and only for fighting.
//
// The sky earns a bonus: no retreating downhill, a long fall back to the bottom of a climb
// you just made, and camps as thick as anything on the ground. Without one the archipelago is
// a scenic detour and the optimal play is to stay on the floor. With too much of one it
// quietly replaces DEPTH as the game's long climb, which is the thing it must not do.

import test from "node:test";
import assert from "node:assert";
import { altitudeBonus } from "./xp.js";
import { player } from "../state.js";
import { groundY } from "../world/gen.js";
import { XP } from "../config.js";

function standAt(up) {
  player.x = 3000; player.z = 3000;
  player.y = groundY(player.x, player.z) + up;
}

test("on the ground it is worth nothing", () => {
  standAt(0);
  assert.equal(altitudeBonus(), 1);
});

test("it climbs with you and stops", () => {
  standAt(XP.altFull / 2);
  const half = altitudeBonus();
  assert.ok(half > 1.2 && half < 1.4, `half height should be about 1.3, got ${half.toFixed(2)}`);
  standAt(XP.altFull);
  assert.ok(Math.abs(altitudeBonus() - (1 + XP.altBonus)) < 1e-9);
  standAt(XP.altFull * 10);
  assert.equal(altitudeBonus(), 1 + XP.altBonus, "ten times as high is not ten times the pay");
});

// A mountaintop is not the sky. The bonus is measured against the LOCAL land, so you have to
// be off the world rather than high on it.
test("digging down never pays", () => {
  standAt(-50);
  assert.equal(altitudeBonus(), 1);
});

// The guard rail that matters: this must stay smaller than going OUT.
test("height is worth less than depth", () => {
  assert.ok(XP.altBonus <= 1,
    `altBonus ${XP.altBonus} would make climbing worth more than a whole extra ring`);
});
