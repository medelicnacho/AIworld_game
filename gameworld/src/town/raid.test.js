// Tripwires for the raid layer and the settlement dealing underneath it. The raid's combat
// can only be felt in play, but the RULES that make it fair — every ring holds all three
// colours, a sacked town stays down long enough to matter, the champions outrank the line —
// live in data, and data can be pinned.

import { test } from "node:test";
import assert from "node:assert/strict";
import { RAID, SETTLE } from "../config.js";
import { townCount, tierSettlements } from "../world/sanctuary.js";

test("every ring deals all three colours, and deals them EVENLY", () => {
  // A random roll can hand a whole ring to one faction, and a player hunting their own
  // colour (or a rival to raid) finds nothing. The dealing must guarantee representation.
  for (let t = 1; t <= 6; t++) {
    const n = townCount(t);
    assert.equal(n % 3, 0, `tier ${t}: town count ${n} must be a multiple of three`);
    const towns = tierSettlements(t).filter((s) => !s.city);
    const byFac = [0, 0, 0];
    for (const s of towns) {
      assert.ok(s.faction === 0 || s.faction === 1 || s.faction === 2,
        `tier ${t}: a town must fly one of the three colours, got ${s.faction}`);
      byFac[s.faction]++;
    }
    assert.ok(byFac.every((c) => c === byFac[0]),
      `tier ${t}: colours must come out even, got ${byFac.join("/")}`);
  }
});

test("more towns than before, growing with depth, capped", () => {
  assert.equal(townCount(0), SETTLE.townsBase, "the spawn town stands alone");
  for (let t = 2; t <= 6; t++) {
    assert.ok(townCount(t) >= townCount(t - 1), "the frontier gets denser, never thinner");
  }
  assert.ok(townCount(1) >= 6, "even the first ring out holds two of each colour");
  assert.ok(townCount(9) <= SETTLE.townCap, "and the cap holds");
});

test("the sack is a RAID, not a faucet: rebuild long, loot real, champions ranked", () => {
  // The rebuild timer is what separates 'raiding' from 'farming one poor village forever'.
  assert.ok(RAID.rebuild >= 300, "a sacked town must stay down for minutes, not moments");
  assert.ok(RAID.loot > 0, "victory must LOOK like victory — the fountain is the point");
  // The hierarchy the fight teaches: soldiers < adept < herbalist < quartermaster. The
  // healer outlasting the artillery is what makes kill order a decision, and the QM being
  // the wall is what makes the fight end on a boss rather than fizzle out.
  assert.ok(RAID.soldierHp < RAID.adeptHp, "a champion outranks the line");
  assert.ok(RAID.adeptHp < RAID.herbHp, "the healer must survive being focused first");
  assert.ok(RAID.herbHp < RAID.qmHp, "the quartermaster is the boss of the town");
  assert.ok(RAID.qmDamage > 1, "...and hits harder than a soldier");
  // The barrage must be a stream you can dodge by moving, not one lump or an endless hose.
  assert.ok(RAID.burst >= 3 && RAID.burst <= 8, "a barrage, not a shot or a hose");
  assert.ok(RAID.burstGap > 0.05 && RAID.burstGap < 0.6, "spaced so strafing answers it");
  // The heal pulse must matter without making the garrison unkillable by one player.
  assert.ok(RAID.healFrac > 0 && RAID.healFrac <= 0.25, "a lifeline, not immortality");
  assert.ok(RAID.notice > 0 && RAID.engage > RAID.notice,
    "the garrison musters before it can possibly see you — never in front of you");
});
