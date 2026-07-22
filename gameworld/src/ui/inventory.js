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
  constructor(el, abilities) {
    this.el = el;
    this.abilities = abilities;
    this.open = false;
    this.picked = null;      // {from: "bag"|"slot", index}

    this.el.addEventListener("click", (e) => this.onClick(e));
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

  onClick(e) {
    if (e.target.closest("[data-close]")) { this.picked = null; this.render(); return; }
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
      // Already equipped elsewhere? Move it rather than cloning it into two slots.
      const at = a.slots.findIndex((s) => s && s.id === def.id);
      const displaced = a.slots[to.index];
      a.slots[to.index] = def;
      if (at >= 0 && at !== to.index) a.slots[at] = displaced || null;
    } else if (from.from === "slot" && to.from === "slot") {
      const t = a.slots[to.index];
      a.slots[to.index] = a.slots[from.index];
      a.slots[from.index] = t;
    } else if (from.from === "slot" && to.from === "bag") {
      a.slots[from.index] = null;      // dragged out of the bar: unequip
    }
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
        <header><h2>Inventory</h2><button class="x" data-close>✕</button></header>
        <div class="bag">${bag}</div>
        <h3>Ability bar</h3>
        <div class="bar">${bar}</div>
        <footer>${this.picked
          ? "Now click a slot to place it"
          : "Drag or click an ability onto a slot · drag it out to unequip · click the world to resume"}</footer>
      </div>`;
  }
}
