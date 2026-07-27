// ENERGY — the shared cost the ability bar never had.
//
// The failure state this is built around is NOT the empty bar. Nobody dies to an empty bar;
// they die to a plan that needed one more cast. So what these pin is the RHYTHM: that energy
// is what actually limits the small spells (a cooldown sitting behind a cost is invisible —
// whichever is longer is the only one anyone feels), that a burst runs out where it should,
// and that escape never costs anything.

import test from "node:test";
import assert from "node:assert";
import { ENERGY, NOVA, DASH, CHAIN, FIRERING, RANK2, WHIRL, HEAL, GRENADE } from "../config.js";
import { Abilities } from "./abilities.js";
import { GOODS } from "../ui/shop.js";

test("energy, not cooldown, is what limits the small spells", () => {
  for (const [name, cost, cd] of [
    ["Dash", ENERGY.dash, DASH.cd], ["Nova", ENERGY.nova, NOVA.cd], ["Chain", ENERGY.chain, CHAIN.cd],
  ]) {
    assert.ok(cost / ENERGY.regen > cd,
      `${name}: its ${cd}s cooldown outlasts its cost, so the cost is a bar nobody feels`);
  }
});

// Explosion USED to be the exception that proved the rule — the one big button gated by a
// fifteen-second cooldown rather than by its price. That was reversed in play (2026-07-27):
// it now casts on a one-second cooldown for the dearest cost on the bar, which puts it under
// the same law as everything else. The exception is gone, so what is pinned here is that it
// went all the way over rather than landing in the invisible middle: a spell whose cooldown
// and cost are comparable is a spell where neither is felt.
test("even the big button is limited by its price now, not its cooldown", () => {
  assert.ok(ENERGY.firering / ENERGY.regen > FIRERING.cd,
    "Explosion's cost must outlast its cooldown, or the price is a bar nobody feels");
  // Dearer than everything a character OWNS at level one, which is the tier it has to be
  // rationed against: at a one-second cooldown its price is the only brake, and the widest
  // radius in the kit must never be the cheapest way to spend a bar. (Chain costs more
  // still, and that is fine — it is a different promise: single-target reach, not a room.)
  for (const [name, cost] of [["Dash", ENERGY.dash], ["Heal", ENERGY.heal],
                              ["Grenade", ENERGY.grenade], ["Nova", ENERGY.nova]]) {
    assert.ok(ENERGY.firering > cost,
      `Explosion must cost more than ${name} — it clears the room, and it does so every second`);
  }
  // ...and dear enough that a full bar cannot pour out three of them.
  assert.ok(ENERGY.max / ENERGY.firering < 3,
    "a full bar must not fund three Explosions — the widest radius in the kit needs a real floor");
});

// The exact edge the design is built around: an opener spends most of the bar and leaves you
// enough for one small thing, never for a repeat of the big one.
test("a burst leaves you short of a second big spell", () => {
  const after = ENERGY.max - ENERGY.nova - ENERGY.dash;
  assert.ok(after > 0, "an opener must not empty the bar outright");
  assert.ok(after < ENERGY.nova, "there must never be room for a second Nova");
});

test("you are never left standing about", () => {
  assert.ok(ENERGY.max / ENERGY.regen < 6,
    `empty to full takes ${(ENERGY.max / ENERGY.regen).toFixed(1)}s — the punishment is the ` +
    "cast you could not make, not a wait");
});

// THE TWO YOU START WITH. Heal and the grenade were free while they lived on their own keys
// outside the bar; as spells they pay like spells, and the whole point of the price is that
// panicking costs you. What must stay true is that neither one can be spammed on the bar's
// own terms — the ENERGY has to be the thing that says no, exactly as above.
test("the starter spells are limited by their cost, not by a cooldown", () => {
  for (const [name, cost, cd] of [
    ["Heal", ENERGY.heal, HEAL.cooldown], ["Grenade", ENERGY.grenade, GRENADE.cooldown],
  ]) {
    assert.ok(cost > 0, `${name} is a spell now — a free spell is a key you mash`);
    assert.ok(cost / ENERGY.regen > cd,
      `${name}: its ${cd}s cooldown outlasts its cost, so the cost is a bar nobody feels`);
  }
});

// You always have both, so between them they must not be able to empty the bar in one breath
// and leave you with no escape — the resource is meant to punish a bad plan, not the opening.
test("heal and a grenade together still leave you a dash", () => {
  assert.ok(ENERGY.max - ENERGY.heal - ENERGY.grenade >= ENERGY.dash,
    "the two abilities everyone owns must not spend the whole bar between them");
});

// The one addition worth keeping from the expensive-dash detour: the abilities you ESCAPE with
// are the ones this resource does not govern at all, and that absence is the guarantee. A cost
// appearing here for any of them turns a mistake into a death sentence, which ENERGY forbids
// in its own comment.
test("the tools you escape with are never priced", () => {
  for (const free of ["dodge", "kick", "potion", "sprint"]) {
    assert.equal(ENERGY[free], undefined, `${free} must stay free — it is how you survive a bad plan`);
  }
});

// Being punished for a misjudgement is the point. Losing the tool that would let you survive
// it is not — that turns a mistake into a death sentence.
test("whirlwind is affordable from a full bar, and never runs dry mid-spin", () => {
  assert.ok(ENERGY.whirl <= ENERGY.max, "it must be castable at all");
  // The old assertion here — "invulnerability should cost more than damage" — was retired by
  // decree: Whirlwind is priced as a rhythm spell now, paired with Dash, and the ration on
  // being untouchable is its long cooldown rather than its price. What must still hold is
  // that the pair leaves room to mend, or the melee sentence ends every fight at zero.
  assert.ok(ENERGY.max - ENERGY.dash - ENERGY.whirl >= ENERGY.heal,
    "dash + whirl must leave a heal behind");
  // Charged up front, so the spin's length is irrelevant to whether it can finish.
  assert.ok(WHIRL.spinTime > 0);
});

// AN UPGRADE MAY SHARPEN A SPELL; IT MAY NEVER DELETE THE PRICE. Rank defs replace the base
// ability wholesale (see acquire), so a rank that forgets to declare `energy` silently makes
// the spell FREE — which happened to Explosion II, and read in play as "every spell has a
// weird delay except Explosion". The bug is invisible in code because the field is simply
// absent; this walks every replacement chain and demands the cost survives the upgrade.
test("no rank upgrade drops its spell out of the economy", () => {
  const a = new Abilities({});
  const seen = new Map();          // id -> def, in shop order (base before its ranks)
  for (const g of GOODS.adept || []) {
    const before = new Set(a.owned.map((o) => o.id));
    g.apply({ abilities: a });
    for (const d of a.owned) if (!before.has(d.id)) seen.set(d.id, d);
  }
  for (const d of seen.values()) {
    if (!d.replaces) continue;
    const base = seen.get(d.replaces);
    if (!base || base.energy === undefined) continue;   // a free line stays free — its call
    assert.equal(d.energy, base.energy,
      `${d.id} replaces ${d.replaces} but changes its energy cost from ${base.energy} to ${d.energy}`);
  }
});

// A RANK MUST NEVER BE A DOWNGRADE. Explosion II sold a shorter cooldown (11s against rank
// 1's 15) until rank 1 dropped to one second — at which point two hundred and ten points
// bought you an eleven-times-longer wait. That is the failure mode a rank system produces
// every time a base number moves and its ranks do not follow, so it gets a tripwire rather
// than a promise to remember.
test("Explosion II is never worse than the Explosion you already own", () => {
  assert.ok(RANK2.fireringCd <= FIRERING.cd,
    `rank 2 waits ${RANK2.fireringCd}s against rank 1's ${FIRERING.cd}s — an upgrade that downgrades`);
});
