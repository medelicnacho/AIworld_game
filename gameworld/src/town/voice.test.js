// Tripwires for the mouth-scrubber. The bug this pins: gemma, prompted for a murmur,
// sometimes returns literal humming ("Mmm, hmm, mmmm") or stage directions, and Piper
// phonemizes them into audible porridge. Nothing unspeakable may reach the synth.

import { test } from "node:test";
import assert from "node:assert/strict";
import { cleanLine } from "./voice.js";

test("a plain line passes through untouched", () => {
  assert.equal(cleanLine("The broth wants salt again."), "The broth wants salt again.");
});

test("literal humming dies before it reaches the synth", () => {
  assert.equal(cleanLine("Mmm, hmm, mmmm."), null);
  assert.equal(cleanLine("mbmmmbnmnbmsbasbmm"), null);
});

test("stage directions and theatrics are stripped, the words survive", () => {
  assert.equal(cleanLine("*sighs* The winter took the roads."), "The winter took the roads.");
  assert.equal(cleanLine("(hums softly) Cold wind off the ridge tonight."),
    "Cold wind off the ridge tonight.");
});

test("a leading hum is dropped without losing the sentence", () => {
  assert.equal(cleanLine("Hmmm, the soup wants salt again."), "the soup wants salt again.");
});

test("smart quotes and emoji go; a mostly-broken line goes entirely", () => {
  assert.equal(cleanLine("“Quiet days are borrowed days.”"), "Quiet days are borrowed days.");
  assert.equal(cleanLine("🔥🔥 grr brr zzz 🔥"), null);
});

test("too short after scrubbing means silence, not a two-word bark", () => {
  assert.equal(cleanLine("Mmm. Salt."), null);
});

test("mood is read off the drift, and heard darkness genuinely darkens it", async () => {
  const { moodOf } = await import("./voice.js");
  assert.equal(moodOf(["the war took the cold dead winter"]), "bleak");
  assert.equal(moodOf(["the fire fed the soup and the salt held"]), "bright");
  assert.equal(moodOf(["the rings go on past counting"]), "steady");
  // Mixed talk leans where its words lean — mood is arithmetic over the subconscious,
  // not a dial anyone sets.
  assert.equal(moodOf(["the fire held", "the winter took the roads", "cold wind bites"]),
    "uneasy");
});
