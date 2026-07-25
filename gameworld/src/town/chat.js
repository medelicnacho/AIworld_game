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
    return { logs: [...this.logs.entries()].slice(-12) };   // the last dozen acquaintances
  }

  /** Put those memories back, each turn marked PRIOR — an earlier visit, not this
   *  conversation. The prompt treats the two differently: prior turns are what she
   *  REMEMBERS about you; this session's turns are what you are saying now. */
  restore(data) {
    if (!data?.logs?.length) return;
    let n = 0;
    for (const [k, log] of data.logs) {
      if (!Array.isArray(log) || !log.length) continue;
      this.logs.set(k, log.map((t) => ({ who: t.who, text: String(t.text || ""), prior: true }))
        .filter((t) => t.text).slice(-LOG_KEEP));
      n++;
    }
    if (n) console.info(`[chat] ${n} villager${n > 1 ? "s" : ""} remember${n > 1 ? "" : "s"} talking to you`);
  }

  /** G was pressed. Open on the nearest villager if the venue allows; else do nothing —
   *  the same venue rule as the ambient voice (the neutral starter town, model up). */
  tryOpen() {
    if (this.open) { this.close(); return true; }
    const s = sanctuaryOf(player.x, player.z, 0);
    if (!s || !s.neutral || s.city) return false;
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
        + `A wanderer — an armed traveller the town knows by sight — has stopped to talk `
        + `to you while you work. `
        + (past ? `You have spoken with this wanderer before; you remember ${past}. ` : "")
        + (now ? `So far today: ${now} ` : "")
        + `The wanderer just said to you: "${said.replace(/"/g, "'")}". `
        + `Your mood is ${mood}. ${MOOD_STYLE[mood] || ""} `
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
      console.info(`[chat] you: "${said}" -> ${nameOf(v)} the ${v.role.name} (${mood}): "${clean}"`);
      if (wav) this.sfx.playClip(wav, v.x, v.z, VOICE.volume);
    } catch {
      console.info(`[chat] you: "${said}" -> ${v.role.name}: NO REPLY (error)`);
      log.push({ who: "them", text: "…" });          // the lab hiccuped; she just works on
    } finally {
      this.busy = false;
      this.hooks.onThinking?.(false);
      if (this.open) { this.render(); this.input.focus(); }
    }
  }
}
