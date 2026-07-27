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
import { nearestGate, inDungeon } from "../world/dungeon.js";
import { servesYou, isHostileSanctuary, isMyAlly, FACTIONS } from "../prog/factions.js";
import { Villagers } from "../town/villagers.js";

const RANGE = 130;        // world units from centre to rim — UNCHANGED as the map grows, so
                          // a bigger map means a CLOSER look rather than a wider one. With a
                          // pack on top of you the question is "how many and where", and that
                          // needs the dots pulled apart, not more ground squeezed in.
const TERRAIN_RES = 108;  // offscreen resolution of the baked terrain (was 72 — a bigger map
                          // stretches this further, and 72 was already visibly blocky)
const REBAKE_DIST = 6;    // re-bake once you've moved this far
const REBAKE_TIME = 0.6;

// The map sizes itself to the window rather than being a fixed number of pixels, because a
// fixed size is wrong on both ends: 180 was cramped on a desktop and 280 would swallow a
// laptop screen. Bounded at both ends so it can never become a postage stamp or a wall.
const MAP_MIN = 200, MAP_MAX = 360, MAP_FRAC = 0.28;

/**
 * WHAT COLOUR A TOWN FLIES ON THE MAP.
 *
 * Every settlement used to be drawn the same green — the colour that means "refuge" — while
 * two out of every three would fight you the moment you stepped inside. The map was telling
 * you the opposite of the truth, and the faction system it was hiding is the whole point of
 * choosing a side. Whether a town is yours is now the FIRST thing you can see about it, from
 * across the map, before you are close enough for its garrison to muster.
 *
 * Three states, because there are exactly three answers a player needs:
 *   green   it serves you — your own colour, a neutral city, the spawn town. Walk in.
 *   red     a rival's. Its war-camp is standing right there and it will answer if you start.
 *   its own colour — before you have sworn to anyone, nothing in the world is hostile yet,
 *           so the map teaches you the board instead: which town belongs to which faction,
 *           so the choice you make at the quartermaster is an informed one.
 */
// And its NAME, written inside its own walls. The colour answers "do I fight here"; the name
// answers "which of the three is this" — a different question, and the one you are asking when
// you are hunting one colour in particular and every other camp on the ring belongs to somebody
// whose war is not yours. Two channels, because a red shape and a red shape are the same shape.
function townFlag(s) {
  const f = (s.faction === null || s.faction === undefined)
    ? null : FACTIONS[s.faction % FACTIONS.length];
  const name = f ? `${f.name} Camp` : s.city ? "Free City" : "Free Town";
  if (servesYou(s)) return { name, wall: "#4fbf6a", fill: "rgba(79,191,106,0.20)" };
  if (isHostileSanctuary(s)) return { name, wall: "#e0553f", fill: "rgba(224,85,63,0.20)" };
  if (!f) return { name, wall: "#c9d2e0", fill: "rgba(201,210,224,0.16)" };
  return { name, wall: f.color, fill: hexToFill(f.color, 0.18) };
}

/** "#5b9dff" -> "rgba(91,157,255,0.18)". The faction colours are authored as hex strings for
 *  text, and a wall needs the same hue at low alpha behind it. */
function hexToFill(hex, a) {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
}

export class Minimap {
  constructor(canvas) {
    this.c = canvas;
    this.ctx = canvas.getContext("2d");

    this.terrain = document.createElement("canvas");
    this.terrain.width = this.terrain.height = TERRAIN_RES;
    this.tctx = this.terrain.getContext("2d");
    this.bakedAt = null;
    this.bakeTimer = 0;
    this.resize();
  }

  /**
   * Fit to the window. The canvas keeps TWO sizes: the CSS size everything is drawn in, and a
   * backing store scaled by the display's pixel density — without that second one the town
   * labels turn to mush on a high-DPI screen, which is exactly the readability this change
   * exists to deliver.
   */
  resize() {
    const size = Math.round(Math.max(MAP_MIN, Math.min(MAP_MAX, innerHeight * MAP_FRAC)));
    const dpr = Math.min(devicePixelRatio || 1, 2);
    this.size = size;
    this.r = size / 2;
    this.c.style.width = `${size}px`;
    this.c.style.height = `${size}px`;
    this.c.width = Math.round(size * dpr);
    this.c.height = Math.round(size * dpr);
    // Draw in CSS pixels; the transform handles the density. Reset first, or resizing twice
    // would compound the scale.
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.bakedAt = null;      // the terrain is stretched to a new size; redraw it
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

  /**
   * Traders, labelled, tracked live.
   *
   * A town is a place you go TO do something — resupply, re-arm, sell what you dragged home —
   * and until now finding the person who does it meant walking laps of the enclosure reading
   * nameplates. They also drift: each villager walks a slow circuit, so a marker painted once
   * would send you where the smith USED to be. These are read fresh every frame, so the dot is
   * always where the person actually is.
   *
   * Only the ones who SELL get a marker. Labelling every resident would turn a town into a
   * wall of text and bury the three names that matter.
   */
  drawVendors(ctx, villagers, R, scale) {
    if (!villagers) return;
    ctx.font = "8px ui-monospace, monospace";
    ctx.textAlign = "center";
    const placed = [];
    for (const v of villagers.list) {
      if (!Villagers.sells(v)) continue;
      const m = this.toMap(v.x - player.x, v.z - player.z);
      if (Math.hypot(m.mx, m.my) > RANGE) continue;
      const px = R + m.mx * scale, py = R - m.my * scale;

      ctx.beginPath();
      ctx.arc(px, py, 2.6, 0, Math.PI * 2);
      ctx.fillStyle = "#5fe08a";
      ctx.fill();
      ctx.strokeStyle = "#0d3a22";
      ctx.lineWidth = 1;
      ctx.stroke();

      // A city holds two of each trade, and three names stacked on one spot is mush. If a
      // label would land on one already drawn, keep the dot and drop the word — the dot still
      // says "someone sells here", which is most of the value.
      const label = v.role.name;
      const w = ctx.measureText(label).width;
      const box = { x0: px - w / 2 - 1, x1: px + w / 2 + 1, y0: py - 13, y1: py - 4 };
      if (placed.some((b) => box.x0 < b.x1 && box.x1 > b.x0 && box.y0 < b.y1 && box.y1 > b.y0)) continue;
      placed.push(box);

      ctx.lineWidth = 2.5;
      ctx.strokeStyle = "rgba(6,18,12,0.85)";   // a dark outline, so it reads over pale terrain
      ctx.strokeText(label, px, py - 5);
      ctx.fillStyle = "#b8ffd2";
      ctx.fillText(label, px, py - 5);
    }
  }

  /**
   * The nearest settlement that will actually serve you.
   *
   * Today that is simply the closest one, because every town trades with everybody. When
   * factions land this is the ONE place that has to learn the difference — your own towns and
   * the neutral city yes, a rival's town no — and the arrow keeps meaning exactly what it
   * means now: that way to spend your points.
   */
  nearestTradePost() {
    let best = null, bd = 1e9, fallback = null, fd = 1e9;
    for (const s of sanctuariesNear(player.x, player.z, 900)) {
      const d = Math.hypot(s.x - player.x, s.z - player.z);
      if (d < fd) { fd = d; fallback = s; }
      if (!servesYou(s)) continue;
      if (d < bd) { bd = d; best = s; }
    }
    // Before you have picked a side nothing "serves you" but the cities, and very early on
    // there may be no city at all — so fall back to the nearest settlement rather than
    // leaving a new player with no arrow and no idea there are towns.
    return best || fallback;
  }

  /**
   * One compass marker: a diamond where the place is if it fits on the map, otherwise an
   * arrow pinned to the rim with the distance beside it. `placed` collects the label boxes so
   * two markers pointing the same way cannot print their words on top of each other — the
   * second keeps its arrow and drops its text, which still says "something is that way".
   */
  compass(ctx, R, scale, m, fill, edge, label, placed, shape = "diamond") {
    const d = Math.hypot(m.mx, m.my);
    const near = d <= RANGE - 10;
    const k = near ? 1 : (RANGE - 12) / (d || 1);
    const x = R + m.mx * scale * k, y = R - m.my * scale * k;

    ctx.save();
    ctx.translate(x, y);
    ctx.lineJoin = "round";
    if (near && shape === "dot") {
      // A DOT for a dungeon mouth. The diamond is the shape this map uses for "a place you
      // travel to"; a dungeon is a hole in the ground you stand on top of, and giving it its
      // own shape means the two never have to be told apart by colour alone — which matters
      // for anyone reading this map who does not separate green from orange easily.
      ctx.beginPath();
      ctx.arc(0, 0, 4.2, 0, Math.PI * 2);
      ctx.fillStyle = fill;
      ctx.fill();
      ctx.strokeStyle = edge;
      ctx.lineWidth = 1.6;
      ctx.stroke();
    } else if (near) {
      ctx.rotate(Math.PI / 4);
      ctx.fillStyle = fill;
      ctx.fillRect(-4, -4, 8, 8);
      ctx.strokeStyle = edge;
      ctx.lineWidth = 1.6;
      ctx.strokeRect(-4, -4, 8, 8);
    } else {
      ctx.rotate(Math.atan2(m.mx, m.my));
      ctx.beginPath();
      ctx.moveTo(0, -8);
      ctx.lineTo(6.5, 6);
      ctx.lineTo(-6.5, 6);
      ctx.closePath();
      ctx.fillStyle = fill;
      ctx.fill();
      ctx.strokeStyle = edge;
      ctx.lineWidth = 1.4;
      ctx.stroke();
    }
    ctx.restore();

    // The word, upright regardless of which way the arrow points — text that rotates with a
    // compass is a puzzle, not a label.
    const text = `${label} ${Math.round(d)}m`;
    ctx.font = "9px ui-monospace, monospace";
    ctx.textAlign = "center";
    const w = ctx.measureText(text).width;
    const ly = y + (y < R ? 17 : -12);
    // PULLED BACK INSIDE THE MAP. A rim arrow sits ON the edge, so a label centred under it
    // hangs half its width over the side — and everything here draws inside a circular clip,
    // which does not wrap the overflow, it deletes it. The longer the word the more of it
    // goes, which is why "dungeon" lost more of itself than "town" ever did. Slide the text
    // along until it fits; the arrow stays exactly where it was pointing.
    const tx = Math.max(w / 2 + 3, Math.min(R * 2 - w / 2 - 3, x));
    const box = { x0: tx - w / 2 - 2, x1: tx + w / 2 + 2, y0: ly - 9, y1: ly + 3 };
    if (placed.some((b) => box.x0 < b.x1 && box.x1 > b.x0 && box.y0 < b.y1 && box.y1 > b.y0)) return;
    placed.push(box);
    ctx.lineWidth = 2.5;
    ctx.strokeStyle = "rgba(8,12,18,0.85)";
    ctx.strokeText(text, tx, ly);
    ctx.fillStyle = fill;
    ctx.fillText(text, tx, ly);
  }

  draw(dt, mobs, boss, villagers) {
    const ctx = this.ctx, R = this.r;

    // THE THROTTLE ACTUALLY THROTTLES NOW. It used to read "moved OR the timer expired",
    // which let movement bypass the very limit the timer existed to impose — so sprinting
    // re-baked the whole heightfield several times a second, a steady stutter that looked
    // like a framerate problem. Re-baking is the single most expensive thing this file does
    // and it just got more expensive with the bigger map, so the gate has to hold: move far
    // enough AND wait long enough.
    this.bakeTimer -= dt;
    const moved = !this.bakedAt
      || Math.hypot(player.x - this.bakedAt.x, player.z - this.bakedAt.z) > REBAKE_DIST;
    if (moved && this.bakeTimer <= 0) {
      this.bakeTimer = REBAKE_TIME;
      this.bakeTerrain();
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
    const names = [];
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
      const flag = townFlag(s);
      ctx.fillStyle = flag.fill;
      ctx.fill();

      // HOW FAR UP. A sky town's footprint on a flat map is indistinguishable from a town on
      // the ground, so you navigate to it, arrive, and find nothing — it is two hundred blocks
      // over your head, and fog closes at about a hundred. The arrow is the whole fix: it says
      // which way to go once you have arrived.
      if (s.sky) {
        const [cx0, cy0] = pt(s.x, s.z);
        const up = s.plateau + 1 - player.y;
        if (Math.abs(up) > 8) {
          ctx.fillStyle = flag.wall;
          ctx.font = "bold 11px ui-monospace, monospace";
          ctx.textAlign = "center";
          ctx.fillText(up > 0 ? "▲" : "▼", cx0, cy0 + 4);
        } else {
          // You are level with it — that is the moment it stops being a puzzle.
          ctx.strokeStyle = flag.wall;
          ctx.lineWidth = 1.2;
          ctx.beginPath();
          ctx.arc(cx0, cy0, 5, 0, Math.PI * 2);
          ctx.stroke();
        }
      }

      // Outline drawn edge by edge with the gate arc LEFT OUT, so the opening reads as a
      // gap in the wall rather than needing a legend to explain it.
      ctx.strokeStyle = flag.wall;
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

      // AND MARK IT, BIG AND BLUE. This is the single most navigationally useful point on the
      // whole map — a town's wall is unbroken except here, so arriving anywhere else means
      // walking the perimeter until you find the way in. At 3.4px in amber it was smaller than
      // a vendor dot and the same family of colour as the town fill it sat on, so it read as
      // decoration on the outline rather than as the one thing you were looking for.
      //
      // Blue because nothing else on this map is: the factions own red, orange and green, the
      // dungeon arrow is green, vendors are green, and a colour already spoken for cannot mean
      // "door". Ringed in white so it holds against a green town, a red camp or bare terrain
      // alike — the mark has to survive whatever it happens to be drawn on top of.
      const gr = boundaryAt(s, s.gate);
      const [gx, gy] = pt(Math.cos(s.gate) * gr, Math.sin(s.gate) * gr);
      ctx.beginPath();
      ctx.arc(gx, gy, 8, 0, Math.PI * 2);
      ctx.fillStyle = "#3aa2ff";
      ctx.fill();
      ctx.strokeStyle = "#eaf4ff";
      ctx.lineWidth = 2;
      ctx.stroke();
      // A darker core, so the disc still reads as a RING at a glance rather than a blob —
      // shape carries as far as colour does, and further for anyone who separates hues poorly.
      ctx.beginPath();
      ctx.arc(gx, gy, 3, 0, Math.PI * 2);
      ctx.fillStyle = "#0b2f57";
      ctx.fill();

      // The name is DEFERRED, not drawn here — a garrison stands in the middle of its own
      // town, so writing the name now would put it under fifteen mob dots. Same rule the
      // trader labels already follow: words go on top of markers, never under them.
      const [cx, cy] = pt(0, 0);
      if (Math.hypot(cx - R, cy - R) < R - 12) names.push({ cx, cy, flag });
    }

    // Mobs — red for a threat, GOLD for an elite, GREEN for your own army (an ally).
    for (const e of mobs.entities()) {
      const m = this.toMap(e.x - player.x, e.z - player.z);
      if (Math.hypot(m.mx, m.my) > RANGE) continue;
      const ally = isMyAlly(e.faction);
      ctx.beginPath();
      ctx.arc(R + m.mx * scale, R - m.my * scale, e.elite ? 3.8 : 2.6, 0, Math.PI * 2);
      ctx.fillStyle = ally ? "#5fe08a" : e.elite ? "#ffd24a" : "#ff6b6b";
      ctx.fill();
    }

    // Camp names, over the dots. Whose camp it is survives the garrison standing on top of it.
    ctx.font = "bold 10px ui-monospace, monospace";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.lineWidth = 2.5;
    ctx.lineJoin = "round";
    for (const n of names) {
      ctx.strokeStyle = "rgba(8,12,18,0.9)";
      ctx.strokeText(n.flag.name, n.cx, n.cy);
      ctx.fillStyle = n.flag.wall;
      ctx.fillText(n.flag.name, n.cx, n.cy);
    }
    ctx.textBaseline = "alphabetic";   // the compass and vendor labels assume the default


    // Traders, on top of the dots so a label is never buried under a mob marker.
    this.drawVendors(ctx, villagers, R, scale);

    // Boss — always shown, clamped to the rim if it's beyond range.
    if (boss.active) {
      const m = this.toMap(boss.alive.x - player.x, boss.alive.z - player.z);
      const d = Math.hypot(m.mx, m.my) || 1;
      const cl = Math.min(1, (RANGE - 6) / d);
      ctx.beginPath();
      ctx.arc(R + m.mx * scale * cl, R - m.my * scale * cl, 6, 0, Math.PI * 2);
      ctx.fillStyle = "#ff2d2d";
      ctx.fill();
      ctx.strokeStyle = "#ffffffcc";
      ctx.stroke();
    }

    // THE COMPASSES. Blue points at somewhere that will trade with you; grey points home.
    //
    // Only things you would actually TRAVEL to earn a place on the rim — the boss above, and
    // these two. That is a rule worth holding: four arrows stop being something you glance at
    // and become something you decode, and the whole point of this map is the glance.
    const placed = [];
    // THE WAY UNDERGROUND GOES FIRST, and the order is the whole point: when two markers
    // point the same way the SECOND one silently drops its word and keeps only its arrow.
    // Drawn after the town, a gate in roughly the town's direction became a green arrow with
    // nothing written on it — the one marker on this map whose shape you have no other way to
    // read. Town and spawn can afford to lose a label; you can find a town by walking at it,
    // and spawn is written in the rings. A dungeon is a specific hole in a specific hillside.
    const gate = inDungeon() ? null : nearestGate(player.x, player.z);
    if (gate) {
      const g = this.toMap(gate.x - player.x, gate.z - player.z);
      this.compass(ctx, R, scale, g, "#3ddc84", "#0a3b21", "dungeon", placed, "dot");
    }
    const nearestTown = this.nearestTradePost();
    if (nearestTown) {
      const t = this.toMap(nearestTown.x - player.x, nearestTown.z - player.z);
      this.compass(ctx, R, scale, t, "#4ea8ff", "#08243f", "town", placed);
    }
    // Spawn is not really a destination any more, but which way is SHALLOW is worth knowing
    // when you are hurt and deep, so it keeps an arrow — in grey, so blue reads as the one
    // you are probably heading for.
    this.compass(ctx, R, scale, origin, "#c3ccd9", "#23282f", "spawn", placed);

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
