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

// The key is a NUMBER, not a string. Measured in a staged 700-body war: the flocking scan
// alone asked for buckets thousands of times a frame, and every ask minted a fresh
// "12,-3"-style string — the sim was spending real frame time manufacturing garbage for
// the collector. A grid cell packs into one exact integer (unique for |cell| < 32768,
// which at 24 units a cell is ~780k world units of frontier — the despawn ring will never
// see the edge). Same Map, same buckets, no alloc per ask.
export const gridKey = (gx, gz) => (gx + 0x8000) * 0x10000 + (gz + 0x8000);
export const regionKey = (x, z) =>
  gridKey(Math.floor(x / REGION_SIZE), Math.floor(z / REGION_SIZE));

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
  // How far the eye is still BEHIND the feet after an auto step-up, in blocks. Purely
  // cosmetic — nothing in the sim may read this.
  stepLift: 0,
  // The spell budget. See ENERGY — it governs offence only, never escape.
  energy: 100,
  // Inside a friendly settlement's walls. Set each frame from main's sanctuary test; the
  // controller reads it to drop your speed stats (not your jumps) while you are in a town.
  inTown: false,
  jumpsLeft: 2,
  sprinting: false,
  dodgeT: 0, dodgeCd: 0, iframes: 0, dodgeX: 0, dodgeZ: 0,
  // The cleaver's right-click spin. Transient combat state, never saved.
  spinT: 0, spinCd: 0,
  // The lance's, which is a different animal despite the name — see LANCE_SPIN. Kept as its
  // own pair rather than shared with the cleaver's: they run different lengths, different
  // cooldowns and different guards, and one weapon's spin ending must never be able to cancel
  // the other's just because you switched guns mid-swing.
  lanceSpinT: 0, lanceSpinCd: 0,
  // Dash carries a vertical component too, so looking up throws you up. Y is separate from
  // dashX/dashZ because everything else about the dash is a flat heading.
  dashT: 0, dashX: 0, dashY: 0, dashZ: 0,
  leapT: 0, leapX: 0, leapZ: 0, leapPending: false, whirlT: 0,
  hp: 100, maxHp: 100,
  level: 1, xp: 0, dmgMult: 1, speedMult: 1, jumpMult: 1, maxJumps: 2,
  // The wall kick's committed arc — see DODGE.kickHold.
  kickT: 0, kickX: 0, kickZ: 0,
  surgeT: 0,
  points: 0, potions: 0, potionCd: 0, gearDmg: 0,
  // GEAR: five equipment slots (one piece each) and everything you own. All the stats across
  // worn pieces are SUMMED into the fields below by recomputeGear() — armor, the attributes,
  // the four damage buckets, and the three secondary ratings — then applyLevelStats derives
  // the effects. These are outputs of the gear sum; do not write them directly.
  gearSlots: { helm: null, shoulders: null, vest: null, pants: null, boots: null },
  ownedGear: [],
  armor: 0, stamina: 0, str: 0, agi: 0,
  dmgGlobal: 0, dmgGun: 0, dmgSpell: 0, dmgGrenade: 0, moveSpeed: 0,
  rHaste: 0, rAtkSpeed: 0, rReload: 0, graceMitigation: 0, sprintT: 0,
  haste: 0, hasteFire: 1, hasteCd: 1, hasteCast: 1, gearSpeed: 0, gearReload: 0,
  dashRank: 0, dashMult: 1, upgrades: {},
  // FACTION. null while unaligned, which is a supported way to play forever — you simply
  // have no ladder. `rep` is standing with the faction you are in NOW; switching zeroes it.
  faction: null, rep: 0,
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
      const ids = world.regions.get(gridKey(cx + dx, cz + dz));
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
