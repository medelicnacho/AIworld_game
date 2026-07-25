// WAR-CRIES — the three armies find their voices.
//
// COHERENT AT BAKE, FREE AT PLAY: because cries are synthesized at rest and only replayed
// in combat, the model can WRITE them — a clan creed, the wanderer's latest deed, one
// brutal line — at zero combat cost. The Markov corpus (seeded with each identity, fed
// from the deed feed) remains the no-model fallback, so an army is never mute for lack
// of ollama. Either way: sack a camp, and the cries coming at you can be ABOUT the
// camp-burner. Your reputation, screamed back at you across a battlefield.
//
// AND IT IS A WARBAND, not a soloist: a lead cry gates on tight cooldowns, but nearby
// packmates ECHO it — staggered, overlapping, each throat pitched differently — so a
// noticed pack sounds like a group of warriors taking up a shout.
//
// The engineering rule that makes it shippable: NO SYNTHESIS IN COMBAT. Cries are baked
// in town — the quiet place, the natural pre-bake station — into a per-faction cache of
// WAVs, and the field only ever plays what is already baked. A faction whose cache is
// empty simply doesn't scream yet; silence is the baseline everywhere in this project.

import { WARCRY } from "../config.js";
import { player, nearby } from "../state.js";
import { sanctuaryOf } from "../world/sanctuary.js";
import { isHostileSanctuary } from "../prog/factions.js";
import { mulberry32 } from "../rng.js";
import { Drift } from "../town/drift.js";
import { cleanLine } from "../town/voice.js";
import { deeds } from "../world/events.js";

// Who is doing the screaming — each clan's creed, for the model that writes its cries.
const CRY_IDENTITY = {
  0: { name: "Iron", creed: "you outlast what should have killed you; grim, unbreakable" },
  1: { name: "Ash", creed: "you hit first and hit hardest; ferocious, hungry" },
  2: { name: "Vale", creed: "you are never where the blow lands; swift, mocking" },
};

// Per war-colour identity, as short imperatives that splice well. The shared scaffold
// words ("them", "the", "down") let the order-2 chain cross phrases at joints that still
// scream properly.
const CRY_SEEDS = {
  0: [   // IRON — outlasts what should have killed it
    "hold the line", "iron does not break", "stand and bleed them dry",
    "the black banner holds", "break on us then", "no step back",
    "outlast them all", "shields up and teeth shut", "let them come to iron",
  ],
  1: [   // ASH — hits harder than it can take
    "burn them down", "blood for the blue", "hit first and hit twice",
    "ash takes the field", "leave nothing standing", "strike now and strike hard",
    "the blue comes killing", "tear them open", "burn the field bare",
  ],
  2: [   // VALE — never where the blow lands
    "run them down", "quick now quick", "the green wind cuts",
    "never where they strike", "in and out and gone", "vale takes the roads",
    "fast as the fallows wind", "circle and cut them", "gone before the blow",
  ],
};

// What an ally says when you walk past — the no-model fallback rotation. The model
// version adds clan flavour; these are the floor, and the floor is exactly what was
// asked for: hail soldier, greetings warrior.
const HAIL_SEEDS = [
  "Hail, soldier.", "Hail, friend.", "Greetings, warrior.", "Well met, friend.",
  "Good hunting out there.", "The colours hold.", "Walk safe, soldier.",
];

export class WarCries {
  constructor(bridge, sfx) {
    this.bridge = bridge;
    this.sfx = sfx;
    this.rng = mulberry32(0xC121E5);
    this.corpora = new Map();      // colour -> Drift
    for (const c of [0, 1, 2]) {
      const d = new Drift(mulberry32(0x1A0 + c));
      d.learn(CRY_SEEDS[c].map((text) => ({ text, weight: 1 })));
      this.corpora.set(c, d);
    }
    this.cache = new Map([[0, []], [1, []], [2, []]]);   // colour -> [{text, wav}]
    this.hails = new Map([[0, []], [1, []], [2, []]]);   // the friendly cache
    // The hardcoded floor — filled first, kept forever, and PER FACTION: each clan
    // taunts in its own throat, through the same voices table the war-cries use.
    this.taunts = new Map([[0, []], [1, []], [2, []]]);
    // BAKED AUDIO SURVIVES THE PAGE. Every reload used to dump every WAV — in a dev loop
    // that reloads constantly, the armies were forever starting mute. IndexedDB holds the
    // baked bytes; a fresh session wakes with yesterday's arsenal and improves it.
    this.db = null;
    this.loadPersisted();
    this.newsCursor = 0;           // this reader's place in the deed feed
    this.bakeT = 0;
    this.baking = false;
    this.globalCd = 0;
    this.factionCd = new Map([[0, 0], [1, 0], [2, 0]]);
    this.hailCd = 0;
    this.fightCd = 0;
    this.warCd = 0;
    // THE TOWN OUTRANKS THE ARSENAL. main wires this to "is any voice system mid-request"
    // — while a villager is speaking (or the town is dreaming), the baker stands down.
    // The model has one thread; conversation gets it first, rehearsal takes the gaps.
    this.holdWhile = null;
  }

  async openDb() {
    if (typeof indexedDB === "undefined") return null;    // headless tests, old browsers
    if (this.db !== null) return this.db;
    this.db = await new Promise((res) => {
      const req = indexedDB.open("gw-voice", 1);
      req.onupgradeneeded = () => req.result.createObjectStore("wavs");
      req.onsuccess = () => res(req.result);
      req.onerror = () => res(null);
    });
    return this.db;
  }

  async persist(key, text, wav) {
    try {
      const db = await this.openDb();
      if (!db) return;
      db.transaction("wavs", "readwrite").objectStore("wavs").put({ text, wav }, key);
    } catch { /* storage full or blocked — the session cache still works */ }
  }

  async loadPersisted() {
    try {
      const db = await this.openDb();
      if (!db) return;
      const store = db.transaction("wavs", "readonly").objectStore("wavs");
      const [keys, vals] = await Promise.all([
        new Promise((res) => { const r = store.getAllKeys(); r.onsuccess = () => res(r.result); r.onerror = () => res([]); }),
        new Promise((res) => { const r = store.getAll(); r.onsuccess = () => res(r.result); r.onerror = () => res([]); }),
      ]);
      let n = 0;
      for (let i = 0; i < keys.length; i++) {
        const key = String(keys[i]);
        const { text, wav } = vals[i] || {};
        if (!text || !wav) continue;
        const [kind, colour] = key.split("|");
        if (kind === "taunt") {
          // Only lines still in the config list — re-toning the taunts retires old audio.
          const bin = this.taunts.get(Number(colour) % 3);
          if (bin && WARCRY.taunts.includes(text) && !bin.some((t) => t.text === text)) {
            bin.push({ text, wav });
            n++;
          }
        } else if (kind === "cry" || kind === "hail") {
          const bins = kind === "cry" ? this.cache : this.hails;
          const cap = kind === "cry" ? WARCRY.cachePerFaction : WARCRY.hailPerFaction;
          const bin = bins.get(Number(colour) % 3);
          if (bin && bin.length < cap && !bin.some((t) => t.text === text)) {
            bin.push({ text, wav });
            n++;
          }
        }
      }
      if (n) console.info(`[warcry] ${n} lines woke from the last session's arsenal`);
    } catch { /* an empty arsenal bakes fresh; never fatal */ }
  }

  /** Deeds join every faction's corpus — all three armies hear of the wanderer, and the
   *  chain splices your legend into their screaming. The freshest deed is also kept whole
   *  for the model, which weaves it into cries with actual grammar. */
  catchUpOnDeeds() {
    const { events, cursor } = deeds.since(this.newsCursor);
    if (!events.length) return;
    this.newsCursor = cursor;
    this.lastDeed = events[events.length - 1].text;
    for (const [c, d] of this.corpora) {
      d.learn(CRY_SEEDS[c].map((text) => ({ text, weight: 1 }))
        .concat(events.map((e) => ({ text: e.text, weight: 1.3 }))));
    }
  }

  update(dt) {
    if (!WARCRY.enabled) return;
    this.globalCd = Math.max(0, this.globalCd - dt);
    this.hailCd = Math.max(0, this.hailCd - dt);
    this.fightCd = Math.max(0, this.fightCd - dt);
    this.warCd = Math.max(0, this.warCd - dt);
    for (const [c, t] of this.factionCd) this.factionCd.set(c, Math.max(0, t - dt));
    this.catchUpOnDeeds();

    // BAKING happens only at rest: inside a town that serves you, with the bridge up.
    // The field never synthesizes — it is either already baked, or it is quiet.
    this.bakeT -= dt;
    if (this.baking || this.bakeT > 0) return;
    if (this.holdWhile?.()) return;
    if (this.bridge.state !== "online") return;
    // THE FLOOR FILLS FIRST, AND FILLS ANYWHERE: hardcoded taunts are piper-only — no
    // model to contend for — so they bake in the field too. Gating them to town once left
    // a reloaded session shouting its single loaded line ("I will kill you!") for a whole
    // fight. The model-backed shelves below still wait for a town's quiet.
    const shortTaunts = [0, 1, 2].filter((c) => this.taunts.get(c).length < WARCRY.taunts.length);
    if (shortTaunts.length) {
      // Emptiest clan first, so all three find a voice early instead of one army getting
      // the whole script while the other two stand there mute.
      shortTaunts.sort((a, b) => this.taunts.get(a).length - this.taunts.get(b).length);
      this.bakeT = WARCRY.tauntBakeEvery;
      this.bakeTaunt(shortTaunts[0]);
      return;
    }
    const s = sanctuaryOf(player.x, player.z, 0);
    if (!s || isHostileSanctuary(s)) return;
    const shortCries = [0, 1, 2].filter((c) => this.cache.get(c).length < WARCRY.cachePerFaction);
    const shortHails = [0, 1, 2].filter((c) => this.hails.get(c).length < WARCRY.hailPerFaction);
    if (!shortCries.length && !shortHails.length) return;
    this.bakeT = WARCRY.bakeEvery;
    // Bake whichever SHELF is emptier, by fill fraction — never one kind to completion
    // first. "Cries first, then hails" starved the hails behind twenty-four slow bakes:
    // three minutes in town before the first ally could say hello. Courtesy and war fill
    // side by side now.
    const cryFill = ([0, 1, 2].reduce((n, c) => n + this.cache.get(c).length, 0))
      / (3 * WARCRY.cachePerFaction);
    const hailFill = ([0, 1, 2].reduce((n, c) => n + this.hails.get(c).length, 0))
      / (3 * WARCRY.hailPerFaction);
    if (shortHails.length && (hailFill <= cryFill || !shortCries.length)) {
      this.bakeHail(shortHails[(this.rng() * shortHails.length) | 0]);
    } else {
      this.bakeOne(shortCries[(this.rng() * shortCries.length) | 0]);
    }
  }

  async bakeTaunt(colour) {
    this.baking = true;
    try {
      const bin = this.taunts.get(colour);
      // The next line this clan has not learned yet — order preserved, so the config list
      // reads as the order they pick them up.
      const text = WARCRY.taunts.find((t) => !bin.some((b) => b.text === t));
      if (!text) return;
      const { model, pace } = WARCRY.voices[colour];
      const wav = await this.bridge.speak(text, model, pace);
      if (wav) {
        bin.push({ text, wav });
        this.persist(`taunt|${colour}|${text}`, text, wav);
        console.info(`[warcry] taunt loaded for colour ${colour} `
          + `${bin.length}/${WARCRY.taunts.length}: "${text}"`);
      }
    } catch { /* a missing taunt is a quieter floor */ } finally {
      this.baking = false;
    }
  }

  /** One line for a mouth: the hardcoded floor or a baked cry, mixed by tauntChance —
   *  and always the floor when the baked shelf is still empty. */
  pickLine(colour) {
    const bin = this.cache.get(colour);
    const floor = this.taunts.get(colour);
    const useFloor = floor.length && (this.rng() < WARCRY.tauntChance || !bin.length);
    if (useFloor) return floor[(this.rng() * floor.length) | 0];
    return bin.length ? bin[(this.rng() * bin.length) | 0] : null;
  }

  async bakeHail(colour) {
    this.baking = true;
    try {
      const { model } = WARCRY.voices[colour];
      let text = null;
      // FAST-TRACK THE FIRST GREETINGS: the opening hail per faction skips the model and
      // speaks the rotation directly (~1.5s instead of ~6) — an ally who can say "Hail,
      // soldier" within seconds of you reaching town beats a poet who needs three minutes.
      // Later bakes upgrade the shelf with clan-flavoured lines.
      if (this.hails.get(colour).length >= 1 && this.bridge.info?.llm) {
        const who = CRY_IDENTITY[colour];
        const res = await this.bridge.line(
          `You are a soldier of the ${who.name} clan on a war-torn frontier — ${who.creed}. `
          + `A sworn ally, the lone wanderer who fights beside your colours, walks past your `
          + `post. Greet them in ONE short hail, two to six words — like "Hail, soldier" or `
          + `"Well met, warrior". No stage directions, no quotes, just the hail.`,
          { words: 6, voice: model, lengthScale: 1.0 });
        const clean = res?.text ? cleanLine(res.text, 1) : null;
        if (clean && clean.split(" ").length <= 7 && res.audio) {
          const gist = (t) => t.toLowerCase().replace(/[^a-z]+/g, " ").trim();
          let wav = res.audio;
          if (gist(clean) !== gist(res.text)) wav = await this.bridge.speak(clean, model, 1.0);
          if (wav) { this.stashHail(colour, clean, wav); return; }
        }
      }
      // No model: the rotation the feature was asked for with, verbatim.
      text = HAIL_SEEDS[(this.rng() * HAIL_SEEDS.length) | 0];
      const wav = await this.bridge.speak(text, model, 1.0);
      if (wav) this.stashHail(colour, text, wav);
    } catch {
      // A failed bake is a quieter camp, nothing more.
    } finally {
      this.baking = false;
    }
  }

  stashHail(colour, text, wav) {
    const bin = this.hails.get(colour);
    bin.push({ text, wav });
    if (bin.length > WARCRY.hailPerFaction) bin.shift();
    this.persist(`hail|${colour}|${text}`, text, wav);
    console.info(`[warcry] baked hail for colour ${colour}: "${text}"`);
  }

  async bakeOne(colour) {
    this.baking = true;
    try {
      const { model, pace } = WARCRY.voices[colour];
      // COHERENCE COSTS NOTHING HERE — baking happens at rest, so the model can write the
      // cry (a Markov splice screamed at you read as noise, not menace). The clan's creed
      // shapes it, and the wanderer's freshest deed gives it a TARGET: sack a camp and
      // the next batch of cries can be about the camp-burner specifically. Markov remains
      // the no-model fallback, so an army is never mute for lack of ollama.
      if (this.bridge.info?.llm) {
        const who = CRY_IDENTITY[colour];
        const word = this.lastDeed ? ` The lone wanderer you all hunt is out there; word is ${this.lastDeed}.` : "";
        const res = await this.bridge.line(
          `You are a war-crier of the ${who.name} clan on a war-torn frontier — ${who.creed}.${word} `
          + `Shout ONE battle cry, three to eight words, plain and brutal. `
          + `No stage directions, no quotes, just the cry itself.`,
          { words: 8, voice: model, lengthScale: pace });
        const clean = res?.text ? cleanLine(res.text, 1) : null;
        if (clean && clean.split(" ").length <= 9) {
          const gist = (t) => t.toLowerCase().replace(/[^a-z]+/g, " ").trim();
          let wav = res.audio;
          if (gist(clean) !== gist(res.text)) wav = await this.bridge.speak(clean, model, pace);
          if (wav) {
            this.stash(colour, clean, wav);
            return;
          }
        }
      }
      // The Markov fallback: half-formed, but an army with no model still screams.
      const drift = this.corpora.get(colour);
      let text = null;
      for (let i = 0; i < 4 && !text; i++) {
        const f = drift.step();
        if (f && f.indexOf(" ") > 0 && f.split(" ").length <= 6) text = f;
      }
      if (!text) return;
      const wav = await this.bridge.speak(`${text}!`, model, pace);
      if (wav) this.stash(colour, `${text}!`, wav);
    } catch {
      // A failed bake is a quieter army, nothing more.
    } finally {
      this.baking = false;
    }
  }

  stash(colour, text, wav) {
    const bin = this.cache.get(colour);
    bin.push({ text, wav });
    if (bin.length > WARCRY.cachePerFaction) bin.shift();
    this.persist(`cry|${colour}|${text}`, text, wav);
    console.info(`[warcry] baked for colour ${colour}: "${text}"`);
  }

  /**
   * A mob wants to scream. `kind` prices the moment: a charge nearly always cries (it is
   * the audio telegraph), a pack noticing you sometimes does, a garrison arming always.
   * Budget gates keep a battlefield from becoming a playground.
   */
  cry(e, kind = "aggro") {
    if (!WARCRY.enabled || !e) return;
    const colour = (e.faction || 0) % 3;
    // A HAIL is its own channel: friendly cache, natural pitch, no echoes — a greeting is
    // a voice, not a warband — and its own battlefield cooldown, so courtesy never eats
    // the war's budget (or vice versa).
    if (kind === "hail") {
      if (this.hailCd > 0 || this.rng() >= WARCRY.hailChance) return;
      const bin = this.hails.get(colour);
      if (!bin.length) return;
      const { text, wav } = bin[(this.rng() * bin.length) | 0];
      this.hailCd = WARCRY.hailCd;
      this.sfx.playClip(wav, e.x, e.z, WARCRY.hailVolume, 1);
      console.info(`[warcry] colour ${colour} (hail): "${text}"`);
      return;
    }
    // BATTLE CHATTER (fight / war): shares the one-voice gate so a fight never turns to
    // mush, keeps its own slower clock, and deliberately does NOT set the faction cooldown
    // — a charge telegraph must never be blocked by someone running their mouth. No echoes.
    if (kind === "fight" || kind === "war") {
      const isWar = kind === "war";
      if (this.globalCd > 0) return;
      if ((isWar ? this.warCd : this.fightCd) > 0) return;
      if (this.rng() >= (isWar ? WARCRY.warChance : WARCRY.fightChance)) return;
      const pick = this.pickLine(colour);
      if (!pick) return;
      this.globalCd = WARCRY.globalCd;
      if (isWar) this.warCd = WARCRY.warCd; else this.fightCd = WARCRY.fightCd;
      const { rate } = WARCRY.voices[colour];
      this.sfx.playClip(pick.wav, e.x, e.z, WARCRY.volume, rate);
      console.info(`[warcry] colour ${colour} (${kind}): "${pick.text}"`);
      return;
    }
    if (this.globalCd > 0 || this.factionCd.get(colour) > 0) return;
    const chance = kind === "charge" ? WARCRY.chargeChance
      : kind === "arm" ? 1 : WARCRY.aggroChance;
    if (this.rng() >= chance) return;
    const pick = this.pickLine(colour);
    if (!pick) return;                             // nothing loaded yet: still quiet
    const { text, wav } = pick;
    this.globalCd = WARCRY.globalCd;
    this.factionCd.set(colour, WARCRY.factionCd);
    const { rate } = WARCRY.voices[colour];
    this.sfx.playClip(wav, e.x, e.z, WARCRY.volume, rate);
    console.info(`[warcry] colour ${colour} (${kind}): "${text}"`);

    // THE WARBAND ANSWERS. Packmates near the crier take up the cry — staggered, from
    // their own positions, each throat pitched a little differently so one cached WAV
    // reads as several voices. Echoes ride OUTSIDE the cooldowns: they are part of this
    // volley, not new cries. This is the difference between a soloist and a war party.
    let echoes = 0;
    for (const o of nearby(e.x, e.z, 34)) {
      if (echoes >= WARCRY.echoes) break;
      if (o === e || o.kind !== "mob" || o.hp <= 0 || ((o.faction || 0) % 3) !== colour) continue;
      const echoPick = this.pickLine(colour);
      if (!echoPick) break;
      const delay = WARCRY.echoDelayMin + this.rng() * (WARCRY.echoDelayMax - WARCRY.echoDelayMin);
      const throat = rate * (0.94 + this.rng() * 0.12);
      setTimeout(() => {
        if (o.hp > 0) this.sfx.playClip(echoPick.wav, o.x, o.z, WARCRY.volume * WARCRY.echoVolume, throat);
      }, delay * 1000);
      echoes++;
    }
  }
}
