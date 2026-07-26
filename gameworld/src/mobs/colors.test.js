// A body's colour answers exactly one question: whose side is it on.
//
// Elite colours used to be derived — the faction colour lerped 40% toward white. That
// brightens a hue and ANNIHILATES a faction that hasn't got one: Iron is deliberately
// achromatic, so #26262c became #7d7d80, a neutral grey naming no side at all. Since only
// elites can fly and elites are the big ones, that one line greyed out every large or
// airborne Iron body in the game.

import test from "node:test";
import assert from "node:assert";
import * as THREE from "three";
import { Mobs } from "./mobs.js";

const mobs = new Mobs(new THREE.Scene(), 0xC010);
const FACTIONS = [0, 1, 2];
const NAMES = ["Iron", "Ash", "Vale"];

/** Straight RGB distance — crude, but it is the question being asked: do these read alike? */
function dist(a, b) {
  return Math.hypot(a.r - b.r, a.g - b.g, a.b - b.b);
}

// THE INVARIANT. An elite must still look like its own faction — closer to the colour its
// rank and file wear than to any other faction's. This is what the old derivation broke.
test("an elite reads as its own faction, not another", () => {
  for (const f of FACTIONS) {
    const elite = mobs.colorOf({ elite: true, faction: f });
    const own = dist(elite, mobs.factionCols[f]);
    for (const other of FACTIONS) {
      if (other === f) continue;
      assert.ok(own < dist(elite, mobs.factionCols[other]),
        `${NAMES[f]} elite is closer to ${NAMES[other]}'s colour than to its own`);
    }
  }
});

test("no elite colour is neutral grey", () => {
  for (const f of FACTIONS) {
    const c = mobs.colorOf({ elite: true, faction: f });
    const spread = Math.max(c.r, c.g, c.b) - Math.min(c.r, c.g, c.b);
    assert.ok(spread > 0.04, `${NAMES[f]} elite has almost no colour in it (spread ${spread.toFixed(3)})`);
  }
});

test("an elite is brighter than its rank and file", () => {
  for (const f of FACTIONS) {
    const lum = (c) => c.r * 0.3 + c.g * 0.6 + c.b * 0.1;
    assert.ok(lum(mobs.colorOf({ elite: true, faction: f })) > lum(mobs.factionCols[f]),
      `${NAMES[f]} elite must read as lit`);
  }
});

// Iron being the dark one is the tell that survives at any distance.
test("Iron stays the darkest faction, elite or not", () => {
  const lum = (c) => c.r * 0.3 + c.g * 0.6 + c.b * 0.1;
  for (const elite of [false, true]) {
    const iron = lum(mobs.colorOf({ elite, faction: 0 }));
    assert.ok(iron < lum(mobs.colorOf({ elite, faction: 1 })), "Iron must be darker than Ash");
    assert.ok(iron < lum(mobs.colorOf({ elite, faction: 2 })), "Iron must be darker than Vale");
  }
});

// Every flying mob is an elite, so this pairing is exactly what the bug report was about.
test("the three factions stay apart from each other at elite tier", () => {
  for (const a of FACTIONS) {
    for (const b of FACTIONS) {
      if (a >= b) continue;
      const d = dist(mobs.colorOf({ elite: true, faction: a }), mobs.colorOf({ elite: true, faction: b }));
      assert.ok(d > 0.2, `${NAMES[a]} and ${NAMES[b]} elites look too alike (${d.toFixed(2)})`);
    }
  }
});
