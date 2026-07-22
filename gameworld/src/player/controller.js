// Input + player physics. Runs on a fixed step so movement feel never depends on framerate.
//
// Collision is AABB-vs-voxel, resolved one axis at a time — the standard trick that lets you
// slide along a wall instead of sticking to it. It samples the world function directly, so
// there is no collider to build, bake, or keep in sync with the mesh.

import { PLAYER, CAMERA } from "../config.js";
import { player } from "../state.js";
import { solidAt } from "../world/gen.js";

export const input = {
  fwd: 0, right: 0, jump: false, sprint: false, aim: false,
};

const LOOK_KEY = "gw.look";

export function attachInput(canvas, hooks = {}) {
  // Live-tuned look speed survives a reload — otherwise every refresh throws away the
  // feel you just dialled in, and vite reloads on every save.
  const saved = Number(localStorage.getItem(LOOK_KEY));
  if (saved > 0) CAMERA.sensitivity = saved;

  const keys = new Set();
  const refresh = () => {
    input.fwd = (keys.has("KeyW") ? 1 : 0) - (keys.has("KeyS") ? 1 : 0);
    input.right = (keys.has("KeyD") ? 1 : 0) - (keys.has("KeyA") ? 1 : 0);
    input.jump = keys.has("Space");
    input.sprint = keys.has("ShiftLeft") || keys.has("ShiftRight");
  };

  window.addEventListener("keydown", (e) => {
    if (e.code === "F5") { e.preventDefault(); hooks.toggleCamera?.(); return; }
    if (e.code === "KeyM") { hooks.toggleMusic?.(); return; }
    // Live look-speed tuning: 20% per press, clamped to a sane band.
    if (e.code === "BracketLeft" || e.code === "BracketRight") {
      const f = e.code === "BracketRight" ? 1.2 : 1 / 1.2;
      CAMERA.sensitivity = Math.max(0.0005, Math.min(0.05, CAMERA.sensitivity * f));
      localStorage.setItem(LOOK_KEY, String(CAMERA.sensitivity));
      return;
    }
    keys.add(e.code);
    refresh();
  });
  window.addEventListener("keyup", (e) => { keys.delete(e.code); refresh(); });
  window.addEventListener("blur", () => { keys.clear(); refresh(); });

  canvas.addEventListener("click", () => canvas.requestPointerLock());
  document.addEventListener("pointerlockchange", () => {
    const locked = document.pointerLockElement === canvas;
    document.body.classList.toggle("locked", locked);
    if (locked) hooks.onLock?.();
  });

  document.addEventListener("mousemove", (e) => {
    if (document.pointerLockElement !== canvas) return;
    player.yaw -= e.movementX * CAMERA.sensitivity;
    player.pitch -= e.movementY * CAMERA.sensitivity;
    player.pitch = Math.max(CAMERA.minPitch, Math.min(CAMERA.maxPitch, player.pitch));
  });

  // D4: hold to aim. The camera blends toward first person; releasing blends back.
  document.addEventListener("mousedown", (e) => { if (e.button === 2) input.aim = true; });
  document.addEventListener("mouseup", (e) => { if (e.button === 2) input.aim = false; });
  window.addEventListener("contextmenu", (e) => e.preventDefault());
}

/** Is the player's capsule blocked at this position? Sampled as a voxel-span AABB test. */
function blocked(x, y, z) {
  const r = PLAYER.radius;
  const y0 = Math.floor(y), y1 = Math.floor(y + PLAYER.height - 0.001);
  for (let vy = y0; vy <= y1; vy++) {
    for (let vz = Math.floor(z - r); vz <= Math.floor(z + r); vz++) {
      for (let vx = Math.floor(x - r); vx <= Math.floor(x + r); vx++) {
        if (solidAt(vx, vy, vz)) return true;
      }
    }
  }
  return false;
}

export function stepPlayer(dt) {
  const speed = input.sprint && !input.aim ? PLAYER.sprintSpeed : PLAYER.walkSpeed;

  // Desired horizontal velocity in the yaw frame.
  const sin = Math.sin(player.yaw), cos = Math.cos(player.yaw);
  let dx = -sin * input.fwd + cos * input.right;
  let dz = -cos * input.fwd - sin * input.right;
  const len = Math.hypot(dx, dz);
  if (len > 0) { dx /= len; dz /= len; }

  const targetVx = dx * speed, targetVz = dz * speed;
  const blend = 1 - Math.exp(-(len > 0 ? PLAYER.accel : PLAYER.friction) * dt);
  player.vx += (targetVx - player.vx) * blend;
  player.vz += (targetVz - player.vz) * blend;

  player.vy = Math.max(PLAYER.maxFall, player.vy + PLAYER.gravity * dt);
  if (input.jump && player.onGround) {
    player.vy = PLAYER.jumpSpeed;
    player.onGround = false;
  }

  // Axis-separated resolution: try each move independently so a blocked X still allows Z.
  const nx = player.x + player.vx * dt;
  if (!blocked(nx, player.y, player.z)) player.x = nx; else player.vx = 0;

  const nz = player.z + player.vz * dt;
  if (!blocked(player.x, player.y, nz)) player.z = nz; else player.vz = 0;

  const ny = player.y + player.vy * dt;
  if (!blocked(player.x, ny, player.z)) {
    player.y = ny;
    player.onGround = false;
  } else {
    if (player.vy < 0) {
      player.onGround = true;
      player.y = Math.floor(player.y) + 0.0001;   // settle onto the block top
    }
    player.vy = 0;
  }

  player.sprinting = input.sprint && len > 0;
}
