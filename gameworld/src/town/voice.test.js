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

test("a paraphrase is not a reply — the parrot guard", async () => {
  const { tooSimilar } = await import("./voice.js");
  assert.equal(tooSimilar(
    "Cold wind bites, and the road ain't clear now.",
    "Aye, the cold wind bites and the road is not clear."), true);
  assert.equal(tooSimilar(
    "Cold wind bites, and the road ain't clear now.",
    "Iron holds the west roads, let them freeze on them."), false);
  assert.equal(tooSimilar(
    "The soup wants salt.",
    "The soup wants salt again, always salt."), true);
});

test("contractions SURVIVE the scrubber — a curly apostrophe is not a quote mark", async () => {
  const { cleanLine } = await import("./voice.js");
  // The bug this pins, transcribed from a live session: "don't" became "don" and the
  // wreckage was spoken aloud ("Spinning rings don fill bellies").
  assert.equal(cleanLine("Spinning rings don’t fill bellies, just hungry ghosts."),
    "Spinning rings don't fill bellies, just hungry ghosts.");
  assert.equal(cleanLine("this endless war won’t end tonight."),
    "this endless war won't end tonight.");
  // While straight quotes used AS quotes still go.
  assert.equal(cleanLine("'The gate holds', she said."), "The gate holds she said.");
});

test("C2: the town's memory survives a save round-trip, and time away FADES it", async () => {
  const { TownVoice } = await import("./voice.js");
  const mk = () => new TownVoice({ state: "offline", info: null }, { list: [] }, {}, null);
  const a = mk();
  a.hear("the wanderer burned a vale camp");
  a.hear("cake is for birthdays");
  const data = a.dump();

  // Back after a short break: both memories intact.
  const b = mk();
  b.restore(data, 0.5);
  assert.equal(b.heard.length, 2, "a short absence forgets nothing");

  // Back after a week: the town has honestly forgotten.
  const c = mk();
  c.restore(data, 24 * 7);
  assert.equal(c.heard.length, 0, "a week away rots remembered talk to nothing");

  // And a corrupt or absent memory never breaks the load.
  const d = mk();
  d.restore(null, 1);
  d.restore({ heard: [{ bad: true }] }, 1);
  assert.equal(d.heard.length, 0);
});

test("dialogue floor: 'Mara.' is an answer in chat, still noise as a murmur", async () => {
  const { cleanLine, nameOf } = await import("./voice.js");
  // The glitch this pins: asking a villager her name produced a short, correct reply the
  // 3-word ambient floor scrubbed to silence — she read as broken for answering properly.
  assert.equal(cleanLine("Mara.", 1), "Mara.");
  assert.equal(cleanLine("Mara.", 3), null);
  // And identity is STABLE ON uid, untouched by the stroll: the same body mid-walk keeps
  // its name and voice; a different body gets its own. (The bug this pins: identity once
  // hashed the walk angle, so a villager's name changed as she walked her circuit.)
  const { voiceOf } = await import("./voice.js");
  const v = { uid: 3, ang: 2.184, role: { key: "keeper", name: "Keeper" } };
  const walked = { ...v, ang: 4.9 };
  assert.equal(nameOf(v), nameOf(walked), "walking must never rename her");
  assert.deepEqual(voiceOf(v), voiceOf(walked), "nor change her voice");
  assert.notEqual(nameOf(v), nameOf({ ...v, uid: 4 }), "but two bodies are two people");
});

test("introductions become facts: nameIn hears a name and refuses a verb", async () => {
  const { nameIn } = await import("./chat.js");
  // The playtest lines that motivated this, verbatim:
  assert.equal(nameIn("hey my names dilhead jones whats your name"), "Dilhead Jones");
  assert.equal(nameIn("thanks for the help. my name is john snow by the way."), "John Snow");
  assert.equal(nameIn("im dilhead jones"), "Dilhead Jones");
  assert.equal(nameIn("call me Rook"), "Rook");
  // And the traps: mid-sentence "i'm X" is speech, not an introduction.
  assert.equal(nameIn("im going to go kill some noobs"), null);
  assert.equal(nameIn("i'm fine"), null);
  assert.equal(nameIn("hello there"), null);
});

test("C3 regard: rudeness costs, courtesy pays, one outburst is a mark not a verdict", async () => {
  const { regardShift, regardWord } = await import("./chat.js");
  // The playtest lines that demanded this, verbatim:
  assert.equal(regardShift("well screw you too"), -1);
  assert.equal(regardShift("your mom is lame"), -1);
  assert.equal(regardShift("thanks for the help. my name is john snow by the way."), 1);
  assert.equal(regardShift("hey whats up"), 0);
  // Clamped per message: a torrent of insults in one breath is still one step.
  assert.equal(regardShift("stupid dumb worthless idiot"), -1);
  // And the ladder reads right at both ends.
  assert.equal(regardWord(-4), "hostile");
  assert.equal(regardWord(-1), "sour");
  assert.equal(regardWord(0), "wary");
  assert.equal(regardWord(3), "friendly");
});
