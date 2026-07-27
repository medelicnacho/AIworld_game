// The distance tick, and the caster's vertical patience.
//
// Two rules born from the same playtest ("big fights lag, and the sky is full of ranged
// mobs that don't add much"): attention costs what it is worth, and a caster's fight is on
// its own floor. Both are relationships between constants, and relationships are exactly
// what quiet retuning breaks — so they are pinned here the way the SPIN gap is.

import test from "node:test";
import assert from "node:assert";
import { tickStride } from "./mobs.js";
import { MOB } from "../config.js";

const calm = { aggro: false };
const fighting = { aggro: true };
const NEAR = 10;
const FAR = MOB.farTick + 1;
const CALM_FAR = MOB.calmTick + 1;

test("a body next to you always thinks at full rate", () => {
  assert.equal(tickStride(calm, NEAR), 1);
  assert.equal(tickStride(fighting, NEAR), 1);
});

test("far theatre strides; the calm stride further than the fighting", () => {
  assert.equal(tickStride(fighting, FAR), MOB.farStride);
  assert.equal(tickStride(calm, CALM_FAR), MOB.calmStride);
  assert.ok(MOB.calmStride >= MOB.farStride,
    "a milling camp must never think MORE often than a fighting one at the same distance");
});

// A committed attack is a promise about where a body will be. Promises are kept at full
// rate — a charge updated every other frame teleports through the moment you dodge it.
test("committed states never stride, however far away", () => {
  for (const state of [{ leapT: 1 }, { lungeT: 1 }, { windT: 1 }, { rushT: 1 },
                       { recoverT: 1 }, { castT: 1 }, { burstLeft: 2 }, { playerHurtT: 0.2 }]) {
    assert.equal(tickStride({ aggro: true, ...state }, FAR), 1,
      `${Object.keys(state)[0]} must hold full rate`);
    assert.equal(tickStride({ aggro: false, ...state }, CALM_FAR + 1000), 1);
  }
});

// "Just hurt" means hurt BY YOU. War blows set the same red flash, and if the flash were
// the exemption, a giant brawl would exempt itself entirely — the bigger the fight, the
// less the stride would do, which is backwards.
test("the war flashing itself red does not buy full attention", () => {
  assert.equal(tickStride({ aggro: true, hurtT: 0.2 }, FAR), MOB.farStride,
    "a body hurt by the WAR strides like any other far body");
  assert.equal(tickStride({ aggro: true, hurtT: 0.2, playerHurtT: 0.2 }, FAR), 1,
    "a body hurt by the PLAYER never strides");
});

// A giant fight is mostly not about you: bodies locked on another mob are a fight you
// watch, and past arm's length a watched brawl decides at half rate invisibly.
test("the war is theatre from arm's length out", () => {
  const brawler = { aggro: true, warFoeId: 7 };
  assert.equal(tickStride(brawler, MOB.warTick + 1), MOB.farStride);
  assert.equal(tickStride(brawler, MOB.warTick - 1), 1,
    "a brawl AT arm's length is on screen and stays frame-perfect");
  assert.ok(MOB.warTick < MOB.farTick,
    "the war strides sooner than a body hunting YOU ever does");
});

// In a stampede the floors give way — a crowd too big to watch individuals is a crowd
// where nobody can tell who is thinking. What concerns YOU never strides regardless.
test("the stampede drops every floor except yours", () => {
  const brawler = { aggro: true, warFoeId: 7 };
  const hunter = { aggro: true };                   // hunting the player, no war target
  const calm = { aggro: false };
  assert.equal(tickStride(brawler, 5, true), MOB.stampedeStride,
    "a stampede brawl strides even at your feet — and deepest of all");
  assert.ok(MOB.stampedeStride >= MOB.farStride,
    "the stampede war stride is never lighter than the ordinary far stride");
  assert.equal(tickStride(calm, 5, true), MOB.calmStride);
  assert.equal(tickStride(hunter, 5, true), 1,
    "a body hunting YOU at knife range is frame-perfect even in a stampede");
  assert.equal(tickStride(hunter, MOB.warTick + 1, true), MOB.farStride,
    "a stampede chaser past arm's reach strides — its lunge snaps it back via commitment");
  assert.equal(tickStride({ ...brawler, playerHurtT: 0.2 }, 5, true), 1,
    "the just-shot exemption outranks the stampede");
});

test("striding starts past clear-read distance, inside the despawn ring", () => {
  assert.ok(MOB.calmTick < MOB.despawn && MOB.farTick < MOB.despawn,
    "a stride threshold past despawn is a stride that never happens");
  assert.ok(MOB.calmTick > MOB.spawnMin,
    "a camp can spawn at spawnMin — it must arrive thinking at full rate");
});

// The caster's vertical patience: it must end before its range does, and it must out-reach
// melee upward, or terraces stop being contested and the bow stops meaning anything.
test("a caster gives up vertically before its shot gives out", () => {
  assert.ok(MOB.castVert < MOB.castMax,
    "patience past the edge of its own shot is the treadmill this rule exists to kill");
  assert.ok(MOB.castVert > MOB.meleeClearY,
    "ranged must contest ledges that melee cannot — that is what makes it ranged");
});

// "Reduce the ranged mobs in the sky by a lot" — the ask, encoded. If someone tunes the
// keep-rate back above a third, the sky is growing its artillery back and this should argue.
test("the sky keeps at most a fifth of its bows", () => {
  assert.ok(MOB.skyCasterKeep <= 0.2,
    `skyCasterKeep is ${MOB.skyCasterKeep} — the sky garrison is meant to be a melee fight`);
});
