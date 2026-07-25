// THE RAID — a rival faction's town, defended and sackable.
//
// The rule this whole file exists to serve was already in the game: a rival's town is COLD,
// NOT HOSTILE (factions.js isHostileSanctuary) — you may fight there, and nobody will trade
// with you. But a rule that only ever costs you (no shop) and never offers you anything is
// half a rule. This is the other half: the town's people take up arms, and killing every
// last defender SACKS the town for a boss-sized payout.
//
// Defenders are ordinary MOBS flying the town's colour, spawned inside the walls with the
// town as their home. That one decision buys the entire combat stack for free — shooting,
// blast damage, spells, knockback, crowd control, damage numbers, death effects, faction
// colouring — because a defender is just a mob standing somewhere mobs normally can't be.
// The champions are role-flavoured overrides on top: the ADEPT casts (with a barrage), the
// QUARTERMASTER charges (with a boss's health), the HERBALIST heals the garrison (mobs.js
// carries those three behaviours, keyed on e.champion / e.defender).

import { MOB, RAID } from "../config.js";
import { player, world } from "../state.js";
import { sanctuariesNear } from "../world/sanctuary.js";
import { isHostileSanctuary } from "../prog/factions.js";
import { tierAt, ringPressure } from "../world/gen.js";

export class Raids {
  /**
   * @param mobs   the mob layer — defenders are spawned through it
   * @param onSack called with the sacked sanctuary when its last defender falls
   */
  constructor(mobs, onSack) {
    this.mobs = mobs;
    this.onSack = onSack;
    // townId -> { ids:Set, total, killed, sackedT }. Kill attribution is EXACT: mobs.hit
    // calls onDefenderKill on the death of anything flagged e.defender, so a garrison that
    // merely despawned behind you (you walked away mid-raid) never counts as conquered.
    this.state = new Map();
    mobs.onDefenderKill = (e) => {
      const st = this.state.get(e.defender);
      if (st) st.killed++;
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
  }

  /** One defender: a mob of the town's colour, homed to the town, that never breeds,
   *  never wars, and watches for intruders further than a wild mob would. */
  spawnDefender(s, packId, ang, rad, baseHp) {
    const x = s.x + Math.cos(ang) * rad;
    const z = s.z + Math.sin(ang) * rad;
    const e = this.mobs.spawnOne(x, z, packId, s.x, s.z, [], s.faction);
    // Champions are DESIGNED, not rolled — strip whatever the spawn table dealt.
    e.elite = false; e.caster = false; e.charger = false; e.flies = false;
    e.affixes = [];
    e.defender = s.id;
    e.notice = RAID.notice;
    e.breedCd = Infinity;          // a garrison holds; it does not multiply
    e.maxHp = e.hp = baseHp;
    return e;
  }

  /** The garrison: soldiers plus the three champions, scattered through the streets. */
  muster(s) {
    const ring = tierAt(s.x, s.z);
    // The same base a wild mob of this ring rolls (sans elite), so RAID.*Hp multipliers
    // read as "times a local mob" everywhere balance is discussed.
    const baseHp = MOB.hp * Math.pow(MOB.hpGrowth, ringPressure(ring, MOB.ramp));
    const packId = this.mobs.nextPack++;
    this.mobs.packs.set(packId, { x: s.x, z: s.z });
    const rng = this.mobs.rng;
    const ids = new Set();
    const innerR = Math.max(6, s.rMin - 8);

    for (let i = 0; i < RAID.soldiers; i++) {
      const e = this.spawnDefender(s, packId, rng() * Math.PI * 2,
        4 + rng() * innerR * 0.8, baseHp * RAID.soldierHp);
      ids.add(e.id);
    }
    // The three champions: what was the shop is now the fight.
    const adept = this.spawnDefender(s, packId, rng() * Math.PI * 2, innerR * 0.5, baseHp * RAID.adeptHp);
    adept.caster = true; adept.champion = "adept"; adept.scale = RAID.champScale;
    const herb = this.spawnDefender(s, packId, rng() * Math.PI * 2, innerR * 0.5, baseHp * RAID.herbHp);
    herb.champion = "herbalist"; herb.scale = RAID.champScale;
    const qm = this.spawnDefender(s, packId, 0.6, innerR * 0.4, baseHp * RAID.qmHp);
    qm.charger = true; qm.champion = "qm"; qm.scale = RAID.qmScale;
    qm.damage *= RAID.qmDamage;
    ids.add(adept.id); ids.add(herb.id); ids.add(qm.id);

    this.state.set(s.id, { ids, total: ids.size, killed: 0, sackedT: 0 });
  }

  update(dt) {
    // Rebuild clocks tick wherever you are — a town does not wait for you to watch it heal.
    for (const [id, st] of this.state) {
      if (st.sackedT > 0) {
        st.sackedT -= dt;
        if (st.sackedT <= 0) this.state.delete(id);   // fully rebuilt: fresh garrison next visit
      }
    }

    for (const s of sanctuariesNear(player.x, player.z, RAID.engage)) {
      if (!isHostileSanctuary(s)) continue;
      const st = this.state.get(s.id);
      if (!st) { this.muster(s); continue; }
      if (st.sackedT > 0) continue;                   // quiet: the town is rebuilding

      // Count the garrison. Ids leave the world by being killed (counted via the hook) or
      // by despawning behind a player who abandoned the raid — only a full count of KILLS
      // is a conquest; an abandoned raid resets to a fresh garrison on the next approach.
      let alive = 0;
      for (const id of st.ids) if (world.entities.get(id)) alive++;
      if (alive > 0) continue;
      if (st.killed >= st.total) {
        st.sackedT = RAID.rebuild;
        this.onSack?.(s);
      } else {
        this.state.delete(s.id);
      }
    }
  }
}
