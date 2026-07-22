// Q — the channelled heal.
//
// The interesting part isn't the healing, it's the ROOT. Every other verb in this game is
// movement; this one forbids it for 1.5 seconds and breaks the moment you're touched. So
// it's not a button you press when hurt — it's a window you have to earn, by reading the
// boss's volley gaps or by breaking line of sight from a pack first.

import * as THREE from "three";
import { HEAL } from "../config.js";
import { player } from "../state.js";
import { sfx } from "../audio/sfx.js";

export class Heal {
  constructor(scene) {
    this.castT = 0;
    this.cooldown = 0;
    this.voice = null;        // handle to the rising cast tone, so an interrupt can cut it
    this.lastResult = "";

    const ring = new THREE.RingGeometry(0.75, 1.05, 32);
    ring.rotateX(-Math.PI / 2);
    this.ring = new THREE.Mesh(ring, new THREE.MeshBasicMaterial({
      color: 0x66ffaa, transparent: true, opacity: 0, depthWrite: false,
      side: THREE.DoubleSide,
    }));
    this.ring.visible = false;
    scene.add(this.ring);

    this.flash = new THREE.Mesh(
      new THREE.IcosahedronGeometry(1, 2),
      new THREE.MeshBasicMaterial({ color: 0x88ffbb, transparent: true, opacity: 0 }),
    );
    this.flash.visible = false;
    scene.add(this.flash);
    this.flashT = 0;
  }

  get casting() { return this.castT > 0; }
  get progress() { return this.casting ? 1 - this.castT / HEAL.castTime : 0; }

  start() {
    if (this.casting || this.cooldown > 0) return false;
    if (player.hp >= player.maxHp) { this.lastResult = "already whole"; return false; }
    this.castT = HEAL.castTime;
    this.ring.visible = true;
    this.voice = sfx.healCast(HEAL.castTime);
    this.lastResult = "";
    return true;
  }

  /** Movement, a dodge, a jump, or a hit — all of them break the channel. */
  interrupt(why = "interrupted") {
    if (!this.casting) return;
    this.castT = 0;
    this.ring.visible = false;
    this.voice?.stop();
    this.voice = null;
    this.lastResult = why;
    sfx.healBreak();
  }

  update(dt, moving) {
    if (this.cooldown > 0) this.cooldown -= dt;

    if (this.casting) {
      if (moving) {
        this.interrupt("moved");
      } else {
        this.castT -= dt;
        const p = this.progress;
        this.ring.position.set(player.x, player.y + 0.05, player.z);
        this.ring.scale.setScalar(1.6 - p * 0.6);        // tightens as it completes
        this.ring.material.opacity = 0.25 + p * 0.5;
        if (this.castT <= 0) this.complete();
      }
    }

    if (this.flashT > 0) {
      this.flashT -= dt;
      const f = Math.max(0, this.flashT / 0.4);
      this.flash.position.set(player.x, player.y + 0.9, player.z);
      this.flash.scale.setScalar(1.4 - f * 0.7);
      this.flash.material.opacity = f * 0.55;
      if (this.flashT <= 0) this.flash.visible = false;
    }
  }

  complete() {
    const before = player.hp;
    player.hp = Math.min(player.maxHp, player.hp + HEAL.amount);
    this.castT = 0;
    this.cooldown = HEAL.cooldown;
    this.ring.visible = false;
    this.voice = null;
    this.flash.visible = true;
    this.flashT = 0.4;
    this.lastResult = `+${Math.round(player.hp - before)} hp`;
    sfx.healDone();
  }
}
