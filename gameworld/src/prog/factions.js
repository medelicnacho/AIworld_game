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
import { MOB } from "../config.js";
import { sanctuariesNear } from "../world/sanctuary.js";

/**
 * The three. `enemy` is the mob colour they are sworn against — it indexes the same faction
 * tag every camp already carries, so the war they are part of is the war already happening.
 *
 * `focus` is what their gear pulls your build toward, and it is the reason the choice matters
 * beyond flavour: three routes to a different character, and you can only walk one at a time.
 */
// The three warring mob colours ARE the three factions' field armies. Joining a faction puts
// you on ONE colour's side:
//   ally   — that colour's camps are yours. You cannot attack them; they fight for you.
//   enemy  — a different colour, the one that pays reputation when you cut it down.
//   (the third colour is nobody's business of yours — neutral, still hostile, no rep.)
// It is a rock-paper-scissors: Ash hunts Iron's black, Vale hunts Ash's blue, Iron hunts
// Vale's green — so no two factions share an ally OR an enemy.
export const FACTIONS = [
  {
    id: "ash", name: "Ash", ally: 1, enemy: 0, focus: "damage",
    color: "#5b9dff",   // blue
    blurb: "Hits harder than it can take. Strength, and every kind of damage.",
  },
  {
    id: "vale", name: "Vale", ally: 2, enemy: 1, focus: "speed",
    color: "#5fd66a",   // green
    blurb: "Never where the blow lands. Agility, movement, shorter cooldowns.",
  },
  {
    id: "iron", name: "Iron", ally: 0, enemy: 2, focus: "survival",
    color: "#aab0be",   // iron/black — a legible steel for text; its mobs are truly black
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

// WHERE REPUTATION COMES FROM. Deliberately NOT from cutting down ordinary camps — the
// frontier is full of them and that would make standing a grind you do by accident. It comes
// from things you CHOOSE and things that are hard:
//   - handing gear to your quartermaster (your bag of unworn drops becomes progress),
//   - killing a BOSS (rare, and a real fight),
//   - quests (a board, when it is built).
export const REP = {
  perRing: 0.3,
  // Handing in gear you will never wear. This exists because your bag fills with pieces that
  // convert into points you do not need — the pile is dead weight the moment your kit is
  // good. Turning it into progress means a drop is never wasted, even when it is worse than
  // what you have on.
  turnIn: { common: 8, uncommon: 30, rare: 110, epic: 400, faction: 0 },
  // A boss is the big lump of standing between turn-in trickles — scaled by depth like
  // everything else, so a deep boss is worth far more than a shallow one.
  bossBase: 800,
  bossPerRing: 0.6,
};

/** Reputation for a boss kill, by the ring it fell in. The main non-quest source of standing. */
export function repForBoss(ring) {
  return Math.round(REP.bossBase * (1 + REP.bossPerRing * ring));
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

/**
 * THE PITCH — what joining actually hands you, in the order a player needs it.
 *
 * The recruiter used to lead with character ("Hits harder than it can take") and never
 * once name the WEAPON, which is the only part that changes how you play. A newcomer
 * asked to make the game's one irreversible choice was reading poetry about three
 * temperaments while the actual question — do I want to lob bombs, swing a cleaver, or
 * hold a beam on a line — went unasked. WEAPONS.md said it first: the weapon IS the
 * identity. So the desk says the weapon first, the stats second, the poetry last.
 *
 * `weapon` is the verb. `spec` is where the numbers go. Both are written for someone who
 * has never played, which is exactly who is standing at the desk.
 */
export const FACTION_PITCH = {
  vale: {
    weapon: "A LOBBER — a shell you arc into a crowd that bursts in a wide blast. "
      + "Forgiving to aim: you are covering ground, not tracking a head.",
    spec: "Speed & haste — movement, dash, shorter cooldowns.",
  },
  iron: {
    weapon: "A CLEAVER — a heavy melee arc that hits everything in front of you and "
      + "knocks it back, plus a whirlwind spin that opens with invulnerable frames.",
    spec: "Defence & health — armour and stamina.",
  },
  ash: {
    weapon: "A LANCE — a long, precise beam you hold on a line, cutting through "
      + "everything standing in it. Rewards aim and positioning.",
    spec: "Strength & raw damage — every kind of damage you deal.",
  },
};

// --- player state --------------------------------------------------------------------

/** The faction you belong to, or null. */
export const myFaction = () => (player.faction ? factionById(player.faction) : null);

/** True when this mob colour is the one your faction wants dead. */
export function isMyEnemy(mobFaction) {
  const f = myFaction();
  return !!f && f.enemy === mobFaction;
}

/** The mob colour that fights on YOUR side, or -1 if unaligned. */
export function allyColor() {
  const f = myFaction();
  return f ? f.ally : -1;
}

/**
 * True when this colour is YOUR army — the camps you cannot attack and that will not attack
 * you. Checked at every place the player could deal damage, so a stray grenade or a beam
 * sweeping across a friendly camp does nothing. `mobFaction` may be undefined (a mob with no
 * side); that is never an ally.
 */
export function isMyAlly(mobFaction) {
  const f = myFaction();
  return !!f && mobFaction !== undefined && f.ally === mobFaction;
}

/** The colour of the three that names a faction, for tinting mobs and bosses to their side. */
export const FACTION_COLORS = {
  0: 0x26262c,   // black — Iron
  1: 0x3f6fd1,   // blue  — Ash
  2: 0x4fae5a,   // green — Vale
};

// YOU WEAR YOUR COLOURS TOO. The same war-colour space the towns use (villagers.js
// TOWN_TINT), lifted the same way for the same reason: Iron's true black reads as a hole
// in the world rather than a body, so it becomes a dark steel that still says black at a
// glance. The unaligned wanderer keeps the original rust — a colour none of the three
// owns, which is exactly what having no banner should look like.
export const PLAYER_UNSWORN = 0xd8734a;
export const PLAYER_COLORS = {
  iron: 0x32323a,
  ash: 0x3f6fd1,
  vale: 0x4fae5a,
};

/** What the player's body should be painted right now — their banner, or rust. */
export function playerColor() {
  return PLAYER_COLORS[player.faction] ?? PLAYER_UNSWORN;
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

/**
 * Add reputation to the faction you belong to. The one door standing gains through, so every
 * source — a turn-in, a boss, a quest — passes through here and an unaligned player can never
 * bank anything. Returns what was added.
 */
export function gainRep(amount) {
  if (!player.faction || amount <= 0) return 0;
  player.rep = (player.rep || 0) + amount;
  return amount;
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
  // THE WAR IS NONE OF YOURS until you pick a side. Before the raid existed, "hostile" only
  // meant "your dash works here and the shop is closed" — harmless to a newcomer. Now it
  // means an emptied town and a war-camp that hunts you, so it must NEVER apply to the
  // unaligned: a level-1 player wandering into their first coloured town gets a cold
  // shoulder, not an execution. Choosing a faction is the act that arms the map.
  if (!player.faction) return false;
  return !!sanctuary && !servesYou(sanctuary);
}

/**
 * THE WAR-COLOUR OF WHOEVER HOLDS THIS GROUND, or -1 for no-man's-land.
 *
 * Camps used to roll their colour at random, which meant the ring around an Iron town could
 * be pitched with Ash and Vale camps — the bodies outside a town's gate wearing colours the
 * town's own people don't. That reads as the war being decorative: three hues sprinkled over
 * the map rather than three armies holding ground.
 *
 * A town now claims the land around it, and camps inside that claim fly its colour. What this
 * buys is a map you can read from the field: the colour of the first camp you meet tells you
 * whose territory you have walked into, long before a wall comes over the horizon. The gaps
 * BETWEEN claims stay random, and that is deliberate — unclaimed ground is where camps of
 * different colours still meet and fight each other, so the war has a front line instead of
 * being evenly spread confetti.
 */
export function territoryColorAt(x, z) {
  let best = null, bd = MOB.territory;
  for (const s of sanctuariesNear(x, z, MOB.territory)) {
    // A SKY TOWN CLAIMS NO LAND. Its banner flies over its own platform, hundreds of blocks
    // up; the ground under it belongs to whoever holds the ground. Without this a town in the
    // air quietly recoloured the field war happening beneath it.
    if (s.sky) continue;
    if (s.city || s.neutral || s.faction === null || s.faction === undefined) continue;
    const d = Math.hypot(s.x - x, s.z - z);
    if (d < bd) { bd = d; best = s; }
  }
  return best ? FACTIONS[best.faction % FACTIONS.length].ally : -1;
}

/** Which faction flies over this town, by name. Null for neutral ground. */
export function factionOfTown(sanctuary) {
  if (!sanctuary || sanctuary.city || sanctuary.neutral) return null;
  const n = sanctuary.faction;
  if (n === null || n === undefined) return null;
  return FACTIONS[n % FACTIONS.length].id;
}
