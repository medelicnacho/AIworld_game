// Villagers: the people who live inside a sanctuary and trade with you.
//
// Unlike the nomads, these are BOUND to their refuge — they never leave the walls. That is
// what makes a sanctuary a destination rather than a wall you hide behind: gold you take
// off the frontier is only worth anything where someone will take it.
//
// Same scope discipline as the folk: bodies, roles and a trade table. No speech, no memory,
// no bonds. When the substrate arrives at Stage 3, THESE are the souls — a walled settlement
// with residents is exactly the shape a town needs, and the seam is already the right one.

import * as THREE from "three";
import { VILLAGE } from "../config.js";
import { player } from "../state.js";
import { groundY } from "../world/gen.js";
import { sanctuariesNear } from "../world/sanctuary.js";
import { GOODS } from "../ui/shop.js";
import { mulberry32 } from "../rng.js";

// Who lives here. What they actually SELL is a table in ui/shop.js (GOODS), keyed by these
// role keys — stock is data, so adding wares never touches this file or the game loop.
export const ROLES = [
  { key: "herbalist", name: "Herbalist", color: 0x63d1a0 },
  { key: "smith", name: "Smith", color: 0xd8b06a },
  { key: "adept", name: "Adept", color: 0x14141c },   // black: the one who sells abilities
  { key: "keeper", name: "Keeper", color: 0x8fa6c4 },
  // QUARTERMASTERS. One per faction, and they are the only people in the world who can take
  // you into one or sell you its kit. A TOWN gets the one whose colour it flies; a CITY keeps
  // all three, which is what makes cities the neutral ground you can always fall back to —
  // and why the choice of who to join happens there.
  { key: "qm_ash", name: "Ash Quartermaster", color: 0xe8804a, faction: "ash" },
  { key: "qm_vale", name: "Vale Quartermaster", color: 0x5fd6b4, faction: "vale" },
  { key: "qm_iron", name: "Iron Quartermaster", color: 0x8fa8d8, faction: "iron" },
];

/** The three quartermaster role keys, in faction order. */
const QM = ["qm_ash", "qm_vale", "qm_iron"];

export class Villagers {
  constructor(scene, seed = 0x71DE) {
    this.rng = mulberry32(seed);
    this.built = new Map();     // sanctuary id -> [villager]
    this.list = [];             // flat, for proximity checks

    this.geo = new THREE.ConeGeometry(0.5, 1.6, 6);
    this.geo.translate(0, 0.8, 0);
    this.mesh = new THREE.InstancedMesh(
      this.geo, new THREE.MeshLambertMaterial({}), VILLAGE.maxRendered);
    this.mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    this.mesh.frustumCulled = false;
    this.mesh.count = 0;
    scene.add(this.mesh);

    this._m = new THREE.Matrix4();
    this._q = new THREE.Quaternion();
    this._p = new THREE.Vector3();
    this._s = new THREE.Vector3(1, 1, 1);
    this._up = new THREE.Vector3(0, 1, 0);
    this._colors = ROLES.map((r) => new THREE.Color(r.color));
  }

  populate(s) {
    const rng = mulberry32(Number(s.id.split(",").reduce((a, b) => a * 31 + Number(b), 7)) >>> 0);
    const folk = [];
    // Every refuge has a herbalist, a smith and an adept — a sanctuary you can't resupply
    // or re-arm at is just scenery — plus keepers so it reads as a place people live.
    const roles = ["herbalist", "smith", "adept"];
    // A city is bigger, so it holds more people AND a second set of traders — walking a
    // city to find the one adept would be a chore rather than a place.
    if (s.city) roles.push("herbalist", "smith", "adept");
    // Whose desk is here. NEUTRAL ground — every city, and the spawn town — keeps all three
    // quarters, because that is what neutral means and it is where you go to pick a side.
    // A town that flies a colour keeps only its own.
    const neutral = s.city || s.neutral;
    if (neutral) roles.push(...QM);
    else if (s.faction !== null && s.faction !== undefined) roles.push(QM[s.faction % QM.length]);
    const want = Math.round(VILLAGE.perSanctuary * (s.r / 46));
    while (roles.length < want) roles.push("keeper");

    // QUARTERMASTERS STAND STILL, and stand APART. Everyone else strolls a slow circuit,
    // which is right for people who live here and wrong for someone at a desk: a recruiter
    // you have to chase is a recruiter you give up on. Fixed posts also make them findable —
    // you learn where the Ash desk is and it is still there next time.
    //
    // They are spread on evenly-divided bearings so three of them in one city never end up
    // standing on each other, which is the thing that would make the choice look like one
    // muddled clump instead of three quarters.
    let qmSeen = 0;
    const qmCount = roles.filter((k) => QM.includes(k)).length;
    for (const key of roles) {
      const ri = ROLES.findIndex((r) => r.key === key);
      const isQm = QM.includes(key);
      const ang = isQm
        ? (qmSeen / Math.max(1, qmCount)) * Math.PI * 2 + 0.4
        : rng() * Math.PI * 2;
      if (isQm) qmSeen++;
      folk.push({
        role: ROLES[ri], ri, s,
        ang,
        // Posted a comfortable way in from the wall — far enough to be inside the town proper,
        // near enough that you meet them on the way through rather than having to hunt.
        rad: isQm ? Math.max(6, Math.min(16, s.rMin - 12)) : 4 + rng() * Math.max(4, s.rMin - 9),
        spd: isQm ? 0 : (rng() < 0.5 ? -1 : 1) * (0.02 + rng() * 0.05),
        bob: isQm ? 0 : rng() * Math.PI * 2,
        still: isQm,
        x: s.x, z: s.z, y: 0,
      });
    }
    this.built.set(s.id, folk);
  }

  /** Only the ones with something to sell are worth labelling. A quartermaster always is —
   *  their stock is generated rather than listed in GOODS, and even a rival's desk is worth
   *  finding on the map so you know whose ground you are standing on. */
  static sells(v) {
    return !!v.role.faction || (GOODS[v.role.key] || []).length > 0;
  }

  update(dt) {
    const want = new Set();
    for (const s of sanctuariesNear(player.x, player.z, VILLAGE.keepRange)) {
      want.add(s.id);
      if (!this.built.has(s.id)) this.populate(s);
    }
    for (const id of [...this.built.keys()]) if (!want.has(id)) this.built.delete(id);

    this.list = [];
    for (const folk of this.built.values()) {
      for (const v of folk) {
        // A slow circuit of the enclosure. They have somewhere to be, and it is here.
        // Quartermasters are the exception: they hold their post, so their spot on the map
        // and their place in your memory of the town both stay put.
        if (!v.still) {
          v.ang += v.spd * dt;
          v.bob += dt * 1.8;
        }
        v.x = v.s.x + Math.cos(v.ang) * v.rad;
        v.z = v.s.z + Math.sin(v.ang) * v.rad;
        v.y = groundY(v.x, v.z) + (v.still ? 0 : Math.sin(v.bob) * 0.04);
        this.list.push(v);
      }
    }
    this.render();
  }

  /**
   * The nearest villager you can actually DO something with.
   *
   * Only traders count. Most of a town's population is keepers — they exist so a settlement
   * reads as somewhere people live rather than a row of shops — and returning them here meant
   * walking up to someone, pressing the trade key, and being shown a full-screen panel with
   * nothing in it. Worse now that quartermasters exist: with ten keepers to four traders, the
   * person you came to see was usually crowded out by someone with no reason to be spoken to.
   *
   * Keepers stay in the world and stay unlabelled. They are scenery, and scenery should not
   * intercept the one key you press to get things done.
   */
  nearest() {
    let best = null, bd = VILLAGE.talkRange;
    for (const v of this.list) {
      if (!Villagers.sells(v)) continue;
      const d = Math.hypot(v.x - player.x, v.z - player.z);
      if (d < bd) { bd = d; best = v; }
    }
    return best;
  }

  render() {
    let i = 0;
    const cap = this.mesh.instanceMatrix.count;
    for (const v of this.list) {
      if (i >= cap) break;
      this._q.setFromAxisAngle(this._up, -v.ang);
      this._m.compose(this._p.set(v.x, v.y, v.z), this._q, this._s);
      this.mesh.setMatrixAt(i, this._m);
      this.mesh.setColorAt(i, this._colors[v.ri]);
      i++;
    }
    this.mesh.count = i;
    this.mesh.instanceMatrix.needsUpdate = true;
    if (this.mesh.instanceColor) this.mesh.instanceColor.needsUpdate = true;
  }
}


