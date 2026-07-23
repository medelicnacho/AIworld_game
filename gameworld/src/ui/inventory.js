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
import { WEAPONS, STAT_INFO } from "../config.js";
import { statLine } from "./shop.js";

const SLOT_LABEL = { helm: "Helm", shoulders: "Shoulders", vest: "Vest", pants: "Legs", boots: "Boots" };

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
    this.hoverUid = null;    // gear cell under the cursor, for the compare tooltip
    this.shift = false;

    // A floating tooltip that lives OUTSIDE the panel's innerHTML, so a re-render can't wipe
    // it. Shows a hovered piece's stats, and — with Shift held — the +/- against what you wear.
    this.tip = document.createElement("div");
    this.tip.className = "geartip";
    this.tip.style.display = "none";
    document.body.appendChild(this.tip);

    this.el.addEventListener("click", (e) => this.onClick(e));
    this.el.addEventListener("mousemove", (e) => this.onHover(e));
    this.el.addEventListener("mouseleave", () => this.hideTip());
    this.el.addEventListener("contextmenu", (e) => this.onDrop2(e));  // right-click drops it
    // Shift toggles the comparison while the cursor sits still on a piece.
    window.addEventListener("keydown", (e) => { if (e.key === "Shift" && !this.shift) { this.shift = true; this.refreshTip(); } });
    window.addEventListener("keyup", (e) => { if (e.key === "Shift") { this.shift = false; this.refreshTip(); } });
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
    this.hideTip();
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

    // Character tab: click an owned weapon or armour piece to equip it.
    const wep = e.target.closest("[data-weapon]");
    if (wep) { this.hooks.equipWeapon?.(wep.dataset.weapon); this.render(); return; }
    const arm = e.target.closest("[data-gear]");
    if (arm) { this.hooks.equipGear?.(arm.dataset.gear); this.render(); return; }

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

  // --- the compare tooltip & selling --------------------------------------------
  /** Format a stat value; `signed` prefixes a + on positives (for deltas). */
  fmt(k, v, signed) {
    const info = STAT_INFO[k];
    const s = signed && v > 0 ? "+" : "";
    if (info?.kind === "pct") return `${s}${Math.round(v * 100)}%`;
    return `${s}${v}`;
  }

  statRows(stats) {
    return Object.entries(stats).map(([k, v]) => {
      const info = STAT_INFO[k];
      if (!info) return "";
      return `<div><span>${info.label}</span><b>${this.fmt(k, v, false)}</b></div>`;
    }).join("");
  }

  /** Only the CHANGED stats vs the worn piece, each signed and coloured up/down. */
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

  buildTip() {
    const gear = this.hooks.gearState?.();
    if (!gear) return "";
    const piece = gear.owned.find((p) => p.uid === this.hoverUid);
    if (!piece) return "";
    const equipped = gear.slots.find((sl) => sl.slot === piece.slot)?.piece;
    const worn = equipped && equipped.uid === piece.uid;

    let html = `<div class="tt-name" style="color:${piece.color}">${piece.name}</div>`;
    html += `<div class="tt-slot">${SLOT_LABEL[piece.slot] || piece.slot}${worn ? " · equipped" : ""}</div>`;
    html += `<div class="tt-stats">${this.statRows(piece.stats)}</div>`;
    if (this.shift && equipped && !worn) {
      html += `<div class="tt-cmp">vs equipped — ${equipped.name}</div>`;
      const d = this.deltaRows(piece.stats, equipped.stats);
      html += `<div class="tt-stats">${d || '<div class="tt-hint">identical stats</div>'}</div>`;
    } else if (!worn) {
      html += `<div class="tt-hint">${equipped ? "hold Shift to compare · " : ""}right-click to drop</div>`;
    }
    return html;
  }

  onHover(e) {
    if (!this.open) return;
    const cell = e.target.closest("[data-gear]");
    if (!cell) { this.hideTip(); return; }
    this.hoverUid = cell.dataset.gear;
    const html = this.buildTip();
    if (!html) { this.hideTip(); return; }
    this.tip.innerHTML = html;
    this.tip.style.display = "block";
    this.tip.style.left = `${Math.min(e.clientX + 16, innerWidth - 270)}px`;
    this.tip.style.top = `${Math.min(e.clientY + 12, innerHeight - this.tip.offsetHeight - 12)}px`;
  }

  refreshTip() {
    if (!this.open || !this.hoverUid || this.tip.style.display === "none") return;
    const html = this.buildTip();
    if (html) this.tip.innerHTML = html;
  }

  hideTip() {
    this.tip.style.display = "none";
    this.hoverUid = null;
  }

  onDrop2(e) {
    if (!this.open) return;
    const cell = e.target.closest("[data-gear]");
    if (!cell) return;
    e.preventDefault();
    const ok = this.hooks.dropGear?.(cell.dataset.gear);
    this.hideTip();
    this.render();
    if (ok) this.flash("Dropped it in front of you");
  }

  /** A brief line in the footer, e.g. after a sale. */
  flash(msg) {
    const foot = this.el.querySelector("footer");
    if (foot) foot.textContent = msg;
  }

  // --- CHARACTER: paperdoll + stats + bags ---------------------------------------
  characterHtml() {
    const gun = this.hooks.gun?.();
    const s = this.hooks.charStats?.() || {};
    const gear = this.hooks.gearState?.() || { slots: [], owned: [] };

    // Paperdoll: the Weapon slot, then the five armour slots. A worn piece shows its name in
    // its rarity colour, so a glance reads what's blue, what's still grey, and what's empty.
    let doll = `
      <div class="gslot ${gun ? "" : "empty"}">
        <span class="lbl">Weapon</span><span class="val">${gun?.weapon?.name || "—"}</span>
      </div>`;
    for (const { slot, piece } of gear.slots) {
      doll += `
        <div class="gslot ${piece ? "" : "empty"}">
          <span class="lbl">${SLOT_LABEL[slot] || slot}</span>
          <span class="val" style="${piece ? `color:${piece.color}` : ""}">${piece ? piece.name : "—"}</span>
        </div>`;
    }

    const row = (label, val) => `<div class="strow"><span>${label}</span><b>${val}</b></div>`;
    const stats = [
      row("Level", s.level ?? "—"),
      row("Points", s.points ?? 0),
      row("Health", `${Math.round(s.hp ?? 0)} / ${Math.round(s.maxHp ?? 0)}`),
      `<div class="sthr"></div>`,
      row("Strength", `${s.str ?? 0}  <em>+${Math.round((s.globalPct ?? 0))}% dmg</em>`),
      row("Agility", `${s.agi ?? 0}  <em>speed & dash</em>`),
      row("Stamina", `${s.stamina ?? 0}  <em>health</em>`),
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

    // Bags: your weapons and every gear piece you own. A piece's border is its rarity colour;
    // its tooltip is its full stat list. Click to equip (into its slot, replacing what's there).
    const weps = gun
      ? [...gun.owned].map((id) => {
        const w = WEAPONS[id];
        return `<div class="cell ${gun.weapon.id === id ? "eq" : ""}" data-weapon="${id}"
                     title="${w.name} — ${w.desc}"><span class="nm">${w.name}</span></div>`;
      }).join("")
      : "";
    const worn = new Set(gear.slots.map((x) => x.piece?.uid).filter(Boolean));
    const pieces = (gear.owned || []).map((p) =>
      `<div class="cell ${worn.has(p.uid) ? "eq" : ""}" data-gear="${p.uid}"
            style="border-color:${p.color}"
            title="${p.name} — ${statLine(p.stats)}"><span class="nm"
            style="color:${p.color}">${p.name}</span></div>`).join("");
    const items = weps + pieces;

    // The legend: every stat, in plain terms. This is what makes the numbers on a piece mean
    // something without a wiki.
    const legend = Object.values(STAT_INFO).map((info) =>
      `<span class="leg"><b>${info.label}</b> — ${info.note}</span>`).join("");

    return `
      <div class="char">
        <div class="paperdoll">
          <h3>Equipped</h3>
          ${doll}
        </div>
        <div class="statcol">${stats}</div>
        <div class="bagcol">
          <h3>Bags — click to equip</h3>
          <div class="bag">${items
            || `<p class="none">Empty. Gear you find or buy drops here.</p>`}</div>
        </div>
      </div>
      <div class="legend"><h3>What the stats do</h3>${legend}</div>`;
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
      : this.tab === "character"
        ? "Click a piece to equip · hold Shift to compare · right-click to drop · sell at a vendor"
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
