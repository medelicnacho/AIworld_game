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
import { settlementFloorAt } from "../world/sanctuary.js";
import { sanctuariesNear } from "../world/sanctuary.js";
import { GOODS } from "../ui/shop.js";
import { mulberry32 } from "../rng.js";
import { isHostileSanctuary, FACTIONS } from "../prog/factions.js";

// A SMALL faction town wears its colours on its PEOPLE: keepers and the smith are tinted the
// town's war colour, so the whole settlement reads as one allegiance from across a field.
// The working vendors stay legible by KEEPING their trade colours — green herbalist, black
// adept — and the quartermaster goes RED: the one desk that matters most in a faction town,
// wearing the one colour no faction owns. Cities stay as they are — grayish civilians with
// the three war-coloured desks side by side — because neutral ground should look neutral.
// (Iron's black is lifted a shade, same as its guards, so a town of them reads at distance.)
const TOWN_TINT = { 0: 0x32323a, 1: 0x3f6fd1, 2: 0x4fae5a };   // war-colour space
const QM_TOWN_RED = 0xd23c3c;

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
  //
  // They wear their faction's WAR colours — the exact colours the mobs fly (FACTION_COLORS:
  // blue/green/black). In a city the three desks side by side read as three armies' embassies,
  // and the colour you have learned to fight (or fight beside) is the colour at the desk.
  { key: "qm_ash", name: "Ash Quartermaster", color: 0x3f6fd1, faction: "ash" },
  { key: "qm_vale", name: "Vale Quartermaster", color: 0x4fae5a, faction: "vale" },
  { key: "qm_iron", name: "Iron Quartermaster", color: 0x26262c, faction: "iron" },
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
    // A RIVAL faction's town has NO villagers at all. Its people ARE the garrison
    // (town/raid.js): a war-camp of fighters in the town's colour, led by the three
    // champions in their trade colours. A civilian idly strolling through a raid read as
    // someone who forgot to fight — every body on hostile ground is now a combatant.
    const hostile = isHostileSanctuary(s);
    if (hostile) { this.built.set(s.id, []); return; }
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

    // QUARTERMASTERS STAND STILL, and stand TOGETHER. Everyone else strolls a slow circuit,
    // which is right for people who live here and wrong for someone at a desk: a recruiter you
    // have to chase is a recruiter you give up on.
    //
    // The three quarters line up SIDE BY SIDE in one place — a recruiting row — rather than
    // being scattered around the walls. Choosing a side is meant to be one moment where you
    // weigh three options against each other, and you cannot weigh what you have to walk a
    // town to find one at a time. A short row on a fixed radius and heading, close enough to
    // stand shoulder to shoulder but spaced so they never overlap: findable, comparable, and
    // the same spot every time.
    // The town's tint (small faction towns only): civilians wear the colour, vendors keep
    // their trades, the quartermaster turns red. See TOWN_TINT above.
    const townCol = (!neutral && s.faction !== null && s.faction !== undefined)
      ? TOWN_TINT[FACTIONS[s.faction % FACTIONS.length].ally] : null;
    const qmRoles = roles.filter((k) => QM.includes(k));
    const qmCount = qmRoles.length;
    const QM_RAD = Math.max(6, Math.min(15, s.rMin - 12));
    const QM_HEADING = 0.6;          // which way the row sits from the centre — fixed, so it
                                     // is in the same place in every town you ever enter
    const QM_SPACING = 3.6 / QM_RAD; // ~3.6 world units apart, as an angle at this radius

    // THE MARKET ROW, beside the recruiting row — cities only.
    //
    // A city is the place you come back to with a full bag, and the three people who empty it
    // were scattered on random bearings and STROLLING, so restocking meant three laps of the
    // largest enclosure in the game hunting moving targets. The quartermasters solved exactly
    // this for themselves years ago (see above) and the reasoning applies wholesale: someone
    // standing at a counter should be where the counter is.
    //
    // So in a city the herbalist, smith and adept form a second short row on the same radius,
    // just around the arc from the desks — one visit, four people, everything a city is for
    // within a few paces. Towns keep their strollers: a hamlet with four residents is small
    // enough to cross at a glance, and people wandering is most of what makes it feel lived in.
    // ONE OF EACH, not all of them. A city's roster carries two herbalists, two smiths and
    // two adepts — which nobody ever noticed while they were scattered on random bearings,
    // and which turned the first version of this row into six people strung across eighteen
    // units of arc. A counter you have to walk the length of is the problem this was fixing.
    // The first of each trade takes the desk; the second keeps strolling, and a city having
    // spare tradesfolk wandering about is exactly right for the biggest place in the world.
    const TRADE = ["herbalist", "smith", "adept"];
    const tradeRow = s.city ? [...new Set(roles.filter((k) => TRADE.includes(k)))] : [];
    const posted_ = new Set();
    // Far enough round that the two rows read as separate counters rather than one crowd,
    // close enough that both are in frame at once when you walk up to either.
    const TRADE_HEADING = QM_HEADING + (qmCount * QM_SPACING) / 2 + 5.2 / QM_RAD;
    const TRADE_SPACING = 3.6 / QM_RAD;
    let qmSeen = 0, tradeSeen = 0;
    for (const key of roles) {
      const ri = ROLES.findIndex((r) => r.key === key);
      const isQm = QM.includes(key);
      // Only the FIRST of each trade is posted — see tradeRow.
      const isTrader = tradeRow.includes(key) && !posted_.has(key);
      if (isTrader) posted_.add(key);
      let ang;
      if (isQm) ang = QM_HEADING + (qmSeen - (qmCount - 1) / 2) * QM_SPACING;
      else if (isTrader) {
        ang = TRADE_HEADING + (tradeSeen - (tradeRow.length - 1) / 2) * TRADE_SPACING;
        tradeSeen++;
      } else ang = rng() * Math.PI * 2;
      if (isQm) qmSeen++;
      const posted = isQm || isTrader;    // anyone at a counter stands at it
      // Colour override, town scheme: civilians carry the flag, the QM desk goes red,
      // herbalist and adept keep the trade colours you learned in the spawn town.
      let col = null;
      if (townCol !== null) {
        if (isQm) col = QM_TOWN_RED;
        else if (key === "keeper" || key === "smith") col = townCol;
      }
      folk.push({
        role: ROLES[ri], ri, s,
        // WHO this body is, permanently. populate() is deterministic per town, so the
        // index survives every rebuild (faction switches, walking away and back, reloads)
        // — which makes it the one field identity may hang from. It exists because names,
        // voices and chat memory once hashed the walk angle instead, believing it fixed;
        // strollers update it every frame, so a villager's NAME changed as she walked her
        // circuit and her memory of you shattered across the moments of her stroll.
        uid: folk.length,
        col: col !== null ? new THREE.Color(col) : null,
        ang,
        rad: posted ? QM_RAD : 4 + rng() * Math.max(4, s.rMin - 9),
        spd: posted ? 0 : (rng() < 0.5 ? -1 : 1) * (0.02 + rng() * 0.05),
        bob: posted ? 0 : rng() * Math.PI * 2,
        still: posted,
        x: s.x, z: s.z, y: 0,
      });
    }
    this.built.set(s.id, folk);
  }

  /** Which towns are hostile depends on WHOSE colours you wear, so populated towns must be
   *  rebuilt when the player joins or switches factions — otherwise the old faction's view
   *  of who serves you keeps walking around. */
  refresh() { this.built.clear(); }

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
        v.y = settlementFloorAt(v.x, v.z) + (v.still ? 0 : Math.sin(v.bob) * 0.04);
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
      this.mesh.setColorAt(i, v.col || this._colors[v.ri]);
      i++;
    }
    this.mesh.count = i;
    this.mesh.instanceMatrix.needsUpdate = true;
    if (this.mesh.instanceColor) this.mesh.instanceColor.needsUpdate = true;
  }
}


