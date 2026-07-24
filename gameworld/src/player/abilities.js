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

// The spell bar keys, in order. More than the old four so there's room to SET more spells;
// keys chosen to avoid the load-bearing ones (R reload, F trade). The bar and the controller
// both read this, so adding a key here is the only change needed.
export const SLOT_KEYS = ["1", "2", "3", "4", "5", "6", "T", "Tab"];
export const SLOTS = SLOT_KEYS.length;

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
    // Cooldowns and charges are keyed by ABILITY ID, not by slot index. Keying by slot
    // meant dragging an ability to a different bar position gave it a fresh cooldown, and
    // an ability sitting in two slots ran two independent timers. By id, an ability has one
    // cooldown wherever it happens to sit — and cannot be duplicated into two of them.
    this.state = new Map();   // id -> { cd, ch, def }
  }

  /** The live cooldown/charge record for an ability, created on first sight. */
  stateOf(def) {
    if (!def) return null;
    let st = this.state.get(def.id);
    if (!st) {
      st = { cd: 0, ch: def.maxCharges || 1, def };
      this.state.set(def.id, st);
    }
    st.def = def;
    return st;
  }

  maxChargesOf(i) { return this.slots[i]?.maxCharges || 1; }

  /** Charges to display, from wherever that slot's truth lives. */
  chargesOf(i) {
    const a = this.slots[i];
    if (!a) return null;
    if (a.charges) return a.charges();              // backed by its own system
    return (a.maxCharges || 1) > 1 ? this.stateOf(a).ch : null;
  }

  /** Seconds left on a slot, from wherever that slot's truth lives. */
  cooldownOf(i) {
    const a = this.slots[i];
    if (!a) return 0;
    return a.cooldown ? a.cooldown() : this.stateOf(a).cd;
  }

  readyOf(i) {
    const a = this.slots[i];
    if (!a) return false;
    if (a.ready) return a.ready();
    const st = this.stateOf(a);
    if ((a.maxCharges || 1) > 1) return st.ch > 0;
    return st.cd <= 0;
  }

  update(dt) {
    // Every ability you own ticks, equipped or not — an ability does not stop recovering
    // because you dragged it off the bar for a moment.
    for (const st of this.state.values()) {
      if (st.cd <= 0) continue;
      st.cd -= dt;
      if (st.cd > 0) continue;
      const max = st.def?.maxCharges || 1;
      if (max > 1 && st.ch < max) {
        st.ch++;
        // Still short of full? Start the next charge immediately rather than waiting for
        // a use — otherwise a half-empty ability would sit there never refilling.
        if (st.ch < max) st.cd = st.def.cd;
      }
    }
  }

  /** Buy: remember it, and put it straight on the bar if there's room. */
  acquire(def) {
    if (!def || this.owned.some((o) => o.id === def.id)) return false;

    // An upgrade takes the place of what it upgrades, in the bag AND on the bar. Leaving
    // rank 1 lying around next to rank 2 is clutter that can only ever be a mistake.
    let placed = false;
    if (def.replaces) {
      const at = this.owned.findIndex((o) => o.id === def.replaces);
      if (at >= 0) this.owned.splice(at, 1);
      this.state.delete(def.replaces);          // the old rank's timer goes with it
      for (let i = 0; i < SLOTS; i++) {
        if (this.slots[i]?.id === def.replaces) { this.slots[i] = def; placed = true; }
      }
    }

    this.owned.push(def);
    // Only reach for a free slot if the upgrade did not already take its predecessor's
    // place. Doing both is what put rank 1 and rank 2 on the bar at once, each running its
    // own cooldown.
    if (!placed) {
      const free = this.firstFree();
      if (free >= 0) this.equip(free, def);
    }
    return true;
  }

  /**
   * Drop an ability into a slot (or the first free one with i = -1). An ability can only
   * be in ONE slot: if it is already on the bar it MOVES rather than appearing twice.
   */
  equip(i, def) {
    const at = i < 0 ? this.slots.findIndex((s) => s === null) : i;
    if (at < 0 || at >= SLOTS || !def) return false;
    const already = this.slots.findIndex((s) => s && s.id === def.id);
    const displaced = this.slots[at];
    this.slots[at] = def;
    if (already >= 0 && already !== at) this.slots[already] = displaced || null;
    this.stateOf(def);      // make sure it has a timer record; never resets an existing one
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
    const st = this.stateOf(a);
    const max = a.maxCharges || 1;
    if (max > 1) {
      st.ch--;
      if (st.cd <= 0) st.cd = a.cd;   // don't restart a recharge already running
    } else if (typeof a.cd === "number") {
      st.cd = a.cd;
    }
    return "";
  }
}
