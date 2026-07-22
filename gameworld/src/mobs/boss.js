// D10 — the giant boss and its meteor volleys.
//
// The design rule this file exists to enforce: EVERY source of damage is telegraphed and
// avoidable. A meteor paints a ring on the ground for 1.3s before it commits, so being hit
// is always a failure to move, never a failure to have guessed. That's what separates a
// boss from a damage tax — and it's why the fight can be long without being tedious.
//
// One rig, re-dressed per ring (scale, tint, volley size). Authoring twelve unique fights
// is the tarpit; authoring one readable fight and varying its dressing is not.

import * as THREE from "three";
import { BOSS } from "../config.js";
import { player } from "../state.js";
import { groundY, ringAt, tierAt, ringPressure } from "../world/gen.js";
import { sanctuaryOf } from "../world/sanctuary.js";
import { mulberry32 } from "../rng.js";
import { sfx } from "../audio/sfx.js";

const METEOR_POOL = 28;

export class Boss {
  constructor(scene, seed = 0xB055) {
    this.scene = scene;
    this.rng = mulberry32(seed);
    this.alive = null;        // the sim record — plain data (socket 2)
    this.group = null;
    this.shake = 0;
    this.killed = 0;

    // Meteors are pooled: a volley in phase 2 can put a dozen rocks in the air at once,
    // and allocating meshes mid-fight is exactly when you can least afford a GC pause.
    // The beam: a column of light with a burning spot under it. Reads from any camera
    // angle and on any slope, which a ground-level beam would not.
    this.beamCol = new THREE.Mesh(
      new THREE.CylinderGeometry(BOSS.beamRadius, BOSS.beamRadius * 0.8, 70, 20, 1, true),
      new THREE.MeshBasicMaterial({
        color: 0xff4d2b, transparent: true, opacity: 0, side: THREE.DoubleSide, depthWrite: false,
      }));
    this.beamCol.visible = false;
    scene.add(this.beamCol);

    const spot = new THREE.CircleGeometry(BOSS.beamRadius, 32);
    spot.rotateX(-Math.PI / 2);
    this.beamSpot = new THREE.Mesh(spot, new THREE.MeshBasicMaterial({
      color: 0xff7a3a, transparent: true, opacity: 0, depthWrite: false, side: THREE.DoubleSide,
    }));
    this.beamSpot.visible = false;
    scene.add(this.beamSpot);

    this.meteors = [];
    const rockGeo = new THREE.IcosahedronGeometry(1.5, 0);
    const ringGeo = new THREE.RingGeometry(BOSS.meteorRadius * 0.55, BOSS.meteorRadius, 24);
    ringGeo.rotateX(-Math.PI / 2);
    for (let i = 0; i < METEOR_POOL; i++) {
      const rock = new THREE.Mesh(rockGeo, new THREE.MeshLambertMaterial({
        color: 0x3a2018, emissive: 0xff4400, emissiveIntensity: 0.9,
      }));
      const mark = new THREE.Mesh(ringGeo, new THREE.MeshBasicMaterial({
        color: 0xff3322, transparent: true, opacity: 0, depthWrite: false,
        side: THREE.DoubleSide,
      }));
      rock.visible = false;
      mark.visible = false;
      scene.add(rock);
      scene.add(mark);
      this.meteors.push({ rock, mark, state: "idle", t: 0, x: 0, z: 0, y: 0 });
    }
  }

  get active() { return this.alive !== null; }

  spawn(x, z) {
    if (this.alive) return null;
    // Never on holy ground. A boss inside the walls would be unkillable (weapons are
    // stowed in there) and would break the one promise a sanctuary makes.
    if (sanctuaryOf(x, z, BOSS.contactRange + 12)) return null;
    const ring = Math.max(BOSS.spawnRing, tierAt(x, z));
    // Accelerates with depth like the trash, but on a gentler ramp — see BOSS.ramp.
    const hp = BOSS.hp * Math.pow(BOSS.hpGrowth, ringPressure(ring, BOSS.ramp));

    this.alive = {
      x, y: groundY(x, z), z,
      ring, hp, maxHp: hp,
      // One multiplier, applied wherever this boss deals damage.
      dmg: 1 + BOSS.damagePerTier * ring,
      volleyCd: 2.6,
      contactCd: 0,
      phase: 1,
      charging: false,
      roarCd: BOSS.roarEvery[0],
      nextIsBeam: false,          // alternates with the volley
      beamWarm: 0, beamT: 0, beamX: x, beamZ: z,
    };
    sfx.roar(x, z, true);          // it announces itself

    // The rig: a bulk, a head, and a glowing core that is the whole reason to aim.
    const g = new THREE.Group();
    const tint = new THREE.Color().setHSL(0.02 + ring * 0.07, 0.45, 0.34);
    const body = new THREE.Mesh(
      new THREE.ConeGeometry(1.1, 2.6, 6),
      new THREE.MeshLambertMaterial({ color: tint }),
    );
    body.position.y = 1.3;
    const head = new THREE.Mesh(
      new THREE.IcosahedronGeometry(0.72, 0),
      new THREE.MeshLambertMaterial({ color: tint.clone().offsetHSL(0, 0, -0.1) }),
    );
    head.position.y = 2.9;
    this.core = new THREE.Mesh(
      new THREE.IcosahedronGeometry(0.34, 1),
      new THREE.MeshBasicMaterial({ color: 0x66ffcc }),
    );
    this.core.position.set(0, 1.75, 0.85);   // on the chest, facing you
    g.add(body, head, this.core);
    g.scale.setScalar(BOSS.scale);
    g.position.set(x, this.alive.y, z);
    this.scene.add(g);
    this.group = g;
    return this.alive;
  }

  /** Are we somewhere a boss is allowed to find us? */
  get eligible() {
    return !this.alive && ringAt(player.x, player.z) >= BOSS.spawnRing;
  }

  /** Spawn one near the player if none is up and we're out past the Commons. */
  maybeSpawn() {
    if (!this.eligible) return false;
    // Several attempts: near a big city most bearings are blocked, and one rejected roll
    // would otherwise mean no boss appears at all for the whole retry interval.
    for (let i = 0; i < 12; i++) {
      const a = this.rng() * Math.PI * 2;
      const d = BOSS.spawnDist[0] + this.rng() * (BOSS.spawnDist[1] - BOSS.spawnDist[0]);
      if (this.spawn(player.x + Math.cos(a) * d, player.z + Math.sin(a) * d)) return true;
    }
    return false;
  }

  despawn() {
    this.hideBeam();
    if (!this.group) return;
    this.scene.remove(this.group);
    this.group.traverse((o) => { if (o.isMesh) { o.geometry.dispose(); o.material.dispose(); } });
    this.group = null;
    this.alive = null;
  }

  /** Body and core are separate spheres so the core can pay out for precision (D4/D5). */
  targets() {
    if (!this.alive) return [];
    const b = this.alive;
    const s = BOSS.scale;
    const corePos = new THREE.Vector3(0, 1.75, 0.85).multiplyScalar(s).applyAxisAngle(
      new THREE.Vector3(0, 1, 0), this.group.rotation.y,
    );
    return [
      { id: -1, tag: "boss", x: b.x, y: b.y + 1.5 * s, z: b.z, r: 1.15 * s },
      { id: -2, tag: "bossWeak", x: b.x + corePos.x, y: b.y + corePos.y, z: b.z + corePos.z, r: 0.42 * s },
    ];
  }

  hit(tag, amount) {
    if (!this.alive) return null;
    const dmg = tag === "bossWeak" ? amount * BOSS.weakMultiplier : amount;
    this.alive.hp -= dmg;
    if (this.alive.hp <= 0) {
      const ring = this.alive.ring;
      this.despawn();
      this.killed++;
      return { killed: true, ring, weak: tag === "bossWeak", dmg };
    }
    return { killed: false, weak: tag === "bossWeak", dmg };
  }

  fireVolley() {
    const b = this.alive;
    let n = BOSS.volleyCount + BOSS.volleyPerRing * b.ring;
    if (b.phase === 2) n += BOSS.phase2Bonus;

    for (let i = 0; i < n; i++) {
      const slot = this.meteors.find((m) => m.state === "idle");
      if (!slot) break;                       // pool exhausted — drop the extra rock

      // Most rocks track YOU (so standing still is never safe); the rest rain around the
      // boss, which keeps melee range dangerous and gives the arena its shape.
      const atPlayer = this.rng() < BOSS.meteorAtPlayer;
      const cx = atPlayer ? player.x : b.x;
      const cz = atPlayer ? player.z : b.z;
      const a = this.rng() * Math.PI * 2;
      const r = this.rng() * BOSS.meteorScatter;

      slot.x = cx + Math.cos(a) * r;
      slot.z = cz + Math.sin(a) * r;
      if (sanctuaryOf(slot.x, slot.z, 0)) continue;   // rocks do not fall on holy ground
      slot.y = groundY(slot.x, slot.z);
      slot.state = "telegraph";
      slot.t = BOSS.meteorTelegraph;

      slot.mark.position.set(slot.x, slot.y + 0.06, slot.z);
      slot.mark.visible = true;
      slot.mark.material.opacity = 0.15;
      slot.rock.visible = false;
    }
  }

  update(dt, onPlayerHit, onMeteorHit, onBeamHit) {
    if (this.shake > 0) this.shake = Math.max(0, this.shake - dt * 1.8);
    this.updateMeteors(dt, onMeteorHit);
    this.updateBeam(dt, onBeamHit);

    const b = this.alive;
    if (!b) return;

    const dx = player.x - b.x, dz = player.z - b.z;
    const dist = Math.hypot(dx, dz) || 1;
    if (dist > BOSS.despawn) { this.despawn(); return; }

    if (b.phase === 1 && b.hp / b.maxHp <= BOSS.phase2At) {
      b.phase = 2;
      b.volleyCd = Math.min(b.volleyCd, 1.4);
      sfx.roar(b.x, b.z, true);                 // the phase change announces itself
    }

    if (b.contactCd > 0) b.contactCd -= dt;

    // A refuge holds against the boss too: it stops calling volleys down on you and stops
    // advancing. Meteors already in the air still land — you ran, they were already falling.
    if (sanctuaryOf(player.x, player.z, 0)) {
      b.charging = false;
      b.beamWarm = 0;
      b.beamT = 0;
      b.volleyCd = Math.max(b.volleyCd, BOSS.chargeTime + 0.5);
    } else if (dist < BOSS.aggroRange) {
      // Ambient roars: it is heard before it is seen, and keeps being heard.
      b.roarCd -= dt;
      if (b.roarCd <= 0) {
        const [lo, hi] = BOSS.roarEvery;
        b.roarCd = lo + this.rng() * (hi - lo);
        sfx.roar(b.x, b.z, false);
      }

      b.volleyCd -= dt;

      // The wind-up is a STATE, not just a sound cue — so the audio warning and the
      // mechanic can never drift out of sync. Charge starts, then rocks commit.
      if (!b.charging && b.volleyCd <= BOSS.chargeTime) {
        b.charging = true;
        sfx.charge(b.x, b.z, BOSS.chargeTime);
      }

      if (b.volleyCd <= 0) {
        b.volleyCd = BOSS.volleyCd * (b.phase === 2 ? BOSS.phase2Rate : 1);
        b.charging = false;
        if (b.nextIsBeam) {
          // Start the beam a little away from the player, so it has to travel to reach
          // you — arriving already on top of you would be unavoidable damage.
          const a = this.rng() * Math.PI * 2;
          b.beamX = player.x + Math.cos(a) * 9;
          b.beamZ = player.z + Math.sin(a) * 9;
          b.beamWarm = BOSS.beamWarm;
          sfx.charge(b.x, b.z, BOSS.beamWarm);
        } else {
          this.fireVolley();
        }
        b.nextIsBeam = !b.nextIsBeam;
      }
      // Lumbering approach. It should always be outrunnable — the pressure comes from
      // the sky, not from its feet.
      // Ward the boss the same way as the mobs: it writes position directly, so without
      // this it would simply walk through a town wall.
      const ux = dx / dist, uz = dz / dist;
      const nx = b.x + ux * BOSS.speed * dt;
      const nz = b.z + uz * BOSS.speed * dt;
      if (!sanctuaryOf(nx, nz, BOSS.contactRange)) { b.x = nx; b.z = nz; }
      b.y = groundY(b.x, b.z);

      if (dist < BOSS.contactRange && b.contactCd <= 0 && player.iframes <= 0) {
        b.contactCd = BOSS.contactCd;
        onPlayerHit?.(BOSS.contactDamage * b.dmg, b.x, b.z);
      }
    }

    this.group.position.set(b.x, b.y, b.z);
    this.group.rotation.y = Math.atan2(dx, dz);
    // The core pulses faster in phase 2 — a read on the fight's state you can see without
    // looking at a health bar. While charging it swells and goes hot, so the wind-up is
    // legible with the sound off too (never gate a mechanic on audio alone).
    const pulse = 1 + 0.16 * Math.sin(performance.now() * (b.phase === 2 ? 0.018 : 0.007));
    if (b.charging) {
      const f = 1 - Math.max(0, b.volleyCd) / BOSS.chargeTime;
      this.core.scale.setScalar(pulse * (1 + f * 1.6));
      this.core.material.color.setRGB(1, 0.55 - f * 0.45, 0.2);
    } else {
      this.core.scale.setScalar(pulse);
      this.core.material.color.setHex(0x66ffcc);
    }
  }

  /**
   * The beam hunts at a FIXED speed rather than interpolating toward the player. Lerping
   * would make it fastest when far and slowest when close — the exact opposite of the
   * pressure we want. Fixed speed means moving always escapes and standing always cooks.
   */
  updateBeam(dt, onBeamHit) {
    const b = this.alive;
    if (!b) { this.hideBeam(); return; }

    if (b.beamWarm > 0) {
      b.beamWarm -= dt;
      if (b.beamWarm <= 0) {
        b.beamT = BOSS.beamTime;
        this.beamVoice = sfx.beam(b.beamX, b.beamZ, BOSS.beamTime);
      }
    } else if (b.beamT > 0) {
      b.beamT -= dt;
      const speed = BOSS.beamSpeed + BOSS.beamSpeedPerTier * b.ring;
      const dx = player.x - b.beamX, dz = player.z - b.beamZ;
      const d = Math.hypot(dx, dz);
      if (d > 0.01) {
        const step = Math.min(d, speed * dt);
        b.beamX += (dx / d) * step;
        b.beamZ += (dz / d) * step;
      }
      if (d < BOSS.beamRadius && player.iframes <= 0) {
        onBeamHit?.(BOSS.beamDps * b.dmg * dt, b.beamX, b.beamZ);
      }
      if (b.beamT <= 0) this.hideBeam();
    } else {
      this.hideBeam();
      return;
    }

    const gy = groundY(b.beamX, b.beamZ);
    const warming = b.beamWarm > 0;
    this.beamSpot.position.set(b.beamX, gy + 0.07, b.beamZ);
    this.beamSpot.visible = true;
    this.beamSpot.material.opacity = warming ? 0.25 + 0.3 * (1 - b.beamWarm / BOSS.beamWarm) : 0.75;
    this.beamCol.position.set(b.beamX, gy + 35, b.beamZ);
    this.beamCol.visible = !warming;
    this.beamCol.material.opacity = warming ? 0 : 0.34;
  }

  hideBeam() {
    this.beamCol.visible = false;
    this.beamSpot.visible = false;
    this.beamVoice?.stop();
    this.beamVoice = null;
  }

  updateMeteors(dt, onMeteorHit) {
    for (const m of this.meteors) {
      if (m.state === "idle") continue;
      m.t -= dt;

      if (m.state === "telegraph") {
        // The marker brightens as the window closes: the fairness signal, and the reason
        // a hit is always "I didn't move" rather than "I couldn't have known".
        const f = 1 - m.t / BOSS.meteorTelegraph;
        m.mark.material.opacity = 0.15 + 0.55 * f * f;
        m.mark.scale.setScalar(1 + 0.25 * (1 - f));
        if (m.t <= 0) {
          m.state = "falling";
          m.t = BOSS.meteorFall;
          m.rock.visible = true;
        }
      } else if (m.state === "falling") {
        const f = Math.max(0, m.t / BOSS.meteorFall);
        m.rock.position.set(m.x, m.y + BOSS.meteorHeight * f * f, m.z);
        m.rock.rotation.x += dt * 6;
        m.rock.rotation.z += dt * 4;
        if (m.t <= 0) {
          const d = Math.hypot(player.x - m.x, player.z - m.z);
          if (d < BOSS.meteorRadius && player.iframes <= 0) {
            onMeteorHit?.(BOSS.meteorDamage * (this.alive?.dmg || 1), m.x, m.z);
          }
          sfx.explosion(m.x, m.z, 1.35);
          this.shake = Math.min(1, this.shake + BOSS.shake);
          m.state = "idle";
          m.rock.visible = false;
          m.mark.visible = false;
          m.mark.material.opacity = 0;
        }
      }
    }
  }
}
