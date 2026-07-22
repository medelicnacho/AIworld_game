// The minimap, and the thing it exists for: always knowing the way home.
//
// Spawn is the anchor of the whole difficulty design (D8) — every threat is defined by how
// far from it you are — so "which way is spawn, and how far" must never be a guess. Inside
// range it's a marker on the map; outside range it clamps to the rim as an ARROW with the
// distance beside it, so the compass keeps working at any distance.
//
// The map is rotated so UP is where you're facing, which is what you want for navigating.
// Terrain is baked north-up into an offscreen canvas and rotated at draw time — otherwise
// every frame would re-sample the heightfield just because you turned your head.

import { RINGS } from "../config.js";
import { player } from "../state.js";
import { heightAt, ringAt, tierStart } from "../world/gen.js";
import { sanctuariesNear, boundaryAt, gateArc } from "../world/sanctuary.js";

const RANGE = 130;        // world units from centre to rim
const TERRAIN_RES = 72;   // offscreen resolution of the baked terrain
const REBAKE_DIST = 6;    // re-bake once you've moved this far
const REBAKE_TIME = 0.6;

export class Minimap {
  constructor(canvas) {
    this.c = canvas;
    this.ctx = canvas.getContext("2d");
    this.size = canvas.width;
    this.r = this.size / 2;

    this.terrain = document.createElement("canvas");
    this.terrain.width = this.terrain.height = TERRAIN_RES;
    this.tctx = this.terrain.getContext("2d");
    this.bakedAt = null;
    this.bakeTimer = 0;
  }

  /** World offset -> map-space (mx = right, my = forward). */
  toMap(dx, dz) {
    const s = Math.sin(player.yaw), c = Math.cos(player.yaw);
    return { mx: dx * c - dz * s, my: -dx * s - dz * c };
  }

  bakeTerrain() {
    const img = this.tctx.createImageData(TERRAIN_RES, TERRAIN_RES);
    const d = img.data;
    const step = (RANGE * 2) / TERRAIN_RES;
    for (let j = 0; j < TERRAIN_RES; j++) {
      for (let i = 0; i < TERRAIN_RES; i++) {
        // North-up: +x right, +z down. Rotation happens at draw time.
        const wx = player.x + (i - TERRAIN_RES / 2) * step;
        const wz = player.z + (j - TERRAIN_RES / 2) * step;
        const h = heightAt(wx, wz);
        const tint = RINGS[ringAt(wx, wz)].tint;
        // Elevation shading over the ring tint: you can read both the land and the band.
        const v = 0.30 + Math.max(0, Math.min(1, (h - 18) / 30)) * 0.55;
        const k = (j * TERRAIN_RES + i) * 4;
        d[k] = 255 * v * tint[0] * 0.85;
        d[k + 1] = 255 * v * tint[1] * 0.95;
        d[k + 2] = 255 * v * tint[2] * 0.80;
        d[k + 3] = 255;
      }
    }
    this.tctx.putImageData(img, 0, 0);
    this.bakedAt = { x: player.x, z: player.z };
  }

  draw(dt, mobs, boss, folk) {
    const ctx = this.ctx, R = this.r;

    this.bakeTimer -= dt;
    const moved = !this.bakedAt
      || Math.hypot(player.x - this.bakedAt.x, player.z - this.bakedAt.z) > REBAKE_DIST;
    if (moved || this.bakeTimer <= 0) {
      this.bakeTimer = REBAKE_TIME;
      if (moved) this.bakeTerrain();
    }

    ctx.clearRect(0, 0, this.size, this.size);
    ctx.save();
    ctx.beginPath();
    ctx.arc(R, R, R - 2, 0, Math.PI * 2);
    ctx.clip();

    // Terrain, rotated so your facing points up.
    ctx.save();
    ctx.translate(R, R);
    ctx.rotate(player.yaw);
    ctx.imageSmoothingEnabled = true;
    const span = (R / RANGE) * (RANGE * 2);
    ctx.drawImage(this.terrain, -span / 2, -span / 2, span, span);
    ctx.restore();

    const scale = R / RANGE;
    const origin = this.toMap(-player.x, -player.z);   // spawn is world (0,0)

    // Ring boundaries, centred on spawn — the difficulty bands, drawn where they are.
    ctx.lineWidth = 1;
    for (let k = 1; k < RINGS.length + 4; k++) {
      const rr = tierStart(k) * scale;
      const cx = R + origin.mx * scale, cy = R - origin.my * scale;
      if (rr > R * 6) break;
      ctx.beginPath();
      ctx.arc(cx, cy, rr, 0, Math.PI * 2);
      ctx.strokeStyle = "rgba(255,255,255,0.16)";
      ctx.stroke();
    }

    // Sanctuaries — the thing most worth being able to find on a map, and the GATE most of
    // all: a doorway you have to run the whole perimeter to find is tedium, not challenge.
    for (const s of sanctuariesNear(player.x, player.z, RANGE * 1.4)) {
      const pt = (lx, lz) => {
        const p = this.toMap(s.x + lx - player.x, s.z + lz - player.z);
        return [R + p.mx * scale, R - p.my * scale];
      };

      ctx.beginPath();
      s.corners.forEach((c, i) => {
        const [px, py] = pt(c.x, c.z);
        if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
      });
      ctx.closePath();
      ctx.fillStyle = "rgba(79,191,106,0.20)";
      ctx.fill();

      // Outline drawn edge by edge with the gate arc LEFT OUT, so the opening reads as a
      // gap in the wall rather than needing a legend to explain it.
      ctx.strokeStyle = "#4fbf6a";
      ctx.lineWidth = 1.6;
      const arc = gateArc(boundaryAt(s, s.gate));
      for (let i = 0; i < s.corners.length; i++) {
        const A = s.corners[i], B = s.corners[(i + 1) % s.corners.length];
        const steps = 10;
        for (let k = 0; k < steps; k++) {
          const f0 = k / steps, f1 = (k + 1) / steps;
          const x0 = A.x + (B.x - A.x) * f0, z0 = A.z + (B.z - A.z) * f0;
          const x1 = A.x + (B.x - A.x) * f1, z1 = A.z + (B.z - A.z) * f1;
          const mid = Math.atan2((z0 + z1) / 2, (x0 + x1) / 2);
          let d = Math.abs(((mid - s.gate + Math.PI * 3) % (Math.PI * 2)) - Math.PI);
          if (d < arc) continue;                       // the gateway: leave it open
          const [ax, ay] = pt(x0, z0), [bx, by] = pt(x1, z1);
          ctx.beginPath();
          ctx.moveTo(ax, ay);
          ctx.lineTo(bx, by);
          ctx.stroke();
        }
      }

      // And mark it, so it's findable at a glance rather than only if you study the shape.
      const gr = boundaryAt(s, s.gate);
      const [gx, gy] = pt(Math.cos(s.gate) * gr, Math.sin(s.gate) * gr);
      ctx.beginPath();
      ctx.arc(gx, gy, 3.4, 0, Math.PI * 2);
      ctx.fillStyle = "#ffe066";
      ctx.fill();
      ctx.strokeStyle = "#4a3a00";
      ctx.lineWidth = 1.2;
      ctx.stroke();
    }

    // Mobs.
    for (const e of mobs.entities()) {
      const m = this.toMap(e.x - player.x, e.z - player.z);
      if (Math.hypot(m.mx, m.my) > RANGE) continue;
      ctx.beginPath();
      ctx.arc(R + m.mx * scale, R - m.my * scale, e.elite ? 3.4 : 2.2, 0, Math.PI * 2);
      ctx.fillStyle = e.elite ? "#ffd24a" : "#ff6b6b";
      ctx.fill();
    }

    // The green folk.
    if (folk) {
      for (const e of folk.entities()) {
        const m = this.toMap(e.x - player.x, e.z - player.z);
        if (Math.hypot(m.mx, m.my) > RANGE) continue;
        ctx.beginPath();
        ctx.arc(R + m.mx * scale, R - m.my * scale, 2, 0, Math.PI * 2);
        ctx.fillStyle = "#5fe08a";
        ctx.fill();
      }
    }

    // Boss — always shown, clamped to the rim if it's beyond range.
    if (boss.active) {
      const m = this.toMap(boss.alive.x - player.x, boss.alive.z - player.z);
      const d = Math.hypot(m.mx, m.my) || 1;
      const cl = Math.min(1, (RANGE - 6) / d);
      ctx.beginPath();
      ctx.arc(R + m.mx * scale * cl, R - m.my * scale * cl, 5, 0, Math.PI * 2);
      ctx.fillStyle = "#ff2d2d";
      ctx.fill();
      ctx.strokeStyle = "#ffffffcc";
      ctx.stroke();
    }

    // SPAWN: a marker in range, an arrow on the rim out of range.
    const od = Math.hypot(origin.mx, origin.my);
    const inRange = od <= RANGE - 8;
    const ox = R + origin.mx * scale * (inRange ? 1 : (RANGE - 10) / od);
    const oy = R - origin.my * scale * (inRange ? 1 : (RANGE - 10) / od);
    ctx.save();
    ctx.translate(ox, oy);
    if (inRange) {
      ctx.rotate(Math.PI / 4);
      ctx.fillStyle = "#7fffd0";
      ctx.fillRect(-3.5, -3.5, 7, 7);
      ctx.strokeStyle = "#04372b";
      ctx.lineWidth = 1.5;
      ctx.strokeRect(-3.5, -3.5, 7, 7);
    } else {
      // Point the arrow along the direction to spawn.
      ctx.rotate(Math.atan2(origin.mx, origin.my));
      ctx.beginPath();
      ctx.moveTo(0, -7);
      ctx.lineTo(5.5, 5);
      ctx.lineTo(-5.5, 5);
      ctx.closePath();
      ctx.fillStyle = "#7fffd0";
      ctx.fill();
      ctx.strokeStyle = "#04372b";
      ctx.lineWidth = 1.2;
      ctx.stroke();
    }
    ctx.restore();

    ctx.restore();   // un-clip

    // Rim.
    ctx.beginPath();
    ctx.arc(R, R, R - 2, 0, Math.PI * 2);
    ctx.strokeStyle = "rgba(220,232,248,0.5)";
    ctx.lineWidth = 2;
    ctx.stroke();

    // You, at the centre, facing up.
    ctx.beginPath();
    ctx.moveTo(R, R - 6);
    ctx.lineTo(R + 4.5, R + 5);
    ctx.lineTo(R - 4.5, R + 5);
    ctx.closePath();
    ctx.fillStyle = "#ffffff";
    ctx.fill();

    // Distance home, always legible.
    const home = Math.hypot(player.x, player.z);
    ctx.font = "10px ui-monospace, monospace";
    ctx.textAlign = "center";
    ctx.fillStyle = "#cfe3ff";
    ctx.fillText(`spawn ${Math.round(home)}m`, R, this.size - 5);
  }
}
