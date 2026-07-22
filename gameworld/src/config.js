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
export const RING_SIZE = 400;           // world units per ring
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
  maxFall: -60,
};

// D3/D4: three camera states. AIM blends to first person so steep upward aim stops
// fighting the over-shoulder rig; the blend (not a cut) is what makes it feel good.
export const CAMERA = {
  fov: 72,
  aimFov: 60,
  thirdPersonDist: 4.2,
  shoulder: 0.7,
  height: 1.55,
  aimBlendTime: 0.17,   // seconds — BOTW-ish
  minPitch: -Math.PI / 2 + 0.05,
  maxPitch: Math.PI / 2 - 0.05,
  // Radians of turn per pixel of mouse travel. Tune live in-game with [ and ] — feel is
  // not a thing to guess at in a config file. This value is just the starting point.
  sensitivity: 0.004,
};
