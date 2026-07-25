// THE GARRISON, and THE RAID it becomes on rival ground.
//
// EVERY faction town keeps a garrison: a big group bunched at the gate, in the town's war
// colour, made of the mob vocabulary you already know — melee bodies, casters, chargers.
// They fight the faction war for real (a siege at a gate is the war made visible), and the
// old hitscan gate detachment survives only on neutral ground, where civic police read right.
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
import { sanctuariesNear } from "../world/sanctuary.js";
import { isHostileSanctuary, FACTIONS } from "../prog/factions.js";
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

  /** One defender: a mob of the town's colour (the WAR-colour of the faction the town
   *  belongs to — town.faction indexes FACTIONS, mobs speak colour), homed to the town,
   *  that never breeds and watches for intruders further than a wild mob would. */
  spawnDefender(s, packId, ang, rad, baseHp, hostile) {
    const x = s.x + Math.cos(ang) * rad;
    const z = s.z + Math.sin(ang) * rad;
    const colour = FACTIONS[s.faction % FACTIONS.length].ally;
    const e = this.mobs.spawnOne(x, z, packId, s.x, s.z, [], colour);
    // Garrison bodies are DESIGNED, not rolled — strip whatever the spawn table dealt.
    e.elite = false; e.caster = false; e.charger = false; e.flies = false;
    e.affixes = [];
    e.defender = s.id;
    e.notice = RAID.notice;
    e.noAggroPlayer = !hostile;    // a garrison that isn't your enemy watches you pass
    e.breedCd = Infinity;          // a garrison holds; it does not multiply
    e.maxHp = e.hp = baseHp;
    return e;
  }

  /** The garrison: a big group BUNCHED AT THE GATE — melee, ranged and chargers — plus,
   *  on hostile ground only, the three champions standing deeper in the streets. */
  muster(s) {
    const hostile = isHostileSanctuary(s);
    const ring = tierAt(s.x, s.z);
    // The same base a wild mob of this ring rolls (sans elite), so RAID.*Hp multipliers
    // read as "times a local mob" everywhere balance is discussed.
    const baseHp = MOB.hp * Math.pow(MOB.hpGrowth, ringPressure(ring, MOB.ramp));
    const packId = this.mobs.nextPack++;
    this.mobs.packs.set(packId, { x: s.x, z: s.z });
    const rng = this.mobs.rng;
    const ids = new Set();
    const innerR = Math.max(6, s.rMin - 8);

    // The line: clustered just inside the gateway, where a defence should stand.
    const post = (kind) => {
      const ang = s.gate + (rng() - 0.5) * 1.2;
      const rad = innerR * (0.55 + rng() * 0.35);
      const e = this.spawnDefender(s, packId, ang, rad, baseHp * RAID.soldierHp, hostile);
      if (kind === "ranged") e.caster = true;
      if (kind === "charger") e.charger = true;
      ids.add(e.id);
    };
    for (let i = 0; i < RAID.melee; i++) post("melee");
    for (let i = 0; i < RAID.ranged; i++) post("ranged");
    for (let i = 0; i < RAID.chargers; i++) post("charger");

    // The champions muster only against an ENEMY: in your own or a neutral-to-you town the
    // herbalist, adept and quartermaster are still shopkeepers (villagers.js), not fighters.
    if (hostile) {
      const adept = this.spawnDefender(s, packId, rng() * Math.PI * 2, innerR * 0.5, baseHp * RAID.adeptHp, true);
      adept.caster = true; adept.champion = "adept"; adept.scale = RAID.champScale;
      const herb = this.spawnDefender(s, packId, rng() * Math.PI * 2, innerR * 0.5, baseHp * RAID.herbHp, true);
      herb.champion = "herbalist"; herb.scale = RAID.champScale;
      const qm = this.spawnDefender(s, packId, 0.6, innerR * 0.4, baseHp * RAID.qmHp, true);
      qm.charger = true; qm.champion = "qm"; qm.scale = RAID.qmScale;
      qm.damage *= RAID.qmDamage;
      ids.add(adept.id); ids.add(herb.id); ids.add(qm.id);
    }

    this.state.set(s.id, { ids, total: ids.size, killed: 0, sackedT: 0, hostile });
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
      // Every FACTION town garrisons; neutral ground keeps its civic guards instead.
      if (s.city || s.neutral || s.faction === null || s.faction === undefined) continue;
      const st = this.state.get(s.id);
      if (!st) { this.muster(s); continue; }
      if (st.sackedT > 0) continue;                   // quiet: the town is rebuilding

      // Count the garrison. Ids leave the world by being killed (counted via the hooks on
      // both damage paths — yours and the war's) or by despawning behind a player who
      // walked away — only a full count of DEATHS is a fall; an abandoned or wiped-and-
      // forgotten garrison simply re-musters on the next approach.
      let alive = 0;
      for (const id of st.ids) if (world.entities.get(id)) alive++;
      if (alive > 0) continue;
      if (st.hostile && st.killed >= st.total) {
        st.sackedT = RAID.rebuild;
        this.onSack?.(s);
      } else {
        this.state.delete(s.id);
      }
    }
  }
}
