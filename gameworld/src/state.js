// Sockets 2 and 3 (PLAN.md M1).
//
// SOCKET 2 — sim state is not render state. Gameplay data lives in plain records here; the
// renderer READS them and owns nothing. That seam is where a mob brain (M1) and a soul brain
// (M3) later plug into the same body, and why the substrate can arrive without a rewrite.
//
// SOCKET 3 — entities are bucketed by REGION, not held in one flat list. Free at M1 scale;
// it is the exact shape the settlement Workers need at M3, where a region is the unit of
// simulation cost (PLAN.md §3: cost tracks local density, so density must be addressable).

import { PLAYER } from "./config.js";
import { groundY } from "./world/gen.js";

// 24, not 128. Flocking asks for neighbours within ~10 units, and at 128 that query
// returned nearly every mob on the map — which is O(n²) once there are 340 of them, and
// exactly the frame-time collapse that makes the audio stutter. Small buckets make the
// question local again.
export const REGION_SIZE = 24;   // world units per region bucket

export const regionKey = (x, z) =>
  `${Math.floor(x / REGION_SIZE)},${Math.floor(z / REGION_SIZE)}`;

export const world = {
  time: 0,
  entities: new Map(),        // id -> entity record
  regions: new Map(),         // regionKey -> Set<id>
  nextId: 1,
};

export const player = {
  id: 0,
  kind: "player",
  x: 0, y: 0, z: 0,
  vx: 0, vy: 0, vz: 0,
  yaw: 0, pitch: 0,
  onGround: false,
  jumpsLeft: 2,
  sprinting: false,
  dodgeT: 0, dodgeCd: 0, iframes: 0, dodgeX: 0, dodgeZ: 0,
  dashT: 0, dashX: 0, dashZ: 0,
  leapT: 0, leapX: 0, leapZ: 0, leapPending: false, whirlT: 0,
  hp: 100, maxHp: 100,
  level: 1, xp: 0, dmgMult: 1, speedMult: 1, jumpMult: 1, maxJumps: 2,
  surgeT: 0,
  points: 0, potions: 0, potionCd: 0, gearDmg: 0, armor: 0, dmgTakenMult: 1,
  haste: 0, hasteFire: 1, hasteCd: 1, hasteCast: 1, gearSpeed: 0, gearReload: 0, upgrades: {},
};

export function spawnPlayer() {
  player.x = 0.5;
  player.z = 0.5;
  player.y = groundY(player.x, player.z) + 0.5;
  player.vx = player.vy = player.vz = 0;
}

export function addEntity(e) {
  const id = world.nextId++;
  const rec = { id, hp: 1, vx: 0, vy: 0, vz: 0, ...e };
  world.entities.set(id, rec);
  rec._region = regionKey(rec.x, rec.z);
  bucket(rec._region).add(id);
  return rec;
}

export function removeEntity(id) {
  const e = world.entities.get(id);
  if (!e) return;
  world.regions.get(e._region)?.delete(id);
  world.entities.delete(id);
}

/** Call after moving an entity so its region bucket stays correct. */
export function reindex(e) {
  const k = regionKey(e.x, e.z);
  if (k === e._region) return;
  world.regions.get(e._region)?.delete(e.id);
  bucket(k).add(e.id);
  e._region = k;
}

function bucket(k) {
  let s = world.regions.get(k);
  if (!s) world.regions.set(k, (s = new Set()));
  return s;
}

/** Iterate entities in the regions touching a radius — the update loop's unit of work. */
export function* nearby(x, z, radius = REGION_SIZE) {
  const r = Math.ceil(radius / REGION_SIZE);
  const cx = Math.floor(x / REGION_SIZE), cz = Math.floor(z / REGION_SIZE);
  for (let dz = -r; dz <= r; dz++) {
    for (let dx = -r; dx <= r; dx++) {
      const ids = world.regions.get(`${cx + dx},${cz + dz}`);
      if (!ids) continue;
      for (const id of ids) {
        const e = world.entities.get(id);
        if (e) yield e;
      }
    }
  }
}

export const playerAABB = () => ({
  r: PLAYER.radius,
  h: PLAYER.height,
});
