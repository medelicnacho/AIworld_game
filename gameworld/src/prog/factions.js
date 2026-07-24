// FACTIONS — the first real choice in the game.
//
// Everything else you acquire is additive: another spell, another piece, another level. You
// have never once had to give something up to get something else, which is why a character
// sheet full of upgrades still did not feel like a BUILD. This is the system that costs you
// something.
//
// Three ideas hold it together:
//
//   ONE ENEMY. Each faction is sworn against one of the mob colours already warring out
//   there, and only that colour pays reputation. So joining does not change what you are
//   called, it changes WHO YOU HUNT — you start reading camps at a distance and choosing
//   fights instead of killing whatever is nearest.
//
//   REPUTATION IS ACCESS, POINTS ARE PRICE. Climbing the ladder does not hand you gear, it
//   earns you the RIGHT TO BUY it, and the price is heavy. Neither can shortcut the other:
//   points alone is money-grinding, reputation alone is kill-counting, and needing both means
//   the only road to a full kit is playing the way your faction wants for a long time.
//
//   THE COST IS THE OTHER TWO. Rival towns stay safe and still mend you — they simply will
//   not sell you their kit. You give up two thirds of the best gear in the game by choosing,
//   and that is the entire point. A choice with no cost is a menu.
//
// The fiction is deliberately thin here. Names are placeholders; what each faction BELIEVES
// belongs to the author, and none of the machinery cares what they are called.

import { player } from "../state.js";

/**
 * The three. `enemy` is the mob colour they are sworn against — it indexes the same faction
 * tag every camp already carries, so the war they are part of is the war already happening.
 *
 * `focus` is what their gear pulls your build toward, and it is the reason the choice matters
 * beyond flavour: three routes to a different character, and you can only walk one at a time.
 */
export const FACTIONS = [
  {
    id: "ash", name: "Ash", enemy: 0, focus: "damage",
    color: "#e8804a",
    blurb: "Hits harder than it can take. Strength, and every kind of damage.",
  },
  {
    id: "vale", name: "Vale", enemy: 1, focus: "speed",
    color: "#5fd6b4",
    blurb: "Never where the blow lands. Agility, movement, shorter cooldowns.",
  },
  {
    id: "iron", name: "Iron", enemy: 2, focus: "survival",
    color: "#8fa8d8",
    blurb: "Outlasts what should have killed it. Armour and Stamina.",
  },
];

export const factionById = (id) => FACTIONS.find((f) => f.id === id) || null;

// You cannot swear to anyone until you have made a name. The choice is meant to be the first
// real decision in the game, and a decision made before you understand what the options DO is
// not a decision — at level 1 you have never seen a camp's colour matter, never spent points
// on anything you regretted, and have no idea which of the three fits how you actually play.
// The desks exist in every town from the start on purpose: seeing one you cannot use yet is
// a promise, and it teaches you where to come back to.
export const JOIN_LEVEL = 10;

/**
 * The ladder. Joining puts you at the bottom rung WITH something already for sale, so there
 * is a goal to save toward from the first minute rather than a counter that does nothing
 * until later. The gaps widen hard: the first grade is an evening, the last is the thing you
 * are still working on weeks from now.
 */
export const REP_TIERS = [
  { name: "Known", at: 0 },
  { name: "Trusted", at: 3000 },
  { name: "Honoured", at: 12000 },
  { name: "Sworn", at: 40000 },
];

// What a kill of your enemy's colour is worth. Scales with depth and stars like everything
// else in the world, so the frontier pays for reputation the same way it pays for xp.
export const REP = {
  perKill: 10,
  perRing: 0.3,
  eliteMult: 4,
  // Handing in gear you will never wear. This exists because your bag fills with pieces that
  // convert into points you do not need — the pile is dead weight the moment your kit is
  // good. Turning it into progress means a drop is never wasted, even when it is worse than
  // what you have on.
  turnIn: { common: 8, uncommon: 30, rare: 110, epic: 400, faction: 0 },
};

/** How much reputation one kill is worth, given where it died and whether it was a star. */
export function repForKill(ring, elite) {
  return Math.round(REP.perKill * (1 + REP.perRing * ring) * (elite ? REP.eliteMult : 1));
}

/** Which rung you are on: an index into REP_TIERS. */
export function tierOf(rep) {
  let t = 0;
  for (let i = 0; i < REP_TIERS.length; i++) if (rep >= REP_TIERS[i].at) t = i;
  return t;
}

/** Progress toward the next rung, and what it is called — for the HUD and the vendor. */
export function repProgress(rep) {
  const i = tierOf(rep);
  const next = REP_TIERS[i + 1];
  return {
    tier: i,
    name: REP_TIERS[i].name,
    nextName: next ? next.name : null,
    have: rep,
    need: next ? next.at : null,
    frac: next ? Math.max(0, Math.min(1, (rep - REP_TIERS[i].at) / (next.at - REP_TIERS[i].at))) : 1,
  };
}

// --- the gear ------------------------------------------------------------------------
//
// Generated the same way the smith's stock is: a grade crossed with the five slots. Cheap to
// build, trivially re-tunable, and every faction's template carries its character so a full
// kit actually reads as a build rather than as five pieces that happened to match.

const SLOTS = ["helm", "shoulders", "vest", "pants", "boots"];
const SLOT_NOUN = { helm: "Helm", shoulders: "Guards", vest: "Vest", pants: "Legs", boots: "Boots" };

// Grade rows. `a` armour, `attr` primary points, `stam`, `rate` secondary rating, `dmg` a
// damage-bucket fraction. Prices are deliberately brutal — this is where points finally go.
const GRADES = [
  { key: "worn", label: "Worn", a: 120, attr: 12, stam: 22, rate: 90, dmg: 0.06, price: 620 },
  { key: "keen", label: "Keen", a: 210, attr: 22, stam: 40, rate: 165, dmg: 0.10, price: 1850 },
  { key: "grand", label: "Grand", a: 340, attr: 36, stam: 66, rate: 270, dmg: 0.16, price: 5200 },
  { key: "sworn", label: "Sworn", a: 520, attr: 55, stam: 100, rate: 420, dmg: 0.24, price: 14000 },
];

/**
 * What each faction's gear is FOR, per slot. This is where the three builds diverge.
 *
 * MOSTLY one thing, with a LITTLE of the others. A set that carried nothing but its headline
 * stat would make a whole faction read as one number going up — a spreadsheet column rather
 * than a character — and would leave the two builds you did not pick feeling like things you
 * are missing rather than things you traded away. A splash of the other two keeps every piece
 * worth reading, lets a slot occasionally surprise you, and means a full kit still HAS a
 * spine without being a single bone.
 *
 * `m` is the minor helping: a fraction of the headline number, applied to the stats that
 * belong to the OTHER two factions. Change that one value to make the sets purer or muddier.
 */
const MINOR = 0.32;
const mi = (n) => Math.max(1, Math.round(n * MINOR));       // whole-number stats
const mf = (n) => +(n * MINOR).toFixed(3);                  // fractions (damage, move speed)

const TEMPLATES = {
  damage: {
    helm: (g) => ({ armor: g.a, str: g.attr, dmgSpell: g.dmg, rHaste: mi(g.rate) }),
    shoulders: (g) => ({ armor: g.a, str: g.attr, dmgGun: g.dmg, agi: mi(g.attr) }),
    vest: (g) => ({ armor: Math.round(g.a * 1.2), str: g.attr, dmgGlobal: g.dmg, stamina: mi(g.stam) }),
    pants: (g) => ({ armor: g.a, str: g.attr, dmgGrenade: g.dmg, stamina: mi(g.stam) }),
    boots: (g) => ({ armor: Math.round(g.a * 0.8), str: g.attr, dmgGlobal: g.dmg * 0.6, moveSpeed: mf(g.dmg) }),
  },
  speed: {
    helm: (g) => ({ armor: Math.round(g.a * 0.8), agi: g.attr, rHaste: g.rate, dmgSpell: mf(g.dmg) }),
    shoulders: (g) => ({ armor: Math.round(g.a * 0.8), agi: g.attr, rAtkSpeed: g.rate, str: mi(g.attr) }),
    vest: (g) => ({ armor: g.a, agi: g.attr, moveSpeed: g.dmg * 0.5, stamina: mi(g.stam) }),
    pants: (g) => ({ armor: Math.round(g.a * 0.8), agi: g.attr, rReload: g.rate, dmgGun: mf(g.dmg) }),
    boots: (g) => ({ armor: Math.round(g.a * 0.7), agi: Math.round(g.attr * 1.4), moveSpeed: g.dmg * 0.8, stamina: mi(g.stam) }),
  },
  survival: {
    helm: (g) => ({ armor: Math.round(g.a * 1.3), stamina: g.stam, rHaste: mi(g.rate) }),
    shoulders: (g) => ({ armor: Math.round(g.a * 1.3), stamina: g.stam, str: mi(g.attr) }),
    vest: (g) => ({ armor: Math.round(g.a * 1.8), stamina: Math.round(g.stam * 1.5), dmgGlobal: mf(g.dmg) }),
    pants: (g) => ({ armor: Math.round(g.a * 1.3), stamina: g.stam, agi: mi(g.attr) }),
    boots: (g) => ({ armor: g.a, stamina: g.stam, moveSpeed: g.dmg * 0.3, agi: mi(g.attr) }),
  },
};

/**
 * Every piece a faction sells, flat, each carrying the rung it needs. Built once at load —
 * it is a pure function of the tables above and never changes at runtime.
 */
export const FACTION_GEAR = [];
for (const f of FACTIONS) {
  GRADES.forEach((g, gi) => {
    for (const slot of SLOTS) {
      const stats = TEMPLATES[f.focus][slot](g);
      // Fractions come out of the templates with long tails; round them so a tooltip reads
      // as a number a person chose rather than as arithmetic.
      for (const k of Object.keys(stats)) {
        stats[k] = k.startsWith("dmg") || k === "moveSpeed"
          ? +stats[k].toFixed(3) : Math.round(stats[k]);
      }
      FACTION_GEAR.push({
        id: `fac_${f.id}_${g.key}_${slot}`,
        faction: f.id,
        repTier: gi,
        slot,
        name: `${g.label} ${f.name} ${SLOT_NOUN[slot]}`,
        price: g.price,
        armor: stats.armor,
        stats,
      });
    }
  });
}

/** The stock one faction offers you right now — everything up to the rung you have earned. */
export function stockFor(factionId, rep) {
  const t = tierOf(rep);
  return FACTION_GEAR.filter((p) => p.faction === factionId && p.repTier <= t);
}

/** ...and what is still locked, so the vendor can show you what you are working toward. */
export function lockedFor(factionId, rep) {
  const t = tierOf(rep);
  return FACTION_GEAR.filter((p) => p.faction === factionId && p.repTier === t + 1);
}

/**
 * Which weapon each faction teaches. Sold at the BOTTOM rung, not gated behind the climb —
 * the weapon is the faction's identity, the thing that changes how you fight, and it should
 * land the day you join rather than three hours later. The price is the gate.
 */
export const FACTION_WEAPON = { iron: "cleaver", vale: "lobber", ash: "lance" };

// --- player state --------------------------------------------------------------------

/** The faction you belong to, or null. */
export const myFaction = () => (player.faction ? factionById(player.faction) : null);

/** True when this mob colour is the one your faction wants dead. */
export function isMyEnemy(mobFaction) {
  const f = myFaction();
  return !!f && f.enemy === mobFaction;
}

/**
 * Join. Switching is allowed and costs you every point of reputation you earned — you keep
 * all your gear, because taking someone's kit back off them is a punishment out of proportion
 * to changing your mind, but the ladder starts again from the bottom.
 */
export function join(factionId) {
  if (!factionById(factionId)) return false;
  if (player.level < JOIN_LEVEL) return false;
  if (player.faction === factionId) return false;
  player.faction = factionId;
  player.rep = 0;
  return true;
}

/** Award reputation for a kill, if it was the right colour. Returns what was earned. */
export function awardRep(mobFaction, ring, elite) {
  if (!isMyEnemy(mobFaction)) return 0;
  const n = repForKill(ring, elite);
  player.rep = (player.rep || 0) + n;
  return n;
}

/** Hand a piece over. Better gear is worth more; faction gear cannot be recycled. */
export function repForTurnIn(piece) {
  return REP.turnIn[piece?.rarity] || 0;
}

/**
 * Does this settlement deal with you?
 *
 * Cities are neutral ground — all three keep a house there, so wherever you are there is one
 * place that always serves you. Towns fly a colour: yours trades, a rival's stays SAFE but
 * will not sell you their kit. Cold, not hostile. Losing the shop is a real cost; losing the
 * ability to heal would just make the map annoying to cross.
 */
export function servesYou(sanctuary) {
  if (!sanctuary) return false;
  if (sanctuary.city || sanctuary.neutral) return true;
  if (!player.faction) return false;              // unaligned: only cities have a desk for you
  // A town stores its allegiance as a COLOUR INDEX, because that is what the seeded world roll
  // produces and what the mob camps already use. The player stores a NAME. Comparing the two
  // directly is always false, which quietly made every town in the world cold — including your
  // own — and would have looked like the faction system simply not working.
  return factionOfTown(sanctuary) === player.faction;
}

/**
 * Is this sanctuary HOSTILE to you — a town you are not welcome in?
 *
 * A place that serves you (your own colours, neutral ground, a city) is a refuge, and combat
 * moves have no business there: it is why weapons stow at the gate. A rival's town does not
 * serve you — you are an intruder inside someone else's walls — so it is treated as hostile
 * ground where your dash still answers. One rule, so "where am I allowed to fight-move" and
 * "who will sell to me" can never give different answers about the same town.
 */
export function isHostileSanctuary(sanctuary) {
  return !!sanctuary && !servesYou(sanctuary);
}

/** Which faction flies over this town, by name. Null for neutral ground. */
export function factionOfTown(sanctuary) {
  if (!sanctuary || sanctuary.city || sanctuary.neutral) return null;
  const n = sanctuary.faction;
  if (n === null || n === undefined) return null;
  return FACTIONS[n % FACTIONS.length].id;
}
