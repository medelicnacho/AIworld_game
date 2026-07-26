// A town wall is ten blocks tall, not infinitely tall.
//
// wallBlocks answers "is there a wall at this x,z" and nothing more, which was complete while
// nothing in the game could get above ten blocks. Once the sky filled with islands you could
// stand two hundred blocks over a town and be stopped by an invisible barrier reaching to the
// top of the world — and, worse, be refused a jump INTO a town from above.

import test from "node:test";
import assert from "node:assert";
import { wallBlocks, wallBlocksBody, tierSettlements, boundaryAt, WALL_H } from "./sanctuary.js";
import { groundY } from "./gen.js";
import { PLAYER } from "../config.js";

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
