// The item bar: four slots on 1–4, for things bought from vendors.
//
// It holds ITEMS ONLY. The gun, the grenade and the heal are general abilities on their own
// keys and are shown in the HUD beside the rest of your state — they are not items and do
// not belong here.
//
// A slot definition is data: {name, desc, use(), cooldown(), ready(), charges()}. Only name
// and use() are required; a slot with no cooldown() simply always reads as ready. The bar
// never owns a cooldown — it reads whatever the item's own system reports, so there is only
// ever one copy of the number.

export const SLOTS = 4;

export class Abilities {
  constructor(ctx) {
    this.ctx = ctx;
    // All four start empty. These slots are ITEMS you buy — the gun, the grenade and the
    // heal are general abilities and live on their own keys, not in here.
    this.slots = new Array(SLOTS).fill(null);
    // Everything you have ever bought. Slots hold references INTO this, so unequipping
    // something never destroys it — it goes back to the bag.
    this.owned = [];
    // Items granted by a vendor usually have no system of their own, so the bar tracks a
    // cooldown for any slot whose definition carries a plain `cd` number. Slots backed by a
    // real system (a grenade, a channel) still report their own and are never touched here.
    this.cd = new Array(SLOTS).fill(0);
  }

  /** Seconds left on a slot, from wherever that slot's truth lives. */
  cooldownOf(i) {
    const a = this.slots[i];
    if (!a) return 0;
    return a.cooldown ? a.cooldown() : this.cd[i];
  }

  readyOf(i) {
    const a = this.slots[i];
    if (!a) return false;
    if (a.ready) return a.ready();
    return this.cd[i] <= 0;
  }

  update(dt) {
    for (let i = 0; i < SLOTS; i++) if (this.cd[i] > 0) this.cd[i] -= dt;
  }

  /** Buy: remember it, and put it straight on the bar if there's room. */
  acquire(def) {
    if (!def || this.owned.some((o) => o.id === def.id)) return false;
    this.owned.push(def);
    const free = this.firstFree();
    if (free >= 0) this.slots[free] = def;
    return true;
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
    if (!this.readyOf(i)) {
      const left = this.cooldownOf(i);
      return left > 0 ? `${a.name} — ${left.toFixed(1)}s` : `${a.name} not ready`;
    }
    // Declining (returning false) must not spend the cooldown.
    if (a.use() === false) return "";
    if (typeof a.cd === "number") this.cd[i] = a.cd;
    return "";
  }
}
