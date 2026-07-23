// Pure-math tripwires for the world's difficulty geometry. tierAt is the closed-form inverse
// of tierStart — the exact kind of relationship an off-by-one hides in until you're deep.

import { test } from "node:test";
import assert from "node:assert/strict";
import { tierStart, tierWidth, tierAt, ringPressure } from "./gen.js";
import { RING_SIZE } from "../config.js";

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

test("ringPressure: accelerates — grows faster than linear past ring 1", () => {
  const ramp = 0.2;
  for (let r = 2; r < 12; r++) {
    assert.ok(ringPressure(r, ramp) > r, `effective ring must exceed ${r}`);
    // Each step's increase should itself grow (convexity).
    const step1 = ringPressure(r, ramp) - ringPressure(r - 1, ramp);
    const step2 = ringPressure(r + 1, ramp) - ringPressure(r, ramp);
    assert.ok(step2 > step1, `acceleration should increase at ring ${r}`);
  }
});

test("ringPressure: ramp 0 collapses to the flat curve", () => {
  for (let r = 0; r < 10; r++) assert.equal(ringPressure(r, 0), r);
});
