// Tripwires for the world's clock.

import { test } from "node:test";
import assert from "node:assert/strict";
import { DayNight } from "./daynight.js";
import { DAYNIGHT } from "../config.js";

test("the day has the right shape: dawn rises, noon holds, dusk falls, night is dark", () => {
  const d = new DayNight();
  d.t = 0;                       assert.equal(d.daylight(), 0, "the instant of dawn is dark");
  d.t = DAYNIGHT.edge / 2;       assert.equal(d.daylight(), 0.5, "half-dawn is half-light");
  d.t = DAYNIGHT.dayLen / 2;     assert.equal(d.daylight(), 1, "midday is full");
  d.t = DAYNIGHT.dayLen - DAYNIGHT.edge / 2;
  assert.equal(d.daylight(), 0.5, "half-dusk is half-light");
  d.t = DAYNIGHT.dayLen + 100;   assert.equal(d.daylight(), 0, "night is night");
  assert.equal(d.phase(), "night");
  d.t = DAYNIGHT.edge / 2;       assert.equal(d.phase(), "dawn");
});

test("sleep moves the clock to dawn, and the cycle wraps rather than escaping", () => {
  const d = new DayNight();
  d.t = DAYNIGHT.dayLen + 500;
  d.skipToDawn();
  assert.equal(d.t, 0);
  d.t = d.cycle - 1;
  d.advance(10);
  assert.ok(d.t < d.cycle && d.t >= 0, "advance wraps");
});
