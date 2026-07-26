// Entry point. Slice 1 of M1: a world you can walk around in.
//
// The loop is deliberately split: PHYSICS runs on a fixed step (feel must not depend on
// framerate), RENDER runs per frame. The substrate's 10Hz tick will slot in as a third
// clock at M3 — the same split localprototype/world/sim.py already uses to keep its fast
// clocks off the slow model calls.

import * as THREE from "three";
import { CAMERA, MOB, BOSS, GRENADE, HEAL, FIRERING, DASH, WHIRL, REGEN, LOOT, DROP, VILLAGE, VIEW_RADIUS, CHUNK_X, RINGS, ARMOR, ARMOR_SLOT_ORDER, TIMEWARP, ORB, NOVA, CHAIN, SPRINT, SPIN, WEAPONS, DIFFICULTY, RAID, BUILD_TAG, ENERGY, BLAST_VSCALE } from "./config.js";
import { Mobs } from "./mobs/mobs.js";
import { affixList, brokenAffixes } from "./mobs/affixes.js";
import { Boss } from "./mobs/boss.js";
import { Villagers } from "./town/villagers.js";
import { TownVoice } from "./town/voice.js";
import { TownChat } from "./town/chat.js";
import { Raids } from "./town/raid.js";
import { Shop, GOODS, statLine } from "./ui/shop.js";
import { ICONS } from "./ui/icons.js";
import { Inventory } from "./ui/inventory.js";
import { Nameplates } from "./ui/nameplates.js";
import { HealthBars } from "./ui/healthbars.js";
import { DamageText } from "./ui/damagetext.js";
import { armorDR } from "./prog/stats.js";
import { rollGear, vendorPiece, sellValue, RARITY } from "./prog/gear.js";
import { repForTurnIn, repForBoss, gainRep, myFaction, repProgress, isMyAlly, isHostileSanctuary, servesYou, factionOfTown, playerColor } from "./prog/factions.js";
import { player, spawnPlayer, world } from "./state.js";
import { ChunkStreamer } from "./world/streamer.js";
import { ringAt, tierAt, tierStart, groundY, solidAt, surfaceNear } from "./world/gen.js";
import { Sanctuaries, sanctuariesNear, boundaryAt, homeOfTier, sanctuaryUnder, wallNormalAt, wallBlocks, WALL_H } from "./world/sanctuary.js";
import { attachInput, input, stepPlayer } from "./player/controller.js";
import { CameraRig } from "./player/camera.js";
import { Gun } from "./player/gun.js";
import { Music } from "./audio/music.js";
import { sfx } from "./audio/sfx.js";
import { Grenades } from "./player/grenade.js";
import { Heal } from "./player/heal.js";
import { Abilities, SLOTS, SLOT_KEYS } from "./player/abilities.js";
import { Minimap } from "./ui/minimap.js";
import { Bridge } from "./net/bridge.js";
import { award, killValue, bossValue, xpToNext, levelProgress, loseLevel, applyLevelStats, respawnTierFor, xpLevelMult, altitudeBonus } from "./prog/xp.js";
import { save as saveGame, load as loadSave, restore as restoreSave, hasSave, wipe as wipeSave } from "./prog/save.js";
import { mulberry32 } from "./rng.js";
import { deeds } from "./world/events.js";
import { WarCries } from "./mobs/warcry.js";
import { voiceQueue } from "./net/queue.js";
import { DayNight } from "./world/daynight.js";
import { setDifficulty, diff } from "./prog/difficulty.js";

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

const hemi = new THREE.HemisphereLight(0xbcd8f0, 0x4a4a44, 0.85);
scene.add(hemi);
const sun = new THREE.DirectionalLight(0xfff2dd, 1.15);
sun.position.set(0.5, 1, 0.3);
scene.add(sun);

// The player's body. A box until M1 gets a real model — but it exists from day one because
// third person is the default (D3), and you cannot tune a follow camera against nothing.
// Slimmer than the collision capsule on purpose: a body that exactly fills its hitbox looks
// bulky in third person and hides more of the screen than it needs to.
const body = new THREE.Mesh(
  new THREE.BoxGeometry(0.42, 1.25, 0.3),
  // Painted by paintPlayer() below: the wanderer WEARS their banner. Rust until sworn.
  new THREE.MeshLambertMaterial({ color: 0xd8734a }),
);
scene.add(body);

/**
 * THE WANDERER WEARS THEIR BANNER. Swear to Iron and you go black; Ash, blue; Vale, green
 * — the same three war-colours every camp, town and garrison in the world already flies,
 * so in third person you can see at a glance which side of the map is yours. Unaligned
 * stays rust, a colour none of the three owns: having no banner should LOOK like having
 * no banner. Called on join, on switch, and on load — every door allegiance changes by.
 */
function paintPlayer() {
  body.material.color.setHex(playerColor());
}

const streamer = new ChunkStreamer(scene);
const rig = new CameraRig(camera);
const music = new Music();
// Bulletproof audio start: a browser may refuse to start media from the pointer-lock handler
// (it isn't always a "user activation" context), so ALSO kick the soundtrack from the first
// raw clicks/keys, and retry on every gesture until playback actually sticks. start()/resume()
// are idempotent, so hammering them is safe.
const kickAudio = () => { music.start(); music.resume(); };

// THE GLOBAL FADER. One number scales every sound the game makes — effects and voices
// (sfx master) and the soundtrack (music master) — set from the pause screen, remembered
// between sessions. Audio you cannot turn down is audio that gets muted entirely.
const VOL_KEY = "gw.volume", MUSIC_KEY = "gw.volMusic", VOICE_KEY = "gw.volVoice";
function setVolume(v) {
  v = Math.max(0, Math.min(2, v));   // up to 200%: the sfx limiter absorbs the push
  sfx.setVolume(v);
  music.setMaster(v);
  try { localStorage.setItem(VOL_KEY, String(v)); } catch { /* private mode; play on */ }
  return v;
}
// BALANCE, not loudness. The global fader can only answer "everything is too loud"; these two
// answer "the music is buried under the villagers", which is a different complaint and the
// one people actually have. Both sit UNDER the global fader rather than beside it.
function setMusicVolume(v) {
  v = Math.max(0, Math.min(2, v));
  music.setUser(v);
  try { localStorage.setItem(MUSIC_KEY, String(v)); } catch { /* private mode; play on */ }
  return v;
}
function setVoiceVolume(v) {
  v = Math.max(0, Math.min(2, v));
  sfx.setVoiceVolume(v);
  try { localStorage.setItem(VOICE_KEY, String(v)); } catch { /* private mode; play on */ }
  return v;
}
for (const [key, apply] of [[VOL_KEY, setVolume], [MUSIC_KEY, setMusicVolume], [VOICE_KEY, setVoiceVolume]]) {
  const saved = parseFloat(localStorage.getItem(key) ?? "");
  if (Number.isFinite(saved)) apply(saved);
}
addEventListener("pointerdown", kickAudio);
addEventListener("keydown", kickAudio);
const gun = new Gun(scene, camera);
const gunRng = mulberry32(0xBADA55);    // D14: even bullet spread is seeded
// Affix hooks reach the world through this, rather than mobs.js importing main's
// damage routing and creating a cycle. blast is a hoisted declaration, so this is safe here.
const mobs = new Mobs(scene, 0x5EED, { blast, damagePlayer });
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

function fireRing(knock = false) {
  fireT = FIRERING.grow;
  fireRingMesh.position.set(player.x, player.y + 0.35, player.z);
  fireRingMesh.visible = true;
  fireLight.position.set(player.x, player.y + 2, player.z);
  sfx.explosion(player.x, player.z, 1.6);
  // Reuses the same blast path as everything else; hurtsYou = false, since it's centred
  // on you and a ring that killed its caster would be a joke.
  blast(player.x, player.y + 1, player.z,
        FIRERING.radius, FIRERING.damage, FIRERING.knock, false, false, knock, "spell");
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
    const res = mobs.hit(e.id, DASH.damage * player.dmgMult * (1 + (player.dmgSpell || 0)));
    hits++;
    if (res?.killed) { reward(res); grenades.refill(); }
  }
  if (boss.active
      && segDist(boss.alive.x, boss.alive.z, x0, z0, x1, z1) < DASH.radius + BOSS.contactRange * 0.5) {
    // Read the position BEFORE the hit: a killing blow despawns the boss, and the relic
    // has to fall where it stood.
    const bx = boss.alive.x, bz = boss.alive.z;
    const res = boss.hit("boss", DASH.damage * player.dmgMult * (1 + (player.dmgSpell || 0)));
    hits++;
    if (res?.killed) { rewardBoss(res.ring, bx, bz); grenades.refill(GRENADE.max); }
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

// Whirlwind. Two phases: a leap that ends in a slam, then a spin you keep moving through.
const whirlRing = (() => {
  const g = new THREE.RingGeometry(0.5, 1.0, 40);
  g.rotateX(-Math.PI / 2);
  const m = new THREE.Mesh(g, new THREE.MeshBasicMaterial({
    color: 0xffd9a0, transparent: true, opacity: 0, side: THREE.DoubleSide, depthWrite: false,
  }));
  m.visible = false;
  scene.add(m);
  return m;
})();
const spinRing = (() => {
  // Inner/outer straight from the damage radius: one number, one truth.
  const g = new THREE.RingGeometry(WHIRL.spinRadius * 0.45, WHIRL.spinRadius, 48);
  g.rotateX(-Math.PI / 2);
  const m = new THREE.Mesh(g, new THREE.MeshBasicMaterial({
    color: 0xbfe4ff, transparent: true, opacity: 0, side: THREE.DoubleSide, depthWrite: false,
  }));
  m.visible = false;
  scene.add(m);
  return m;
})();
let slamFx = 0, whirlTick = 0;

function whirlwind() {
  // Paid before anything happens, and refused outright if you cannot afford it — so the spin
  // can never end early and leave you standing in the open without the invulnerability you
  // committed to. Returning false spends nothing, exactly like every other refusal.
  if (player.energy < ENERGY.whirl) { flashStarved(); return false; }
  const dir = new THREE.Vector3();
  camera.getWorldDirection(dir);
  dir.y = 0;
  if (dir.lengthSq() < 1e-6) return false;
  dir.normalize();

  player.leapX = dir.x;
  player.leapZ = dir.z;
  player.leapT = WHIRL.leapTime;
  player.leapPending = true;
  player.vy = WHIRL.leapUp;
  player.onGround = false;
  player.iframes = Math.max(player.iframes, WHIRL.leapTime + 0.15);
  sfx.whoosh();
  markCombat();
  return true;
}

/** The landing. Ends the leap, hits everything around, and starts the spin. */
function whirlSlam() {
  player.leapT = 0;
  player.leapPending = false;
  blast(player.x, player.y + 1, player.z,
        WHIRL.slamRadius, WHIRL.slamDamage, 14, false, false, false, "spell");
  whirlRing.position.set(player.x, player.y + 0.3, player.z);
  whirlRing.visible = true;
  slamFx = 0.45;
  sfx.explosion(player.x, player.z, 1.3);
  player.energy = Math.max(0, player.energy - ENERGY.whirl);
  player.whirlT = WHIRL.spinTime;
  whirlTick = 0;
}

// THE CLEAVER'S SPIN (WEAPONS.md). Not a purchased spell — it comes WITH the weapon, which
// is why it lives here beside the abilities rather than in the shop's tables.
//
// Untouchable only for the opening window. The full-length version was safe three seconds in
// every four and, with haste, permanently — which deletes every telegraph in the game. A
// window you have to TIME is a skill, and it is the same skill everything else here teaches:
// read the thing coming at you and answer it.
const spinRingFx = (() => {
  const g = new THREE.RingGeometry(SPIN.radius * 0.5, SPIN.radius, 44);
  g.rotateX(-Math.PI / 2);
  const m = new THREE.Mesh(g, new THREE.MeshBasicMaterial({
    color: 0xcfd9ff, transparent: true, opacity: 0, side: THREE.DoubleSide, depthWrite: false,
  }));
  m.visible = false;
  scene.add(m);
  return m;
})();
let spinTick = 0;

function trySpin() {
  if (player.spinT > 0 || player.spinCd > 0) return;
  player.spinT = SPIN.time;
  // No cooldown yet — it does not start until the spin is over (set in updateSpin). While
  // spinning you are untouchable start to finish; the danger lives in the gap that opens after.
  player.iframes = Math.max(player.iframes, SPIN.iframes);
  spinTick = 0;
  // ONE shove, on the opening beat.
  for (const e of [...world.entities.values()]) {
    if (e.kind !== "mob") continue;
    if (Math.hypot(e.x - player.x, e.z - player.z) > SPIN.radius) continue;
    mobs.push(e, player.x, player.z, SPIN.knock);
  }
  sfx.whoosh();
  markCombat();
}

function updateSpin(dt) {
  if (player.spinCd > 0) player.spinCd -= dt;
  if (player.spinT > 0) {
    player.spinT -= dt;
    // Untouchable the WHOLE spin: keep i-frames topped up to whatever spin time remains.
    player.iframes = Math.max(player.iframes, player.spinT);
    spinTick -= dt;
    if (spinTick <= 0) {
      spinTick = SPIN.tick;
      // Flat to the rim, like Whirlwind: the ring you see is the ring that hits. Through the
      // GUN bucket — this is the weapon working, not a spell.
      blast(player.x, player.y + 1, player.z, SPIN.radius, SPIN.damage, 4, false, true, false, "gun");
    }
    if (player.spinT <= 0) {
      // Spin just ended — NOW the cooldown starts. Haste shortens it, the floor stops haste
      // breaking it, the same rail as everywhere else.
      player.spinCd = Math.max(SPIN.cdFloor, SPIN.cd * (player.hasteCd || 1));
    }
    spinRingFx.visible = true;
    spinRingFx.position.set(player.x, player.y + 0.35, player.z);
    spinRingFx.rotation.y -= dt * 22;
    // Bright the whole spin, because the whole spin is untouchable now.
    spinRingFx.material.opacity = 0.8;
  } else if (spinRingFx.visible) {
    spinRingFx.visible = false;
  }
}

// State for the weapon routing in the frame loop.
let prevRmb = false, wasOverheated = false, lanceVoice = null, beamFlushT = 0;
const beamAcc = new Map();

// ============================ NEW SPELLS ============================
// Ground POOLS: tick spell-damage to mobs inside and optionally slow/root them. Pooled meshes
// like meteors and impacts — never allocated per cast.
const POOL_MAX = 8;
const spellPools = [];
let poolI = 0;
const poolMeshes = (() => {
  const geo = new THREE.CircleGeometry(1, 28);
  geo.rotateX(-Math.PI / 2);
  return Array.from({ length: POOL_MAX }, () => {
    const m = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({
      color: 0xd21e1e, transparent: true, opacity: 0, side: THREE.DoubleSide, depthWrite: false,
    }));
    m.visible = false;
    scene.add(m);
    return m;
  });
})();

function dropPool(x, z, { r, dps, life, tick = 0.3, slowMul = 1, slowT = 0, rootT = 0, color = 0xd21e1e }) {
  const mesh = poolMeshes[poolI = (poolI + 1) % poolMeshes.length];
  const old = spellPools.findIndex((p) => p.mesh === mesh);
  if (old >= 0) spellPools.splice(old, 1);
  mesh.material.color.setHex(color);
  // On the FLOOR IT LANDED ON, not on the land. groundY answers with the ground far below an
  // island, so a pool thrown onto one was drawn hundreds of blocks underneath your feet — you
  // could see the burst, take the damage, and never see where it was burning.
  const py = surfaceNear(x, z, player.y);
  mesh.position.set(x, py + 0.06, z);
  mesh.scale.setScalar(r);
  mesh.visible = true;
  // The FLOOR it was laid on, remembered — the damage test needs to know what "on the ground"
  // means here, and asking again later would answer for wherever the victim is standing.
  spellPools.push({ x, y: py, z, r, dps, t: life, tick, tk: 0, slowMul, slowT, rootT, mesh });
}

function updatePools(dt) {
  for (let i = spellPools.length - 1; i >= 0; i--) {
    const p = spellPools[i];
    p.t -= dt;
    p.mesh.material.opacity = Math.min(1, p.t / 0.5) * 0.45 * (0.7 + 0.3 * Math.sin(performance.now() * 0.008));
    p.tk -= dt;
    if (p.tk <= 0) {
      p.tk = p.tick;
      for (const e of [...world.entities.values()]) {
        if (e.kind !== "mob") continue;
        // A burning pool is a FLOOR, like the burner's fire patch — measured against the
        // surface it was laid on, so it stops scorching things on other levels entirely.
        if (Math.hypot(e.x - p.x, e.z - p.z, (e.y - p.y) * BLAST_VSCALE) > p.r) continue;
        const res = mobs.hit(e.id, p.dps * p.tick * player.dmgMult * (1 + (player.dmgSpell || 0)));
        if (res?.killed) { reward(res); grenades.refill(); }
      }
      if (p.slowT > 0 || p.rootT > 0) mobs.chill(p.x, p.z, p.r, { slowT: p.slowT, slowMul: p.slowMul, rootT: p.rootT });
    }
    if (p.t <= 0) { p.mesh.visible = false; spellPools.splice(i, 1); }
  }
}

// Cataclysm Orb: a red ball that arcs out, bursts, and leaves a DoT pool (slows @r2, roots @r3).
const orbMesh = new THREE.Mesh(new THREE.SphereGeometry(0.6, 14, 14), new THREE.MeshBasicMaterial({ color: 0xff2a1a }));
orbMesh.visible = false;
scene.add(orbMesh);
const orbLight = new THREE.PointLight(0xff3a1a, 0, 22);
scene.add(orbLight);
let orb = null;

function cataclysmOrb(rank = 1) {
  const dir = new THREE.Vector3();
  camera.getWorldDirection(dir);
  orb = {
    x: player.x, y: player.y + 1.4, z: player.z,
    vx: dir.x * ORB.speed, vy: dir.y * ORB.speed + ORB.up, vz: dir.z * ORB.speed, rank, dist: 0,
    bounced: 0,
  };
  orbMesh.visible = true;
  orbMesh.position.set(orb.x, orb.y, orb.z);
  sfx.whoosh();
  markCombat();
}

function updateOrb(dt) {
  if (!orb) return;
  orb.vy += GRENADE.gravity * dt;
  const nx = orb.x + orb.vx * dt, ny = orb.y + orb.vy * dt, nz = orb.z + orb.vz * dt;
  orb.dist += Math.hypot(nx - orb.x, nz - orb.z);
  orbMesh.rotation.x += dt * 9; orbMesh.rotation.y += dt * 7;

  // A TOWN WALL IS NOT VOXELS. It is analytic geometry the voxel test cannot see, so the orb
  // used to sail straight through one and burst in the market behind it. It rebounds now —
  // off the EDGE's own normal rather than the direction away from the town centre, which on a
  // nine-corner town differ by twenty degrees or more and is the gap between a bounce that
  // reads and one that looks like a bug.
  const hitWall = orb.bounced < ORB.bounces ? wallBlocks(nx, nz) : null;
  if (hitWall && ny < hitWall.plateau + WALL_H) {
    const { nx: wx, nz: wz } = wallNormalAt(hitWall, Math.atan2(nz - hitWall.z, nx - hitWall.x));
    const dot = orb.vx * wx + orb.vz * wz;
    orb.vx = (orb.vx - 2 * dot * wx) * ORB.bounce;
    orb.vz = (orb.vz - 2 * dot * wz) * ORB.bounce;
    // Nudged back to the side it came from, or the next frame re-detects the same wall and it
    // sticks to the stone rattling between two reflections.
    orb.x += wx * 1.2; orb.z += wz * 1.2;
    orb.bounced++;
    sfx.hitConfirm(orb.x, orb.z, false);
    orbMesh.position.set(orb.x, orb.y, orb.z);
    orbLight.position.set(orb.x, orb.y, orb.z);
    return;
  }

  if (solidAt(nx, ny, nz) || ny <= groundY(nx, nz) || orb.dist > ORB.range) {
    const bx = orb.x, bz = orb.z;
    // On the floor it actually landed on — groundY answers with the land far below an island.
    blast(bx, surfaceNear(bx, bz, orb.y) + 1, bz, ORB.burstRadius, ORB.burstDamage, 9, false, false, false, "spell");
    const opts = { r: ORB.poolRadius, dps: ORB.poolDps, life: ORB.poolLife, tick: ORB.poolTick };
    if (orb.rank >= 2) { opts.slowMul = ORB.slowMul; opts.slowT = ORB.slowT; }
    if (orb.rank >= 3) opts.rootT = ORB.rootT;
    dropPool(bx, bz, opts);
    sfx.explosion(bx, bz, 1.35);
    orb = null; orbMesh.visible = false; orbLight.intensity = 0;
    return;
  }
  orb.x = nx; orb.y = ny; orb.z = nz;
  orbMesh.position.set(nx, ny, nz);
  orbLight.position.set(nx, ny, nz);
  orbLight.intensity = 14;
}

// Frost Nova: instant ring, damage + a hard slow (rank 2 roots instead).
const novaMesh = (() => {
  const g = new THREE.RingGeometry(0.6, 1.0, 40);
  g.rotateX(-Math.PI / 2);
  const m = new THREE.Mesh(g, new THREE.MeshBasicMaterial({
    color: 0x8fdcff, transparent: true, opacity: 0, side: THREE.DoubleSide, depthWrite: false,
  }));
  m.visible = false; scene.add(m); return m;
})();
let novaFx = 0;

function frostNova(rank = 1) {
  blast(player.x, player.y + 1, player.z, NOVA.radius, NOVA.damage, 6, false, false, false, "spell");
  mobs.chill(player.x, player.z, NOVA.radius, {
    slowT: NOVA.slowT, slowMul: NOVA.slowMul, rootT: rank >= 2 ? NOVA.rootT : 0,
  });
  novaMesh.position.set(player.x, player.y + 0.3, player.z);
  novaMesh.visible = true;
  novaFx = 0.4;
  sfx.explosion(player.x, player.z, 0.7);
  markCombat();
}

// Chain Lightning: arcs from the nearest foe to the next, damage falling each jump.
const BOLT_MAX = 8;
let boltT = 0, boltFlick = 0;
// Each arc is a run of little cylinders rather than one line, because a line cannot be thick:
// LineBasicMaterial's linewidth is ignored on essentially every desktop GPU, which is why the
// spell read as a hairline no matter what was set. Segments also buy the zigzag for free.
const boltGeo = new THREE.CylinderGeometry(1, 1, 1, 6);
const boltMat = new THREE.MeshBasicMaterial({
  color: 0xdff0ff, transparent: true, opacity: 0, blending: THREE.AdditiveBlending,
  depthWrite: false,
});
const bolts = Array.from({ length: BOLT_MAX }, () => {
  const segs = Array.from({ length: CHAIN.boltSegs }, () => {
    const m = new THREE.Mesh(boltGeo, boltMat);
    m.frustumCulled = false;
    m.visible = false;
    scene.add(m);
    return m;
  });
  return { segs, ax: 0, ay: 0, az: 0, bx: 0, by: 0, bz: 0, live: false };
});

const _bUp = new THREE.Vector3(0, 1, 0);
const _bDir = new THREE.Vector3();
const _bMid = new THREE.Vector3();
const _bQ = new THREE.Quaternion();

/**
 * Lay one arc between two points as a jagged run of cylinders.
 *
 * Re-run every flicker, so the bolt writhes while it is on screen — a static zigzag reads as a
 * drawn shape, and a moving one reads as electricity. Seeded like everything else (D14).
 */
function shapeBolt(b) {
  const dx = b.bx - b.ax, dy = b.by - b.ay, dz = b.bz - b.az;
  const len = Math.hypot(dx, dy, dz) || 1;
  // A pair of axes across the bolt, to push the joints sideways rather than along it.
  const ux = dx / len, uy = dy / len, uz = dz / len;
  let px = -uz, py = 0, pz = ux;
  const pl = Math.hypot(px, py, pz) || 1;
  px /= pl; pz /= pl;
  const qx = uy * pz - uz * py, qy = uz * px - ux * pz, qz = ux * py - uy * px;

  let lx = b.ax, ly = b.ay, lz = b.az;
  for (let i = 0; i < b.segs.length; i++) {
    const t = (i + 1) / b.segs.length;
    // The ends are pinned; the middle wanders most, so it hangs off its targets properly.
    const wob = Math.sin(t * Math.PI) * CHAIN.boltJitter;
    const j1 = (shakeRng() - 0.5) * 2 * wob, j2 = (shakeRng() - 0.5) * 2 * wob;
    const nx = b.ax + dx * t + px * j1 + qx * j2;
    const ny = b.ay + dy * t + py * j1 + qy * j2;
    const nz = b.az + dz * t + pz * j1 + qz * j2;
    const sx = nx - lx, sy = ny - ly, sz = nz - lz;
    const sl = Math.hypot(sx, sy, sz) || 1e-4;
    const m = b.segs[i];
    _bMid.set((lx + nx) / 2, (ly + ny) / 2, (lz + nz) / 2);
    _bDir.set(sx / sl, sy / sl, sz / sl);
    _bQ.setFromUnitVectors(_bUp, _bDir);
    m.position.copy(_bMid);
    m.quaternion.copy(_bQ);
    // Thinner toward the far end, so an arc reads as leaving you rather than just existing.
    m.scale.set(CHAIN.boltWidth * (1.15 - t * 0.5), sl, CHAIN.boltWidth * (1.15 - t * 0.5));
    m.visible = true;
    lx = nx; ly = ny; lz = nz;
  }
}

function chainLightning() {
  const list = [...world.entities.values()].filter((e) => e.kind === "mob");
  let cur = null, best = CHAIN.range;
  for (const e of list) {
    const d = Math.hypot(e.x - player.x, e.z - player.z);
    if (d < best) { best = d; cur = e; }
  }
  if (!cur) return false;   // nothing in range: don't spend the cooldown
  const seen = new Set();
  let dmg = CHAIN.damage, fx = player.x, fy = player.y + 1.2, fz = player.z, bi = 0;
  for (let j = 0; j < CHAIN.jumps && cur; j++) {
    seen.add(cur.id);
    const b = bolts[bi++ % bolts.length];
    b.ax = fx; b.ay = fy; b.az = fz;
    b.bx = cur.x; b.by = cur.y + 0.6; b.bz = cur.z;
    b.live = true;
    shapeBolt(b);
    const res = mobs.hit(cur.id, dmg * player.dmgMult * (1 + (player.dmgSpell || 0)));
    if (res?.killed) { reward(res); grenades.refill(); }
    fx = cur.x; fy = cur.y + 0.6; fz = cur.z;
    dmg *= CHAIN.falloff;
    let next = null, nd = CHAIN.jumpRange;
    for (const e of list) {
      if (seen.has(e.id)) continue;
      const d = Math.hypot(e.x - cur.x, e.z - cur.z);
      if (d < nd) { nd = d; next = e; }
    }
    cur = next;
  }
  for (let k = bi; k < bolts.length; k++) {          // arcs left over from a longer chain
    bolts[k].live = false;
    for (const m of bolts[k].segs) m.visible = false;
  }
  boltT = CHAIN.boltLife;
  boltFlick = 0;
  boltMat.opacity = 1;
  sfx.gunshot();
  markCombat();
  return true;
}

// Sprint: a burst of movement speed (a movement spell; the controller reads player.sprintT).
function sprint() { player.sprintT = SPRINT.dur; sfx.whoosh(); }

// Timewarp: stamp position + HP now; 5s later (or on re-press) SNAP back with cooldowns reset.
const twMarker = (() => {
  const g = new THREE.RingGeometry(0.5, 0.85, 24);
  g.rotateX(-Math.PI / 2);
  const m = new THREE.Mesh(g, new THREE.MeshBasicMaterial({
    color: 0xcf9bff, transparent: true, opacity: 0.7, side: THREE.DoubleSide, depthWrite: false,
  }));
  m.visible = false; scene.add(m); return m;
})();
let twState = null, twCd = 0;

function doRewind() {
  const s = twState;
  player.x = s.x; player.y = s.y + 0.2; player.z = s.z;
  player.vx = player.vy = player.vz = 0;
  player.hp = s.hp;
  player.iframes = Math.max(player.iframes, 0.6);
  for (const st of abilities.state.values()) {
    if (st.def?.id === "timewarp") continue;    // resets everything BUT itself
    st.cd = 0;
    st.ch = st.def?.maxCharges || 1;
  }
  heal.cooldown = 0;
  grenades.cooldown = 0;
  twState = null;
  twMarker.visible = false;
  killFeed = "◷ rewound — cooldowns reset";
  sfx.healDone();
}

function timewarp() {
  if (twState) { doRewind(); return; }          // press again while active → rewind NOW
  if (twCd > 0) return false;
  twState = { x: player.x, y: player.y, z: player.z, hp: player.hp, t: TIMEWARP.window };
  twCd = TIMEWARP.cd;
  twMarker.position.set(player.x, groundY(player.x, player.z) + 0.08, player.z);
  twMarker.visible = true;
  sfx.charge(player.x, player.z, TIMEWARP.window);
  markCombat();
}
const timewarpReady = () => twCd <= 0 || twState !== null;
const timewarpCd = () => Math.max(0, twCd);

function updateSpells(dt) {
  updatePools(dt);
  updateOrb(dt);
  if (twCd > 0) twCd -= dt;
  if (twState) {
    twState.t -= dt;
    twMarker.rotation.y += dt * 2.5;
    if (twState.t <= 0) doRewind();
  }
  if (novaFx > 0) {
    novaFx -= dt;
    const f = 1 - Math.max(0, novaFx) / 0.4;
    novaMesh.scale.setScalar(1 + f * NOVA.radius);
    novaMesh.material.opacity = (1 - f) * 0.8;
    if (novaFx <= 0) novaMesh.visible = false;
  }
  if (boltT > 0) {
    boltT -= dt;
    // One shared material, so the whole chain fades as one thing. Squared, so it holds bright
    // for most of its life and then goes — a linear fade reads as a light being turned down.
    const f = Math.max(0, boltT / CHAIN.boltLife);
    boltMat.opacity = f * f;
    boltFlick -= dt;
    if (boltFlick <= 0) {
      boltFlick = CHAIN.boltFlicker;
      for (const b of bolts) if (b.live) shapeBolt(b);
    }
    if (boltT <= 0) for (const b of bolts) { b.live = false; for (const m of b.segs) m.visible = false; }
  }
}

// Level-up flourish: a WoW-style golden BEAM up through the character with an expanding ring
// at the feet, and the rising jingle. Purely cosmetic, triggered from award() level gains.
const levelBeam = (() => {
  const g = new THREE.CylinderGeometry(1.0, 1.4, 9, 22, 1, true);
  g.translate(0, 4.5, 0);
  const m = new THREE.Mesh(g, new THREE.MeshBasicMaterial({
    color: 0xffe08a, transparent: true, opacity: 0, side: THREE.DoubleSide,
    depthWrite: false, blending: THREE.AdditiveBlending,
  }));
  m.visible = false; scene.add(m); return m;
})();
const levelRing = (() => {
  const g = new THREE.RingGeometry(0.6, 1.0, 36);
  g.rotateX(-Math.PI / 2);
  const m = new THREE.Mesh(g, new THREE.MeshBasicMaterial({
    color: 0xffe8a0, transparent: true, opacity: 0, side: THREE.DoubleSide,
    depthWrite: false, blending: THREE.AdditiveBlending,
  }));
  m.visible = false; scene.add(m); return m;
})();
const levelLight = new THREE.PointLight(0xffe08a, 0, 30);
scene.add(levelLight);
let levelFx = 0;
const LEVEL_FX = 1.2;

const levelBannerEl = document.getElementById("levelbanner");
function levelUp() {
  levelFx = LEVEL_FX;
  levelBeam.visible = true;
  levelRing.visible = true;
  sfx.levelUp();
  // The WORD, big and bright, to go with the golden beam. Retrigger by yanking the class off
  // and forcing a reflow before adding it back — CSS will not replay an animation on an
  // element that already has the class, so a level-up while the last banner is still fading
  // would otherwise show nothing.
  levelBannerEl.textContent = `LEVEL ${player.level} REACHED`;
  levelBannerEl.classList.remove("show");
  void levelBannerEl.offsetWidth;
  levelBannerEl.classList.add("show");
  saveSoon();       // the thing you are least willing to re-earn
}

function updateLevelFx(dt) {
  if (levelFx <= 0) return;
  levelFx -= dt;
  const t = 1 - Math.max(0, levelFx) / LEVEL_FX;     // 0 → 1 over the flourish
  const beamGlow = Math.sin(Math.min(1, t) * Math.PI);  // fade in then out
  levelBeam.position.set(player.x, player.y - 0.5 + t * 1.5, player.z);
  levelBeam.scale.set(1 - t * 0.4, 1, 1 - t * 0.4);
  levelBeam.material.opacity = beamGlow * 0.85;
  levelBeam.rotation.y += dt * 3;
  levelRing.position.set(player.x, player.y + 0.06, player.z);
  levelRing.scale.setScalar(1 + t * 5);
  levelRing.material.opacity = (1 - t) * 0.9;
  levelLight.position.set(player.x, player.y + 1.5, player.z);
  levelLight.intensity = beamGlow * 22;
  if (levelFx <= 0) {
    levelBeam.visible = false;
    levelRing.visible = false;
    levelLight.intensity = 0;
  }
}

// The glow an EPIC drop carries. One light, lent to whichever purple is nearest — see
// updateGearDrops. It is the only light any piece of loot gets, because a light everything
// has is a light that says nothing.
const epicLight = new THREE.PointLight(0x7a1fd0, 0, 26);
scene.add(epicLight);

/**
 * WHAT A BOSS LEAVES BEHIND.
 *
 * Relics are gone. They were designed as "a bundle of shop purchases" back when the shop was
 * where power came from — but the game grew a five-slot loot system with rarity colours, and
 * that is a far better home for a boss prize. A relic was a paragraph you read once; a purple
 * drop is a thing you wear, compare, and remember where you got.
 *
 * Two guarantees make it feel like a boss rather than a big mob: nothing below blue ever
 * falls, and there is a real shot at purple that grows with depth. And sometimes it gives up
 * a SPELL instead — the only reward in the game that changes how you play rather than what
 * your numbers say, which is why it is worth the occasional piece of armour.
 */
function dropBossLoot(x, z, tier) {
  const spell = shakeRng() < DROP.bossSpell ? grantUnownedSpell(tier) : null;
  const pieces = DROP.bossPieces - (spell ? 1 : 0);
  let best = null;
  for (let i = 0; i < pieces; i++) {
    const piece = rollGear(tier, shakeRng, {
      minRarity: DROP.bossMinRarity,
      epicChance: DROP.bossEpic + DROP.bossEpicPerRing * tier,
    });
    if (!best || piece.rarity === "epic") best = piece;
    // Scattered where it fell, so you still have to walk into the arena to collect — a last
    // small decision if anything else is still alive.
    const a = shakeRng() * Math.PI * 2, r = 1.5 + shakeRng() * 2.5;
    placeGearDrop(piece, x + Math.cos(a) * r, z + Math.sin(a) * r);
  }
  killFeed = `◆ BOSS DOWN ◆   ${spell ? `${spell} — a new power` : ""}`
    + `${spell && best ? "  ·  " : ""}${best ? `${best.rarity === "epic" ? "★ EPIC ★ " : ""}${best.name}` : ""}`;
}

/**
 * Hand over an ability the player does not own yet, respecting the same depth gates the shop
 * uses — a ring-1 boss must not skip you past three rings of progression. Returns its name,
 * or null when there is nothing left to give (in which case the caller drops armour instead,
 * so a boss never pays out nothing).
 */
function grantUnownedSpell(tier) {
  const owned = new Set(abilities.owned.map((a) => a.id));
  const pool = (GOODS.adept || []).filter((g) => (g.minTier || 0) <= tier && !owned.has(g.id));
  if (!pool.length) return null;
  const good = pool[Math.floor(shakeRng() * pool.length)];
  if (good.apply(gameCtx) === false) return null;
  player.upgrades[good.id] = (player.upgrades[good.id] || 0) + 1;   // the shop must agree
  sfx.levelUp();
  return good.name;
}

// GEAR DROPS. Everything a fight leaves behind now comes through here — trash drops and boss
// drops alike — a POOL of small coloured cubes on the ground, grey through purple by rarity.
// Walk over one and it goes to your BAG (never auto-worn), so picking a drop up is free but
// wearing it is a choice.
const GEAR_DROP_POOL = 16;
const gearDrops = [];      // { piece, x, y, z, t, mesh }
let gearDropI = 0;
const gearDropMeshes = (() => {
  const geo = new THREE.BoxGeometry(0.55, 0.55, 0.55);
  const arr = [];
  for (let i = 0; i < GEAR_DROP_POOL; i++) {
    const m = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ color: 0xffffff }));
    m.visible = false;
    scene.add(m);
    arr.push(m);
  }
  return arr;
})();

/** Put a specific piece on the ground as a pickup. */
function placeGearDrop(piece, x, z) {
  const mesh = gearDropMeshes[gearDropI = (gearDropI + 1) % gearDropMeshes.length];
  // Recycling a mesh drops whatever old item was still riding it — a fair trade at 16 slots.
  const old = gearDrops.findIndex((d) => d.mesh === mesh);
  if (old >= 0) gearDrops.splice(old, 1);
  mesh.material.color.set(piece.color);
  const y = groundY(x, z) + 0.8;
  mesh.position.set(x, y, z);
  mesh.visible = true;
  gearDrops.push({ piece, x, y, z, t: DROP.life, mesh });
}

const dropGear = (x, z, ring) => placeGearDrop(rollGear(ring, shakeRng), x, z);

/** Drop an OWNED piece out of the bag onto the ground a few steps ahead of you. */
function dropOwnedGear(uid) {
  const i = player.ownedGear.findIndex((g) => g.uid === uid);
  if (i < 0) return false;
  const piece = player.ownedGear[i];
  player.ownedGear.splice(i, 1);
  // A forward vector from the player's facing (same basis controller.js uses), so the item
  // lands in front — far enough not to be re-grabbed the instant you start walking.
  const fx = -Math.sin(player.yaw), fz = -Math.cos(player.yaw);
  placeGearDrop(piece, player.x + fx * 3.5, player.z + fz * 3.5);
  sfx.whoosh();
  return true;
}

function updateGearDrops(dt) {
  // Only an EPIC glows, and only the nearest one carries the light — a light per drop would
  // be a light per grey helmet, which would make the rarest thing in the game look like every
  // other thing in the game. Scarcity is the whole signal; spending it on commons wastes it.
  let lit = null, litD = 1e9;
  for (let i = gearDrops.length - 1; i >= 0; i--) {
    const d = gearDrops[i];
    d.t -= dt;
    // A purple turns faster and rides higher, so it reads as different before you can even
    // make out the colour.
    const epic = d.piece.rarity === "epic";
    d.mesh.rotation.y += dt * (epic ? 3.2 : 1.7);
    d.mesh.position.y = d.y + Math.sin(performance.now() * 0.004 + i) * (epic ? 0.26 : 0.14);
    if (epic) {
      d.mesh.scale.setScalar(1.35 + Math.sin(performance.now() * 0.006) * 0.12);
      const dist = Math.hypot(player.x - d.x, player.z - d.z);
      if (dist < litD) { litD = dist; lit = d; }
    }
    if (Math.hypot(player.x - d.x, player.z - d.z) < DROP.pickupRange) {
      bagGear(d.piece);
      killFeed = `↑ ${d.piece.name}  (${statLine(d.piece.stats)})`;
      sfx.pickup();
      d.mesh.visible = false;
      gearDrops.splice(i, 1);
      continue;
    }
    if (d.t <= 0) { d.mesh.visible = false; gearDrops.splice(i, 1); }
  }
  if (lit) {
    epicLight.color.setHex(lit.piece.glow || 0x7a1fd0);
    epicLight.position.set(lit.x, lit.y + 0.6, lit.z);
    epicLight.intensity = 16 + Math.sin(performance.now() * 0.005) * 5;
  } else {
    epicLight.intensity = 0;
  }
}

const barEl = document.getElementById("bar");
barEl.innerHTML = Array.from({ length: SLOTS }, (_, i) => slotHtml(SLOT_KEYS[i])).join("")
  + `<div class="sep"></div>`
  + GENERAL.map((g) => slotHtml(g.key)).join("");
const allSlots = [...barEl.querySelectorAll(".slot")];
const barSlots = allSlots.slice(0, SLOTS);
const genSlots = allSlots.slice(SLOTS);
const pointsEl = document.getElementById("points");
const inventory = new Inventory(document.getElementById("inv"), abilities, {
  onClose: () => resumeFromShop(),
  gun: () => gun,
  equipWeapon: (id) => gun.carry(id),
  // Gear: the five worn slots, and every piece you own (for the bag).
  gearState: () => ({
    slots: ARMOR_SLOT_ORDER.map((slot) => ({ slot, piece: player.gearSlots[slot] })),
    owned: player.ownedGear,
  }),
  equipGear: (uid) => equipGearByUid(uid),
  dropGear: (uid) => dropOwnedGear(uid),   // right-click in the sheet drops it in front of you
  // The live character-sheet numbers. Damage buckets and Str/Agi are 0 until the gear step
  // wires them, but the sheet reads them now so it's complete the day gear rolls them.
  charStats: () => ({
    level: player.level, hp: player.hp, maxHp: player.maxHp, points: player.points,
    str: player.str || 0, agi: player.agi || 0, stamina: player.stamina || 0,
    armor: player.armor || 0, armorDR: armorDR(player.armor, tierAt(player.x, player.z)),
    dmgGlobal: player.dmgGlobal || 0, dmgGun: player.dmgGun || 0,
    dmgSpell: player.dmgSpell || 0, dmgGrenade: player.dmgGrenade || 0,
    globalPct: (player.dmgGlobal || 0) * 100,
    speedMult: player.speedMult, dashMult: player.dashMult,
  }),
  // START OVER. Wipes the slot and reloads, rather than trying to unwind a live game back to
  // its opening state by hand — there are a dozen places holding a piece of who you are (the
  // bar, your guns, worn gear, bought upgrades, stat multipliers), and a reset that misses one
  // of them leaves a character that is neither old nor new. A reload cannot miss any.
  resetGame: () => {
    resetting = true;      // must come FIRST — the reload below fires the save-on-exit hooks
    wipeSave();
    window.location.reload();
  },
  state: () => ({ level: player.level, points: player.points }),
  addPoints: (n) => { player.points += n; },
  setLevel: (n) => {
    player.level = Math.max(1, n);
    player.xp = 0;
    applyLevelStats();
    player.hp = player.maxHp;
  },
  // Grant abilities free — the point of a test button is to skip the economy, not to
  // simulate it. Tier gates are ignored here on purpose.
  catalog: () => (GOODS.adept || []).map((g) => ({ id: g.id, name: g.name, grants: g.id })),
  give: (id) => {
    const g = (GOODS.adept || []).find((x) => x.id === id);
    g?.apply(gameCtx);
  },
  grantAll: () => {
    for (const g of GOODS.adept || []) g.apply(gameCtx);
  },
  // Spawn a star pack carrying exactly these affixes, next to you, tier gates ignored.
  affixes: () => affixList().map((a) => ({ id: a.id, name: a.name, desc: a.desc || "" })),
  spawnAffix: (id) => { mobs.spawnPackWith([id]); },
  spawnBreed: (kind) => { mobs.spawnBreed(kind); },
  spawnAffixMix: () => {
    const all = affixList().map((a) => a.id);
    mobs.spawnPackWith(all.slice(0, 3));
  },
  // THE AUDIO FADERS. These live here, in the INVENTORY's hooks, because the character sheet
  // is the only thing that reads them — they were previously declared in the object below
  // this one, which nothing consults for audio, so every slider rendered, slid, and did
  // absolutely nothing. A control wired to no one is worse than no control: it teaches the
  // player that the game simply ignores them.
  volume: () => sfx.volume,
  setVolume: (v) => setVolume(v),
  musicVolume: () => music.user,
  setMusicVolume: (v) => setMusicVolume(v),
  voiceVolume: () => sfx.voice,
  setVoiceVolume: (v) => setVoiceVolume(v),
});
const minimap = new Minimap(document.getElementById("minimap"));
const sanctuaries = new Sanctuaries(scene);
const villagers = new Villagers(scene);
const raids = new Raids(mobs, (s) => sackTown(s), (e) => champFalls(e));
const plates = new Nameplates(document.getElementById("plates"), camera);
// The name a raid champion wears on its red plate — the same trade its friendly-town self runs.
const CHAMPION_NAME = { adept: "Adept", herbalist: "Herbalist", qm: "Quartermaster" };
const hpBars = new HealthBars(document.getElementById("hpbars"), camera);
const dmgText = new DamageText(document.getElementById("dmg"), camera);
let tradeMsg = "", tradeMsgT = 0;
// One context object for anything that can grant or change player state, so the shop and
// the admin panel hand out abilities through exactly the same path. Getters are lazy
// because grenades/abilities are constructed further down.
const gameCtx = {
  get grenades() { return grenades; },
  get abilities() { return abilities; },
  get gun() { return gun; },
  fireRing,
  dashStrike,
  whirlwind,
  cataclysmOrb,
  frostNova,
  chainLightning,
  sprint,
  timewarp,
  timewarpReady,
  timewarpCd,
  applyStats: () => applyLevelStats(),   // gear changes re-derive the same way levels do
  // Joining or switching factions redraws the whole map's loyalties: which towns serve you,
  // which ones muster defenders against you. Both caches must let go of the old world.
  onFactionChange: () => {
    villagers.refresh();
    raids.reset();
    paintPlayer();
    const f = myFaction();
    if (f) deeds.push(`the wanderer swore to ${f.name} and wears their colours now`, 2.0);
  },
  equipArmor: (id) => buyArmor(id),      // smith buys a fixed piece by config id
  sellGear: (uid) => sellGear(uid),      // sell one bag piece at a vendor
  sellAllCommon: () => sellAllCommon(),  // "sell all gray" button
  // Faction kit goes to the BAG like any other purchase, so a buy shows up where you expect
  // it and wearing it stays a separate, deliberate act.
  giveFactionGear: (p) => {
    bagGear({
      uid: `fac_${p.id}_${Date.now()}`, slot: p.slot, rarity: "faction",
      color: RARITY.faction.color, glow: RARITY.faction.glow,
      tier: p.repTier, armor: p.armor, stats: { ...p.stats }, name: p.name,
    });
    sfx.equip("rare");
  },
  // Hand a piece to your own quartermaster: it leaves the bag and becomes standing.
  turnIn: (uid) => {
    const i = player.ownedGear.findIndex((g) => g.uid === uid);
    if (i < 0) return 0;
    const piece = player.ownedGear[i];
    const worth = repForTurnIn(piece);
    if (!worth) return 0;
    player.ownedGear.splice(i, 1);
    player.rep = (player.rep || 0) + worth;
    recomputeGear();
    return worth;
  },
  /**
   * Hand in EVERY gray at once — the quartermaster's answer to the smith's "sell all gray".
   * Grays are what a bag fills with, and clicking twenty of them one at a time is the kind
   * of chore that makes a player stop picking things up. Deliberately gray-only, exactly
   * like the sell button: bulk actions must never be able to swallow something you meant
   * to keep, and everything above common is worth a deliberate click.
   */
  turnInAllCommon: () => {
    let total = 0, n = 0;
    for (const p of [...player.ownedGear]) {
      if (p.rarity !== "common") continue;
      const worth = repForTurnIn(p);
      if (!worth) continue;
      const i = player.ownedGear.findIndex((g) => g.uid === p.uid);
      if (i < 0) continue;
      player.ownedGear.splice(i, 1);
      total += worth;
      n++;
    }
    if (n) {
      player.rep = (player.rep || 0) + total;
      recomputeGear();
    }
    return total;
  },
  onClose: () => resumeFromShop(),
};

// GEAR ENGINE. Five slots, one piece each; recomputeGear sums EVERY stat across the worn
// pieces into the player fields, then re-derives. There is no stacking of a slot — a new
// piece replaces the one already there — but a full kit of five sums to something real.
function recomputeGear() {
  const sum = {
    armor: 0, stamina: 0, str: 0, agi: 0,
    dmgGlobal: 0, dmgGun: 0, dmgSpell: 0, dmgGrenade: 0, moveSpeed: 0,
    rHaste: 0, rAtkSpeed: 0, rReload: 0,
  };
  for (const slot of ARMOR_SLOT_ORDER) {
    const p = player.gearSlots[slot];
    if (!p) continue;
    for (const k of Object.keys(p.stats)) sum[k] = (sum[k] || 0) + p.stats[k];
  }
  for (const k of Object.keys(sum)) player[k] = sum[k];
  applyLevelStats();
  saveSoon();       // every equip, sell and purchase lands here eventually
}

/**
 * Equip a piece into its slot. The bag holds only what you AREN'T wearing: the piece leaves
 * the bag, and whatever it replaces returns to the bag — a straight swap, nothing lost.
 */
function equipGear(piece) {
  if (!piece || !ARMOR_SLOT_ORDER.includes(piece.slot)) return;
  const i = player.ownedGear.findIndex((g) => g.uid === piece.uid);
  if (i >= 0) player.ownedGear.splice(i, 1);          // out of the bag
  const prev = player.gearSlots[piece.slot];
  if (prev && prev.uid !== piece.uid) player.ownedGear.push(prev);   // the old one goes back
  player.gearSlots[piece.slot] = piece;
  recomputeGear();
  sfx.equip(piece.rarity);
}
const equipGearByUid = (uid) => equipGear(player.ownedGear.find((g) => g.uid === uid));

/** Sell an owned piece for points. If it was worn, its slot empties and stats re-derive. */
function sellGear(uid) {
  const i = player.ownedGear.findIndex((g) => g.uid === uid);
  if (i < 0) return 0;
  const piece = player.ownedGear[i];
  player.ownedGear.splice(i, 1);
  if (player.gearSlots[piece.slot]?.uid === uid) player.gearSlots[piece.slot] = null;
  const worth = sellValue(piece);
  player.points += worth;
  recomputeGear();
  return worth;
}

/** Dump every grey (common) piece in the bag at once — the one-click declutter. */
function sellAllCommon() {
  let total = 0;
  for (const p of [...player.ownedGear]) {
    if (p.rarity === "common") total += sellGear(p.uid);
  }
  return total;
}
/** A piece goes to the BAG (not auto-worn) — you choose when to equip it. */
const bagGear = (piece) => { if (piece) player.ownedGear.push(piece); };
/** Smith purchase: a FIXED config piece drops into your BAG, same as a find. You then equip
 *  it from the sheet — so a buy shows up in your bags everywhere, not silently worn. */
const buyArmor = (id) => { if (ARMOR[id]) { bagGear(vendorPiece(ARMOR[id])); sfx.pickup(); } };

const shop = new Shop(document.getElementById("shop"), gameCtx);

// The bridge to the Python lab. Optional by construction: if it never connects, nothing
// below notices (STAGES Stage 1). Speech is fire-and-forget — a pending request must never
// hold up a frame, so nothing here is awaited from the loop.
const bridge = new Bridge();
bridge.connect();
let subtitle = "", subtitleT = 0, speaking = false;

// The starter town murmurs (VOICE.md V1). Subtitled per D9 — a line nobody heard is a line
// that didn't ship — with the speaker's trade named, because "who said that" is the first
// thing a voice makes you ask.
const townVoice = new TownVoice(bridge, villagers, sfx, (name, text, dur) => {
  subtitle = `${name} · ${text}`;
  subtitleT = Math.max(3, dur + 0.8);
});

// TALKING BACK (VOICE.md C1): G near a villager. The chat pauses the WORLD but not the
// SOUND — the reply has to be audible while the sim stands still, so setPaused() below
// leaves the audio context running whenever the chat owns the pause.
// The armies' voices (mobs/warcry.js): baked in town, screamed in the field.
const warcries = new WarCries(bridge, sfx);
mobs.onWarcry = (e, kind) => warcries.cry(e, kind);   // returns true if it spoke

/**
 * IS A HOSTILE BODY AT THIS POINT? The contact test for everything that FLIES rather than
 * hitscans — the lobber's shells and thrown grenades both ask it every step.
 *
 * It reuses the very same target spheres the hitscan already trusts (mobs.targets() skips
 * allies and phased bodies; boss.targets() carries the bulk and the weak core), so a
 * grenade and a bullet can never disagree about what is solid. A generous +0.35 pads the
 * sphere, because a thrown explosive that visibly clips a shoulder and sails on is exactly
 * the complaint this was written for.
 */
function bodyAt(x, y, z) {
  for (const t of mobs.targets()) {
    const r = t.r + 0.35;
    const dx = t.x - x, dy = t.y - y, dz = t.z - z;
    if (dx * dx + dy * dy + dz * dz <= r * r) return t;
  }
  for (const t of boss.targets()) {
    const r = t.r + 0.35;
    const dx = t.x - x, dy = t.y - y, dz = t.z - z;
    if (dx * dx + dy * dy + dz * dz <= r * r) return t;
  }
  return null;
}
gun.bodyAt = bodyAt;
grenades.bodyAt = bodyAt;

// The world's clock (world/daynight.js). main drives the lights off daylight() below —
// sim state is not render state, and time is sim state.
const dayNight = new DayNight();
const SKY_DAY = new THREE.Color(0x8fb6d8);
const SKY_NIGHT = new THREE.Color(0x131c33);

const townChat = new TownChat(bridge, villagers, townVoice, sfx, {
  onOpen: () => {
    // The player pressed G: whatever the ambient voice was mid-generating is aborted and
    // its result discarded — she must never mumble her queued line AT you while you wait
    // to talk to her — and the arsenal drops its in-flight bake so the model frees fast.
    voiceQueue.clear("the player opened a chat");
    setPaused(true);
  },
  onClose: () => resumeFromShop(),
  onThinking: (b) => { speaking = b; },
});
const shakeRng = mulberry32(0x51AE);
let bossTimer = 6;

const hurtEl = document.getElementById("hurt");
const subEl = document.getElementById("subtitle");
const energyEl = document.getElementById("energy");
const energyFill = energyEl.querySelector(".en-fill");
let energyStarveT = 0;

/** The bar. Width every frame (it moves constantly); the classes only when they change. */
function drawEnergy() {
  const f = Math.max(0, Math.min(1, player.energy / ENERGY.max));
  energyFill.style.width = `${f * 100}%`;
  energyEl.classList.toggle("full", f > 0.995);
  if (energyStarveT > 0) energyStarveT -= 1;
}

/** A refused cast is the ONE moment this needs to shout — it is the mistake the whole
 *  resource exists to make legible, and it happens while you are looking somewhere else. */
function flashStarved() {
  energyEl.classList.remove("starved");
  void energyEl.offsetWidth;              // restart the animation
  energyEl.classList.add("starved");
}

const jumpsEl = document.getElementById("jumps");
let jumpsLeftShown = -1, jumpsMaxShown = -1;

/** Redrawn only when the count actually changes — this is asked every frame and the answer
 *  is the same on nearly all of them. */
function drawJumps() {
  if (player.jumpsLeft === jumpsLeftShown && player.maxJumps === jumpsMaxShown) return;
  jumpsLeftShown = player.jumpsLeft; jumpsMaxShown = player.maxJumps;
  let html = "";
  for (let i = 0; i < player.maxJumps; i++) html += `<i class="${i < player.jumpsLeft ? "" : "spent"}"></i>`;
  jumpsEl.innerHTML = html;
}

const bossEl = document.getElementById("bossbar");
let bossShown = false, bossEnraged = false;

/**
 * The boss bar. Rebuilt only when the boss appears or its phase turns — the fill width is
 * a style poke every frame, but the markup is not, because writing innerHTML sixty times a
 * second to change one number is how a HUD ends up costing more than the fight.
 */
function drawBossBar() {
  // Only while the fight is actually happening. A boss can be alive two hundred metres away
  // for minutes; a permanent bar for a thing you are not fighting is furniture, and the
  // whole point of taking the top of the screen was that it means something when it appears.
  const b = boss.alive?.engaged > 0 ? boss.alive : null;
  if (!b) {
    if (bossShown) { bossEl.classList.remove("show", "enraged"); bossShown = false; }
    return;
  }
  const enraged = b.phase === 2;
  if (!bossShown || enraged !== bossEnraged) {
    bossEl.innerHTML = `<div class="bb-top"><span>${enraged ? "BOSS HEALTH · ENRAGED" : "BOSS HEALTH"}</span>`
      + `<span class="bb-hp"></span></div>`
      + `<div class="bb-track"><div class="bb-fill"></div></div>`;
    bossEl.classList.add("show");
    bossEl.classList.toggle("enraged", enraged);
    bossShown = true; bossEnraged = enraged;
  }
  const frac = Math.max(0, Math.min(1, b.hp / b.maxHp));
  bossEl.querySelector(".bb-fill").style.width = `${frac * 100}%`;
  bossEl.querySelector(".bb-hp").textContent =
    `${Math.max(0, Math.round(b.hp))} / ${Math.round(b.maxHp)}`;
}
let hurtT = 0, killFeed = "";

// `sustained` marks damage that arrives continuously rather than as a blow — only the beam,
// today. It exists purely so the hurt sound can tell a burn apart from a punch.
function damagePlayer(amount, fromX, fromZ, knock = MOB.knockback, sustained = false) {
  if (player.iframes > 0) return;      // the dodge window actually pays out here
  // A sanctuary is safe — UNLESS it is a RIVAL faction's town. The mobs, the boss and the
  // projectiles each have their own behavioural guards, but those are about looking right;
  // this is the guarantee, and the raid needs the guarantee to have exactly one exception:
  // on hostile ground the town's own garrison can genuinely hurt you. Wild threats still
  // can't follow you in, so the walls still mean something — just not immunity.
  {
    const s = sanctuaryUnder(player.x, player.y, player.z, 0);
    if (s && !isHostileSanctuary(s)) return;
  }
  // Armour applies HERE, at the one place damage enters the player — so it covers mob hits,
  // meteors, the beam, burning ground and your own grenades without any of them knowing it
  // exists. GEAR.md G1: mitigation is the WoW armour curve, and it reads the attacker's tier
  // (proxied by where you are standing, since what hits you is native to your ring) — the
  // same armour is worth less the deeper you go, which is why it can't be grinded shallow.
  // Difficulty rides in HERE, at the same one choke point armour uses, so Easy softens mob
  // hits, meteors, the beam, burning ground and your own grenades all at once — none of them
  // needing to know a difficulty setting exists.
  player.hp -= amount * diff().incoming * (1 - armorDR(player.armor, tierAt(player.x, player.z)))
    * (1 - (player.graceMitigation || 0));       // early-game grace: fades out by ~level 8
  hurtT = 0.35;
  // Severity is the fraction of your MAX health this took, so the sound scales with what it
  // cost you rather than with a raw number that means nothing at level 30.
  sfx.playerHurt(fromX, fromZ, amount * diff().incoming / Math.max(1, player.maxHp), sustained);
  markCombat();
  if (HEAL.breakOnDamage) heal.interrupt("hit");
  // Knockback, so a hit moves you and reads as physical rather than as a number ticking.
  const dx = player.x - fromX, dz = player.z - fromZ;
  const d = Math.hypot(dx, dz) || 1;
  player.vx += (dx / d) * knock;
  player.vz += (dz / d) * knock;
  if (player.hp <= 0 && !dead) onDeath();
}

const hurtPlayer = (mob) => damagePlayer(mob.damage, mob.x, mob.z);

function reward(res) {
  player.points += Math.round((LOOT.base + LOOT.perTier * res.ring)
    * (res.elite ? LOOT.eliteMult : 1));
  // HEIGHT PAYS. Applied at the call site rather than inside award() so the number the kill
  // feed shows you is the number you actually got — a bonus you cannot see is not a reward,
  // it is an accounting detail.
  const xp = Math.round(killValue(res.ring, res.elite, player.level) * altitudeBonus());
  const lv = award(xp);
  // Ordinary kills pay NO reputation — standing comes from turn-ins, bosses and quests, not
  // from the endless frontier, so it stays something you choose rather than something you
  // accumulate by walking through camps.
  // Naming what you killed is half of learning to read them.
  const what = res.affixes ? `★ ${res.affixes}` : res.elite ? "★ elite" : "kill";
  killFeed = `${what}  +${xp}xp${lv ? `   ▲ LEVEL ${player.level}` : ""}`;
  if (lv) levelUp();

  // Gear drops: frequent, and a lot more from elites. A piece lands a couple of steps away
  // so you walk over it. rollGear scales the numbers and rolls the rarity by ring.
  if (shakeRng() < (res.elite ? 0.4 : 0.12)) {
    const a = shakeRng() * Math.PI * 2, r = 2 + shakeRng() * 2.5;
    dropGear(player.x + Math.cos(a) * r, player.z + Math.sin(a) * r, res.ring);
  }
}

function rewardBoss(ring, x, z) {
  player.points += Math.round((LOOT.base + LOOT.perTier * ring) * LOOT.bossMult);
  const alt = altitudeBonus();
  const xp = Math.round(bossValue(ring, player.level) * alt);
  const lv = award(xp);
  // A boss is the big lump of standing. This is where reputation actually comes from, along
  // with turn-ins and (later) quests — never from the trash you clear on the way to it.
  const rep = gainRep(Math.round(repForBoss(ring) * alt));
  killFeed = `◆ BOSS DOWN ◆  +${xp}xp${rep ? `  +${rep} standing` : ""}${lv ? `   ▲ LEVEL ${player.level}` : ""}`;
  if (lv) levelUp();
  // News travels with the traveller (world/events.js): told the way a townsperson would.
  deeds.push(`the wanderer felled a great beast out in ${RINGS[Math.min(ring, RINGS.length - 1)].name}`, 2.2);
  // The relic falls where the boss did — you have to walk into the arena to take it, which
  // is a last small decision if anything else is still alive.
  if (x !== undefined) dropBossLoot(x, z, ring);
}

/**
 * THE SACK. The last defender of a rival town has fallen. Pays like a boss: raiding and
 * boss-hunting are two equal roads up the reputation ladder, on purpose — one is found by
 * pushing out, the other by reading the map. The loot FOUNTAIN scatters field-table rolls
 * (mostly grays — the spectacle is the point) across the whole town, so victory looks like
 * victory and the streets are worth walking even after the fight. Reagents will take over
 * gray slots in this same fountain later; the roll is table-driven for exactly that reason.
 */
function sackTown(s) {
  const ring = tierAt(s.x, s.z);
  const alt = altitudeBonus();
  const rep = gainRep(Math.round(repForBoss(ring) * alt));
  const xp = Math.round(bossValue(ring, player.level) * alt);
  const lv = award(xp);
  player.points += Math.round((LOOT.base + LOOT.perTier * ring) * LOOT.bossMult);
  killFeed = `⚑ TOWN SACKED ⚑  +${xp}xp${rep ? `  +${rep} standing` : ""}${lv ? `   ▲ LEVEL ${player.level}` : ""}`;
  if (lv) levelUp();
  {
    const f = factionOfTown(s);
    deeds.push(`the wanderer sacked ${f ? `a ${f} camp` : "a camp"} out in `
      + `${RINGS[Math.min(ringAt(s.x, s.z), RINGS.length - 1)].name}`, 2.0);
  }
  const innerR = Math.max(6, (s.rMin || 20) - 6);
  for (let i = 0; i < RAID.loot; i++) {
    const a = shakeRng() * Math.PI * 2;
    const r = 3 + shakeRng() * innerR;
    dropGear(s.x + Math.cos(a) * r, s.z + Math.sin(a) * r, ring);
  }
  sfx.levelUp();
}

/**
 * A raid champion fell — the mini-boss payout, ON the kill, WHERE it died. Each pays a
 * fraction of a true boss (RAID.champRep, laddered so the QM — the wall — is the prize),
 * bursts a pile of gear at its feet, and its death is durable (raid.js `fallen`): the same
 * champion cannot be farmed by walking out of range and back. Fires exactly once per head
 * per rebuild — raid.js guarantees it — so everything here can pay full price without
 * checking anything.
 */
function champFalls(e) {
  const ring = tierAt(e.x, e.z);
  // Two fractions on purpose: standing is deliberately thin (champRep — the ladder must run
  // through real bosses), while xp and points still pay like the mini-boss the fight is.
  const repFrac = RAID.champRep[e.champion] ?? 0.0625;
  const xpFrac = RAID.champXp[e.champion] ?? 0.25;
  const alt = altitudeBonus();
  const rep = gainRep(Math.round(repForBoss(ring) * repFrac * alt));
  const xp = Math.round(bossValue(ring, player.level) * xpFrac * alt);
  const lv = award(xp);
  player.points += Math.round((LOOT.base + LOOT.perTier * ring) * LOOT.bossMult * xpFrac);
  const name = (CHAMPION_NAME[e.champion] || "Champion").toUpperCase();
  killFeed = `☠ ${name} SLAIN  +${xp}xp${rep ? `  +${rep} standing` : ""}${lv ? `   ▲ LEVEL ${player.level}` : ""}`;
  deeds.push(`the wanderer cut down a camp ${(CHAMPION_NAME[e.champion] || "champion").toLowerCase()} `
    + `out in ${RINGS[Math.min(ring, RINGS.length - 1)].name}`, 1.6);
  if (lv) levelUp();
  const n = e.champion === "qm" ? RAID.champLootQm : RAID.champLoot;
  for (let i = 0; i < n; i++) {
    const a = shakeRng() * Math.PI * 2;
    const r = 1.5 + shakeRng() * 5;
    dropGear(e.x + Math.cos(a) * r, e.z + Math.sin(a) * r, ring);
  }
  sfx.equip("rare");
}

/**
 * A grenade went off. THIS is where an explosion learns what exists in the world —
 * grenade.js only knows a position and a radius, so bosses, mobs and you all take the same
 * blast without it importing any of them. Damage falls off with distance from the centre.
 */
/**
 * @param {boolean} flat - full damage right out to the rim instead of tapering. A spin you
 *   are standing inside should hurt the same wherever something is in it; taper made the
 *   drawn ring and the felt ring disagree, which reads as the hitbox being too small.
 */
function blast(x, y, z, radius = GRENADE.radius, damage = GRENADE.damage,
               knock = GRENADE.knockback, hurtsYou = true, flat = false, shove = false,
               kind = "grenade") {
  const falloff = (d) => (flat ? 1 : Math.max(0.25, 1 - d / radius));
  // The damage BUCKET for this source (grenade blasts vs spell/ability blasts). It scales the
  // ENEMY damage only — your own self-damage below stays on the base so it can't grow with
  // your gear and blow you up.
  const bucket = 1 + (kind === "spell" ? (player.dmgSpell || 0)
    : kind === "gun" ? (player.dmgGun || 0) : (player.dmgGrenade || 0));

  for (const e of [...world.entities.values()]) {
    if (e.kind !== "mob") continue;
    // The vertical axis is STRETCHED, not squashed — see BLAST_VSCALE. Scaling it by 0.5
    // doubled the vertical reach, so every ground effect was a column reaching far further up
    // and down than it ever did outward.
    const d = Math.hypot(e.x - x, e.z - z, (e.y - y) * BLAST_VSCALE);
    if (d > radius) continue;
    const res = mobs.hit(e.id, damage * player.dmgMult * bucket * falloff(d));
    if (res?.killed) { reward(res); grenades.refill(); }
    else if (shove) mobs.push(e, x, z, FIRERING.shove);   // survivors get thrown clear
  }

  if (boss.active) {
    const b = boss.alive;
    const bx = b.x, bz = b.z;
    const d = Math.hypot(b.x - x, b.z - z);
    if (d < radius + BOSS.contactRange * 0.5) {
      const res = boss.hit("boss", damage * player.dmgMult * bucket * falloff(Math.max(0, d - BOSS.contactRange * 0.5)));
      if (res?.killed) { rewardBoss(res.ring, bx, bz); grenades.refill(GRENADE.max); }
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

// Relative, not "/audio/..." — see the note in audio/music.js: a leading slash breaks
// anywhere the game is served from a subfolder rather than a domain root.
const deathSound = new Audio("audio/popsound.mp3");
const deathSubEl = document.getElementById("death-sub");

// Death is now a SCREEN, not an instant teleport: the pop sound plays, the music stops, and
// the game holds on a "Respawn" button until you press it. D9's level loss lands here, so the
// screen can tell you about it.
function onDeath() {
  if (dead) return;
  dead = true;
  deeds.push(`the wanderer fell out in ${RINGS[Math.min(ringAt(player.x, player.z), RINGS.length - 1)].name} `
    + `and came back walking`, 1.8);
  const lost = loseLevel();
  // COMMIT IT, this instant. Every other save can wait; this one cannot. The whole weight of
  // dying rests on the level being genuinely gone, and a player who works out that closing the
  // tab on the death screen undoes it has been handed a way to opt out of the only real stake
  // in the game — and will use it, because everyone does.
  saveNow();
  document.body.classList.add("dead");
  music.pause();
  deathSound.currentTime = 0;
  deathSound.play().catch(() => {});
  if (document.pointerLockElement) document.exitPointerLock();
  deathSubEl.textContent = lost
    ? `You slipped to level ${player.level}. Respawn at the nearest safe town.`
    : "Respawn at the nearest safe town.";
}

function doRespawn() {
  // You wake in the great city of the ring you fell in — but only as deep as your LEVEL
  // entitles you to, so dying deep while under-levelled isn't a free teleport past everything.
  const diedIn = tierAt(player.x, player.z);
  const allowed = respawnTierFor(player.level);
  const wokeIn = Math.min(diedIn, allowed);
  const home = homeOfTier(wokeIn);
  if (home) {
    player.x = home.x;
    player.z = home.z;
    player.y = groundY(home.x, home.z) + 0.5;
    player.vx = player.vy = player.vz = 0;
    player.dodgeT = player.dashT = player.surgeT = 0;
  } else {
    spawnPlayer();
  }
  player.hp = player.maxHp;
  player.iframes = 1.5;                 // grace on arrival, so you can't be spawn-camped
  killFeed = `woke in ${home?.city ? "the city" : "town"}`
    + (wokeIn < diedIn ? `, carried back to ${RINGS[Math.min(wokeIn, RINGS.length - 1)].name}` : "");
  dead = false;
  document.body.classList.remove("dead");
  music.resume();
  resumeFromShop();                     // resume the world and chase the pointer lock back
}
document.getElementById("respawn-btn").addEventListener("click", doRespawn);

// Start INSIDE the spawn town, not on the bare plain outside it — the first thing you see is
// the place you'll come back to, and you're safe while you find your feet.
function spawnInTown() {
  const home = homeOfTier(0);
  if (!home) { spawnPlayer(); return; }
  player.x = home.x;
  player.z = home.z;
  player.y = groundY(home.x, home.z) + 0.5;
  player.vx = player.vy = player.vz = 0;
}
spawnInTown();

// --- PERSISTENCE ---------------------------------------------------------------------
// One slot, written quietly, never rewindable. See prog/save.js for why that is a design
// decision rather than a shortcut: a game whose death penalty is a whole level only keeps
// that stake if closing the tab cannot undo it.
const saveCtx = {
  get abilities() { return abilities; },
  get gun() { return gun; },
  get game() { return gameCtx; },
  get townVoice() { return townVoice; },
  get townChat() { return townChat; },
  get dayNight() { return dayNight; },
  get raids() { return raids; },
  slots: SLOTS,
  recomputeGear,
};
// Once a wipe is underway, NOTHING may write again. Erasing the slot reloads the page, and a
// reload fires the very "save before you go" handler below — which cheerfully wrote the whole
// character back over the wipe a few milliseconds after it happened, so Start Over erased
// nothing at all. Any code that can save must first ask whether saving is still allowed.
let resetting = false;
// A debounced write, for the things that happen in clusters — walking over three drops in a
// second should cost one save, not three. Anything that must not be lost calls saveNow.
let saveT = 0;
const persist = () => { if (!resetting) saveGame(saveCtx); };
const saveSoon = () => { saveT = 1.5; };
const saveNow = () => { saveT = 0; persist(); };

// A brand-new game needs a difficulty chosen before the first hit lands; a returning one
// already carries the choice in its save and must never be asked again.
let newGame = true;
if (hasSave()) {
  const data = loadSave();
  try {
    restoreSave(data, saveCtx);   // this also restores the saved difficulty
    paintPlayer();                // load your colours back on with everything else
    killFeed = "welcome back";
    newGame = false;
  } catch (err) {
    // A save that will not load must never be a wall. Better a fresh character than a game
    // that cannot be started at all — one costs a session, the other costs the player.
    console.warn("[save] could not restore, starting fresh:", err);
    wipeSave();
    spawnInTown();
  }
}

// THE DIFFICULTY PICKER. Held in front of a fresh start until a card is chosen — nothing
// begins, no first click starts play, until you have picked. A returning player skips it
// entirely (their save decided), and Start Over wipes the save and reloads, so a new run
// lands here again and can pick afresh.
const diffEl = document.getElementById("difficulty");
let choosing = false;
function showDifficultyPicker() {
  choosing = true;
  clickEl.style.display = "none";
  diffEl.style.display = "grid";
  let selected = null;

  diffEl.innerHTML = `
    <h1>WAR NACHO</h1>
    <div class="sub">Choose how hard the frontier bites. This is set for the whole run.</div>
    <div class="modes">
      ${Object.values(DIFFICULTY).map((d) => `
        <button class="mode ${d.id}" data-diff="${d.id}">
          <span class="nm">${d.label}</span>
          <span class="bl">${d.blurb}</span>
        </button>`).join("")}
    </div>
    <button class="startbtn hidden" data-start>▶  CLICK TO START  ◀</button>
    <div class="hint">You can start a fresh run and pick again from the character sheet.</div>`;

  const modes = diffEl.querySelector(".modes");
  const startBtn = diffEl.querySelector("[data-start]");

  // FIRST click a card: it lights up green and the choice is locked in — but the game does
  // NOT begin yet, so you can change your mind, and so starting is always a deliberate second
  // click rather than something that fires the instant you touch a card.
  diffEl.querySelectorAll("[data-diff]").forEach((b) => {
    b.addEventListener("click", () => {
      selected = b.dataset.diff;
      setDifficulty(selected);
      applyLevelStats();          // the choice is live from the moment it is made
      diffEl.querySelectorAll(".mode").forEach((m) => m.classList.toggle("sel", m === b));
      modes.classList.add("chosen");
      startBtn.classList.remove("hidden");
    });
  });

  // THEN click START. This is the user gesture that both begins the game and — because it is
  // a real click — is allowed to grab the mouse. Doing it here rather than waiting for a
  // separate world-click means one clear "start" button, exactly what was asked for.
  startBtn.addEventListener("click", () => {
    if (!selected) return;
    choosing = false;
    diffEl.style.display = "none";
    clickEl.style.display = "";
    saveNow();                    // remember the choice from the very first frame
    music.start();
    sfx.unlock();
    if (paused) { lockTries = 0; setPaused(false); }
    renderer.domElement.requestPointerLock?.();   // this click is a fresh user gesture
  });
}
// The browser can close without warning. This is the last chance to commit, and it has to be
// cheap and synchronous — 'hidden' fires on tab-switch and phone-lock too, which are exactly
// the moments a session quietly ends for good.
addEventListener("pagehide", () => persist());
document.addEventListener("visibilitychange", () => { if (document.hidden) persist(); });

attachInput(renderer.domElement, {
  toggleCamera: () => rig.toggle(),
  toggleMusic: () => music.toggle(),
  reload: () => gun.reload(),
  cycleWeapon: (dir) => gun.cycle(dir),
  interact: () => {
    const v = villagers.nearest();
    if (!v) return;
    shop.show(v);
    // Pause the world ON PURPOSE, not as a side effect of losing the mouse. Relying on the
    // unlock event left a gap where the panel was open while the game still ran behind it —
    // and if the unlock happened to land inside the post-resume grace window, that gap
    // lasted the whole visit: WASD quietly walked you away from the person you were
    // talking to.
    setPaused(true);
  },
  ability: (i) => {
    if (inSafe) { tradeMsg = "weapons stowed inside the walls"; tradeMsgT = 2; return; }
    const msg = abilities.use(i);
    if (msg.includes("not enough energy")) flashStarved();
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
    // A fraction of max HP that steps up every 10 levels — see VILLAGE.potionFrac*.
    const frac = VILLAGE.potionFracBase + Math.floor(player.level / 10) * VILLAGE.potionFracPer10;
    const heal = Math.round(player.maxHp * frac);
    player.hp = Math.min(player.maxHp, player.hp + heal);
    tradeMsg = `potion  +${heal}`;
    tradeMsgT = 2;
    sfx.healDone();
  },
  // G: talk to the nearest villager (town/chat.js). Replaces the old dev speak-test —
  // the chat IS that test grown up: typed line in, spoken line out, in a real character.
  chat: () => townChat.tryOpen(),
  sleep: () => trySleep(),
  // Clicking the world starts the game, lock or no lock. tryLock() keeps chasing the mouse
  // capture separately; not getting it costs you comfortable looking, not the ability to play.
  startPlaying: () => {
    // Return false to REFUSE — the click handler then also skips grabbing the mouse, so the
    // lock cannot unpause us behind a picker or a panel.
    if (dead || shop.open || inventory.open || choosing) return false;   // pick a difficulty first
    // Clicking the world with a chat open means "done talking" — close it; its onClose
    // runs the resume, so falling through here would double-handle one click.
    if (townChat.open) { townChat.close(); return false; }
    music.start();
    sfx.unlock();
    if (paused) { lockTries = 0; setPaused(false); }
    return true;
  },
  // Escape as a KEY. Only fires when no panel claimed it first (they take it in capture).
  // If the mouse is captured, stay out of the way — the browser is about to release it and
  // the unlock path below will pause; acting here too would double-handle one press. If it
  // is NOT captured, this is the only pause there is.
  escapeKey: () => {
    if (dead || shop.open || inventory.open || paused || choosing) return;
    if (document.pointerLockElement) return;
    setPaused(true);
  },
  onLock: () => { music.start(); sfx.unlock(); setPaused(false); },
  onUnlock: () => {
    if (dead) return;                   // death owns the pause; the button resumes
    // Ignore an unlock landing in the instant after a deliberate resume — the browser race
    // this guards against resolves within the same keypress, tens of milliseconds. It was
    // 900ms, which swallowed the player's own DELIBERATE Escape for most of a second after
    // leaving a vendor: the pause ate the press, the mouse was gone, and the key went dead
    // until they clicked. Short window, and a swallowed release now re-chases the capture
    // so the game never idles unlocked with nothing pending.
    if (performance.now() - resumedAt < 300) { setTimeout(tryLock, 400); return; }
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
  minimap.resize();      // the map is sized from the window, so it has to follow it
});

const sleepEl = document.getElementById("sleep");
let sleeping = false;
/**
 * SLEEP (Z, inside a safe town). The fade is not decoration — the dark is when the town
 * DREAMS: consolidate() digests the day's talk into standing lore, with the model if one
 * is up and mechanically if not, deadline-capped so the town always wakes. Then dawn, a
 * full heal (a bed is the one rest this game gives), and the save — a night is a chapter.
 */
function trySleep() {
  if (sleeping || dead || paused || choosing) return;
  if (!inSafe) { tradeMsg = "sleep needs a safe town's walls"; tradeMsgT = 2; return; }
  sleeping = true;
  sleepEl.classList.add("show");
  setTimeout(async () => {
    try { await townVoice.consolidate(bridge); } catch { /* the town wakes regardless */ }
    dayNight.skipToDawn();
    player.hp = player.maxHp;
    saveNow();
    sleepEl.classList.remove("show");
    sleeping = false;
  }, 1000);
}

const clickEl = document.getElementById("click");
let paused = true, everPlayed = false, inSafe = false, dead = false;
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
  // Denied. Usually the post-Escape cooldown; in Firefox it also happens on a perfectly
  // ordinary first click, because it gates pointer lock far more tightly than Chrome does.
  //
  // This used to bail out when `paused` — which was exactly the state of the FIRST click, so
  // the one moment it most needed to retry was the one moment it refused to. Keep asking
  // either way; the game is already running by now, so a failure here costs mouse capture,
  // not the session.
  if (lockTries++ > 4) return;
  setTimeout(tryLock, 400 + lockTries * 400);
});

function setPaused(p) {
  paused = p;
  document.body.classList.toggle("running", !p);
  // Pausing IS opening the inventory — the paused moment is exactly when you want to
  // rearrange your kit, and it saves inventing another key for it.
  if (p && everPlayed && !shop.open && !townChat.open) inventory.show();
  else inventory.hide();
  // Shopping — and talking to a villager — pauses the WORLD but not the soundtrack: you
  // are standing in a town talking to someone, and the music cutting out is the tell that
  // you've left the game. The chat also keeps SFX running, because the villager's spoken
  // reply has to be audible while the sim stands still. A real pause silences everything.
  music.setPaused(p && !shop.open && !townChat.open);
  sfx.setPaused(p && !townChat.open);
  if (!p) { everPlayed = true; return; }
  if (everPlayed && !townChat.open) clickEl.innerHTML = "PAUSED &nbsp;·&nbsp; click to resume";
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
  if (inSafe) return "✦ SANCTUARY";
  // WHICH WAY UP. Distance alone sent you to the right patch of map to find nothing there,
  // because the town was overhead and fog closes long before it.
  const climb = Math.round((best.plateau + 1) - player.y);
  const updown = Math.abs(climb) > 8 ? `  ${climb > 0 ? "▲" : "▼"}${Math.abs(climb)}m` : "  · level ·";
  // Whose gate it is, not just how far. The map carries this as colour (ui/minimap townFlag);
  // saying it in words too is what makes the colour learnable in the first place.
  const whose = best.city || best.neutral ? "neutral"
    : isHostileSanctuary(best) ? "RIVAL"
    : servesYou(best) ? "yours"
    : factionOfTown(best) || "neutral";
  return `town gate ${Math.round(bd)}m${updown} (${whose})`;
}

// The one question hours of "still broken" reports finally came down to: WHICH BUILD IS ON
// SCREEN. Stamped once at boot; if the corner doesn't say config.js's current BUILD_TAG,
// the copy being played predates the fix being tested.
document.getElementById("buildtag").textContent = BUILD_TAG;
console.info(`[build] ${BUILD_TAG}`);

const hud = document.getElementById("stats");
const healthEl = document.getElementById("health");
const ammoEl = document.getElementById("ammo");
const xpEl = document.getElementById("xp");
const repEl = document.getElementById("rep");
// The rep bar's gain-flash: brightened while this runs down, so every point of standing —
// a turn-in, a boss — announces itself on the bar the moment it lands.
let lastRep = -1, repFlashT = 0;
const alertEl = document.getElementById("alert");
const sleepHintEl = document.getElementById("sleephint");
let acc = 0, last = performance.now(), fps = 60;
// Latch for the overlay wipe above: cleared once when the world stops, armed again the
// moment it resumes.
let overlaysCleared = false;
const AUTOSAVE_EVERY = 25;      // seconds; the backstop under the event-driven saves
let autosaveT = AUTOSAVE_EVERY;

function frame(now) {
  requestAnimationFrame(frame);
  const dt = Math.min((now - last) / 1000, MAX_CATCHUP);
  last = now;    // updated even while paused, so resuming never simulates the gap

  if (paused || dead) {
    // A STOPPED WORLD SHOWS NO LIVE OVERLAYS. Everything below this line — damage numbers,
    // health bars, nameplates — is drawn and tidied by the loop we are about to skip, so
    // anything alive at this instant would freeze on screen with nothing left running to
    // clear it. The reported symptom was a bright amber crit stranded mid-air until the
    // page was refreshed. Cleared ONCE on entering the state, not every frame, so pausing
    // never thrashes the DOM.
    if (!overlaysCleared) {
      overlaysCleared = true;
      dmgText.clear();
      hpBars.clear();
      plates.clear();
      alertEl.classList.remove("show");
      sleepHintEl.classList.remove("show");
    }
    renderer.render(scene, camera);
    return;
  }
  overlaysCleared = false;

  fps += (1 / Math.max(dt, 1e-4) - fps) * 0.05;

  acc += dt;
  while (acc >= FIXED_DT) {
    stepPlayer(FIXED_DT);
    acc -= FIXED_DT;
  }

  streamer.update(player.x, player.z, player.y);
  sanctuaries.update(dt, player.x, player.z);
  // The camera must settle BEFORE the gun reads it — firing off last frame's camera is a
  // subtle, maddening "my shots trail my aim" bug when you're turning fast.
  // The cleaver never pulls to first person: RMB is its SPIN, and there is nothing for ADS
  // to buy on a weapon with no spread. The other two aim exactly like guns.
  rig.update(dt, input.aim && gun.weapon.mode !== "melee");

  // Weapons stow inside the walls. Gated HERE rather than inside gun.js, for the same
  // reason the damage rule lives in damagePlayer: systems don't learn each other's names,
  // and "what does a sanctuary mean" belongs in one place. A RIVAL's town is not safe:
  // weapons stay out, the fast mend stays off, and the ✦ SANCTUARY label stays away —
  // everything that reads inSafe learns "this is intruder ground" from this one line.
  {
    const s = sanctuaryUnder(player.x, player.y, player.z, 0);
    inSafe = s !== null && !isHostileSanctuary(s);
  }
  const inSafeZone = inSafe;

  // RMB on the cleaver is the spin, edge-triggered like every other press-to-act input —
  // holding the button must not queue a second spin the instant the first cooldown ends.
  {
    const rmbPressed = input.aimHeld && !prevRmb;
    prevRmb = input.aimHeld;
    if (rmbPressed && gun.weapon.mode === "melee") {
      if (inSafeZone) { tradeMsg = "weapons stowed inside the walls"; tradeMsgT = 2; }
      else if (gun.lockedFor(player.faction)) { tradeMsg = `swear to ${gun.weapon.faction} to wield this`; tradeMsgT = 2; }
      else trySpin();
    }
  }

  /** One damage number for anything the player's weapon touched, through the GUN bucket. */
  const applyWeaponHit = (t, dmg, knock = 0) => {
    if (t.tag === "boss" || t.tag === "bossWeak") {
      const bx = boss.alive?.x, bz = boss.alive?.z;
      const res = boss.hit(t.tag, dmg);
      if (res?.killed) { rewardBoss(res.ring, bx, bz); grenades.refill(GRENADE.max); }
      else if (res?.weak) killFeed = "core hit ×2.5";
      return;
    }
    const res = mobs.hit(t.id, dmg);
    if (res?.killed) { reward(res); grenades.refill(); }
    else if (knock > 0) {
      // Survivors of a swing get thrown — the shove is half of what a cleaver IS.
      const e = world.entities.get(t.id);
      if (e) mobs.push(e, player.x, player.z, knock);
    }
  };

  {
    // tryFire is called every frame with whether the trigger is HELD, so the gun itself can
    // enforce semi-auto (release between shots) for the shotgun and sniper. A safe zone reads
    // as trigger-up. One shot can strike several targets now (shotgun pellets), so damage is
    // applied per struck target, each pellet dealing the weapon's damage through dmgMult.
    const shot = gun.tryFire(rig.blend > 0.5, gunRng,
      [...mobs.targets(), ...boss.targets()],
      input.firing && !inSafeZone && !gun.lockedFor(player.faction), dt);

    if (shot?.beam) {
      // THE BEAM does not deal its damage here. It burns for tiny amounts sixty times a
      // second, and pushing each sliver through the normal hit path would fire the confirm
      // sound and a floating number PER FRAME per target — a scream and a blizzard. So it
      // pours into an accumulator that is emptied a few times a second: same damage, one
      // legible number, one tick of feedback.
      markCombat();
      if (!lanceVoice) lanceVoice = sfx.lanceHum();
      for (const t of shot.targets) {
        const k = t.tag || t.id;
        const acc = beamAcc.get(k) || { t, dmg: 0 };
        acc.dmg += shot.damage;
        beamAcc.set(k, acc);
      }
    } else {
      if (lanceVoice) { lanceVoice.stop(); lanceVoice = null; }
      if (shot?.fired) {
        markCombat();
        for (const t of shot.targets) {
          const dmg = shot.damage * player.dmgMult * (1 + (player.dmgGun || 0));
          applyWeaponHit(t, dmg, shot.melee ? shot.knock : 0);
        }
      }
    }
    // The redline is a moment, not a state — it gets one clunk, on the transition.
    if (gun.overheated > 0 && !wasOverheated) sfx.overheat();
    wasOverheated = gun.overheated > 0;
  }

  // Empty the beam's accumulator on a slow clock: damage arrives in readable bites.
  beamFlushT -= dt;
  if (beamFlushT <= 0 && beamAcc.size) {
    beamFlushT = 0.18;
    for (const { t, dmg } of beamAcc.values()) {
      applyWeaponHit(t, dmg * player.dmgMult * (1 + (player.dmgGun || 0)));
    }
    beamAcc.clear();
  }

  // The lobber's shells in flight. Bursts route through the same blast() as everything else
  // — main decides what an explosion touches — but through the GUN damage bucket, and they
  // never hurt the one who fired them (WEAPONS.md: the cost is leading the shot, not fear).
  gun.updateShells(dt, (sx, sy, sz) => {
    blast(sx, sy, sz, WEAPONS.lobber.blastRadius, WEAPONS.lobber.blastDamage,
          8, false, false, false, "gun");
    sfx.explosion(sx, sz, 0.9);
    markCombat();
  });
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
  // Leap -> slam. Gated on a PENDING FLAG, not on leapT still being positive: leapT is
  // decremented inside the fixed-step physics loop, so by the time this frame-level check
  // ran it had already crossed zero — and since the arc lasts longer than leapT, the player
  // was still airborne. The slam never fired at all, which is why the spin did no damage:
  // it never started.
  if (player.leapPending && (player.onGround || player.leapT <= 0)) whirlSlam();

  // ENERGY. Always climbing, so you are never standing about waiting for a bar — the cost of a
  // misjudgement is the cast you could not make, not a minute of idling.
  player.energy = Math.min(ENERGY.max, player.energy + ENERGY.regen * dt);

  if (player.whirlT > 0) {
    player.whirlT -= dt;
    player.iframes = Math.max(player.iframes, 0.2);   // untouchable for the whole spin
    whirlTick -= dt;
    if (whirlTick <= 0) {
      whirlTick = WHIRL.spinTick;
      // Flat damage to the rim, so what you see is what it hits.
      blast(player.x, player.y + 1, player.z, WHIRL.spinRadius, WHIRL.spinDamage, 5, false, true, false, "spell");
    }
    spinRing.visible = true;
    spinRing.position.set(player.x, player.y + 0.35, player.z);
    spinRing.rotation.y += dt * 26;
    spinRing.material.opacity = 0.35 + 0.25 * Math.sin(performance.now() * 0.03);
  } else if (spinRing.visible) {
    spinRing.visible = false;
  }

  if (slamFx > 0) {
    slamFx -= dt;
    const f = 1 - Math.max(0, slamFx) / 0.45;
    whirlRing.scale.setScalar(1 + f * WHIRL.slamRadius);
    whirlRing.material.opacity = (1 - f) * 0.85;
    if (slamFx <= 0) whirlRing.visible = false;
  }

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
  const paint = (el, def, left, ready, charges = undefined) => {
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
    const n = charges === undefined ? (def?.charges ? def.charges() : null) : charges;
    el.querySelector(".ch").textContent = n === null || n === undefined ? "" : "●".repeat(n);
    el.title = def?.desc || "empty";
    el.querySelector(".cool").textContent = left > 0 ? left.toFixed(left < 3 ? 1 : 0) : "";
  };
  barSlots.forEach((el, i) => {
    const a = abilities.slots[i];
    el.querySelector(".k").textContent = SLOT_KEYS[i];
    paint(el, a, abilities.cooldownOf(i), abilities.readyOf(i), abilities.chargesOf(i));
  });
  genSlots.forEach((el, i) => {
    const g = GENERAL[i];
    paint(el, g, g.cooldown(), g.ready());
  });

  gun.update(dt);
  mobs.update(dt, hurtPlayer);
  villagers.update(dt);
  townVoice.update(dt);    // fire-and-forget inside; never awaited from the loop
  warcries.update(dt);     // bakes in town, ticks its budgets everywhere
  raids.update(dt);
  // The sun does its slow work. Sky, fog, and both lights ride one number.
  dayNight.advance(dt);
  {
    const dl = dayNight.daylight();
    SKY.copy(SKY_NIGHT).lerp(SKY_DAY, dl);
    scene.fog.color.copy(SKY);
    sun.intensity = 0.08 + 1.07 * dl;
    hemi.intensity = 0.22 + 0.63 * dl;
  }
  // Only traders get a plate: labelling every keeper would turn a town into a wall of text.
  hpBars.draw(mobs.entities());
  // Floating damage numbers for your hits (mob + boss), then clear the frame's events.
  for (const ev of mobs.hitEvents) dmgText.spawn(ev.x, ev.y, ev.z, ev.amount, ev.weak);
  for (const ev of boss.hitEvents) dmgText.spawn(ev.x, ev.y, ev.z, ev.amount, ev.weak);
  mobs.hitEvents.length = 0;
  boss.hitEvents.length = 0;
  dmgText.draw(dt);
  // Trader nameplates, plus a green ALLY marker over the nearest of your own army — only the
  // closest handful, so a friendly horde does not become a wall of labels. The gun already
  // ignores them; this is the second half, telling you at a glance which ones NOT to shoot.
  const allyPlates = [];
  // RAID CHAMPIONS get RED plates — the same name a friendly town's vendor wears, but marked
  // as a threat, so "kill the Herbalist first" is a decision the labels actually let you make.
  const champPlates = [];
  if (player.faction) {
    const near = [];
    for (const e of mobs.entities()) {
      if (e.champion) {
        const d = (e.x - player.x) ** 2 + (e.z - player.z) ** 2;
        if (d < 46 * 46) champPlates.push({
          x: e.x, y: e.y + 2.4 * (e.scale || 1), z: e.z, label: CHAMPION_NAME[e.champion], champion: true,
        });
        continue;
      }
      if (!isMyAlly(e.faction)) continue;
      const d = (e.x - player.x) ** 2 + (e.z - player.z) ** 2;
      if (d < 34 * 34) near.push({ e, d });
    }
    near.sort((a, b) => a.d - b.d);
    for (const { e } of near.slice(0, 10)) {
      allyPlates.push({ x: e.x, y: e.y + 1.9, z: e.z, label: "ALLY", ally: true });
    }
  }
  plates.draw([
    ...villagers.list.filter((v) => Villagers.sells(v))
      .map((v) => ({ x: v.x, y: v.y + 2.05, z: v.z, label: v.role.name, sub: "F to trade" })),
    ...champPlates,
    ...allyPlates,
  ]);

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
  // Anything the boss lands on you counts as engagement too, so the bar stays up through a
  // stretch where you are doing nothing but surviving.
  boss.update(dt,
    (dmg, bx, bz) => { boss.engage(); damagePlayer(dmg, bx, bz, 9); },
    (dmg, mx, mz) => { boss.engage(); damagePlayer(dmg, mx, mz, 7); },
    // The beam burns continuously, so it deals damage with NO knockback — being shoved
    // every frame while standing in it would fight the very movement it is demanding.
    (dmg, bx, bz) => { boss.engage(); damagePlayer(dmg, bx, bz, 0, true); });

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

  // The debounced write, plus a slow backstop so a long quiet session of just walking and
  // killing is never entirely unrecorded.
  if (saveT > 0) { saveT -= dt; if (saveT <= 0) persist(); }
  autosaveT -= dt;
  if (autosaveT <= 0) { autosaveT = AUTOSAVE_EVERY; persist(); }

  if (player.potionCd > 0) player.potionCd -= dt;
  if (combatT > 0) combatT -= dt;
  hunted = mobs.anyHunting() || (boss.active
    && Math.hypot(boss.alive.x - player.x, boss.alive.z - player.z) < BOSS.aggroRange);
  if (player.hp < player.maxHp) {
    if (inSafe) {
      // A town mends you fast, ignoring the combat delay — walk in hurt, walk out whole.
      player.hp = Math.min(player.maxHp, player.hp + player.maxHp * REGEN.safeFrac * dt);
    } else if (combatT <= 0 && !hunted) {
      player.hp = Math.min(player.maxHp, player.hp + REGEN.rate * dt);
    }
  }

  updateGearDrops(dt);
  updateSpells(dt);
  updateSpin(dt);
  updateLevelFx(dt);
  minimap.draw(dt, mobs, boss, villagers);

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

  drawBossBar();
  drawJumps();
  drawEnergy();

  if (hurtT > 0) {
    hurtT -= dt;
    hurtEl.style.opacity = String(Math.max(0, hurtT / 0.35) * 0.55);
  }

  // Socket 2 in practice: the render layer READS sim state and owns none of it.
  body.position.set(player.x, player.y + 0.62, player.z);
  body.rotation.y = (player.whirlT > 0 || player.spinT > 0) ? (body.rotation.y + dt * 22) : player.yaw;
  body.visible = rig.blend < 0.85;      // hide your own head in first person

  const ring = ringAt(player.x, player.z);
  const tier = tierAt(player.x, player.z);
  const fromSpawn = Math.hypot(player.x, player.z);
  const toNextRing = tierStart(tier + 1) - fromSpawn;
  const bossStatus = boss.active ? ""
    : boss.eligible ? `boss  inbound ~${Math.ceil(bossTimer)}s\n`
      : `boss  none in ${RINGS[0].name} — ${Math.ceil(tierStart(1) - fromSpawn)}m to ${RINGS[1].name}\n`;
  const broken = brokenAffixes();
  // The HP bar is a FIXED length that fills by FRACTION of max HP, so gaining max health from
  // Stamina makes the NUMBER climb, not the bar grow ever longer across the screen.
  const HPBAR = 12;
  const hpN = player.maxHp > 0
    ? Math.max(0, Math.min(HPBAR, Math.round(player.hp / player.maxHp * HPBAR))) : 0;
  hud.textContent =
    (broken.length ? `⚠ affix disabled: ${broken.join(", ")} — see console\n` : "") +
    bossStatus +
    `${nearestGate()}\n` +
    `${RINGS[ring].name}  (tier ${tier})   ${Math.round(fromSpawn)}m out` +
    `   next ring ${Math.max(0, Math.ceil(toNextRing))}m   · ${dayNight.phase()}\n` +
    `xyz  ${player.x.toFixed(1)} ${player.y.toFixed(1)} ${player.z.toFixed(1)}\n` +
    // Pitch is on the debug HUD because "the view is stuck pointing up" was impossible to
    // diagnose without it — nothing in the game reported where you were looking, so the one
    // number that would have named the bug in seconds could only be guessed at from
    // screenshots. A state you cannot observe is a state you cannot debug.
    `cam  ${rig.mode}   look ${CAMERA.sensitivity.toFixed(4)}  [ / ]   ` +
    `pitch ${(player.pitch * 180 / Math.PI).toFixed(0)}°\n` +
    `${(() => {
      const f = myFaction();
      if (!f) return player.level >= 10 ? "unaligned — a quartermaster in any city will take you in\n" : "";
      const pr = repProgress(player.rep || 0);
      const n = Math.round(pr.frac * 10);
      return `${f.name}  ${pr.name}  ${"▮".repeat(n)}${"▯".repeat(10 - n)}`
        + `${pr.need ? ` ${player.rep}/${pr.need}` : " · highest"}\n`;
    })()}` +
    `LVL ${player.level}  dmg ×${player.dmgMult.toFixed(2)}  spd ×${player.speedMult.toFixed(2)}  jmp ×${player.jumpMult.toFixed(2)}\n` +
    `    ${"▮".repeat(Math.round(levelProgress() * 12))}` +
    `${"▯".repeat(12 - Math.round(levelProgress() * 12))} ${player.xp}/${xpToNext(player.level)}xp\n` +
    `hp   ${"█".repeat(hpN)}${"░".repeat(HPBAR - hpN)} ` +
    `${Math.max(0, Math.round(player.hp))}/${Math.round(player.maxHp)}` +
    `${player.hp < player.maxHp
      ? hunted ? "  (hunted)"
        : combatT > 0 ? `  (${combatT.toFixed(0)}s)`
          : "  ▲"
      : ""}` +
    `   kills ${mobs.killed}  born ${mobs.born}  packs ${mobs.packs.size}  ${killFeed}\n` +
    `${heal.casting
      ? `${"▰".repeat(Math.round(heal.progress * 10))}${"▱".repeat(10 - Math.round(heal.progress * 10))} HOLD STILL\n`
      : ""}` +
    `${player.gearDmg ? `   dmg +${Math.round(player.gearDmg * 100)}%` : ""}` +
    `${player.armor ? `   armour ${player.armor} (-${Math.round(armorDR(player.armor, tier) * 100)}%)` : ""}` +
    `${player.haste ? `   haste +${Math.round((player.hasteFire - 1) * 100)}%` : ""}\n` +

    `${gun.weapon.name}  ${inSafeZone ? "stowed (safe zone)" : gun.reloading > 0 ? "reloading…"
    : gun.weapon.mode === "beam" ? `heat ${Math.round(gun.heat * 100)}%${gun.overheated > 0 ? " OVERHEAT" : ""}`
    : gun.weapon.mode === "melee" ? (player.spinCd > 0 ? `spin ${player.spinCd.toFixed(1)}s` : "spin ready")
    : `${gun.mag}/${gun.weapon.magSize}`}${gun.loadout.length > 1 ? "  (wheel to swap)" : ""}` +
    `   ${player.iframes > 0 ? "· I-FRAMES ·" : player.dodgeCd > 0 ? "dodge cd" : "dodge ready"}\n` +
    `${bridge.label}${speaking ? "  ·  thinking…" : ""}\n` +
    `${!paused && document.pointerLockElement !== renderer.domElement
      ? "click to restore mouse look\n" : ""}` +
    `in   fwd ${input.fwd >= 0 ? " " : ""}${input.fwd} str ${input.right >= 0 ? " " : ""}${input.right}` +
    `  ${input.aimHeld ? "AIM" : "---"}${input.aim ? "*" : " "}` +
    `  ${player.dodgeT > 0 ? "ROLL" : "    "}  ${player.onGround ? "grnd" : "air "}\n` +
    `fps  ${fps.toFixed(0)}   chunks ${streamer.loaded.size}`;

  // Overwatch-style HUD: big health bottom-left, big ammo bottom-right.
  const hpFrac = player.maxHp > 0 ? player.hp / player.maxHp : 0;
  const dr = player.armor ? Math.round(armorDR(player.armor, tier) * 100) : 0;
  healthEl.className = hpFrac < 0.35 ? "low" : "";
  healthEl.innerHTML =
    `<div class="hp-lvl">LVL ${player.level}</div>`
    + `<div class="hp-top"><span class="hp-num">${Math.max(0, Math.round(player.hp))}</span>`
    + `<span class="hp-max">/ ${Math.round(player.maxHp)}</span>`
    + `${dr ? `<span class="hp-arm">◆ ${dr}% ARMOR</span>` : ""}</div>`
    + `<div class="hp-track"><div class="hp-fill" style="width:${Math.max(0, Math.min(100, hpFrac * 100))}%"></div></div>`;

  // The weapon panel now answers a second question. LMB state was always here (ammo /
  // reload / stowed); the faction weapons put something real on RMB too, and a cooldown you
  // cannot see is a cooldown you do not use — so the right-click's state sits beside the
  // ammo, in the one corner your eyes already visit for weapon truth.
  {
    const w = gun.weapon;
    const magMax = w.magSize;
    const lowAmmo = gun.mag <= Math.ceil(magMax * 0.25);
    let left;
    if (gun.lockedFor(player.faction)) left = `<span class="am-reload">NOT ${w.faction.toUpperCase()}</span>`;
    else if (inSafeZone) left = `<span class="am-stow">STOWED</span>`;
    else if (w.mode === "melee") left = `<span class="am-cur">∞</span>`;
    else if (w.mode === "beam") {
      // Heat is the lance's ammunition, so it lives where ammunition lives.
      const pct = Math.round(gun.heat * 100);
      left = gun.overheated > 0
        ? `<span class="am-reload">OVERHEAT</span>`
        : `<span class="am-cur ${pct > 70 ? "low" : ""}">${pct}%</span><span class="am-max"> heat</span>`;
    } else if (gun.reloading > 0) left = `<span class="am-reload">RELOAD</span>`;
    else left = `<span class="am-cur ${lowAmmo ? "low" : ""}">${gun.mag}</span><span class="am-max">/ ${magMax}</span>`;

    let rc = "";
    if (w.mode === "melee" && !inSafeZone) {
      rc = player.spinT > 0 ? `<span class="am-rc on">SPINNING</span>`
        : player.spinCd > 0 ? `<span class="am-rc">RMB ${player.spinCd.toFixed(1)}s</span>`
          : `<span class="am-rc up">RMB SPIN</span>`;
    }
    ammoEl.innerHTML =
      `<div class="am-name" style="${w.color ? `color:${w.color}` : ""}">${w.name}${gun.loadout.length > 1 ? " ⟳" : ""}</div>`
      + `<div class="am-row">${left}${rc}</div>`;
  }

  const xpPct = Math.round(levelProgress() * 100);
  xpEl.innerHTML = `<div class="xp-fill" style="width:${xpPct}%"></div>`
    + `<div class="xp-txt">LVL ${player.level} · ${player.xp}/${xpToNext(player.level)} XP</div>`;

  // Reputation, directly above XP, in your faction's colour. Only exists once you have
  // sworn — and it flashes when standing lands, so a turn-in reads on the bar, not just in
  // a number buried on a vendor screen.
  {
    const f = myFaction();
    if (!f) { repEl.style.display = "none"; lastRep = -1; }
    else {
      repEl.style.display = "";
      const rep = player.rep || 0;
      if (lastRep >= 0 && rep > lastRep) repFlashT = 0.8;
      lastRep = rep;
      repFlashT = Math.max(0, repFlashT - dt);
      repEl.classList.toggle("flash", repFlashT > 0);
      const pr = repProgress(rep);
      const pct = Math.round(pr.frac * 100);
      repEl.innerHTML = `<div class="rep-fill" style="width:${pct}%;background:${f.color}"></div>`
        + `<div class="rep-txt" style="color:${f.color}">${f.name.toUpperCase()} · ${pr.name.toUpperCase()}`
        + `${pr.need ? ` ${pr.have}/${pr.need}` : ""} REP</div>`;
    }
  }

  // Nudge outward once the ground you're on has greyed for your level (kills barely pay).
  const greyMult = xpLevelMult(tier, player.level);
  const greying = !inSafeZone && greyMult < 0.6;
  alertEl.classList.toggle("show", greying);
  // The night's one affordance, surfaced exactly when it's usable: safe walls, dark sky.
  sleepHintEl.classList.toggle("show", inSafe && dayNight.daylight() < 0.35 && !sleeping && !dead);
  if (greying) {
    alertEl.textContent = greyMult <= 0
      ? "➤ These lands hold no more for you — travel to the next ring for XP"
      : "➤ Your XP here is fading — push to the next ring";
  }

  renderer.render(scene, camera);
}
requestAnimationFrame(frame);

// A fresh run must choose its difficulty before anything can start.
if (newGame) showDifficultyPicker();
