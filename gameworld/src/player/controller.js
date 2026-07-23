// Input + player physics. Runs on a fixed step so movement feel never depends on framerate.
//
// Collision is AABB-vs-voxel, resolved one axis at a time — the standard trick that lets you
// slide along a wall instead of sticking to it. It samples the world function directly, so
// there is no collider to build, bake, or keep in sync with the mesh.

import { PLAYER, CAMERA, DODGE, DASH, WHIRL, ABILITY, SPRINT } from "../config.js";
import { player } from "../state.js";
import { solidAt } from "../world/gen.js";
import { wallBlocks } from "../world/sanctuary.js";

// Which keyboard code maps to which spell-bar slot index. Matches abilities.SLOT_KEYS order.
const SLOT_CODE = {
  Digit1: 0, Digit2: 1, Digit3: 2, Digit4: 3, Digit5: 4, Digit6: 5, KeyT: 6, Backquote: 7,
};

export const input = {
  fwd: 0, right: 0, sprint: false, firing: false,
  // aimHeld is the PHYSICAL button; `aim` is derived each step. Writing to `aim` directly
  // (as the dodge used to) desyncs it from the mouse — you hold RMB and nothing happens
  // until you release and press again.
  aimHeld: false, aim: false,
  // Dodge is double-tap-a-direction, so the queued roll remembers WHICH key fired it —
  // you roll the way you tapped, not the way you happen to be steering a frame later.
  dodgeQueued: false, dodgeFwd: 0, dodgeRight: 0, throwQueued: false, healQueued: false,
  // Jump is EDGE-triggered, not held: one press = one jump. A held-key check would let you
  // bunny-hop forever by leaning on space, and would burn both air jumps in a single frame.
  jumpQueued: false,
};

const LOOK_KEY = "gw.look";

// [forward, right] per movement key — the frame a dodge direction is built in.
const MOVE_DIRS = {
  KeyW: [1, 0], KeyS: [-1, 0], KeyA: [0, -1], KeyD: [0, 1],
};
const lastTap = {};

export function attachInput(canvas, hooks = {}) {
  // Live-tuned look speed survives a reload — otherwise every refresh throws away the
  // feel you just dialled in, and vite reloads on every save.
  const saved = Number(localStorage.getItem(LOOK_KEY));
  if (saved > 0) CAMERA.sensitivity = saved;

  const keys = new Set();
  const refresh = () => {
    input.fwd = (keys.has("KeyW") ? 1 : 0) - (keys.has("KeyS") ? 1 : 0);
    input.right = (keys.has("KeyD") ? 1 : 0) - (keys.has("KeyA") ? 1 : 0);
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
    // !e.repeat: the OS fires keydown repeatedly while a key is held — without this, one
    // long press would queue a jump every few milliseconds.
    if (e.code === "Space" && !e.repeat) input.jumpQueued = true;
    if (e.code === "KeyR") hooks.reload?.();
    if (e.code === "KeyF" && !e.repeat) hooks.interact?.();
    if (e.code === "KeyC" && !e.repeat) hooks.drink?.();
    // General abilities keep their own keys, exactly as before — they are not items.
    if (e.code === "KeyE" && !e.repeat) input.throwQueued = true;
    if (e.code === "KeyQ" && !e.repeat) input.healQueued = true;
    // The spell bar: 1-6, then T and ` for slots 7-8. R and F are left alone (reload, trade).
    if (!e.repeat) {
      const slot = SLOT_CODE[e.code];
      if (slot !== undefined) hooks.ability?.(slot);
    }
    if (e.code === "KeyG" && !e.repeat) hooks.bridgeTest?.();   // dev: speak a line

    // Double-tap a movement key to roll that way. Timestamps are per-key, so tapping
    // W then D reads as two separate first-taps rather than a double-tap.
    const move = MOVE_DIRS[e.code];
    if (move && !e.repeat) {
      const t = performance.now();
      if (t - (lastTap[e.code] || 0) < DODGE.doubleTapMs) {
        input.dodgeQueued = true;
        input.dodgeFwd = move[0];
        input.dodgeRight = move[1];
        lastTap[e.code] = 0;      // consumed — a third tap starts a fresh pair
      } else {
        lastTap[e.code] = t;
      }
    }
    keys.add(e.code);
    refresh();
  });
  window.addEventListener("keyup", (e) => { keys.delete(e.code); refresh(); });
  // Drop held keys ONLY once we have genuinely stopped receiving input. While pointer lock
  // is active we are still getting events, so clearing would be a lie about what's held.
  //
  // This is the bug behind "strafe dies after aiming". Right-click can fire a spurious blur
  // even while locked, which wiped the key set — and Linux gives key-repeat to the MOST
  // RECENT key only, so a still-held D then sends nothing further and never returns to the
  // set. W worked because you had just pressed it. Hence: sideways stops working until you
  // go forward. Clearing state you cannot rebuild is only safe once input has really ended.
  const release = () => {
    if (document.pointerLockElement === canvas) return;   // still playing — keep the keys
    keys.clear();
    refresh();
  };
  window.addEventListener("blur", release);
  document.addEventListener("visibilitychange", () => { if (document.hidden) release(); });

  canvas.addEventListener("click", () => canvas.requestPointerLock());
  document.addEventListener("pointerlockchange", () => {
    const locked = document.pointerLockElement === canvas;
    document.body.classList.toggle("locked", locked);
    // Escape is reserved by the browser for releasing pointer lock, so a keydown never
    // reliably arrives — losing the lock IS the pause signal, and it also covers
    // alt-tabbing away, which should pause for the same reason.
    if (locked) {
      hooks.onLock?.();
    } else {
      // Clear on UNLOCK only. Clearing as we regain lock would wipe a key you were already
      // holding, and Linux key-repeat never re-announces it — the same bug in a new place.
      keys.clear();
      refresh();
      hooks.onUnlock?.();
    }
  });

  document.addEventListener("mousemove", (e) => {
    // movementX/Y are delivered on ORDINARY mousemove too, not only under pointer lock —
    // so look control does not have to wait for the lock to come back. That matters after
    // Escape closes a vendor: Chrome refuses to re-lock for ~1.25s, and a game that runs
    // but will not turn its head reads as "still paused" even though it isn't.
    if (document.pointerLockElement !== canvas && !hooks.lookUnlocked?.()) return;
    player.yaw -= e.movementX * CAMERA.sensitivity;
    player.pitch -= e.movementY * CAMERA.sensitivity;
    player.pitch = Math.max(CAMERA.minPitch, Math.min(CAMERA.maxPitch, player.pitch));
  });

  // D4: hold RMB to aim (camera blends toward first person), hold LMB to fire.
  document.addEventListener("mousedown", (e) => {
    if (document.pointerLockElement !== canvas) return;
    // Keep the right button from triggering any browser/OS focus behaviour at all — the
    // blur it can provoke is what started this whole class of bug.
    if (e.button === 2) e.preventDefault();
    if (e.button === 2) input.aimHeld = true;
    if (e.button === 0) input.firing = true;
  });
  document.addEventListener("mouseup", (e) => {
    if (e.button === 2) input.aimHeld = false;
    if (e.button === 0) input.firing = false;
  });
  // Mouse wheel cycles owned weapons — the FPS convention, and the only free input left.
  document.addEventListener("wheel", (e) => {
    if (document.pointerLockElement !== canvas) return;
    hooks.cycleWeapon?.(e.deltaY > 0 ? 1 : -1);
  }, { passive: true });
  window.addEventListener("contextmenu", (e) => e.preventDefault());
}

/** Is the player's capsule blocked at this position? Sampled as a voxel-span AABB test. */
function blocked(x, y, z) {
  // The wall is an analytic ring, not voxels — so it's a maths test, and the collision can
  // never disagree with what's drawn. The gate is a gap: you walk in and out freely.
  if (wallBlocks(x, z)) return true;
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
  // Derived, every step: held AND not mid-roll.
  input.aim = input.aimHeld && player.dodgeT <= 0;
  if (player.sprintT > 0) player.sprintT -= dt;
  const speed = (input.sprint && !input.aim ? PLAYER.sprintSpeed : PLAYER.walkSpeed)
    * player.speedMult * (player.surgeT > 0 ? ABILITY.surgeSpeed : 1)
    * (player.sprintT > 0 ? SPRINT.mult : 1)
    * (player.whirlT > 0 ? WHIRL.spinSpeed : 1);

  // Desired horizontal velocity in the yaw frame.
  const sin = Math.sin(player.yaw), cos = Math.cos(player.yaw);
  let dx = -sin * input.fwd + cos * input.right;
  let dz = -cos * input.fwd - sin * input.right;
  const len = Math.hypot(dx, dz);
  if (len > 0) { dx /= len; dz /= len; }

  // --- dodge ---------------------------------------------------------------------
  if (player.dodgeCd > 0) player.dodgeCd -= dt;
  if (player.iframes > 0) player.iframes -= dt;

  if (input.dodgeQueued) {
    input.dodgeQueued = false;
    if (player.dodgeCd <= 0 && player.dodgeT <= 0) {
      // Roll the way you TAPPED, resolved against the camera yaw at the moment of the roll.
      const f = input.dodgeFwd, r = input.dodgeRight;
      const rx = -sin * f + cos * r;
      const rz = -cos * f - sin * r;
      const rl = Math.hypot(rx, rz) || 1;
      player.dodgeX = rx / rl;
      player.dodgeZ = rz / rl;
      player.dodgeT = DODGE.time;
      player.iframes = DODGE.iframes;
      player.dodgeCd = DODGE.cooldown;
      // D4: dodging drops you out of ADS — but only for the duration of the roll. The
      // physical button state is untouched, so holding RMB through a dodge resumes aiming
      // the instant it ends.
    }
  }

  if (player.leapT > 0) {
    // The leap drives horizontal velocity only — vertical is left to gravity so it ARCS
    // rather than flying flat, which is what makes the landing read as a slam.
    player.leapT -= dt;
    player.vx = player.leapX * WHIRL.leapSpeed;
    player.vz = player.leapZ * WHIRL.leapSpeed;
  } else if (player.dashT > 0) {
    // Dash Strike: committed like the dodge, but faster and further. Terrain still stops
    // you — the normal collision below runs unchanged, so you cannot blink through a wall.
    player.dashT -= dt;
    player.vx = player.dashX * DASH.speed;
    player.vz = player.dashZ * DASH.speed;
  } else if (player.dodgeT > 0) {
    player.dodgeT -= dt;
    // The roll OWNS horizontal velocity while it lasts — no steering mid-roll. Committing
    // to the direction is what makes it a dodge instead of a speed boost. dashMult scales
    // the SPEED (not the duration), so a faster roll covers more ground in the same i-frame
    // window — farther and quicker at once, exactly what speed and the Vault stat buy.
    player.vx = player.dodgeX * DODGE.speed * player.dashMult;
    player.vz = player.dodgeZ * DODGE.speed * player.dashMult;
  } else {
    const targetVx = dx * speed, targetVz = dz * speed;
    const blend = 1 - Math.exp(-(len > 0 ? PLAYER.accel : PLAYER.friction) * dt);
    player.vx += (targetVx - player.vx) * blend;
    player.vz += (targetVz - player.vz) * blend;
  }

  // Standing on the ground restocks every jump. Walking off a ledge without jumping leaves
  // the full set — deliberately forgiving, and it doubles as coyote time.
  if (player.onGround) player.jumpsLeft = player.maxJumps;

  player.vy = Math.max(PLAYER.maxFall, player.vy + PLAYER.gravity * dt);

  if (input.jumpQueued) {
    input.jumpQueued = false;
    if (player.jumpsLeft > 0) {
      const fromGround = player.onGround;
      // SET the velocity rather than adding: an air jump while falling fast should feel
      // like a clean second launch, not a rounding error against your downward momentum.
      player.vy = PLAYER.jumpSpeed * player.jumpMult * (fromGround ? 1 : PLAYER.airJumpScale);
      player.jumpsLeft--;
      player.onGround = false;
    }
  }

  // If we're ALREADY inside something — shoved into a sanctuary wall by knockback, or a
  // grenade — every candidate position is blocked, including the one we're standing on, so
  // both axes refuse and the player is welded in place. Detect that and let them walk out.
  const stuck = blocked(player.x, player.y, player.z);

  // SUBSTEPPED. Speed has no ceiling, so a single frame's movement can be many blocks; a
  // one-shot test would sample the far side of a wall and find it clear, stepping straight
  // through. Splitting the move into sub-block pieces makes the collision honest at any
  // speed, which is what lets the stat stay unbounded.
  const move = Math.hypot(player.vx * dt, player.vz * dt, player.vy * dt);
  const steps = Math.min(16, Math.max(1, Math.ceil(move / 0.4)));
  const sdt = dt / steps;

  for (let k = 0; k < steps; k++) {
    // Axis-separated resolution: try each move independently so a blocked X still allows Z.
    const nx = player.x + player.vx * sdt;
    if (stuck || !blocked(nx, player.y, player.z)) player.x = nx; else player.vx = 0;

    const nz = player.z + player.vz * sdt;
    if (stuck || !blocked(player.x, player.y, nz)) player.z = nz; else player.vz = 0;
  }

  const ny = player.y + player.vy * dt;
  if (stuck || !blocked(player.x, ny, player.z)) {
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
