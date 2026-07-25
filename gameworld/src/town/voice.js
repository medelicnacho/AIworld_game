// The town's voice (VOICE.md V1) — the first thing in this world that speaks.
//
// One villager at a time, in the STARTER TOWN only, on a long cooldown, murmuring a
// half-formed Markov fragment through Piper via the bridge. Every constraint here is
// VOICE.md's silence budget made code:
//
//   D1/D2  only inside the neutral spawn town — never mobs, never combat, never a rival's
//          walls. The audio channel out there belongs to the telegraphs.
//   D3     no LLM anywhere in this loop. bridge.speak() is text -> Piper -> WAV, and the
//          half-formed drift IS the product; a murmur that parsed cleanly would be worse.
//   D5     one voice in flight, ever, and a cooldown measured in tens of seconds. A town
//          that murmurs once a minute reads as alive; one that chatters reads as a lobby.
//   D7     the voice model is passed EXPLICITLY on every call — the bridge's server-side
//          default is lessac, which is Santāna's, and she has not arrived yet.
//   D8     fails soft at every layer, exactly like the bridge itself: lab down, synth slow,
//          decode failed — the town simply stays quiet, and quiet is the baseline anyway.
//
// The murmur is an enhancement, never a dependency.

import { VOICE } from "../config.js";
import { player } from "../state.js";
import { sanctuaryOf } from "../world/sanctuary.js";
import { mulberry32 } from "../rng.js";
import { Drift } from "./drift.js";
import { deeds } from "../world/events.js";

// The starter town's shared vocabulary — what its people have on their minds. REWRITTEN
// for the order-2 chain (VOICE.md rung 2): every phrase is one clean clause, and the
// phrases deliberately SHARE BIGRAMS ("the walls", "out past", "the deep", "this year")
// so that when the chain crosses between thoughts it crosses at a joint that still parses
// — "the rain is back out past the fallows" is a splice, but it is a GRAMMATICAL splice.
// Junction words carry the wandering; clause shape carries the coherence. V3 replaces
// much of this with memories the player caused; the shape is already the lab's, so that
// upgrade is data, not code.
// THE WORLD, in one breath — the context every speaker stands in. The starter town is
// neutral ground, so its people are not partisans; the war is the weather they live under,
// which is exactly how neutral civilians talk about one.
//
// "The rings" must be GLOSSED, not just named: handed the bare phrase, the model decided
// they were spinning objects, and — because heard lines feed the drift — the whole town
// spent an afternoon philosophising about the turning of the rings. A made-up term in a
// prompt is a vacuum the model will fill with the nearest cliché; define it once and the
// talk snaps to geography: distances, roads, who holds what.
export const WORLD = "You live in a small neutral town in a war-torn land. The wild country "
  + "beyond the walls stretches out in ever-harsher bands people call the rings — the "
  + "further out the ring, the deadlier it gets — and three clans, Ash, Iron, and Vale, "
  + "have torn it apart fighting each other for it: burned camps, closed roads, fields "
  + "gone back to the wild. Your town is neutral ground, the last safe walls for anyone "
  + "from any side, and everything the war breaks eventually limps through your gate. ";

// WHAT A TOWN IN A WAR-TORN LAND TALKS ABOUT. Left to itself the corpus collapsed into
// ABSTRACT doom — rot and hungry rings, a village waiting to die — because the mood loop
// amplifies whatever the talk already is and nothing was feeding it particulars. The fix
// is not cheerfulness, it is SPECIFICITY: a war-torn land is full of concrete things —
// the wounded, the refugees, the roads you can no longer take, whose camp burned. One
// topic is rolled per soliloquy as a nudge ("if it comes naturally..."), which keeps the
// talk orbiting the war's damage without scripting a word of it — and concrete subjects
// carry their own variety of feeling, which is what breaks the doom spiral.
const TOPICS = [
  "who limped through the gate today, and whose colours they wore",
  "refugees from a village the war reached",
  "the caravan that never arrived",
  "a camp burned two rings out — Ash, Iron, or Vale, nobody agrees whose",
  "which roads are closed to fighting this season",
  "the wounded the herbalist has been tending",
  "young folk leaving to take a clan's coin, and the ones who came back",
  "what farms out in the rings looked like before the war",
  "prices, now the war has swallowed the good land",
  "which clan is winning this season, as far as anyone can tell",
  "the wanderer who drinks here between fights",
  "how quiet the far roads have gone",
];

const SEEDS = [
  "ash riders were seen past the ridge",
  "iron holds the west roads this season",
  "vale runners move quick through the fallows",
  "three banners, and none of them ours",
  "an iron caravan paid in coin and bad news",
  "more refugees at the gate this morning",
  "the fields out past the fallows are burned black",
  "the west road is closed to fighting again",
  "clan folk in the square, watching each other",
  "the herbalist ran out of clean linen yesterday",
  "the rain is back on the walls",
  "the roads are worse this year",
  "the deep keeps what it takes",
  "the gate held all through the winter",
  "the winter took the roads out west",
  "the smith works late these nights",
  "the soup wants salt again",
  "the war is out past the fallows",
  "the wanderer paid in strange coin",
  "the ground shook again out west",
  "the rings go on past counting",
  "quiet days are borrowed days",
  "cold wind coming down off the ridge",
  "another season and still no word",
  "they came back short two this time",
  "the far towns fly their own colours",
  "keep the fire fed and the door shut",
  "nothing grows where the ash fell",
  "old walls, and older ground under them",
];

// THE CASTING (VOICE.md V2, §3). Voice is cast per ROLE, not per individual — a herbalist
// should sound like a herbalist in every town you ever enter, the same lesson the trade
// colours already teach by sight. Distinctness among the keepers comes from model × pace:
// four models and a per-villager pace jitter make a town of individuals from four files.
// lessac appears nowhere in this table and never will (D7 — it is Santāna's).
const CAST = {
  herbalist: { model: "en_GB-cori-medium.onnx", pace: 1.05 },   // warm — the one who mends you
  smith: { model: "en_GB-northern_english_male-medium.onnx", pace: 1.1 },  // bleak, gruff
  adept: { model: "en_GB-alan-medium.onnx", pace: 1.18 },       // slow; knows more than it says
};
// What each trade DOES, said outright — a 1b model handed only a job title will happily
// have the smith out gathering herbs. One clause of identity keeps hands on the right work.
export const TRADE = {
  Herbalist: "you tend herbs and mend the hurt",
  Smith: "you work iron at the forge",
  Adept: "you deal in spells and strange goods",
  Keeper: "you keep the town — gates, gardens, errands",
};

const KEEPER_MODELS = [
  "en_US-amy-medium.onnx",
  "en_US-joe-medium.onnx",
  "en_US-kristin-medium.onnx",
  "en_US-ryan-medium.onnx",
];

/**
 * The identity hash. Everything a villager IS — name, voice, pace, chat memory — hangs
 * off uid, the permanent index populate() dealt them. It HASHED THE WALK ANGLE once,
 * believing it fixed; strollers update it every frame, so a villager's name changed as
 * she walked ("Nell" at one bench, "Sage" at the next — the same woman), and her memory
 * of you was keyed to moments of her stroll. One body, one number, forever.
 */
const identOf = (v) => Math.imul((v.uid ?? 0) + 1, 2654435761) >>> 0;

/** A villager's voice, stable for as long as the villager exists. */
export function voiceOf(v) {
  const cast = CAST[v.role.key];
  if (cast) return cast;
  const h = identOf(v);
  return {
    model: KEEPER_MODELS[h % KEEPER_MODELS.length],
    // WIDENED from 0.94..1.18: with four models and a narrow band, two keepers on the same
    // model still blurred into one person. 0.86..1.30 spans "brisk" to "unhurried" — wide
    // enough that pace alone separates same-model neighbours, short of caricature.
    pace: 0.86 + ((h >>> 3) % 45) * 0.01,                       // 0.86..1.30
  };
}

// MOOD, read off the subconscious. Nobody sets a villager's mood — it is scored from the
// words the drift has been churning lately, and the drift includes what has been SAID in
// town (heard lines join its sources). So a run of grim talk genuinely darkens the next
// speaker's register, and a warm exchange lifts it: mood is downstream of conversation,
// which is the only place it could come from and still be called emergent.
// Extended with the war-torn vocabulary (2026-07-25): the world rewrite put burned camps,
// refugees and the wounded into the talk, and a lexicon that couldn't see those words was
// scoring a war-torn conversation as neutral — mood half-blind to what was being said.
const DARK = new Set(["cold", "war", "worse", "short", "ash", "fell", "shook", "took",
  "strange", "borrowed", "bad", "gone", "dead", "winter", "bites", "hard", "nothing",
  "burned", "burnt", "wounded", "refugees", "limped", "blood", "bleeding", "rot",
  "grim", "broken", "lost", "death", "storm", "grey", "empty", "closed"]);
const WARM = new Set(["fire", "fed", "soup", "salt", "held", "home", "warm", "good",
  "easy", "clear", "spring", "gold", "bloom", "mend", "mended", "safe", "shelter",
  "calm", "bread"]);

/** One word the prompt can carry: what the recent drift feels like. Exported for tests. */
export function moodOf(fragments) {
  let score = 0, n = 0;
  for (const f of fragments) {
    for (const w of f.toLowerCase().split(/\s+/)) {
      if (DARK.has(w)) { score -= 1; n += 1; }
      else if (WARM.has(w)) { score += 1; n += 1; }
    }
  }
  const m = n ? score / n : 0;
  return m <= -0.5 ? "bleak" : m < 0 ? "uneasy" : m > 0.5 ? "bright" : m > 0 ? "warm" : "steady";
}

// A mood is an INSTRUCTION, not a label. Handed the bare word "bleak", the model reached
// for poetry — "consumed by endless, brutal strife" — but tired people don't orate, they
// say "west road's closed again." Each mood ships with its register, and bleak's is the
// one that matters: TERSE, tired, pessimistic. Doom is right for a war-torn land; ornate
// doom is a narrator, and nobody in this town is a narrator.
export const MOOD_STYLE = {
  bleak: "Bleak means terse, tired, and pessimistic — short flat words, no poetry.",
  uneasy: "Uneasy means watchful and clipped.",
  steady: "Steady means plain and matter-of-fact.",
  warm: "Warm means dry, quiet good humour.",
  bright: "Bright means quick and light on your feet.",
};

/**
 * Is a reply just the previous line wearing a different hat? A small model, handed a
 * quoted line and asked to answer it, loves to paraphrase it back — which reads as two
 * people repeating each other, the opposite of a conversation. Measured as word overlap
 * against the SHORTER line; above the bar, the reply is discarded and the villager holds
 * their tongue. Silence reads as someone who had nothing to add — which is true.
 * Exported for tests.
 */
export function tooSimilar(a, b) {
  const setOf = (t) => new Set(t.toLowerCase().split(/\s+/)
    .map((w) => w.replace(/[^a-z]/g, "")).filter((w) => w.length > 2));
  const A = setOf(a), B = setOf(b);
  if (!A.size || !B.size) return false;
  let shared = 0;
  for (const w of A) if (B.has(w)) shared++;
  return shared / Math.min(A.size, B.size) > 0.6;
}

/**
 * Scrub a model line before it reaches a MOUTH. gemma, asked for a murmur, sometimes
 * delivers one literally — "Mmm, hmm, mmmm" — or emits stage directions ("*sighs*",
 * "(hums softly)"), smart quotes, emoji. Piper dutifully phonemizes all of it into
 * porridge ("mbmmmbnmn..."). So: strip the theatrics, drop any word that could not be
 * spoken (no vowel, consonant mashes, letter-stutters), and if what remains is not a
 * mostly-intact short sentence, return null — the villager stays quiet, which is always
 * better than gargling. Exported for its tests.
 */
// THE REGISTER TRIPWIRE — the lab's GENERIC_ASSISTANT detector (services/drift.py),
// ported as a gate. The failure it caught live, ambient, in play: "The arrival of
// refugees simply exacerbates existing resource constraints" — a townsperson possessed
// by a policy memo. One of these words is human; two in one short line is the assistant
// voice surfacing, and the line dies. This is the one register this project must never
// drift into, and now the mouth itself refuses it.
const ASSISTANT_WORDS = new Set(["certainly", "however", "additionally", "furthermore",
  "overall", "ultimately", "assist", "assistance", "provide", "ensure", "explore",
  "delve", "insights", "perspective", "highlights", "options", "recommend", "solution",
  "solutions", "moreover", "significant", "individuals", "resources", "constraints",
  "exacerbates", "impacts", "numerous", "various", "regarding", "facilitate",
  "utilize", "prioritize", "implement"]);

export function cleanLine(raw, minWords = 3) {
  if (!raw) return null;
  const t = raw
    .replace(/[’‘]/g, "'")               // curly apostrophes become straight ones FIRST —
                                         // stripping them as quotes turned "don't" into
                                         // "don", and the wreckage was SPOKEN ("this war
                                         // won end tonight"). A contraction is a word.
    .replace(/\*[^*]*\*/g, " ")          // *sighs*
    .replace(/\([^)]*\)/g, " ")          // (hums softly)
    .replace(/["“”`]/g, " ")
    .replace(/(^|[^a-zA-Z])'/g, "$1 ")   // apostrophes that AREN'T inside a word are
    .replace(/'(?![a-zA-Z])/g, " ")      // quote marks; the ones in "don't" stay put
    .replace(/[^\x20-\x7E]/g, " ")       // emoji, smart punctuation, anything non-ASCII
    .replace(/\s+/g, " ")
    .trim();
  const words = t.split(" ").filter(Boolean);
  const speakable = words.filter((w) => {
    const core = w.replace(/[^a-zA-Z]/g, "");
    if (!core) return false;
    if (!/[aeiouy]/i.test(core)) return false;                   // "mbmmm": no vowel
    if (/[bcdfghjklmnpqrstvwxz]{5,}/i.test(core)) return false;  // consonant mash
    if (/(.)\1\1/i.test(core)) return false;                     // mmm / hmmm / ummm
    return true;
  });
  // minWords is the REGISTER floor, and it depends on who is listening. An ambient murmur
  // under three words is noise (the default). But in DIALOGUE, "Mara." is a complete
  // answer from a terse townsperson — the chat passes 1, and asking a villager her name
  // stops reading as her glitching into silence.
  if (speakable.length < minWords || speakable.length < words.length * 0.7) return null;
  let assistant = 0;
  for (const w of speakable) {
    if (ASSISTANT_WORDS.has(w.toLowerCase().replace(/[^a-z]/g, ""))) assistant++;
  }
  if (assistant >= 2) return null;    // the register this project must never drift into
  return speakable.join(" ");
}

// NAMES. Villagers had only trades, so "what's your name" made the model invent one — a
// different one per asking, when it wasn't answering so short the scrubber ate it. Hashed
// off uid like the voice, so a body keeps ONE name for as long as it exists — ask twice,
// or tomorrow, and meet the same woman.
const NAMES = [
  "Mara", "Edda", "Bram", "Cole", "Tess", "Hale", "June", "Petra",
  "Otto", "Finn", "Sage", "Rook", "Ivy", "Dora", "Gil", "Hetty",
  "Jonas", "Kell", "Lena", "Moss", "Nell", "Orin", "Rue", "Silas",
];

/** A villager's given name, stable for as long as the villager exists. A different
 *  multiplier than the voice hash, so name and voice deal independently. */
export function nameOf(v) {
  return NAMES[(Math.imul((v.uid ?? 0) + 1, 40503) >>> 0) % NAMES.length];
}

export class TownVoice {
  /**
   * @param bridge    net/bridge.js — used only for speak(); state checked, never assumed
   * @param villagers town/villagers.js — the bodies who can be heard
   * @param sfx       audio/sfx.js — positional playback through the game's one mixer
   * @param onLine    (speakerName, text, durationSec) => void — the subtitle hook (D9)
   */
  constructor(bridge, villagers, sfx, onLine) {
    this.bridge = bridge;
    this.villagers = villagers;
    this.sfx = sfx;
    this.onLine = onLine;
    this.rng = mulberry32(0xB01CE);
    this.drift = new Drift(mulberry32(0xD41F7));
    this.drift.learn(SEEDS.map((text) => ({ text, weight: 1 })));
    this.cooldown = VOICE.firstDelay;
    this.busy = false;
    // THE CONVERSATION. The last settled line hangs in the air for a while; the next
    // settled speaker replies to it instead of soliloquising — villagers chatting across
    // the square. Capped at a few turns so the town talks, but never becomes a podcast.
    this.lastLine = null;      // { name, text, t, turns }
    // HEARING WRITES MEMORY — the lab's one loop, closed. Every settled line is pushed
    // into the town's drift sources at above-seed weight, so what was SAID aloud starts
    // surfacing, warped, in later murmurs. Speech feeding the subconscious feeding speech.
    this.heard = [];
    // LORE — what the town has DECIDED to remember. Written only by sleep (consolidate):
    // each night digests the day's heard talk into one line of standing memory. Unlike
    // heard[], lore does not decay on absence — it is the town's long-term self, capped
    // and slow, the first game-side echo of the lab's consolidation machinery.
    this.lore = [];
    // THE NEWS. This reader's place in the deed feed, and the freshest deed to arrive —
    // held for a couple of speaking slots so the first murmurs after you walk in are
    // ABOUT what you did out there, not about the weather.
    this.newsCursor = 0;
    this.news = null;
    this.newsSlots = 0;
  }

  /** Deeds become town knowledge the moment you arrive — news travels WITH the traveller.
   *  Each lands in heard[] at its own weight (a boss outranks gossip), and the freshest
   *  becomes the standing topic for the next couple of murmurs. */
  catchUpOnNews() {
    const { events, cursor } = deeds.since(this.newsCursor);
    if (!events.length) return;
    this.newsCursor = cursor;
    // A traveller brings HEADLINES, not a ledger — and a headline is the BIGGEST story,
    // not the latest. Taking the last three by recency once dropped two boss kills and a
    // faction oath in favour of the skirmish that happened after them. Top three by
    // weight, retold in the order they happened.
    const headlines = [...events].sort((a, b) => b.weight - a.weight).slice(0, 3)
      .sort((a, b) => a.id - b.id);
    for (const e of headlines) {
      this.heard.push({ text: e.text, weight: e.weight });
      console.info(`[voice] the town hears news: "${e.text}"`);
    }
    if (this.heard.length > VOICE.heardMax) {
      this.heard.splice(0, this.heard.length - VOICE.heardMax);
    }
    this.learnAll();
    this.news = headlines[headlines.length - 1].text;
    this.newsSlots = 2;
  }

  /** The drift's full diet, in one place: the town's standing seeds, its slow lore, and
   *  the day's talk. Three callers used to build this by hand; they disagreed eventually. */
  learnAll() {
    this.drift.learn(SEEDS.map((t) => ({ text: t, weight: 1 }))
      .concat(this.lore)
      .concat(this.heard));
  }

  /** Something was SAID in this town — by a villager, or by YOU (the chat feeds through
   *  here too: player input is just another utterance, the lab's founding rule). It joins
   *  the drift sources at above-seed weight, FIFO-capped so old talk fades. */
  hear(text) {
    this.heard.push({ text, weight: VOICE.heardWeight });
    if (this.heard.length > VOICE.heardMax) this.heard.shift();
    this.learnAll();
  }

  /** The town's mood right now, read off the recent drift — for anyone else (the chat)
   *  building a prompt about one of its people. */
  currentMood() {
    return moodOf(this.drift.current(5));
  }

  /**
   * SLEEP DIGESTS THE DAY (the lab's consolidation, first game-side echo). Called from the
   * dark of the sleep fade: the day's heard talk is compressed into ONE line of standing
   * lore — with the model when it's up ("how will the town remember this day"), or
   * mechanically without it (the loudest thing said becomes lore verbatim). Either way
   * heard[] is cleared: yesterday's echoes become a preoccupation, not a recording. The
   * fade gives the model a few free seconds; past the deadline, the mechanical memory
   * wins and the town wakes on time.
   */
  async consolidate(bridge) {
    if (!this.heard.length) return null;
    const material = [...this.heard].sort((a, b) => b.weight - a.weight);
    let lore = null;
    if (bridge?.state === "online" && bridge.info?.llm) {
      try {
        const texts = material.slice(0, 8).map((h) => `"${h.text}"`).join(", ");
        const res = await Promise.race([
          bridge.line(
            `Overnight, a small neutral town in a war-torn land digests the day's talk: `
            + `${texts}. Write ONE short line — how the town will remember this day. `
            + `Plain frontier speech, no greetings, no names of who said what.`,
            { words: 12, voice: "en_US-kristin-medium.onnx" }),
          new Promise((r) => setTimeout(() => r(null), 9000)),
        ]);
        lore = res?.text ? cleanLine(res.text) : null;
      } catch { /* the mechanical memory below */ }
    }
    if (!lore) lore = material[0].text;
    this.lore.push({ text: lore, weight: 1.2 });
    if (this.lore.length > 10) this.lore.shift();
    this.heard = [];
    this.news = null;
    this.newsSlots = 0;
    this.learnAll();
    console.info(`[voice] the town sleeps on it — new lore: "${lore}"`);
    return lore;
  }

  /** What the town remembers hearing, as plain data — for the save (VOICE.md C2). */
  dump() {
    return {
      heard: this.heard.map((h) => ({ ...h })),
      lore: this.lore.map((l) => ({ ...l })),
    };
  }

  /**
   * Put remembered talk back — DECAYED by how long you were away. "Remembers you,
   * fallibly" is the whole promise: what was said yesterday returns faded, and what was
   * said last week is simply gone. Weight rots per hour away; entries that rot below a
   * floor never come back. No decay while you PLAY — the FIFO cap handles forgetting
   * in-session, and double-charging would empty the town's head by suppertime.
   */
  restore(data, hoursAway = 0) {
    if (!data?.heard?.length) return;
    const rot = Math.pow(0.92, Math.max(0, hoursAway));
    this.heard = data.heard
      .map((h) => ({ text: String(h.text || ""), weight: (h.weight || 1) * rot }))
      .filter((h) => h.text && h.weight >= 0.5)
      .slice(-VOICE.heardMax);
    this.lore = (data.lore || []).filter((l) => l && l.text).slice(-10);
    this.learnAll();
    if (this.heard.length) {
      console.info(`[voice] the town remembers ${this.heard.length} things it heard`
        + `${hoursAway > 1 ? ` (faded by ${Math.round(hoursAway)}h away)` : ""}`);
    }
  }

  update(dt) {
    if (this.lastLine && (this.lastLine.t -= dt) <= 0) this.lastLine = null;
    if (this.busy || !VOICE.enabled) return;
    const s = sanctuaryOf(player.x, player.z, 0);
    // V1's venue: the one neutral, non-city town — where you wake, where speech should be
    // learned. Leaving resets toward the settle-in delay so re-entry doesn't fire instantly.
    if (!s || !s.neutral || s.city) {
      this.cooldown = Math.max(this.cooldown, VOICE.firstDelay);
      return;
    }
    // News lands whether or not the model is up — memory is model-free; only mouths need it.
    this.catchUpOnNews();
    // THE DRIFT WENT BACK UNDERGROUND (decided in play, 2026-07-25). Voicing raw Markov
    // was tried and it sounded like what it is; the lab's original shape won: everything
    // AUDIBLE is deliberate LLM speech, and the chain is purely subconscious — it feeds
    // the prompt (drifting thoughts), it sets the MOOD, and nobody ever hears it raw.
    // Which also means: no model, no voices. The town without ollama is simply quiet.
    if (this.bridge.state !== "online" || !this.bridge.info?.llm) return;
    this.cooldown -= dt;
    if (this.cooldown > 0) return;

    const v = this.pickSpeaker(s);
    if (!v) { this.cooldown = 4; return; }          // nobody close enough — retry soon

    this.drift.step();                              // churn the subconscious; spoken by no one
    if (this.newsSlots > 0) this.newsSlots--;       // fresh news headlines a couple of slots
    this.busy = true;
    this.sayLine(v).finally(() => {
      this.busy = false;
      this.cooldown = VOICE.cooldown + this.rng() * VOICE.jitter;
    });
  }

  /** The nearest villager of THIS town close enough to be heard clearly. Quartermasters
   *  are excluded: they are the faction characters, and their voices are cast in V2.
   *  Mid-conversation, the LAST speaker is passed over when anyone else is in range — a
   *  reply in the same voice is a monologue wearing two hats. */
  pickSpeaker(s) {
    let best = null, bd = VOICE.range, other = null, od = VOICE.range;
    for (const v of this.villagers.list) {
      if (v.s !== s || v.role.faction) continue;
      const d = Math.hypot(v.x - player.x, v.z - player.z);
      if (d < bd) { bd = d; best = v; }
      if (d < od && v.role.name !== this.lastLine?.name) { od = d; other = v; }
    }
    return (this.lastLine && other) ? other : best;
  }

  /** The settled line: drift fragments -> the model -> one clear sentence, spoken in the
   *  villager's own cast voice. Slow (seconds) by nature — the busy flag holds the town's
   *  one speaking slot for the duration, which is also why it can never stack. Uncached
   *  on purpose: a settled line should never come around twice. */
  async sayLine(v) {
    try {
      const { model, pace } = voiceOf(v);
      const frags = this.drift.current(3).map((f) => `"${f}"`).join(", ");
      // "Say", never "murmur" — ask a model to murmur and it will hand you "Mmm, hmm,
      // mmmm" to synthesize. The register comes from the framing; the WORDS must be words.
      //
      // A line still hanging in the air turns this slot into a REPLY: the last speaker's
      // words go in as what was just heard, and the soliloquy rules relax — you may
      // address them, you may ask something back. That is all a conversation is here:
      // the previous utterance made prompt. (The lab's whole thesis, one town wide.)
      const reply = this.lastLine && this.lastLine.turns < VOICE.convoMax
        && this.lastLine.name !== v.role.name ? this.lastLine : null;
      // The MOOD is read off the same drift the thoughts come from — one word, but it is
      // the word that turns the same prompt into a different person on a different day.
      const mood = moodOf(this.drift.current(5));
      const who = `You are the town ${v.role.name} — ${TRADE[v.role.name] || "you live and work here"}. `;
      const moodLine = `Your mood is ${mood}. ${MOOD_STYLE[mood] || ""} `;
      const prompt = reply
        ? WORLD + who + `The ${reply.name} works nearby and just said aloud: `
          + `"${reply.text}". ` + moodLine
          + `Answer with ONE short line of your own — agree, push back, add news, or turn `
          + `the subject, but NEVER repeat or rephrase their words. Plain frontier speech `
          + `in real words only, chatting while you both work. Avoid stock filler like `
          + `"I reckon". No humming or sound effects, no stage directions.`
        : WORLD + who + `You are talking quietly to yourself while you work. `
          + moodLine + `Your drifting thoughts just now: ${frags}. `
          + `If it comes naturally, let your line touch on `
          + `${this.newsSlots > 0 && this.news
            ? `the news everyone has heard: ${this.news}`
            : TOPICS[(this.rng() * TOPICS.length) | 0]}. `
          + `Say ONE short line to yourself — plain frontier speech in real words only. `
          + `Avoid stock filler like "I reckon". No greetings, no questions, no humming `
          + `or sound effects, no stage directions, never address anyone.`;
      const res = await this.bridge.line(prompt, {
        words: VOICE.lineWords, voice: model, lengthScale: pace,
      });
      if (!res?.text) return;
      // THE TRANSCRIPT. Every line the model produces is logged — spoken OR rejected,
      // with which guard killed it and why — because a voice layer can only be tuned
      // against what it actually says, and subtitles evaporate in seconds. One line per
      // utterance, greppable on "[voice]", same rule as the raid breadcrumbs.
      //
      // The line was already synthesized server-side from the RAW text — so if scrubbing
      // changed anything, that audio contains the porridge and is discarded; the clean
      // text goes back through /speak for a fresh mouth. Unscathed lines keep their WAV.
      const clean = cleanLine(res.text);
      if (!clean) {                              // unusable — quiet beats gargling
        console.info(`[voice] ✂ scrubbed to silence — ${v.role.name} tried: "${res.text}"`);
        return;
      }
      // A reply that parrots the line it answers is discarded whole. This is the hard
      // guard behind the prompt's "never repeat" — small models agree to that and then
      // paraphrase anyway, and a paraphrase spoken aloud reads as a broken record.
      if (reply && tooSimilar(reply.text, clean)) {
        console.info(`[voice] ✂ parrot — ${v.role.name} answered "${reply.text}" with "${clean}"`);
        return;
      }
      console.info(`[voice] ${v.role.name} (${mood}${reply ? ` ← ${reply.name}` : ""}): "${clean}"`
        + `${clean !== res.text.trim() ? `   [scrubbed from: "${res.text.trim()}"]` : ""}`);
      // Re-synthesize ONLY when scrubbing changed what would be SAID — letters, not
      // typography. Comparing raw strings re-synthesized ~70% of lines over a curly
      // apostrophe Piper never even pronounces differently.
      const gist = (t) => t.toLowerCase().replace(/[^a-z]+/g, " ").trim();
      let wav = res.audio;
      if (gist(clean) !== gist(res.text)) {
        wav = await this.bridge.speak(clean, model, pace);
      }
      if (!wav) return;
      const dur = await this.sfx.playClip(wav, v.x, v.z, VOICE.volume);
      if (!dur) return;
      this.onLine?.(v.role.name, clean, dur, true);
      // The line now hangs in the air for the next speaker to answer...
      this.lastLine = {
        name: v.role.name, text: clean, t: VOICE.convoWindow,
        turns: (reply ? reply.turns : 0) + 1,
      };
      // ...and HEARING WRITES MEMORY: spoken words join the drift sources at above-seed
      // weight, capped FIFO so old talk fades. From here on, murmurs can echo — warped,
      // half-remembered — what somebody actually said. The loop the lab exists to prove.
      this.hear(clean);
    } catch {
      // Same rule as the murmur: the model is an enhancement, never a dependency.
    }
  }
}
