// The boss health bar's engagement clock.
//
// A boss can be alive two hundred metres away for minutes on end. The bar owns the top of
// the screen, so it only earns that while the fight is actually happening — and it has to
// survive a disengage (dodge out, heal, reload) or it would blink off at exactly the moments
// you most want to read it.

import test from "node:test";
import assert from "node:assert";
import * as THREE from "three";
import { Boss } from "./boss.js";
import { BOSS } from "../config.js";
import { player } from "../state.js";

/**
 * A boss clear of any sanctuary, with the player standing in front of it — update() culls a
 * boss you have walked away from, and a test that let that happen would pass because the
 * boss vanished rather than because the clock ran down.
 */
function spawned() {
  const b = new Boss(new THREE.Scene(), 0xB055);
  const alive = b.spawn(4000, 4000);
  assert.ok(alive, "test needs a spawned boss");
  player.x = 4060; player.z = 4000;
  assert.ok(BOSS.despawn > 60, "player must be inside despawn range");
  return b;
}

test("a boss you have not touched shows no bar", () => {
  assert.equal(spawned().alive.engaged, 0);
});

test("hitting the boss starts the clock", () => {
  const b = spawned();
  b.hit("boss", 1);
  assert.equal(b.alive.engaged, BOSS.barHold);
});

test("the clock runs down and stops at zero", () => {
  const b = spawned();
  b.engage();
  for (let i = 0; i < BOSS.barHold * 2 + 4; i++) b.update(0.5, () => {}, () => {}, () => {});
  assert.ok(b.alive, "the boss must still be here — otherwise this proves nothing");
  assert.equal(b.alive.engaged, 0);
});

// The disengage this exists to survive: stop shooting, live through a few seconds of
// dodging, and the bar must still be there when you come back.
test("the bar survives a pause shorter than the hold", () => {
  const b = spawned();
  b.hit("boss", 1);
  for (let i = 0; i < 8; i++) b.update(0.5, () => {}, () => {}, () => {});   // 4s of nothing
  assert.ok(b.alive.engaged > 0, "bar should still be up mid-fight");
  b.hit("boss", 1);
  assert.equal(b.alive.engaged, BOSS.barHold, "a fresh hit refreshes the full hold");
});

// engage() is called from main's damage callbacks too — being beamed is being in the fight.
test("engage() is safe with no boss alive", () => {
  const b = new Boss(new THREE.Scene(), 0xB055);
  assert.doesNotThrow(() => b.engage());
});
