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
  walkSpeed: 7.3,      // level-1 baseline; levels multiply this (XP.speedGrowth)
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
// WEAPONS — a family, not a gun. Each is the same hitscan core (one ray from the crosshair)
// with a different feel dialled entirely in data: rate, magazine, spread, range, pellets,
// and semi-vs-auto. They are the Weapon slot of GEAR.md — you own guns and switch between
// them (mouse wheel), and buying one from the smith equips it. Damage still rides the level
// multiplier and the (coming) Gun-Damage stat, so a weapon's number is its IDENTITY, not its
// power ceiling — a sniper hits like a truck at every level, an MG spits chip damage at every
// level, and gear scales both together.
export const WEAPONS = {
  rifle: {
    id: "rifle", name: "Repeater", price: 0,   // the starter; owned from the first frame
    damage: 12, fireRate: 7.5, magSize: 18, reloadTime: 1.15, range: 220,
    pellets: 1, auto: true, recoil: 0.016, recoilRecover: 0.75,
    spreadHip: 0.06, spreadAim: 0.002, sound: "rifle",
    desc: "Balanced automatic. Hold to fire.",
  },
  shotgun: {
    id: "shotgun", name: "Scattergun", price: 260,
    // A wall of pellets that now carries a real distance. One booming shot, a pump between.
    damage: 11, fireRate: 1.3, magSize: 5, reloadTime: 0.65, range: 90,
    pellets: 9, auto: false, pump: true, recoil: 0.05, recoilRecover: 0.6,
    spreadHip: 0.14, spreadAim: 0.09, sound: "shotgun",
    desc: "9 pellets, long reach now, one booming shot with a pump between rounds.",
  },
  sniper: {
    id: "sniper", name: "Longshot", price: 300,
    // One enormous round across the whole map, then a bolt cycle. bam — ka-chunk — bam.
    damage: 165, fireRate: 1.1, magSize: 1, reloadTime: 1.05, range: 600,
    pellets: 1, auto: false, pump: true, recoil: 0.09, recoilRecover: 0.5,
    spreadHip: 0.11, spreadAim: 0.0, sound: "sniper",
    desc: "One huge round per reload — bam, bolt, bam. Enormous damage, map-long range.",
  },
  mg: {
    id: "mg", name: "Ripper", price: 300,
    // A hose. Low per-shot, huge belt, so it answers crowds and never stops for long.
    damage: 6, fireRate: 12, magSize: 60, reloadTime: 2.0, range: 180,
    pellets: 1, auto: true, recoil: 0.012, recoilRecover: 0.8,
    spreadHip: 0.12, spreadAim: 0.028, sound: "mg",
    desc: "Low damage, huge belt, high rate. Hoses down crowds.",
  },
};

// The starting weapon, and a back-compat alias for a few call sites that still say GUN.
export const GUN = WEAPONS.rifle;

// ARMOR — a WoW-style SLOT SET, and every piece rolls a LIST of stats, not just armour.
// Five slots, one unique piece each; ALL the stats across your worn pieces add up (see
// recomputeGear in main). A better piece REPLACES the one in ITS slot — you can never wear
// two of the same slot, but a full kit of five, each contributing its spread, is the goal.
//
// Each slot has a CHARACTER, so building a set is a set of choices: the vest is the tank
// piece, shoulders bring Strength, boots bring Agility and speed, and so on. The plain-terms
// meaning of every stat is spelled out in the character sheet's legend.
export const ARMOR_SLOT_ORDER = ["helm", "shoulders", "vest", "pants", "boots"];
const ARMOR_SLOT_NOUN = { helm: "Helm", shoulders: "Guards", vest: "Vest", pants: "Legs", boots: "Boots" };
// Three material tiers. `a` armour, `attr` primary points, `stam`, `rate` secondary rating,
// `dmg` a damage-bucket fraction — each slot draws the ones that fit its character.
const ARMOR_TIERS = [
  { key: "padded", label: "Padded", a: 26, attr: 3, stam: 6, rate: 22, dmg: 0.02, price: 70, minTier: 0 },
  { key: "chain", label: "Chain", a: 58, attr: 6, stam: 12, rate: 46, dmg: 0.04, price: 150, minTier: 1 },
  { key: "plate", label: "Plate", a: 108, attr: 11, stam: 21, rate: 82, dmg: 0.07, price: 300, minTier: 3 },
];
// What each slot rolls, as a function of the tier row. This is where slot identity lives.
const ARMOR_SLOT_STATS = {
  helm: (t) => ({ armor: t.a, rHaste: t.rate, dmgSpell: t.dmg }),
  shoulders: (t) => ({ armor: t.a, str: t.attr, dmgGun: t.dmg }),
  vest: (t) => ({ armor: Math.round(t.a * 1.3), stamina: t.stam, dmgGlobal: t.dmg }),
  pants: (t) => ({ armor: t.a, agi: t.attr, dmgGrenade: t.dmg }),
  boots: (t) => ({ armor: Math.round(t.a * 0.75), agi: t.attr, moveSpeed: t.dmg + 0.02 }),
};
export const ARMOR = {};
for (const slot of ARMOR_SLOT_ORDER) {
  for (const t of ARMOR_TIERS) {
    const id = `${t.key}_${slot}`;
    const stats = ARMOR_SLOT_STATS[slot](t);
    ARMOR[id] = {
      id, slot, name: `${t.label} ${ARMOR_SLOT_NOUN[slot]}`,
      stats, armor: stats.armor, price: t.price, minTier: t.minTier,
    };
  }
}

// Human-readable stat meanings — the legend the character sheet prints so the numbers on a
// piece mean something. Keyed by the stat field; {label, kind} where kind picks formatting.
export const STAT_INFO = {
  armor: { label: "Armor", kind: "flat", note: "reduces damage taken (less per point as it grows, and less against deeper enemies)" },
  stamina: { label: "Stamina", kind: "flat", note: "+8 max health each" },
  str: { label: "Strength", kind: "flat", note: "raises ALL your damage — gun, grenade and spells" },
  agi: { label: "Agility", kind: "flat", note: "movement speed and dash distance" },
  dmgGlobal: { label: "Global Damage", kind: "pct", note: "more damage from every source" },
  dmgGun: { label: "Gun Damage", kind: "pct", note: "more damage from your guns" },
  dmgSpell: { label: "Spell Damage", kind: "pct", note: "more damage from abilities (ring, dash, whirlwind)" },
  dmgGrenade: { label: "Grenade Damage", kind: "pct", note: "more grenade damage" },
  rHaste: { label: "Haste", kind: "rate", note: "shorter ability cooldowns" },
  rAtkSpeed: { label: "Attack Speed", kind: "rate", note: "faster gun fire rate" },
  rReload: { label: "Reload", kind: "rate", note: "faster reloads" },
  moveSpeed: { label: "Move Speed", kind: "pct", note: "faster movement" },
};

// Early-game GRACE. Levels 1-3 should be EASY: a fresh player has no gear and the whole point
// of the first hour is to get some. This bonus is large at level 1 and fades to nothing by
// `levels`, so a gearless newbie hits hard and shrugs off hits, and the challenge RAMPS UP as
// you level and kit out instead of landing all at once at the door. The "more powerful at low
// level" dial — turn it up to make the start kinder, down to make it bite sooner.
export const GRACE = {
  levels: 8,          // fully gone at this level
  dmgBonus: 0.9,      // +90% damage at level 1, fading linearly to 0
  mitigation: 0.45,   // -45% damage taken at level 1, fading to 0
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
  // How much a kill is worth per ring out. Tuned so an ON-LEVEL regular mob is worth about
  // what a same-level WoW Classic mob is: at level 20 you're in tier 3, so 12 × (1 + 1.3×3)
  // = ~59 xp against a ~9,600 level ≈ 0.6% per kill (Classic's ~145 / ~24,000 ≈ 0.6%). So
  // regular mobs stay worth killing at every depth, not just elites and bosses. Tier 0 is
  // unaffected (ring 0 → ×1), so the one-kill opening level is untouched.
  perRing: 1.3,
  eliteMult: 7,
  bossBase: 900,
  bossPerRing: 0.8,

  // A THREE-PHASE level curve shaped after WoW Classic (long grind, quadratic-ish) but a bit
  // faster, and keyed so a mob is worth ~12 xp: level 1 is ONE kill, and it climbs from there.
  // Continuous at the breakpoints (each phase starts where the last ended, just steeper), so
  // the first ten levels are quick RELATIVE to how long 20+ takes.
  //   kills-to-next (at ~12 xp/kill): L1 ~1 · L2 ~4 · L3 ~10 · L4 ~20 · L5 ~32 · L9 ~120
  //   xp: L1 12 · L5 ~390 · L10 ~1690 · L20 ~9560 · L30 ~32k · L50 ~149k  (Classic L50 ≈ 170k)
  xpBase: 12,
  xpEarlyExp: 2.15,    // phase 1 (below break1): quadratic, WoW-shaped
  xpMidExp: 2.5,       // phase 2 (break1..break2): the climb
  xpLateExp: 3.0,      // phase 3 (break2+): 20+ "takes forever"
  xpBreak1: 10,
  xpBreak2: 20,

  // WoW's GREY-MOB mechanic: once you outlevel a ring, its kills stop being worth your time,
  // so easy back-zones can't be farmed for xp — you're pushed outward. Each ring greys out
  // (0 xp) at greyBase + greyPerTier*ring, with a steep drop over the last greyBand levels.
  //   tier 0: full ≤ L9 · L10 ~42% · L11 ~9% · L12 ZERO   (exactly the "big drop then nothing")
  //   tier 1: full ≤ L14 · greys at L17 · tier 2: greys at L22 · …
  greyBase: 12,        // level at which the FIRST ring (tier 0) gives no xp
  greyPerTier: 5,      // each ring's grey level is this much higher
  greyBand: 3,         // levels over which xp falls from full to zero
  greyExp: 2.2,        // >1 makes the drop punchy rather than linear
  bossXpFloor: 0.2,    // a boss never greys BELOW this — it's still a fight, just not farmable

  // Interim level rewards. D9's real answer is a 1-of-3 card pick — this keeps levelling
  // FELT until that UI exists, and is meant to be replaced by it, not kept.
  // Levels buy MOBILITY, not bulk. Max HP never moves, so a meteor is as lethal at level 40
  // as at level 4 and survival stays a question of reading telegraphs rather than of having
  // a bigger bar. What you gain is the ability to be somewhere else.
  hpPerLevel: 0,
  speedGrowth: 1.02,      // raw per-level; fed through a tanh soft cap (see applyLevelStats)
  // The most speed levels + gear can ever add, as a fraction of base. tanh approaches but
  // never quite reaches it, so effective speed tops out near ×(1 + this). 1.2 = ~2.2× base
  // at the extreme, vs the old uncapped 3-5×. This is the "you go too fast" dial.
  speedSoftCap: 1.2,
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
  rate: 3.2,         // hp per second in the field
  // A town MENDS you: it ignores the combat delay and heals a fraction of your max HP per
  // second, so you're back to full in a few seconds regardless of how big your pool is.
  safeFrac: 0.28,    // ~3.5s to full inside the walls
};

// Q — the heal. A 1.5s channel that ROOTS you, breaks if you move, and breaks if you're
// hit. In a game whose every other verb is movement, the cost of standing still is the
// whole design: it turns the boss's volley gaps into the window you're hunting for.
export const HEAL = {
  castTime: 1.5,
  // Heals a FRACTION of your max HP (so it stays relevant as your pool grows) boosted by
  // Spell Power, so a caster build mends more. No cooldown any more — the 1.5s root that
  // breaks on a hit is the whole cost.
  fraction: 0.55,
  cooldown: 0,
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

// --- New spells (WoW / LoL / Overwatch flavoured), sold by the Adept -------------------
// Timewarp: stamp your position/HP now; 5s later you SNAP back to it with all cooldowns
// reset (Zilean's Chronoshift crossed with a Recall). A panic button and a burst enabler.
export const TIMEWARP = { price: 340, minTier: 1, cd: 40, window: 5 };
// Cataclysm Orb: lob a red ball that bursts and leaves a burning pool doing heavy DoT.
// Rank 2 the pool SLOWS, rank 3 it ROOTS.
export const ORB = {
  price: 240, minTier: 0, cd: 11, speed: 27, up: 5, range: 66,
  burstRadius: 6, burstDamage: 130,
  poolRadius: 5.5, poolDps: 78, poolLife: 5, poolTick: 0.3,
  slowMul: 0.5, slowT: 1.2, rootT: 1.1,
};
// Frost Nova: instant ring around you — damage + a hard slow. Rank 2 roots instead.
export const NOVA = { price: 175, minTier: 0, cd: 9, radius: 11, damage: 95, slowMul: 0.5, slowT: 3, rootT: 1.6 };
// Chain Lightning: arcs from the nearest foe to the next, damage falling each jump.
export const CHAIN = { price: 210, minTier: 1, cd: 8, range: 34, jumps: 5, jumpRange: 15, damage: 130, falloff: 0.8 };
// Sprint: a burst of movement speed on demand (a movement spell, the first of several).
export const SPRINT = { price: 150, minTier: 0, cd: 11, dur: 4, mult: 1.7 };

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
  // Haste shrinks the throw cooldown (0.92^haste). Without a floor, enough speed drives it
  // to ~0, and you empty the whole stock in a blink -- then, since supply only ever came
  // from kills, nothing you throw has died yet and they never come back. Same shape as the
  // gun-reload bug: a rate pushed past the floor it needed. Floor it, and haste makes
  // grenades arrive SOONER instead of breaking them.
  cdFloor: 0.4,
  maxFuse: 4.0,          // safety net; ground contact is the real trigger
  max: 3,
  refillPerKill: 1,
  // A real reload, so spamming can no longer strand you at zero. Kills still refill FASTER
  // (that is the "rewarded by fighting" design), but the stock always crawls back on its
  // own -- hasted like everything else, and likewise floored so speed can never zero it.
  reload: 4.2,
  reloadFloor: 1.1,
  knockback: 11,
};

// Villagers, and the little economy that gives a sanctuary a point. Gold comes off the
// GEAR.md G1 — the additive stat model (see src/prog/stats.js for the formulas). Every value
// here is a raw number that goes ON gear; the diminishing returns are in the formulas, so
// these can grow without ever needing a clamp.
export const STATS = {
  // Health from Stamina. Base is the old flat 100; stamina on gear (G2) grows it from there.
  baseHp: 100,
  stamHp: 8,
  // Armour curve: DR = armor / (armor + armorK + armorPerTier*attackerTier). Tuned so the
  // old shop feel roughly ports -- 1 Heavy Plating (+45) ~13% at tier 0, 5 ~43%, 10 ~60%,
  // close to the old 0.9^n at low-mid stacks but SANE at high stacks and weaker at depth.
  armorK: 300,
  armorPerTier: 60,
  armorDRCap: 0.85,       // a rail, not a target; the formula approaches but rarely nears it
  // Primary attributes -> effect. Strength pours into GLOBAL damage; Agility into speed and
  // dash. Both are flat integers on gear; these coefficients turn a point into an effect.
  strDmg: 0.006,          // each Strength = +0.6% to ALL damage
  agiSpeed: 0.004,        // each Agility = +0.4% into the speed input (before the soft cap)
  agiDash: 0.05,          // dash gains agiDash * sqrt(Agility)
  // Secondary-rating denominators (rating -> % via rating/(rating+K)). Diminishing by shape:
  // a lone 80-rating helm ~35%, and stacking more approaches but never reaches 100%.
  hasteK: 150,
  attackSpeedK: 150,
  reloadK: 150,
};

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
  // Potions heal a FRACTION of your max HP, stepping up every 10 levels, so they stay a real
  // emergency button at any level instead of a flat 60 that does nothing once your pool is big.
  //   L0-9 40% · L10-19 50% · L20-29 60% · L30-39 70% · …
  potionFracBase: 0.4,
  potionFracPer10: 0.1,
  potionCap: 5,          // hold at most this many at once
  potionCd: 18,          // an emergency, not a rotation — but usable more than once a fight now
};

// Gate guards: a standing detachment outside every gate, permanently in a scrap with
// whatever has wandered up. Better than a turret in every way that matters — it is a fight
// to walk past rather than a wall of fire, it pulls mobs OFF you, and it makes a town look
// like somewhere people are holding rather than somewhere the architecture is.
export const GUARD = {
  count: 4,
  spread: 7,            // how far they fan out from the gate
  post: 11,             // how far they will stray from their post
  range: 26,            // engagement range
  fireRate: 0.85,
  damage: 55,
  damagePerTier: 0.9,   // mob HP compounds; a fixed number would be decoration by tier 3
  hp: 320,
  hpPerTier: 0.9,
  regen: 9,             // per second, when nothing is on them
  respawn: 18,          // seconds after falling
  taunt: 22,            // mobs this close to a guard fight the GUARD instead of you
  meleeRange: 3.0,
  soundRange: 46,       // guard shots are silent past this — a town you are not at is quiet
  // Within this of a guard you earn NOTHING. Otherwise the best way to play is to stand
  // behind the line and let the town farm the frontier for you.
  deadZone: 38,
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
  // A touch lower than before, since the first level read as a little hard in general — but
  // the real "levels 1-3 too hard" fix is the early-game GRACE bonus on the PLAYER (see
  // config GRACE and applyLevelStats), which makes a fresh, gearless character strong and
  // fades out by ~level 8, so the game ramps up as you level and gear rather than at the door.
  hp: 76,
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
  // The LINEAR term sets early-ring damage; the ramp below sets how it accelerates. Rings 1-3
  // were too punishing, so the linear base drops (gentle early) while rampDamage rises (still
  // brutal deep) — the acceleration does the work instead of a flat high number everywhere.
  damagePerRing: 0.30,
  speedPerRing: 0.06,

  // ACCELERATION on top of the flat curve above (see ringPressure() in gen.js). The base
  // exponentials hold time-to-kill constant; these BEND them so the first ring past the
  // Commons is barely harder and the deep climbs fast. For an on-level player that lands at
  // roughly: ring 2 ~1.1x TTK, ring 4 ~1.8x, ring 5 ~2.8x, ring 6 ~4.5x, ring 8 ~16x — so
  // "multiple bombs per regular mob" arrives around ring 5 and only worsens. An UNDER-level
  // player (run out ahead of your bed) feels it far sooner, which is the whole point of a
  // frontier. Turn these DOWN to soften the deep; they are the difficulty dial now.
  //
  // REBALANCED after play: the deep was bullet-sponge tanky AND toothless -- HP raced away
  // while damage crawled, so a fight was long and safe, the worst combination. The two ramps
  // are now nearly swapped. Player HP is a flat 100 (only armour makes you tankier), so mob
  // damage has to climb hard to matter against a plated build, and HP should climb GENTLY so
  // depth is lethal, not tedious.
  ramp: 0.09,           // HP — halved: deep mobs die in a few shots, not a magazine
  rampDamage: 0.38,     // damage — accelerates hard, so the deep still bites despite the lower base
  rampCrowd: 0.14,      // more bodies, sooner — reaches the population cap faster

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

  // --- SWARM: tiny, fast, fragile, and only dangerous in numbers ------------------
  // The question it asks is "do you have a crowd answer" — Ring of Fire finally has a
  // customer, and a single-target build has to learn to back up.
  swarmPackChance: 0.26,  // of new camps
  swarmSize: [14, 22],
  swarmHp: 0.15,
  swarmSpeed: 1.55,
  swarmScale: 0.5,
  swarmDamage: 0.45,
  swarmCohesion: 2.4,     // multiplier on the flocking pull: they move as one body

  // --- CHARGER: wind up, commit, then be helpless ---------------------------------
  // The question is sidestep TIMING. Everything else punishes where you stand; this
  // punishes when you move. Its recovery is a real window, not a formality.
  chargerChance: 0.17,    // of ordinary (non-caster) mobs
  chargeRange: 27,
  chargeWind: 0.75,       // rooted and glowing before it goes
  chargeSpeed: 21,
  chargeTime: 1.15,
  chargeRecover: 1.7,     // helpless afterwards, whether it hit or missed
  chargeDamage: 2.3,      // multiplier on its own damage
  chargeKnock: 15,

  // --- FACTIONS AT WAR: the cheap emergent win ------------------------------------
  // Every camp belongs to a faction (a colour). Enemy factions fight EACH OTHER, not just
  // you — so you can crest a hill onto two armies already colliding and rob the winner. It
  // reuses the aggro/steering/pack brain wholesale: a mob simply treats a near enemy-faction
  // mob as a target the way it treats you, and brawls it in melee.
  factions: 3,           // how many warring colours exist
  factionWar: true,      // toggle the whole behaviour
  warRange: 17,          // a mob engages an enemy-faction mob within this
  factionDamage: 0.65,   // mob-vs-mob hits for this fraction of their damage-to-you

  // --- steering: emergent movement, no substrate required -------------------------
  // The brain decides INTENT (close, hold, lunge); these decide HOW the body gets there.
  // Same seam as PLAN §4 — a mob brain and a soul brain will drive the same locomotion.
  neighborRadius: 10,     // who counts as "nearby" for flocking
  // In a dense pile-up, EVERY mob scanning EVERY neighbour is the O(n²) that lags. Flocking
  // only needs a SAMPLE, so we stop after this many — the motion looks identical, the cost
  // stops exploding. This is the single biggest knob for big-group performance.
  maxNeighbours: 12,
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
  // The tier-0 BASE is deliberately calm — the Commons is where you learn the game, and it
  // read as a swarm. The crowd ramp (rampCrowd) climbs off this base fast, so ring 1 is
  // already busier and the deep still fills to the cap; only the first level is quieter.
  // Tier 0 was BOTH the most crowded AND the hardest, which is backwards for a learning zone.
  // The count drops hard at the base and the ramp steepens to make it up, so the Commons is
  // a handful of mobs you can read while the deep stays a horde. (GEAR.md G5/G6 take this
  // further into the MMO direction: fewer, meatier mobs.)
  maxAlive: 44,
  maxAlivePerTier: 28,    // tier 1: ~72 · tier 3: ~150 · tier 6+: capped — less swarm early
  maxAliveCap: 380,
  maxPacks: 6,
  maxPacksPerTier: 5,
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
  // HP COMPOUNDS, like the mobs'. The curve was matched to LEVELS alone — but gear and relic
  // damage are uncapped and multiply on top, so a player who stacked sharpen deleted bosses
  // that the maths said should last five rotations. That is exactly the "bosses die super
  // fast" you hit. Two answers: a higher base (the shallow fight), and a depth RAMP so bosses
  // accelerate alongside the now-accelerating trash instead of becoming the softest thing on
  // the ring. The ramp is deliberately GENTLER than the mobs' HP ramp — a boss already lasts
  // ~22s, so mob-grade acceleration would turn the deep ones into minutes of tedium.
  //   tier 1: 5680 · tier 3: 14100 · tier 5: 46600 · tier 8: ~471000
  hp: 4000,
  hpGrowth: 1.42,
  ramp: 0.10,            // see ringPressure(); << MOB.ramp on purpose — bosses tank, not sponge

  // TOUGHNESS — the answer to uncapped gear, and why it does NOT punish an ungeared player.
  //
  // A flat "damage taken x0.7" would be a lie: mathematically it is identical to giving the
  // boss more HP, so it hits the level-baseline damage exactly as hard as it hits the gear
  // bonus, and an ungeared player just fights a longer fight for no reason. What actually
  // separates a geared player from a bare one is BIG PER-HIT NUMBERS. So the boss caps the
  // damage any SINGLE hit may deal to a fraction of its max HP: small hits sail under it
  // untouched, burst gets clamped. A whale can no longer delete a boss in three buttons, an
  // ungeared player never even notices the cap exists, and the floor on a fight becomes
  // "1 / fraction" hits no matter how absurd your sharpen stack.
  //
  // It scales with tier two ways: the cap is a fraction of a tier-scaled HP pool, and the
  // fraction itself tightens with depth — so the deep bosses are the hardest to burst.
  maxHitFraction: 0.03,     // ring 1: no single hit may exceed 3% of max HP (~34-hit floor)
  hitCapTighten: 0.06,      // and that shrinks: fraction / (1 + this * ring)

  // EVADE. Run past aggroRange and the boss disengages: it drops every telegraph and heals
  // back to full, so you can't chip it down and stroll away between fights. Same idea as a
  // WoW boss resetting when you leash it out. regenFrac is fraction of MAX HP per second, so
  // a full reset takes ~1/regenFrac seconds regardless of the boss's tier.
  regenFrac: 0.12,          // ~8s from near-death back to full once you've left
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
  // Out in the ring, not on top of you. Past aggroRange (90) so a boss appears at a distance
  // — you spot it on the minimap and GO to it, rather than it materialising in your face.
  spawnDist: [110, 165],
  spawnRing: 1,           // no bosses in the Commons — it stays the safe ground
  retry: 12,              // seconds between spawn attempts once you're eligible
  despawn: 250,           // wider than spawnDist, so a boss you're walking toward won't vanish

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

  // The roll SCALES now (see applyLevelStats -> player.dashMult). It gets both faster and
  // farther — the i-frame window is unchanged, so a bigger dash covers more ground inside
  // the same protection, which is pure mobility, not more safety. Two sources, each with
  // sqrt diminishing returns: always growing, never linear, no hard ceiling (faith with the
  // no-limits rule), but the tenth stack is worth a fraction of the first.
  //   speedGain: ANY speed increase — levels, Lighten, Swiftness relics — lengthens the dash
  //   dashStatGain: the dedicated Vault stat you buy or find
  speedGain: 0.5,
  dashStatGain: 0.22,
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
