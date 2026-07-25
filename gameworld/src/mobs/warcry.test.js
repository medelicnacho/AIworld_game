// Tripwires for the war-cries — the budget and the bake gate, the parts that keep a
// battlefield from becoming a playground.

import { test } from "node:test";
import assert from "node:assert/strict";
import { WarCries } from "./warcry.js";
import { deeds } from "../world/events.js";

const played = [];
const fakeSfx = { playClip: (wav, x, z, vol, rate) => { played.push({ wav, rate }); return 1; } };
const offline = { state: "offline", info: null };

test("an unbaked army is a QUIET army — never a crash, never a live synth", () => {
  played.length = 0;
  const w = new WarCries(offline, fakeSfx);
  w.cry({ faction: 1, x: 0, z: 0 }, "charge");
  assert.equal(played.length, 0, "no cache, no cry");
});

test("the budget holds: one cry per battlefield, one per faction, on cooldowns", () => {
  played.length = 0;
  const w = new WarCries(offline, fakeSfx);
  w.cache.get(1).push({ text: "burn them down", wav: new ArrayBuffer(4) });
  w.cache.get(2).push({ text: "run them down", wav: new ArrayBuffer(4) });
  w.cry({ faction: 1, x: 0, z: 0 }, "arm");         // arm always cries
  assert.equal(played.length, 1);
  w.cry({ faction: 1, x: 0, z: 0 }, "arm");         // same faction, cooling down
  assert.equal(played.length, 1, "the faction cooldown holds");
  w.cry({ faction: 2, x: 0, z: 0 }, "arm");         // other faction, but global cd holds
  assert.equal(played.length, 1, "the battlefield cooldown holds");
  w.update(5);                                       // global cd (4s) expires; faction 2 clear
  w.cry({ faction: 2, x: 0, z: 0 }, "arm");
  assert.equal(played.length, 2, "another army may answer");
});

test("deeds reach every corpus — your legend joins their screaming", () => {
  const w = new WarCries(offline, fakeSfx);
  w.newsCursor = deeds.since(0).cursor;
  deeds.push("the wanderer sacked a vale camp out in the Reach", 2.0);
  w.catchUpOnDeeds();
  // The corpus must now be able to produce fragments containing deed vocabulary.
  const words = new Set();
  for (let i = 0; i < 400; i++) {
    for (const t of (w.corpora.get(0).step() || "").split(" ")) words.add(t.toLowerCase());
  }
  assert.ok(words.has("wanderer") || words.has("sacked"),
    "the deed's words entered the war vocabulary");
});

test("hails are their own channel: friendly cache, own budget, never the war's", () => {
  played.length = 0;
  const w = new WarCries(offline, fakeSfx);
  w.hails.get(2).push({ text: "Hail, soldier.", wav: new ArrayBuffer(4) });
  w.cache.get(2).push({ text: "run them down!", wav: new ArrayBuffer(4) });
  // Force the chance roll aside: hailChance gates are probabilistic, so drive till it lands.
  let greeted = 0;
  for (let i = 0; i < 50 && !greeted; i++) {
    w.cry({ faction: 2, x: 0, z: 0 }, "hail");
    greeted = played.length;
  }
  assert.equal(greeted, 1, "an ally eventually says hello");
  assert.equal(played[0].rate, 1, "a greeting is a voice, not a monster");
  w.cry({ faction: 2, x: 0, z: 0 }, "hail");
  assert.equal(played.length, 1, "the courtesy cooldown holds");
  w.cry({ faction: 2, x: 0, z: 0 }, "arm");
  assert.equal(played.length, 2, "and the war's budget is untouched by courtesy");
});
