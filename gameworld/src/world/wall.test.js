// A town wall is ten blocks tall, not infinitely tall.
//
// wallBlocks answers "is there a wall at this x,z" and nothing more, which was complete while
// nothing in the game could get above ten blocks. Once the sky filled with islands you could
// stand two hundred blocks over a town and be stopped by an invisible barrier reaching to the
// top of the world — and, worse, be refused a jump INTO a town from above.

import test from "node:test";
import assert from "node:assert";
import { wallBlocks, wallBlocksBody, tierSettlements, boundaryAt, WALL_H, sanctuaryUnder } from "./sanctuary.js";
import { groundY } from "./gen.js";
import { PLAYER, SETTLE } from "../config.js";

/** A point standing in the wall of the spawn town, away from its gate. */
function onTheWall() {
  const s = tierSettlements(0)[0];
  for (let i = 0; i < 720; i++) {
    const ang = (i / 720) * Math.PI * 2;
    const r = boundaryAt(s, ang);
    const x = s.x + Math.cos(ang) * r, z = s.z + Math.sin(ang) * r;
    if (wallBlocks(x, z)) return { x, z, g: groundY(x, z) };
  }
  return null;
}

test("the test needs an actual wall to stand in", () => {
  assert.ok(onTheWall(), "no wall found around the spawn town");
});

test("at ground level a wall still stops you", () => {
  const w = onTheWall();
  assert.ok(wallBlocksBody(w.x, w.g, w.z, PLAYER.height), "walls must still be walls");
});

test("stepping up onto it does not get you through", () => {
  const w = onTheWall();
  for (let dy = 0; dy < WALL_H - PLAYER.height; dy += 1) {
    assert.ok(wallBlocksBody(w.x, w.g + dy, w.z, PLAYER.height),
      `a body ${dy} blocks up is still inside a ${WALL_H}-block wall`);
  }
});

// THE BUG. Above the parapet there is nothing but air, and air is what you move through.
test("above the wall you are free — you can fly over, and drop in", () => {
  const w = onTheWall();
  assert.ok(!wallBlocksBody(w.x, w.g + WALL_H + 1, w.z, PLAYER.height),
    "just over the parapet must be open");
  assert.ok(!wallBlocksBody(w.x, w.g + 60, w.z, PLAYER.height),
    "sixty blocks up must be open");
  assert.ok(!wallBlocksBody(w.x, w.g + 200, w.z, PLAYER.height),
    "an island two hundred blocks over a town is not its wall");
});

test("open ground is open at every height", () => {
  const s = tierSettlements(0)[0];
  const far = { x: s.x + s.rMax + 60, z: s.z };
  for (const y of [0, 20, 120]) {
    assert.ok(!wallBlocksBody(far.x, groundY(far.x, far.z) + y, far.z, PLAYER.height));
  }
});

// A TOWN IS A PLACE ON THE GROUND. Being "in a sanctuary" was a purely flat question, which
// made a hover two hundred blocks over a town the safest spot in the world — every rule that
// keys off sanctuary (damage immunity, stowed weapons, whether the garrison cares) inherited
// it. Above SETTLE.roof you are in the sky, and the sky belongs to nobody.
test("a town's protection has a ceiling", () => {
  const s = tierSettlements(0)[0];
  const g = groundY(s.x, s.z);
  assert.ok(sanctuaryUnder(s.x, g, s.z), "standing in the square is in town");
  assert.ok(sanctuaryUnder(s.x, g + SETTLE.roof - 1, s.z),
    "and so is anywhere you could jump to from inside");
  assert.equal(sanctuaryUnder(s.x, g + SETTLE.roof + 1, s.z), null, "just above the roof is sky");
  assert.equal(sanctuaryUnder(s.x, g + 200, s.z), null, "an island over a town is not the town");
});

test("the ceiling clears anything reachable from inside the walls", () => {
  // Walls are WALL_H tall and a double jump adds ~2.5 — ordinary play must never touch this.
  const reach = WALL_H + PLAYER.jumpSpeed ** 2 / (2 * -PLAYER.gravity) * 2;
  assert.ok(SETTLE.roof > reach + 4,
    `roof ${SETTLE.roof} is too close to the ${reach.toFixed(1)} you can reach from the wall`);
});

test("outside a town, height changes nothing", () => {
  const s = tierSettlements(0)[0];
  const far = { x: s.x + s.rMax + 80, z: s.z };
  for (const y of [0, 30, 300]) {
    assert.equal(sanctuaryUnder(far.x, groundY(far.x, far.z) + y, far.z), null);
  }
});

// UNDER A TOWN IS NOT IN IT. The roof test bounded only the top, so the ground far beneath a
// sky town counted as inside its walls: nothing could hurt you there, while the frontier
// around you went on spawning camps and bosses, because those ask a different question.
test("a sky town protects its platform, not the world beneath it", () => {
  const sky = tierSettlements(2).find((s) => s.sky);
  assert.ok(sky, "tier 2 must have a sky town to test");
  const floor = sky.plateau + 1;
  assert.ok(sanctuaryUnder(sky.x, floor, sky.z), "standing in its square is in town");
  assert.ok(sanctuaryUnder(sky.x, floor + SETTLE.roof - 2, sky.z), "and just under its roof");
  assert.equal(sanctuaryUnder(sky.x, floor - SETTLE.cellar - 2, sky.z), null,
    "just below its slab is already outside");
  assert.equal(sanctuaryUnder(sky.x, groundY(sky.x, sky.z), sky.z), null,
    "and the LAND beneath it is open frontier, not a refuge");
});

test("a town on the ground is unchanged by any of this", () => {
  const s = tierSettlements(1).find((q) => !q.sky && !q.city);
  const g = groundY(s.x, s.z);
  assert.ok(sanctuaryUnder(s.x, g, s.z), "you are in town when you are in town");
  assert.ok(sanctuaryUnder(s.x, g + 4, s.z), "and while you are jumping in it");
  assert.equal(sanctuaryUnder(s.x, g + SETTLE.roof + 4, s.z), null, "the sky above it is sky");
});

// A POLYGON'S EDGES DIP INSIDE ITS CORNERS. The collision test used the smallest corner as an
// early-out and skipped anything nearer, so every stretch of wall that passed closer than that
// was a hole you walked straight through — measured at 28 units deep on a city.
test("no stretch of any wall is inside the collision early-out", () => {
  for (let t = 0; t <= 6; t++) {
    for (const s of tierSettlements(t)) {
      let minR = Infinity;
      for (let i = 0; i < 720; i++) minR = Math.min(minR, boundaryAt(s, (i / 720) * Math.PI * 2));
      assert.ok(s.rInner <= minR + 0.5,
        `${s.id}: rInner ${s.rInner.toFixed(1)} claims more than the wall's true ${minR.toFixed(1)}`);
    }
  }
});

test("you cannot walk through a wall anywhere along it", () => {
  const s = tierSettlements(1).find((q) => !q.city && !q.sky);
  const g = groundY(s.x, s.z);
  let solid = 0;
  for (let i = 0; i < 720; i++) {
    const ang = (i / 720) * Math.PI * 2;
    const r = boundaryAt(s, ang);
    const x = s.x + Math.cos(ang) * r, z = s.z + Math.sin(ang) * r;
    if (wallBlocksBody(x, g, z, PLAYER.height)) solid++;
  }
  // Everything but the gateway has to stop you. One doorway is a few percent of the ring.
  assert.ok(solid / 720 > 0.9, `only ${(solid / 720 * 100).toFixed(0)}% of the wall line blocks`);
});

// A SHOVE MUST NOT PARK A BODY IN THE STONE. wallOk asked only which side of a boundary a mob
// was on — the right question for "may it enter the town" and no question at all about the
// wall itself, which is a band of solid either side of that line. You could watch a mob
// standing waist-deep in masonry after a knockback.
test("a mob cannot be pushed into a wall, but one already in it can leave", async () => {
  const THREE = await import("three");
  const { Mobs } = await import("../mobs/mobs.js");
  const mobs = new Mobs(new THREE.Scene(), 0x5A11, {});
  const s = tierSettlements(1).find((q) => !q.city && !q.sky);
  const g = groundY(s.x, s.z);

  // A point standing in the wall, away from the gate.
  let inWall = null;
  for (let i = 0; i < 720 && !inWall; i++) {
    const ang = (i / 720) * Math.PI * 2;
    const r = boundaryAt(s, ang);
    const x = s.x + Math.cos(ang) * r, z = s.z + Math.sin(ang) * r;
    if (wallBlocks(x, z)) inWall = { x, z, ang, r };
  }
  assert.ok(inWall, "the town must have a wall to test");

  // Standing outside, shoved at it: refused.
  const outside = {
    x: s.x + Math.cos(inWall.ang) * (inWall.r + 8),
    z: s.z + Math.sin(inWall.ang) * (inWall.r + 8),
    y: g, defender: false,
  };
  assert.equal(mobs.wallOk(outside, inWall.x, inWall.z), false,
    "a body outside must not be shoved into the stone");

  // Already stuck in it: allowed out, or a stranded body is welded there for ever.
  const stuck = { x: inWall.x, z: inWall.z, y: g, defender: false };
  assert.ok(mobs.wallOk(stuck, outside.x, outside.z), "a stranded body must be able to leave");
});
