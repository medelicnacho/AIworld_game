// Pure-math tripwires for the world's difficulty geometry. tierAt is the closed-form inverse
// of tierStart — the exact kind of relationship an off-by-one hides in until you're deep.

import { test } from "node:test";
import assert from "node:assert/strict";
import { tierStart, tierWidth, tierAt, ringPressure } from "./gen.js";
import { RING_SIZE, RAMP_FREE, RAMP_KNEE } from "../config.js";

test("tierStart: tier 0 begins at the origin", () => {
  assert.equal(tierStart(0), 0);
});

test("tierStart: bands begin further out as tier rises", () => {
  for (let t = 0; t < 12; t++) {
    assert.ok(tierStart(t + 1) > tierStart(t), `tier ${t + 1} must start beyond ${t}`);
  }
});

test("tierWidth: a band's width equals the gap to the next tier's start", () => {
  for (let t = 0; t < 12; t++) {
    const gap = tierStart(t + 1) - tierStart(t);
    assert.ok(Math.abs(gap - tierWidth(t)) < 1e-6, `width mismatch at tier ${t}`);
  }
});

test("tierAt is the inverse of tierStart — every band round-trips", () => {
  // Sample just inside and just past each band boundary along the +x axis.
  for (let t = 0; t < 15; t++) {
    const start = tierStart(t);
    // A hair past the start: still tier t (until the next band).
    assert.equal(tierAt(start + 0.5, 0), t, `just inside band ${t}`);
    // A hair before the next start: still tier t.
    assert.equal(tierAt(tierStart(t + 1) - 0.5, 0), t, `just before band ${t + 1} ends`);
  }
});

test("tierAt: origin and negative-coordinate symmetry", () => {
  assert.equal(tierAt(0, 0), 0);
  assert.equal(tierAt(RING_SIZE * 3, 0), tierAt(0, -RING_SIZE * 3), "radial: sign-independent");
});

test("ringPressure: rings 0 and 1 are unbent (the (ring-1) term is zero)", () => {
  assert.equal(ringPressure(0, 0.2), 0);
  assert.equal(ringPressure(1, 0.2), 1);
});

test("ringPressure: the early rings accelerate — leaving the Commons must cost", () => {
  const ramp = 0.2;
  for (let r = 2; r < RAMP_FREE; r++) {
    assert.ok(ringPressure(r, ramp) > r, `effective ring must exceed ${r}`);
    // Each step's increase should itself grow (convexity).
    const step1 = ringPressure(r, ramp) - ringPressure(r - 1, ramp);
    const step2 = ringPressure(r + 1, ramp) - ringPressure(r, ramp);
    assert.ok(step2 > step1, `acceleration should increase at ring ${r}`);
  }
});

// AND THEN IT STOPS ACCELERATING, which is the whole point. Mob HP is hpGrowth raised to this
// number and the player's damage grows exponentially in a LINE, so while this was a pure
// quadratic the two were of different ORDER and could only diverge. Measured before the fix, a
// plain mob took 0.8 swings at ring 2, 20.7 at ring 8 and 3925 at ring 12. Depth must keep
// costing — it must not become an exponent of a different order to the player's own growth.
test("ringPressure: the deep settles into a straight line, and never stops costing", () => {
  const ramp = 0.2;
  // Past the free rings the curve CONVERGES on a slope of 1 + ramp*RAMP_KNEE — approaching it
  // from below, because the saturation bites hardest immediately after RAMP_FREE. What has to
  // hold is that it never exceeds that slope: a bounded slope is a straight line, and a
  // straight line is the same ORDER as the player's own growth, which is the entire fix.
  const slope = 1 + ramp * RAMP_KNEE;
  let prev = ringPressure(RAMP_FREE, ramp);
  for (let r = RAMP_FREE + 1; r < 60; r++) {
    const now = ringPressure(r, ramp);
    assert.ok(now > prev, `ring ${r} must still cost more than ${r - 1}`);
    assert.ok(now - prev <= slope + 1e-9,
      `ring ${r} jumped ${(now - prev).toFixed(3)}, past the ${slope} it may converge to`);
    prev = now;
  }
  // Measured against the shape that was broken rather than against an exact line — the curve
  // converges to `slope` plus a small constant, so it sits a hair above ring*slope for ever.
  // What matters is the order: the old quadratic put ring 50 at 540, and a plain mob there
  // would have needed more swings than a session has seconds.
  const quadratic = 50 + ramp * 50 * 49;
  assert.ok(ringPressure(50, ramp) < quadratic / 5,
    `ring 50 pressure ${ringPressure(50, ramp).toFixed(0)} is still near the old ${quadratic}`);
});

test("ringPressure: ramp 0 collapses to the flat curve", () => {
  for (let r = 0; r < 10; r++) assert.equal(ringPressure(r, 0), r);
});
