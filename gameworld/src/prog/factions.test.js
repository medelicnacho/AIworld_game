// Tripwires for the faction layer. Almost none of this is reachable by clicking around —
// joining needs a level, a quartermaster and a town of the right colour — so the rules that
// make the choice MEAN something have to be checked here or they are never checked at all.

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  FACTIONS, REP_TIERS, JOIN_LEVEL, factionById, repForKill, tierOf, repProgress,
  FACTION_GEAR, stockFor, lockedFor, join, awardRep, isMyEnemy, servesYou, repForTurnIn,
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

test("only your enemy's colour pays — this is the whole choice", () => {
  fresh();
  join("ash");
  const ash = factionById("ash");
  assert.ok(isMyEnemy(ash.enemy));
  const paid = awardRep(ash.enemy, 3, false);
  assert.ok(paid > 0, "your enemy pays");
  const before = player.rep;
  for (const f of FACTIONS) {
    if (f.enemy === ash.enemy) continue;
    assert.equal(awardRep(f.enemy, 8, true), 0, "everyone else pays nothing, however deep");
  }
  assert.equal(player.rep, before, "and nothing was quietly added anyway");
});

test("an unaligned player earns nothing from anyone", () => {
  fresh();
  for (const f of FACTIONS) assert.equal(awardRep(f.enemy, 5, true), 0);
  assert.equal(player.rep, 0);
});

test("kills pay more the deeper they die, and much more for a star", () => {
  assert.ok(repForKill(5, false) > repForKill(0, false), "depth pays");
  assert.ok(repForKill(0, true) > repForKill(0, false) * 2, "a star pays a lot more");
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

test("each faction's gear actually pulls its own way", () => {
  const has = (fid, stat) => FACTION_GEAR
    .filter((p) => p.faction === fid)
    .some((p) => p.stats[stat] > 0);
  assert.ok(has("ash", "str"), "the damage faction sells Strength");
  assert.ok(has("vale", "agi"), "the speed faction sells Agility");
  assert.ok(has("iron", "stamina"), "the survival faction sells Stamina");
  // ...and does NOT sell the others' identity, or the three tracks blur into one.
  assert.ok(!has("iron", "str"), "survival gear should not be a damage set in disguise");
  assert.ok(!has("ash", "stamina"), "damage gear should not quietly be the tank set");
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
