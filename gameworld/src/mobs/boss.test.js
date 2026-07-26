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

// THE FIGHT HAS A CEILING. Every distance a boss measured was flat, which was the whole truth
// while the world was a surface — with a sky full of islands it meant a boss standing under
// you at ground level read as being at your feet, and clubbed and beamed you from a hundred
// blocks below.
test("a boss under your feet still fights you", () => {
  const b = spawned();
  player.x = b.alive.x + 3; player.z = b.alive.z; player.y = b.alive.y + 2;
  b.update(0.1, () => {}, () => {}, () => {});
  assert.ok(b.alive, "close range, same level — this is just a fight");
});

test("a boss cannot reach you from far below", () => {
  const b = spawned();
  let hits = 0;
  player.x = b.alive.x; player.z = b.alive.z;      // directly overhead: flat distance is ZERO
  player.y = b.alive.y + BOSS.reachY + 40;
  for (let i = 0; i < 40; i++) b.update(0.1, () => { hits++; }, () => { hits++; }, () => { hits++; });
  assert.equal(hits, 0, "it landed a blow on someone forty blocks past its reach");
});

// Dropping onto one from a ledge has to stay a fight, or the answer to every boss is a rock.
test("a few storeys up is still inside the fight", () => {
  assert.ok(BOSS.reachY > 20, `reachY ${BOSS.reachY} is low enough that any ledge beats a boss`);
  assert.ok(BOSS.reachY < 60, `reachY ${BOSS.reachY} is high enough to be no limit at all`);
});
