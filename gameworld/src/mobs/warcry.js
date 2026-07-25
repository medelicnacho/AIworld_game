// WAR-CRIES — the three armies find their voices.
//
// This is the one place raw Markov IS voiced, and deliberately: a scream is not
// conversation. The town's drift went underground because half-formed murmurs sounded
// broken; a half-formed BATTLE CRY sounds exactly like a battle cry — grammar is not what
// a charging soldier is known for. Each war-colour keeps its own drift corpus, seeded
// with its identity (Iron endures, Ash burns, Vale runs) and FED FROM THE DEED FEED —
// so after you sack a camp, the cries coming at you can carry warped fragments of your
// own legend. Your reputation, screamed back at you across a battlefield.
//
// The engineering rule that makes it shippable: NO SYNTHESIS IN COMBAT. Cries are baked
// in town — the quiet place, the natural pre-bake station — into a per-faction cache of
// WAVs, and the field only ever plays what is already baked. A faction whose cache is
// empty simply doesn't scream yet; silence is the baseline everywhere in this project.

import { WARCRY } from "../config.js";
import { player } from "../state.js";
import { sanctuaryOf } from "../world/sanctuary.js";
import { isHostileSanctuary } from "../prog/factions.js";
import { mulberry32 } from "../rng.js";
import { Drift } from "../town/drift.js";
import { deeds } from "../world/events.js";

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
    this.newsCursor = 0;           // this reader's place in the deed feed
    this.bakeT = 0;
    this.baking = false;
    this.globalCd = 0;
    this.factionCd = new Map([[0, 0], [1, 0], [2, 0]]);
  }

  /** Deeds join every faction's corpus — all three armies hear of the wanderer, and the
   *  chain splices your legend into their screaming. */
  catchUpOnDeeds() {
    const { events, cursor } = deeds.since(this.newsCursor);
    if (!events.length) return;
    this.newsCursor = cursor;
    for (const [c, d] of this.corpora) {
      d.learn(CRY_SEEDS[c].map((text) => ({ text, weight: 1 }))
        .concat(events.map((e) => ({ text: e.text, weight: 1.3 }))));
    }
  }

  update(dt) {
    if (!WARCRY.enabled) return;
    this.globalCd = Math.max(0, this.globalCd - dt);
    for (const [c, t] of this.factionCd) this.factionCd.set(c, Math.max(0, t - dt));
    this.catchUpOnDeeds();

    // BAKING happens only at rest: inside a town that serves you, with the bridge up.
    // The field never synthesizes — it is either already baked, or it is quiet.
    this.bakeT -= dt;
    if (this.baking || this.bakeT > 0) return;
    if (this.bridge.state !== "online") return;
    const s = sanctuaryOf(player.x, player.z, 0);
    if (!s || isHostileSanctuary(s)) return;
    const short = [0, 1, 2].filter((c) => this.cache.get(c).length < WARCRY.cachePerFaction);
    if (!short.length) return;
    this.bakeT = WARCRY.bakeEvery;
    this.bakeOne(short[(this.rng() * short.length) | 0]);
  }

  async bakeOne(colour) {
    this.baking = true;
    try {
      const drift = this.corpora.get(colour);
      let text = null;
      for (let i = 0; i < 4 && !text; i++) {
        const f = drift.step();
        if (f && f.indexOf(" ") > 0 && f.split(" ").length <= 6) text = f;
      }
      if (!text) return;
      const { model, pace } = WARCRY.voices[colour];
      const wav = await this.bridge.speak(`${text}!`, model, pace);
      if (!wav) return;
      const bin = this.cache.get(colour);
      bin.push({ text, wav });
      if (bin.length > WARCRY.cachePerFaction) bin.shift();
      console.info(`[warcry] baked for colour ${colour}: "${text}!"`);
    } catch {
      // A failed bake is a quieter army, nothing more.
    } finally {
      this.baking = false;
    }
  }

  /**
   * A mob wants to scream. `kind` prices the moment: a charge nearly always cries (it is
   * the audio telegraph), a pack noticing you sometimes does, a garrison arming always.
   * Budget gates keep a battlefield from becoming a playground.
   */
  cry(e, kind = "aggro") {
    if (!WARCRY.enabled || !e) return;
    const colour = (e.faction || 0) % 3;
    if (this.globalCd > 0 || this.factionCd.get(colour) > 0) return;
    const chance = kind === "charge" ? WARCRY.chargeChance
      : kind === "arm" ? 1 : WARCRY.aggroChance;
    if (this.rng() >= chance) return;
    const bin = this.cache.get(colour);
    if (!bin.length) return;                       // not baked yet: this army is still quiet
    const { text, wav } = bin[(this.rng() * bin.length) | 0];
    this.globalCd = WARCRY.globalCd;
    this.factionCd.set(colour, WARCRY.factionCd);
    const { rate } = WARCRY.voices[colour];
    this.sfx.playClip(wav, e.x, e.z, WARCRY.volume, rate);
    console.info(`[warcry] colour ${colour} (${kind}): "${text}!"`);
  }
}
