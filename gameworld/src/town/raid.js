// THE GARRISON, and THE RAID it becomes on rival ground.
//
// EVERY faction town keeps a garrison: a big group filling the INSIDE of the walls, in the
// town's war colour, made of the mob vocabulary you already know — melee bodies, casters,
// chargers. They fight ONE enemy: you. Town fighters are out of the mob war entirely
// (mobs.js) — a garrison the field could whittle down was a garrison that was sometimes
// dead when you arrived, and "every town is manned" outranks "the war is visible at gates".
// (The old hitscan gate-guard detachment is GONE from the game entirely, 2026-07-25.)
//
//   YOUR colour's garrison   your army. Can't be hurt by you, ignores you, wars beside you.
//   A RIVAL's garrison       the raid. It hunts you inside the walls, its traders take up
//                            arms as champions, and killing every last defender SACKS the
//                            town — a boss-sized payout and a loot fountain.
//   Before you choose        every garrison watches you pass. The war is none of yours yet.
//
// Defenders are ordinary MOBS flying the town's colour, spawned inside the walls with the
// town as their home. That one decision buys the entire combat stack for free — shooting,
// blast damage, spells, knockback, crowd control, damage numbers, death effects, faction
// colouring, the war itself. The champions are role-flavoured overrides on top: the ADEPT
// casts (with a barrage), the QUARTERMASTER charges (with a boss's health), the HERBALIST
// heals the garrison (mobs.js carries those behaviours, keyed on e.champion / e.defender).

import { MOB, RAID } from "../config.js";
import { player, world } from "../state.js";
import { sanctuariesNear, sanctuaryOf } from "../world/sanctuary.js";
import { isHostileSanctuary, FACTIONS } from "../prog/factions.js";
import { tierAt, ringPressure } from "../world/gen.js";

export class Raids {
  /**
   * @param mobs       the mob layer — defenders are spawned through it
   * @param onSack     called with the sacked sanctuary when its last defender falls
   * @param onChampion called ONCE per champion death (entity still positioned) — the reward
   */
  constructor(mobs, onSack, onChampion) {
    this.mobs = mobs;
    this.onSack = onSack;
    this.onChampion = onChampion;
    // townId -> { roles:Set, t }. THE CHAMPIONS' GRAVES. Deliberately SEPARATE from
    // this.state: state is the atomic body bookkeeping and is thrown away whole every time
    // a town leaves range, while a champion's death has to survive exactly that — it is the
    // memory that stops the three hardest kills of a raid being rebuilt by walking away and
    // back. Ticks down on the same clock a sack does; when it runs out, they are rebuilt.
    this.fallen = new Map();
    // townId -> { ids:Set, total, killed, sackedT, armed, ... }. Kill attribution is EXACT:
    // mobs.hit calls onDefenderKill on the death of anything flagged e.defender, so a garrison
    // that merely despawned behind you (you walked away mid-raid) never counts as conquered.
    this.state = new Map();
    mobs.onDefenderKill = (e) => {
      const st = this.state.get(e.defender);
      if (!st) return;
      st.killed++;
      // Killing one of them IS declaring the war, and it is the one trip the periodic check
      // in update() cannot see: a corpse has no health left to read as damaged. Arm here,
      // synchronously inside the kill, so the rest of the garrison answers the first shot
      // rather than a frame later.
      if (st.hostile && !st.armed) this.arm(st);
      // A champion's fall is recorded BEFORE the reward fires, and the set is checked first
      // — so no path, however the hook gets called, can ever pay the same head twice.
      if (e.champion) {
        let f = this.fallen.get(e.defender);
        if (!f) this.fallen.set(e.defender, f = { roles: new Set(), t: 0 });
        if (!f.roles.has(e.champion)) {
          f.roles.add(e.champion);
          f.t = RAID.rebuild;
          this.onChampion?.(e);
        }
      }
    };
  }

  /** A raid in progress or done here recently? (For UI / respawn logic if wanted.) */
  sackedRecently(townId) {
    const st = this.state.get(townId);
    return !!st && st.sackedT > 0;
  }

  /** The player changed factions: who counts as hostile just changed under every garrison.
   *  Despawn all defenders and forget everything — towns re-muster on next approach. */
  reset() {
    for (const st of this.state.values()) {
      for (const id of st.ids) if (world.entities.get(id)) this.mobs.despawn(id);
    }
    this.state.clear();
    this.fallen.clear();   // new loyalties, new enemies — old graves belong to an old war
  }

  /** One defender: a mob of the town's colour (the WAR-colour of the faction the town
   *  belongs to — town.faction indexes FACTIONS, mobs speak colour), homed to the town,
   *  that never breeds and watches for intruders further than a wild mob would.
   *
   *  `armed` is whether this body is hunting you RIGHT NOW — not whether it is your enemy.
   *  A rival's garrison stands its posts, fully manned and visible, until you give it a
   *  reason (see arm()). */
  spawnDefender(s, packId, ang, rad, baseHp, armed) {
    const x = s.x + Math.cos(ang) * rad;
    const z = s.z + Math.sin(ang) * rad;
    const colour = FACTIONS[s.faction % FACTIONS.length].ally;
    const e = this.mobs.spawnOne(x, z, packId, s.x, s.z, [], colour);
    // Garrison bodies are DESIGNED, not rolled — strip whatever the spawn table dealt.
    e.elite = false; e.caster = false; e.charger = false; e.flies = false;
    e.affixes = [];
    e.defender = s.id;
    e.notice = RAID.notice;
    e.noAggroPlayer = !armed;      // a garrison with no quarrel with you watches you pass
    e.breedCd = Infinity;          // a garrison holds; it does not multiply
    e.maxHp = e.hp = baseHp;
    return e;
  }

  /** Spawn the full garrison — melee, ranged, chargers bunched at the gate, plus (against an
   *  ENEMY) the three big champions. Returns the id set.
   *
   *  `hostile` says whose ground this is and therefore whether the champions muster at all;
   *  `armed` says whether they open fire on sight. Every town in the world gets its whole
   *  garrison the moment you come near — the two flags only decide how it behaves. */
  spawnGarrison(s, packId, baseHp, hostile, armed = false) {
    const rng = this.mobs.rng;
    const ids = new Set();
    const innerR = Math.max(6, s.rMin - 8);

    // THE WHOLE GARRISON LIVES INSIDE THE WALLS. Every body — the line and the champions —
    // is scattered through the town's INTERIOR, filling it the way a population would. Two
    // placements were tried and rejected: bunched at the gate (the town behind them read as
    // empty), and posted OUTSIDE the walls for visibility (worse — a stray splash from your
    // fight with a wild camp could clip one, and first blood arms the whole town, which
    // read as "I killed a mob and a war-camp spawned"). Inside the walls, nothing you do
    // to the frontier can touch them: the fight starts when YOU walk in, and what you find
    // when you do is a town FULL of soldiers, already standing there.
    const post = (kind) => {
      const ang = rng() * Math.PI * 2;
      const rad = innerR * (0.25 + rng() * 0.55);
      const e = this.spawnDefender(s, packId, ang, rad, baseHp * RAID.soldierHp, armed);
      if (kind === "ranged") e.caster = true;
      if (kind === "charger") e.charger = true;
      e.aggro = armed; e.aggroT = armed ? 99 : 0;
      ids.add(e.id);
    };
    for (let i = 0; i < RAID.melee; i++) post("melee");
    for (let i = 0; i < RAID.ranged; i++) post("ranged");
    for (let i = 0; i < RAID.chargers; i++) post("charger");

    // The champions muster only against an ENEMY: in your own or a neutral-to-you town the
    // herbalist, adept and quartermaster are still shopkeepers (villagers.js), not fighters.
    if (hostile) {
      // THE DEAD STAY DEAD. A champion whose role is in the graves does not re-muster —
      // this is what makes killing one PROGRESS rather than a fight the walk back resets.
      const down = this.fallen.get(s.id)?.roles;
      // The champions hold the MIDDLE of their town, dealt to three fixed bearings 120°
      // apart — never rolled, because three rolls can cluster and a cluster reads as one
      // boss with two hiding behind it. Homed to their posts so they stay spread: walking
      // in, you see all three at once, each in its own third of the town.
      const CHAMP_SLOT = { qm: 0, adept: 1, herbalist: 2 };
      const champ = (role, hp, scale) => {
        if (down?.has(role)) return null;
        const ang = s.gate + Math.PI * 0.5 + CHAMP_SLOT[role] * (Math.PI * 2 / 3);
        const e = this.spawnDefender(s, packId, ang, innerR * 0.45, baseHp * hp, armed);
        e.homeX = e.x; e.homeZ = e.z;
        e.champion = role; e.scale = scale; e.aggro = armed; e.aggroT = armed ? 99 : 0;
        ids.add(e.id);
        return e;
      };
      const adept = champ("adept", RAID.adeptHp, RAID.champScale);
      if (adept) adept.caster = true;
      champ("herbalist", RAID.herbHp, RAID.champScale);
      const qm = champ("qm", RAID.qmHp, RAID.qmScale);
      if (qm) { qm.charger = true; qm.damage *= RAID.qmDamage; }
    }
    return ids;
  }

  /**
   * A town readies its defence when you come near — EVERY town, and always the whole thing.
   *
   * This used to be an ambush: a rival town spawned one lone sentinel and the garrison
   * sprang out of the kill hook. It was a neat trick and it was the wrong trade. A town is
   * a PLACE, and a place is read from outside before it is entered — a war-camp you cannot
   * see is a war-camp you cannot choose to avoid, cannot scout, cannot judge the size of,
   * and cannot decide you are not strong enough for. Worse, it made every settlement look
   * abandoned until it wasn't, which reads as a game that forgot to spawn its people.
   *
   * So the bodies are always there, and the CHOICE moves from spawning to aggro:
   *   YOUR / neutral-to-you town  the standing garrison, no champions. Never hunts you.
   *   A RIVAL town                the full war-camp, champions and all, holding its posts.
   *                               It watches you walk past. It comes for you the moment you
   *                               cross the wall or draw first blood (see arm()).
   *
   * The rule "the war only starts when YOU join it" is intact — it is now enforced by what
   * the garrison DOES rather than by whether it exists.
   */
  muster(s) {
    const hostile = isHostileSanctuary(s);
    const ring = tierAt(s.x, s.z);
    // The same base a wild mob of this ring rolls (sans elite), so RAID.*Hp multipliers
    // read as "times a local mob" everywhere balance is discussed.
    const baseHp = MOB.hp * Math.pow(MOB.hpGrowth, ringPressure(ring, MOB.ramp));
    const packId = this.mobs.nextPack++;
    this.mobs.packs.set(packId, { x: s.x, z: s.z });

    const ids = this.spawnGarrison(s, packId, baseHp, hostile, false);
    this.state.set(s.id, {
      s, packId, baseHp, ids,
      total: ids.size, killed: 0, sackedT: 0, hostile, armed: false,
    });
    // Diagnostic breadcrumb, kept cheap and permanent: after a bug that was "the garrison
    // isn't there" for hours, the console must be able to answer exactly what mustered,
    // where, and how big — one line per town, only on approach, never per frame.
    console.info(`[raid] mustered ${s.id}: ${ids.size} bodies${hostile ? " (hostile: full line + champions)" : ""}`);
  }

  /**
   * The war starts. Every defender still standing turns on you at once.
   *
   * One call, from two triggers, because both mean the same thing — you decided this town is
   * a fight. Turning the WHOLE garrison at once (rather than letting them notice you one at
   * a time) is what makes it read as a town rising against you instead of a queue of mobs.
   */
  arm(st) {
    st.armed = true;
    for (const id of st.ids) {
      const e = world.entities.get(id);
      if (!e || e.hp <= 0) continue;
      e.noAggroPlayer = false;
      e.aggro = true;
      e.aggroT = 99;
    }
  }

  /** Have you started this one? Inside their walls, or blood already drawn on their people. */
  shouldArm(st) {
    if (sanctuaryOf(player.x, player.z) === st.s) return true;
    for (const id of st.ids) {
      const e = world.entities.get(id);
      if (e && e.hp > 0 && e.hp < e.maxHp) return true;
    }
    return false;
  }

  update(dt) {
    // Rebuild clocks tick wherever you are — a town does not wait for you to watch it heal.
    for (const [id, st] of this.state) {
      if (st.sackedT > 0) {
        st.sackedT -= dt;
        if (st.sackedT <= 0) this.state.delete(id);   // fully rebuilt: fresh garrison next visit
      }
    }
    // The champions' graves run the same clock: when it expires the town has replaced them.
    for (const [id, f] of this.fallen) {
      f.t -= dt;
      if (f.t <= 0) this.fallen.delete(id);
    }

    // A GARRISON IS ATOMIC: it exists whole, or not at all. When a town falls out of range
    // its entire garrison is despawned and its state forgotten in one stroke — never body
    // by body — so returning always finds either the full group standing or a full fresh
    // muster. Partial garrisons were the recurring glitch: individuals lost off-screen left
    // "some alive" bookkeeping that did nothing until a kill collapsed it into a re-muster,
    // which read as the town spawning off your first shot. Evicted at engage+60, mustered
    // at engage: the gap is hysteresis, so pacing the boundary doesn't flicker the town.
    for (const [id, st] of this.state) {
      if (st.sackedT > 0) continue;                    // no bodies standing; just a timer
      if (Math.hypot(st.s.x - player.x, st.s.z - player.z) > RAID.engage + 60) {
        for (const mid of st.ids) if (world.entities.get(mid)) this.mobs.despawn(mid);
        this.state.delete(id);
      }
    }

    for (const s of sanctuariesNear(player.x, player.z, RAID.engage)) {
      // Every FACTION town garrisons; neutral ground keeps its civic guards instead.
      if (s.city || s.neutral || s.faction === null || s.faction === undefined) continue;
      const st = this.state.get(s.id);
      if (!st) { this.muster(s); continue; }
      if (st.sackedT > 0) continue;                   // quiet: the town is rebuilding

      // A rival's garrison holds until you make it a fight. Checked here rather than in the
      // mob loop so the trigger stays one rule in one place, next to the town it belongs to.
      if (st.hostile && !st.armed && this.shouldArm(st)) this.arm(st);

      // Count the garrison. Ids leave the world by being killed (counted via the hooks on
      // both damage paths — yours and the war's) or by despawning behind a player who
      // walked away — only a full count of DEATHS is a fall; an abandoned or wiped-and-
      // forgotten garrison simply re-musters on the next approach.
      let alive = 0;
      for (const id of st.ids) if (world.entities.get(id)) alive++;
      if (alive > 0) continue;
      // The town is EMPTY, and however it emptied it STAYS empty for the rebuild window.
      // This used to bare-delete the state when the wipe didn't qualify as a sack (an
      // unaligned player clearing a watching garrison, or bookkeeping that lost bodies
      // without deaths) — and the very next frame's muster resurrected a full garrison ON
      // TOP of whoever had just cleared it: the second face of the "kill the last mob and
      // everything spawns" glitch. Only a genuine sack pays; every wipe goes quiet.
      st.sackedT = RAID.rebuild;
      if (st.hostile && st.killed >= st.total) this.onSack?.(s);
    }
  }
}
