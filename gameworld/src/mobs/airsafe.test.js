// THE AIR IS SUPPOSED TO BE ANSWERABLE — nothing on the ground may hit a player it cannot
// reach. This family of bug has now been found FOUR times in one codebase: the charge's
// 36-block hit cylinder, the lunge riding the same 18-block allowance, burning ground as an
// infinite column, and the player's own grenade with its vertical term scaled backwards. Each
// looked correct in code and each was found in the hands, so what gets pinned here is not any
// one number but the RELATIONSHIPS between them — the things that break silently when someone
// retunes a jump, a hover, or a slab three months from now.

import test from "node:test";
import assert from "node:assert/strict";

import { MOB, PLAYER } from "../config.js";

// How high one press of Space carries you: v²/2g, the only honest measure of "in the air".
const apex = (PLAYER.jumpSpeed * PLAYER.jumpSpeed) / (2 * -PLAYER.gravity);

test("a single jump clears grounded melee — the air is an answer, not a place to die", () => {
  assert.ok(MOB.meleeClearY < apex,
    `meleeClearY ${MOB.meleeClearY} must sit under the ${apex.toFixed(2)}-block jump apex, ` +
    "or no height a player can reach escapes a bite from the floor");
});

test("a hunting flyer sits ABOVE the grounded gate — the exemption is load-bearing", () => {
  // A flyer's resting attack height is player.y + flyChaseLift (± flyBob). If that ever drops
  // under meleeClearY the special flyer gate in mobs.js becomes dead code — harmless. If this
  // test fails the other way after someone deletes that gate as "redundant", flyers cannot
  // land a hit at all: their by-design hover keeps them outside the grounded rule forever.
  assert.ok(MOB.flyChaseLift + MOB.flyBob > MOB.meleeClearY,
    "the hover the flyer keeps while hunting exceeds the grounded melee gate — " +
    "which is exactly why mobs.js derives a separate reach for it");
});

test("the lunge commits only at what it could plausibly reach", () => {
  // Looser than the connect gate (the ground resolves as the lunge travels) but bounded by
  // what the lunge can actually cross — lungeSpeed × lungeTime of travel cannot climb more
  // terrain than it covers. A start gate far above that is mobs hopping at unreachable air,
  // which spends the game's "you are about to be hit" tell on non-threats.
  const travel = MOB.lungeSpeed * MOB.lungeTime;
  assert.ok(MOB.lungeStartY >= MOB.meleeClearY, "may start anywhere it could connect");
  assert.ok(MOB.lungeStartY <= travel + 1,
    `lungeStartY ${MOB.lungeStartY} should not far exceed the ~${travel.toFixed(1)} blocks ` +
    "a lunge travels — past that it is committing at air it cannot cross");
});

test("burning ground can be jumped", () => {
  // The fire slab's whole design (see MOB.fireHeight) is that clearing a patch mid-stride is
  // a real option. That claim was written when the jump was 1.36 and nothing re-checked it —
  // this does, against whatever the jump is NOW.
  assert.ok(MOB.fireHeight < apex,
    `fireHeight ${MOB.fireHeight} must stay under the ${apex.toFixed(2)}-block jump apex, ` +
    "or standing in fire and jumping over it become the same mistake");
});
