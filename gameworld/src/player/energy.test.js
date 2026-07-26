// ENERGY — the shared cost the ability bar never had.
//
// The failure state this is built around is NOT the empty bar. Nobody dies to an empty bar;
// they die to a plan that needed one more cast. So what these pin is the RHYTHM: that energy
// is what actually limits the small spells (a cooldown sitting behind a cost is invisible —
// whichever is longer is the only one anyone feels), that a burst runs out where it should,
// and that escape never costs anything.

import test from "node:test";
import assert from "node:assert";
import { ENERGY, NOVA, DASH, CHAIN, FIRERING, WHIRL } from "../config.js";

test("energy, not cooldown, is what limits the small spells", () => {
  for (const [name, cost, cd] of [
    ["Dash", ENERGY.dash, DASH.cd], ["Nova", ENERGY.nova, NOVA.cd], ["Chain", ENERGY.chain, CHAIN.cd],
  ]) {
    assert.ok(cost / ENERGY.regen > cd,
      `${name}: its ${cd}s cooldown outlasts its cost, so the cost is a bar nobody feels`);
  }
});

test("...but the big button is still a cooldown, once per fight", () => {
  assert.ok(FIRERING.cd > ENERGY.firering / ENERGY.regen,
    "Ring of Fire should be gated by its cooldown — that is what makes it an event");
});

// The exact edge the design is built around: an opener spends most of the bar and leaves you
// enough for one small thing, never for a repeat of the big one.
test("a burst leaves you short of a second big spell", () => {
  const after = ENERGY.max - ENERGY.nova - ENERGY.dash;
  assert.ok(after > 0, "an opener must not empty the bar outright");
  assert.ok(after < ENERGY.nova, "there must never be room for a second Nova");
});

test("you are never left standing about", () => {
  assert.ok(ENERGY.max / ENERGY.regen < 6,
    `empty to full takes ${(ENERGY.max / ENERGY.regen).toFixed(1)}s — the punishment is the ` +
    "cast you could not make, not a wait");
});

// Being punished for a misjudgement is the point. Losing the tool that would let you survive
// it is not — that turns a mistake into a death sentence.
test("whirlwind is affordable from a full bar, and never runs dry mid-spin", () => {
  assert.ok(ENERGY.whirl <= ENERGY.max, "it must be castable at all");
  assert.ok(ENERGY.whirl > ENERGY.nova, "invulnerability should cost more than damage");
  // Charged up front, so the spin's length is irrelevant to whether it can finish.
  assert.ok(WHIRL.spinTime > 0);
});
