// Tripwires for the Markov port (VOICE.md V1). The lab's thought.py has no tests of its
// own — the experiments are its harness — but the port rides in a game with a lint-enforced
// determinism rule, so the properties that rule buys must be pinned: same seed, same drift.

import { test } from "node:test";
import assert from "node:assert/strict";
import { Drift } from "./drift.js";
import { mulberry32 } from "../rng.js";

const SOURCES = [
  { text: "the rain finds the walls again", weight: 1 },
  { text: "the deep takes more than it gives", weight: 1 },
  { text: "quiet tonight, too quiet for the season", weight: 1 },
];

const fresh = (seed = 7) => {
  const d = new Drift(mulberry32(seed));
  d.learn(SOURCES);
  return d;
};

test("deterministic: same seed, same drift — replayable like everything else (D14)", () => {
  const a = fresh(), b = fresh();
  for (let i = 0; i < 50; i++) assert.equal(a.step(), b.step());
});

test("fragments are short, non-empty, and made ONLY of learned words", () => {
  const vocab = new Set(SOURCES.flatMap((s) => Drift.words(s.text).map((w) => w.toLowerCase())));
  const d = fresh(11);
  for (let i = 0; i < 200; i++) {
    const f = d.step();
    assert.ok(f && f.length, "a learned chain always produces something");
    const ws = f.split(" ");
    assert.ok(ws.length <= 7, `fragment must stay half-formed, got ${ws.length} words`);
    for (const w of ws) assert.ok(vocab.has(w.toLowerCase()), `unknown word "${w}" — the chain invented vocabulary`);
  }
});

test("the chain actually WANDERS between sources — juxtaposition is the product", () => {
  // Shared words ("the", "quiet") must let a fragment cross from one seed phrase into
  // another at least sometimes; a chain that only replays its inputs is a phrase list.
  const originals = new Set(SOURCES.map((s) => Drift.words(s.text).join(" ")));
  const d = fresh(13);
  let novel = 0;
  for (let i = 0; i < 300; i++) if (!originals.has(d.step())) novel++;
  assert.ok(novel > 30, `expected wandering, got ${novel}/300 novel fragments`);
});

test("the rolling buffer holds five and current() reads the tail", () => {
  const d = fresh(17);
  for (let i = 0; i < 20; i++) d.step();
  assert.equal(d.drift.length, 5, "buffer trims to BUFFER");
  assert.deepEqual(d.current(3), d.drift.slice(-3));
});

test("unlearned chain refuses politely", () => {
  const d = new Drift(mulberry32(1));
  assert.equal(d.step(), null);
});

test("order-2 coherence: most adjacent word pairs in a fragment are LEARNED bigrams", () => {
  // The upgrade's whole point, pinned: with pair-following at ~0.78 (1 - BACKOFF_CHANCE),
  // the bulk of every fragment must be locally grammatical — seams allowed, salad not.
  const bigrams = new Set();
  for (const s of SOURCES) {
    const ws = Drift.words(s.text).map((w) => w.toLowerCase());
    for (let i = 0; i < ws.length - 1; i++) bigrams.add(`${ws[i]} ${ws[i + 1]}`);
  }
  const d = fresh(23);
  let learned = 0, total = 0;
  for (let i = 0; i < 300; i++) {
    const ws = d.step().toLowerCase().split(" ");
    for (let j = 0; j < ws.length - 1; j++) {
      total++;
      if (bigrams.has(`${ws[j]} ${ws[j + 1]}`)) learned++;
    }
  }
  assert.ok(learned / total > 0.6,
    `expected mostly grammatical joints, got ${(learned / total * 100).toFixed(0)}%`);
});
