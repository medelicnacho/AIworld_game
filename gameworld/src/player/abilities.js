// The ability bar: four slots on 1–4.
//
// SCOPE, deliberately: this is the FRAME, not the content. Every slot starts empty and
// nothing is equipped by default — abilities arrive as things you buy from a vendor, so
// what fills these belongs in the shop's goods table, not here.
//
// An ability is data: {id, name, cd, run(ctx)}. `run` returning false means it declined
// (already channelling, no projectile free), and a declined ability does NOT spend its
// cooldown — a cooldown burned on a no-op reads as a bug.
//
// LIBRARY holds implementations that are ready to be attached to an item whenever you want
// one; none of them is reachable until something calls equip().

import { player } from "../state.js";

export const SLOTS = 4;

export const LIBRARY = {
  bomb: {
    id: "bomb", name: "Firebomb", cd: 5,
    desc: "Lobbed explosive, detonates on impact.",
    run: (ctx) => ctx.grenades.throwFrom(ctx.camera),
  },
  mend: {
    id: "mend", name: "Mend", cd: 12,
    desc: "Channel to heal. Breaks if you move or are hit.",
    run: (ctx) => ctx.heal.start(),
  },
};

export class Abilities {
  constructor(ctx) {
    this.ctx = ctx;
    this.slots = new Array(SLOTS).fill(null);
    this.cd = new Array(SLOTS).fill(0);
  }

  /** Put an ability (by LIBRARY id, or a definition object) into a slot. */
  equip(i, ability) {
    const def = typeof ability === "string" ? LIBRARY[ability] : ability;
    if (i < 0 || i >= SLOTS || !def) return false;
    this.slots[i] = def;
    this.cd[i] = 0;
    return true;
  }

  /** The first free slot, or -1 — what a purchased ability will want. */
  firstFree() {
    return this.slots.findIndex((s) => s === null);
  }

  /** @returns {string} a line for the HUD when nothing happened. */
  use(i) {
    const a = this.slots[i];
    if (!a) return `slot ${i + 1} is empty`;
    if (this.cd[i] > 0) return `${a.name} — ${this.cd[i].toFixed(1)}s`;
    if (a.run(this.ctx) === false) return "";
    this.cd[i] = a.cd;
    return "";
  }

  update(dt) {
    for (let i = 0; i < SLOTS; i++) if (this.cd[i] > 0) this.cd[i] -= dt;
    if (player.surgeT > 0) player.surgeT -= dt;
  }
}
