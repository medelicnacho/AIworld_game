// Tripwires for the faction weapons — guarding the DESIGN RULES from WEAPONS.md, not the
// numbers. Every assertion here is a sentence from that document turned into something that
// can fail: if a retune quietly breaks one of the agreements that make these three weapons
// three different questions, this is where it gets caught.

import { test } from "node:test";
import assert from "node:assert/strict";
import * as THREE from "three";
import { WEAPONS, SPIN, WHIRL } from "../config.js";
import { FACTIONS, FACTION_WEAPON } from "../prog/factions.js";
import { Gun } from "./gun.js";
import { player } from "../state.js";

// The Gun is pure state until something renders it, so it runs headless — which means the
// carry rules can be tested as rules instead of hoped-for behaviours.
const mkGun = () => new Gun(new THREE.Scene(), new THREE.PerspectiveCamera());

test("every faction teaches exactly one weapon, and each asks a different question", () => {
  const modes = new Set();
  for (const f of FACTIONS) {
    const wid = FACTION_WEAPON[f.id];
    const w = WEAPONS[wid];
    assert.ok(w, `${f.id} maps to a weapon that exists`);
    assert.equal(w.faction, f.id, `${wid} knows whose it is`);
    assert.ok(w.mode, `${wid} has a firing mode — it must not be another hitscan reskin`);
    modes.add(w.mode);
  }
  // Three weapons, three verbs. Two sharing a mode would be the old problem again:
  // adjectives (rate, damage) pretending to be a choice.
  assert.equal(modes.size, FACTIONS.length, "each weapon must be a different KIND of weapon");
});

test("the original four guns are untouched by any of this", () => {
  for (const id of ["rifle", "shotgun", "sniper", "mg"]) {
    assert.equal(WEAPONS[id].mode, undefined, `${id} must stay plain hitscan`);
    assert.equal(WEAPONS[id].faction, undefined, `${id} belongs to nobody`);
  }
});

test("faction weapons cost a fortune — the price IS the gate", () => {
  for (const wid of Object.values(FACTION_WEAPON)) {
    assert.ok(WEAPONS[wid].price >= 500,
      `${wid} must be a real purchase, not an impulse buy (${WEAPONS[wid].price})`);
  }
});

test("SPIN: untouchable is a WINDOW, and uptime stays on the game's budget", () => {
  // The whole argument: everything else in this game is safe about a quarter of the time
  // (dodge 0.2s/0.7s, Whirlwind 3.6s/13s). If the spin's guarded window over its FLOORED
  // cooldown ever exceeds that, haste stacking walks it toward permanent invulnerability —
  // which deletes every telegraph in the game.
  assert.ok(SPIN.iframes < SPIN.time, "the guard must end before the spin does");
  assert.ok(SPIN.iframes / SPIN.cdFloor <= 0.25 + 1e-9,
    `guarded uptime at the haste floor is ${(SPIN.iframes / SPIN.cdFloor).toFixed(2)} — over budget`);
  assert.ok(SPIN.cdFloor > 0, "haste has no ceiling; the floor is the rail");
});

test("SPIN: sustained damage loses to swinging, and to Whirlwind", () => {
  const spinPerSec = SPIN.damage / SPIN.tick;
  const cleaver = WEAPONS.cleaver;
  const swingPerSec = cleaver.damage * cleaver.fireRate;
  // Under the cleaver: if spinning out-damages swinging on one target, the spin becomes the
  // whole rotation and the cone stops being the weapon.
  assert.ok(spinPerSec < swingPerSec * 0.8,
    `spin ${spinPerSec}/s must clearly lose to swinging ${swingPerSec}/s`);
  // Under Whirlwind: a purchased spell on a long cooldown must stay the heavier hitter, or
  // a free weapon attack outclasses something the player paid for.
  const whirlPerSec = WHIRL.spinDamage / WHIRL.spinTick;
  assert.ok(spinPerSec < whirlPerSec,
    `spin ${spinPerSec}/s must stay under Whirlwind's ${whirlPerSec}/s`);
});

test("LOBBER: never hurts you — the cost is leading the shot, not fear", () => {
  const w = WEAPONS.lobber;
  assert.equal(w.selfDamage, false, "an explosive fired like a sidearm must not punish being close");
  assert.ok(w.speed > 0 && w.blastRadius > 0 && w.blastDamage > 0);
  // The safety valve on "strictly better grenade": the splash must stay TIGHTER than a
  // grenade's, because difficulty is the only cost this weapon has left.
  assert.ok(w.blastRadius < 6.5, "the lobber's splash must stay tighter than a grenade's");
});

test("LOADOUT: you carry two, and buying a third swaps the one in your HANDS", () => {
  const g = mkGun();
  assert.deepEqual(g.loadout, ["rifle"], "you start carrying only the starter");
  g.acquire("shotgun");
  assert.deepEqual([...g.loadout].sort(), ["rifle", "shotgun"], "the second purchase fills the free hand");
  assert.equal(g.weapon.id, "shotgun", "and a new weapon lands in your hands");
  // Buying a third replaces what you are HOLDING — the holstered weapon is the one you
  // deliberately kept, and it must never be silently discarded.
  g.acquire("sniper");
  assert.ok(g.loadout.includes("sniper"));
  assert.ok(g.loadout.includes("rifle"), "the holstered rifle survives the purchase");
  assert.ok(!g.loadout.includes("shotgun"), "the shotgun you were holding is what got swapped out");
  assert.ok(g.owned.has("shotgun"), "...but it is still OWNED — it went to the bag, not the bin");
});

test("LOADOUT: the wheel is a toggle between the two carried, never a carousel", () => {
  const g = mkGun();
  g.acquire("shotgun");
  g.acquire("sniper");     // owns three, carries rifle + sniper
  const first = g.weapon.id;
  g.cycle();
  const second = g.weapon.id;
  assert.notEqual(first, second, "the wheel must change hands");
  g.cycle();
  assert.equal(g.weapon.id, first, "two flicks of the wheel must bring the first weapon back");
  assert.ok(!["rifle", "sniper"].includes("shotgun"), "the bagged weapon never appears in the cycle");
});

test("LOADOUT: equip refuses weapons that are not carried; carry() is the door", () => {
  const g = mkGun();
  g.acquire("shotgun");
  g.acquire("sniper");     // shotgun now bagged
  g.equip("shotgun");
  assert.notEqual(g.weapon.id, "shotgun", "a bagged weapon cannot be equipped directly");
  g.carry("shotgun");
  assert.equal(g.weapon.id, "shotgun", "carrying it first is what brings it to hand");
});

test("LOADOUT: a restored loadout keeps only what is actually owned", () => {
  const g = mkGun();
  g.acquire("cleaver");
  g.setLoadout(["cleaver", "lance", "nonsense"]);     // lance never bought
  assert.deepEqual(g.loadout, ["cleaver"], "unowned and unknown weapons are dropped");
});

test("SWING: the height you cut at follows where you look", () => {
  // The request, verbatim: "the hit box should change when you are looking up or down".
  // Sideways the swing stays a fixed wide arc — that is a swing's nature — but the vertical
  // band it covers is centred on your pitch.
  const g = mkGun();
  g.owned.add("cleaver");
  g.loadout = ["cleaver"];
  g.equip("cleaver");
  player.x = 0; player.y = 0; player.z = 0;

  const level = { x: 0, y: 0, z: -1 };                       // looking straight ahead
  const up50 = { x: 0, y: Math.sin(0.87), z: -Math.cos(0.87) };   // looking well up

  const ahead = { id: 1, x: 0, y: 1.1, z: -4, r: 0.5 };      // chest height, in front
  const high = { id: 2, x: 0, y: 5.6, z: -3, r: 0.5 };       // up a ledge, ~56° above
  const feet = { id: 3, x: 0, y: 0, z: -3, r: 0.5 };         // at your feet
  const behind = { id: 4, x: 0, y: 1.1, z: 4, r: 0.5 };      // behind you

  const ids = (fwd, targets) => g.swing(fwd, targets).map((t) => t.id);

  assert.deepEqual(ids(level, [ahead, high, behind]), [1],
    "looking level: you hit what is ahead, not the ledge above, never behind");
  assert.deepEqual(ids(up50, [ahead, high, feet]), [2],
    "looking up: the cut moves up — the ledge is in reach, and your feet are not");
  assert.ok(ids(level, [feet]).includes(3),
    "looking level still catches things at your feet — the band is generous, not a razor");
});

test("LANCE: heat makes it a weapon you manage, not a hose", () => {
  const w = WEAPONS.lance;
  assert.ok(w.heatUp > 0 && w.heatDown > 0 && w.overheatLock > 0);
  const secondsToRedline = 1 / w.heatUp;
  // Long enough to be a weapon, short enough to be a decision.
  assert.ok(secondsToRedline >= 2, `redline in ${secondsToRedline.toFixed(1)}s is too twitchy`);
  assert.ok(secondsToRedline <= 6, `redline in ${secondsToRedline.toFixed(1)}s barely exists`);
  assert.ok(w.aimMult > 1, "aiming must pay, or RMB means nothing on this weapon");
});
