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
import { VILLAGE, FIRERING, DASH, WHIRL, RANK2, WEAPONS, ARMOR, STAT_INFO, TIMEWARP, ORB, NOVA, CHAIN, SPRINT } from "../config.js";
import { tierAt } from "../world/gen.js";
import { sellValue, sortBag } from "../prog/gear.js";
import { factionById, repProgress, stockFor, lockedFor, REP_TIERS, repForTurnIn, join, JOIN_LEVEL, FACTION_WEAPON }
  from "../prog/factions.js";
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
    // REMOVED: "Quick Loader", the stacking -8% reload passive. Same story as Haste Weave at
    // the Adept — gear rolls a Reload rating that does the identical job on a proper curve, so
    // this was the second half of one job being done twice. Both were bought once, forgotten,
    // and changed nothing about how the gun was actually used.
    //
    // As with haste, the machinery survives: player.gearReload simply stays at zero now, which
    // collapses its term to 1 and leaves the gear rating deciding reload speed on its own.
  ],
  // REMOVED: "Haste Weave", the stacking passive that used to sit at the top of this list.
  // Gear rolls a Haste rating that does the same job on a proper diminishing curve, so the
  // two were one job done twice — and of everything the Adept sells it was the only thing
  // that changed no decision. You bought it, your numbers moved, and you played identically.
  // A shop should sell you new verbs, not bigger adjectives.
  //
  // The haste MACHINERY stays alive and untouched: player.haste simply never leaves zero now,
  // which collapses its term to 1 and leaves the gear rating driving fire rate, cooldowns and
  // the heal channel exactly as before.
  adept: [
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
      const joinId = e.target?.closest?.("[data-join]")?.dataset?.join;
      if (joinId) {
        if (join(joinId)) { sfx.levelUp(); this.flash = `you ride with ${factionById(joinId).name}`; }
        this.render();
        return;
      }
      // Switching sides is a two-press confirm: first click arms it (the button re-labels to
      // name what you would lose), second click does it.
      const switchId = e.target?.closest?.("[data-switch]")?.dataset?.switch;
      if (switchId) {
        if (this.confirmSwitch !== switchId) { this.confirmSwitch = switchId; this.render(); return; }
        this.confirmSwitch = null;
        if (join(switchId)) { sfx.levelUp(); this.flash = `you ride with ${factionById(switchId).name} now`; }
        this.render();
        return;
      }
      // Any OTHER click in the panel disarms a pending switch — you must mean it in one go,
      // not leave a loaded button waiting for the next stray press.
      if (this.confirmSwitch) { this.confirmSwitch = null; this.render(); return; }
      const facId = e.target?.closest?.("[data-buyfac]")?.dataset?.buyfac;
      if (facId) { this.buyFaction(facId); return; }
      const wepId = e.target?.closest?.("[data-buyweapon]")?.dataset?.buyweapon;
      if (wepId) {
        const wd = WEAPONS[wepId];
        if (wd && player.points >= wd.price && !this.game.gun.owned.has(wepId)) {
          player.points -= wd.price;
          this.game.gun.acquire(wepId);       // buys AND equips, like the smith's guns
          sfx.levelUp();
          this.flash = `${wd.name} — yours`;
        } else if (wd) {
          this.flash = "not enough points";
        }
        this.render();
        return;
      }
      const turnUid = e.target?.closest?.("[data-turnin]")?.dataset?.turnin;
      if (turnUid) {
        const got = this.game.turnIn?.(turnUid) || 0;
        if (got) sfx.sell();
        this.flash = got ? `handed in — +${got} standing` : "";
        this.render();
        return;
      }
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
    this.confirmSwitch = null;      // an armed switch must never survive to the next visit
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

  /** The piece a hovered row refers to — an armour ware, a bag piece, or faction kit. */
  pieceFromTarget(el) {
    const buyId = el.closest("[data-buy]")?.dataset.buy;
    if (buyId?.startsWith("buy_")) {
      const cfg = ARMOR[buyId.slice(4)];
      return cfg ? { slot: cfg.slot, name: cfg.name, stats: cfg.stats, color: "#5fd66a" } : null;
    }
    // Faction kit at the quartermaster — the same compare, so you can weigh a piece against
    // what you're wearing BEFORE you spend hard-won points on it, not after.
    const facId = el.closest("[data-buyfac]")?.dataset.buyfac;
    if (facId) {
      const p = stockFor(player.faction, player.rep || 0).find((x) => x.id === facId);
      return p ? { slot: p.slot, name: p.name, stats: p.stats, color: factionById(p.faction)?.color } : null;
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
    html += `<div class="tt-slot">${piece.slot}`
      + `${piece.tier === undefined ? "" : ` · tier ${piece.tier}`}${worn ? " · equipped" : ""}</div>`;
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
    const target = e.target.closest?.("[data-buy],[data-sell],[data-buyfac]");
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

  /**
   * THE QUARTERMASTER. A different panel from the ordinary vendor, because they answer a
   * different question — not "what do you want to buy" but "whose side are you on".
   *
   * Three states, and each one is a different screen:
   *   unaligned      an offer to join, and what joining would mean
   *   this is yours  the ladder, the stock you have earned, and the turn-in desk
   *   a rival's      a refusal. Cold, not hostile: you are standing safely in their town and
   *                  they simply will not deal with you. That refusal IS the cost of having
   *                  chosen, so it should be plain rather than hidden behind an empty list.
   */
  quartermasterHtml(fid) {
    const f = factionById(fid);
    const mine = player.faction;
    const rep = player.rep || 0;

    if (!mine && player.level < JOIN_LEVEL) {
      return `
        <div class="qm">
          <p class="qmlead" style="color:${f.color}">${f.name} does not know you yet.</p>
          <p class="qmblurb">${f.blurb}</p>
          <p class="qmnote">Come back at <b>level ${JOIN_LEVEL}</b>. Choosing a side is the
            first thing in this world you cannot undo cheaply, and it is worth understanding
            what you are choosing between first.</p>
        </div>`;
    }

    if (!mine) {
      return `
        <div class="qm">
          <p class="qmlead" style="color:${f.color}">${f.name} will take you in.</p>
          <p class="qmblurb">${f.blurb}</p>
          <p class="qmnote">Their quarrel is with one of the three warring camps out there.
            Once you join, <b>only that colour earns you standing</b> — you will start reading
            camps before you fight them.</p>
          <p class="qmnote">Their kit unlocks as you climb, and every piece still has to be
            paid for. You may join one of the three. The other two will stay safe ground and
            keep their gear to themselves.</p>
          <button class="join" data-join="${f.id}" style="border-color:${f.color}">
            Join ${f.name}
          </button>
        </div>`;
    }

    if (mine !== fid) {
      const own = factionById(mine);
      const ownPr = repProgress(rep);
      // TWO PRESSES, and the button changes its words on the first — the same guard the Start
      // Over button uses. Abandoning a faction throws away every hour of standing you have
      // earned, so it must not be a thing muscle memory can do; a button that suddenly reads
      // "give up X standing?" cannot be double-clicked through the way one that keeps its
      // label can. What you would LOSE is named on the confirm, not buried in a note.
      const swap = this.confirmSwitch === fid
        ? `<button class="join go" data-switch="${f.id}" style="border-color:${f.color}">
             Abandon ${own?.name || "your faction"}? — lose ${ownPr.name} · ${rep} standing
           </button>`
        : `<button class="join" data-switch="${f.id}" style="border-color:${f.color}">
             Swear to ${f.name} instead
           </button>`;
      return `
        <div class="qm">
          <p class="qmlead" style="color:${f.color}">${f.name} has nothing for you — yet.</p>
          <p class="qmblurb">You wear ${own?.name || "another"}'s colours. You are welcome to
            rest here and buy what any traveller can — but their kit is not for sale to you.</p>
          <p class="qmnote">Change sides and you keep every item you own, but your standing
            with ${own?.name || "your faction"} — <b>${ownPr.name}, ${rep}</b> — is gone, and
            you begin ${f.name}'s ladder at the bottom.</p>
          ${swap}
        </div>`;
    }

    const pr = repProgress(rep);
    const stock = stockFor(fid, rep);
    const locked = lockedFor(fid, rep);
    const bar = Math.round(pr.frac * 24);

    const row = (p, buyable) => `
      <button class="item${buyable ? (player.points >= p.price ? "" : " poor") : " locked"}"
              ${buyable ? `data-buyfac="${p.id}"` : "disabled"}>
        <span class="nm" style="color:${buyable ? "#ffc03a" : "#7d8798"}">${p.name}</span>
        <span class="ds">${statLine(p.stats)}</span>
        <span class="pr">${buyable ? p.price : REP_TIERS[p.repTier].name}</span>
      </button>`;

    // THE WEAPON, first in the list. It is what the faction IS — the piece of kit that
    // changes how you fight rather than what your numbers say — so it leads the stock.
    const wid = FACTION_WEAPON[fid];
    const wdef = WEAPONS[wid];
    const wOwned = this.game.gun?.owned?.has(wid);
    const weaponRow = wdef ? (wOwned
      ? `<button class="item poor" disabled>
           <span class="nm">${wdef.name} <em>owned</em></span>
           <span class="ds">${wdef.desc}</span>
         </button>`
      : `<button class="item${player.points >= wdef.price ? "" : " poor"}" data-buyweapon="${wid}">
           <span class="nm legendary" style="color:${wdef.color || f.color}">★ ${wdef.name}</span>
           <span class="ds">${wdef.desc}</span>
           <span class="pr">${wdef.price}</span>
         </button>`) : "";

    return `
      <div class="qm">
        <div class="repbar">
          <span class="reptier" style="color:${f.color}">${pr.name}</span>
          <span class="reptrack">${"█".repeat(bar)}${"░".repeat(24 - bar)}</span>
          <span class="repnum">${pr.need ? `${rep} / ${pr.need} → ${pr.nextName}` : `${rep} · highest`}</span>
        </div>
        <div class="items">${weaponRow}${stock.map((p) => row(p, true)).join("")}</div>
        ${locked.length ? `<h3>Earned at ${REP_TIERS[locked[0].repTier].name}</h3>
          <div class="items">${locked.map((p) => row(p, false)).join("")}</div>` : ""}
      </div>`;
  }

  /**
   * Buy a piece of faction kit. Reputation decided you were ALLOWED to; points are the price,
   * and it is heavy. Neither can stand in for the other — that pairing is the whole reason
   * points mean anything again.
   */
  buyFaction(id) {
    const p = stockFor(player.faction, player.rep || 0).find((x) => x.id === id);
    if (!p) return;
    if (player.points < p.price) { this.flash = "not enough points"; this.render(); return; }
    player.points -= p.price;
    this.game.giveFactionGear?.(p);
    this.flash = `bought ${p.name}`;
    this.render();
  }

  render() {
    if (!this.vendor) return;
    // A quartermaster gets their own panel entirely — see quartermasterHtml.
    const fid = this.vendor.role.faction;
    if (fid) {
      const bag = sortBag(player.ownedGear);
      const mine = player.faction === fid;
      // The TURN-IN desk. Your bag fills with pieces you will never wear, and selling them
      // gives points that stop mattering the moment you have enough. Handing them to your own
      // faction turns dead weight into progress instead — which is also why a drop is never
      // wasted, even when it is worse than what you have on.
      const turnRows = mine && bag.length
        ? bag.map((p) => {
          const worth = repForTurnIn(p);
          return `
            <button class="sellitem ${worth ? "" : "off"}" ${worth ? `data-turnin="${p.uid}"` : "disabled"}
                    style="border-color:${p.color}" title="${statLine(p.stats)}">
              <span class="nm" style="color:${p.color}">${p.name}</span>
              <span class="tr">T${p.tier ?? 0}</span>
              <span class="pr">${worth ? `+${worth}` : "—"}</span>
            </button>`;
        }).join("")
        : `<p class="empty">${mine ? "Nothing to hand in." : ""}</p>`;

      this.el.innerHTML = `
        <div class="panel wide">
          <header>
            <h2>${this.vendor.role.name}</h2>
            <span class="gold">${player.points} pts</span>
            <button class="x" data-close>✕</button>
          </header>
          <div class="cols">
            <div class="col">${this.quartermasterHtml(fid)}</div>
            ${mine ? `<div class="col sellcol">
              <h3>Hand in for standing</h3>
              <div class="items sellitems">${turnRows}</div>
            </div>` : ""}
          </div>
          <footer>${this.flash || "Esc or ✕ to leave"}</footer>
        </div>`;
      this.flash = "";
      return;
    }
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
    // The SAME order as the character sheet — this is the same bag, and two views of one
    // thing that disagree about what is best is worse than either ordering on its own.
    const bag = sortBag(player.ownedGear);
    const grayCount = bag.filter((p) => p.rarity === "common").length;
    const sellRows = bag.length ? bag.map((p) => `
      <button class="sellitem" data-sell="${p.uid}" style="border-color:${p.color}"
              title="${statLine(p.stats)}">
        <span class="nm" style="color:${p.color}">${p.name}</span>
        <span class="tr">T${p.tier ?? 0}</span>
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
