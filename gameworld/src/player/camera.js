// D3/D4/D5 — the camera state machine.
//
//   EXPLORE  third-person over-shoulder. Default: you see your body, your gear, your
//            companion, and a boss's full silhouette (D3).
//   AIM      hold RMB -> BLENDS to first person over ~170ms. This is the fix for steep
//            upward aim: over-shoulder free-aim upward clips the camera into terrain and
//            runs the reticle off screen, so BOTW/TOTK pull to FP on draw. A blend, never
//            a cut — the cut is what makes people motion-sick.
//   FP       F5 sticky toggle, for players who just prefer it.
//
// D5: aiming is ONE raycast from the camera through the crosshair in every state. The
// states differ by camera offset and (later) cone width — never by a second shooting path.

import * as THREE from "three";
import { CAMERA } from "../config.js";
import { player } from "../state.js";
import { solidAt } from "../world/gen.js";

export class CameraRig {
  constructor(camera) {
    this.camera = camera;
    this.stickyFP = false;
    this.blend = 0;            // 0 = third person, 1 = first person
    this.forward = new THREE.Vector3();
  }

  toggle() { this.stickyFP = !this.stickyFP; }

  get mode() {
    if (this.stickyFP) return "FP";
    return this.blend > 0.5 ? "AIM" : "EXPLORE";
  }

  update(dt, aiming) {
    const target = aiming || this.stickyFP ? 1 : 0;
    const rate = dt / CAMERA.aimBlendTime;
    this.blend += Math.max(-rate, Math.min(rate, target - this.blend));
    this.blend = Math.max(0, Math.min(1, this.blend));

    const eased = this.blend * this.blend * (3 - 2 * this.blend);   // smoothstep

    const cp = Math.cos(player.pitch), sp = Math.sin(player.pitch);
    const cy = Math.cos(player.yaw), sy = Math.sin(player.yaw);
    this.forward.set(-sy * cp, sp, -cy * cp).normalize();

    // The head: where the eye sits in first person, and what the third-person camera orbits.
    const hx = player.x, hy = player.y + CAMERA.height, hz = player.z;

    // Third-person anchor: back along the view ray, offset over the shoulder.
    const dist = CAMERA.thirdPersonDist * (1 - eased);
    const shoulder = CAMERA.shoulder * (1 - eased);
    // Right vector = normalize(cross(forward, up)) on the yaw plane. At yaw 0 the forward
    // is -Z, so right must be +X: (cos yaw, 0, -sin yaw). The old (-cy, sy) was its
    // negation, which put the camera over the LEFT shoulder.
    const rx = cy, rz = -sy;

    let px = hx - this.forward.x * dist + rx * shoulder;
    let py = hy - this.forward.y * dist;
    let pz = hz - this.forward.z * dist + rz * shoulder;

    // Camera obstruction: march from the head to the desired spot and stop short of terrain,
    // so backing into a hillside pulls the camera in instead of putting you inside the world.
    if (dist > 0.01) {
      const steps = 8;
      for (let i = 1; i <= steps; i++) {
        const t = i / steps;
        const sx = hx + (px - hx) * t, sy2 = hy + (py - hy) * t, sz = hz + (pz - hz) * t;
        if (solidAt(sx, sy2, sz)) {
          const back = (i - 1) / steps * 0.9;
          px = hx + (px - hx) * back;
          py = hy + (py - hy) * back;
          pz = hz + (pz - hz) * back;
          break;
        }
      }
    }

    this.camera.position.set(px, py, pz);
    // Orientation is yaw/pitch DIRECTLY — never lookAt(head + forward). Aiming at a point
    // one unit ahead of the head toes an offset camera sharply inward, which skews the
    // view and makes everything sit at an angle. Offsets move the camera's POSITION; they
    // must never rotate it. This also makes D5 exact: the crosshair ray IS camera-forward.
    this.camera.rotation.set(player.pitch, player.yaw, 0, "YXZ");

    const fov = CAMERA.fov + (CAMERA.aimFov - CAMERA.fov) * eased;
    if (Math.abs(this.camera.fov - fov) > 0.01) {
      this.camera.fov = fov;
      this.camera.updateProjectionMatrix();
    }
  }
}
