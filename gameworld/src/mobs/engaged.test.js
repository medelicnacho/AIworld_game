// A FIGHT YOU ARE IN DOES NOT EVAPORATE.
//
// Two complaints from play, one cause. First: sniping with the Ash lance, a wounded body
// simply faded, so finishing it meant walking toward the thing you had deliberately engaged
// from range. Then, worse: leaping high above a brawl — the rotor and the cannon's recoil
// both throw you tens of blocks up ON PURPOSE — and the whole fight vanished underneath you.
//
// The cause was the despawn sweep's altitude term, written when the sky held half the war
// and climbing meant abandoning the ground. The game sells flight now, so that assumption
// had to go: the altitude weight came down, the leash got longer, and anything actually
// fighting you rides a FLAT leash on top of that.
//
// These tests are the corners of the rule. The first two are the reported bugs, kept as
// scenarios so nobody removes the guard without seeing what it was for.

import test from "node:test";
import assert from "node:assert";
import { Mobs } from "./mobs.js";
import { player } from "../state.js";
import { groundY } from "../world/gen.js";
import { MOB, WEAPONS } from "../config.js";

// The lance shot the first complaint was about: inside the weapon's reach, fired downhill.
const SNIPE = 70, DROP = 40;
// The leap the second was about: high enough over your own brawl that the old sweep read
// every body in it as gone. The rotor alone climbs ~16 blocks a spin; a recoil jump plus a
// perch puts you here easily.
const LEAP = 100;

function world() {
  const mobs = new Mobs({ add() {}, remove() {} }, 0xE7A6ED);
  player.x = 300; player.z = 40; player.y = groundY(300, 40) + 0.5;
  player.faction = null;
  return mobs;
}

/** A body at (flat out, blocks below) the player, freshly spawned into a headless world. */
function bodyAt(mobs, out, below) {
  mobs.spawnPack(0);
  const e = [...mobs.entities()][0];
  e.x = player.x + out; e.z = player.z; e.y = player.y - below;
  e.aggro = false; e.warFoeId = 0; e.engagedT = 0;
  return e;
}

test("a downhill lance shot no longer culls its own target — fixed at the root", () => {
  const mobs = world();
  const e = bodyAt(mobs, SNIPE, DROP);
  assert.ok(SNIPE < WEAPONS.lance.range, `${SNIPE} blocks is a shot the lance can make`);
  // This USED to be swept: at an altitude weight of 2.4 against a 105 leash it measured 119.
  // It survives now on the ordinary leash alone, with no reprieve needed — which is the
  // point. A guard that has to rescue ordinary play is a patch; this is a fixed assumption.
  assert.equal(mobs.sweepable(e), false,
    "a body you can shoot must not be a body the budget deletes");
});

test("leaping over your own brawl does not delete it", () => {
  const mobs = world();
  const e = bodyAt(mobs, 30, LEAP);          // you are 100 blocks above it, still fighting
  assert.ok(mobs.farFrom(e.x, e.y, e.z) > MOB.despawn,
    "a leap this high does still read as far on the ordinary sweep");
  e.aggro = true;                             // ...but it is hunting YOU
  assert.equal(mobs.sweepable(e), false,
    "anything hunting you rides the flat leash — leaving the ground is a MOVE, not an exit");
});

test("both halves of 'in a fight with you' count: hunted, and hit", () => {
  const mobs = world();
  const hit = bodyAt(mobs, 30, LEAP);
  mobs.hit(hit.id, 1);
  assert.ok(hit.engagedT > 0, "the one door all player damage comes through marks the body");
  assert.equal(mobs.sweepable(hit), false, "something you shot from range stays shootable");
});

test("the war's own scraps are theatre and sweep normally", () => {
  const mobs = world();
  const e = bodyAt(mobs, 30, LEAP);
  e.aggro = true; e.warFoeId = 7;             // aggro, but at another clan — not at you
  assert.equal(mobs.sweepable(e), true,
    "a brawl you are merely flying over is not your fight, and must not hold a budget slot");
});

test("the reprieve is a leash, not immortality: the loaded world is the limit", () => {
  const mobs = world();
  const e = bodyAt(mobs, SNIPE, DROP);
  mobs.hit(e.id, 1);
  e.x = player.x + MOB.engagedDespawn + 10;
  assert.equal(mobs.sweepable(e), true,
    "past the loaded chunks it goes regardless — a body standing on unloaded world is worse " +
    "than the bug this fixes");
});

test("the grace expires, and the ordinary sweep takes it back", () => {
  const mobs = world();
  const e = bodyAt(mobs, 30, LEAP);
  mobs.hit(e.id, 1);
  e.engagedT = 0; e.aggro = false;            // it lost you, and 45s passed
  assert.equal(mobs.sweepable(e), true, "a fight that ended is ordinary again");
});

// The shape of the whole rule, in relationships rather than numbers.
test("the leashes stay in the right order and inside the world", () => {
  assert.ok(MOB.engagedDespawn > MOB.despawn,
    "a fight must outlast ordinary interest, or the reprieve means nothing");
  assert.ok(MOB.engagedDespawn > WEAPONS.lance.range,
    "the reprieve must cover every shot the longest weapon can take");
  assert.ok(MOB.engagedDespawn <= 160,
    "...and stay within the streamed world, or bodies outlive the ground they stand on");
  assert.ok(MOB.despawnVScale > 1 && MOB.despawnVScale < 2,
    "altitude should count for more than horizontal — but never so much that a jump is a cull");
});
