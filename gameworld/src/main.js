// Entry point. Slice 1 of M1: a world you can walk around in.
//
// The loop is deliberately split: PHYSICS runs on a fixed step (feel must not depend on
// framerate), RENDER runs per frame. The substrate's 10Hz tick will slot in as a third
// clock at M3 — the same split localprototype/world/sim.py already uses to keep its fast
// clocks off the slow model calls.

import * as THREE from "three";
import { CAMERA, GUN, MOB, BOSS, GRENADE, HEAL, FIRERING, DASH, WHIRL, REGEN, LOOT, VILLAGE, RELIC, VIEW_RADIUS, CHUNK_X, RINGS } from "./config.js";
import { Mobs } from "./mobs/mobs.js";
import { affixList, brokenAffixes } from "./mobs/affixes.js";
import { Boss } from "./mobs/boss.js";
import { Folk } from "./mobs/folk.js";
import { Villagers } from "./town/villagers.js";
import { Guards } from "./town/guards.js";
import { Shop, GOODS } from "./ui/shop.js";
import { ICONS } from "./ui/icons.js";
import { Inventory } from "./ui/inventory.js";
import { Nameplates } from "./ui/nameplates.js";
import { HealthBars } from "./ui/healthbars.js";
import { rollRelic, applyRelic } from "./prog/relics.js";
import { armorDR } from "./prog/stats.js";
import { player, spawnPlayer, world } from "./state.js";
import { ChunkStreamer } from "./world/streamer.js";
import { ringAt, tierAt, tierStart, groundY } from "./world/gen.js";
import { Sanctuaries, sanctuaryOf, sanctuariesNear, boundaryAt, homeOfTier } from "./world/sanctuary.js";
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
import { award, killValue, bossValue, xpToNext, levelProgress, loseLevel, applyLevelStats, respawnTierFor, levelForTier } from "./prog/xp.js";
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
// Slimmer than the collision capsule on purpose: a body that exactly fills its hitbox looks
// bulky in third person and hides more of the screen than it needs to.
const body = new THREE.Mesh(
  new THREE.BoxGeometry(0.42, 1.25, 0.3),
  new THREE.MeshLambertMaterial({ color: 0xd8734a }),
);
scene.add(body);

const streamer = new ChunkStreamer(scene);
const rig = new CameraRig(camera);
const music = new Music();
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
        FIRERING.radius, FIRERING.damage, FIRERING.knock, false, false, knock);
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
    // Read the position BEFORE the hit: a killing blow despawns the boss, and the relic
    // has to fall where it stood.
    const bx = boss.alive.x, bz = boss.alive.z;
    const res = boss.hit("boss", DASH.damage * player.dmgMult);
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
        WHIRL.slamRadius, WHIRL.slamDamage, 14, false);
  whirlRing.position.set(player.x, player.y + 0.3, player.z);
  whirlRing.visible = true;
  slamFx = 0.45;
  sfx.explosion(player.x, player.z, 1.3);
  player.whirlT = WHIRL.spinTime;
  whirlTick = 0;
}

// Boss relics lying on the ground. One mesh, one relic at a time — bosses are rare enough
// that two drops never coexist, and a pool would be ceremony for a maximum of one.
const relicMesh = (() => {
  const g = new THREE.OctahedronGeometry(0.6, 0);
  const m = new THREE.Mesh(g, new THREE.MeshBasicMaterial({ color: 0xffd45e }));
  m.visible = false;
  scene.add(m);
  return m;
})();
const relicLight = new THREE.PointLight(0xffc94a, 0, 22);
scene.add(relicLight);
let groundRelic = null;      // { relic, x, y, z, t }

function dropRelic(x, z, tier) {
  const relic = rollRelic(tier, shakeRng);
  groundRelic = { relic, x, y: groundY(x, z) + 1.1, z, t: RELIC.life };
  relicMesh.position.set(x, groundRelic.y, z);
  relicMesh.visible = true;
  killFeed = `◆ BOSS DOWN ◆   ${relic.name} lies where it fell`;
  relicMesh.material.color.set(relic.color);
}

function updateRelic(dt) {
  if (!groundRelic) return;
  groundRelic.t -= dt;
  const r = groundRelic;
  relicMesh.rotation.y += dt * 1.6;
  relicMesh.position.y = r.y + Math.sin(performance.now() * 0.003) * RELIC.bob;
  relicLight.position.copy(relicMesh.position);
  relicLight.intensity = 8 + Math.sin(performance.now() * 0.005) * 3;

  if (Math.hypot(player.x - r.x, player.z - r.z) < RELIC.pickupRange) {
    applyRelic(r.relic, gameCtx);
    applyLevelStats();                  // fold it in the same way a purchase would
    tradeMsg = `${r.relic.name} — ${r.relic.lines.join(", ")}`;
    tradeMsgT = 6;
    sfx.healDone();
    groundRelic = null;
    relicMesh.visible = false;
    relicLight.intensity = 0;
    return;
  }
  if (r.t <= 0) {
    groundRelic = null;
    relicMesh.visible = false;
    relicLight.intensity = 0;
  }
}

const barEl = document.getElementById("bar");
barEl.innerHTML = Array.from({ length: SLOTS }, (_, i) => slotHtml(i + 1)).join("")
  + `<div class="sep"></div>`
  + GENERAL.map((g) => slotHtml(g.key)).join("");
const allSlots = [...barEl.querySelectorAll(".slot")];
const barSlots = allSlots.slice(0, SLOTS);
const genSlots = allSlots.slice(SLOTS);
const pointsEl = document.getElementById("points");
const inventory = new Inventory(document.getElementById("inv"), abilities, {
  onClose: () => resumeFromShop(),
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
});
const minimap = new Minimap(document.getElementById("minimap"));
const sanctuaries = new Sanctuaries(scene);
const folk = new Folk(scene);
const villagers = new Villagers(scene);
const guards = new Guards(scene);
const plates = new Nameplates(document.getElementById("plates"), camera);
const hpBars = new HealthBars(document.getElementById("hpbars"), camera);
let tradeMsg = "", tradeMsgT = 0;
// One context object for anything that can grant or change player state, so the shop and
// the admin panel hand out abilities through exactly the same path. Getters are lazy
// because grenades/abilities are constructed further down.
const gameCtx = {
  get grenades() { return grenades; },
  get abilities() { return abilities; },
  fireRing,
  dashStrike,
  whirlwind,
  applyStats: () => applyLevelStats(),   // gear changes re-derive the same way levels do
  onClose: () => resumeFromShop(),
};
const shop = new Shop(document.getElementById("shop"), gameCtx);

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
  // Armour applies HERE, at the one place damage enters the player — so it covers mob hits,
  // meteors, the beam, burning ground and your own grenades without any of them knowing it
  // exists. GEAR.md G1: mitigation is the WoW armour curve, and it reads the attacker's tier
  // (proxied by where you are standing, since what hits you is native to your ring) — the
  // same armour is worth less the deeper you go, which is why it can't be grinded shallow.
  player.hp -= amount * (1 - armorDR(player.armor, tierAt(player.x, player.z)));
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
  // Standing behind the guns must never pay. Without this the optimal way to play is to let
  // the town farm the frontier for you, which is both boring and unbeatable.
  if (guards.inDeadZone()) { killFeed = "no reward near the gate guards"; return; }
  player.points += Math.round((LOOT.base + LOOT.perTier * res.ring)
    * (res.elite ? LOOT.eliteMult : 1));
  const xp = killValue(res.ring, res.elite);
  const lv = award(xp);
  // Naming what you killed is half of learning to read them.
  const what = res.affixes ? `★ ${res.affixes}` : res.elite ? "★ elite" : "kill";
  killFeed = `${what}  +${xp}xp${lv ? `   ▲ LEVEL ${player.level}` : ""}`;
  if (lv) sfx.healDone();
}

function rewardBoss(ring, x, z) {
  player.points += Math.round((LOOT.base + LOOT.perTier * ring) * LOOT.bossMult);
  const xp = bossValue(ring);
  const lv = award(xp);
  killFeed = `◆ BOSS DOWN ◆  +${xp}xp${lv ? `   ▲ LEVEL ${player.level}` : ""}`;
  if (lv) sfx.healDone();
  // The relic falls where the boss did — you have to walk into the arena to take it, which
  // is a last small decision if anything else is still alive.
  if (x !== undefined) dropRelic(x, z, ring);
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
               knock = GRENADE.knockback, hurtsYou = true, flat = false, shove = false) {
  const falloff = (d) => (flat ? 1 : Math.max(0.25, 1 - d / radius));

  for (const e of [...world.entities.values()]) {
    if (e.kind !== "mob") continue;
    const d = Math.hypot(e.x - x, e.z - z, (e.y - y) * 0.5);
    if (d > radius) continue;
    const res = mobs.hit(e.id, damage * player.dmgMult * falloff(d));
    if (res?.killed) { reward(res); grenades.refill(); }
    else if (shove) mobs.push(e, x, z, FIRERING.shove);   // survivors get thrown clear
  }

  if (boss.active) {
    const b = boss.alive;
    const bx = b.x, bz = b.z;
    const d = Math.hypot(b.x - x, b.z - z);
    if (d < radius + BOSS.contactRange * 0.5) {
      const res = boss.hit("boss", damage * player.dmgMult * falloff(Math.max(0, d - BOSS.contactRange * 0.5)));
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

function respawn() {
  // D9: death costs your top level. Not the run, not your gear — one level, and you land
  // halfway to earning it back, so the loss stings without erasing the walk that bought it.
  const lost = loseLevel();

  // You wake in the great city of the ring you fell in — but only as deep as your LEVEL
  // entitles you to. Dying at tier 5 while under-levelled would otherwise be a free
  // teleport past everything you skipped, and the walk back out is the thing that makes
  // the frontier feel earned rather than handed over.
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
  const where = home?.city ? "the city" : "town";
  killFeed = `you died${lost ? `  ▼ LEVEL ${player.level}` : ""}  · woke in ${where}`
    + (wokeIn < diedIn
      ? `, carried back to ${RINGS[Math.min(wokeIn, RINGS.length - 1)].name}`
        + ` (tier ${diedIn} wants level ${levelForTier(diedIn)})`
      : "");
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
  // Pausing IS opening the inventory — the paused moment is exactly when you want to
  // rearrange your kit, and it saves inventing another key for it.
  if (p && everPlayed && !shop.open) inventory.show();
  else inventory.hide();
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
        const bx = boss.alive?.x, bz = boss.alive?.z;
        const res = boss.hit(hit.targetTag, GUN.damage * player.dmgMult);
        if (res?.killed) { rewardBoss(res.ring, bx, bz); grenades.refill(GRENADE.max); }
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
  // Leap -> slam. Gated on a PENDING FLAG, not on leapT still being positive: leapT is
  // decremented inside the fixed-step physics loop, so by the time this frame-level check
  // ran it had already crossed zero — and since the arc lasts longer than leapT, the player
  // was still airborne. The slam never fired at all, which is why the spin did no damage:
  // it never started.
  if (player.leapPending && (player.onGround || player.leapT <= 0)) whirlSlam();

  if (player.whirlT > 0) {
    player.whirlT -= dt;
    player.iframes = Math.max(player.iframes, 0.2);   // untouchable for the whole spin
    whirlTick -= dt;
    if (whirlTick <= 0) {
      whirlTick = WHIRL.spinTick;
      // Flat damage to the rim, so what you see is what it hits.
      blast(player.x, player.y + 1, player.z, WHIRL.spinRadius, WHIRL.spinDamage, 5, false, true);
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
    el.querySelector(".k").textContent = a?.key || String(i + 1);
    paint(el, a, abilities.cooldownOf(i), abilities.readyOf(i), abilities.chargesOf(i));
  });
  genSlots.forEach((el, i) => {
    const g = GENERAL[i];
    paint(el, g, g.cooldown(), g.ready());
  });

  gun.update(dt);
  mobs.update(dt, hurtPlayer);
  folk.update(dt);
  villagers.update(dt);
  // Guard kills award nothing at all -- guards.update handles their kills internally and
  // never pays. The reward() dead-zone check remains, but only for YOUR OWN kills made while
  // standing at the gate; a guard dropping a mob out on the frontier no longer pays you.
  guards.update(dt, mobs);
  // Only traders get a plate: labelling every keeper would turn a town into a wall of text.
  hpBars.draw(mobs.entities());
  plates.draw(villagers.list
    .filter((v) => Villagers.sells(v))
    .map((v) => ({ x: v.x, y: v.y + 2.05, z: v.z, label: v.role.name, sub: "F to trade" })));

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

  updateRelic(dt);
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
  body.position.set(player.x, player.y + 0.62, player.z);
  body.rotation.y = player.whirlT > 0 ? (body.rotation.y + dt * 22) : player.yaw;
  body.visible = rig.blend < 0.85;      // hide your own head in first person

  const ring = ringAt(player.x, player.z);
  const tier = tierAt(player.x, player.z);
  const fromSpawn = Math.hypot(player.x, player.z);
  const toNextRing = tierStart(tier + 1) - fromSpawn;
  const bossStatus = boss.active ? ""
    : boss.eligible ? `boss  inbound ~${Math.ceil(bossTimer)}s\n`
      : `boss  none in ${RINGS[0].name} — ${Math.ceil(tierStart(1) - fromSpawn)}m to ${RINGS[1].name}\n`;
  const bossLine = boss.active
    ? `BOSS ${"█".repeat(Math.max(0, Math.round(boss.alive.hp / boss.alive.maxHp * 20)))}` +
      `${"░".repeat(Math.max(0, 20 - Math.round(boss.alive.hp / boss.alive.maxHp * 20)))}` +
      ` ${Math.max(0, Math.round(boss.alive.hp))}  ${boss.alive.phase === 2 ? "· ENRAGED ·" : ""}\n`
    : "";
  const broken = brokenAffixes();
  hud.textContent =
    (broken.length ? `⚠ affix disabled: ${broken.join(", ")} — see console\n` : "") +
    bossLine + bossStatus +
    `${nearestGate()}\n` +
    `${RINGS[ring].name}  (tier ${tier})   ${Math.round(fromSpawn)}m out` +
    `   next ring ${Math.max(0, Math.ceil(toNextRing))}m\n` +
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
    `${player.gearDmg ? `   dmg +${Math.round(player.gearDmg * 100)}%` : ""}` +
    `${player.armor ? `   armour ${player.armor} (-${Math.round(armorDR(player.armor, tier) * 100)}%)` : ""}` +
    `${player.haste ? `   haste +${Math.round((player.hasteFire - 1) * 100)}%` : ""}\n` +

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
