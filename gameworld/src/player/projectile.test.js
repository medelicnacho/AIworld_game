// Tripwires for PROJECTILE CONTACT — the playtest bug where a lobber shell and a thrown
// grenade both sailed clean through a boss and only ever burst on terrain, so the
// aim-forgiving weapon could score a perfect direct hit for zero damage.
//
// The contract under test is the shape of the test main installs as `bodyAt`: it consults
// the SAME target spheres the hitscan already trusts, so a grenade and a bullet can never
// disagree about what is solid.

import { test } from "node:test";
import assert from "node:assert/strict";
import { BOSS } from "../config.js";

/** The predicate exactly as main builds it, over injected target lists. */
function makeBodyAt(targets) {
  return (x, y, z) => targets.find((t) => {
    const r = t.r + 0.35;
    const dx = t.x - x, dy = t.y - y, dz = t.z - z;
    return dx * dx + dy * dy + dz * dz <= r * r;
  }) || null;
}

test("a shell flying through a BOSS registers — the bug this fixes", () => {
  // The boss's own bulk sphere, at the scale boss.targets() reports.
  const s = BOSS.scale;
  const boss = [{ id: -1, tag: "boss", x: 40, y: 1.5 * s, z: 0, r: 1.15 * s }];
  const bodyAt = makeBodyAt(boss);
  // A shell arcing along y = boss centre height, stepping toward it, MUST report contact
  // somewhere inside the silhouette rather than passing through.
  let contacted = false;
  for (let x = 0; x < 80; x += 0.9) if (bodyAt(x, 1.5 * s, 0)) { contacted = true; break; }
  assert.ok(contacted, "a shell on a collision course must burst on the boss");
  // Dead centre is unambiguous.
  assert.ok(bodyAt(40, 1.5 * s, 0), "a direct hit is a hit");
  // And a shot that genuinely misses still flies on.
  assert.equal(bodyAt(40, 1.5 * s, 40), null, "a clean miss stays a miss");
});

test("the weak core counts too — the lobber can reward aim it does not require", () => {
  const s = BOSS.scale;
  const bodyAt = makeBodyAt([{ id: -2, tag: "bossWeak", x: 10, y: 5, z: 2, r: 0.42 * s }]);
  assert.ok(bodyAt(10, 5, 2), "the core is a body like any other");
});

test("mob spheres are padded, so a clipped shoulder bursts", () => {
  const bodyAt = makeBodyAt([{ id: 7, x: 0, y: 1, z: 0, r: 0.55 }]);
  assert.ok(bodyAt(0.8, 1, 0), "a graze inside the pad still detonates");
  assert.equal(bodyAt(2.5, 1, 0), null, "but empty air does not");
});

test("allies are absent from the list, so a shell never bursts on your own army", () => {
  // mobs.targets() filters isMyAlly before main ever sees them; the predicate simply has
  // nothing to find, which is what makes friendly fire impossible rather than merely rude.
  const bodyAt = makeBodyAt([]);
  assert.equal(bodyAt(0, 1, 0), null);
});
