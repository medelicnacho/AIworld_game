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

import { SLOTS, SLOT_KEYS } from "../player/abilities.js";
import { ICONS } from "./icons.js";
import { WEAPONS, STAT_INFO, ADMIN_CODE, CAMERA } from "../config.js";
import { setLook, LOOK_MIN, LOOK_MAX } from "../player/controller.js";
import { statLine } from "./shop.js";
import { sortBag } from "../prog/gear.js";

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
    // Asked once per page load, not once per visit to the sheet — a code you retype every
    // time you tab out to change something is a tax on the person it is meant to serve.
    this.adminUnlocked = false;
    this.adminAsking = false;
    this.adminWrong = false;
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
      // Enter submits the code box. Escape must NOT close the sheet while you are typing in
      // it either — losing what you typed to a stray key is the kind of small cruelty that
      // makes people stop using a tool.
      if (e.target?.id === "adm-code") {
        if (e.code === "Enter") { e.preventDefault(); e.stopPropagation(); this.tryAdminCode(); }
        return;
      }
      if (e.code === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        this.close();
      }
    }, true);
    // Live while you drag. Deliberately does NOT re-render the panel: rebuilding the markup
    // under the cursor would tear the slider out from under the mouse on the first pixel of
    // movement, so only the number beside it is updated.
    this.el.addEventListener("input", (e) => {
      if (e.target?.id === "opt-sens") {
        const v = setLook(Number(e.target.value));
        const out = this.el.querySelector(".sens-val");
        if (out) out.textContent = (v * 1000).toFixed(1);
      }
      // All three faders behave identically, so they are one table rather than three blocks.
      for (const [id, hook, cls] of [
        ["opt-vol", "setVolume", ".vol-val"],
        ["opt-music", "setMusicVolume", ".music-val"],
        ["opt-voice", "setVoiceVolume", ".voice-val"],
      ]) {
        if (e.target?.id !== id) continue;
        const v = this.hooks[hook]?.(Number(e.target.value));
        const out = this.el.querySelector(cls);
        if (out && v !== undefined) out.textContent = `${Math.round(v * 100)}%`;
      }
    });
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

    if (e.target.closest("[data-admin]")) {
      // Unlocked already: it is just a toggle. Locked: ask, rather than opening.
      if (this.adminUnlocked) this.admin = !this.admin;
      else { this.adminAsking = !this.adminAsking; this.adminWrong = false; }
      this.render();
      if (this.adminAsking) this.el.querySelector("#adm-code")?.focus();
      return;
    }
    if (e.target.closest("[data-admincode]")) { this.tryAdminCode(); return; }
    // BACK TO CHARACTER SELECT. No confirm and no danger: your character is saved on the way
    // out, and the slot screen is where you switch, start another, or delete one. Erasing used
    // to live here as "Start over", which meant the destructive button sat inside the panel
    // you open forty times a session — right beside the tabs. It belongs on the screen whose
    // whole job is choosing a character, and nowhere else.
    if (e.target.closest("[data-slots]")) { this.hooks.toCharacterSelect?.(); return; }
    // UNSTUCK closes the panel on the way out. You pressed it to look at the world, and the
    // whole point is seeing whether it worked — leaving the sheet over the top would mean
    // pressing it again because nothing appeared to happen.
    if (e.target.closest("[data-unstuck]")) { this.hooks.unstick?.(); this.close(); return; }
    if (e.target.closest("[data-grant]")) { this.hooks.grantAll?.(); this.render(); return; }
    const one = e.target.closest("[data-give]");
    if (one) { this.hooks.give?.(one.dataset.give); this.render(); return; }
    const fac = e.target.closest("[data-faction]");
    if (fac) { this.hooks.setFaction?.(fac.dataset.faction); this.render(); return; }
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

  /**
   * One draggable square. `key` is the keyboard key this slot answers to, drawn in the corner
   * exactly where the in-game bar draws it — this screen is where you DECIDE what sits on which
   * key, and it was the one place that never said. You arranged a bar by position and then went
   * back to a HUD labelled Q/E/1/2/3/4, which is a translation nobody should have to do. Blank
   * slots get the badge too, and want it most: an empty square is a question about a key.
   */
  cell(def, attr, i, extra = "", key = "") {
    const label = def ? `${def.name} — ${def.desc || ""}` : key ? `empty — ${key}` : "empty";
    return `
      <div class="cell ${def ? "" : "blank"} ${extra}" ${attr}="${i}" ${def ? 'draggable="true"' : ""}
           title="${label}">
        ${key ? `<span class="k">${key}</span>` : ""}
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
    // Look in the bag AND in what you are wearing. The bag deliberately holds only what you
    // are NOT using, so a worn piece was invisible to this and hovering your own kit did
    // nothing at all.
    const piece = gear.owned.find((p) => p.uid === this.hoverUid)
      || gear.slots.map((sl) => sl.piece).find((p) => p && p.uid === this.hoverUid);
    if (!piece) return "";
    const equipped = gear.slots.find((sl) => sl.slot === piece.slot)?.piece;
    const worn = equipped && equipped.uid === piece.uid;

    let html = `<div class="tt-name" style="color:${piece.color}">${piece.name}</div>`;
    html += `<div class="tt-slot">${SLOT_LABEL[piece.slot] || piece.slot}`
      + ` · tier ${piece.tier ?? 0}${worn ? " · equipped" : ""}</div>`;
    html += `<div class="tt-stats">${this.statRows(piece.stats)}</div>`;
    // A worn piece gets the stats and nothing else. There is nothing to compare it against
    // (it IS the comparison), and nothing to do with it from here — so any extra line would
    // be a prompt to press a key that does nothing.
    if (worn) return html;
    if (this.shift && equipped) {
      html += `<div class="tt-cmp">vs equipped — ${equipped.name}</div>`;
      const d = this.deltaRows(piece.stats, equipped.stats);
      html += `<div class="tt-stats">${d || '<div class="tt-hint">identical stats</div>'}</div>`;
    } else {
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
    // Only from the BAG. The paperdoll now carries data-gear as well so its rows can be
    // hovered for stats, but right-clicking what you are wearing should not throw it on the
    // floor — unequip it first, deliberately, and then decide.
    const cell = e.target.closest(".bag [data-gear]");
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
    // The worn pieces carry data-gear too, so hovering one shows the same stat card the bag
    // gives you. Reading what you are WEARING should never be harder than reading what you
    // are carrying — and until now the only way to check your own kit was to remember it.
    for (const { slot, piece } of gear.slots) {
      doll += `
        <div class="gslot ${piece ? "" : "empty"} ${piece?.rarity === "epic" ? "epic" : ""}"
             ${piece ? `data-gear="${piece.uid}"` : ""}>
          <span class="lbl">${SLOT_LABEL[slot] || slot}</span>
          <span class="val" style="${piece ? `color:${piece.color}` : ""}">${piece ? piece.name : "—"}</span>
          ${piece ? `<span class="tier">T${piece.tier ?? 0}</span>` : ""}
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
    // Weapons: you CARRY two of everything you own. Green is in your hands, gold is on your
    // back, plain is in the bag — clicking any of them takes it in hand, swapping out
    // whatever you were holding. The one on your back is never silently discarded.
    const weps = gun
      ? [...gun.owned].map((id) => {
        const w = WEAPONS[id];
        const active = gun.weapon.id === id;
        const carried = gun.loadout?.includes(id);
        const state = active ? "in hand" : carried ? "carried" : "click to carry (swaps what you hold)";
        const leg = w.rarity === "legendary";
        return `<div class="cell ${active ? "eq" : carried ? "held" : ""} ${leg ? "legendary" : ""}"
                     data-weapon="${id}" ${leg ? `style="border-color:${w.color}"` : ""}
                     title="${w.name} — ${w.desc} · ${state}"><span class="nm"
                     style="${leg ? `color:${w.color}` : ""}">${w.name}</span></div>`;
      }).join("")
      : "";
    const worn = new Set(gear.slots.map((x) => x.piece?.uid).filter(Boolean));
    // Best at the top, worst at the bottom. The ordering itself lives in gear.js so that the
    // shop's bag and this one can never disagree about which piece is better.
    const sorted = sortBag(gear.owned);
    // The TIER badge. Rarity (the colour) says how many stats a piece carries; tier says how
    // big they are, and they move independently — a blue out of the Commons and a blue out of
    // the Deep look identical without this while one has several times the numbers. Two pieces
    // cannot be compared on colour alone, so the second number has to be on the tile.
    const pieces = sorted.map((p) =>
      `<div class="cell ${worn.has(p.uid) ? "eq" : ""} ${p.rarity === "epic" ? "epic" : ""}"
            data-gear="${p.uid}" style="border-color:${p.color}"
            title="${p.name} — ${statLine(p.stats)}"><span class="nm"
            style="color:${p.color}">${p.name}</span><span class="tier">T${p.tier ?? 0}</span></div>`).join("");
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
        this.picked?.from === "slot" && this.picked.index === i ? "held" : "", SLOT_KEYS[i])).join("");
    // The heading names the keys rather than stating a range. It said "(1–4)" long after the
    // bar stopped being four slots on 1–4 — a hardcoded description of a list that is right
    // there to be read is a comment pretending to be UI, and it goes stale in silence.
    const free = a.slots.filter((s) => !s).length;
    return `
      <div class="bag">${bag}</div>
      <h3>Ability bar — ${SLOT_KEYS.join(" · ")}${
        a.owned.length > SLOTS
          ? ` <span class="hint">${a.owned.length - SLOTS + free} left in the bag — you cannot carry them all</span>`
          : ""}</h3>
      <div class="bar">${bar}</div>`;
  }

  talentsHtml() {
    return `<div class="talents">
      <p class="none">Spec tree coming soon — spend points as you level to branch your build.</p>
    </div>`;
  }

  /** Check what was typed into the code box. Right: open up, and stay open for the session. */
  tryAdminCode() {
    const v = this.el.querySelector("#adm-code")?.value?.trim();
    if (v === ADMIN_CODE) {
      this.adminUnlocked = true;
      this.admin = true;
      this.adminAsking = false;
      this.adminWrong = false;
    } else {
      this.adminWrong = true;
    }
    this.render();
    if (this.adminAsking) this.el.querySelector("#adm-code")?.focus();
  }

  /** The code box. Shown in place of the panel until the right code goes in. */
  adminGateHtml() {
    if (!this.adminAsking || this.adminUnlocked) return "";
    return `
      <div class="admin">
        <div class="row">
          <span class="lbl">${this.adminWrong ? "wrong code" : "testing tools — code:"}</span>
          <input id="adm-code" type="password" autocomplete="off" inputmode="numeric">
          <button data-admincode>unlock</button>
        </div>
      </div>`;
  }

  /** A testing panel: set level, hand yourself points, grant every ability at once. */
  adminHtml() {
    if (!this.admin || !this.adminUnlocked) return "";
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
          <span class="lbl">swear to:</span>
          ${["iron", "ash", "vale"].map((f) => `
            <button class="give ${p.faction === f ? "has" : ""}" data-faction="${f}">
              ${f}${p.faction === f ? " ✓" : ""}
            </button>`).join("")}
        </div>
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
    // The way out to the slot screen. Safe by construction — it saves and returns you to the
    // character list, where switching, starting another and deleting one all live together.
    const reset = `<button class="reset" data-slots>Characters</button>`;
    // UNSTUCK lives here rather than on a key. It is pressed when the world has gone wrong,
    // which is never a moment that needs to be fast — and a hotkey for it is a hotkey somebody
    // fat-fingers mid-fight. Beside "Characters" on purpose: both are ways out, and a player
    // hunting for one has already found the other.
    const unstuck = `<button class="reset unstuck" data-unstuck title="Stand you back up if the world has closed over you">Unstuck</button>`;

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
          ${unstuck}
          ${reset}
          <button class="adm ${this.admin ? "on" : ""}" data-admin>admin</button>
          <button class="x" data-close>✕</button>
        </header>
        <nav class="tabs">${tabs}</nav>
        <div class="scroll">
          <div class="tabbody">${body}</div>
          ${this.adminGateHtml()}
          ${this.adminHtml()}
        </div>
        <div class="opts">
          <label for="opt-sens">Mouse sensitivity</label>
          <input id="opt-sens" type="range" min="${LOOK_MIN}" max="${LOOK_MAX}" step="0.0005"
                 value="${CAMERA.sensitivity}">
          <span class="optval sens-val">${(CAMERA.sensitivity * 1000).toFixed(1)}</span>
          <span class="opthint">or <b>[</b> <b>]</b> while playing</span>
        </div>
        <div class="opts">
          <label for="opt-vol">Volume</label>
          <input id="opt-vol" type="range" min="0" max="2" step="0.05"
                 value="${this.hooks.volume?.() ?? 1}">
          <span class="optval vol-val">${Math.round((this.hooks.volume?.() ?? 1) * 100)}%</span>
          <span class="opthint">all game audio — past 100% is boost</span>
        </div>
        <div class="opts">
          <label for="opt-music">Music</label>
          <input id="opt-music" type="range" min="0" max="2" step="0.05"
                 value="${this.hooks.musicVolume?.() ?? 1}">
          <span class="optval music-val">${Math.round((this.hooks.musicVolume?.() ?? 1) * 100)}%</span>
          <span class="opthint">the soundtrack, on its own</span>
        </div>
        <div class="opts">
          <label for="opt-voice">Voices</label>
          <input id="opt-voice" type="range" min="0" max="2" step="0.05"
                 value="${this.hooks.voiceVolume?.() ?? 1}">
          <span class="optval voice-val">${Math.round((this.hooks.voiceVolume?.() ?? 1) * 100)}%</span>
          <span class="opthint">villagers, war cries and hails</span>
        </div>
        <footer>${foot}</footer>
      </div>`;
  }
}
