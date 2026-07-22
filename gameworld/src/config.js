// Tunables in one place. Anything a designer would want to feel out belongs here.

export const WORLD_SEED = 1337;

// Chunk dimensions. Y is the full world height — the world is read-only (D1), so a
// chunk is a column, never a stack, and there is no vertical streaming to write.
export const CHUNK_X = 16;
export const CHUNK_Y = 80;
export const CHUNK_Z = 16;

export const VIEW_RADIUS = 7;          // chunks loaded around the player
export const CHUNKS_PER_FRAME = 2;     // build budget — keeps frame time flat while streaming

// Terrain shape
export const SEA_LEVEL = 24;
export const BASE_HEIGHT = 30;
export const CONTINENT_SCALE = 0.0035;  // big landforms
export const CONTINENT_AMP = 20;
export const HILL_SCALE = 0.02;         // local relief
export const HILL_AMP = 6;

// D8: difficulty is legible. Rings are named, visibly tinted bands of distance from
// spawn — not a smooth invisible gradient. Mob tables, loot, and (later) settlement
// harshness all key off ringAt().
// 260, not 400: at a walk of ~5-8 u/s, 400 units meant ~60s of travel IN A STRAIGHT LINE
// before you left the Commons, and wandering never gets there at all — you can circle for
// ten minutes and stay in ring 0. A ring should be a journey, not a commute.
export const RING_SIZE = 260;           // world units per ring
export const RINGS = [
  { name: "the Commons",  tint: [1.00, 1.00, 1.00] },
  { name: "the Fallows",  tint: [0.96, 0.98, 0.88] },
  { name: "the Reach",    tint: [0.90, 0.94, 0.86] },
  { name: "the Waste",    tint: [0.96, 0.88, 0.78] },
  { name: "the Ashlands", tint: [0.88, 0.78, 0.74] },
  { name: "the Deep",     tint: [0.74, 0.72, 0.82] },
];

// Player physics
export const PLAYER = {
  radius: 0.35,
  height: 1.8,
  eye: 1.62,
  walkSpeed: 5.2,
  sprintSpeed: 8.0,
  accel: 45,
  friction: 12,
  gravity: -26,
  jumpSpeed: 8.4,
  jumps: 2,             // ground jump + this many air jumps - 1
  airJumpScale: 0.92,   // air jumps slightly weaker, so the first one still feels best
  maxFall: -60,
};

// D6: one hitscan gun. A raycast — no ballistics, no projectile pooling. Everything here
// is a stat a level-up card will later multiply (D9), which is why they're all named.
export const GUN = {
  damage: 12,
  fireRate: 7.5,        // shots per second, hold to fire
  magSize: 18,
  reloadTime: 1.15,
  range: 220,
  recoil: 0.016,        // radians kicked up per shot
  recoilRecover: 0.75,  // fraction of the kick that drifts back down
  spreadHip: 0.022,     // radians of cone — the third-person/hip penalty
  spreadAim: 0.002,     // ADS is near-exact, and that IS the reward for D4's camera pull
};

// D9 — endless levels, and the economy that makes distance the real progression.
//
// The curve is the design. Level cost grows as level^1.55 while a trash mob's value is
// FLAT for its ring, so early on four mobs is a level and by level 20 it's a hundred.
// Elite value scales the same way but starts 7× higher, so elites overtake trash as the
// backbone of progress — while packs of small ones still meaningfully top you up during a
// fight. Both stay worth killing; only their ROLE changes.
export const XP = {
  mobBase: 12,
  perRing: 0.9,        // a ring-3 mob is worth 12 × (1 + 2.7) = 44
  eliteMult: 7,
  bossBase: 900,
  bossPerRing: 0.8,

  curveBase: 50,
  curveExp: 1.55,      // L1→2: 50 xp · L5: 572 · L10: 1774 · L20: 5200

  // Interim level rewards. D9's real answer is a 1-of-3 card pick — this keeps levelling
  // FELT until that UI exists, and is meant to be replaced by it, not kept.
  // Levels buy MOBILITY, not bulk. Max HP never moves, so a meteor is as lethal at level 40
  // as at level 4 and survival stays a question of reading telegraphs rather than of having
  // a bigger bar. What you gain is the ability to be somewhere else.
  hpPerLevel: 0,
  speedGrowth: 1.02,      // L10 ×1.22 · L20 ×1.49 · L35 ×2.00
  jumpGrowth: 1.015,      // L20 ×1.35 launch = ~1.8× the height (h scales with v²)
  jumpsPerLevels: 10,     // +1 air jump at 10, 20, 30, …
  // COMPOUNDING, not additive. Mob HP grows 55% per ring and levelling is what carries you
  // outward, so a flat +6%/level meant getting relatively weaker the further you went.
  // 9% compounding: L5 ×1.4 · L10 ×2.2 · L20 ×5.1 · L35 ×18.7 — it outruns ring HP slowly,
  // which is the power fantasy without erasing the danger.
  damageGrowth: 1.09,
};

// Q — the heal. A 1.5s channel that ROOTS you, breaks if you move, and breaks if you're
// hit. In a game whose every other verb is movement, the cost of standing still is the
// whole design: it turns the boss's volley gaps into the window you're hunting for.
export const HEAL = {
  castTime: 1.5,
  amount: 45,
  cooldown: 12,
  breakOnDamage: true,
};

// Grenade: your answer to a crowd, and the only thing in the game that can kill YOU by
// your own hand. Supply refills on kills, so using it is rewarded by fighting, not hoarding.
export const GRENADE = {
  throwSpeed: 19,
  upBias: 0.28,          // arcs instead of flying flat
  gravity: -26,          // matches the player's, so the arc reads as the same world
  radius: 6.5,
  damage: 90,
  selfScale: 0.5,        // you take half — dangerous, not instantly lethal
  cooldown: 2.2,
  maxFuse: 4.0,          // safety net; ground contact is the real trigger
  max: 3,
  refillPerKill: 1,
  knockback: 11,
};

// D7: mobs are SOULLESS. Stats roll from the ring they spawn in; no memory, no bonds, no
// substrate — the emergent layer arrives at M3 and lands on settlements, not on things you
// kill in three seconds.
export const MOB = {
  hp: 30,
  damage: 8,
  speed: 3.1,
  // They live their own lives until you give them a reason. Notice range is SHORT, and the
  // leash is measured from HOME, not from you — mirroring how the lab's souls are held by
  // their own place and people rather than by the player (world/sim.py _drift_positions).
  noticeRange: 20,
  leashRange: 62,         // drag them this far from home and they give up and go back
  loseInterest: 7.0,      // seconds out of contact before disengaging
  alertRadius: 15,        // hurt one and its pack hears about it
  homeWander: 8,          // how far they mill around their camp when idle
  homePull: 1.1,
  attackRange: 2.4,
  attackCd: 1.15,
  lungeTime: 0.28,
  lungeSpeed: 9.5,
  radius: 0.55,
  knockback: 5.5,

  // Per-ring multipliers — D8's difficulty gradient, expressed as numbers.
  hpPerRing: 0.55,
  damagePerRing: 0.40,
  speedPerRing: 0.06,

  // ★elites: rarer near spawn, common in the deep. Valheim's star system, which is the
  // cheapest legible "this one is worse" signal there is.
  eliteChance: 0.06,
  eliteChancePerRing: 0.06,   // ring 5: 36% elite — the deep is mostly stars
  // Elites get tougher the further out they are, on TOP of the flat per-tier HP every mob
  // gets — so a star near spawn is a speed bump and a star in the deep is a real fight.
  eliteHp: 2.2,
  eliteHpPerRing: 0.15,   // tier 5 star: ×2.95 · tier 10: ×3.7
  eliteDamage: 1.5,
  eliteScale: 1.55,

  // --- steering: emergent movement, no substrate required -------------------------
  // The brain decides INTENT (close, hold, lunge); these decide HOW the body gets there.
  // Same seam as PLAN §4 — a mob brain and a soul brain will drive the same locomotion.
  neighborRadius: 10,     // who counts as "nearby" for flocking
  separation: 2.8,        // below this they actively push apart — no stacking, ever
  sepForce: 3.4,
  alignForce: 1.0,        // match your neighbours' heading: a pack moves as one body
  cohesionForce: 0.45,    // stragglers rejoin rather than trickling in alone
  // ENCIRCLEMENT: they steer to a slot on a ring around you, not to your feet. This is
  // what makes a group spread out and surround instead of forming a queue.
  ringRadius: 6.0,
  ringForce: 2.4,
  slotSpread: 2.4,        // radians of arc a pack fans across
  // COURAGE FROM NUMBERS: alone they circle at range; in a pack they commit. Emergent
  // "they gather, then they come" — nothing scripts the wave.
  packCourage: 3,
  timidStandoff: 11.0,
  // One mob committing makes its neighbours more likely to follow within the second.
  contagion: 0.45,
  maxClimb: 1.15,         // blocks it can step up; steeper terrain must be walked around
  avoidArc: 1.05,         // radians it will veer to find a walkable line

  // Population around the player. Cost is bounded by COUNT, not by world size.
  // Packs, not scattered individuals: a camp of 3-6 that mills, flocks, and BREEDS.
  maxAlive: 20,
  maxPacks: 3,
  packSize: [3, 6],
  packCap: 9,             // a camp can grow this large before it stops breeding
  breedEvery: [55, 120],  // seconds between a mob's offspring (idle only, never mid-fight)
  spawnMin: 34,
  spawnMax: 62,
  despawn: 105,
  spawnInterval: 2.5,
};

// D10 — the giant boss. ONE reusable rig, re-dressed per ring. Everything here is tuned
// around a single rule: the fight must be long enough that its pattern becomes legible,
// and every source of damage must be avoidable by a player who reads the telegraph.
export const BOSS = {
  // Base was 1800 with +80%/tier, which made your FIRST boss (tier 1) a 3240 HP slog at
  // level 3 — a minute-plus of holding the trigger, which is tedium, not difficulty.
  // Halved the base and steepened the distance term instead: the frontier, not the floor,
  // is where a boss gets terrifying.
  //   tier 1: 1700 · tier 3: 3400 · tier 5: 5100 · tier 10: 9350
  hp: 850,
  hpPerRing: 1.0,
  speed: 1.7,             // slow — you can always outrun it; the meteors are the threat
  scale: 6.0,
  contactRange: 6.5,
  contactDamage: 26,
  contactCd: 1.4,
  weakMultiplier: 2.5,    // the glowing core: aim is rewarded, spraying is not
  aggroRange: 90,
  spawnDist: [45, 70],
  spawnRing: 1,           // no bosses in the Commons — it stays the safe ground
  retry: 12,              // seconds between spawn attempts once you're eligible
  despawn: 190,

  // Meteor volleys.
  volleyCd: 4.6,
  chargeTime: 1.25,       // audible + visible wind-up BEFORE the ground markers appear
  roarEvery: [7, 13],     // ambient roars while it's alive and near — dread on a timer
  volleyCount: 5,
  volleyPerRing: 1,
  phase2At: 0.5,          // below this HP fraction: faster volleys, more rocks
  phase2Rate: 0.6,
  phase2Bonus: 3,

  meteorTelegraph: 1.30,  // seconds the ground marker shows BEFORE the rock lands
  meteorFall: 0.45,       // seconds from sky to impact once it's committed
  meteorHeight: 46,
  meteorRadius: 3.6,
  meteorDamage: 34,
  meteorScatter: 9,       // spread around the aim point
  meteorAtPlayer: 0.6,    // fraction aimed at you; the rest rain around the boss
  shake: 0.55,
};

// Dodge-roll. i-frames are the point of it; the burst of speed is what makes it read.
export const DODGE = {
  speed: 15.0,
  time: 0.30,
  iframes: 0.22,
  cooldown: 0.70,
  // Double-tap window. Too long and ordinary strafing triggers rolls you didn't ask for;
  // too short and deliberate taps get eaten. 280ms is the usual comfortable middle.
  doubleTapMs: 280,
};

// D3/D4: three camera states. AIM blends to first person so steep upward aim stops
// fighting the over-shoulder rig; the blend (not a cut) is what makes it feel good.
export const CAMERA = {
  fov: 72,
  aimFov: 60,
  thirdPersonDist: 4.2,
  // 0 = camera dead behind you, character centred (Zelda/Mario framing).
  // >0 offsets to the right, putting the body left of centre (Gears/Fortnite framing) —
  // that exists so the crosshair isn't behind your own head, which is a problem this game
  // doesn't have: aiming blends to first person anyway (D4). Centred it is.
  shoulder: 0.0,
  height: 1.55,
  aimBlendTime: 0.17,   // seconds — BOTW-ish
  minPitch: -Math.PI / 2 + 0.05,
  maxPitch: Math.PI / 2 - 0.05,
  // Radians of turn per pixel of mouse travel. Tune live in-game with [ and ] — feel is
  // not a thing to guess at in a config file. This value is just the starting point.
  sensitivity: 0.004,
};
