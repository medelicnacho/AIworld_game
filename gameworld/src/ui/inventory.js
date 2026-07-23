// The character sheet — and the pause screen.
//
// Escape releases pointer lock, which pauses the game; rather than a bare "click to resume"
// panel, the paused moment is your WoW-style character screen. Three tabs:
//   Character — your paperdoll (equipped gear), live stats, and your bags of items
//   Spells    — the abilities you own and the four-slot bar you drag them onto
//   Talents   — the spec tree (a placeholder until it is built)
//
// Drag and click both work for everything: drag-and-drop is unreliable on trackpads and
// impossible one-handed, and an interface with only one input path excludes people for no
// reason.

import { SLOTS } from "../player/abilities.js";
import { ICONS } from "./icons.js";
import { WEAPONS } from "../config.js";

const TABS = [
  { id: "character", name: "Character" },
  { id: "spells", name: "Spells" },
  { id: "talents", name: "Talents" },
];

export class Inventory {
  constructor(el, abilities, hooks = {}) {
    this.el = el;
    this.abilities = abilities;
    this.hooks = hooks;      // { onClose, gun, charStats, equipWeapon, grantAll, setLevel, ... }
    this.open = false;
    this.admin = false;
    this.tab = "character";
    this.picked = null;      // {from: "bag"|"slot", index} — Spells tab only

    this.el.addEventListener("click", (e) => this.onClick(e));
    // Escape must leave. The lock was already released to open this, so no lockchange will
    // ever fire — it needs its own handler, in capture, exactly like the shop.
    window.addEventListener("keydown", (e) => {
      if (!this.open) return;
      if (e.code === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        this.close();
      }
    }, true);
    this.el.addEventListener("dragstart", (e) => this.onDragStart(e));
    this.el.addEventListener("dragover", (e) => {
      if (e.target.closest("[data-slot],[data-bag]")) e.preventDefault();   // allow drop
    });
    this.el.addEventListener("drop", (e) => this.onDrop(e));
  }

  show() {
    this.open = true;
    this.picked = null;
    document.body.classList.add("inv");
    this.render();
  }

  hide() {
    this.open = false;
    this.picked = null;
    document.body.classList.remove("inv");
  }

  /** Where a drag or click started: a bag entry, or one of the bar slots (Spells tab). */
  static origin(target) {
    const slot = target.closest("[data-slot]");
    if (slot) return { from: "slot", index: Number(slot.dataset.slot) };
    const bag = target.closest("[data-bag]");
    if (bag) return { from: "bag", index: Number(bag.dataset.bag) };
    return null;
  }

  onDragStart(e) {
    if (this.tab !== "spells") return;
    const o = Inventory.origin(e.target);
    if (!o) return;
    this.picked = o;
    e.dataTransfer?.setData("text/plain", `${o.from}:${o.index}`);   // Firefox needs data set
  }

  onDrop(e) {
    e.preventDefault();
    const to = Inventory.origin(e.target);
    if (to && this.picked) this.move(this.picked, to);
    this.picked = null;
    this.render();
  }

  close() {
    this.hide();
    this.hooks.onClose?.();
  }

  onClick(e) {
    // THE BACKDROP COVERS THE WHOLE SCREEN, so without this there is nothing left to click
    // to get back into the game — the panel swallowed every click and the pause was a
    // dead end.
    if (e.target === this.el) { this.close(); return; }
    if (e.target.closest("[data-close]")) { this.close(); return; }

    const tab = e.target.closest("[data-tab]");
    if (tab) { this.tab = tab.dataset.tab; this.picked = null; this.render(); return; }

    // Character tab: click an owned weapon to equip it into the Weapon slot.
    const wep = e.target.closest("[data-weapon]");
    if (wep) { this.hooks.equipWeapon?.(wep.dataset.weapon); this.render(); return; }

    if (e.target.closest("[data-admin]")) { this.admin = !this.admin; this.render(); return; }
    if (e.target.closest("[data-grant]")) { this.hooks.grantAll?.(); this.render(); return; }
    const one = e.target.closest("[data-give]");
    if (one) { this.hooks.give?.(one.dataset.give); this.render(); return; }
    const spawn = e.target.closest("[data-spawn]");
    if (spawn) { this.hooks.spawnAffix?.(spawn.dataset.spawn); this.close(); return; }
    if (e.target.closest("[data-spawnmix]")) { this.hooks.spawnAffixMix?.(); this.close(); return; }
    const breed = e.target.closest("[data-breed]");
    if (breed) { this.hooks.spawnBreed?.(breed.dataset.breed); this.close(); return; }
    if (e.target.closest("[data-setlevel]")) {
      const v = Number(this.el.querySelector("#adm-level")?.value);
      if (v > 0) this.hooks.setLevel?.(Math.floor(v));
      this.render();
      return;
    }
    if (e.target.closest("[data-setpoints]")) {
      const v = Number(this.el.querySelector("#adm-points")?.value);
      if (v >= 0) this.hooks.addPoints?.(Math.floor(v));
      this.render();
      return;
    }

    // Spells tab: click to pick up / put down an ability.
    if (this.tab !== "spells") return;
    const o = Inventory.origin(e.target);
    if (!o) return;
    if (!this.picked) {
      this.picked = o;                 // first click picks up
    } else {
      this.move(this.picked, o);       // second click puts down
      this.picked = null;
    }
    this.render();
  }

  /** Move whatever is at `from` to `to`, swapping if the destination is occupied. */
  move(from, to) {
    const a = this.abilities;
    if (from.from === "bag" && to.from === "slot") {
      const def = a.owned[from.index];
      if (!def) return;
      // equip() owns the one-ability-one-slot rule, including moving it if it is already
      // on the bar. Doing that here as well is how the two copies happened.
      a.equip(to.index, def);
    } else if (from.from === "slot" && to.from === "slot") {
      const t = a.slots[to.index];
      a.slots[to.index] = a.slots[from.index];
      a.slots[from.index] = t;
    } else if (from.from === "slot" && to.from === "bag") {
      a.slots[from.index] = null;      // dragged out of the bar: unequip
    }
  }

  cell(def, attr, i, extra = "") {
    return `
      <div class="cell ${def ? "" : "blank"} ${extra}" ${attr}="${i}" ${def ? 'draggable="true"' : ""}
           title="${def ? `${def.name} — ${def.desc || ""}` : "empty"}">
        <span class="ic">${def ? (ICONS[def.icon] || "") : ""}</span>
        <span class="nm">${def ? def.name : ""}</span>
      </div>`;
  }

  // --- CHARACTER: paperdoll + stats + bags ---------------------------------------
  characterHtml() {
    const gun = this.hooks.gun?.();
    const s = this.hooks.charStats?.() || {};

    // Equipment paperdoll. Weapon is live; the rest are placeholders waiting on the gear
    // system (GEAR.md G2), shown so the sheet reads as the real thing from day one.
    const slots = [
      { name: "Weapon", val: gun?.weapon?.name || "—", live: !!gun },
      { name: "Armor", val: "—" },
      { name: "Trinket", val: "—" },
      { name: "Boots", val: "—" },
    ];
    const doll = slots.map((sl) => `
      <div class="gslot ${sl.live ? "" : "empty"}">
        <span class="lbl">${sl.name}</span>
        <span class="val">${sl.val}</span>
      </div>`).join("");

    const row = (label, val) => `<div class="strow"><span>${label}</span><b>${val}</b></div>`;
    const stats = [
      row("Level", s.level ?? "—"),
      row("Health", `${Math.round(s.hp ?? 0)} / ${Math.round(s.maxHp ?? 0)}`),
      `<div class="sthr"></div>`,
      row("Strength", `${s.str ?? 0}  <em>+${Math.round((s.globalPct ?? 0))}% dmg</em>`),
      row("Agility", `${s.agi ?? 0}  <em>speed & dash</em>`),
      row("Stamina", `${s.stamina ?? 0}`),
      row("Armor", `${s.armor ?? 0}  <em>-${Math.round((s.armorDR ?? 0) * 100)}%</em>`),
      `<div class="sthr"></div>`,
      row("Global dmg", `+${Math.round((s.dmgGlobal ?? 0) * 100)}%`),
      row("Gun dmg", `+${Math.round((s.dmgGun ?? 0) * 100)}%`),
      row("Spell dmg", `+${Math.round((s.dmgSpell ?? 0) * 100)}%`),
      row("Grenade dmg", `+${Math.round((s.dmgGrenade ?? 0) * 100)}%`),
      `<div class="sthr"></div>`,
      row("Move speed", `×${(s.speedMult ?? 1).toFixed(2)}`),
      row("Dash", `×${(s.dashMult ?? 1).toFixed(2)}`),
    ].join("");

    // Bags. Weapons you own live here as items you can equip; found gear will join them once
    // the gear system lands.
    const weps = gun
      ? [...gun.owned].map((id) => {
        const w = WEAPONS[id];
        return `<div class="cell ${gun.weapon.id === id ? "eq" : ""}" data-weapon="${id}"
                     title="${w.name} — ${w.desc}"><span class="nm">${w.name}</span></div>`;
      }).join("")
      : "";

    // Paperdoll, stats and bags all in ONE row, so equipping from a bag and watching the
    // stat column move happen on the same screen — the whole point of a character sheet.
    return `
      <div class="char">
        <div class="paperdoll">
          <h3>Equipped</h3>
          ${doll}
        </div>
        <div class="statcol">${stats}</div>
        <div class="bagcol">
          <h3>Bags — click to equip</h3>
          <div class="bag">${weps
            || `<p class="none">Empty. Gear you find or buy drops here.</p>`}</div>
        </div>
      </div>`;
  }

  // --- SPELLS: the ability bag + bar (the old inventory, now a tab) ---------------
  spellsHtml() {
    const a = this.abilities;
    const equippedIds = new Set(a.slots.filter(Boolean).map((s) => s.id));
    const bag = a.owned.length
      ? a.owned.map((d, i) => this.cell(d, "data-bag", i, equippedIds.has(d.id) ? "eq" : "")).join("")
      : `<p class="none">Nothing yet. Adepts in the towns sell abilities.</p>`;
    const bar = Array.from({ length: SLOTS }, (_, i) =>
      this.cell(a.slots[i], "data-slot", i,
        this.picked?.from === "slot" && this.picked.index === i ? "held" : "")).join("");
    return `
      <div class="bag">${bag}</div>
      <h3>Ability bar (1–4)</h3>
      <div class="bar">${bar}</div>`;
  }

  talentsHtml() {
    return `<div class="talents">
      <p class="none">Spec tree coming soon — spend points as you level to branch your build.</p>
    </div>`;
  }

  /** A testing panel: set level, hand yourself points, grant every ability at once. */
  adminHtml() {
    if (!this.admin) return "";
    const p = this.hooks.state?.() || {};
    const owned = new Set(this.abilities.owned.map((o) => o.id));
    const list = (this.hooks.catalog?.() || []).map((g) => `
      <button class="give ${owned.has(g.grants) ? "has" : ""}" data-give="${g.id}">
        ${g.name}${owned.has(g.grants) ? " ✓" : ""}
      </button>`).join("");
    return `
      <div class="admin">
        <div class="row">
          <label>level <input id="adm-level" type="number" min="1" value="${p.level || 1}"></label>
          <button data-setlevel>set</button>
          <label>points <input id="adm-points" type="number" min="0" value="1000"></label>
          <button data-setpoints>add</button>
          <button data-grant>grant all</button>
        </div>
        <div class="row give-row">${list}</div>
        <div class="row give-row">
          <span class="lbl">spawn star pack:</span>
          ${(this.hooks.affixes?.() || []).map((a) => `
            <button class="give spawn" data-spawn="${a.id}" title="${a.desc}">${a.name}</button>`).join("")}
          <button class="give spawn" data-spawnmix>mixed</button>
          <button class="give spawn" data-breed="swarm">swarm pack</button>
          <button class="give spawn" data-breed="charger">chargers</button>
        </div>
      </div>`;
  }

  render() {
    if (!this.open) return;
    const tabs = TABS.map((t) =>
      `<button class="tab ${this.tab === t.id ? "on" : ""}" data-tab="${t.id}">${t.name}</button>`).join("");
    const body = this.tab === "character" ? this.characterHtml()
      : this.tab === "spells" ? this.spellsHtml()
        : this.talentsHtml();
    const foot = this.tab === "spells"
      ? (this.picked ? "Now click a slot to place it"
        : "Drag or click an ability onto a slot · drag it out to unequip · Esc to resume")
      : "Esc, ✕ or click outside to resume";

    this.el.innerHTML = `
      <div class="panel">
        <header>
          <h2>Character</h2>
          <button class="adm ${this.admin ? "on" : ""}" data-admin>admin</button>
          <button class="x" data-close>✕</button>
        </header>
        <nav class="tabs">${tabs}</nav>
        <div class="tabbody">${body}</div>
        ${this.adminHtml()}
        <footer>${foot}</footer>
      </div>`;
  }
}
