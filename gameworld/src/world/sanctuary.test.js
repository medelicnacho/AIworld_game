// Settlement placement — the invariant is simply that no two of them are the same ground.
//
// This exists because the city used to ignore it. Towns are dealt onto evenly-spread
// bearings and have never collided; the city took a random bearing in the same band and
// landed on a town in eight of the first fourteen rings.

import test from "node:test";
import assert from "node:assert";
import { tierSettlements, footprint, cityOfTier } from "./sanctuary.js";
import { SETTLE } from "../config.js";

const TIERS = 20;

test("no settlement overlaps another in the same ring", () => {
  const bad = [];
  for (let t = 0; t <= TIERS; t++) {
    const ss = tierSettlements(t);
    for (let i = 0; i < ss.length; i++) {
      for (let j = i + 1; j < ss.length; j++) {
        const a = ss[i], b = ss[j];
        // Two settlements only contend for ground if they are ON the same ground. A sky town
        // three hundred blocks over a field is not crowding it — that is the entire point of
        // building one up there.
        if (Math.abs(a.plateau - b.plateau) > 40) continue;
        const d = Math.hypot(a.x - b.x, a.z - b.z);
        const need = footprint(a) + footprint(b);
        if (d < need) bad.push(`${a.id} x ${b.id}: ${d.toFixed(0)} apart, needs ${need.toFixed(0)}`);
      }
    }
  }
  assert.deepEqual(bad, []);
});

test("no settlement reaches into the next ring's", () => {
  const bad = [];
  for (let t = 0; t < TIERS; t++) {
    for (const a of tierSettlements(t)) {
      for (const b of tierSettlements(t + 1)) {
        if (Math.abs(a.plateau - b.plateau) > 40) continue;
        const d = Math.hypot(a.x - b.x, a.z - b.z);
        const need = footprint(a) + footprint(b);
        if (d < need) bad.push(`${a.id} x ${b.id}: ${d.toFixed(0)} apart, needs ${need.toFixed(0)}`);
      }
    }
  }
  assert.deepEqual(bad, []);
});

// The retry loop is allowed to give up and take the roomiest candidate. It must never give
// up on placing a city at all — homeOfTier() answers respawns with it.
test("every ring from cityFromTier out still has its city", () => {
  for (let t = SETTLE.cityFromTier; t <= TIERS; t++) {
    assert.ok(cityOfTier(t), `tier ${t} lost its city`);
  }
});

// Placement is a pure function of the world seed (D1) — asking twice must not move anything.
test("placement is stable across calls", () => {
  const a = tierSettlements(4).map((s) => `${s.id}@${s.x.toFixed(3)},${s.z.toFixed(3)}`);
  const b = tierSettlements(4).map((s) => `${s.id}@${s.x.toFixed(3)},${s.z.toFixed(3)}`);
  assert.deepEqual(a, b);
});
