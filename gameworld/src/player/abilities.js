// The ability bar — a VIEW of mechanics that already exist, not an owner of them.
//
// Grenades keep their own charges and cooldown; the heal keeps its own channel and
// cooldown. This file neither duplicates nor replaces any of that: each slot names a
// mechanic, says how to fire it, and reads its live state so the bar can draw it. Change a
// cooldown in GRENADE or HEAL and the bar follows, because there is only one copy of the
// number and this isn't it.
//
// Slots 3 and 4 are empty on purpose, waiting for items bought from vendors. equip() drops
// a definition into any slot: {name, desc, use(), cooldown(), ready(), charges()}.

import { GRENADE, HEAL } from "../config.js";

export const SLOTS = 4;

export class Abilities {
  constructor(ctx) {
    this.ctx = ctx;
    this.slots = [
      {
        id: "bomb", name: "Firebomb", key: "E",
        desc: "Lobbed explosive, detonates on impact.",
        use: () => ctx.grenades.throwFrom(ctx.camera),
        cooldown: () => ctx.grenades.cooldown,
        maxCooldown: GRENADE.cooldown,
        charges: () => ctx.grenades.count,
        ready: () => ctx.grenades.ready,
      },
      {
        id: "mend", name: "Mend", key: "Q",
        desc: "Channel to heal. Breaks if you move or are hit.",
        use: () => ctx.heal.start(),
        cooldown: () => ctx.heal.cooldown,
        maxCooldown: HEAL.cooldown,
        ready: () => ctx.heal.cooldown <= 0 && !ctx.heal.casting,
      },
      null,
      null,
    ];
  }

  /** Drop a purchased ability into a slot (or the first free one with i = -1). */
  equip(i, def) {
    const at = i < 0 ? this.slots.findIndex((s) => s === null) : i;
    if (at < 0 || at >= SLOTS || !def) return false;
    this.slots[at] = def;
    return true;
  }

  firstFree() { return this.slots.findIndex((s) => s === null); }

  /** @returns {string} a line for the HUD when nothing happened. */
  use(i) {
    const a = this.slots[i];
    if (!a) return `slot ${i + 1} is empty`;
    if (a.ready && !a.ready()) {
      const left = a.cooldown?.() || 0;
      return left > 0 ? `${a.name} — ${left.toFixed(1)}s` : `${a.name} not ready`;
    }
    a.use();
    return "";
  }
}
