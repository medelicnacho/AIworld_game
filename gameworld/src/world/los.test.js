// Line of sight over a heightmap.
//
// Terrain has no overhangs by construction, so "can these two see each other" is exactly
// "does the ground ever rise above the line between them". These tests pin that, and pin the
// assumption too — if Stage 2 adds real overhangs, the overhang case below is the one that
// should start failing and send someone to raycastVoxel.

import test from "node:test";
import assert from "node:assert";
import { terrainClear } from "./raycast.js";
import { heightAt } from "./gen.js";

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

test("high above the land, nothing blocks", () => {
  // CHUNK_Y is 80 and no column reaches it, so a line up here must always be clear.
  assert.ok(terrainClear(2000, 78, 2000, 2200, 78, 2200));
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
