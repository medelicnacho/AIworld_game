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
import { VILLAGE } from "../config.js";

const PRICE_GROWTH = 1.28;      // per purchase, for repeatable upgrades

export const GOODS = {
  herbalist: [
    { id: "potion", name: "Healing Potion", price: 25, repeat: true,
      desc: `Instantly restores ${VILLAGE.potionHeal} health. Press C to drink.`,
      apply: () => { player.potions++; } },
  ],
  smith: [
    { id: "sharpen", name: "Sharpen Weapon", price: 140, upgrade: true,
      desc: "+8% damage, permanently. Stacks with every level you gain.",
      apply: () => { player.gearDmg += 0.08; } },
    { id: "lighten", name: "Lighten Armour", price: 110, upgrade: true,
      desc: "+4% movement speed, permanently.",
      apply: () => { player.gearSpeed += 0.04; } },
    { id: "quickload", name: "Quick Loader", price: 95, upgrade: true,
      desc: "-8% reload time, permanently.",
      apply: () => { player.gearReload = Math.min(0.6, player.gearReload + 0.08); } },
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
      if (id) this.buy(id);
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
    const goods = GOODS[this.vendor.role.key] || [];
    const good = goods.find((g) => g.id === id);
    if (!good) return;
    const price = priceOf(good);
    if (player.gold < price) { this.flash = "not enough gold"; this.render(); return; }
    player.gold -= price;
    good.apply(this.game);
    if (good.upgrade) {
      player.upgrades[good.id] = (player.upgrades[good.id] || 0) + 1;
      this.game.applyStats?.();     // fold the new gear into the derived stats
    }
    this.flash = `bought ${good.name}`;
    this.render();
  }

  render() {
    if (!this.vendor) return;
    const goods = GOODS[this.vendor.role.key] || [];
    const rows = goods.length ? goods.map((g) => {
      const price = priceOf(g);
      const owned = player.upgrades?.[g.id] || 0;
      const afford = player.gold >= price;
      return `
        <button class="item${afford ? "" : " poor"}" data-buy="${g.id}">
          <span class="nm">${g.name}${owned ? ` <em>×${owned}</em>` : ""}</span>
          <span class="ds">${g.desc}</span>
          <span class="pr">${price}g</span>
        </button>`;
    }).join("") : `<p class="empty">Nothing for sale. Try the herbalist or the smith.</p>`;

    this.el.innerHTML = `
      <div class="panel">
        <header>
          <h2>${this.vendor.role.name}</h2>
          <span class="gold">${player.gold}g</span>
          <button class="x" data-close>✕</button>
        </header>
        <div class="items">${rows}</div>
        <footer>${this.flash || "Click an item to buy · Esc or ✕ to leave"}</footer>
      </div>`;
    this.flash = "";
  }
}
