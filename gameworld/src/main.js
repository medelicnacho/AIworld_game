// Entry point. Slice 1 of M1: a world you can walk around in.
//
// The loop is deliberately split: PHYSICS runs on a fixed step (feel must not depend on
// framerate), RENDER runs per frame. The substrate's 10Hz tick will slot in as a third
// clock at M3 — the same split localprototype/world/sim.py already uses to keep its fast
// clocks off the slow model calls.

import * as THREE from "three";
import { CAMERA, GUN, MOB, BOSS, GRENADE, HEAL, FIRERING, DASH, REGEN, LOOT, VILLAGE, VIEW_RADIUS, CHUNK_X, RING_SIZE, RINGS } from "./config.js";
import { Mobs } from "./mobs/mobs.js";
import { Boss } from "./mobs/boss.js";
import { Folk } from "./mobs/folk.js";
import { Villagers } from "./town/villagers.js";
import { Shop } from "./ui/shop.js";
import { ICONS } from "./ui/icons.js";
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
import { Abilities, SLOTS } from "./player/abilities.js";
import { Minimap } from "./ui/minimap.js";
import { Bridge } from "./net/bridge.js";
import { award, killValue, bossValue, xpToNext, levelProgress, loseLevel, applyLevelStats } from "./prog/xp.js";
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
const abilities = new Abilities({
  get grenades() { return grenades; },
  get heal() { return heal; },
  camera,
});
// Ring of Fire: an expanding wall of flame. The mesh is created once and reused — the
// ability is on a long cooldown, so two can never overlap.
const fireRingMesh = (() => {
  const g = new THREE.RingGeometry(0.55, 1.0, 48);
  g.rotateX(-Math.PI / 2);
  const m = new THREE.Mesh(g, new THREE.MeshBasicMaterial({
    color: 0xff7a1e, transparent: true, opacity: 0, side: THREE.DoubleSide, depthWrite: false,
  }));
  m.visible = false;
  scene.add(m);
  return m;
})();
const fireLight = new THREE.PointLight(0xff8a2e, 0, 40);
scene.add(fireLight);
let fireT = 0;

function fireRing() {
  fireT = FIRERING.grow;
  fireRingMesh.position.set(player.x, player.y + 0.35, player.z);
  fireRingMesh.visible = true;
  fireLight.position.set(player.x, player.y + 2, player.z);
  sfx.explosion(player.x, player.z, 1.6);
  // Reuses the same blast path as everything else; hurtsYou = false, since it's centred
  // on you and a ring that killed its caster would be a joke.
  blast(player.x, player.y + 1, player.z,
        FIRERING.radius, FIRERING.damage, FIRERING.knock, false);
  markCombat();
}

// Dash Strike. The damage is a LINE test, not a radius: only what you actually cut through
// is hit, which is what makes aiming it the whole skill.
const dashTrail = (() => {
  const m = new THREE.Mesh(
    new THREE.BoxGeometry(1, 0.9, 1),
    new THREE.MeshBasicMaterial({ color: 0x9be8ff, transparent: true, opacity: 0, depthWrite: false }),
  );
  m.visible = false;
  scene.add(m);
  return m;
})();
let dashFx = 0;

/** Distance from a point to a segment, on the ground plane. */
function segDist(px, pz, x0, z0, x1, z1) {
  const dx = x1 - x0, dz = z1 - z0;
  const len2 = dx * dx + dz * dz;
  const t = len2 ? Math.max(0, Math.min(1, ((px - x0) * dx + (pz - z0) * dz) / len2)) : 0;
  return Math.hypot(px - (x0 + dx * t), pz - (z0 + dz * t));
}

function dashStrike() {
  const dir = new THREE.Vector3();
  camera.getWorldDirection(dir);
  dir.y = 0;
  if (dir.lengthSq() < 1e-6) return false;
  dir.normalize();

  player.dashX = dir.x;
  player.dashZ = dir.z;
  player.dashT = DASH.time;
  player.iframes = Math.max(player.iframes, DASH.time + DASH.iframePad);

  const x0 = player.x, z0 = player.z;
  const len = DASH.speed * DASH.time;
  const x1 = x0 + dir.x * len, z1 = z0 + dir.z * len;

  let hits = 0;
  for (const e of [...world.entities.values()]) {
    if (e.kind !== "mob") continue;
    if (segDist(e.x, e.z, x0, z0, x1, z1) > DASH.radius) continue;
    const res = mobs.hit(e.id, DASH.damage * player.dmgMult);
    hits++;
    if (res?.killed) { reward(res); grenades.refill(); }
  }
  if (boss.active
      && segDist(boss.alive.x, boss.alive.z, x0, z0, x1, z1) < DASH.radius + BOSS.contactRange * 0.5) {
    const res = boss.hit("boss", DASH.damage * player.dmgMult);
    hits++;
    if (res?.killed) { rewardBoss(res.ring); grenades.refill(GRENADE.max); }
  }

  // Draw the line you cut.
  dashTrail.position.set((x0 + x1) / 2, player.y + 1, (z0 + z1) / 2);
  dashTrail.rotation.y = Math.atan2(dir.x, dir.z);
  dashTrail.scale.set(DASH.radius * 1.4, 1, len);
  dashTrail.visible = true;
  dashFx = 0.3;

  sfx.whoosh();
  if (hits) sfx.explosion(x1, z1, 0.6);
  markCombat();
  return true;
}

// The bar is two groups: bought ITEMS on 1-4, then the general abilities you always have.
// They read the same way but are never confusable with stock you can buy.
const GENERAL = [
  {
    key: "E", name: "Firebomb", icon: "octagon",
    cooldown: () => grenades.cooldown, ready: () => grenades.ready,
    charges: () => grenades.count,
  },
  {
    key: "Q", name: "Heal", icon: "plus",
    cooldown: () => heal.cooldown, ready: () => heal.cooldown <= 0 && !heal.casting,
  },
  {
    key: "C", name: "Potion", icon: "flask",
    cooldown: () => player.potionCd,
    ready: () => player.potionCd <= 0 && player.potions > 0,
    charges: () => player.potions,
  },
];

const slotHtml = (key) => `
  <div class="slot">
    <span class="k">${key}</span>
    <span class="ic"></span><span class="n"></span>
    <span class="ch"></span><span class="cool"></span>
  </div>`;

const barEl = document.getElementById("bar");
barEl.innerHTML = Array.from({ length: SLOTS }, (_, i) => slotHtml(i + 1)).join("")
  + `<div class="sep"></div>`
  + GENERAL.map((g) => slotHtml(g.key)).join("");
const allSlots = [...barEl.querySelectorAll(".slot")];
const barSlots = allSlots.slice(0, SLOTS);
const genSlots = allSlots.slice(SLOTS);
const pointsEl = document.getElementById("points");
const minimap = new Minimap(document.getElementById("minimap"));
const sanctuaries = new Sanctuaries(scene);
const folk = new Folk(scene);
const villagers = new Villagers(scene);
let tradeMsg = "", tradeMsgT = 0;
const shop = new Shop(document.getElementById("shop"), {
  get grenades() { return grenades; },
  get abilities() { return abilities; },
  fireRing,
  dashStrike,   // lazily read: grenades is defined further down
  applyStats: () => applyLevelStats(),  // gear changes re-derive the same way levels do
  onClose: () => resumeFromShop(),
});

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
  player.points += Math.round((LOOT.base + LOOT.perTier * res.ring)
    * (res.elite ? LOOT.eliteMult : 1));
  const xp = killValue(res.ring, res.elite);
  const lv = award(xp);
  killFeed = `${res.elite ? "★ elite" : "kill"}  +${xp}xp${lv ? `   ▲ LEVEL ${player.level}` : ""}`;
  if (lv) sfx.healDone();
}

function rewardBoss(ring) {
  player.points += Math.round((LOOT.base + LOOT.perTier * ring) * LOOT.bossMult);
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
function blast(x, y, z, radius = GRENADE.radius, damage = GRENADE.damage,
               knock = GRENADE.knockback, hurtsYou = true) {
  const falloff = (d) => Math.max(0.25, 1 - d / radius);

  for (const e of [...world.entities.values()]) {
    if (e.kind !== "mob") continue;
    const d = Math.hypot(e.x - x, e.z - z, (e.y - y) * 0.5);
    if (d > radius) continue;
    const res = mobs.hit(e.id, damage * player.dmgMult * falloff(d));
    if (res?.killed) { reward(res); grenades.refill(); }
  }

  if (boss.active) {
    const b = boss.alive;
    const d = Math.hypot(b.x - x, b.z - z);
    if (d < radius + BOSS.contactRange * 0.5) {
      const res = boss.hit("boss", damage * player.dmgMult * falloff(Math.max(0, d - BOSS.contactRange * 0.5)));
      if (res?.killed) { rewardBoss(res.ring); grenades.refill(GRENADE.max); }
    }
  }

  // You are not exempt. Half damage, but a point-blank throw will still hurt badly —
  // which is what makes it a decision rather than a free button.
  // Cataclysm is centred on you, so it must not blow you up — hence hurtsYou.
  const dp = Math.hypot(player.x - x, player.z - z, (player.y - y) * 0.5);
  if (hurtsYou && dp < radius) {
    damagePlayer(damage * falloff(dp) * GRENADE.selfScale, x, z, knock);
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
  interact: () => {
    const v = villagers.nearest();
    if (!v) return;
    shop.show(v);
  },
  ability: (i) => {
    if (inSafe) { tradeMsg = "weapons stowed inside the walls"; tradeMsgT = 2; return; }
    const msg = abilities.use(i);
    if (msg) { tradeMsg = msg; tradeMsgT = 1.2; }
    else markCombat();
  },
  drink: () => {
    if (player.potionCd > 0) {
      tradeMsg = `potion — ${player.potionCd.toFixed(1)}s`;
      tradeMsgT = 1.2;
      return;
    }
    if (player.potions <= 0) { tradeMsg = "no potions"; tradeMsgT = 2; return; }
    if (player.hp >= player.maxHp) { tradeMsg = "already whole"; tradeMsgT = 2; return; }
    player.potions--;
    player.potionCd = VILLAGE.potionCd;
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
  onUnlock: () => {
    // Belt and braces for the same collision: ignore an unlock that lands in the moment
    // after a deliberate resume, so a stray release can never re-pause what we just resumed.
    if (performance.now() - resumedAt < 900) return;
    setPaused(true);
  },
  // Look control is allowed whenever the game is actually RUNNING, lock or no lock. The
  // only time it must be off is while a panel owns the cursor.
  lookUnlocked: () => !paused && !shop.open,
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

/**
 * Leaving a vendor must resume the GAME, whether or not the browser will give the mouse
 * back yet. Chrome refuses requestPointerLock for ~1.25s after Escape is pressed — so
 * asking on close and waiting for the lock to confirm meant Escape reliably dumped you on
 * the pause screen. Unpause immediately; chase the lock separately and retry until it takes.
 */
let lockTries = 0, resumedAt = 0;

function tryLock() {
  const el = renderer.domElement;
  if (paused || document.pointerLockElement === el) return;
  el.requestPointerLock?.();
}

function resumeFromShop() {
  setPaused(false);
  lockTries = 0;
  resumedAt = performance.now();
  // Do NOT request the lock inside the Escape keypress. Our handler runs first, takes the
  // lock — and then the browser's OWN Escape handling runs and releases it again, which
  // fires onUnlock and re-pauses. That is the "unpauses then instantly pauses" loop: one
  // key press doing both jobs. Wait until the key event is completely finished.
  setTimeout(tryLock, 350);
}

document.addEventListener("pointerlockerror", () => {
  // Denied — almost always the post-Escape cooldown. Wait it out and ask again.
  if (paused || lockTries++ > 4) return;
  setTimeout(tryLock, 400 + lockTries * 400);
});

function setPaused(p) {
  paused = p;
  document.body.classList.toggle("running", !p);
  // Shopping pauses the WORLD but not the soundtrack: you are standing in a town talking to
  // someone, and the town's music cutting out is the tell that you've left the game. A real
  // pause (Escape to the menu) still silences everything.
  music.setPaused(p && !shop.open);
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
      markCombat();
    }
  }
  grenades.update(dt, blast);

  // The root condition, in one expression: steering, rolling, or airborne all break it.
  if (input.healQueued) {
    input.healQueued = false;
    if (inSafeZone) {
      tradeMsg = "no need — the walls mend you";
      tradeMsgT = 2;
    } else {
      heal.start();
    }
  }
  const stirring = input.fwd !== 0 || input.right !== 0 || player.dodgeT > 0 || !player.onGround;
  heal.update(dt, stirring);
  abilities.update(dt);
  if (dashFx > 0) {
    dashFx -= dt;
    dashTrail.material.opacity = Math.max(0, dashFx / 0.3) * 0.55;
    if (dashFx <= 0) dashTrail.visible = false;
  }
  if (fireT > 0) {
    fireT -= dt;
    const f = 1 - Math.max(0, fireT) / FIRERING.grow;
    fireRingMesh.scale.setScalar(1 + f * FIRERING.radius);
    fireRingMesh.material.opacity = (1 - f) * 0.9;
    fireLight.intensity = (1 - f) * 30;
    if (fireT <= 0) { fireRingMesh.visible = false; fireLight.intensity = 0; }
  }

  pointsEl.innerHTML = `${player.points} <small>POINTS</small>`;
  const paint = (el, def, left, ready) => {
    el.classList.toggle("up", !!def && ready);
    el.classList.toggle("empty", !def);
    // Icons are static per slot — only rewrite the SVG when the slot's contents change,
    // rather than reparsing markup 60 times a second for a picture that never moves.
    const icon = def?.icon || "";
    if (el.dataset.icon !== icon) {
      el.dataset.icon = icon;
      el.querySelector(".ic").innerHTML = ICONS[icon] || "";
    }
    el.querySelector(".n").textContent = def?.name || "";
    el.querySelector(".ch").textContent = def?.charges ? "●".repeat(def.charges()) : "";
    el.title = def?.desc || "empty";
    el.querySelector(".cool").textContent = left > 0 ? left.toFixed(left < 3 ? 1 : 0) : "";
  };
  barSlots.forEach((el, i) => {
    const a = abilities.slots[i];
    el.querySelector(".k").textContent = a?.key || String(i + 1);
    paint(el, a, abilities.cooldownOf(i), abilities.readyOf(i));
  });
  genSlots.forEach((el, i) => {
    const g = GENERAL[i];
    paint(el, g, g.cooldown(), g.ready());
  });

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
    (dmg, mx, mz) => damagePlayer(dmg, mx, mz, 7),
    // The beam burns continuously, so it deals damage with NO knockback — being shoved
    // every frame while standing in it would fight the very movement it is demanding.
    (dmg, bx, bz) => damagePlayer(dmg, bx, bz, 0));

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
  music.setPlace(inSafe ? "town" : "world");

  if (player.potionCd > 0) player.potionCd -= dt;
  if (combatT > 0) combatT -= dt;
  hunted = mobs.anyHunting() || (boss.active
    && Math.hypot(boss.alive.x - player.x, boss.alive.z - player.z) < BOSS.aggroRange);
  if (combatT <= 0 && !hunted && player.hp < player.maxHp) {
    player.hp = Math.min(player.maxHp,
      player.hp + REGEN.rate * (inSafe ? REGEN.safeMult : 1) * dt);
  }

  minimap.draw(dt, mobs, boss, folk);

  const vendor = shop.open ? null : villagers.nearest();
  if (tradeMsgT > 0) tradeMsgT -= dt;
  if (vendor || tradeMsgT > 0) {
    subEl.textContent = tradeMsgT > 0 ? tradeMsg
      : vendor.role.offer
        ? `${vendor.role.name} — press F to trade`
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
          : "  ▲"
      : ""}` +
    `   kills ${mobs.killed}  born ${mobs.born}  packs ${mobs.packs.size}  ${killFeed}\n` +
    `${heal.casting
      ? `${"▰".repeat(Math.round(heal.progress * 10))}${"▱".repeat(10 - Math.round(heal.progress * 10))} HOLD STILL\n`
      : ""}` +
    `${player.gearDmg ? `   gear +${Math.round(player.gearDmg * 100)}%` : ""}\n` +

    `gun  ${inSafeZone ? "stowed (safe zone)" : gun.reloading > 0 ? "reloading…" : `${gun.mag}/${GUN.magSize}`}` +
    `   ${player.iframes > 0 ? "· I-FRAMES ·" : player.dodgeCd > 0 ? "dodge cd" : "dodge ready"}\n` +
    `${bridge.label}${speaking ? "  ·  thinking…" : ""}\n` +
    `${!paused && document.pointerLockElement !== renderer.domElement
      ? "click to restore mouse look\n" : ""}` +
    `in   fwd ${input.fwd >= 0 ? " " : ""}${input.fwd} str ${input.right >= 0 ? " " : ""}${input.right}` +
    `  ${input.aimHeld ? "AIM" : "---"}${input.aim ? "*" : " "}` +
    `  ${player.dodgeT > 0 ? "ROLL" : "    "}  ${player.onGround ? "grnd" : "air "}\n` +
    `fps  ${fps.toFixed(0)}   chunks ${streamer.loaded.size}   ` +
    `jumps ${"◆".repeat(player.jumpsLeft)}${"◇".repeat(Math.max(0, player.maxJumps - player.jumpsLeft))}`;

  renderer.render(scene, camera);
}
requestAnimationFrame(frame);
