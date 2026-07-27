// A DUNGEON IS NOT A PLACE IN THE WORLD. It is a different world, entered in place.
//
// The obvious way to build one is a parallel voxel store: allocate a room, write blocks into
// it, teach the collider to read it, teach the mesher to draw it, teach line of sight to
// consult it. Four systems that already work, taught to work a second way — which is four
// chances for them to disagree, and this codebase has spent a whole day paying for systems
// that computed the same thing two different ways.
//
// So it does none of that. The world is a pure function of coordinates and a seed (D1) that
// everything reads through ONE door, blockAt (D15). A dungeon is simply a DIFFERENT PURE
// FUNCTION behind that same door. Enter one and the fill changes; the streamer rebuilds, and
// movement, sight, the mesher and every effect follow it without being told, because none of
// them ever knew where blocks came from in the first place.
//
// Two things fall out of that for free:
//
//   NO MEMORY. The room you are standing in is computed, not stored — exactly like the
//   mountain it is inside. An instance costs one small object.
//
//   NO DIFFICULTY PLUMBING. It is generated at the GATE'S OWN x,z (just far above the
//   terrain), and tierAt() is a function of x,z — so a dungeon in the mouth of a ring-9
//   mountain is a ring-9 dungeon, and its pressure scales from where you found it with no
//   special case anywhere.
//
// What is here now is ONE EMPTY ROOM, deliberately: the milestone is proving that you can
// walk in, stand in a space the open world cannot see into, and walk back out with the world
// intact. Layout, mobs and loot are the next step and go behind the same door.

import { AIR, STONE, gateOfRing, tierAt } from "./gen.js";
import { mulberry32 } from "../rng.js";
import { DUNGEON } from "../config.js";

/**
 * WHERE THE DOORS ARE: cut into the mountains, one per ring.
 *
 * The placement itself lives in worldgen beside the mountain (gateOfRing), because the
 * mountain has to level the ground under its own doorway and cannot be told about it from
 * out here. This module only decides which of them you are near — a gate is a hole in
 * terrain first and a dungeon entrance second.
 *
 * Ring 0 has no mountain (the Commons is where movement is taught, not where a hundred-block
 * wall of rock goes), so a new player's first gate is ring 1's: a short walk out, visible
 * from most of the way there, and a reason to leave the field you started in.
 */
const GATE_RINGS = 24;              // how far out gates are enumerated when hunting the nearest

/** Every gate near enough to matter, cheapest first. */
export function allGates(aroundRing = 1) {
  const out = [];
  for (let k = Math.max(1, aroundRing - 2); k <= aroundRing + 2 && k <= GATE_RINGS; k++) {
    const g = gateOfRing(k);
    if (g) out.push(g);
  }
  return out;
}

/** The closest gate to a point, or null. What the map's arrow and the door both ask. */
export function nearestGate(x, z) {
  let best = null, bd = Infinity;
  for (const g of allGates(Math.max(1, tierAt(x, z)))) {
    const d = Math.hypot(g.x - x, g.z - z);
    if (d < bd) { bd = d; best = g; }
  }
  return best;
}

/** The instance you are inside, or null out in the world. */
let active = null;

export function activeDungeon() { return active; }
export function inDungeon() { return active !== null; }

/**
 * Build the instance behind a gate. Pure: the same gate always opens the same dungeon, which
 * is what lets it be thrown away and recomputed rather than saved.
 *
 * It keeps the RING it belongs to, and that one field is what makes a dungeon saveable. The
 * room itself never needs storing — it is a pure function of the gate, like the terrain (D1) —
 * so "where was I" collapses to a single number that rebuilds the whole place on load.
 *
 * @param {object} gate  a gate from gateOfRing(): {ring, x, z, seed}
 */
export function makeDungeon(gate) {
  const rng = mulberry32(gate.seed >>> 0);
  // Seeded procedural, starting with the only dimension one room has: its size.
  const hx = DUNGEON.roomMin + Math.floor(rng() * DUNGEON.roomSpan);
  const hz = DUNGEON.roomMin + Math.floor(rng() * DUNGEON.roomSpan);
  const gx = gate.x, gz = gate.z;
  // ONE COLOUR HOLDS IT. Out on the frontier a camp's faction is rolled per camp, because the
  // frontier is a three-sided war and watching two of those sides maul each other is half of
  // what makes it feel like a war. A dungeon is not that: it is somebody's stronghold, and its
  // occupants tearing into one another while you stand in the doorway reads as a bug — which
  // is exactly what it looked like. Rolled from the gate, so a given door always belongs to
  // the same side and you can learn which.
  const faction = Math.floor(rng() * 3);
  const [glo, ghi] = DUNGEON.garrison;
  return {
    ring: gate.ring, seed: gate.seed, gx, gz, faction,
    garrison: glo + Math.floor(rng() * (ghi - glo + 1)),
    slain: 0,                               // how many of them you have already put down
    side: Math.floor(rng() * 4),            // which wall the way out is cut into
    x: Math.round(gx), z: Math.round(gz),
    floor: DUNGEON.y,                       // world Y of the floor you stand on
    hx, hz,
    height: DUNGEON.height,
    exit: null,          // the spot in the world you came from; set on entry
  };
}

/**
 * THE WAY OUT, as a PLACE.
 *
 * Leaving used to be "press F, anywhere" — which meant the room had no geography. You could
 * stand in the far corner with the last of the garrison between you and daylight and simply
 * step out of the world, so nothing inside a dungeon was ever actually between you and
 * anything. A dungeon whose exit is a keypress is a room with a menu in it.
 *
 * So the door is cut into one of the four walls, seeded per gate, and it is the only place the
 * key does anything. You arrive beside it — near enough to see it and to know that is the way
 * back, far enough that getting to it is a short run rather than a reflex.
 *
 * @returns {{x, z, bearing, inX, inZ}|null} the doorway and the direction it faces (into the
 *   room), or null out in the world.
 */
export function dungeonDoor() {
  const d = active;
  if (!d) return null;
  // Middle of one wall. inX/inZ point INTO the room, which is both the way the arch faces and
  // the direction the arrival step is taken in.
  const sides = [
    { x: d.x, z: d.z + d.hz, inX: 0, inZ: -1 },
    { x: d.x, z: d.z - d.hz, inX: 0, inZ: 1 },
    { x: d.x + d.hx, z: d.z, inX: -1, inZ: 0 },
    { x: d.x - d.hx, z: d.z, inX: 1, inZ: 0 },
  ];
  const s = sides[d.side % 4];
  return { ...s, bearing: Math.atan2(-s.inZ, -s.inX) };
}

/** Where you stand the moment you arrive: beside the door, facing into the room. */
export function dungeonEntry() {
  const d = active;
  if (!d) return null;
  const door = dungeonDoor();
  return {
    x: door.x + door.inX * DUNGEON.entryStep,
    y: d.floor,
    z: door.z + door.inZ * DUNGEON.entryStep,
  };
}

/** Are you standing at the way out? The only place leaving is allowed. */
export function atDungeonDoor(x, z) {
  const door = dungeonDoor();
  return !!door && Math.hypot(x - door.x, z - door.z) <= DUNGEON.enterRange;
}

/** Step inside. `from` is where you were standing, so leaving can put you back. */
export function enterDungeon(d, from) {
  active = d;
  d.exit = { x: from.x, y: from.y, z: from.z };
  return dungeonEntry();
}

/** Step back out, and hand back the spot in the world you came from. */
export function leaveDungeon() {
  const back = active?.exit || null;
  active = null;
  return back;
}

/** Which side holds the instance you are in, or null out in the world. */
export function dungeonFaction() { return active ? active.faction : null; }

/**
 * HOW MANY DEFENDERS ARE STILL OWED, given how many are already on their feet.
 *
 * This is what makes a dungeon finishable. The open-world budget asks "is the frontier full
 * enough", which is a question with no end state — the right question inside four walls is
 * "have all of them come out yet", and once the answer is no more, killing the last one means
 * something.
 */
export function dungeonGarrisonLeft(alive = 0) {
  if (!active) return Infinity;
  return Math.max(0, active.garrison - active.slain - alive);
}

/** One of them is down. Counted on the instance, so it survives leaving and reloading. */
export function noteDungeonKill() {
  if (active) active.slain++;
}

/** Put a reloaded tally back. See dungeonState() in main — this is the whole of "progress". */
export function setDungeonSlain(n) {
  if (active) active.slain = Math.max(0, Math.min(active.garrison, n | 0));
}

/** Is it done? Nothing reads this yet; the reward for clearing is the next piece of work. */
export function dungeonCleared() {
  return active ? active.slain >= active.garrison : false;
}

/**
 * Pull a point back inside the walls, or pass it through untouched out in the world.
 *
 * A camp scatters its members MOB.homeWander around its home, which is right on open ground
 * and wrong in a box: the knot straddles the wall and half of it materialises in the void
 * outside, where it can neither reach you nor be reached. The camp's own spot is already
 * chosen inside; this is for the bodies standing around it.
 */
export function clampToRoom(x, z) {
  const d = active;
  if (!d) return { x, z };
  const mx = Math.max(1, d.hx - 1), mz = Math.max(1, d.hz - 1);
  return {
    x: Math.max(d.x - mx, Math.min(d.x + mx, x)),
    z: Math.max(d.z - mz, Math.min(d.z + mz, z)),
  };
}

/**
 * A spot inside the room for a camp to stand, or null out in the world.
 *
 * The open-world spawner deals camps onto a ring 22-58 blocks around you, which is the right
 * shape for open ground and the wrong one for a room: nine attempts in ten landed outside the
 * shell, in the void, and were thrown away. A dungeon is a bounded space, so it answers with a
 * bounded point — inside the walls, and pushed away from whoever is standing in it so a camp
 * never materialises on top of the player.
 *
 * @param {() => number} rng  the spawner's own seeded source; this adds no randomness of its own
 * @param {{x:number, z:number}} away  a point to keep clear of
 */
export function dungeonSpawnPoint(rng, away) {
  const d = active;
  if (!d) return null;
  const mx = Math.max(1, d.hx - 2), mz = Math.max(1, d.hz - 2);
  let best = null, bestD = -1;
  // A few tries, keeping the roomiest. A small room may simply have nowhere far from you, and
  // "the far corner of a cramped room" is the honest answer there rather than no camp at all.
  for (let i = 0; i < 6; i++) {
    const x = d.x + (rng() * 2 - 1) * mx;
    const z = d.z + (rng() * 2 - 1) * mz;
    const dist = Math.hypot(x - away.x, z - away.z);
    if (dist > bestD) { bestD = dist; best = { x, z }; }
    if (dist > 14) break;
  }
  return best;
}

/**
 * THE FILL. Everything the instance is, in one function.
 *
 * Beyond the rock shell it answers AIR rather than STONE, and that is load-bearing rather
 * than cosmetic: the streamer will happily ask about every column for a hundred blocks in
 * each direction, and a dungeon that answered "stone" to all of them would hand the mesher a
 * solid cube the size of the view distance. What is actually here is a small sealed box
 * floating in nothing, which is cheap to build, cheap to draw, and impossible to see out of.
 */
export function dungeonBlockAt(wx, wy, wz) {
  const d = active;
  if (!d) return AIR;
  const lx = wx - d.x, ly = wy - d.floor, lz = wz - d.z;

  // Inside the room: the air you walk through.
  if (ly >= 0 && ly < d.height && Math.abs(lx) <= d.hx && Math.abs(lz) <= d.hz) return AIR;

  // The rock around it. One wall's thickness in every direction, floor and ceiling included.
  const w = DUNGEON.wall;
  const inShell = ly >= -w && ly < d.height + w
                  && Math.abs(lx) <= d.hx + w && Math.abs(lz) <= d.hz + w;
  if (!inShell) return AIR;                  // the void the box floats in

  // THE DOORWAY, bitten out of the wall so the way out is a hole and not a picture of one.
  // Only the inner layers go: the outermost course of stone stays, or the recess would open
  // straight into the void and the first thing anyone did with the exit would be to fall
  // through it. What makes leaving happen is the key at the door (atDungeonDoor), not a gap
  // you can walk through — this is the doorway telling you where that is.
  const door = dungeonDoor();
  if (door && ly >= 0 && ly < DUNGEON.doorH) {
    const dx = wx - door.x, dz = wz - door.z;
    // Distance ALONG the wall, and depth INTO it. inX/inZ point inward, so the along-axis is
    // whichever of the two the door does not face.
    const along = door.inX ? dz : dx;
    const depth = door.inX ? (dx * -door.inX) : (dz * -door.inZ);
    if (Math.abs(along) <= DUNGEON.doorW && depth >= 0 && depth < w - 1) return AIR;
  }
  return STONE;

}

/**
 * The "ground" of an instance — how tall this column is, for everything that asks a column
 * rather than asking a point whether it is solid.
 *
 * IT HAS TO VARY, and that is not a detail. Mobs do not collide with voxels; they navigate by
 * HEIGHT, stepping only where the rise is under MOB.maxClimb (see tryMove). Answering "the
 * floor" for every column in the instance made the walls perfectly flat ground as far as the
 * AI could tell, and the garrison walked straight into the stone and stood inside it.
 *
 * So a wall column is as tall as the wall. The rise into one is the whole height of the room,
 * which no mob can climb, and the existing step test turns them away without a single line in
 * mobs.js knowing that dungeons exist. The player is unaffected either way — the controller
 * collides against real voxels and always did.
 */
export function dungeonHeightAt(wx, wz) {
  const d = active;
  if (!d) return 0;
  const lx = wx - d.x, lz = wz - d.z;
  // Inside the room: the floor you walk on. heightAt is the TOP SOLID block, so +1 is the floor.
  if (Math.abs(lx) <= d.hx && Math.abs(lz) <= d.hz) return d.floor - 1;
  const w = DUNGEON.wall;
  // In the shell: the top of the stonework, a whole room's height above the floor.
  if (Math.abs(lx) <= d.hx + w && Math.abs(lz) <= d.hz + w) return d.floor + d.height + w - 1;
  // The void beyond it. Far below anything, so a step out there reads as a fall no mob will
  // take (MOB.maxDrop) — the shell already encloses them, this is belt and braces.
  return d.floor - 200;
}

/** The world-Y band an instance occupies, so fillChunk can sweep it and nothing else. */
export function dungeonYRange() {
  if (!active) return null;
  const w = DUNGEON.wall;
  return [active.floor - w, active.floor + active.height + w];
}
