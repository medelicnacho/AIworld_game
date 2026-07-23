# CONTENT.md — the enemy, elite and boss backlog

*Researched 2026-07-22 against Risk of Rain 2, Diablo 3, Terraria and Doom Eternal (sources
at the bottom). Everything here is mapped to systems that already exist — blast(), the
knockback state, the caster/flyer brains, the beam, flocking, the tier gradient — so cost
estimates are honest.*

## 0. The one insight that pays for everything else

**Affixes multiply content; new enemies add it.** Diablo 3 built decades of variety from
~25 composable elite modifiers on ONE monster roster. Risk of Rain 2 ships five elite types
that recolour existing enemies and change one rule each. Neither builds new creatures per
difficulty band — they build *modifiers that stack*.

We already have the seed of this (★elite = bigger/tougher, casters, flyers). The cheapest
path to "way more content" is a real **affix system**: each affix is one rule + one colour,
they roll independently, and deep tiers roll two or three at once. Ten affixes ≈ 100+
distinct encounters at combinatorial cost.

**The RoR2 design bar (worth keeping taped to the monitor):** a good elite "complicates
matters subtly" — it changes *how you fight it*, not just its numbers. And the Doom rule:
every enemy is a chess piece that asks a **question**; if two enemies are answered the same
way, one is decoration.

---

## 1. Elite affixes (rollable on ANY mob, stack at depth)

Ordered by value ÷ cost. Colour is the tell — one affix, one hue, always.

| affix | rule | asks | cost |
|---|---|---|---|
| **Burning** | leaves a fire trail where it walks (RoR2 Blazing / D3 Molten) | stop fighting where it has been | trivial: drop `blast()`-style ground patches on a timer |
| **Dying burst** | explodes on death, telegraphed ring for 0.8s | kill it, then LEAVE | trivial: `blast()` on despawn + a mark |
| **Shielded** | immune from the front arc; flank or wait for the turn | positioning, not aim | small: dot-product check in `hit()` |
| **Vampiric** | heals its packmates when it hits you | focus it FIRST | small: heal-in-radius on `onPlayerHit` |
| **Warding** | projects a bubble; packmates inside take half damage | kill the ward through its own bubble | small: damage multiplier if within radius of a warder |
| **Puller** | periodically yanks you toward it (D3 Vortex) | save your dodge for the yank, not the lunge | small: reuse the knockback state with negative force |
| **Waller** | throws up a short block wall behind you when it engages (D3 Waller) | it cuts off retreat — commit or dash out | medium: 3–4 temporary wall segments using sanctuary-wall pieces |
| **Splitting** | dies into 2–3 fast weaklings | the kill is not the end | small: spawnOne ×2 on death |
| **Frost** | its hits slow you 40% for 2s | getting touched now compounds | small: a speed debuff timer on the player |
| **Phasing** | briefly untargetable every few seconds, shimmer tell | hold fire for the window — trigger discipline | small: skip in `targets()` while phased |

Deep-tier rule: tier 3+ can roll two affixes, tier 6+ three. A **Burning-Warding-Puller**
star at tier 7 is a completely different fight from any of its parts — that's the
combinatorial payoff.

## 2. New enemy silhouettes (each must ask a NEW question)

Current roster answers: encircle (melee pack), close-the-gap (violet ranged), look-up (red
flyer). Missing questions, in the order I'd add them:

1. **Charger** — long telegraphed straight rush, big damage, long recovery. *Question:
   sidestep timing.* Doom's Pinky. Reuses the lunge code with 4× range and a wind-up glow.
2. **Swarm** — tiny, fast, 1-shot HP, spawn in 10–15, only dangerous in numbers. *Question:
   crowd verbs (Ring of Fire finally has a dedicated customer).* Reuses flocking with
   tighter cohesion; instanced rendering already affords the count.
3. **Artillery** — stationary once planted, lobs SLOW arcing shells at long range with
   D3-Arcane-style ground markers. *Question: keep moving between cover, close the gap.*
   Reuses meteor telegraph + caster standoff.
4. **Healer** — flees you, channels a visible beam that regenerates its pack. *Question:
   target priority under pressure.* Reuses the flee force + a beam visual.
5. **Burrower** — submerges (untargetable), dirt-plume trail, erupts under you with a 1s
   ground ring. *Question: watch the ground, not the horizon.* Medium cost; the plume is
   the telegraph, the eruption is `blast()`.

## 3. Bosses — one rig, rolled attack sets (the Terraria lesson)

Terraria's best fights are **phase changes that alter the rules mid-fight** (Plantera's
tunnel-chase → bullet-hell; Eye of Cthulhu's 65%-HP snap into aggression), not bigger
numbers. And its worst-beloved trick is the best cheap one: **the boss summons adds**, so
the arena decays around you.

Current rig has: meteors, hunting beam, phase-2 rage. Build to a pool of attack sets and
**roll 2 of N per boss** (plus tier-gated guarantees):

| attack set | rule | reuses |
|---|---|---|
| **Summoner** | periodically calls 4–6 swarm mobs from the ground | spawnOne + a ground-ring tell |
| **Shockwave stomp** | expanding ground ring you must JUMP (not dodge sideways) | the fire-ring mesh + a jump-height check |
| **Mirror images** | phase 2: two half-scale decoys with small HP, only the real one keeps the core | the boss rig ×2, `targets()` tags |
| **Enrage timer** | volleys accelerate 1% per second alive — soft DPS check, rewards commitment | one multiplier |
| **Meteor rain → safe ring** | phase 3: everything is marked EXCEPT a moving safe circle — inverted telegraph | existing meteor pool, inverted |
| **The leash snap** | if you kite too far it roars, becomes invulnerable, and CHARGES back — repositioning the arena | boss movement + the roar |

Then two genuinely new rigs when the pool feels thin:
- **The Serpent** (Terraria's Destroyer): segmented body, only the head takes full damage,
  weaves through terrain. Segments = one InstancedMesh.
- **The Warden** (for cities later): humanoid, sword arcs telegraphed as ground sectors —
  a melee boss, which the roster completely lacks.

## 3b. World bosses — roaming and persistent, not spawned-on-demand (requested 2026-07-23)

A real redesign of how bosses exist, and its own build. Today there is ONE boss, conjured
near you when you're eligible and despawned after. The ask: bosses ROAM the world, each ring
holds SEVERAL, they respawn SLOWLY, and deeper/bigger rings hold MORE — so clearing a ring's
bosses means the ring is genuinely clear until they come back, and hunting them is a thing
you go and do rather than a thing that spawns at you.

Approach (the honest cost is in the multi-boss rewrite):
- **From `this.alive` to a LIST.** `boss.js` currently assumes a single boss; the meteor and
  beam pools are shared for that one. Multiple simultaneous bosses need either per-boss pools
  (memory) or a shared pool the near boss draws from (cheaper, and only the nearest boss or
  two are ever really fighting you at once).
- **Persistent, seeded homes.** Each ring seeds N boss "territories" from the world seed (like
  settlements), N growing with the ring — bigger rings, more bosses. A boss exists at its
  territory whether or not you're there; only bosses within the sim radius get full AI and a
  mesh (stream like mobs/sanctuaries), the rest are just "alive/dead + respawn timer" state.
- **Roaming.** A live boss wanders its territory (slow, the existing speed) instead of homing
  on you until you enter its aggro range — then the current fight rig takes over.
- **Slow respawn.** Kill one and its territory goes dormant for a long timer (minutes), so a
  cleared ring stays cleared for a while. A "bosses: 3/5 alive in this ring" read makes the
  clearing legible.
- **Ties into GEAR.md:** a roaming boss you can find on purpose is the natural source of the
  guaranteed high-ilvl drop, and "go kill the three bosses of ring 4" becomes real content.

Gate: you can walk a ring, find and kill its bosses one by one, see the ring empty of them,
and come back later to find some respawned — with no boss ever conjured out of thin air at you.

## 4. Town NPC ideas (for when the substrate lands)

- **Bounty keeper** — names a specific elite pack ("the Burning star west of town"),
  double points on it. Cheap: pick a live pack, tag it, check the kill. First quest-shaped
  thing, no quest system needed.
- **Gate warden** — a town NPC with a gun who actually shoots hostiles that come within
  range of the gate. Makes safety feel *defended* rather than decreed.
- **Caravan** — a walking mini-town: 3 pack animals + 2 guards travelling between
  settlements on the roads the nomad bands already walk. Protect it (or just travel with
  it) for points. Reuses folk band movement wholesale.
- **The hermit** — one NPC in the wilds per tier, sells ONE random affix-ware cheap.
  Reason to explore off the town bearings.

## 5. The implementation plan — slices C1–C7, each with a gate

*Same discipline as STAGES.md: a slice is done when its gate question is answered honestly
in play, not when the code runs. Cross-cutting rules for every slice:*

- *Every affix/enemy gets an **admin spawn button** the same day it gets code — testing a
  tier-6 combination must never require walking to tier 6.*
- *One affix = one colour = one rule. If it needs a tooltip to understand in the field, it
  fails its gate.*
- *Ground effects come from **pools**, like meteors and impacts — never allocated per use.*

### C1 — the affix engine ⏱ ~2 days
The foundation everything else plugs into.
- [ ] Affix registry: `{id, name, color, minTier, weight, hooks}` — hooks for `onSpawn`,
      `onTick`, `onHitPlayer`, `onDeath`, and a `targets()` filter (Phasing needs it)
- [ ] Roll in `rollStats()`: elites roll 1 affix at tier 1+, 2 at tier 3+, 3 at tier 6+
- [ ] Colour: the FIRST affix owns the body tint (elites stay gold-marked via scale);
      second/third affixes show as a slow colour pulse between their hues
- [ ] Admin: a per-affix spawn row in the panel (spawn one pack with exactly these affixes)
- [ ] HUD kill feed names the affixes ("★ burning-splitting down")
- **Gate:** in a mixed camp you can name every affix present from colour + behaviour alone.

### C2 — affix wave 1: Dying Burst · Burning · Splitting ⏱ ~1 day
The cheapest three, all reusing `blast()` / `spawnOne()` / pooled ground marks.
- **Gate:** you catch yourself *leaving* a fresh kill, *routing around* scorched ground,
  and *holding a shot* for the split — behaviour change, not stat change.

### C3 — the two missing silhouettes: Swarm · Charger ⏱ ~4 days
- [ ] Swarm: 10–15 per spawn, 1-shot HP, tight flock, fast — Ring of Fire's customer
- [ ] Charger: wind-up glow → long straight rush (the lunge code at 4× range) → a genuine
      recovery window where it is helpless
- [ ] Spawn tables mix silhouettes per tier instead of one roll for everything
- **Gate:** you change behaviour on silhouette alone, before reading colour or count.

### C4 — boss attack sets ⏱ ~1 week
- [ ] Refactor volley/beam into a pool of attack sets; each boss rolls 2, tier-gated
- [ ] **Summoner** and **Shockwave stomp** (jump, don't strafe) first
- [ ] **Enrage** (volleys accelerate 1%/s alive) third — the soft DPS check
- [ ] Mirror Images and the inverted safe-ring phase later, they're the expensive ones
- **Gate:** two consecutive bosses at the same tier play differently enough to name.

### C5 — the tactical affix band: Shielded · Warding · Puller · Frost · Phasing ⏱ ~3 days
Tier 3+ material — these ask positioning/priority questions, so they need the player to
already speak the game's basic language.
- **Gate:** a Warding star changes your TARGET ORDER, a Shielded one your POSITION.

### C6 — Artillery · Healer, then the Serpent rig ⏱ ~2 weeks
The last two questions (cover, priority-under-pressure), then the first genuinely new boss
skeleton once the attack-set pool feels thin.

### C7 — town content: Bounty keeper · Gate wardens · Caravan · Hermit ⏱ ~1 week
Deliberately LAST among the combat slices but before the substrate: these are also the
fake-data narration groundwork — a bounty keeper naming a real elite pack is the first
sentence the town ever says about the world, and it needs no simulation behind it.
- **Gate:** a new player finds and completes a bounty without being told the system exists.

Sources: [RoR2 elite design analysis](https://parryeverything.com/2021/08/13/the-elites-of-risk-of-rain-2-efficient-design-and-the-fundamentals-of-real-time-combat/) ·
[RoR2 monsters wiki](https://riskofrain2.wiki.gg/wiki/Monsters) ·
[D3 elite affix mechanics](https://maxroll.gg/d3/resources/elite-affixes) ·
[D3 affix strategy](https://blizzardwatch.com/2015/07/11/combat-elite-monster-affixes-diablo-3/) ·
[Terraria boss encyclopedia](https://www.playterraria.com/terraria-bosses/) ·
[Doom Eternal combat-puzzle design](https://www.gamespot.com/articles/doom-eternal-is-a-fantasy-combat-puzzle-but-what-d/1100-6467505/) ·
[Doom 2016 AI](https://www.gamedeveloper.com/design/cyber-demons-the-ai-of-doom-2016-) ·
[Doom Eternal combat evolution Q&A](https://www.gamedeveloper.com/design/q-a-evolving-the-combat-design-of-id-software-s-i-doom-eternal-i-)
