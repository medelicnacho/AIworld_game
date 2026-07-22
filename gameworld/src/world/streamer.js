// Chunk streaming: keep a disc of chunks loaded around the player, build a couple per frame,
// drop the ones that fall out of range.
//
// Read-only terrain (D1) makes this the easy half of a voxel engine: nothing is ever dirty,
// so unloading is just disposal — there is no save path, no delta store, no re-mesh on edit.

import * as THREE from "three";
import { CHUNK_X, CHUNK_Z, VIEW_RADIUS, CHUNKS_PER_FRAME } from "../config.js";
import { fillChunk } from "./gen.js";
import { buildChunkGeometry } from "./mesher.js";

const key = (cx, cz) => `${cx},${cz}`;

export class ChunkStreamer {
  constructor(scene) {
    this.scene = scene;
    this.loaded = new Map();     // key -> { mesh, cx, cz }
    this.material = new THREE.MeshLambertMaterial({ vertexColors: true });
    this.built = 0;
  }

  chunkOf(x, z) {
    return [Math.floor(x / CHUNK_X), Math.floor(z / CHUNK_Z)];
  }

  update(playerX, playerZ) {
    const [pcx, pcz] = this.chunkOf(playerX, playerZ);

    // Build the nearest missing chunks first, within a frame budget — streaming should
    // cost a steady few ms, never a hitch.
    const wanted = [];
    for (let dz = -VIEW_RADIUS; dz <= VIEW_RADIUS; dz++) {
      for (let dx = -VIEW_RADIUS; dx <= VIEW_RADIUS; dx++) {
        const d2 = dx * dx + dz * dz;
        if (d2 > VIEW_RADIUS * VIEW_RADIUS) continue;
        const cx = pcx + dx, cz = pcz + dz;
        if (!this.loaded.has(key(cx, cz))) wanted.push({ cx, cz, d2 });
      }
    }
    wanted.sort((a, b) => a.d2 - b.d2);
    for (let i = 0; i < Math.min(CHUNKS_PER_FRAME, wanted.length); i++) {
      this.build(wanted[i].cx, wanted[i].cz);
    }

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
    const geom = buildChunkGeometry(fillChunk(cx, cz));
    const mesh = new THREE.Mesh(geom, this.material);
    mesh.matrixAutoUpdate = false;      // chunks never move
    mesh.updateMatrix();
    this.scene.add(mesh);
    this.loaded.set(key(cx, cz), { mesh, cx, cz });
    this.built++;
  }
}
