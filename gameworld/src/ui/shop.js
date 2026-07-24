// The vendor panel — click-to-buy, in the shape everyone already knows from an RPG vendor.
//
// Opening it releases pointer lock, which pauses the game (see main.js): you should never
// be shot at while reading a price list. The pause overlay is suppressed while shopping so
// the two don't fight over the screen.
//
// Goods are DATA — id, price, an apply() — so adding stock later is a line in a table
// rather than a change to any of this. Permanent upgrades get more expensive each time you
// buy them, which is what stops gold from becoming meaningless once you're farming a tier.

import { player } from "../state.js";
import { VILLAGE, FIRERING, DASH, WHIRL, RANK2, HASTE, WEAPONS, ARMOR, STAT_INFO, TIMEWARP, ORB, NOVA, CHAIN, SPRINT } from "../config.js";
import { tierAt } from "../world/gen.js";
import { sellValue } from "../prog/gear.js";
import { sfx } from "../audio/sfx.js";

const PRICE_GROWTH = 1.28;      // per purchase, for repeatable upgrades

/** A piece's stats as a readable line: "26 Armor, +3 Strength, +3% Gun Damage". */
export function statLine(stats) {
  return Object.entries(stats).map(([k, v]) => {
    const info = STAT_INFO[k];
    if (!info) return null;
    return info.kind === "pct" ? `+${Math.round(v * 100)}% ${info.label}` : `${v} ${info.label}`;
  }).filter(Boolean).join(", ");
}

// The smith's FIXED armour stock: every config piece, one buyable instance each, tier-gated.
const ARMOR_GOODS = Object.values(ARMOR).map((a) => ({
  id: `buy_${a.id}`, name: a.name, price: a.price, once: true, minTier: a.minTier || 0,
  desc: `${statLine(a.stats)}. Fills your ${a.slot} slot — replaces what's there.`,
  apply: (game) => game.equipArmor(a.id),
}));

export const GOODS = {
  herbalist: [
    { id: "potion", name: "Healing Potion", price: 25, repeat: true,
      desc: `Restores a big share of your health (more every 10 levels). Press C. `
        + `Hold up to ${VILLAGE.potionCap}.`,
      // Returning false when full makes buy() refund and refuse — no more paying for nothing.
      apply: () => {
        if (player.potions >= VILLAGE.potionCap) return false;
        player.potions++;
      } },
    { id: "grenade", name: "Firebomb", price: 45, repeat: true,
      desc: "Refills one grenade charge.",
      apply: (game) => { game.grenades.refill(1); } },
  ],
  smith: [
    { id: "w_shotgun", name: "Scattergun", price: WEAPONS.shotgun.price, once: true,
      desc: WEAPONS.shotgun.desc + " Mouse-wheel to switch weapons.",
      apply: (game) => game.gun.acquire("shotgun") },
    { id: "w_sniper", name: "Longshot", price: WEAPONS.sniper.price, once: true,
      desc: WEAPONS.sniper.desc + " Mouse-wheel to switch weapons.",
      apply: (game) => game.gun.acquire("sniper") },
    { id: "w_mg", name: "Ripper", price: WEAPONS.mg.price, once: true, minTier: 1,
      desc: WEAPONS.mg.desc + " Mouse-wheel to switch weapons.",
      apply: (game) => game.gun.acquire("mg") },
    ...ARMOR_GOODS,
    { id: "vault", name: "Vault Treads", price: 120, upgrade: true,
      desc: "Your double-tap dodge goes farther and faster. Stacks with diminishing "
        + "returns — and everything that raises your speed lengthens it too.",
      apply: () => { player.dashRank += 1; } },
    { id: "quickload", name: "Quick Loader", price: 95, upgrade: true,
      desc: "-8% reload time, permanently.",
      // Capped HERE, and this is now the only place it can be raised from: relics grant
      // by calling this very function, so a lucky drop obeys the same ceiling a purchase
      // does. Reload reaching 1.0 was what made the gun's reload vanish entirely.
      apply: () => { player.gearReload = Math.min(0.6, player.gearReload + 0.08); } },
  ],
  adept: [
    { id: "haste", name: "Haste Weave", price: HASTE.price, upgrade: true,
      desc: `+${Math.round((HASTE.fire - 1) * 100)}% fire rate, `
        + `-${Math.round((1 - HASTE.cooldown) * 100)}% grenade cooldown and a `
        + `-${Math.round((1 - HASTE.cast) * 100)}% shorter heal channel. Permanent, stacking.`,
      apply: () => { player.haste += 1; } },
    { id: "firering", name: "Ring of Fire", price: FIRERING.price, once: true,
      desc: `A wall of flame erupts outward, ${FIRERING.damage} damage to everything within `
        + `${FIRERING.radius}m. ${FIRERING.cd}s cooldown. Goes to your first free slot.`,
      apply: (game) => game.abilities.acquire({
        id: "firering",
        name: "Ring of Fire",
        icon: "burst",
        desc: "A wall of flame erupts around you.",
        cd: FIRERING.cd,
        use: () => game.fireRing(),
      }) },
    { id: "dash", name: "Dash Strike", price: DASH.price, once: true,
      desc: `Blink forward through your enemies — untouchable while you travel, `
        + `${DASH.damage} damage to anything you cut through. Narrow: only what you pass. `
        + `${DASH.cd}s cooldown.`,
      apply: (game) => game.abilities.acquire({
        id: "dash",
        name: "Dash Strike",
        icon: "arrow",
        desc: "Blink forward, untouchable, cutting through whatever you pass.",
        cd: DASH.cd,
        use: () => game.dashStrike(),
      }) },
    { id: "firering2", name: "Ring of Fire II", price: RANK2.fireringPrice, once: true,
      minTier: 1,
      desc: `The same wall of flame on a ${RANK2.fireringCd}s cooldown instead of `
        + `${FIRERING.cd}s, and anything that survives it is thrown clear. `
        + `Replaces Ring of Fire.`,
      apply: (game) => game.abilities.acquire({
        id: "firering2", name: "Ring of Fire II", icon: "burst", replaces: "firering",
        desc: `A wall of flame around you; survivors are thrown clear. `
          + `${RANK2.fireringCd}s cooldown.`,
        cd: RANK2.fireringCd,
        use: () => game.fireRing(true),
      }) },
    { id: "dash2", name: "Dash Strike II", price: RANK2.dashPrice, once: true, minTier: 1,
      desc: `Dash Strike with ${RANK2.dashCharges} charges — blink twice before you wait. `
        + `Replaces Dash Strike.`,
      apply: (game) => game.abilities.acquire({
        id: "dash2", name: "Dash Strike II", icon: "arrow", replaces: "dash",
        desc: `Blink forward, untouchable. ${RANK2.dashCharges} charges.`,
        cd: DASH.cd, maxCharges: RANK2.dashCharges,
        use: () => game.dashStrike(),
      }) },
    { id: "whirl", name: "Whirlwind", price: WHIRL.price, once: true, minTier: WHIRL.minTier,
      desc: `Leap forward and land for ${WHIRL.slamDamage} damage, then spin for `
        + `${WHIRL.spinTime}s — untouchable, faster, and shredding everything around you. `
        + `${WHIRL.cd}s cooldown.`,
      apply: (game) => game.abilities.acquire({
        id: "whirl",
        name: "Whirlwind",
        icon: "spiral",
        desc: "Leap, slam, then spin through whatever is left.",
        cd: WHIRL.cd,
        use: () => game.whirlwind(),
      }) },
    { id: "orb", name: "Cataclysm Orb", price: ORB.price, once: true,
      desc: `Lob a burning orb: ${ORB.burstDamage} on impact, then a pool doing heavy `
        + `damage over ${ORB.poolLife}s. ${ORB.cd}s cooldown.`,
      apply: (game) => game.abilities.acquire({
        id: "orb", name: "Cataclysm Orb", icon: "orb",
        desc: "A burning pool that eats anything standing in it.",
        cd: ORB.cd, use: () => game.cataclysmOrb(1),
      }) },
    { id: "orb2", name: "Cataclysm Orb II", price: Math.round(ORB.price * 1.4), once: true, minTier: 1,
      desc: "The pool now SLOWS anything caught in it. Replaces Cataclysm Orb.",
      apply: (game) => game.abilities.acquire({
        id: "orb2", name: "Cataclysm Orb II", icon: "orb", replaces: "orb",
        desc: "Burning pool that slows.", cd: ORB.cd, use: () => game.cataclysmOrb(2),
      }) },
    { id: "orb3", name: "Cataclysm Orb III", price: Math.round(ORB.price * 2), once: true, minTier: 3,
      desc: "The pool ROOTS anything caught in it. Replaces Cataclysm Orb II.",
      apply: (game) => game.abilities.acquire({
        id: "orb3", name: "Cataclysm Orb III", icon: "orb", replaces: "orb2",
        desc: "Burning pool that roots.", cd: ORB.cd, use: () => game.cataclysmOrb(3),
      }) },
    { id: "nova", name: "Frost Nova", price: NOVA.price, once: true,
      desc: `A ring of frost: ${NOVA.damage} damage and a hard slow to everything within `
        + `${NOVA.radius}m. ${NOVA.cd}s cooldown.`,
      apply: (game) => game.abilities.acquire({
        id: "nova", name: "Frost Nova", icon: "frost",
        desc: "Damages and slows everything around you.", cd: NOVA.cd, use: () => game.frostNova(1),
      }) },
    { id: "nova2", name: "Frost Nova II", price: Math.round(NOVA.price * 1.5), once: true, minTier: 2,
      desc: "The nova now ROOTS instead of slowing. Replaces Frost Nova.",
      apply: (game) => game.abilities.acquire({
        id: "nova2", name: "Frost Nova II", icon: "frost", replaces: "nova",
        desc: "Damages and roots everything around you.", cd: NOVA.cd, use: () => game.frostNova(2),
      }) },
    { id: "chain", name: "Chain Lightning", price: CHAIN.price, once: true, minTier: 1,
      desc: `A bolt that leaps between up to ${CHAIN.jumps} enemies, ${CHAIN.damage} damage `
        + `falling each jump. ${CHAIN.cd}s cooldown.`,
      apply: (game) => game.abilities.acquire({
        id: "chain", name: "Chain Lightning", icon: "bolt",
        desc: "Arcs from foe to foe.", cd: CHAIN.cd, use: () => game.chainLightning(),
      }) },
    { id: "sprint", name: "Sprint", price: SPRINT.price, once: true,
      desc: `Burst to ${Math.round((SPRINT.mult - 1) * 100)}% faster for ${SPRINT.dur}s. `
        + `${SPRINT.cd}s cooldown.`,
      apply: (game) => game.abilities.acquire({
        id: "sprint", name: "Sprint", icon: "boots",
        desc: "A burst of movement speed.", cd: SPRINT.cd, use: () => game.sprint(),
      }) },
    { id: "timewarp", name: "Timewarp", price: TIMEWARP.price, once: true, minTier: 1,
      desc: `Mark this spot and your health. After ${TIMEWARP.window}s (or press again) you `
        + `SNAP back to it with every cooldown reset. ${TIMEWARP.cd}s cooldown.`,
      apply: (game) => game.abilities.acquire({
        id: "timewarp", name: "Timewarp", icon: "clock",
        desc: "Rewind to where and how you were; all cooldowns reset.",
        ready: () => game.timewarpReady(), cooldown: () => game.timewarpCd(),
        use: () => game.timewarp(),
      }) },
  ],
  keeper: [],
};

/** What a repeatable upgrade costs right now, given how many you already own. */
export function priceOf(good) {
  const bought = player.upgrades?.[good.id] || 0;
  return good.upgrade ? Math.round(good.price * Math.pow(PRICE_GROWTH, bought)) : good.price;
}

export class Shop {
  constructor(el, game) {
    this.el = el;
    this.game = game;         // { grenades, applyStats, onClose }
    this.vendor = null;
    this.shift = false;
    this._hoverEl = null;
    // Same compare tooltip as the character sheet: hover a piece for its stats, hold Shift to
    // see the +/- against what you're wearing. .geartip is a global class, shared styling.
    this.tip = document.createElement("div");
    this.tip.className = "geartip";
    this.tip.style.display = "none";
    document.body.appendChild(this.tip);
    this.el.addEventListener("mousemove", (e) => this.onHover(e));
    this.el.addEventListener("mouseleave", () => this.hideTip());
    window.addEventListener("keydown", (e) => { if (e.key === "Shift" && !this.shift) { this.shift = true; this.refreshTip(); } });
    window.addEventListener("keyup", (e) => { if (e.key === "Shift") { this.shift = false; this.refreshTip(); } });
    this.el.addEventListener("click", (e) => {
      const id = e.target?.closest?.("[data-buy]")?.dataset?.buy;
      if (id) { this.buy(id); return; }
      const sellId = e.target?.closest?.("[data-sell]")?.dataset?.sell;
      if (sellId) {
        const got = this.game.sellGear?.(sellId);
        if (got) sfx.sell();
        this.flash = got ? `sold — +${got} pts` : "";
        this.render();
        return;
      }
      if (e.target?.closest?.("[data-sellgray]")) {
        const got = this.game.sellAllCommon?.() || 0;
        if (got) sfx.sell();
        this.flash = got ? `sold all gray — +${got} pts` : "no gray to sell";
        this.render();
        return;
      }
      if (e.target?.closest?.("[data-close]")) this.close();
      // Clicking the backdrop leaves, the way every panel like this behaves.
      if (e.target === this.el) this.close();
    });
    // Escape can't come through the pointer-lock path — opening the shop already released
    // the lock, so no lockchange will ever fire. It needs its own handler, and it must run
    // BEFORE anything else can treat Escape as "pause the game", hence capture: true.
    window.addEventListener("keydown", (e) => {
      if (!this.open) return;
      if (e.code === "Escape" || e.code === "KeyF") {
        e.preventDefault();
        e.stopPropagation();
        this.close();
      }
    }, true);
  }

  get open() { return this.vendor !== null; }

  show(vendor) {
    if (!vendor) return;
    this.vendor = vendor;
    document.body.classList.add("shopping");
    this.render();
    if (document.pointerLockElement) document.exitPointerLock();
  }

  // --- the compare tooltip (mirrors inventory.js) -------------------------------
  fmt(k, v, signed) {
    const info = STAT_INFO[k];
    const s = signed && v > 0 ? "+" : "";
    if (info?.kind === "pct") return `${s}${Math.round(v * 100)}%`;
    return `${s}${v}`;
  }

  statRows(stats) {
    return Object.entries(stats).map(([k, v]) => {
      const info = STAT_INFO[k];
      return info ? `<div><span>${info.label}</span><b>${this.fmt(k, v, false)}</b></div>` : "";
    }).join("");
  }

  deltaRows(next, cur) {
    const keys = new Set([...Object.keys(next), ...Object.keys(cur)]);
    return [...keys].map((k) => {
      const info = STAT_INFO[k];
      if (!info) return "";
      const d = (next[k] || 0) - (cur[k] || 0);
      if (Math.abs(d) < 1e-9) return "";
      return `<div><span>${info.label}</span><b class="${d > 0 ? "up" : "down"}">${this.fmt(k, d, true)}</b></div>`;
    }).join("");
  }

  /** The piece a hovered row refers to — an armour ware, or a bag piece being sold. */
  pieceFromTarget(el) {
    const buyId = el.closest("[data-buy]")?.dataset.buy;
    if (buyId?.startsWith("buy_")) {
      const cfg = ARMOR[buyId.slice(4)];
      return cfg ? { slot: cfg.slot, name: cfg.name, stats: cfg.stats, color: "#5fd66a" } : null;
    }
    const sellUid = el.closest("[data-sell]")?.dataset.sell;
    if (sellUid) return (player.ownedGear || []).find((p) => p.uid === sellUid) || null;
    return null;
  }

  buildTip(el) {
    const piece = this.pieceFromTarget(el);
    if (!piece) return "";
    const equipped = player.gearSlots?.[piece.slot];
    const worn = equipped && equipped.uid === piece.uid;
    let html = `<div class="tt-name" style="color:${piece.color || "#dfe8f5"}">${piece.name}</div>`;
    html += `<div class="tt-slot">${piece.slot}${worn ? " · equipped" : ""}</div>`;
    html += `<div class="tt-stats">${this.statRows(piece.stats)}</div>`;
    if (this.shift && equipped && !worn) {
      html += `<div class="tt-cmp">vs equipped — ${equipped.name}</div>`;
      const d = this.deltaRows(piece.stats, equipped.stats);
      html += `<div class="tt-stats">${d || '<div class="tt-hint">identical stats</div>'}</div>`;
    } else if (!worn) {
      html += `<div class="tt-hint">${equipped ? "hold Shift to compare" : (this.shift ? "that slot is empty" : "hold Shift to compare")}</div>`;
    }
    return html;
  }

  onHover(e) {
    if (!this.open) return;
    const target = e.target.closest?.("[data-buy],[data-sell]");
    if (!target) { this.hideTip(); return; }
    this._hoverEl = target;
    const html = this.buildTip(target);
    if (!html) { this.hideTip(); return; }
    this.tip.innerHTML = html;
    this.tip.style.display = "block";
    this.tip.style.left = `${Math.min(e.clientX + 16, innerWidth - 270)}px`;
    this.tip.style.top = `${Math.min(e.clientY + 12, innerHeight - this.tip.offsetHeight - 12)}px`;
  }

  refreshTip() {
    if (!this.open || !this._hoverEl || this.tip.style.display === "none") return;
    const html = this.buildTip(this._hoverEl);
    if (html) this.tip.innerHTML = html;
  }

  hideTip() { this.tip.style.display = "none"; this._hoverEl = null; }

  close() {
    if (!this.open) return;
    this.vendor = null;
    this.hideTip();
    document.body.classList.remove("shopping");
    this.el.innerHTML = "";
    // Every exit takes the same path — X, backdrop and Escape are one behaviour, not three.
    // A keydown counts as user activation, so re-locking from Escape is allowed; if the
    // browser refuses anyway, the ordinary pause overlay is there and one click resumes.
    this.game.onClose?.();
  }

  buy(id) {
    const tier = tierAt(this.vendor.s.x, this.vendor.s.z);
    const goods = (GOODS[this.vendor.role.key] || []).filter((g) => (g.minTier || 0) <= tier);
    const good = goods.find((g) => g.id === id);
    if (!good) return;
    const price = priceOf(good);
    if (player.points < price) { this.flash = "not enough points"; this.render(); return; }
    player.points -= price;
    if (good.apply(this.game) === false) {   // couldn't complete — refund
      player.points += price;
      this.flash = good.id === "potion" ? `potions full (${VILLAGE.potionCap})` : "no free ability slot";
      this.render();
      return;
    }
    if (good.upgrade || good.once) {
      player.upgrades[good.id] = (player.upgrades[good.id] || 0) + 1;
      this.game.applyStats?.();     // fold the new gear into the derived stats
    }
    this.flash = `bought ${good.name}`;
    this.render();
  }

  render() {
    if (!this.vendor) return;
    // Stock depends on WHERE the vendor is. Deeper settlements carry the deeper wares, so
    // pushing outward buys you access as well as points.
    const tier = tierAt(this.vendor.s.x, this.vendor.s.z);
    const all = GOODS[this.vendor.role.key] || [];
    const goods = all.filter((g) => (g.minTier || 0) <= tier);
    const locked = all.length - goods.length;
    const rows = goods.length ? goods.map((g) => {
      const price = priceOf(g);
      const owned = player.upgrades?.[g.id] || 0;
      const afford = player.points >= price;
      if (g.once && owned) return `
        <button class="item poor" disabled>
          <span class="nm">${g.name} <em>owned</em></span>
          <span class="ds">${g.desc}</span>
        </button>`;
      return `
        <button class="item${afford ? "" : " poor"}" data-buy="${g.id}">
          <span class="nm">${g.name}${owned ? ` <em>×${owned}</em>` : ""}</span>
          <span class="ds">${g.desc}</span>
          <span class="pr">${price}</span>
        </button>`;
    }).join("") : `<p class="empty">Nothing for sale. Try the herbalist or the smith.</p>`;

    // The SELL side: your bags. Click a piece to sell it for points; one button dumps all the
    // grey clutter at once. Worn pieces aren't here (the bag holds only what you aren't using).
    const bag = player.ownedGear || [];
    const grayCount = bag.filter((p) => p.rarity === "common").length;
    const sellRows = bag.length ? bag.map((p) => `
      <button class="sellitem" data-sell="${p.uid}" style="border-color:${p.color}"
              title="${statLine(p.stats)}">
        <span class="nm" style="color:${p.color}">${p.name}</span>
        <span class="pr">+${sellValue(p)}</span>
      </button>`).join("") : `<p class="empty">Your bags are empty.</p>`;

    this.el.innerHTML = `
      <div class="panel wide">
        <header>
          <h2>${this.vendor.role.name}</h2>
          <span class="gold">${player.points} pts</span>
          <button class="x" data-close>✕</button>
        </header>
        <div class="cols">
          <div class="col">
            <h3>For sale</h3>
            <div class="items">${rows}</div>
          </div>
          <div class="col sellcol">
            <h3>Your bags — click to sell</h3>
            <button class="sellall ${grayCount ? "" : "off"}" data-sellgray>
              Sell all gray${grayCount ? ` (${grayCount})` : ""}
            </button>
            <div class="items sellitems">${sellRows}</div>
          </div>
        </div>
        <footer>${this.flash
          || (locked ? `${locked} more ware${locked > 1 ? "s" : ""} sold further out`
            : "Click to buy · click a bag piece to sell · Esc or ✕ to leave")}</footer>
      </div>`;
    this.flash = "";
  }
}
