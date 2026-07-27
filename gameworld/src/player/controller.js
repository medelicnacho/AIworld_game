// Input + player physics. Runs on a fixed step so movement feel never depends on framerate.
//
// Collision is AABB-vs-voxel, resolved one axis at a time — the standard trick that lets you
// slide along a wall instead of sticking to it. It samples the world function directly, so
// there is no collider to build, bake, or keep in sync with the mesh.

import { PLAYER, CAMERA, DODGE, DASH, WHIRL, ABILITY, SPRINT, SPIN, LANCE_SPIN } from "../config.js";
import { player } from "../state.js";
import { solidAt } from "../world/gen.js";
import { wallBlocksBody, sanctuaryUnder, wallBlocks, boundaryAt } from "../world/sanctuary.js";
import { isHostileSanctuary } from "../prog/factions.js";
import { SLOT_KEYS } from "./abilities.js";

// Which keyboard code maps to which spell-bar slot index — DERIVED from SLOT_KEYS rather than
// written out beside it. This was a hand-kept copy whose comment promised it matched, which is
// the arrangement where one of two lists is always about to be wrong: abilities.js says editing
// SLOT_KEYS is the only change needed, and that was true of the HUD and the bag screen and
// quietly untrue here. A key the bar no longer draws that still fires a slot index is a spell
// cast by a button nobody can see.
const SLOT_CODE = Object.fromEntries(SLOT_KEYS.map((k, i) => [
  /^[0-9]$/.test(k) ? `Digit${k}` : k.length === 1 ? `Key${k}` : k, i,
]));

export const input = {
  fwd: 0, right: 0, sprint: false, firing: false,
  // aimHeld is the PHYSICAL button; `aim` is derived each step. Writing to `aim` directly
  // (as the dodge used to) desyncs it from the mouse — you hold RMB and nothing happens
  // until you release and press again.
  aimHeld: false, aim: false,
  // Dodge is double-tap-a-direction, so the queued roll remembers WHICH key fired it —
  // you roll the way you tapped, not the way you happen to be steering a frame later.
  dodgeQueued: false, dodgeFwd: 0, dodgeRight: 0,
  // Jump is EDGE-triggered, not held: one press = one jump. A held-key check would let you
  // bunny-hop forever by leaning on space, and would burn both air jumps in a single frame.
  // jumpHeld is the exception, and it drives exactly ONE thing: the lance spin's rotor
  // (see the gravity block) — a lift you HOLD is the whole point of a rotor, and it never
  // touches the jump charges.
  jumpHeld: false,
  jumpQueued: false,
};

const LOOK_KEY = "gw.look";
export const LOOK_MIN = 0.0015, LOOK_MAX = 0.05;

// Pixels of mouse travel a SINGLE event may claim before we treat it as garbage rather than
// as a person. Mouse reports arrive at 125Hz or faster, so even a violent flick is tens of
// pixels per event; hundreds means the browser is reporting a cursor warp, not a hand.
const MAX_LOOK_STEP = 260;
let swallowNextMove = false;

/**
 * Set and remember look sensitivity. Exported so the pause screen can offer it as a VISIBLE
 * control: a setting that exists only as an undocumented keybind is a setting nobody but the
 * author has. Every player of a build gets the default and no way to learn otherwise, which
 * is how "too slow for me" becomes "the controls are broken" in a bug report.
 */
export function setLook(value) {
  CAMERA.sensitivity = Math.max(LOOK_MIN, Math.min(LOOK_MAX, value));
  try { localStorage.setItem(LOOK_KEY, String(CAMERA.sensitivity)); } catch { /* ignore */ }
  return CAMERA.sensitivity;
}

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
    // Tab is a spell slot AND the browser's focus key — swallow its default so it can never
    // shift focus off the canvas, drop pointer lock, and pause you mid-fight. (Skip it when a
    // text field is focused, e.g. the admin panel, so Tab-between-fields still works there.)
    if (e.code === "Tab" && !/^(INPUT|TEXTAREA)$/.test(e.target?.tagName)) e.preventDefault();
    if (e.code === "F5") { e.preventDefault(); hooks.toggleCamera?.(); return; }
    // ESCAPE MEANS PAUSE — as a key, not only as a side effect. While the browser holds the
    // mouse, Escape's keydown rarely arrives at all: releasing the capture IS its meaning
    // there, and the unlock event carries the pause. But the game now runs WITHOUT the
    // capture too (a refused grab no longer blocks play, and there is always a gap after
    // leaving a vendor while it is re-acquired) — and in that state Escape used to be a
    // completely dead key: nothing to release, no event, no pause, however hard you pressed
    // it. The key itself has to speak whenever no capture is present to speak for it.
    // (The shop and the character sheet claim Escape first, in capture, when they are open.)
    if (e.code === "Escape" && !e.repeat) { hooks.escapeKey?.(); return; }
    if (e.code === "KeyM") { hooks.toggleMusic?.(); return; }
    // Live look-speed tuning: 20% per press, clamped to a sane band.
    if (e.code === "BracketLeft" || e.code === "BracketRight") {
      setLook(CAMERA.sensitivity * (e.code === "BracketRight" ? 1.2 : 1 / 1.2));
      return;
    }
    // !e.repeat: the OS fires keydown repeatedly while a key is held — without this, one
    // long press would queue a jump every few milliseconds.
    if (e.code === "Space") { input.jumpHeld = true; if (!e.repeat) input.jumpQueued = true; }
    if (e.code === "KeyR") hooks.reload?.();
    if (e.code === "KeyF" && !e.repeat) hooks.interact?.();
    if (e.code === "KeyC" && !e.repeat) hooks.drink?.();
    // The spell bar: Q and E, then 1-4 — all of it under a hand that never leaves WASD.
    // R and F are left alone (reload, trade); the key list itself lives in abilities.js.
    // Q and E are no longer special-cased here — heal and the grenade are spells sitting in
    // the first two slots, so they arrive through the same door as everything else.
    // SHIFT IS ALLOWED — it's sprint, so you must be able to cast while running (Shift+Tab
    // still casts, and its focus-shift is already swallowed above). Only Ctrl/Alt/Meta block a
    // cast, because those are browser-shortcut modifiers (Ctrl+1 switches tabs, etc.).
    if (!e.repeat && !e.ctrlKey && !e.altKey && !e.metaKey) {
      const slot = SLOT_CODE[e.code];
      if (slot !== undefined) hooks.ability?.(slot);
    }
    if (e.code === "KeyZ" && !e.repeat) hooks.sleep?.();  // rest in a safe town: skip to dawn

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
  window.addEventListener("keyup", (e) => {
    if (e.code === "Space") input.jumpHeld = false;
    keys.delete(e.code);
    refresh();
  });
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

  canvas.addEventListener("click", () => {
    // START FIRST, capture the mouse second. These used to be the same act: the game only
    // ever unpaused on a SUCCESSFUL lock, so a browser that refused one left the player on
    // the click-to-play screen forever with nothing explaining why. Pointer lock is an
    // enhancement — it makes looking around feel right — and an enhancement must never be
    // the thing standing between someone and the game.
    // If the start is REFUSED — a panel is open, or the difficulty has not been chosen yet —
    // do not grab the mouse either. Taking the lock unpauses through onLock, which would sail
    // straight past the very guard startPlaying just enforced. A refused start is a refused
    // click, whole.
    if (hooks.startPlaying?.() === false) return;
    canvas.requestPointerLock();
  });
  document.addEventListener("pointerlockchange", () => {
    const locked = document.pointerLockElement === canvas;
    // The next mouse report is the cursor being warped, not the player moving. See the
    // mousemove handler — this is set on BOTH directions, since releasing the mouse puts the
    // cursor back where it came from and reports that as movement too.
    swallowNextMove = true;
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

    // THROW AWAY THE FIRST EVENT AFTER A LOCK CHANGE, AND ANY IMPOSSIBLE ONE.
    //
    // Taking the mouse hides the cursor and warps it to the middle of the screen, and
    // browsers report that warp as a MOVEMENT — one event carrying the entire distance from
    // wherever the cursor happened to be. Now that the game starts before the capture is
    // granted, look is live when that arrives, so a single bogus jump used to slam the view
    // to the ceiling and leave it pinned there. Firefox is the worst for it; Chrome does it
    // too, just less often.
    //
    // Two guards, because either alone leaks: skip the first report after any lock change,
    // and refuse any single event too large for a hand to have produced. A real flick is
    // tens of pixels per event at these rates, never hundreds — so this cannot cost anyone a
    // fast turn, and it cannot be defeated by a warp that happens a frame later than expected.
    if (swallowNextMove) { swallowNextMove = false; return; }
    const dx = e.movementX || 0, dy = e.movementY || 0;
    if (Math.abs(dx) > MAX_LOOK_STEP || Math.abs(dy) > MAX_LOOK_STEP) return;

    player.yaw -= dx * CAMERA.sensitivity;
    player.pitch -= dy * CAMERA.sensitivity;
    player.pitch = Math.max(CAMERA.minPitch, Math.min(CAMERA.maxPitch, player.pitch));
  });

  // D4: hold RMB to aim (camera blends toward first person), hold LMB to fire.
  //
  // Gated on the same condition as LOOK, not on pointer lock alone. Where a browser refuses
  // to capture the mouse, the game now runs anyway — and a game you can walk and turn in but
  // cannot shoot in is not a degraded experience, it is a broken one.
  document.addEventListener("mousedown", (e) => {
    if (document.pointerLockElement !== canvas && !hooks.lookUnlocked?.()) return;
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
    if (document.pointerLockElement !== canvas && !hooks.lookUnlocked?.()) return;
    hooks.cycleWeapon?.(e.deltaY > 0 ? 1 : -1);
  }, { passive: true });
  window.addEventListener("contextmenu", (e) => e.preventDefault());
}

/** Is the player's capsule blocked at this position? Sampled as a voxel-span AABB test. */
function blocked(x, y, z) {
  // The wall is an analytic ring, not voxels — so it's a maths test, and the collision can
  // never disagree with what's drawn. The gate is a gap: you walk in and out freely.
  if (wallBlocksBody(x, y, z, PLAYER.height)) return true;
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

/**
 * Walk UP a one-block rise instead of stopping dead against it.
 *
 * Only from the ground: allowed in mid-air this is a wall-climb, since you could hug a cliff
 * and ratchet up it a block at a time. And only ONCE per physics step (the caller's `stepped`
 * latch) — the move is substepped up to sixteen times a frame, so without that you could
 * ascend sixteen blocks in a frame by running at a tall enough wall.
 *
 * A sheer wall still refuses, because the capsule test at the raised position finds the
 * block above. Stairs climb; walls do not. That is the whole rule.
 */
function tryStep(nx, nz) {
  if (!player.onGround) return false;
  const ny = Math.floor(player.y) + PLAYER.stepHeight;
  if (blocked(nx, ny, nz)) return false;
  player.stepLift = Math.min(PLAYER.stepHeight, player.stepLift + (ny - player.y));
  player.y = ny;
  return true;
}

export function stepPlayer(dt) {
  // Derived, every step: held AND not mid-roll.
  input.aim = input.aimHeld && player.dodgeT <= 0;
  if (player.sprintT > 0) player.sprintT -= dt;
  // A TOWN TAKES YOUR SPEED STATS, not your speed. Inside the walls speedMult is ignored, so
  // you move at the level-one baseline — because by level forty you cross a market square in
  // two strides and lining yourself up with a shopkeeper becomes a chore of overshooting them.
  // Only the passive STAT goes: sprinting still sprints, and the movement abilities below are
  // deliberate presses rather than something you carry, so they are left alone.
  //
  // Jumps are untouched on purpose. Your jump height and your double jump are what make a
  // town navigable at walking pace, and taking them would fix one nuisance by adding another.
  const speed = (input.sprint && !input.aim ? PLAYER.sprintSpeed : PLAYER.walkSpeed)
    * (player.inTown ? 1 : player.speedMult)
    * (player.surgeT > 0 ? ABILITY.surgeSpeed : 1)
    * (player.sprintT > 0 ? SPRINT.mult : 1)
    * (player.whirlT > 0 ? WHIRL.spinSpeed : 1)
    * (player.spinT > 0 ? SPIN.speed : 1)
    * (player.lanceSpinT > 0 ? LANCE_SPIN.speed : 1);

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
    // The double-tap dodge is a COMBAT move, so it stows at a friendly gate the same way your
    // weapons do — you do not roll around your own town square. A HOSTILE town (a rival's, one
    // that does not serve you) is intruder ground, and there the dash still answers.
    const here = sanctuaryUnder(player.x, player.y, player.z, 0);
    const peaceful = here && !isHostileSanctuary(here);
    if (!peaceful && player.dodgeCd <= 0 && player.dodgeT <= 0) {
      // Roll the way you TAPPED, resolved against the camera yaw at the moment of the roll.
      const f = input.dodgeFwd, r = input.dodgeRight;
      const rx = -sin * f + cos * r;
      const rz = -cos * f - sin * r;
      const rl = Math.hypot(rx, rz) || 1;
      player.dodgeX = rx / rl;
      player.dodgeZ = rz / rl;
      player.dodgeT = DODGE.time;
      // MAX, never a plain assignment. Every other source of i-frames in the game raises the
      // floor; this one SET it, so rolling in the middle of a 2.5-second spin cut the guard
      // down to the roll's own 0.22 — the one move whose entire promise is "untouchable the
      // whole time", broken by pressing a movement key inside it. A dodge can only ever make
      // you safer.
      player.iframes = Math.max(player.iframes, DODGE.iframes);
      player.dodgeCd = DODGE.cooldown;
      // D4: dodging drops you out of ADS — but only for the duration of the roll. The
      // physical button state is untouched, so holding RMB through a dodge resumes aiming
      // the instant it ends.
    }
  }

  // OFF THE PARAPET. The wall is a solid band with a flat top, so anything that LANDS on it
  // could walk the whole ring — over the gate, over the garrison, sniping into a town it
  // never entered. A wall is a barrier, not a road.
  //
  // Only while STANDING on it. That single condition is what lets you still jump clean over a
  // wall: in the air nothing touches you, and the slide only starts if you actually come to
  // rest up there. Nudging velocity was tried first and lost — it competed with the input's
  // own acceleration, so you could simply walk against it and stay.
  let slideX = 0, slideZ = 0;
  if (player.onGround) {
    const w = wallBlocks(player.x, player.z);
    if (w && player.y > w.plateau + 2) {
      const ox = player.x - w.x, oz = player.z - w.z;
      const od = Math.hypot(ox, oz) || 1;
      // Toward the nearer face: outward if you are past the line, inward if not.
      const side = od >= boundaryAt(w, 0) ? 1 : -1;
      slideX = (ox / od) * side;
      slideZ = (oz / od) * side;
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
    // IT GOES WHERE YOU ARE LOOKING, up and down included. It used to flatten your aim to the
    // horizon, so in a game built out of ledges and islands the one committed movement tool
    // could only ever travel along the floor — you aimed at something above you and slid past
    // underneath it. Driving vy directly (rather than adding to it) means gravity does not get
    // to eat the climb halfway through: the dash OWNS all three axes for its quarter second,
    // the same way it already owned the other two, and gravity resumes the instant it ends.
    player.vy = player.dashY * DASH.speed;
    // ...AND IT ENDS DEAD, vertically. Driving vy for the dash's quarter second is what stops
    // gravity eating the climb; LEAVING it there is a launch. The dash runs at 46, so an
    // upward one expired with 46 of rise still in the bank and gravity spent the next two
    // seconds spending it — about forty further blocks, straight up, well after the dash had
    // visibly finished. Horizontal never showed the bug because vx and vz are rewritten from
    // your input every frame; nothing rewrites vy but gravity, so whatever the dash left there
    // simply happened.
    //
    // Zeroed rather than kept, so the dash is exactly the twelve blocks it advertises and you
    // fall from wherever that put you.
    if (player.dashT <= 0) player.vy = 0;
  } else if (player.dodgeT > 0) {
    player.dodgeT -= dt;
    // The roll OWNS horizontal velocity while it lasts — no steering mid-roll. Committing
    // to the direction is what makes it a dodge instead of a speed boost. dashMult scales
    // the SPEED (not the duration), so a faster roll covers more ground in the same i-frame
    // window — farther and quicker at once, exactly what speed and the Vault stat buy.
    player.vx = player.dodgeX * DODGE.speed * player.dashMult;
    player.vz = player.dodgeZ * DODGE.speed * player.dashMult;
  } else if (player.kickT > 0) {
    // THE WALL KICK OWNS ITS ARC, exactly as the roll above owns its own — see DODGE.kickHold.
    // Held rather than blended, so the leap goes where you kicked it whether or not your hands
    // are on the keys. Vertical is left to gravity: this governs the ACROSS, which is the half
    // the movement blend was quietly deleting.
    player.kickT -= dt;
    // kickSpeed lets other launches ride this ownership at their own strength — the
    // cannon's recoil (gun.js barrage) is the first. Unset means the wall kick's own.
    player.vx = player.kickX * (player.kickSpeed || DODGE.kickOut);
    player.vz = player.kickZ * (player.kickSpeed || DODGE.kickOut);
  } else if (slideX || slideZ) {
    // OWNS horizontal velocity, exactly like the roll above — steering out of it is what made
    // the first attempt useless. Faster than a sprint, so the wall band is behind you inside
    // half a second, and not so fast that it flings you.
    player.vx = slideX * PLAYER.wallSlide;
    player.vz = slideZ * PLAYER.wallSlide;
  } else {
    const targetVx = dx * speed, targetVz = dz * speed;
    const blend = 1 - Math.exp(-(len > 0 ? PLAYER.accel : PLAYER.friction) * dt);
    player.vx += (targetVx - player.vx) * blend;
    player.vz += (targetVz - player.vz) * blend;
  }

  // Standing on the ground restocks every jump. Walking off a ledge without jumping leaves
  // the full set — deliberately forgiving, and it doubles as coyote time.
  //
  // A WALL IS NOT GROUND. Refusing the jump alone was not enough: touching down on a parapet
  // still handed your charges back, so you could ride a wall to the top of the world by
  // spending them, landing on stone to refill, and spending them again. Stone gives you
  // nothing — you get your jumps back the moment you are standing on something real.
  if (player.onGround && !slideX && !slideZ) player.jumpsLeft = player.maxJumps;

  // The launch grace ticks with the physics, not the frame — see the jump below, which
  // reads it to tell a climb you PAID for from one you spammed.
  if (player.launchT > 0) player.launchT -= dt;

  player.vy = Math.max(PLAYER.maxFall, player.vy + PLAYER.gravity * dt);

  // THE ROTOR. While the lance's beam SPINS, held space is lift — the sweep becomes a
  // rotor and Ash flies for as long as the spin lasts. max(), not assignment, so a dash
  // or a jump taken into the spin keeps its speed and the rotor catches you on the way
  // down; release space (or let the spin end) and gravity resumes mid-thought. The spin's
  // own two-second clock is the fuel gauge, its cooldown is the flight's price, and no
  // jump charge is ever spent — which is what makes this a MOVE and not a bigger jump:
  // Iron's spin holds ground, Ash's leaves it.
  // EITHER SPIN IS A ROTOR — Ash's beam and Iron's cleaver both lift you while they turn,
  // and the gap between the two numbers is the faction line. Ash climbs onto a deck; Iron
  // gets a HOP, enough to leave a crowd or take a ledge and not enough to reach the sky's
  // floors. Iron's spin lasts longer, so the two are closer in total height than the lift
  // numbers suggest — which is the right shape: Iron leaves the ground slowly and briefly,
  // and is still the faction that has to come back down into the fight.
  const rotorLift = player.lanceSpinT > 0 ? LANCE_SPIN.lift
    : player.spinT > 0 ? SPIN.lift : 0;
  if (rotorLift > 0 && input.jumpHeld) {
    player.vy = Math.max(player.vy, rotorLift);
  }

  if (input.jumpQueued) {
    input.jumpQueued = false;
    // Space belongs to the rotor while the beam spins — the press that starts the climb
    // must not also burn an air jump.
    // Space belongs to whichever rotor is turning — the press that starts a climb must
    // never also burn an air jump, for either faction.
    if (player.lanceSpinT > 0 || player.spinT > 0) { /* held, not spent */ } else
    // NOT OFF A WALL. Without this the slide is trivially beaten: hop, land, hop again, and
    // you are still standing on the parapet — the slide only owns you while you are on the
    // ground, so a jump is a free half-second of ignoring it. Refusing costs no jump charge;
    // the moment you are clear of the stone, jumping works normally again.
    if (slideX || slideZ) {
      // nothing — you have no footing to push off from
    } else if (player.jumpsLeft > 0) {
      const fromGround = player.onGround;
      const boost = PLAYER.jumpSpeed * player.jumpMult * (fromGround ? 1 : PLAYER.airJumpScale);
      // THREE CASES, and the middle one is the whole reason this is not one line.
      //
      //   FALLING   -> set. An air jump mid-fall must feel like a clean second launch, not
      //               a rounding error against a big negative number.
      //   LAUNCHED  -> add. You paid six shells and a cooldown to be thrown upward; a jump
      //               must not overwrite that and cap you back at jump speed. Two verbs
      //               that both mean "up" never subtract.
      //   OTHERWISE -> the higher of the two. A jump may never LOWER a climb, and may never
      //               raise it beyond what one jump is worth.
      //
      // That last case is the fix for a bug the previous version shipped: "rising, it adds"
      // let jumps compound on EACH OTHER, so spamming the key stacked boost on boost and a
      // high-level character with a fistful of air jumps could climb most of the sky for
      // free. The intent was always that a jump adds to momentum it did not create — the
      // launch is the thing being combined with, and jumps are not launches.
      //
      // player.launchT is what makes "launched" a state rather than a guess (see gun.js).
      // A guess would have been "am I rising fast?", which is the same trap in a costume:
      // it cannot tell a paid launch from three free jumps in a row.
      const launched = player.launchT > 0 && player.vy > 0;
      player.vy = player.vy <= 0 ? boost
        : launched ? player.vy + boost
        : Math.max(player.vy, boost);
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

  let stepped = false;      // at most one block of auto-step per physics step — see tryStep
  // Which way a wall pushed back, if a ROLL ran into one. Captured here and spent after the
  // loop: the sub-steps would otherwise fire a kick several times in a single frame, and the
  // direction has to be read BEFORE the velocity that carried you there is zeroed.
  let kickX = 0, kickZ = 0;
  const rolling = player.dodgeT > 0;
  for (let k = 0; k < steps; k++) {
    // Axis-separated resolution: try each move independently so a blocked X still allows Z.
    const nx = player.x + player.vx * sdt;
    if (stuck || !blocked(nx, player.y, player.z)) player.x = nx;
    else if (!stepped && tryStep(nx, player.z)) { player.x = nx; stepped = true; }
    else { if (rolling && player.vx) kickX = player.vx > 0 ? -1 : 1; player.vx = 0; }

    const nz = player.z + player.vz * sdt;
    if (stuck || !blocked(player.x, player.y, nz)) player.z = nz;
    else if (!stepped && tryStep(player.x, nz)) { player.z = nz; stepped = true; }
    else { if (rolling && player.vz) kickZ = player.vz > 0 ? -1 : 1; player.vz = 0; }
  }

  // THE WALL KICK (see DODGE.kickUp). A roll that hit a wall goes up and off it instead of
  // stopping dead. Anything knee-high was already absorbed by tryStep above, so reaching here
  // means it really was a wall — the terrain has answered "is this worth kicking off" before
  // the question is asked.
  if (rolling && (kickX || kickZ)) {
    const len = Math.hypot(kickX, kickZ) || 1;
    player.dodgeT = 0;                    // the roll is spent on the kick
    player.vy = DODGE.kickUp;
    player.kickX = kickX / len;
    player.kickZ = kickZ / len;
    player.kickSpeed = 0;                 // the wall kick flies at its own strength
    player.kickT = DODGE.kickHold;        // the arc is committed — see the branch above
    player.vx = player.kickX * DODGE.kickOut;
    player.vz = player.kickZ * DODGE.kickOut;
    player.onGround = false;
    // A breath of the roll's own protection carries into the launch, so kicking off a wall
    // with something swinging at you is a read rather than a coin flip.
    player.iframes = Math.max(player.iframes, DODGE.iframes * 0.5);
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

  if (player.stepLift > 0) player.stepLift = Math.max(0, player.stepLift - dt * PLAYER.stepSmooth);

  player.sprinting = input.sprint && len > 0;
}
