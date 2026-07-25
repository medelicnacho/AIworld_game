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

// The starter town's shared vocabulary — what its people have on their minds. REWRITTEN
// for the order-2 chain (VOICE.md rung 2): every phrase is one clean clause, and the
// phrases deliberately SHARE BIGRAMS ("the walls", "out past", "the deep", "this year")
// so that when the chain crosses between thoughts it crosses at a joint that still parses
// — "the rain is back out past the fallows" is a splice, but it is a GRAMMATICAL splice.
// Junction words carry the wandering; clause shape carries the coherence. V3 replaces
// much of this with memories the player caused; the shape is already the lab's, so that
// upgrade is data, not code.
const SEEDS = [
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
const KEEPER_MODELS = [
  "en_US-amy-medium.onnx",
  "en_US-joe-medium.onnx",
  "en_US-kristin-medium.onnx",
  "en_US-ryan-medium.onnx",
];

/** A villager's voice, stable for as long as the villager exists. Keepers hash their walk
 *  angle (fixed at populate time) into a model and a pace nudge, so the same body keeps
 *  the same voice for the whole session instead of re-rolling per murmur. */
function voiceOf(v) {
  const cast = CAST[v.role.key];
  if (cast) return cast;
  const h = Math.abs(Math.floor(v.ang * 10430.378)) >>> 0;      // angle bits as a hash
  return {
    model: KEEPER_MODELS[h % KEEPER_MODELS.length],
    // WIDENED from 0.94..1.18: with four models and a narrow band, two keepers on the same
    // model still blurred into one person. 0.86..1.30 spans "brisk" to "unhurried" — wide
    // enough that pace alone separates same-model neighbours, short of caricature.
    pace: 0.86 + ((h >>> 3) % 45) * 0.01,                       // 0.86..1.30
  };
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
export function cleanLine(raw) {
  if (!raw) return null;
  const t = raw
    .replace(/\*[^*]*\*/g, " ")          // *sighs*
    .replace(/\([^)]*\)/g, " ")          // (hums softly)
    .replace(/["“”‘’'`]/g, " ")
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
  if (speakable.length < 3 || speakable.length < words.length * 0.7) return null;
  return speakable.join(" ");
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
    // WAV bytes by fragment text. Piper is CPU-bound and serialized on the lab side, so a
    // fragment the chain wanders back to should never cost a second synthesis.
    this.cache = new Map();
    // THE CONVERSATION. The last settled line hangs in the air for a while; the next
    // settled speaker replies to it instead of soliloquising — villagers chatting across
    // the square. Capped at a few turns so the town talks, but never becomes a podcast.
    this.lastLine = null;      // { name, text, t, turns }
    // HEARING WRITES MEMORY — the lab's one loop, closed. Every settled line is pushed
    // into the town's drift sources at above-seed weight, so what was SAID aloud starts
    // surfacing, warped, in later murmurs. Speech feeding the subconscious feeding speech.
    this.heard = [];
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
    if (this.bridge.state !== "online") return;
    this.cooldown -= dt;
    if (this.cooldown > 0) return;

    const v = this.pickSpeaker(s);
    if (!v) { this.cooldown = 4; return; }          // nobody close enough — retry soon

    const text = this.drift.step();
    // A one-word fragment isn't a murmur, and an immediate repeat reads as a broken record.
    if (!text || text.indexOf(" ") < 0 || this.drift.current(3).slice(0, -1).includes(text)) {
      this.cooldown = 2;
      return;
    }

    // THE TWO-LAYER VOICE (the lab's architecture, arriving in the game). Mostly the drift
    // is muttered raw — that is the subconscious, and it stays Markov (D3). Occasionally,
    // when the lab has a model up, a villager SETTLES: the LLM is asked to say one line
    // grown from the recent drift, in its own plain voice. The contrast is the point —
    // the half-formed murmur is what makes the rare clear line feel like surfacing.
    // No model running -> lineChance is dead weight and every slot is a murmur (D8).
    //
    // A line hanging in the air raises the odds the next slot ANSWERS it — a conversation
    // has rhythm, and a reply that arrives a minute later is not a reply.
    const chance = this.lastLine ? VOICE.lineChanceReply : VOICE.lineChance;
    const settled = this.bridge.info?.llm && this.rng() < chance;
    this.busy = true;
    (settled ? this.sayLine(v) : this.say(v, text)).finally(() => {
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

  async say(v, text) {
    try {
      const { model, pace } = voiceOf(v);
      // The cache key carries the whole voice, not just the words — the same fragment in
      // the smith's mouth and a keeper's is two different sounds and must be two entries.
      const key = `${model}|${pace.toFixed(2)}|${text}`;
      let wav = this.cache.get(key);
      if (!wav) {
        wav = await this.bridge.speak(text, model, pace);
        if (!wav) return;
        if (this.cache.size >= VOICE.cacheMax) {
          this.cache.delete(this.cache.keys().next().value);   // oldest-in, first-out
        }
        this.cache.set(key, wav);
      }
      const dur = await this.sfx.playClip(wav, v.x, v.z, VOICE.volume);
      if (dur) this.onLine?.(v.role.name, text, dur, false);
    } catch {
      // The murmur is an enhancement, never a dependency (D8). Silence is the baseline.
    }
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
      const prompt = reply
        ? `You are the ${v.role.name} of a small frontier town, working near the `
          + `${reply.name}, who just said aloud: "${reply.text}". Your own drifting `
          + `thoughts: ${frags}. Answer them with ONE short line — plain frontier speech `
          + `in real words only, chatting while you both work. No humming or sound `
          + `effects, no stage directions.`
        : `You are the ${v.role.name} of a small frontier town, talking quietly `
          + `to yourself while you work. Your drifting thoughts just now: ${frags}. `
          + `Say ONE short line to yourself — plain frontier speech in real words only. `
          + `No greetings, no questions, no humming or sound effects, no stage directions, `
          + `never address anyone.`;
      const res = await this.bridge.line(prompt, {
        words: VOICE.lineWords, voice: model, lengthScale: pace,
      });
      if (!res?.text) return;
      // The line was already synthesized server-side from the RAW text — so if scrubbing
      // changed anything, that audio contains the porridge and is discarded; the clean
      // text goes back through /speak for a fresh mouth. Unscathed lines keep their WAV.
      const clean = cleanLine(res.text);
      if (!clean) return;                        // unusable — quiet beats gargling
      let wav = res.audio;
      if (clean !== res.text.trim()) {
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
      this.heard.push({ text: clean, weight: VOICE.heardWeight });
      if (this.heard.length > VOICE.heardMax) this.heard.shift();
      this.drift.learn(SEEDS.map((text) => ({ text, weight: 1 })).concat(this.heard));
    } catch {
      // Same rule as the murmur: the model is an enhancement, never a dependency.
    }
  }
}
