// Entry point. Slice 1 of M1: a world you can walk around in.
//
// The loop is deliberately split: PHYSICS runs on a fixed step (feel must not depend on
// framerate), RENDER runs per frame. The substrate's 10Hz tick will slot in as a third
// clock at M3 — the same split localprototype/world/sim.py already uses to keep its fast
// clocks off the slow model calls.

import * as THREE from "three";
import { CAMERA, GUN, MOB, BOSS, GRENADE, HEAL, REGEN, LOOT, VILLAGE, VIEW_RADIUS, CHUNK_X, RING_SIZE, RINGS } from "./config.js";
import { Mobs } from "./mobs/mobs.js";
import { Boss } from "./mobs/boss.js";
import { Folk } from "./mobs/folk.js";
import { Villagers, trade } from "./town/villagers.js";
import { player, spawnPlayer, world } from "./state.js";
import { ChunkStreamer } from "./world/streamer.js";
import { ringAt, tierAt } from "./world/gen.js";
import { Sanctuaries, sanctuaryOf, sanctuariesNear, boundaryAt } from "./world/sanctuary.js";
import { attachInput, input, stepPlayer } from "./player/controller.js";
import { CameraRig } from "./player/camera.js";
import { Gun } from "./player/gun.js";
import { Music } from "./audio/music.js";
import { sfx } from "./audio/sfx.js";
import { Grenades } from "./player/grenade.js";
import { Heal } from "./player/heal.js";
import { Minimap } from "./ui/minimap.js";
import { Bridge } from "./net/bridge.js";
import { award, killValue, bossValue, xpToNext, levelProgress, loseLevel } from "./prog/xp.js";
import { mulberry32 } from "./rng.js";

const FIXED_DT = 1 / 60;
const MAX_CATCHUP = 0.25;    // never simulate more than this in one frame after a stall

const scene = new THREE.Scene();
const SKY = new THREE.Color(0x8fb6d8);
scene.background = SKY;
scene.fog = new THREE.Fog(SKY, VIEW_RADIUS * CHUNK_X * 0.45, VIEW_RADIUS * CHUNK_X * 0.95);

const camera = new THREE.PerspectiveCamera(CAMERA.fov, innerWidth / innerHeight, 0.1, 2000);
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);
document.body.appendChild(renderer.domElement);

scene.add(new THREE.HemisphereLight(0xbcd8f0, 0x4a4a44, 0.85));
const sun = new THREE.DirectionalLight(0xfff2dd, 1.15);
sun.position.set(0.5, 1, 0.3);
scene.add(sun);

// The player's body. A box until M1 gets a real model — but it exists from day one because
// third person is the default (D3), and you cannot tune a follow camera against nothing.
const body = new THREE.Mesh(
  new THREE.BoxGeometry(0.7, 1.8, 0.5),
  new THREE.MeshLambertMaterial({ color: 0xd8734a }),
);
scene.add(body);

const streamer = new ChunkStreamer(scene);
const rig = new CameraRig(camera);
const music = new Music();
const gun = new Gun(scene, camera);
const gunRng = mulberry32(0xBADA55);    // D14: even bullet spread is seeded
const mobs = new Mobs(scene);
const boss = new Boss(scene);
const grenades = new Grenades(scene);
const heal = new Heal(scene);
const minimap = new Minimap(document.getElementById("minimap"));
const sanctuaries = new Sanctuaries(scene);
const folk = new Folk(scene);
const villagers = new Villagers(scene);
let tradeMsg = "", tradeMsgT = 0;

// The bridge to the Python lab. Optional by construction: if it never connects, nothing
// below notices (STAGES Stage 1). Speech is fire-and-forget — a pending request must never
// hold up a frame, so nothing here is awaited from the loop.
const bridge = new Bridge();
bridge.connect();
let subtitle = "", subtitleT = 0, speaking = false;

async function speakLine(prompt, words = 16) {
  if (speaking || bridge.state !== "online") return;
  speaking = true;
  const res = await bridge.line(prompt, { words });
  speaking = false;
  if (!res) return;
  subtitle = res.text;
  subtitleT = 4 + res.text.length * 0.05;
  const dur = await sfx.playClip(res.audio, player.x, player.z);
  if (dur) subtitleT = Math.max(subtitleT, dur + 0.6);
}
const shakeRng = mulberry32(0x51AE);
let bossTimer = 6;

const hurtEl = document.getElementById("hurt");
const subEl = document.getElementById("subtitle");
let hurtT = 0, killFeed = "";

function damagePlayer(amount, fromX, fromZ, knock = MOB.knockback) {
  if (player.iframes > 0) return;      // the dodge window actually pays out here
  // A sanctuary is safe, FULL STOP. The mobs, the boss and the projectiles each have their
  // own behavioural guards, but those are about looking right; this is the guarantee. One
  // rule in one place beats four that each have to be remembered.
  if (sanctuaryOf(player.x, player.z, 0)) return;
  player.hp -= amount;
  hurtT = 0.35;
  markCombat();
  if (HEAL.breakOnDamage) heal.interrupt("hit");
  // Knockback, so a hit moves you and reads as physical rather than as a number ticking.
  const dx = player.x - fromX, dz = player.z - fromZ;
  const d = Math.hypot(dx, dz) || 1;
  player.vx += (dx / d) * knock;
  player.vz += (dz / d) * knock;
  if (player.hp <= 0) respawn();
}

const hurtPlayer = (mob) => damagePlayer(mob.damage, mob.x, mob.z);

function reward(res) {
  player.gold += Math.round((LOOT.goldBase + LOOT.goldPerTier * res.ring)
    * (res.elite ? LOOT.eliteMult : 1));
  const xp = killValue(res.ring, res.elite);
  const lv = award(xp);
  killFeed = `${res.elite ? "★ elite" : "kill"}  +${xp}xp${lv ? `   ▲ LEVEL ${player.level}` : ""}`;
  if (lv) sfx.healDone();
}

function rewardBoss(ring) {
  player.gold += Math.round((LOOT.goldBase + LOOT.goldPerTier * ring) * LOOT.bossMult);
  const xp = bossValue(ring);
  const lv = award(xp);
  killFeed = `◆ BOSS DOWN ◆  +${xp}xp${lv ? `   ▲ LEVEL ${player.level}` : ""}`;
  if (lv) sfx.healDone();
}

/**
 * A grenade went off. THIS is where an explosion learns what exists in the world —
 * grenade.js only knows a position and a radius, so bosses, mobs and you all take the same
 * blast without it importing any of them. Damage falls off with distance from the centre.
 */
function blast(x, y, z) {
  const falloff = (d) => Math.max(0.25, 1 - d / GRENADE.radius);

  for (const e of [...world.entities.values()]) {
    if (e.kind !== "mob") continue;
    const d = Math.hypot(e.x - x, e.z - z, (e.y - y) * 0.5);
    if (d > GRENADE.radius) continue;
    const res = mobs.hit(e.id, GRENADE.damage * player.dmgMult * falloff(d));
    if (res?.killed) { reward(res); grenades.refill(); }
  }

  if (boss.active) {
    const b = boss.alive;
    const d = Math.hypot(b.x - x, b.z - z);
    if (d < GRENADE.radius + BOSS.contactRange * 0.5) {
      const res = boss.hit("boss", GRENADE.damage * player.dmgMult * falloff(Math.max(0, d - BOSS.contactRange * 0.5)));
      if (res?.killed) { rewardBoss(res.ring); grenades.refill(GRENADE.max); }
    }
  }

  // You are not exempt. Half damage, but a point-blank throw will still hurt badly —
  // which is what makes it a decision rather than a free button.
  const dp = Math.hypot(player.x - x, player.z - z, (player.y - y) * 0.5);
  if (dp < GRENADE.radius) {
    damagePlayer(GRENADE.damage * falloff(dp) * GRENADE.selfScale, x, z, GRENADE.knockback);
  }
}

function respawn() {
  // D9: death costs your top level. Not the run, not your gear — one level, and you land
  // halfway to earning it back, so the loss stings without erasing the walk that bought it.
  const lost = loseLevel();
  spawnPlayer();
  player.hp = player.maxHp;
  player.iframes = 1.5;                 // grace on arrival, so you can't be spawn-camped
  killFeed = lost ? `you died  ▼ LEVEL ${player.level}` : "you died";
}

spawnPlayer();
attachInput(renderer.domElement, {
  toggleCamera: () => rig.toggle(),
  toggleMusic: () => music.toggle(),
  reload: () => gun.reload(),
  interact: () => { tradeMsg = trade(villagers.nearest()); tradeMsgT = 3; },
  drink: () => {
    if (player.potions <= 0) { tradeMsg = "no potions"; tradeMsgT = 2; return; }
    if (player.hp >= player.maxHp) { tradeMsg = "already whole"; tradeMsgT = 2; return; }
    player.potions--;
    player.hp = Math.min(player.maxHp, player.hp + VILLAGE.potionHeal);
    tradeMsg = `potion  +${VILLAGE.potionHeal}`;
    tradeMsgT = 2;
    sfx.healDone();
  },
  bridgeTest: () => {
    const ring = RINGS[ringAt(player.x, player.z)].name;
    speakLine(`You walk beside a traveller in ${ring}, ${Math.round(Math.hypot(player.x, player.z))} metres from where they began. Murmur one short thought about this place.`);
  },
  summonBoss: () => {
    if (boss.active) { boss.despawn(); killFeed = "boss dismissed"; return; }
    const a = shakeRng() * Math.PI * 2;
    boss.spawn(player.x + Math.cos(a) * 34, player.z + Math.sin(a) * 34);
    killFeed = "boss summoned";
  },
  onLock: () => { music.start(); sfx.unlock(); setPaused(false); },
  onUnlock: () => setPaused(true),
});

addEventListener("resize", () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
});

const clickEl = document.getElementById("click");
let paused = true, everPlayed = false, inSafe = false;
// Time left before regen resumes. Dealing damage counts as fighting, not just taking it.
let combatT = 0, hunted = false;
const markCombat = () => { combatT = REGEN.delay; };

function setPaused(p) {
  paused = p;
  music.setPaused(p);
  sfx.setPaused(p);
  if (!p) { everPlayed = true; return; }
  if (everPlayed) clickEl.innerHTML = "PAUSED &nbsp;·&nbsp; click to resume";
}

/** Distance to the nearest town gate — the HUD half of the minimap marker. */
function nearestGate() {
  let best = null, bd = 1e9;
  for (const s of sanctuariesNear(player.x, player.z, 700)) {
    const r = boundaryAt(s, s.gate);
    const gx = s.x + Math.cos(s.gate) * r, gz = s.z + Math.sin(s.gate) * r;
    const d = Math.hypot(gx - player.x, gz - player.z);
    if (d < bd) { bd = d; best = s; }
  }
  if (!best) return "no town within 700m";
  return inSafe ? "✦ SANCTUARY" : `town gate ${Math.round(bd)}m`;
}

const hud = document.getElementById("stats");
let acc = 0, last = performance.now(), fps = 60;

function frame(now) {
  requestAnimationFrame(frame);
  const dt = Math.min((now - last) / 1000, MAX_CATCHUP);
  last = now;    // updated even while paused, so resuming never simulates the gap

  if (paused) {
    renderer.render(scene, camera);
    return;
  }

  fps += (1 / Math.max(dt, 1e-4) - fps) * 0.05;

  acc += dt;
  while (acc >= FIXED_DT) {
    stepPlayer(FIXED_DT);
    acc -= FIXED_DT;
  }

  streamer.update(player.x, player.z);
  sanctuaries.update(dt, player.x, player.z);
  // The camera must settle BEFORE the gun reads it — firing off last frame's camera is a
  // subtle, maddening "my shots trail my aim" bug when you're turning fast.
  rig.update(dt, input.aim);

  // Weapons stow inside the walls. Gated HERE rather than inside gun.js, for the same
  // reason the damage rule lives in damagePlayer: systems don't learn each other's names,
  // and "what does a sanctuary mean" belongs in one place.
  inSafe = sanctuaryOf(player.x, player.z, 0) !== null;
  const inSafeZone = inSafe;

  if (input.firing && !inSafeZone) {
    const before = gun.mag;
    const hit = gun.tryFire(rig.blend > 0.5, gunRng, [...mobs.targets(), ...boss.targets()]);
    if (gun.mag !== before) markCombat();     // a shot fired, hit or miss
    if (hit?.targetId != null) {
      if (hit.targetTag === "boss" || hit.targetTag === "bossWeak") {
        const res = boss.hit(hit.targetTag, GUN.damage * player.dmgMult);
        if (res?.killed) { rewardBoss(res.ring); grenades.refill(GRENADE.max); }
        else if (res?.weak) killFeed = "core hit ×2.5";
      } else {
        const res = mobs.hit(hit.targetId, GUN.damage * player.dmgMult);
        if (res?.killed) { reward(res); grenades.refill(); }
      }
    }
  }
  if (input.throwQueued) {
    input.throwQueued = false;
    if (inSafeZone) {
      tradeMsg = "weapons stowed inside the walls";
      tradeMsgT = 2;
    } else if (grenades.throwFrom(camera)) {
      killFeed = "";
      markCombat();
    }
  }
  grenades.update(dt, blast);

  if (input.healQueued) {
    input.healQueued = false;
    if (inSafeZone) {
      tradeMsg = "no need — the walls mend you";
      tradeMsgT = 2;
    } else {
      heal.start();
    }
  }
  // The root condition, in one expression: steering, rolling, or airborne all break it.
  const stirring = input.fwd !== 0 || input.right !== 0 || player.dodgeT > 0 || !player.onGround;
  heal.update(dt, stirring);

  gun.update(dt);
  mobs.update(dt, hurtPlayer);
  folk.update(dt);
  villagers.update(dt);

  // A boss wanders in on a timer once you're past the Commons. The countdown only runs
  // while you're ELIGIBLE — burning attempts in the safe zone is what made this look broken.
  if (!boss.active) {
    if (boss.eligible) {
      bossTimer -= dt;
      if (bossTimer <= 0) {
        bossTimer = BOSS.retry;
        if (boss.maybeSpawn()) killFeed = "something out there answers";
      }
    } else {
      bossTimer = Math.min(bossTimer, BOSS.retry);
    }
  }
  boss.update(dt,
    (dmg, bx, bz) => damagePlayer(dmg, bx, bz, 9),
    (dmg, mx, mz) => damagePlayer(dmg, mx, mz, 7));

  // Impact shake — applied AFTER the rig sets the camera, so it perturbs the final pose
  // rather than fighting the rig's own smoothing.
  if (boss.shake > 0) {
    const s = boss.shake * 0.45;
    camera.position.x += (shakeRng() - 0.5) * s;
    camera.position.y += (shakeRng() - 0.5) * s;
    camera.position.z += (shakeRng() - 0.5) * s;
  }

  // Regeneration needs BOTH: you've stopped fighting, and nothing is still hunting you.
  // Being chased is combat even if neither side has landed a hit yet — otherwise you could
  // regen while kiting a pack, which is the exact situation it should not rescue.
  if (combatT > 0) combatT -= dt;
  hunted = mobs.anyHunting() || (boss.active
    && Math.hypot(boss.alive.x - player.x, boss.alive.z - player.z) < BOSS.aggroRange);
  if (combatT <= 0 && !hunted && player.hp < player.maxHp) {
    player.hp = Math.min(player.maxHp,
      player.hp + REGEN.rate * (inSafe ? REGEN.safeMult : 1) * dt);
  }

  minimap.draw(dt, mobs, boss, folk);

  const vendor = villagers.nearest();
  if (tradeMsgT > 0) tradeMsgT -= dt;
  if (vendor || tradeMsgT > 0) {
    subEl.textContent = tradeMsgT > 0 ? tradeMsg
      : vendor.role.offer
        ? `${vendor.role.name} — F: ${vendor.role.label} (${vendor.role.price}g)`
        : `${vendor.role.name}`;
    subEl.style.opacity = "1";
    subtitleT = 0;
  } else if (subtitleT > 0) {
    subtitleT -= dt;
    subEl.textContent = subtitle;
    subEl.style.opacity = String(Math.min(1, subtitleT));
  } else if (subEl.style.opacity !== "0") {
    subEl.style.opacity = "0";
  }

  if (hurtT > 0) {
    hurtT -= dt;
    hurtEl.style.opacity = String(Math.max(0, hurtT / 0.35) * 0.55);
  }

  // Socket 2 in practice: the render layer READS sim state and owns none of it.
  body.position.set(player.x, player.y + 0.9, player.z);
  body.rotation.y = player.yaw;
  body.visible = rig.blend < 0.85;      // hide your own head in first person

  const ring = ringAt(player.x, player.z);
  const tier = tierAt(player.x, player.z);
  const fromSpawn = Math.hypot(player.x, player.z);
  const toNextRing = RING_SIZE * (ring + 1) - fromSpawn;
  const bossStatus = boss.active ? ""
    : boss.eligible ? `boss  inbound ~${Math.ceil(bossTimer)}s\n`
      : `boss  none in ${RINGS[0].name} — ${Math.ceil(RING_SIZE - fromSpawn)}m to ${RINGS[1].name}\n`;
  const bossLine = boss.active
    ? `BOSS ${"█".repeat(Math.max(0, Math.round(boss.alive.hp / boss.alive.maxHp * 20)))}` +
      `${"░".repeat(Math.max(0, 20 - Math.round(boss.alive.hp / boss.alive.maxHp * 20)))}` +
      ` ${Math.max(0, Math.round(boss.alive.hp))}  ${boss.alive.phase === 2 ? "· ENRAGED ·" : ""}\n`
    : "";
  hud.textContent =
    bossLine + bossStatus +
    `${nearestGate()}\n` +
    `${RINGS[ring].name}  (tier ${tier})   ${Math.round(fromSpawn)}m out` +
    `${ring + 1 < RINGS.length ? `   next ring ${Math.max(0, Math.ceil(toNextRing))}m` : ""}\n` +
    `xyz  ${player.x.toFixed(1)} ${player.y.toFixed(1)} ${player.z.toFixed(1)}\n` +
    `cam  ${rig.mode}   look ${CAMERA.sensitivity.toFixed(4)}  [ / ]\n` +
    `LVL ${player.level}  dmg ×${player.dmgMult.toFixed(2)}  spd ×${player.speedMult.toFixed(2)}  jmp ×${player.jumpMult.toFixed(2)}\n` +
    `    ${"▮".repeat(Math.round(levelProgress() * 12))}` +
    `${"▯".repeat(12 - Math.round(levelProgress() * 12))} ${player.xp}/${xpToNext(player.level)}xp\n` +
    `hp   ${"█".repeat(Math.max(0, Math.round(player.hp / 10)))}${"░".repeat(Math.max(0, 10 - Math.round(player.hp / 10)))} ` +
    `${Math.max(0, Math.round(player.hp))}` +
    `${player.hp < player.maxHp
      ? hunted ? "  (hunted)"
        : combatT > 0 ? `  (${combatT.toFixed(0)}s)`
          : inSafe ? "  ▲▲" : "  ▲"
      : ""}` +
    `   kills ${mobs.killed}  born ${mobs.born}  packs ${mobs.packs.size}  ${killFeed}\n` +
    `heal ${heal.casting
      ? `${"▰".repeat(Math.round(heal.progress * 10))}${"▱".repeat(10 - Math.round(heal.progress * 10))} HOLD STILL`
      : heal.cooldown > 0 ? `ready in ${Math.ceil(heal.cooldown)}s` : "ready  Q"}` +
    `${heal.lastResult ? `   ${heal.lastResult}` : ""}\n` +
    `gold ${player.gold}   potions ${player.potions}${player.gearDmg ? `   gear +${Math.round(player.gearDmg * 100)}%` : ""}\n` +
    `nade ${"●".repeat(grenades.count)}${"○".repeat(Math.max(0, GRENADE.max - grenades.count))}` +
    `${grenades.cooldown > 0 ? "  (cd)" : ""}   E throw\n` +
    `gun  ${inSafeZone ? "stowed (safe zone)" : gun.reloading > 0 ? "reloading…" : `${gun.mag}/${GUN.magSize}`}` +
    `   ${player.iframes > 0 ? "· I-FRAMES ·" : player.dodgeCd > 0 ? "dodge cd" : "dodge ready"}\n` +
    `${bridge.label}${speaking ? "  ·  thinking…" : ""}\n` +
    `in   fwd ${input.fwd >= 0 ? " " : ""}${input.fwd} str ${input.right >= 0 ? " " : ""}${input.right}` +
    `  ${input.aimHeld ? "AIM" : "---"}${input.aim ? "*" : " "}` +
    `  ${player.dodgeT > 0 ? "ROLL" : "    "}  ${player.onGround ? "grnd" : "air "}\n` +
    `fps  ${fps.toFixed(0)}   chunks ${streamer.loaded.size}   ` +
    `jumps ${"◆".repeat(player.jumpsLeft)}${"◇".repeat(Math.max(0, player.maxJumps - player.jumpsLeft))}`;

  renderer.render(scene, camera);
}
requestAnimationFrame(frame);
