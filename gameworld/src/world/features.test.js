// Sky islands and overhangs — the world's third dimension.
//
// Both are a 2D mask with a vertical profile rather than 3D noise, which is the only reason
// they are affordable: fillChunk keeps ONE evaluation per column instead of one per voxel,
// the difference between a chunk building in about a millisecond and in eighty. These tests
// guard that property as much as the shapes themselves.

import test from "node:test";
import assert from "node:assert";
import { featuresAt, heightAt, surfaceNear, solidAt, fillChunk } from "./gen.js";
import { CHUNK_Y } from "../config.js";

/** Hunt the seeded world for a column with a real island over it. */
function findIsland(minThick = 3) {
  for (let i = 0; i < 60000; i++) {
    const a = i * 2.39996, rad = 1800 + (i % 1400);
    const x = Math.floor(Math.cos(a) * rad), z = Math.floor(Math.sin(a) * rad);
    const h = heightAt(x, z);
    const f = featuresAt(x, z, h);
    if (f?.iHi !== undefined && f.iHi - f.iLo >= minThick) return { x, z, h, f };
  }
  return null;
}

test("the Commons has a plain sky and solid ground", () => {
  for (let i = 0; i < 400; i++) {
    const a = i * 2.39996, rad = 20 + (i % 90);
    const x = Math.floor(Math.cos(a) * rad), z = Math.floor(Math.sin(a) * rad);
    assert.equal(featuresAt(x, z, heightAt(x, z)), null,
      "nothing exotic where movement is taught");
  }
});

test("an island is standable: solid top, open air above it", () => {
  const it = findIsland();
  assert.ok(it, "the world must actually generate islands");
  const top = Math.floor(it.f.iHi);
  assert.ok(solidAt(it.x, top, it.z), "its top must be solid");
  assert.ok(!solidAt(it.x, top + 1, it.z), "and open above, or you cannot stand there");
});

test("an island floats — there is air between it and the land", () => {
  const it = findIsland();
  assert.ok(it.f.iLo > it.h + 1, "it must not be a hill with extra steps");
  assert.ok(!solidAt(it.x, Math.floor(it.f.iLo) - 1, it.z), "open air underneath");
});

test("nothing punches through the top of the world", () => {
  for (let i = 0; i < 8000; i++) {
    const a = i * 2.39996, rad = 1500 + (i % 4000);
    const x = Math.floor(Math.cos(a) * rad), z = Math.floor(Math.sin(a) * rad);
    const f = featuresAt(x, z, heightAt(x, z));
    if (f?.iHi !== undefined) assert.ok(f.iHi <= CHUNK_Y - 2, `island reached ${f.iHi}`);
  }
});

// THE LID. An overhang bites air out from underneath; it must never hole the surface you
// walk on, because groundY — and therefore every spawn and every map — still means that.
test("an overhang never opens a hole in the ground you walk on", () => {
  let checked = 0;
  for (let i = 0; i < 40000 && checked < 60; i++) {
    const a = i * 2.39996, rad = 900 + (i % 3000);
    const x = Math.floor(Math.cos(a) * rad), z = Math.floor(Math.sin(a) * rad);
    const h = heightAt(x, z);
    const f = featuresAt(x, z, h);
    if (f?.hHi === undefined) continue;
    checked++;
    assert.ok(solidAt(x, h, z), `the surface at ${x},${z} was carved away`);
  }
  assert.ok(checked > 0, "the world must actually generate overhangs");
});

// The question a multi-surface world has to answer, and the reason mobs do not walk off
// islands into the air.
test("surfaceNear answers the floor you are actually on", () => {
  const it = findIsland();
  const top = Math.floor(it.f.iHi) + 1;
  assert.equal(surfaceNear(it.x, it.z, top + 2), top, "stood on the island, you get the island");
  assert.equal(surfaceNear(it.x, it.z, it.h), it.h + 1, "stood beneath it, you get the land");
});

test("a plain column still just answers the land", () => {
  const x = 40, z = 12;                     // spawn-side, no features by the test above
  assert.equal(surfaceNear(x, z, 999), heightAt(x, z) + 1);
  assert.equal(surfaceNear(x, z, -999), heightAt(x, z) + 1);
});

// The budget this whole approach exists to protect.
test("a chunk still builds in about a millisecond", () => {
  const t0 = performance.now();
  for (let i = 0; i < 20; i++) fillChunk(300 + i, 300);
  const ms = (performance.now() - t0) / 20;
  assert.ok(ms < 8, `chunk build took ${ms.toFixed(2)}ms — the per-voxel cliff is ~80ms`);
});

// PEBBLES — the small ones. A chain is only crossable if the gap between two real platforms
// has something in the middle of it; these are that something.
test("the sky has small stepping stones, not only platforms", () => {
  let small = 0, total = 0, run = 0;
  for (let x = 1800; x < 9800; x++) {
    const f = featuresAt(x, 0, heightAt(x, 0));
    if (f?.iHi !== undefined) { run++; continue; }
    if (run) { total++; if (run <= 8) small++; run = 0; }
  }
  assert.ok(total > 60, `the sky should be busy; found ${total} islands over 8km`);
  assert.ok(small / total > 0.2, `only ${(small / total * 100).toFixed(0)}% are stepping stones`);
});

// "Vary in height going up super high" — while staying hoppable, which is the tension the
// two-part altitude field exists to resolve.
test("the archipelago climbs high AND stays jumpable", () => {
  const tops = []; let cur = null;
  for (let x = 1800; x < 9800; x++) {
    const f = featuresAt(x, 0, heightAt(x, 0));
    if (f?.iHi !== undefined) { cur = Math.max(cur ?? 0, f.iHi); }
    else if (cur !== null) { tops.push(cur); cur = null; }
  }
  const lo = Math.min(...tops), hi = Math.max(...tops);
  assert.ok(hi - lo > 15, `the sky is flat: altitudes only spanned ${(hi - lo).toFixed(0)} blocks`);
  assert.ok(hi > 60, `nothing goes high; the tallest island top was ${hi.toFixed(0)}`);

  const gaps = [];
  for (let i = 1; i < tops.length; i++) gaps.push(Math.abs(tops[i] - tops[i - 1]));
  const reach = gaps.filter((g) => g <= 2.5).length / gaps.length;
  assert.ok(reach > 0.6, `only ${(reach * 100).toFixed(0)}% of hops are within a double jump`);
});
