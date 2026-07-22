// Turns a chunk's occupancy grid into a mesh: emit a quad wherever a solid voxel touches air.
//
// Face-culled, not greedy-merged. Greedy meshing is the known optimisation (it collapses
// runs of coplanar faces) and it drops in later behind this same interface — but it is an
// optimisation, and M1's gate is "is it fun", not "is it optimal". Measure first.

import * as THREE from "three";
import { CHUNK_X, CHUNK_Y, CHUNK_Z, RINGS } from "../config.js";
import { AIR, BLOCK_COLOR, blockAt, idx, ringAt } from "./gen.js";

// +x, -x, +y, -y, +z, -z : normal, the 4 corner offsets of the quad, and a shade term.
// The shade is the whole lighting model — top faces bright, sides mid, bottom dark. It is
// what makes flat-shaded cubes read as terrain instead of a solid blob.
const FACES = [
  { n: [1, 0, 0],  v: [[1,0,0],[1,1,0],[1,1,1],[1,0,1]], shade: 0.80 },
  { n: [-1, 0, 0], v: [[0,0,1],[0,1,1],[0,1,0],[0,0,0]], shade: 0.72 },
  { n: [0, 1, 0],  v: [[0,1,0],[0,1,1],[1,1,1],[1,1,0]], shade: 1.00 },
  { n: [0, -1, 0], v: [[0,0,1],[0,0,0],[1,0,0],[1,0,1]], shade: 0.55 },
  { n: [0, 0, 1],  v: [[1,0,1],[1,1,1],[0,1,1],[0,0,1]], shade: 0.88 },
  { n: [0, 0, -1], v: [[0,0,0],[0,1,0],[1,1,0],[1,0,0]], shade: 0.64 },
];

export function buildChunkGeometry(chunk) {
  const { blocks, ox, oz } = chunk;
  const pos = [], nor = [], col = [];

  // Ring tint is applied at mesh time so difficulty is VISIBLE from a distance (D8) —
  // one band per ring, readable before anything in it tries to kill you.
  const tint = RINGS[ringAt(ox + CHUNK_X / 2, oz + CHUNK_Z / 2)].tint;

  for (let y = 0; y < CHUNK_Y; y++) {
    for (let z = 0; z < CHUNK_Z; z++) {
      for (let x = 0; x < CHUNK_X; x++) {
        const id = blocks[idx(x, y, z)];
        if (id === AIR) continue;
        const base = BLOCK_COLOR[id];

        for (const f of FACES) {
          const nx = x + f.n[0], ny = y + f.n[1], nz = z + f.n[2];
          // In-bounds neighbours read the grid; out-of-bounds ones re-derive from the
          // world function. Because terrain is pure (D1), chunk meshing needs NO
          // cross-chunk coordination and no neighbour-ready bookkeeping at all.
          const occluded =
            nx >= 0 && nx < CHUNK_X && ny >= 0 && ny < CHUNK_Y && nz >= 0 && nz < CHUNK_Z
              ? blocks[idx(nx, ny, nz)] !== AIR
              : blockAt(ox + nx, ny, oz + nz) !== AIR;
          if (occluded) continue;

          const s = f.shade;
          const r = base[0] * s * tint[0], g = base[1] * s * tint[1], b = base[2] * s * tint[2];
          const [a, bb, c, d] = f.v;
          for (const [vx, vy, vz] of [a, bb, c, a, c, d]) {   // two triangles
            pos.push(x + vx, y + vy, z + vz);
            nor.push(f.n[0], f.n[1], f.n[2]);
            col.push(r, g, b);
          }
        }
      }
    }
  }

  const geom = new THREE.BufferGeometry();
  geom.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  geom.setAttribute("normal", new THREE.Float32BufferAttribute(nor, 3));
  geom.setAttribute("color", new THREE.Float32BufferAttribute(col, 3));
  geom.translate(ox, 0, oz);
  geom.computeBoundingSphere();
  return geom;
}
