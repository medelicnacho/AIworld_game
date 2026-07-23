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
import { VILLAGE, FIRERING, DASH, WHIRL, RANK2, HASTE, WEAPONS, ARMOR, STAT_INFO } from "../config.js";
import { tierAt } from "../world/gen.js";
import { sellValue } from "../prog/gear.js";

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
      desc: `Instantly restores ${VILLAGE.potionHeal} health. Press C to drink.`,
      apply: () => { player.potions++; } },
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
    { id: "lighten", name: "Lighten Armour", price: 110, upgrade: true,
      desc: "+4% movement speed, permanently.",
      apply: () => { player.gearSpeed += 0.04; } },
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
    this.el.addEventListener("click", (e) => {
      const id = e.target?.closest?.("[data-buy]")?.dataset?.buy;
      if (id) { this.buy(id); return; }
      const sellId = e.target?.closest?.("[data-sell]")?.dataset?.sell;
      if (sellId) {
        const got = this.game.sellGear?.(sellId);
        this.flash = got ? `sold — +${got} pts` : "";
        this.render();
        return;
      }
      if (e.target?.closest?.("[data-sellgray]")) {
        const got = this.game.sellAllCommon?.() || 0;
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

  close() {
    if (!this.open) return;
    this.vendor = null;
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
    if (good.apply(this.game) === false) {   // no free slot, nothing bought
      player.points += price;
      this.flash = "no free ability slot";
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
