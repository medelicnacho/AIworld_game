// Mobs throwing themselves at ground they cannot walk up.
//
// RELIEF put ~2-block terraces across the world and MOB.maxClimb is 2.4, so anything above a
// terrace was ground no mob could reach: standing on a ledge beat every enemy in the game.
// The leap is the answer — high ground buys you TIME, not immunity.

import test from "node:test";
import assert from "node:assert";
import * as THREE from "three";
import { Mobs } from "./mobs.js";
import { MOB } from "../config.js";

function bodyAt(x, z, over = {}) {
  return {
    id: "t", kind: "mob", x, y: 40, z, hp: 10, faction: 0, aggro: true, flies: false,
    leapT: 0, leapCd: 0, leapX0: 0, leapZ0: 0, leapX1: 0, leapZ1: 0, leapY0: 0, leapY1: 0,
    heading: 0, wobble: 0, ...over,
  };
}

const mobs = () => new Mobs(new THREE.Scene(), 0x1EA9, {});

test("a body that is not chasing anything does not leap", () => {
  const m = mobs();
  assert.equal(m.tryLeap(bodyAt(3000, 3000, { aggro: false }), 1, 0), false);
});

test("a flier never leaps — it is already above the problem", () => {
  const m = mobs();
  assert.equal(m.tryLeap(bodyAt(3000, 3000, { flies: true }), 1, 0), false);
});

test("one leap at a time, and a cooldown after", () => {
  const m = mobs();
  const e = bodyAt(3000, 3000);
  m.tryLeap(e, 1, 0);
  assert.equal(m.tryLeap(e, 1, 0), false, "already airborne");
  e.leapT = 0;
  assert.ok(e.leapCd > 0, "a leap must leave a cooldown");
  assert.equal(m.tryLeap(e, 1, 0), false, "cooling down — must not strobe");
});

test("a leap commits to a landing spot and arcs to it", () => {
  const m = mobs();
  const e = bodyAt(3000, 3000);
  assert.ok(m.tryLeap(e, 1, 0), "open ground ahead should be leapable");
  const [x0, z0, x1, z1] = [e.leapX0, e.leapZ0, e.leapX1, e.leapZ1];
  assert.deepEqual([x0, z0], [3000, 3000]);
  assert.ok(Math.hypot(x1 - x0, z1 - z0) > 1, "it must actually go somewhere");

  // Mid-flight it is ABOVE the straight line between the two ends — that arc is the whole
  // readability of the move, and it is why restY must not consult the ground underneath.
  e.leapT = MOB.leapDur / 2;
  const mid = m.restY(e);
  assert.ok(mid > (e.leapY0 + e.leapY1) / 2, "the middle of a jump is above its chord");
});

test("stepLeaps carries a body all the way to its landing spot", () => {
  const m = mobs();
  const e = bodyAt(3000, 3000);
  m.tryLeap(e, 1, 0);
  const target = { x: e.leapX1, z: e.leapZ1 };
  m.entities = () => [e];                       // one body, no world needed
  for (let i = 0; i < 30; i++) m.stepLeaps(MOB.leapDur / 10);
  assert.equal(e.leapT, 0, "it must land");
  assert.equal(e.x, target.x);
  assert.equal(e.z, target.z);
});

// The limit that keeps terrain meaningful: a terrace is leapable, a spire is not.
test("leapClimb sits above a terrace and below a spire", () => {
  assert.ok(MOB.leapClimb > MOB.maxClimb, "a leap must reach further than a walk");
  assert.ok(MOB.leapClimb < 10, "it must not scale a spire, or high ground stops mattering");
});
