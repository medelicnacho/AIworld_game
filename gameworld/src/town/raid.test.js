// Tripwires for the raid layer and the settlement dealing underneath it. The raid's combat
// can only be felt in play, but the RULES that make it fair — every ring holds all three
// colours, a sacked town stays down long enough to matter, the champions outrank the line —
// live in data, and data can be pinned.

import { test } from "node:test";
import assert from "node:assert/strict";
import { RAID, SETTLE } from "../config.js";
import { townCount, tierSettlements, boundaryAt } from "../world/sanctuary.js";
import { Raids } from "./raid.js";
import { player, world } from "../state.js";
import { mulberry32 } from "../rng.js";

/** The smallest thing that looks like the mob layer to Raids — enough to count bodies and
 *  read their aggro flags without dragging three.js into a unit test. */
function fakeMobs() {
  let id = 1;
  return {
    rng: mulberry32(7),
    nextPack: 1,
    packs: new Map(),
    onDefenderKill: null,
    spawnOne(x, z) {
      const e = { id: id++, kind: "mob", x, z, hp: 10, maxHp: 10, damage: 1 };
      world.entities.set(e.id, e);
      return e;
    },
    despawn(i) { world.entities.delete(i); },
  };
}

/** Muster one town of a chosen allegiance and hand back the garrison it produced. */
function musterTown(townFaction, playerFaction, onChampion) {
  world.entities.clear();
  player.faction = playerFaction;
  player.x = 1e6; player.z = 1e6;          // far outside every wall: not inside this town
  const s = tierSettlements(1).find((t) => !t.city && t.faction === townFaction);
  const mobs = fakeMobs();
  const raids = new Raids(mobs, () => {}, onChampion);
  raids.muster(s);
  const st = raids.state.get(s.id);
  return { raids, s, st, mobs, bodies: [...st.ids].map((i) => world.entities.get(i)) };
}

test("every ring deals all three colours, and deals them EVENLY", () => {
  // A random roll can hand a whole ring to one faction, and a player hunting their own
  // colour (or a rival to raid) finds nothing. The dealing must guarantee representation.
  for (let t = 1; t <= 6; t++) {
    const n = townCount(t);
    assert.equal(n % 3, 0, `tier ${t}: town count ${n} must be a multiple of three`);
    const towns = tierSettlements(t).filter((s) => !s.city);
    const byFac = [0, 0, 0];
    for (const s of towns) {
      assert.ok(s.faction === 0 || s.faction === 1 || s.faction === 2,
        `tier ${t}: a town must fly one of the three colours, got ${s.faction}`);
      byFac[s.faction]++;
    }
    assert.ok(byFac.every((c) => c === byFac[0]),
      `tier ${t}: colours must come out even, got ${byFac.join("/")}`);
  }
});

test("more towns than before, growing with depth, capped", () => {
  assert.equal(townCount(0), SETTLE.townsBase, "the spawn town stands alone");
  for (let t = 2; t <= 6; t++) {
    assert.ok(townCount(t) >= townCount(t - 1), "the frontier gets denser, never thinner");
  }
  assert.ok(townCount(1) >= 6, "even the first ring out holds two of each colour");
  assert.ok(townCount(9) <= SETTLE.townCap, "and the cap holds");
});

test("the garrison is a BIG group with all three jobs in it", () => {
  // "Reading a garrison is the same skill as reading the field" only holds if the garrison
  // actually carries the field's vocabulary: bodies that close, bodies that stand and cast,
  // bodies that wind up and charge. And it must be a GROUP — a town guarded by three people
  // reads as abandoned, not defended.
  assert.ok(RAID.melee >= 2, "a line of melee bodies");
  assert.ok(RAID.ranged >= 2, "casters behind them");
  assert.ok(RAID.chargers >= 1, "and at least one charger to fear");
  assert.ok(RAID.melee + RAID.ranged + RAID.chargers >= 12,
    "the garrison must read as a WAR-CAMP — a rival town holds no civilians, so its "
    + "fighters have to fill the streets a population used to");
});

test("the sack is a RAID, not a faucet: rebuild long, loot real, champions ranked", () => {
  // The rebuild timer is what separates 'raiding' from 'farming one poor village forever'.
  assert.ok(RAID.rebuild >= 300, "a sacked town must stay down for minutes, not moments");
  assert.ok(RAID.loot > 0, "victory must LOOK like victory — the fountain is the point");
  // The hierarchy the fight teaches: soldiers < adept < herbalist < quartermaster. The
  // healer outlasting the artillery is what makes kill order a decision, and the QM being
  // the wall is what makes the fight end on a boss rather than fizzle out.
  assert.ok(RAID.soldierHp < RAID.adeptHp, "a champion outranks the line");
  assert.ok(RAID.adeptHp < RAID.herbHp, "the healer must survive being focused first");
  assert.ok(RAID.herbHp < RAID.qmHp, "the quartermaster is the boss of the town");
  assert.ok(RAID.qmDamage > 1, "...and hits harder than a soldier");
  // The barrage must be a stream you can dodge by moving, not one lump or an endless hose.
  assert.ok(RAID.burst >= 3 && RAID.burst <= 8, "a barrage, not a shot or a hose");
  assert.ok(RAID.burstGap > 0.05 && RAID.burstGap < 0.6, "spaced so strafing answers it");
  // The heal pulse must matter without making the garrison unkillable by one player.
  assert.ok(RAID.healFrac > 0 && RAID.healFrac <= 0.25, "a lifeline, not immortality");
  assert.ok(RAID.notice > 0 && RAID.engage > RAID.notice,
    "the garrison musters before it can possibly see you — never in front of you");
});

test("EVERY town is fully manned the moment it musters — no lone sentinel, ever", () => {
  // The bug this pins: a rival town used to spawn ONE lookout and hold the rest of the
  // garrison behind its death, so a war-camp read as an empty village until you shot it.
  // A place you cannot see the size of is a place you cannot choose to avoid.
  const line = RAID.melee + RAID.ranged + RAID.chargers;
  const mine = musterTown(2, "iron");       // an Iron town, to an Iron player
  assert.equal(mine.st.hostile, false, "your own colour's town is not hostile ground");
  assert.equal(mine.bodies.length, line, "a friendly garrison is the full line, no champions");

  const rival = musterTown(1, "iron");      // a Vale town, to an Iron player
  assert.equal(rival.st.hostile, true, "a rival's town IS hostile ground");
  assert.equal(rival.bodies.length, line + 3,
    "a rival garrison is the full line PLUS the three champions — all of it, up front");
  assert.ok(rival.bodies.some((e) => e.champion === "qm"),
    "the quartermaster stands there from the start; you can see what you are walking into");
});

test("a rival's garrison holds its posts until YOU start the war", () => {
  // Always-present must not mean always-aggressive: "the war only starts when you join it"
  // is now carried by aggro rather than by spawning, and it has to actually hold.
  const { raids, st, bodies } = musterTown(1, "iron");
  assert.equal(st.armed, false, "mustering is not declaring");
  assert.ok(bodies.every((e) => e.noAggroPlayer && !e.aggro),
    "every defender watches you pass while you keep your hands to yourself");

  // First blood on any one of them turns the whole town at once.
  bodies[0].hp = bodies[0].maxHp - 1;
  assert.equal(raids.shouldArm(st), true, "hurting one of them is starting it");
  raids.arm(st);
  assert.ok(bodies.every((e) => !e.noAggroPlayer && e.aggro),
    "the town rises TOGETHER — not one mob at a time noticing you");
});

test("your own faction's garrison never arms against you", () => {
  // The complaint this pins: joining Iron must make black towns genuinely friendly. A
  // friendly town is not merely un-aggressive, it is never a candidate for arming at all.
  const { st, bodies } = musterTown(2, "iron");
  assert.equal(st.hostile, false);
  assert.ok(bodies.every((e) => e.noAggroPlayer && !e.aggro),
    "your own army does not hunt you inside its own walls");
  assert.ok(!bodies.some((e) => e.champion),
    "and its traders stay traders — champions muster only against an enemy");
});

test("a garrison is ATOMIC — out of range it vanishes whole, never body by body", () => {
  // The recurring glitch: individuals lost off-screen left a half-manned town whose stale
  // bookkeeping collapsed into a full re-muster on your first kill — which read as the town
  // spawning off the shot. The rule now: a garrison leaves the world only as a whole town.
  const { raids, st } = musterTown(1, "iron");
  raids.update(0.016);       // player is parked 1e6 away — far beyond engage+60
  assert.equal(raids.state.size, 0, "the town's state is forgotten in the same stroke");
  assert.ok([...st.ids].every((i) => !world.entities.get(i)), "and no body is left behind");
});

test("a champion dies ONCE: it pays out, stays out of every re-muster, and returns on the clock", () => {
  const paid = [];
  const { raids, s, bodies, mobs } = musterTown(1, "iron", (e) => paid.push(e.champion));
  const qm = bodies.find((e) => e.champion === "qm");

  // The kill: the hook pays exactly once, however many times a hook might fire.
  qm.hp = 0;
  mobs.onDefenderKill(qm);
  mobs.onDefenderKill(qm);
  assert.deepEqual(paid, ["qm"], "one head, one payout — never two");

  // Walk away (eviction) and come back (fresh muster): the QM must NOT be rebuilt —
  // this is the "kill the three bosses and they just spawn again" bug, pinned.
  raids.update(0.016);
  raids.muster(s);
  const again = [...raids.state.get(s.id).ids].map((i) => world.entities.get(i));
  assert.ok(!again.some((e) => e.champion === "qm"), "the fallen champion stays fallen");
  assert.ok(again.some((e) => e.champion === "adept"), "the ones still standing re-muster");

  // ...until the rebuild clock runs out, when the town has replaced them.
  raids.update(RAID.rebuild + 1);
  raids.muster(s);
  const rebuilt = [...raids.state.get(s.id).ids].map((i) => world.entities.get(i));
  assert.ok(rebuilt.some((e) => e.champion === "qm"), "the rebuild clock restores the QM");
});

test("the whole garrison lives INSIDE the walls, and the champions are spread apart", () => {
  // Everything stands within the town — nothing posted outside where a stray splash from a
  // field fight could draw first blood and arm the whole camp (the endless "I killed one
  // mob and a war-camp spawned" report). And the three champions hold separate thirds of
  // the town: clustered, two hide behind the third and the town reads as one boss.
  const { s, bodies } = musterTown(1, "iron");
  for (const e of bodies) {
    const ang = Math.atan2(e.z - s.z, e.x - s.x);
    const d = Math.hypot(e.x - s.x, e.z - s.z);
    assert.ok(d < boundaryAt(s, ang), "every body stands inside its own walls");
  }
  const champs = bodies.filter((e) => e.champion);
  assert.equal(champs.length, 3, "all three champions muster");
  for (let i = 0; i < champs.length; i++) {
    for (let j = i + 1; j < champs.length; j++) {
      const d = Math.hypot(champs[i].x - champs[j].x, champs[i].z - champs[j].z);
      assert.ok(d > 8, "champions hold separate ground — never a stack that reads as one");
    }
  }
});

test("wiping a garrison NEVER re-musters on the next frame — cleared means quiet", () => {
  // The glitch's second face: a wipe that didn't qualify as a sack bare-deleted the state,
  // and the next frame's muster resurrected a full garrison on top of whoever had just
  // cleared the town. Any empty town now goes quiet for the full rebuild window.
  const { raids, s, st, mobs, bodies } = musterTown(1, "iron");
  for (const e of bodies) { e.hp = 0; mobs.onDefenderKill(e); world.entities.delete(e.id); }
  // Stand the player AT the town so eviction can't fire and the muster loop runs for real.
  player.x = s.x; player.z = s.z;
  raids.update(0.016);
  const after = raids.state.get(s.id);
  assert.ok(after && after.sackedT > 0, "the emptied town enters its quiet period");
  assert.equal([...world.entities.values()].filter((e) => e.defender).length, 0,
    "and NOTHING respawns while it is quiet");
  raids.update(0.016);
  assert.equal([...world.entities.values()].filter((e) => e.defender).length, 0,
    "not on the frame after, either");
  void st;
});
