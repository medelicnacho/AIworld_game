// The inventory: everything you own, and the four bar slots you can drag it into.
//
// It IS the pause screen. Escape releases pointer lock, which pauses the game, and rather
// than showing a bare "click to resume" panel that does nothing, the paused moment is where
// you rearrange your kit. One screen, one purpose, no extra key to learn.
//
// Drag to equip, drag between slots to swap, drag out to unequip. Click also works for
// everything drag does — drag-and-drop is unreliable on trackpads and impossible with one
// hand on the keyboard, and an interface with only one input path excludes people for no
// reason.

import { SLOTS } from "../player/abilities.js";
import { ICONS } from "./icons.js";

export class Inventory {
  constructor(el, abilities, hooks = {}) {
    this.el = el;
    this.abilities = abilities;
    this.hooks = hooks;      // { onClose, grantAll, setLevel, addPoints }
    this.open = false;
    this.admin = false;
    this.picked = null;      // {from: "bag"|"slot", index}

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

  /** Where a drag or click started: a bag entry, or one of the bar slots. */
  static origin(target) {
    const slot = target.closest("[data-slot]");
    if (slot) return { from: "slot", index: Number(slot.dataset.slot) };
    const bag = target.closest("[data-bag]");
    if (bag) return { from: "bag", index: Number(bag.dataset.bag) };
    return null;
  }

  onDragStart(e) {
    const o = Inventory.origin(e.target);
    if (!o) return;
    this.picked = o;
    // Firefox refuses to start a drag unless some data is set.
    e.dataTransfer?.setData("text/plain", `${o.from}:${o.index}`);
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

    if (e.target.closest("[data-admin]")) { this.admin = !this.admin; this.render(); return; }
    if (e.target.closest("[data-grant]")) { this.hooks.grantAll?.(); this.render(); return; }
    const one = e.target.closest("[data-give]");
    if (one) { this.hooks.give?.(one.dataset.give); this.render(); return; }
    const spawn = e.target.closest("[data-spawn]");
    if (spawn) { this.hooks.spawnAffix?.(spawn.dataset.spawn); this.close(); return; }
    if (e.target.closest("[data-spawnmix]")) { this.hooks.spawnAffixMix?.(); this.close(); return; }
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

  /** A testing panel: set level, hand yourself points, grant every ability at once. */
  adminHtml() {
    if (!this.admin) return "";
    const p = this.hooks.state?.() || {};
    const owned = new Set(this.abilities.owned.map((o) => o.id));
    // Every ability the game sells, tier gates ignored — the point of a test panel is to
    // reach any state quickly, including ones a real run would take an hour to get to.
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
        </div>
      </div>`;
  }

  render() {
    if (!this.open) return;
    const a = this.abilities;
    const equippedIds = new Set(a.slots.filter(Boolean).map((s) => s.id));

    const cell = (def, attr, i, extra = "") => `
      <div class="cell ${def ? "" : "blank"} ${extra}" ${attr}="${i}" ${def ? 'draggable="true"' : ""}
           title="${def ? `${def.name} — ${def.desc || ""}` : "empty"}">
        <span class="ic">${def ? (ICONS[def.icon] || "") : ""}</span>
        <span class="nm">${def ? def.name : ""}</span>
      </div>`;

    const bag = a.owned.length
      ? a.owned.map((d, i) => cell(d, "data-bag", i, equippedIds.has(d.id) ? "eq" : "")).join("")
      : `<p class="none">Nothing yet. Adepts in the towns sell abilities.</p>`;

    const bar = Array.from({ length: SLOTS }, (_, i) =>
      cell(a.slots[i], "data-slot", i, this.picked?.from === "slot" && this.picked.index === i ? "held" : "")).join("");

    this.el.innerHTML = `
      <div class="panel">
        <header>
          <h2>Inventory</h2>
          <button class="adm ${this.admin ? "on" : ""}" data-admin>admin</button>
          <button class="x" data-close>✕</button>
        </header>
        <div class="bag">${bag}</div>
        <h3>Ability bar</h3>
        <div class="bar">${bar}</div>
        ${this.adminHtml()}
        <footer>${this.picked
          ? "Now click a slot to place it"
          : "Drag or click an ability onto a slot · drag it out to unequip · "
            + "Esc, ✕ or click outside to resume"}</footer>
      </div>`;
  }
}
