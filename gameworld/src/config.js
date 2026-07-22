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
export const RING_SIZE = 260;           // width of the FIRST band
// Each band is wider than the last, so the deep tiers are vast rather than a treadmill of
// thin shells. Band t is RING_SIZE * (1 + t*RING_WIDEN).
export const RING_WIDEN = 0.25;

// How many settlements a band holds: towns double per tier (capped), plus one CITY from
// tier 1 outward that grows as you go. So the frontier gets denser AND grander.
export const SETTLE = {
  townsBase: 1,           // tier 0: the spawn town, alone
  townCap: 10,
  cityFromTier: 1,
  cityScale: 1.55,        // city radius = RADIUS * (cityScale + cityGrow * tier)
  cityGrow: 0.32,
  flatten: 1.25,          // a city flattens terrain out to this multiple of its radius
};
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
  walkSpeed: 6.3,      // level-1 baseline; levels multiply this (XP.speedGrowth)
  sprintSpeed: 9.6,
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

// Out-of-combat regeneration. Slow enough that it is never a substitute for the heal or a
// potion mid-fight — it is what saves you the walk back to town after a scrappy win.
export const REGEN = {
  delay: 6,          // seconds of NOT fighting before it starts
  rate: 3.2,         // hp per second
  // Same rate everywhere. A town's value is that nothing can reach you while it happens —
  // not a faster number. Raise this if a refuge should also mend quicker.
  safeMult: 1.0,
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

// Ability slots hold whatever you equip; each ability carries its own cooldown, so there
// is nothing global to tune here. `surgeSpeed` stays because the movement code reads it for
// any ability that grants a speed burst.
export const ABILITY = {
  surgeSpeed: 1.75,
};

// Dash Strike: a committed line through a fight. Untouchable while it travels, so it is
// both an escape and an opening — but the hitbox is NARROW, so it only catches what you
// actually pass through. Aim is the cost; the short cooldown is the reward for aiming well.
export const DASH = {
  price: 120,
  cd: 4,
  speed: 46,
  time: 0.26,           // ~12 units of travel
  radius: 2.6,          // how close a mob must be to the line you cut
  damage: 95,
  knock: 9,
  iframePad: 0.1,       // a sliver of grace on landing, so you don't eat a hit on arrival
};

// Whirlwind: leap in, land hard, then spin through whatever survived. Two phases in one
// button — the slam is the commitment, the spin is the reward for committing.
export const WHIRL = {
  price: 260,
  minTier: 1,           // stocked from the first ring out
  cd: 13,
  leapSpeed: 24,
  leapUp: 9.5,
  leapTime: 0.55,       // airtime cap; landing early triggers the slam early
  slamRadius: 10,
  slamDamage: 150,
  spinTime: 3.6,
  spinRadius: 7.0,      // matches the drawn ring exactly
  spinTick: 0.22,       // damage every this many seconds while spinning
  spinDamage: 22,       // ~100/s sustained
  spinSpeed: 1.5,       // and you move faster while you do it
};

// Boss relics: a bundle of shop upgrades, dropped on the ground to be walked over.
export const RELIC = {
  minStats: 2,
  maxStats: 2,
  thirdStatTier: 4,     // deep bosses roll a third
  stacksBase: 2,        // "purchases" of each stat at tier 0...
  stacksPerTier: 0.55,  // ...growing with the fight
  pickupRange: 2.4,
  life: 240,            // seconds it waits on the ground before fading
  bob: 0.35,
};

// Haste — the Adept's answer to the smith's plating. Where armour makes you harder to
// kill, haste makes everything you do arrive sooner. All three terms are multiplicative
// per stack, so like armour it approaches a limit instead of crossing one.
export const HASTE = {
  price: 160,
  fire: 1.07,           // gun rounds per second, per stack
  cooldown: 0.92,       // grenade cooldown
  cast: 0.93,           // heal channel length
  castFloor: 0.45,      // ...but a channel can never become instant
};

// Rank 2s. Sold from the first ring out — the reward for leaving the Commons is not just
// bigger numbers but a better VERSION of what you already know how to use.
export const RANK2 = {
  fireringPrice: 210,
  fireringCd: 12,        // 16 -> 12
  dashPrice: 230,
  dashCharges: 2,        // hold two, spend both, then wait two cooldowns
};

// Abilities sold by the Adept. The first one is deliberately strong for its price: it is
// the first real power spike, and it should feel like one on the walk home from buying it.
export const FIRERING = {
  price: 90,
  cd: 16,
  radius: 15,
  damage: 150,          // still clears an early camp; no longer deletes a boss
  knock: 13,
  grow: 0.55,           // seconds for the wall of flame to reach full radius
  shove: 26,            // rank 2 only: how hard survivors are thrown outward
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

// Villagers, and the little economy that gives a sanctuary a point. Gold comes off the
// frontier; it is only worth anything where someone will take it.
export const VILLAGE = {
  perSanctuary: 14,
  maxRendered: 180,
  keepRange: 620,
  talkRange: 3.6,
  smithBonus: 0.08,       // permanent, stacking damage from the smith
  // Armour stacks MULTIPLICATIVELY: each plate multiplies incoming damage by this, so it
  // has diminishing returns by construction and can never reach immunity. Additive
  // reduction would hit 100% at the twelfth purchase and break the game quietly.
  armorMult: 0.90,
  potionHeal: 60,
  potionCd: 40,          // long: a potion is an emergency, not a rotation
};

export const LOOT = {
  base: 4,
  perTier: 2.5,
  eliteMult: 4,
  bossMult: 45,
};

// The green folk — nomad bands. SCOPE, on purpose: movement, bunching and breeding ONLY.
// No speech, no memory, no bonds. This is the BODY layer that the substrate brain will
// drive later; until then nothing here pretends to be a mind.
export const FOLK = {
  maxAlive: 60,
  maxBands: 5,
  bandSize: [4, 8],
  bandCap: 12,
  splitAt: 11,            // outgrow this and the band divides and wanders apart
  maturity: 25,           // seconds before a newborn can itself breed
  breedEvery: [40, 95],
  spawnMin: 40,
  spawnMax: 120,
  spawnInterval: 3.0,
  despawn: 190,

  speed: 2.1,
  travel: 1.5,            // pull toward the band's destination
  roam: 220,              // how far a band will pick its next destination
  retarget: [45, 110],    // seconds before choosing somewhere new
  refugeBias: 0.45,       // ...and how often that somewhere is a sanctuary
  wary: 22,               // hostiles inside this push them away
  flee: 3.2,
  neighborRadius: 11,
  separation: 2.2,
  sepForce: 3.0,
  alignForce: 0.9,
  cohesionForce: 0.8,     // stronger than the mobs': a band travels tight
  maxClimb: 1.15,
};

// D7: mobs are SOULLESS. Stats roll from the ring they spawn in; no memory, no bonds, no
// substrate — the emergent layer arrives at M3 and lands on settlements, not on things you
// kill in three seconds.
export const MOB = {
  hp: 48,                 // ~4 shots at level 1, instead of dying to a sneeze
  damage: 8,
  speed: 3.1,
  // They live their own lives until you give them a reason. Notice range is SHORT, and the
  // leash is measured from HOME, not from you — mirroring how the lab's souls are held by
  // their own place and people rather than by the player (world/sim.py _drift_positions).
  noticeRange: 20,
  leashRange: 62,         // drag them this far from home and they give up and go back
  loseInterest: 7.0,      // seconds out of contact before disengaging
  alertRadius: 18,        // hurt one and its KIN come from this far
  alertOthers: 11,        // anything else nearby reacts too — a scream is a scream
  homeWander: 11,         // how far they mill around their camp when idle
  homePull: 1.1,
  attackRange: 2.4,
  attackCd: 1.15,
  lungeTime: 0.28,
  lungeSpeed: 9.5,
  radius: 0.55,
  knockback: 5.5,
  knockTime: 0.45,        // how long a shoved mob stays airborne-ish
  // Casters FLY. Ranged pressure comes from the sky, which puts it outside the plane every
  // other threat lives in and finally makes pitch matter.
  flyHeight: 8.5,
  flyBob: 0.7,

  // Per-ring multipliers — D8's difficulty gradient, expressed as numbers.
  //
  // HP grows EXPONENTIALLY because player damage does. Compounding 9%/level works out to
  // ~1.41x per tier at the pace people actually level, so linear HP inevitably falls behind
  // and everything starts dying in one shot around level 30. Matching the curve holds
  // time-to-kill at ~4 shots forever: outlevel the frontier and it gets easier, run ahead
  // of your level and it bites. That relationship is the difficulty design, not a number.
  hpGrowth: 1.42,
  damagePerRing: 0.40,
  speedPerRing: 0.06,

  // ★elites: rarer near spawn, common in the deep. Valheim's star system, which is the
  // cheapest legible "this one is worse" signal there is.
  eliteChance: 0.06,
  eliteChancePerRing: 0.06,   // ring 5: 36% elite — the deep is mostly stars
  // Elites get tougher the further out they are, on TOP of the per-tier HP every mob gets —
  // so a star near spawn is a speed bump and a star in the deep is a real fight.
  eliteHp: 2.2,
  eliteHpPerRing: 0.12,
  eliteDamage: 1.5,
  eliteScale: 1.55,

  // CASTERS — a second kind of elite that fights at range. They hold a standoff and lob
  // slow fireballs in a STRAIGHT line, aimed where you were when it left their hands. That
  // makes them a pure movement problem: the counter is to be somewhere else, not to out-DPS
  // them. Mixed into a melee pack they force you to keep moving while something closes.
  casterChance: 0.4,      // of elites; a melee star is still the common case
  flyChance: 1.0,         // ...and elite casters take to the air
  groundCasterChance: 0.2, // ranged that stays on the ground: common, not elite
  flyHitScale: 2.4,       // flyers get a generous hitbox — see targets()
  castMin: 11,            // closer than this and they back off — they don't want a brawl
  castMax: 34,
  castCd: 3.4,
  castWindup: 0.8,        // they stop and glow before releasing: the telegraph
  ballSpeed: 12,          // slow enough to sidestep if you see it coming
  ballDamage: 24,
  ballRadius: 1.0,
  ballLife: 4.5,
  ballPool: 32,

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
  // Packs, not scattered individuals: camps that mill, flock, and BREED.
  //
  // Population scales with TIER as well as being large: the deep is not just meaner, it is
  // more CROWDED. That reinforces D8's gradient with density instead of only with stats,
  // and it's why walking out feels like pressure rather than arithmetic.
  maxAlive: 170,
  maxAlivePerTier: 22,    // tier 3: 236 · tier 8: 346 (capped)
  maxAliveCap: 380,
  maxPacks: 16,
  maxPacksPerTier: 3,
  maxPacksCap: 34,
  packSize: [9, 18],      // a camp is a crowd, not a squad
  packCap: 26,            // and it can breed to this
  breedEvery: [35, 80],   // seconds between a mob's offspring (idle only, never mid-fight)
  // Tighter band than before: camps sat 32-88 units out, which put most of them past the
  // fog and made the world read as empty. 22-58 keeps several in sight at once.
  spawnMin: 22,
  spawnMax: 58,
  despawn: 105,
  // Deeper rings repopulate faster as well as holding more: a camp you clear at tier 8
  // is replaced almost at once, so the frontier never feels emptied.
  spawnInterval: 0.3,
  spawnFasterPerTier: 0.12,   // interval x (1 - this)^tier, floored below
  spawnIntervalMin: 0.06,
};

// D10 — the giant boss. ONE reusable rig, re-dressed per ring. Everything here is tuned
// around a single rule: the fight must be long enough that its pattern becomes legible,
// and every source of damage must be avoidable by a player who reads the telegraph.
export const BOSS = {
  // HP COMPOUNDS, like the mobs' and like your damage. It was still the old linear formula
  // long after mob HP was fixed, so a full ability rotation went from 89% of a tier-1 boss
  // to 220% of a tier-8 one — you could delete them with three buttons. Matching the curve
  // holds a rotation at ~23% of a boss at EVERY depth, so a fight is always four or five
  // rotations plus gunfire rather than a burst check.
  //   tier 1: 3550 · tier 3: 7159 · tier 5: 14434 · tier 8: 41328
  hp: 2500,
  hpGrowth: 1.42,
  // And it hits harder as you go out. A longer fight against fixed damage is an EASIER
  // fight; the deep should not be safer just because it takes longer.
  damagePerTier: 0.18,
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
  // The boss alternates volley -> beam -> volley. They ask opposite questions: meteors
  // punish predictable movement, the beam punishes stillness. Together you have to keep
  // moving without moving in a straight line.
  beamWarm: 1.15,         // telegraph before it burns
  beamTime: 5.0,          // how long it hunts you
  beamRadius: 3.2,
  beamDps: 46,
  beamSpeed: 6.0,         // just under a level-1 walk (6.3): moving escapes, standing cooks
  beamSpeedPerTier: 0.5,  // deeper tiers close the gap, so your speed upgrades stay a reward
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
