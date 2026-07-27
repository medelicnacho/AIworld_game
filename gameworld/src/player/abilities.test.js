// THE BAR IS SUPPOSED TO BE TOO SMALL.
//
// For most of this game's life it was not: ten slots, and ten abilities to put in them. Every
// piece of that was individually reasonable and the sum of it was that buying a spell and
// carrying a spell were the same act, so the loadout screen never asked a question. These
// tests pin the RELATIONSHIP rather than either number, because the failure is silent — add a
// key, retire a spell, and the bar quietly becomes a formality again with nothing to notice.

import test from "node:test";
import assert from "node:assert/strict";

import { Abilities, SLOTS, SLOT_KEYS } from "./abilities.js";
import { GOODS } from "../ui/shop.js";

/**
 * Every ability you can end up owning AT ONCE, measured by buying the whole shop.
 *
 * Counting the vendor's list instead would be wrong and would look right: `replaces` lives
 * inside the closure each entry hands to acquire(), not on the entry, so a shelf of thirteen
 * is ten abilities and three upgrades to ones already there. acquire() is the only thing that
 * knows which — so ask it, rather than keeping a second opinion here.
 */
function ownable() {
  const a = new Abilities({});
  for (const g of GOODS.adept || []) g.apply({ abilities: a });
  // Heal and the grenade are granted in main.js rather than sold, and always occupy a slot.
  return a.owned.length + 2;
}

test("you cannot carry everything you own", () => {
  assert.ok(
    SLOTS < ownable(),
    `${SLOTS} slots for ${ownable()} abilities — a bar you can fill completely is not a loadout`,
  );
});

test("every bar key is reachable without the left hand leaving WASD", () => {
  // The game is played mid-jump. A slot on a key you must reach for is one you will not cast
  // at the moment it mattered, which makes it a menu wearing a hotbar's clothes.
  const reachable = new Set(["Q", "E", "R", "F", "C", "1", "2", "3", "4", "5"]);
  for (const k of SLOT_KEYS) {
    assert.ok(reachable.has(k), `bar key ${k} needs the hand to move`);
  }
});

test("the two you are given never fall off a full bar", () => {
  // Shrinking the bar truncates saved loadouts, and a character built when it was ten slots
  // long can have its heal past the new end. Dropping it leaves someone spawning with no heal
  // key and no explanation — so a starter takes a slot by force, and the spell it displaces is
  // still in the bag.
  const a = new Abilities({});
  for (let i = 0; i < SLOTS; i++) a.acquire({ id: `spell${i}`, name: `Spell ${i}`, use() {} });
  assert.equal(a.firstFree(), -1, "the bar should be full for this test to mean anything");

  const heal = { id: "heal", name: "Heal", starter: true, use() {} };
  a.owned.push(heal);
  assert.equal(a.equip(-1, heal), false, "there is genuinely no free slot");

  const displaced = a.slots[SLOTS - 1];
  a.equip(SLOTS - 1, heal);
  assert.ok(a.slots.some((s) => s?.id === "heal"), "heal ends up on the bar");
  assert.ok(a.owned.includes(displaced), "and the spell it pushed off is still owned");
});

test("an ability left in the bag keeps recovering", () => {
  // Leaving a spell at home has to be a choice about THIS fight, not a punishment that follows
  // you — otherwise swapping at a vendor costs you a cooldown and nobody ever experiments.
  const a = new Abilities({});
  const def = { id: "orb", name: "Orb", cd: 10, use() {} };
  a.acquire(def);
  a.use(a.slots.findIndex((s) => s?.id === "orb"));
  assert.ok(a.stateOf(def).cd > 0, "using it starts the cooldown");

  a.slots.fill(null);           // taken off the bar entirely
  a.update(4);
  assert.ok(a.stateOf(def).cd <= 6.001, "it ticked down while sitting in the bag");
});
