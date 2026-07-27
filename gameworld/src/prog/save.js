// Persistence — one slot, saved quietly, never rewindable.
//
// THE DESIGN DECISION THIS FILE ENCODES, because it is the one that matters:
//
// There is exactly ONE save, it is overwritten in place, and death is written to it
// IMMEDIATELY. That is not laziness about slots — it is what protects the stake. Losing a
// level is meant to be the hardest thing in this game; the moment a player can close the tab
// and reopen it to undo a bad death, that entire design evaporates and every fight afterwards
// is played with a safety net the game never agreed to. A save system decides how much your
// mistakes count, so this one is built to make them count.
//
// WHAT IS WORTH SAVING is a shorter list than it looks. The world is a pure function of its
// seed (D1) — terrain, towns and where they sit are all re-derivable, so none of it is stored.
// Mobs, packs, the boss, loot lying on the ground and every cooldown are deliberately
// transient: they are the situation you were in, not the character you built. You reload as
// yourself, somewhere real, into a world that has moved on without you. That is the right
// feeling for this game anyway.
//
// Abilities are the one awkward part. They are live behaviour, not data — an ability is a
// function that reaches into the running game, and a function cannot be written to disk. So
// we save their NAMES and rebuild them through the shop's own table on load, which is exactly
// how boss relics already grant them. One path, one set of rules, and anything true of buying
// an ability stays true of loading one.

import { player } from "../state.js";
import { GOODS } from "../ui/shop.js";
import { bumpUid } from "./gear.js";
import { applyLevelStats } from "./xp.js";
import { setDifficulty, difficultyId } from "./difficulty.js";

/**
 * THREE SLOTS, and one pointer at whichever you are playing.
 *
 * There was a single key, so there was one character, and "start over" was the only way to
 * try anything else — a different faction, a harder run, a fresh look at the opening — and it
 * cost you the one you had. Slots make experimenting free, which for a game about choosing a
 * side is close to essential.
 *
 * The old single key is MIGRATED into slot 0 on first sight rather than abandoned. Someone
 * with forty levels in it should not be asked to notice a storage change.
 */
export const SLOTS = 3;
const LEGACY_KEY = "gw.save";
const SLOT_KEY = (i) => `gw.save.${i}`;
const ACTIVE_KEY = "gw.slot";
const VERSION = 1;

let active = 0;

function migrate() {
  try {
    const old = localStorage.getItem(LEGACY_KEY);
    if (old && !localStorage.getItem(SLOT_KEY(0))) localStorage.setItem(SLOT_KEY(0), old);
    if (old) localStorage.removeItem(LEGACY_KEY);
  } catch { /* storage unavailable; play on */ }
}
migrate();

try {
  const n = parseInt(localStorage.getItem(ACTIVE_KEY) ?? "", 10);
  if (Number.isInteger(n) && n >= 0 && n < SLOTS) active = n;
} catch { /* nothing to remember */ }

/** Which slot is being played. Everything else here reads this. */
export function activeSlot() { return active; }

/** Choose a slot. Remembered, so a reload comes back to the same character. */
export function setSlot(i) {
  active = Math.max(0, Math.min(SLOTS - 1, i | 0));
  try { localStorage.setItem(ACTIVE_KEY, String(active)); } catch { /* fine */ }
  return active;
}

/** A one-line summary of each slot, for the picker. Never throws — a corrupt slot reads as
 *  empty rather than taking the menu down with it. */
export function listSlots() {
  return Array.from({ length: SLOTS }, (_, i) => {
    try {
      const raw = localStorage.getItem(SLOT_KEY(i));
      if (!raw) return { i, empty: true };
      const d = JSON.parse(raw);
      return {
        i, empty: false,
        level: d.level || 1,
        faction: d.faction || null,
        difficulty: d.difficulty || null,
        at: d.at || 0,
        points: d.points || 0,
      };
    } catch { return { i, empty: true, corrupt: true }; }
  });
}

/** Erase one slot without touching the others, or which one is active. */
export function eraseSlot(i) {
  try { localStorage.removeItem(SLOT_KEY(i)); } catch { /* nothing to do */ }
}

/** Everything that is genuinely YOURS, as plain data. */
export function snapshot(ctx) {
  const { abilities, gun } = ctx;
  return {
    v: VERSION,
    at: null,                    // stamped by the caller; no clocks in here
    level: player.level,
    xp: player.xp,
    points: player.points,
    potions: player.potions,
    hp: player.hp,
    // Who you ride with, and how far up their ladder. Losing this to a reload would
    // undo the longest commitment in the game.
    faction: player.faction || null,
    rep: player.rep || 0,
    difficulty: difficultyId(),
    x: player.x, y: player.y, z: player.z,
    // ...and WHICH WORLD those coordinates belong to. Null out under the sky; inside an
    // instance, the one number that rebuilds it. See dungeonState() in main.
    dungeon: ctx.dungeonState ? ctx.dungeonState() : null,
    yaw: player.yaw, pitch: player.pitch,
    // Stacking upgrade counters. These live on the player rather than in the gear sum, so
    // they have to travel separately or a loaded character quietly loses what it bought.
    haste: player.haste || 0,
    dashRank: player.dashRank || 0,
    gearReload: player.gearReload || 0,
    // What you have bought, which is also what the shop reads to price and grey out its stock.
    upgrades: { ...(player.upgrades || {}) },
    // Gear is already plain data, so it stores as-is — worn and carried both.
    gearSlots: player.gearSlots,
    ownedGear: player.ownedGear,
    // Abilities by NAME (see the header), plus where you had arranged them on the bar.
    abilities: abilities.owned.map((a) => a.id),
    bar: abilities.slots.map((s) => (s ? s.id : null)),
    guns: [...gun.owned],
    loadout: [...gun.loadout],
    gun: gun.weapon.id,
    // THE TOWN'S MEMORY OF YOU (VOICE.md C2): what it heard said — by its own people and
    // by you — and each villager's memory of your conversations. The one exception to
    // "only what is genuinely yours" — because being remembered is the point of the town,
    // and a memory that dies with the tab is not a memory. Restored with decay: away an
    // hour, it fades a little; away a week, the town has honestly forgotten.
    town: ctx.townVoice && ctx.townChat
      ? { voice: ctx.townVoice.dump(), chat: ctx.townChat.dump() }
      : null,
    // WHAT THE WAR REMEMBERS. A town you sacked stays quiet for its rebuild window and a
    // champion you killed stays dead — and neither survived a reload, so refreshing the page
    // handed back every garrison you had just cleared. That is not a save bug so much as a
    // free reset button, and the cheapest way to farm a town was the browser's own.
    raids: ctx.raids ? ctx.raids.dump() : null,
    // Where the sun was. Without this every reload is dawn, and a world whose clock
    // resets when you blink is a stage set, not a place.
    worldT: ctx.dayNight ? ctx.dayNight.t : null,
  };
}

/**
 * Put a snapshot back. Order matters: gear and counters first, then DERIVE, then health —
 * health is a value inside a ceiling that the gear decides, so restoring it before the
 * ceiling exists would clamp it to the wrong number.
 */
export function restore(data, ctx) {
  const { abilities, gun, recomputeGear } = ctx;

  player.level = Math.max(1, data.level | 0);
  player.xp = Math.max(0, data.xp | 0);
  player.points = Math.max(0, data.points | 0);
  player.potions = Math.max(0, data.potions | 0);
  player.faction = data.faction || null;
  player.rep = Math.max(0, data.rep | 0);
  setDifficulty(data.difficulty || "hard");
  player.x = data.x; player.y = data.y; player.z = data.z;
  // WHICH WORLD those coordinates were in. Restored BEFORE anything reads the ground, because
  // groundY means something entirely different once an instance is live.
  const inside = data.dungeon ? !!ctx.restoreDungeon?.(data.dungeon) : false;
  // THE FALL GUARD. A save written before dungeons were saveable — or one whose instance
  // refused to rebuild — can carry a Y hundreds of blocks above the land with no floor under
  // it, and restoring that faithfully means loading into freefall. Nothing legitimate puts you
  // that far over the terrain, so it is treated as the corruption it is and dropped to the
  // ground beneath. Costs a returning player nothing; costs a hardcore one their character.
  if (!inside) {
    const g = ctx.groundAt ? ctx.groundAt(player.x, player.z) : null;
    if (g !== null && player.y > g + 240) player.y = g + 0.5;
  }
  player.yaw = data.yaw || 0; player.pitch = data.pitch || 0;
  player.haste = data.haste || 0;
  player.dashRank = data.dashRank || 0;
  player.gearReload = data.gearReload || 0;
  player.upgrades = { ...(data.upgrades || {}) };

  player.gearSlots = { helm: null, shoulders: null, vest: null, pants: null, boots: null };
  for (const [slot, piece] of Object.entries(data.gearSlots || {})) {
    if (piece) player.gearSlots[slot] = piece;
  }
  player.ownedGear = Array.isArray(data.ownedGear) ? data.ownedGear : [];

  // Fresh drops number themselves from a counter that restarts with the page. Without this,
  // the first thing you picked up after loading would be born holding the same name as
  // something already in your bag — and every action that finds a piece BY name (equip, sell,
  // drop) would then hit whichever one it met first. Step the counter past everything loaded.
  let high = 0;
  for (const p of [...player.ownedGear, ...Object.values(player.gearSlots)]) {
    const n = Number(String(p?.uid || "").replace("drop_", ""));
    if (Number.isFinite(n)) high = Math.max(high, n + 1);
  }
  bumpUid(high);

  // Rebuild each ability by asking the shop to grant it again — the same call the buy button
  // and a boss relic both make.
  const adept = GOODS.adept || [];
  for (const id of data.abilities || []) {
    adept.find((g) => g.id === id)?.apply(ctx.game);
  }
  // ...then put the bar back the way it was. acquire() drops things into the first free slot,
  // which is not where you had them.
  const owned = new Map(abilities.owned.map((a) => [a.id, a]));
  abilities.slots = (data.bar || []).map((id) => (id ? owned.get(id) || null : null));
  while (abilities.slots.length < ctx.slots) abilities.slots.push(null);
  abilities.slots.length = ctx.slots;
  // THE ONES YOU WERE GIVEN. Heal and the grenade were fixed keys before they were spells, so
  // a bar saved back then does not mention them — and rebuilding the bar from that list would
  // strand the two abilities every character owns in the bag. Anything marked `starter` that
  // the saved bar left out goes back onto it. Deliberately not a repair for spells you BOUGHT:
  // those you arranged yourself, and an empty slot is a choice.
  // ...and if there is NOWHERE to put one, make room. The bar shrank from ten slots to six, so
  // a character built back then can load with its heal truncated off the end — equip(-1) finds
  // no free slot, quietly declines, and you spawn with no heal key and no idea why. Nothing was
  // ever lost (the displaced spell is still in `owned`, one drag from the bag), so the trade is
  // an arrangement you can redo in a second against a button your hands reach for without
  // asking. Last slot, so it takes the least-reached key.
  for (const a of abilities.owned) {
    if (!a.starter || abilities.slots.some((s) => s?.id === a.id)) continue;
    if (!abilities.equip(-1, a)) abilities.equip(ctx.slots - 1, a);
  }

  for (const id of data.guns || []) gun.acquire(id);
  // The two you CARRIED, not just the pile you owned. Older saves have no loadout; derive
  // one from what was in hand so nobody loads into empty arms.
  gun.setLoadout(data.loadout || [data.gun, ...(data.guns || [])]);
  if (data.gun) gun.carry(data.gun);

  recomputeGear();          // sums the worn set, then derives every level/gear stat
  applyLevelStats();
  player.hp = Math.max(1, Math.min(player.maxHp, data.hp ?? player.maxHp));

  // The town's memory of you comes back FADED by real time away (data.at is the save's
  // wall-clock). Defensive at every step: an old save has no town field, and a save with
  // one must never be able to break the load — memory is flavour, the character is not.
  if (typeof data.worldT === "number" && ctx.dayNight) {
    ctx.dayNight.t = Math.max(0, data.worldT) % ctx.dayNight.cycle;
  }
  if (data.town && ctx.townVoice && ctx.townChat) {
    try {
      const hoursAway = data.at ? Math.max(0, (Date.now() - data.at) / 3.6e6) : 0;
      ctx.townVoice.restore(data.town.voice, hoursAway);
      ctx.townChat.restore(data.town.chat, hoursAway);
    } catch { /* a corrupt memory is forgotten, not fatal */ }
  }
  if (data.raids && ctx.raids) {
    try {
      // AGED by the time you were away, in seconds — the rebuild timers are real durations,
      // so an hour away should have rebuilt the town rather than preserving it in amber.
      const away = data.at ? Math.max(0, (Date.now() - data.at) / 1000) : 0;
      ctx.raids.restore(data.raids, away);
    } catch { /* a corrupt war is a fresh garrison, not a crash */ }
  }
}

/** Write the slot. Never throws — a full or blocked disk must not interrupt play. */
export function save(ctx) {
  try {
    const data = snapshot(ctx);
    data.at = Date.now();
    localStorage.setItem(SLOT_KEY(active), JSON.stringify(data));
    return true;
  } catch {
    return false;      // private mode, quota, disabled storage — play on regardless
  }
}

/**
 * Read the slot, or null. A save that is corrupt, truncated or from an older shape must
 * START A NEW GAME rather than break — a player who cannot get past the loading of a bad
 * file has lost the game entirely, whereas one who starts fresh has only lost a session.
 */
export function load() {
  try {
    const raw = localStorage.getItem(SLOT_KEY(active));
    if (!raw) return null;
    const data = JSON.parse(raw);
    if (!data || data.v !== VERSION) return null;
    if (typeof data.level !== "number") return null;
    return data;
  } catch {
    return null;
  }
}

export function hasSave() { return load() !== null; }

export function wipe() {
  try { localStorage.removeItem(SLOT_KEY(active)); } catch { /* nothing to do */ }
}
