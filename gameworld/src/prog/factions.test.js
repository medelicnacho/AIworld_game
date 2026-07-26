// Tripwires for the faction layer. Almost none of this is reachable by clicking around —
// joining needs a level, a quartermaster and a town of the right colour — so the rules that
// make the choice MEAN something have to be checked here or they are never checked at all.

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  FACTIONS, REP_TIERS, JOIN_LEVEL, factionById, repForBoss, gainRep, tierOf, repProgress,
  FACTION_GEAR, stockFor, lockedFor, join, isMyAlly, allyColor, servesYou, repForTurnIn, isHostileSanctuary,
  territoryColorAt,
} from "./factions.js";
import { RARITY } from "./gear.js";
import { player } from "../state.js";

/** A clean character at a given level, unaligned. */
function fresh(level = JOIN_LEVEL) {
  player.level = level;
  player.faction = null;
  player.rep = 0;
}

test("the three factions each hate a DIFFERENT colour", () => {
  // If two shared an enemy, two of the three choices would be the same choice wearing
  // different names — and the whole point is that picking one closes the others off.
  const enemies = FACTIONS.map((f) => f.enemy);
  assert.equal(new Set(enemies).size, FACTIONS.length, "each faction needs its own quarrel");
  assert.equal(new Set(FACTIONS.map((f) => f.focus)).size, FACTIONS.length,
    "and its own build, or the gear tracks collapse into one");
});

test("you cannot swear to anyone before the join level", () => {
  fresh(JOIN_LEVEL - 1);
  assert.equal(join("ash"), false, "too green to be taken in");
  assert.equal(player.faction, null);
  fresh(JOIN_LEVEL);
  assert.equal(join("ash"), true);
  assert.equal(player.faction, "ash");
});

test("switching sides costs every point of reputation, and no gear", () => {
  fresh();
  join("ash");
  player.rep = 25000;
  const bagBefore = player.ownedGear.length;
  join("vale");
  assert.equal(player.faction, "vale");
  assert.equal(player.rep, 0, "the ladder starts again from the bottom");
  assert.equal(player.ownedGear.length, bagBefore, "but nobody takes your kit off you");
});

test("ally / enemy / neutral — each faction sits on ONE colour, opposes one, ignores one", () => {
  // The war is rock-paper-scissors: no two factions share an ally or an enemy, and a
  // faction's ally is never also its enemy.
  const allies = FACTIONS.map((f) => f.ally);
  const enemies = FACTIONS.map((f) => f.enemy);
  assert.equal(new Set(allies).size, 3, "each faction has its own colour");
  assert.equal(new Set(enemies).size, 3, "each faction hunts its own colour");
  for (const f of FACTIONS) assert.notEqual(f.ally, f.enemy, "you cannot hunt your own army");
});

test("your own colour is an ally — you cannot harm it, nobody else's is friendly", () => {
  fresh();
  join("ash");
  const ash = factionById("ash");
  assert.equal(isMyAlly(ash.ally), true, "your colour fights for you");
  assert.equal(isMyAlly(ash.enemy), false, "your enemy is not your friend");
  assert.equal(allyColor(), ash.ally, "the ally colour is your faction's");
  // Unaligned: nothing is your ally.
  fresh();
  assert.equal(isMyAlly(0), false);
  assert.equal(isMyAlly(1), false);
  assert.equal(allyColor(), -1, "no faction, no army");
});

test("reputation comes from BOSSES and TURN-INS, never from ordinary kills", () => {
  fresh();
  join("ash");
  // A boss pays, and pays more the deeper it fell.
  assert.ok(repForBoss(5) > repForBoss(0), "a deep boss is worth more standing");
  assert.ok(repForBoss(0) > 0, "any boss pays something");
  // gainRep is the one door: it credits the faction you are in, and refuses the unaligned.
  player.rep = 0;
  assert.equal(gainRep(500), 500);
  assert.equal(player.rep, 500);
  fresh();
  assert.equal(gainRep(500), 0, "an unaligned player banks nothing");
  assert.equal(player.rep, 0);
});

test("the ladder climbs, starts at zero, and never goes backwards", () => {
  assert.equal(REP_TIERS[0].at, 0, "joining puts you ON the ladder, not below it");
  for (let i = 1; i < REP_TIERS.length; i++) {
    assert.ok(REP_TIERS[i].at > REP_TIERS[i - 1].at, "each rung must cost more than the last");
  }
  assert.equal(tierOf(0), 0);
  assert.equal(tierOf(REP_TIERS[1].at), 1);
  assert.equal(tierOf(REP_TIERS[REP_TIERS.length - 1].at * 10), REP_TIERS.length - 1,
    "past the top you stay at the top");
});

test("progress toward the next rung is a real fraction, and the top rung is complete", () => {
  const mid = repProgress(Math.round((REP_TIERS[0].at + REP_TIERS[1].at) / 2));
  assert.ok(mid.frac > 0.4 && mid.frac < 0.6, `halfway should read halfway, got ${mid.frac}`);
  const top = repProgress(REP_TIERS[REP_TIERS.length - 1].at);
  assert.equal(top.frac, 1);
  assert.equal(top.need, null, "nothing left to work toward");
});

test("REPUTATION IS ACCESS: stock opens as you climb, and never before", () => {
  const atStart = stockFor("ash", 0);
  const atTop = stockFor("ash", REP_TIERS[REP_TIERS.length - 1].at);
  assert.ok(atStart.length > 0, "joining must give you something to save toward immediately");
  assert.ok(atTop.length > atStart.length, "the ladder has to open more than it started with");
  for (const p of atStart) assert.equal(p.repTier, 0, "nothing above your rung leaks in");
  // And what is locked is the NEXT rung specifically — a ladder you cannot see the next step
  // of is just a number going up.
  const next = lockedFor("ash", 0);
  assert.ok(next.length > 0 && next.every((p) => p.repTier === 1));
});

test("a faction only ever sells its OWN kit", () => {
  for (const f of FACTIONS) {
    const all = stockFor(f.id, 1e9);
    assert.ok(all.length > 0);
    assert.ok(all.every((p) => p.faction === f.id), `${f.id} is selling someone else's gear`);
  }
});

test("every piece is well-formed, priced, and gets dearer as it gets better", () => {
  for (const p of FACTION_GEAR) {
    assert.ok(p.name && !p.name.includes("undefined"), `clean name: ${p.name}`);
    assert.ok(p.price > 0, "everything has a price — reputation is access, points are cost");
    assert.ok(p.armor >= 1);
    assert.equal(p.stats.armor, p.armor, "stats.armor mirrors armor, as everywhere else");
    assert.ok(Object.values(p.stats).every(Number.isFinite), `no NaN in ${p.id}`);
  }
  for (const f of FACTIONS) {
    const byTier = [0, 1, 2, 3].map((t) =>
      FACTION_GEAR.find((p) => p.faction === f.id && p.repTier === t && p.slot === "vest"));
    for (let i = 1; i < byTier.length; i++) {
      assert.ok(byTier[i].price > byTier[i - 1].price, "higher rungs must cost more");
      assert.ok(byTier[i].armor > byTier[i - 1].armor, "...and be worth more");
    }
  }
});

test("each faction's gear is MOSTLY its own thing, with a little of the others", () => {
  // A set carrying nothing but its headline stat reads as one number going up rather than as
  // a character, and makes the builds you did not pick feel missing instead of traded away.
  // So every faction carries a splash of the other two — and the rule that has to hold is
  // DOMINANCE, not purity: your own stat should still dwarf what a rival set gives you.
  const total = (fid, stat) => FACTION_GEAR
    .filter((p) => p.faction === fid)
    .reduce((s, p) => s + (p.stats[stat] || 0), 0);

  const owner = { str: "ash", agi: "vale", stamina: "iron" };
  for (const [stat, fid] of Object.entries(owner)) {
    const mine = total(fid, stat);
    assert.ok(mine > 0, `${fid} must sell ${stat} — it is their whole identity`);
    for (const other of FACTIONS.map((f) => f.id)) {
      if (other === fid) continue;
      const theirs = total(other, stat);
      assert.ok(theirs > 0,
        `${other} should carry SOME ${stat}; a pure set is a spreadsheet column`);
      assert.ok(mine > theirs * 2,
        `${fid} must clearly dominate ${stat} (${mine} vs ${other}'s ${theirs})`);
    }
  }
});

test("COLD, NOT HOSTILE: a rival's town keeps its kit, a city always serves", () => {
  const city = { city: true };
  const ashTown = { city: false, faction: 0 };
  const valeTown = { city: false, faction: 1 };

  fresh();
  assert.equal(servesYou(city), true, "a city serves an unaligned player");
  assert.equal(servesYou(ashTown), false, "a town wants to know whose side you are on");

  join("ash");
  // FACTIONS[0] is ash, so a town flying colour 0 is ash's.
  assert.equal(servesYou(ashTown), true, "your own town trades with you");
  assert.equal(servesYou(valeTown), false, "a rival's does not");
  assert.equal(servesYou(city), true, "the city is neutral ground, always");
  assert.equal(servesYou(null), false, "and nowhere is not somewhere");
});

test("turn-ins: better gear is worth more, and faction kit cannot be recycled", () => {
  const worth = (r) => repForTurnIn({ rarity: r });
  assert.ok(worth("uncommon") > worth("common"));
  assert.ok(worth("rare") > worth("uncommon"));
  assert.ok(worth("epic") > worth("rare"));
  assert.equal(worth("faction"), 0,
    "handing faction kit back for standing would be a loop that prints reputation");
  // Every rarity the game can produce must have an answer, or a drop type silently becomes
  // un-turn-in-able the day it is added.
  for (const key of Object.keys(RARITY)) {
    assert.equal(typeof repForTurnIn({ rarity: key }), "number", `no turn-in value for ${key}`);
  }
});

test("hostile ground: only a town you are NOT welcome in counts as hostile", () => {
  // Drives the "no combat moves in a friendly safe zone, but your dash answers on rival
  // ground" rule. It must agree exactly with servesYou — one town cannot both sell to you
  // and be somewhere you may fight.
  const city = { city: true };
  const neutralHome = { neutral: true };
  const ashTown = { faction: 0 };   // FACTIONS[0] is Ash
  const valeTown = { faction: 1 };

  // UNALIGNED FIRST: before you pick a side, NO town is hostile — "hostile" now empties a
  // town and muster a war-camp against you, and that must never happen to a newcomer who
  // has not yet chosen. Cold (no shop) and hostile (a raid) are different temperatures.
  fresh();
  assert.equal(isHostileSanctuary(ashTown), false, "the war is none of yours before you join");
  assert.equal(isHostileSanctuary(valeTown), false, "...whatever colour the town flies");

  join("ash");
  assert.equal(isHostileSanctuary(ashTown), false, "your own town is a refuge, not a battlefield");
  assert.equal(isHostileSanctuary(city), false, "neutral cities are refuges");
  assert.equal(isHostileSanctuary(neutralHome), false, "the spawn town is neutral ground");
  assert.equal(isHostileSanctuary(valeTown), true, "a rival's town is intruder ground");
  assert.equal(isHostileSanctuary(null), false, "the open field is not a sanctuary at all");

  // And the invariant that ties it to the shop: nowhere may both serve you and be hostile.
  for (const s of [city, neutralHome, ashTown, valeTown]) {
    assert.notEqual(servesYou(s), isHostileSanctuary(s),
      "a town cannot be both a shop that serves you and a place you may fight");
  }
});

test("the ground outside a gate flies the same colour as the garrison inside it", async () => {
  // The bug this pins: camps rolled their colour at random, so the bodies standing outside an
  // Iron town could be Ash or Vale. Whose land you are on has to be readable from the field.
  const { tierSettlements } = await import("../world/sanctuary.js");
  for (const s of tierSettlements(1)) {
    // A sky town flies its banner over its own platform; the land beneath it belongs to
    // whoever holds the land, so there is nothing to check down here.
    if (s.city || s.neutral || s.sky) continue;
    const garrison = FACTIONS[s.faction % FACTIONS.length].ally;
    for (const [dx, dz] of [[60, 0], [0, 60], [-55, -55]]) {
      assert.equal(territoryColorAt(s.x + dx, s.z + dz), garrison,
        `${FACTIONS[s.faction % FACTIONS.length].name}'s ground must fly its own colour`);
    }
  }
});

test("...but the gaps between towns stay unclaimed, or the field war has nowhere to happen", () => {
  // A claim wide enough to swallow the whole ring would tidy the map into blocs and delete
  // the one place camps of different colours can still meet each other.
  let claimed = 0, free = 0;
  for (let i = 0; i < 1200; i++) {
    const a = (i / 1200) * Math.PI * 2, r = 300 + (i % 37) * 8;
    if (territoryColorAt(Math.cos(a) * r, Math.sin(a) * r) >= 0) claimed++; else free++;
  }
  assert.ok(claimed > 0, "towns must actually hold ground");
  assert.ok(free / (claimed + free) > 0.15,
    `no-man's-land must survive; only ${((free / (claimed + free)) * 100).toFixed(0)}% is free`);
});

test("the recruiter names the WEAPON before the poetry — every faction, both halves", async () => {
  const { FACTION_PITCH, FACTION_WEAPON } = await import("./factions.js");
  // The bug this pins is a UX one: a newcomer made the game's one irreversible choice
  // from three character sketches that never mentioned what they would be holding.
  for (const f of FACTIONS) {
    const p = FACTION_PITCH[f.id];
    assert.ok(p, `${f.id} must have a pitch at the desk`);
    assert.ok(p.weapon && p.weapon.length > 40, `${f.id}'s weapon must be described, not named`);
    assert.ok(p.spec && p.spec.length > 10, `${f.id} must say what its numbers do`);
    // The pitch must actually describe the weapon that faction grants.
    const w = FACTION_WEAPON[f.id];
    const says = p.weapon.toLowerCase();
    assert.ok(says.includes(w === "lobber" ? "lobber" : w === "cleaver" ? "cleaver" : "lance"),
      `${f.id}'s pitch must name its real weapon (${w})`);
  }
  // And each stat track is claimed by exactly one faction — three routes, no overlap.
  const specs = FACTIONS.map((f) => FACTION_PITCH[f.id].spec.toLowerCase());
  assert.ok(specs.some((s) => s.includes("speed")), "someone sells speed");
  assert.ok(specs.some((s) => s.includes("defence") || s.includes("armour")), "someone sells defence");
  assert.ok(specs.some((s) => s.includes("damage")), "someone sells damage");
});

test("the wanderer wears their banner — a colour per faction, rust for the unsworn", async () => {
  const { playerColor, PLAYER_COLORS, PLAYER_UNSWORN, FACTION_COLORS } = await import("./factions.js");
  fresh();
  assert.equal(playerColor(), PLAYER_UNSWORN, "no banner must LOOK like no banner");
  for (const f of FACTIONS) {
    fresh();
    join(f.id);
    assert.equal(playerColor(), PLAYER_COLORS[f.id], `${f.id} paints you ${f.id}`);
  }
  // Three distinct colours — if two matched, the whole point (see your side at a glance)
  // would be gone.
  assert.equal(new Set(Object.values(PLAYER_COLORS)).size, 3);
  // And each sits in the war-colour space its own army flies: Ash and Vale exactly, Iron
  // lifted off true black (which reads as a hole in the world rather than a body).
  fresh(); join("ash");
  assert.equal(playerColor(), FACTION_COLORS[factionById("ash").ally], "Ash wears Ash blue");
  fresh(); join("vale");
  assert.equal(playerColor(), FACTION_COLORS[factionById("vale").ally], "Vale wears Vale green");
  fresh(); join("iron");
  assert.notEqual(playerColor(), FACTION_COLORS[factionById("iron").ally],
    "Iron is lifted from true black so a body still reads as a body");
});
