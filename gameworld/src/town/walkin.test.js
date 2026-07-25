// THE WALK-IN TEST — the one path no other test covers, because every other test either
// stubs the mob layer or teleports the player. The garrison glitch lived precisely there:
// muster fires ~150-208 from a town's centre, the minimap shows the group at 130, fog hides
// it past ~106 — and a duplicate distance-cull inside the real Mobs.update() AI loop deleted
// defenders as they crossed the (105, ~132] band on approach. Spawn, silently unspawn, leave
// 1-2 survivors at the gate, and the kill that cleared them re-mustered everything. Unit
// tests with a fake mob layer can never catch that class of bug; this file runs the REAL
// Mobs against the REAL Raids and physically walks the player in.

import { test } from "node:test";
import assert from "node:assert/strict";
import { Mobs } from "../mobs/mobs.js";
import { Raids } from "./raid.js";
import { player, world } from "../state.js";
import { tierSettlements } from "../world/sanctuary.js";
import { groundY } from "../world/gen.js";

const DT = 1 / 60;
const sceneStub = { add() {}, remove() {} };

/** Count live defenders belonging to one town. */
const garrisonOf = (townId) =>
  [...world.entities.values()].filter((e) => e.defender === townId).length;

test("walking up to a rival town: the garrison NEVER shrinks on approach", () => {
  world.entities.clear();
  world.regions.clear();
  player.faction = "iron";
  const s = tierSettlements(1).find((t) => !t.city && t.faction === 1);   // a Vale town

  const mobs = new Mobs(sceneStub, 0x5EED);
  const raids = new Raids(mobs, () => {}, () => {});

  // Start well outside muster range and walk straight at the town centre, ticking the REAL
  // update loops — the exact frame order main.js uses (mobs, then raids).
  let mustered = 0;
  for (let d = 260; d > 6; d -= 1.2) {           // ~1.2 units/frame ≈ a fast sprint
    player.x = s.x + d;
    player.z = s.z;
    player.y = groundY(player.x, player.z) + 0.5;
    mobs.update(DT, () => {});
    raids.update(DT);
    const now = garrisonOf(s.id);
    if (now > mustered) mustered = now;          // the muster moment
    // THE INVARIANT THE GLITCH BROKE: once mustered, the count can never DROP while the
    // player only walks toward the town — nobody died, so nobody may vanish.
    assert.ok(now >= mustered || now === 0,
      `garrison shrank on approach at ${d.toFixed(0)}u out: ${now}/${mustered} — `
      + "defenders are being despawned by distance again");
  }

  // At the gate: the full war-camp, present without a single shot fired.
  const finalCount = garrisonOf(s.id);
  assert.ok(mustered >= 15, `a full garrison mustered (got ${mustered})`);
  assert.equal(finalCount, mustered,
    `every mustered body is still standing at the gate (${finalCount}/${mustered})`);
  const champs = [...world.entities.values()].filter((e) => e.defender === s.id && e.champion);
  assert.equal(champs.length, 3, "all three champions stand among them");
});
