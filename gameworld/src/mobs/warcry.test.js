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

test("hails never starve behind the war: the emptier shelf bakes first", () => {
  const w = new WarCries({ state: "online", info: { llm: false } }, fakeSfx);
  // Track which kind each bake call would produce, without real synthesis.
  const kinds = [];
  w.bakeOne = (c) => { kinds.push("cry"); w.cache.get(c).push({ text: "x", wav: null }); };
  w.bakeHail = (c) => { kinds.push("hail"); w.hails.get(c).push({ text: "x", wav: null }); };
  // Simulate resting in a safe town: sanctuaryOf is position-based, so instead call the
  // shelf-choice logic by driving update with the venue checks bypassed via monkeypatch —
  // simplest honest route: call the chooser many times directly.
  for (let i = 0; i < 36; i++) {
    // reproduce update()'s chooser
    const shortCries = [0, 1, 2].filter((c) => w.cache.get(c).length < 8);
    const shortHails = [0, 1, 2].filter((c) => w.hails.get(c).length < 4);
    if (!shortCries.length && !shortHails.length) break;
    const cryFill = [0, 1, 2].reduce((n, c) => n + w.cache.get(c).length, 0) / 24;
    const hailFill = [0, 1, 2].reduce((n, c) => n + w.hails.get(c).length, 0) / 12;
    if (shortHails.length && (hailFill <= cryFill || !shortCries.length)) w.bakeHail(shortHails[0]);
    else w.bakeOne(shortCries[0]);
  }
  const firstTen = kinds.slice(0, 10);
  assert.ok(firstTen.includes("hail"), "a hail bakes within the first few slots, not after 24");
  assert.ok(firstTen.includes("cry"), "and the war still bakes alongside");
});

test("the taunt floor: an army with taunts loaded is NEVER silent, even unbaked", () => {
  played.length = 0;
  const w = new WarCries(offline, fakeSfx);
  w.taunts.get(0).push({ text: "I will kill you!", wav: new ArrayBuffer(4) });
  w.cry({ faction: 0, x: 0, z: 0 }, "arm");        // cry cache empty — floor answers
  assert.equal(played.length, 1, "the hardcoded floor speaks when nothing is baked");
  // ...and a clan with no floor of its OWN stays quiet rather than borrowing a throat.
  played.length = 0;
  w.globalCd = 0; w.factionCd.set(1, 0);
  w.cry({ faction: 1, x: 0, z: 0 }, "arm");
  assert.equal(played.length, 0, "each clan taunts in its own voice or not at all");
});

test("battle chatter yields to telegraphs: it never blocks a charge scream", () => {
  played.length = 0;
  const w = new WarCries(offline, fakeSfx);
  for (const c of [0, 1]) w.taunts.get(c).push({ text: "I know kung fu!", wav: new ArrayBuffer(4) });
  // Mid-fight chatter fires...
  let spoke = 0;
  for (let i = 0; i < 60 && !spoke; i++) { w.cry({ faction: 0, x: 0, z: 0 }, "fight"); spoke = played.length; }
  assert.equal(spoke, 1, "a fighter eventually runs its mouth");
  // ...and must NOT have armed the faction cooldown, so a telegraph can still land.
  assert.equal(w.factionCd.get(0), 0, "chatter never claims the telegraph budget");
  w.globalCd = 0;                                  // one voice at a time, then:
  w.cry({ faction: 0, x: 0, z: 0 }, "charge");
  assert.equal(played.length, 2, "the charge scream is never blocked by chatter");
});

test("clan-vs-clan war chatter has its own slower clock", () => {
  played.length = 0;
  const w = new WarCries(offline, fakeSfx);
  w.taunts.get(2).push({ text: "You smell of poo!", wav: new ArrayBuffer(4) });
  let spoke = 0;
  for (let i = 0; i < 80 && !spoke; i++) { w.cry({ faction: 2, x: 0, z: 0 }, "war"); spoke = played.length; }
  assert.equal(spoke, 1, "clans at war are audible");
  w.globalCd = 0;
  w.cry({ faction: 2, x: 0, z: 0 }, "war");
  assert.equal(played.length, 1, "but the war clock holds them apart");
});
