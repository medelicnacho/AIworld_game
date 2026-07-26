// Chunk streaming: keep a disc of chunks loaded around the player, build a couple per frame,
// drop the ones that fall out of range.
//
// Read-only terrain (D1) makes this the easy half of a voxel engine: nothing is ever dirty,
// so unloading is just disposal — there is no save path, no delta store, no re-mesh on edit.

import * as THREE from "three";
import { CHUNK_X, CHUNK_Y, CHUNK_Z, VIEW_RADIUS, CHUNKS_PER_FRAME, WINDOW_STEP } from "../config.js";
import { fillChunk } from "./gen.js";
import { buildChunkGeometry } from "./mesher.js";

const key = (cx, cz) => `${cx},${cz}`;

export class ChunkStreamer {
  constructor(scene) {
    this.scene = scene;
    this.loaded = new Map();     // key -> { mesh, cx, cz }
    this.material = new THREE.MeshLambertMaterial({ vertexColors: true });
    this.built = 0;
    // The world Y this chunk-window sits at. The world is unbounded upward — this is the
    // slice of it that is resident, and it follows you.
    this.oy = 0;
  }

  /**
   * Where the window should sit for a body at this height.
   *
   * Centred a little low rather than exactly: you look DOWN more than up while climbing, and
   * whatever you leave behind at the bottom was past the fog anyway (which closes at about
   * 106 blocks, well inside a 256-tall window). Snapped to WINDOW_STEP so it changes rarely,
   * and floored at zero so standing on the ground always loads the ground.
   */
  windowFor(y) {
    return Math.max(0, Math.floor((y - CHUNK_Y * 0.45) / WINDOW_STEP) * WINDOW_STEP);
  }

  chunkOf(x, z) {
    return [Math.floor(x / CHUNK_X), Math.floor(z / CHUNK_Z)];
  }

  update(playerX, playerZ, playerY = 0) {
    const [pcx, pcz] = this.chunkOf(playerX, playerZ);

    // CLIMBED OUT OF THE WINDOW. Everything resident is now the wrong slice of world, so it
    // all has to be rebuilt — but the old meshes are left standing until their replacements
    // exist, and the rebuild runs nearest-first on the same per-frame budget as ordinary
    // streaming. What you see change is therefore the far edge, which the fog has already
    // taken. Rare by design: WINDOW_STEP is half the window.
    const want = this.windowFor(playerY);
    if (want !== this.oy) {
      this.oy = want;
      this.stale = new Set(this.loaded.keys());
    }

    // Build the nearest missing chunks first, within a frame budget — streaming should
    // cost a steady few ms, never a hitch.
    const wanted = [];
    for (let dz = -VIEW_RADIUS; dz <= VIEW_RADIUS; dz++) {
      for (let dx = -VIEW_RADIUS; dx <= VIEW_RADIUS; dx++) {
        const d2 = dx * dx + dz * dz;
        if (d2 > VIEW_RADIUS * VIEW_RADIUS) continue;
        const cx = pcx + dx, cz = pcz + dz;
        const k = key(cx, cz);
        if (!this.loaded.has(k) || this.stale?.has(k)) wanted.push({ cx, cz, d2 });
      }
    }
    wanted.sort((a, b) => a.d2 - b.d2);
    for (let i = 0; i < Math.min(CHUNKS_PER_FRAME, wanted.length); i++) {
      this.build(wanted[i].cx, wanted[i].cz);
    }
    if (this.stale && this.stale.size === 0) this.stale = null;

    // Drop chunks past the edge (with hysteresis, so walking a boundary doesn't thrash).
    const dropAt = (VIEW_RADIUS + 1.5) ** 2;
    for (const [k, entry] of this.loaded) {
      const dx = entry.cx - pcx, dz = entry.cz - pcz;
      if (dx * dx + dz * dz > dropAt) {
        this.scene.remove(entry.mesh);
        entry.mesh.geometry.dispose();
        this.loaded.delete(k);
      }
    }
  }

  build(cx, cz) {
    const k = key(cx, cz);
    const geom = buildChunkGeometry(fillChunk(cx, cz, this.oy));
    const mesh = new THREE.Mesh(geom, this.material);
    mesh.matrixAutoUpdate = false;      // chunks never move
    mesh.updateMatrix();
    this.scene.add(mesh);
    // Swap, never gap: the old slice stays on screen until this one is ready to replace it.
    const old = this.loaded.get(k);
    if (old) { this.scene.remove(old.mesh); old.mesh.geometry.dispose(); }
    this.loaded.set(k, { mesh, cx, cz });
    this.stale?.delete(k);
    this.built++;
  }
}
