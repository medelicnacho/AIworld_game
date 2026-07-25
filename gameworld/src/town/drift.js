// The subconscious murmur — a port of localprototype/agent/thought.py, upgraded to
// ORDER-2 WITH BACKOFF (the option the lab's own design doc names alongside order-1).
//
// Every start and transition carries a WEIGHT — in the lab that weight is memory
// salience, which is how charged memories come to dominate what an agent mutters about.
// V1 seeds it with a static town vocabulary at weight 1; V3 (VOICE.md) starts writing
// player-caused events in at higher weights, and nothing in this file changes when it
// does. That is the point of porting the lab's shape instead of writing a phrase picker:
// the upgrade path is data.
//
// WHY ORDER-2: an order-1 chain follows one word at a time, and what it produces is not
// "dreamlike", it is word salad — the line between a distracted person and a broken radio.
// Following word PAIRS keeps fragments grammatical for a clause at a stretch. The BACKOFF
// is what keeps the poetry: on a pair dead-end — or a deliberate roll of the dice — the
// chain drops to order-1 for one step and JUMPS to another thought mid-sentence. Grammar
// most of the time, a seam sometimes: exactly a person talking to themselves. Set
// BACKOFF_CHANCE to 0 and it recites its sources; to 1 and it is the old salad machine.
//
// Still deliberately half-formed (D3) — the moment this reads as a well-formed sentence
// it starts competing with the deliberate LLM voice, which is Santāna's register, not a
// villager's. Seeded RNG in, like everything else (D14): same seed, same drift.

const MAX_FRAGMENT = 7;     // max words in a single drift fragment
const BUFFER = 5;           // how many recent fragments the rolling buffer keeps
const BACKOFF_CHANCE = 0.22; // odds per step of a deliberate order-1 jump between thoughts

export class Drift {
  /** @param rng a mulberry32-style () => [0,1) function */
  constructor(rng) {
    this.rng = rng;
    this.starts = [];          // [word, weight]
    this.trans = new Map();    // lowercased word -> [[next, weight], ...]   (order-1)
    this.trans2 = new Map();   // "a b" lowercased pair -> [[next, weight], ...] (order-2)
    this.drift = [];           // rolling buffer of recent fragments
  }

  static words(text) {
    return text.split(/\s+/)
      .map((w) => w.replace(/^[.,!?]+|[.,!?]+$/g, ""))
      .filter((w) => w && w !== "...");
  }

  /** Rebuild the chain from sources: [{ text, weight }]. Call again any time the
   *  vocabulary changes — relearning is cheap and keeps no stale transitions. */
  learn(sources) {
    this.starts.length = 0;
    this.trans.clear();
    this.trans2.clear();
    for (const { text, weight } of sources) {
      const ws = Drift.words(text);
      if (!ws.length) continue;
      this.starts.push([ws[0], weight]);
      for (let i = 0; i < ws.length - 1; i++) {
        const k = ws[i].toLowerCase();
        let list = this.trans.get(k);
        if (!list) this.trans.set(k, (list = []));
        list.push([ws[i + 1], weight]);
        if (i >= 1) {
          const k2 = `${ws[i - 1].toLowerCase()} ${k}`;
          let list2 = this.trans2.get(k2);
          if (!list2) this.trans2.set(k2, (list2 = []));
          list2.push([ws[i + 1], weight]);
        }
      }
    }
  }

  /** Generate one fragment and push it onto the rolling buffer. Null when unlearned. */
  step() {
    if (!this.starts.length) return null;
    const word = this.weighted(this.starts);
    const out = [word];
    for (let i = 0; i < MAX_FRAGMENT - 1; i++) {
      const last = out[out.length - 1].toLowerCase();
      // Prefer the PAIR (grammar), unless the dice call for a jump between thoughts or
      // the pair dead-ends — then one order-1 step (the seam), then back to pairs.
      const pair = out.length >= 2
        ? this.trans2.get(`${out[out.length - 2].toLowerCase()} ${last}`) : null;
      const nxt = (pair && this.rng() >= BACKOFF_CHANCE) ? pair : this.trans.get(last);
      if (!nxt) break;
      out.push(this.weighted(nxt));
    }
    const fragment = out.join(" ");
    this.drift.push(fragment);
    if (this.drift.length > BUFFER) this.drift.splice(0, this.drift.length - BUFFER);
    return fragment;
  }

  /** The most recent fragments — the lab feeds these to the LLM; V1 only reads them
   *  to avoid a villager repeating itself back to back. */
  current(n = 3) {
    return this.drift.slice(-n);
  }

  weighted(choices) {
    let total = 0;
    for (const [, w] of choices) total += w;
    let r = this.rng() * total;
    for (const [item, w] of choices) {
      r -= w;
      if (r <= 0) return item;
    }
    return choices[choices.length - 1][0];
  }
}
