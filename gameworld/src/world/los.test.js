// Line of sight over a heightmap.
//
// Terrain has no overhangs by construction, so "can these two see each other" is exactly
// "does the ground ever rise above the line between them". These tests pin that, and pin the
// assumption too — if Stage 2 adds real overhangs, the overhang case below is the one that
// should start failing and send someone to raycastVoxel.

import test from "node:test";
import assert from "node:assert";
import { terrainClear } from "./raycast.js";
import { heightAt, featuresAt, solidAt } from "./gen.js";

/** Two points on open ground with a known column between them. */
function ridgeBetween(from, to) {
  let peak = -Infinity, at = null;
  const n = 60;
  for (let i = 1; i < n; i++) {
    const t = i / n;
    const x = Math.floor(from.x + (to.x - from.x) * t);
    const z = Math.floor(from.z + (to.z - from.z) * t);
    const h = heightAt(x, z);
    if (h > peak) { peak = h; at = { x, z, h }; }
  }
  return at;
}

test("a point can see itself", () => {
  assert.ok(terrainClear(1000, 50, 1000, 1000, 50, 1000));
});

// THIS TEST USED TO SAY "high above the land, nothing blocks", on the reasoning that no
// column reached 78 so a line up there was always clear. That was true of a heightmap world
// and false the day sky islands landed — there are islands sitting at y 73-81 over the exact
// line it used against a land height of 40. It passed anyway, because sight was measured
// against heightAt and simply could not see them, which is the bug this file now guards.
//
// So it asks the honest version: a line through air the world genuinely has nothing in is
// clear, and it PROVES the air is empty first rather than assuming an altitude is safe.
test("a line through genuinely empty air is clear", () => {
  const y = 78;
  let a = null;
  for (let x = 2000; x < 2400 && !a; x += 4) {
    const clearHere = [0, 1, 2, 3, 4].every((k) => !solidAt(x + k * 4, y, 2000));
    if (clearHere) a = x;
  }
  assert.ok(a !== null, "the seed must offer some open air at this height");
  assert.ok(terrainClear(a, y, 2000, a + 16, y, 2000));
});

// The other half, and the actual fix: something up there DOES block now.
test("a sky island blocks a line that passes through it", () => {
  let found = null;
  for (let x = 2000; x < 3000 && !found; x++) {
    const h = heightAt(x, 2000);
    const f = featuresAt(x, 2000, h);
    if (f?.iHi !== undefined && f.iHi - f.iLo >= 2) found = { x, mid: (f.iLo + f.iHi) / 2 };
  }
  assert.ok(found, "the world must generate islands for this to mean anything");
  // Straight through the middle of it, from open air on one side to open air on the other.
  assert.ok(!terrainClear(found.x - 12, found.mid, 2000, found.x + 12, found.mid, 2000),
    "an island you can stand on must also be one you cannot see through");
});

test("underground, everything blocks", () => {
  assert.ok(!terrainClear(2000, 2, 2000, 2200, 2, 2200));
});

// The one that matters: a shooter at ground level on one side of a ridge cannot see a target
// at ground level on the other side.
test("a ridge blocks two bodies standing behind it", () => {
  const a = { x: 2600, z: 2600 }, b = { x: 2760, z: 2600 };
  const peak = ridgeBetween(a, b);
  const ay = heightAt(a.x, a.z) + 2, by = heightAt(b.x, b.z) + 2;
  const blocked = !terrainClear(a.x, ay, a.z, b.x, by, b.z);
  // Only assert the implication — this is real generated terrain, so the pair might happen
  // to be in a bowl. If the ridge out-tops both bodies, sight MUST be refused.
  if (peak.h > Math.max(ay, by)) {
    assert.ok(blocked, `ridge at ${peak.h} out-tops both (${ay}, ${by}) but sight was allowed`);
  }
});

test("standing on the ridge itself, you can see down both sides", () => {
  const a = { x: 2600, z: 2600 }, b = { x: 2760, z: 2600 };
  const peak = ridgeBetween(a, b);
  const eye = peak.h + 30;                       // well above anything between
  assert.ok(terrainClear(peak.x, eye, peak.z, a.x, heightAt(a.x, a.z) + 2, a.z));
  assert.ok(terrainClear(peak.x, eye, peak.z, b.x, heightAt(b.x, b.z) + 2, b.z));
});
