// Pure-math tripwires for loot rolling. A drop must NEVER come out malformed — no undefined
// name, no zero armour, no stat on a piece its rarity shouldn't have. Distribution is checked
// over many seeded rolls so "gray is common, blue is rare" can't silently drift.

import { test } from "node:test";
import assert from "node:assert/strict";
import { rollGear, sellValue, vendorPiece, RARITY } from "./gear.js";
import { ARMOR, ARMOR_SLOT_ORDER } from "../config.js";
import { mulberry32 } from "../rng.js";

const RARITY_STATS = { common: 0, uncommon: 2, rare: 4 };

test("rollGear: every roll is well-formed", () => {
  const rng = mulberry32(12345);
  for (let i = 0; i < 5000; i++) {
    const ring = i % 12;
    const p = rollGear(ring, rng);
    assert.ok(p.uid, "has a uid");
    assert.ok(typeof p.name === "string" && !p.name.includes("undefined"), `clean name: ${p.name}`);
    assert.ok(ARMOR_SLOT_ORDER.includes(p.slot), `valid slot: ${p.slot}`);
    assert.ok(p.armor >= 1, `armour >= 1 (was ${p.armor})`);
    assert.equal(p.stats.armor, p.armor, "stats.armor mirrors armor");
    assert.ok(RARITY[p.rarity], `known rarity: ${p.rarity}`);
    // The non-armour stat count must match the rarity's budget exactly.
    const bonusStats = Object.keys(p.stats).filter((k) => k !== "armor").length;
    assert.equal(bonusStats, RARITY_STATS[p.rarity], `${p.rarity} carries the right # of stats`);
  }
});

test("rollGear: uids are unique across a run", () => {
  const rng = mulberry32(777);
  const seen = new Set();
  for (let i = 0; i < 2000; i++) {
    const { uid } = rollGear(i % 10, rng);
    assert.ok(!seen.has(uid), `duplicate uid ${uid}`);
    seen.add(uid);
  }
});

test("rollGear: gray common, blue rare — distribution holds", () => {
  const rng = mulberry32(0xC0FFEE);
  const count = { common: 0, uncommon: 0, rare: 0 };
  const N = 20000;
  for (let i = 0; i < N; i++) count[rollGear(0, rng).rarity]++;
  // Common dominates; rare is a small minority. Loose bounds so tuning can move without
  // breaking the test, tight enough to catch an accidental flip of the thresholds.
  assert.ok(count.common / N > 0.75, `common should be the bulk (was ${count.common / N})`);
  assert.ok(count.rare / N < 0.10, `rare should be scarce (was ${count.rare / N})`);
  assert.ok(count.common > count.uncommon && count.uncommon > count.rare, "gray > green > blue");
});

test("rollGear: deeper rings roll bigger armour on average", () => {
  const rng = mulberry32(42);
  const avg = (ring) => {
    let s = 0; const n = 3000;
    for (let i = 0; i < n; i++) s += rollGear(ring, rng).armor;
    return s / n;
  };
  assert.ok(avg(8) > avg(1), "ring 8 armour should out-average ring 1");
});

test("sellValue: always at least 1, and rarer sells for more", () => {
  const mk = (rarity, armor) => ({ rarity, armor });
  assert.ok(sellValue(mk("common", 0)) >= 1);
  assert.ok(sellValue(mk("rare", 100)) > sellValue(mk("uncommon", 100)));
  assert.ok(sellValue(mk("uncommon", 100)) > sellValue(mk("common", 100)));
});

test("vendorPiece: a config piece becomes a green owned instance intact", () => {
  const cfg = ARMOR[Object.keys(ARMOR)[0]];
  const p = vendorPiece(cfg);
  assert.equal(p.slot, cfg.slot);
  assert.equal(p.armor, cfg.armor);
  assert.equal(p.stats, cfg.stats);
  assert.equal(p.rarity, "uncommon");
  assert.ok(p.uid);
});
