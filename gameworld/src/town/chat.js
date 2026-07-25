// TALKING TO A VILLAGER (VOICE.md C1) — press G near one, type, be answered aloud.
//
// The design rule that keeps this from being a chatbot: a villager is not an assistant,
// she is a busy woman at a workbench. She answers in ONE short line, in her own register,
// through the same scrubber every spoken line passes, and goes back to her work. Ask her
// about calculus and she says something tired about the war, because that is who she is.
// The one-line cap is not a cost limit — it is what keeps her a person. (The lab ships a
// literal detector for the failure mode this guards against: drift.py GENERIC_ASSISTANT.)
//
// And the founding rule, applied to YOU: player input is just another utterance. What you
// type goes through townVoice.hear() exactly like a villager's spoken line — into the
// town's drift memory — so what you tell the Herbalist can surface, warped, in the
// Keeper's ambient muttering ten minutes later. That moment is the entire pitch.
//
// This is also, deliberately, a dry run of Santāna's whole interface (typed line in,
// spoken line out, a visible thinking state) on characters where the stakes are low.

import { VOICE } from "../config.js";
import { player } from "../state.js";
import { sanctuaryOf } from "../world/sanctuary.js";
import { servesYou } from "../prog/factions.js";
import { WORLD, TRADE, MOOD_STYLE, voiceOf, cleanLine, nameOf } from "./voice.js";

const LOG_KEEP = 8;      // turns remembered per villager (session memory — C2 persists it)
// CHEAPER MEMORY (tuned after the wedge): every remembered turn is re-processed by the
// model on EVERY reply, and on a CPU that cost compounds — by turn six a conversation had
// crept to ~8s per answer. The model now sees only the last exchange (plus C2's two
// remembered prior turns), each clipped to its gist; the PANEL keeps the full history,
// because the player's memory is free — it is only the model's that is billed per token.
const LOG_PROMPT = 2;    // turns actually shown to the model
const CLIP = 90;         // longest remembered turn, in characters, as the model hears it
const clip = (t) => (t.length > CLIP ? t.slice(0, CLIP - 3) + "..." : t);

// A NAME IS A FACT, NOT A LINE OF DIALOGUE. The playtest that forced this: the player
// introduced themselves, the villager used the name five replies straight — then one
// close-and-reopen later denied ever hearing it, because the name lived only in a
// transcript the cheap-memory window had scrolled past. Facts get extracted ONCE, stored
// beside the log, and stated to the model as things she KNOWS — memory that cannot fall
// out of a context window. Deliberately conservative patterns: mis-hearing "i'm going"
// as an introduction would be worse than missing one.
// `explicit` marks the patterns where the player is unambiguously naming themselves.
// The bare "im X" form is a GUESS — "...im really sorry" once christened the player
// "Really Sorry", and the herbalist warmly used it for the rest of the day — so a guess
// may only fill an empty name, never overwrite a known one.
const NAME_RX = [
  { rx: /\bmy name(?:'s|s| is)\s+([a-z][a-z']+(?:\s+[a-z][a-z']+)?)/i, explicit: true },
  { rx: /\bcall me\s+([a-z][a-z']+(?:\s+[a-z][a-z']+)?)/i, explicit: true },
  { rx: /\b(?:i am|i'm|im)\s+([a-z][a-z']+(?:\s+[a-z][a-z']+)?)\s*[.!]?$/i, explicit: false },
];
// EVERY captured word is checked, and the list leans long: the states of being a person
// declares about themselves ("im really sorry", "im dead serious", "im so tired") must
// never become who they ARE. Missing a real name is recoverable — "my name is" always
// works; wearing an apology as a name is a haunting.
const NOT_NAMES = new Set(["going", "gonna", "here", "sure", "fine", "sorry", "just",
  "back", "leaving", "staying", "done", "good", "okay", "ok", "not", "so", "the",
  "really", "very", "truly", "honestly", "actually", "serious", "dead", "tired",
  "hungry", "lost", "glad", "happy", "sad", "angry", "mad", "busy", "ready", "afraid",
  "scared", "new", "old", "alone", "kidding", "joking", "confused", "curious", "broke",
  "hurt", "well", "home", "away", "outta", "sick", "cold", "warm", "rich", "poor"]);

// REGARD (VOICE.md C3) — what she thinks of YOU, earned one utterance at a time. The
// playtest that demanded it: "screw you too" and "your mom is lame" cost the player
// nothing; every reply came back the same flat cold. Now each message shifts a
// per-villager disposition (clamped so one outburst is a mark, not a verdict), it is
// stored beside her other facts, it survives the save — and grudges FADE slower than
// gossip: a day away softens one step, it never resets. Scored by lexicon, not by the
// model, for the same reason mood is: a dial the sim owns is a dial the sim can trust.
// Expanded from the playtest, whose abuse was more inventive than the first list — "fat
// hoe" and "nasty ass face" sailed past a lexicon that knew only "stupid" and "lame",
// so the worst session on record never cost a single step of regard.
const RUDE = new Set(["screw", "stupid", "idiot", "shut", "dumb", "lame", "suck", "ugly",
  "fool", "fools", "hate", "damn", "worthless", "trash", "loser", "shrew", "hag",
  "ass", "fat", "nasty", "hoe", "bitch", "shit", "fuck", "fucking", "crap", "bastard",
  "jerk", "freak", "pig", "coward", "wench", "crone", "moron", "clown"]);
const KIND = new Set(["please", "thanks", "thank", "sorry", "appreciate", "kind",
  "lovely", "good", "beautiful", "wonderful", "friend", "helpful"]);

/** How this utterance moves her opinion of you: -1, 0, or +1. Exported for its tests. */
export function regardShift(said) {
  const words = said.toLowerCase().replace(/[^a-z' ]+/g, " ").split(/\s+/);
  let d = 0;
  for (const w of words) {
    if (RUDE.has(w)) d--;
    else if (KIND.has(w)) d++;
  }
  return Math.max(-1, Math.min(1, d));
}

/** Disposition as a word the prompt can carry, plus the register it implies. */
export function regardWord(r = 0) {
  return r <= -3 ? "hostile" : r < 0 ? "sour" : r >= 3 ? "friendly" : r > 0 ? "warming" : "wary";
}
const REGARD_STYLE = {
  hostile: "You want this one GONE — cold, cutting, no pleasantries, the shortest answers you have.",
  sour: "They have been rude to you before — keep it short, unhelpful, and unimpressed.",
  wary: "",   // the baseline; the world blurb already carries it
  warming: "They have been decent to you — a little openness under the weariness.",
  friendly: "You like this one — warmth under the weariness, and you use their name.",
};

/** The wanderer's name if this utterance introduces one: { name, explicit } or null.
 *  Exported for its tests. */
export function nameIn(said) {
  for (const { rx, explicit } of NAME_RX) {
    const m = said.match(rx);
    if (!m) continue;
    const words = m[1].trim().split(/\s+/).slice(0, 2);
    if (words.some((w) => NOT_NAMES.has(w.toLowerCase()))) continue;
    return {
      name: words.map((w) => w[0].toUpperCase() + w.slice(1).toLowerCase()).join(" "),
      explicit,
    };
  }
  return null;
}

export class TownChat {
  /**
   * @param bridge    net/bridge.js
   * @param villagers town/villagers.js
   * @param townVoice town/voice.js — the ambient system; the chat borrows its ears (hear),
   *                  its mood, and stays out of its way (its busy flag pauses murmurs)
   * @param sfx       audio/sfx.js
   * @param hooks     { onOpen, onClose, onThinking } — main.js owns pause/resume/HUD
   */
  constructor(bridge, villagers, townVoice, sfx, hooks) {
    this.bridge = bridge;
    this.villagers = villagers;
    this.townVoice = townVoice;
    this.sfx = sfx;
    this.hooks = hooks;
    this.open = false;
    this.busy = false;
    this.target = null;
    // Conversation memory per VILLAGER, keyed stably (role + fixed walk angle) so it
    // survives the villager list being rebuilt. Session-lifetime in C1; C2 saves it.
    this.logs = new Map();
    // What each villager KNOWS about you — facts, not transcript. { name } for now;
    // regard (C3) will live here too. Saved and restored beside the logs.
    this.facts = new Map();
    this.el = document.getElementById("chat");
    this.el.innerHTML = `
      <div class="who"></div>
      <div class="lines"></div>
      <div class="row"><input type="text" maxlength="140" placeholder="say something… (Enter to send · Esc to leave)"><button>say</button></div>`;
    this.whoEl = this.el.querySelector(".who");
    this.linesEl = this.el.querySelector(".lines");
    this.input = this.el.querySelector("input");
    this.sendBtn = this.el.querySelector("button");
    // Keys typed into the chat must NEVER reach the game — the controller listens on
    // window, and without this a typed "w" walks you away from the person you're talking
    // to. stopPropagation at the input, where the event begins.
    this.input.addEventListener("keydown", (e) => {
      e.stopPropagation();
      if (e.code === "Enter") this.send();
      if (e.code === "Escape") this.close();
    });
    this.sendBtn.addEventListener("click", () => this.send());
  }

  // uid, not the walk angle: the angle CHANGES as a villager strolls, which shattered
  // her memory of you across the moments of her circuit — every G a stranger again.
  keyOf(v) { return `${v.s.id}|${v.uid ?? v.role.name}`; }
  logOf(v) {
    const k = this.keyOf(v);
    let log = this.logs.get(k);
    if (!log) this.logs.set(k, (log = []));
    return log;
  }

  /** Every villager's memory of talking to you, as plain data — for the save (C2). */
  dump() {
    return {
      logs: [...this.logs.entries()].slice(-12),   // the last dozen acquaintances
      facts: [...this.facts.entries()].slice(-24),
    };
  }

  /** Put those memories back, each turn marked PRIOR — an earlier visit, not this
   *  conversation. The prompt treats the two differently: prior turns are what she
   *  REMEMBERS about you; this session's turns are what you are saying now. */
  restore(data, hoursAway = 0) {
    if (!data) return;
    if (!data.logs?.length && !data.facts?.length) return;
    let n = 0;
    for (const [k, log] of data.logs) {
      if (!Array.isArray(log) || !log.length) continue;
      this.logs.set(k, log.map((t) => ({ who: t.who, text: String(t.text || ""), prior: true }))
        .filter((t) => t.text).slice(-LOG_KEEP));
      n++;
    }
    // Grudges (and fondness) FADE slower than gossip: one step toward indifference per
    // full day away — never a reset. Names don't fade at all; a name is a name — unless
    // an old save christened the player with a state of being ("Really Sorry", by a
    // pattern since fixed), in which case the false name is quietly unlearned here.
    const soften = Math.floor(Math.max(0, hoursAway) / 24);
    for (const [k, f] of data.facts || []) {
      if (!f || typeof f !== "object") continue;
      const r = f.regard || 0;
      const clean = { ...f, regard: r > 0 ? Math.max(0, r - soften) : Math.min(0, r + soften) };
      if (clean.name && clean.name.split(" ").some((w) => NOT_NAMES.has(w.toLowerCase()))) {
        delete clean.name;
      }
      this.facts.set(k, clean);
    }
    if (n) console.info(`[chat] ${n} villager${n > 1 ? "s" : ""} remember${n > 1 ? "" : "s"} talking to you`);
  }

  /** G was pressed. Open on the nearest villager if the venue allows; else do nothing —
   *  the same venue rule as the ambient voice (the neutral starter town, model up). */
  tryOpen() {
    if (this.open) { this.close(); return true; }
    const s = sanctuaryOf(player.x, player.z, 0);
    if (!s || !servesYou(s)) return false;         // any town that serves you will talk
    if (this.bridge.state !== "online" || !this.bridge.info?.llm) return false;
    let best = null, bd = VOICE.range;
    for (const v of this.villagers.list) {
      if (v.s !== s || v.role.faction) continue;
      const d = Math.hypot(v.x - player.x, v.z - player.z);
      if (d < bd) { bd = d; best = v; }
    }
    if (!best) return false;
    this.target = best;
    this.open = true;
    this.whoEl.textContent = `${nameOf(best)} · the ${best.role.name}`;
    this.render();
    this.el.classList.add("show");
    this.hooks.onOpen?.();
    if (document.pointerLockElement) document.exitPointerLock();
    setTimeout(() => this.input.focus(), 50);
    return true;
  }

  close() {
    if (!this.open) return;
    this.open = false;
    this.busy = false;
    this.hooks.onThinking?.(false);
    this.el.classList.remove("show");
    this.input.blur();
    // A courtesy gap before the ambient voice resumes: the model is serialized on the lab
    // side, and an ambient line firing the instant you close would hog it for seconds —
    // right when you are likeliest to reopen and say one more thing.
    this.townVoice.cooldown = Math.max(this.townVoice.cooldown, 8);
    this.hooks.onClose?.();
  }

  render(thinking = false) {
    const log = this.target ? this.logOf(this.target) : [];
    this.linesEl.innerHTML = log.map((t) =>
      `<div class="${t.who}${t.prior ? " prior" : ""}"><b>${t.who === "you" ? "You" : nameOf(this.target)}</b> ${t.text}</div>`)
      .join("") + (thinking ? `<div class="them"><b>${nameOf(this.target)}</b> <i>…</i></div>` : "");
    this.linesEl.scrollTop = this.linesEl.scrollHeight;
  }

  async send() {
    if (!this.open || this.busy) return;
    const said = this.input.value.trim();
    if (!said) { this.close(); return; }
    this.input.value = "";
    const v = this.target;
    const log = this.logOf(v);
    log.push({ who: "you", text: said });
    if (log.length > LOG_KEEP) log.splice(0, log.length - LOG_KEEP);
    // Introductions become FACTS she keeps, not lines that scroll away — and every
    // utterance moves her REGARD before she answers, so rudeness costs you this very
    // reply, not some later one.
    const k = this.keyOf(v);
    const f = { ...this.facts.get(k) };
    const introduced = nameIn(said);
    if (introduced && (introduced.explicit || !f.name)) f.name = introduced.name;
    f.regard = Math.max(-4, Math.min(4, (f.regard || 0) + regardShift(said)));
    this.facts.set(k, f);
    const known = f.name;
    const regard = regardWord(f.regard);
    // YOUR words enter the town's memory like anyone else's. This single call is C1's
    // whole thesis: what you say here can resurface in ambient talk later.
    this.townVoice.hear(said);
    this.busy = true;
    this.hooks.onThinking?.(true);
    this.render(true);
    try {
      const { model, pace } = voiceOf(v);
      const mood = this.townVoice.currentMood();
      // Two kinds of history, told apart in the prompt: PRIOR turns (an earlier visit —
      // what she REMEMBERS about you, C2) and this conversation's turns (what you are
      // saying now). Collapsing them read as one endless conversation; a person who met
      // you yesterday doesn't resume mid-sentence, she recognises you.
      const past = log.filter((t) => t.prior).slice(-2)
        .map((t) => `${t.who === "you" ? "they said" : "you answered"} "${clip(t.text)}"`).join(", and ");
      const now = log.filter((t) => !t.prior).slice(-LOG_PROMPT - 1, -1)
        .map((t) => `${t.who === "you" ? "The wanderer" : "You"} said: "${clip(t.text)}"`).join(" ");
      const prompt = WORLD
        + `You are ${nameOf(v)}, the town ${v.role.name} — ${TRADE[v.role.name] || "you live and work here"}. `
        + (known
          ? `The wanderer ${known} — an armed traveller you know by name — has stopped to `
            + `talk to you while you work. `
          : `A wanderer — an armed traveller the town knows by sight — has stopped to talk `
            + `to you while you work. `)
        + (past ? `You have spoken with this wanderer before; you remember ${past}. ` : "")
        + (now ? `So far today: ${now} ` : "")
        + `The wanderer just said to you: "${said.replace(/"/g, "'")}". `
        + `Your mood is ${mood}. ${MOOD_STYLE[mood] || ""} `
        + (REGARD_STYLE[regard] ? `Toward this wanderer you are ${regard}: ${REGARD_STYLE[regard]} ` : "")
        + `Answer them with ONE short line and no more — you are busy, and you speak as a `
        + `person of this town, never as a helper or a guide. If they ask something outside `
        + `your world, answer as a tired townsperson would. Plain frontier speech in real `
        + `words only. No stage directions, no lists, no advice unless it is town advice.`;
      const res = await this.bridge.line(prompt, {
        words: VOICE.lineWords, voice: model, lengthScale: pace,
      });
      // "Mara." is an answer (floor 1) — and a leading self-label is stage furniture:
      // the model sometimes writes "Edda: My name's Edda...", theatre-script style.
      let clean = res?.text ? cleanLine(res.text, 1) : null;
      if (clean) clean = clean.replace(new RegExp(`^${nameOf(v)}\\s*[:,-]\\s+`, "i"), "").trim() || clean;
      if (!clean) {                                  // she looks at you and says nothing
        // Failures land in the transcript too — the wedge that motivated this was
        // invisible precisely because only successes were ever logged.
        console.info(`[chat] you: "${said}" -> ${v.role.name}: NO REPLY (${res ? "scrubbed to silence" : "bridge timeout/offline"})`);
        log.push({ who: "them", text: "…" });
        return;
      }
      const gist = (t) => t.toLowerCase().replace(/[^a-z]+/g, " ").trim();
      let wav = res.audio;
      if (gist(clean) !== gist(res.text)) wav = await this.bridge.speak(clean, model, pace);
      log.push({ who: "them", text: clean });
      if (log.length > LOG_KEEP) log.splice(0, log.length - LOG_KEEP);
      this.townVoice.hear(clean);                    // her answer is heard by the town too
      console.info(`[chat] you: "${said}" -> ${nameOf(v)} the ${v.role.name} (${mood}, ${regard}): "${clean}"`);
      if (wav) this.sfx.playClip(wav, v.x, v.z, VOICE.volume);
    } catch {
      console.info(`[chat] you: "${said}" -> ${v.role.name}: NO REPLY (error)`);
      log.push({ who: "them", text: "…" });          // the lab hiccuped; she just works on
    } finally {
      this.busy = false;
      this.hooks.onThinking?.(false);
      if (this.open) {
        // The header carries her disposition once it has one — feedback that words land.
        const rw = regardWord(this.facts.get(this.keyOf(v))?.regard);
        this.whoEl.textContent = `${nameOf(v)} · the ${v.role.name}${rw !== "wary" ? ` · ${rw}` : ""}`;
        this.render();
        this.input.focus();
      }
    }
  }
}
