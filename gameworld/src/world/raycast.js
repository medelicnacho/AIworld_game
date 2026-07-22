// Voxel raycast — Amanatides & Woo grid traversal.
//
// Steps cell-by-cell along the ray instead of sampling at fixed intervals, so it can never
// tunnel through a block, and cost scales with distance travelled rather than precision
// wanted. This is what hitscan fire, and later line-of-sight checks, both ride on.

import { solidAt } from "./gen.js";

const EPS = 1e-8;

/**
 * @returns {{hit:boolean, x:number, y:number, z:number, px:number, py:number, pz:number,
 *            nx:number, ny:number, nz:number, dist:number}}
 *   Voxel coords of the block struck, the exact impact point (px,py,pz), the face normal
 *   (nx,ny,nz), and the distance. hit=false means the ray reached maxDist through open air.
 */
export function raycastVoxel(ox, oy, oz, dx, dy, dz, maxDist = 256) {
  let x = Math.floor(ox), y = Math.floor(oy), z = Math.floor(oz);

  const stepX = dx > 0 ? 1 : -1, stepY = dy > 0 ? 1 : -1, stepZ = dz > 0 ? 1 : -1;
  const tDeltaX = Math.abs(1 / (Math.abs(dx) < EPS ? EPS : dx));
  const tDeltaY = Math.abs(1 / (Math.abs(dy) < EPS ? EPS : dy));
  const tDeltaZ = Math.abs(1 / (Math.abs(dz) < EPS ? EPS : dz));

  // Distance along the ray to the first grid boundary on each axis.
  const bx = dx > 0 ? x + 1 - ox : ox - x;
  const by = dy > 0 ? y + 1 - oy : oy - y;
  const bz = dz > 0 ? z + 1 - oz : oz - z;
  let tMaxX = tDeltaX * bx, tMaxY = tDeltaY * by, tMaxZ = tDeltaZ * bz;

  let nx = 0, ny = 0, nz = 0, t = 0;

  // Firing from inside a block (spawned in terrain, muzzle clipped) — report immediately
  // rather than shooting out through the world.
  if (solidAt(x, y, z)) {
    return { hit: true, x, y, z, px: ox, py: oy, pz: oz, nx: 0, ny: 1, nz: 0, dist: 0 };
  }

  while (t <= maxDist) {
    if (tMaxX < tMaxY && tMaxX < tMaxZ) {
      x += stepX; t = tMaxX; tMaxX += tDeltaX;
      nx = -stepX; ny = 0; nz = 0;
    } else if (tMaxY < tMaxZ) {
      y += stepY; t = tMaxY; tMaxY += tDeltaY;
      nx = 0; ny = -stepY; nz = 0;
    } else {
      z += stepZ; t = tMaxZ; tMaxZ += tDeltaZ;
      nx = 0; ny = 0; nz = -stepZ;
    }
    if (t > maxDist) break;
    if (solidAt(x, y, z)) {
      return {
        hit: true, x, y, z,
        px: ox + dx * t, py: oy + dy * t, pz: oz + dz * t,
        nx, ny, nz, dist: t,
      };
    }
  }
  return {
    hit: false, x, y, z,
    px: ox + dx * maxDist, py: oy + dy * maxDist, pz: oz + dz * maxDist,
    nx: 0, ny: 0, nz: 0, dist: maxDist,
  };
}
