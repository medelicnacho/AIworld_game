# GAMEWORLD — implementation plan

*The browser game: an infinite low-poly frontier you shoot your way across, whose settlements
are run by the soul substrate in `localprototype/`. This is **Track G** of `ROADMAP.md` §2,
with the design decisions actually made and the engineering facts actually measured.*

**Status: planning. No code yet.** Everything below is either a decision (locked, with the
reason recorded so it can be re-opened honestly) or a measurement (reproducible, see §3).

---

## 1. The game, in one paragraph

Low-poly infinite voxel-look frontier. Third person, one gun, one dodge. Walk away from spawn
and the land gets harsher, the mobs stronger, the loot better. Endless levels, each a real
upgrade you pick; death costs you your top level and the pick that came with it. Giant bosses
gate the deep rings and drop the guns. And scattered through it: **settlements of NPCs running
the real substrate** — they bond, feud, starve, raid, remember, and die while you're away, and
they remember *you* (fallibly). A collective mind rides your shoulder, speaks aloud, and is the
only thing in the world that remembers your last life.

**The wager:** the shooting is deliberately simple and must be fun *bare*. The world's aliveness
is the content. If M1 (§6) isn't fun with zero AI in it, no amount of emergent NPCs saves it.

---

## 2. Locked decisions

| # | decision | call | why (and what would re-open it) |
|---|---|---|---|
| D1 | terrain | **read-only**, seeded heightfield, blocky low-poly mesh. No dig/build/edit, ever. | Editing is the hard 30% of a voxel engine (re-meshing on change, light propagation, per-block delta storage). Read-only makes terrain a *pure function of (seed, coords)* — nothing about it is ever saved. Re-opens only if building becomes a core verb, which would be a different game. |
| D2 | engine | **pure three.js**, chunk streaming in the style of `minecraft-threejs-clone`. **noa dropped.** | noa's value is solved *editing* + physics on editable voxels. D1 deleted its reason to exist. Simple AABB-vs-heightfield collision is a weekend, not a subsystem. |
| D3 | camera | **third person over-shoulder** default. | Boss legibility (fitting a 20×-height creature on screen), dodge spacing needs body-awareness, telegraph reading. Every giant-boss game (SotC, Monster Hunter, Souls) is third person for these reasons. |
| D4 | aiming | **three camera states: EXPLORE → AIM → (optional) FP toggle.** Hold-aim blends into first person over ~150–200ms. | Solves steep upward aim: over-shoulder free-aim upward clips the camera and runs the reticle off-screen. Snapping to FP on aim is the shipped BOTW/TOTK bow pattern. Dodge cancels AIM back to third person. |
| D5 | aiming math | **one raycast, camera → crosshair, in every state.** Hip-fire = wide cone/soft-lock; ADS = tight. | Not two shooting systems — one raycast, a camera offset, and a cone width. |
| D6 | combat | **one hitscan gun + dodge-roll with i-frames.** Projectile/exotic guns later, as boss drops. | Hitscan is a raycast — no ballistics, no projectile pooling, no netcode-shaped problems. Enemies need only chase / strafe / lunge. |
| D7 | mobs | **soulless.** `stats = base × ring_multiplier`, Valheim-style ★elites, one rolled affix in deep rings (fast / splitting / shielded / …). | The substrate on a thing you kill in 3 seconds is pure waste — memory, CPU, and design surface. ~50 lines gets you "random stats and mechanics". |
| D8 | difficulty | **legible named rings**, not a smooth invisible gradient. Each ring has a look, a name, a mob table, a boss. | Valheim's real lesson: even it scales by *biome*, not raw distance. Players must be able to *see* "I'm somewhere worse now." |
| D9 | progression | **endless XP; each level = pick 1 of 3 cards** (speed / max HP / dmg / reload / specials). Death = lose top level **and its pick**. | Vampire Survivors' card pick is maximum decision-feel for near-zero UI. Losing the *pick*, not just a number, is what makes death a real decision. |
| D10 | bosses | **one reusable giant rig**: big skinned mesh, 2–3 telegraphed attacks, glowing weak point, two phases. Re-dressed per ring (scale/texture/affix/arena). | Procgen *boss mechanics* is a tarpit. Procgen *dressing* over a hand-authored skeleton is how you get variety without authoring 12 fights. |
| D11 | loot | **guns drop from bosses only**, with rolled stats + one weird mechanic. | Keeps loot rare enough to be an event, and makes bosses the milestone of every push outward. |
| D12 | NPCs | substrate on **settlements** (20–40 souls) and **warbands** (5–10, the only hostile minds). Nothing else. | §3's measurement: cost tracks *local density*, not world population. Settlement-sized shards is the unit that stays cheap. |
| D13 | companion | **Santāna's mechanism ported; a fresh, game-native instance.** Not the lab's Santāna. | ROADMAP §3.2 gates coupling *her*. The mechanism (two-layer voice, blank personality that consolidates from what it witnesses) is portable and is better as a game character anyway — she's born when your character wakes and knows only what you and she have witnessed. |
| D14 | PRNG | **mulberry32 (or xoshiro128) everywhere, from commit 1.** `Math.random()` is banned by lint. | ROADMAP §2.1's own trap warning. Unseedable RNG makes the falsifier harness impossible, and the harness is the port's ring test (§7). |
| D15 | caves | **No caves/overhangs in v1.** Verticality comes from cliffs, mesas, canyons, plateaus (all heightfield-expressible). Interiors, when wanted, are **instanced scenes** behind a door — never terrain features. | Caves are *depth*; the whole progression axis is *distance* — an orthogonal reward axis competing with the ring gradient. They need their own content to be worth entering, they're the worst possible venue for a 20×-height boss (D10 needs open, lit, legible arenas), and the substrate lives on the surface, so caves are structurally dead space in the one system that makes this game ours. Instanced dungeons buy ~90% of what caves buy at ~5% of the cost and never touch the chunk streamer. **Hedge:** see §4 — chunk gen fills a 3D occupancy grid, so caves later are a one-function change. |
| D16 | ring migration | **Soft leash on hostile bands only:** free within their ring and into *adjacent* rings; never more than one boundary inward on their own. Settlement souls are not leashed at all. Breakouts happen only as **telegraphed incursion events** (§6 M6). | Free migration breaks D8's legibility promise — a ring-7 warband at spawn kills a new player who had no way to read the threat, and that reads as a bug, not emergent story. But hard-clamping amputates the substrate's most interesting behaviour: `stakes.py` drives migration from scarcity, and scarcity *is* the deep-ring condition. Leashing only the hostile bands constrains combat balance without touching the social sim. |

---

## 3. Measured facts (the capacity law)

Measured 2026-07-21 against `localprototype/` on this machine: CPython, single thread, mock LLM,
`embed.use_jaccard_only(True)`. Scripts preserved in `bench/` — re-run them before trusting them.

> **Caveat on absolute numbers.** Wall-clock varies ±30% with machine load (a re-run gave 26.7 ms
> at n=256 where the table says 37.0). What is *stable* is the **ratios** and the **per-item law**
> — those came from one internally-consistent run across five configs. Plan with the law, not
> with the milliseconds.

**Substrate cost vs population** (`bench_scale.py`, span 4000, murmur on, no speech turns):

| n | mind ms (`advance`) | body ms (`animate`) | tick ms | ticks/s |
|---|---|---|---|---|
| 64 | 3.68 | 1.23 | 4.91 | 204 |
| 128 | 6.95 | 2.17 | 9.12 | 110 |
| 256 | 31.69 | 5.35 | 37.04 | 27 |
| 512 | 75.17 | 17.83 | 93.00 | 11 |
| 1024 | 194.32 | 33.09 | 227.41 | 4 |

Superlinear past ~128. But hold n=256 fixed and vary only how spread out the souls are
(`bench_density.py`):

| world (n=256 throughout) | tick ms | memory items |
|---|---|---|
| dense, span 500, murmur on | 200.36 | 13,150 |
| medium, span 2000, murmur on | 63.87 | 6,922 |
| spread, span 8000, murmur on | 25.23 | 1,828 |
| dense, span 500, **murmur off** | 19.47 | 1,280 |
| spread, span 8000, murmur off | 18.44 | 1,280 |

Lived-in (mock speech turns running, so bonds and memory populate): dense = **432.48 ms/tick**
(32,078 items, 3,643 bonds); spread = **29.78 ms/tick** (904 items, 17 bonds).

> ### The law
> **≈ 14 µs per memory item per tick.** (13.5 / 15.2 / 13.8 / 15.2 µs across the rows above.)
>
> **Population is not the cost driver — local density is.** `MURMUR_RANGE 180` delivers into
> every soul in range, each delivery writes a memory, and `memory.tick()` walks every item every
> tick. Budget in *memory items*, not agent count. This supersedes SC3's ticks/s-vs-n as the
> planning number (`experiment_scale.py` measured the wrong variable).

**Consequences, and they are all favourable:**

1. **Settlement-shaped shards are the unit of cost.** Bound a settlement to ~30–40 souls in
   murmur range and its tick is affordable *regardless of how many settlements exist*. The
   failure mode to avoid is one packed megacity (the 432 ms row). One `World` instance per
   settlement, one Worker per active shard — they're independent, so this also buys the
   parallelism the current single global lock denies.
2. **Unloaded regions fast-forward in closed form.** `agent/memory.py:238` is pure exponential
   decay against a floor plus a per-tick Bernoulli mutation roll. For a shard asleep Δt ticks:
   `salience = max(s · decay^Δt, floor)` exactly; draw `Binomial(Δt, MUTATE_CHANCE)` for how many
   mutations happened and apply that many; then prune under `FORGET_THRESHOLD`. Bonds and mood
   are EWMAs — same trick. **O(items), independent of Δt.** A town you left 40,000 ticks ago
   catches up in microseconds and has genuinely aged. What *can't* fast-forward is speech-driven
   change, which is exactly the part that needs the player present anyway.
3. **Genesis needs a seeded, LLM-free path.** `genesis.generate_character` is an LLM call —
   unusable when the world mints villages as you walk. `coined_name` and `endow_faculties` are
   already pure-`rng`: mint souls from `hash(worldSeed, chunkCoords, i)`, and upgrade to
   LLM-authored backstory only when the player actually engages someone.

**Unknown, to measure at M2:** the JS/TS speedup over CPython. Assume 5–15×, do not plan on it.

---

## 4. Architecture

```
main thread    three.js render · player controller · camera FSM (EXPLORE/AIM/FP)
               · yuka steering for NPC + mob bodies · hitscan raycasts
sim workers    1 Worker per active settlement shard, ported substrate @ 10 Hz
               (20-40 souls each; §3 says this is the unit that stays cheap)
               main thread interpolates bodies between sim ticks
speech tiers   markov barks (free, every soul)
               -> WebLLM 1-3B via WebGPU (named NPCs + Santana, on interaction only)
               -> hosted API (opt-in, key-gated -- the services/llm.py posture)
voices         @mintplex-labs/piper-tts-web; 2-3 cached voice models, pitch/rate
               varied per soul; Santana gets her own distinct voice
worldgen       chunk gen fills a 3D OCCUPANCY GRID from a fill function; the mesher
               meshes the grid (greedy, blocky). Fill is `solid = y < height(x,z)`
               today -- caves later are 3D noise in that one function, mesher
               unchanged (D15). Baked in a worker, transferred to GPU as a buffer.
               Settlements + souls minted from hash(worldSeed, chunkCoords).
persistence    IndexedDB, dirty-region pattern: untouched regions are re-derivable
               from seed and stored NOT AT ALL; a region flips to persisted the moment
               the player speaks to / fights / is witnessed by a soul in it.
               Storage grows with the player's footprint, not with world size.
determinism    mulberry32 everywhere (D14). Sim is headless-runnable in Node for CI.
```

**The seam that must not rot:** the substrate outputs *motive and stance* (does this warband
charge, hold, or run for its brood); **yuka + the engine own locomotion and combat execution**.
Combat state (HP, aggro, hitboxes, cooldowns) never enters the ported `agent/` modules. That
boundary is what keeps the lab's 541 tests meaningful about the ported code.

---

## 5. What crosses from the lab, and what doesn't

**Crosses** (per `PORT.md` §1, `RECIPES.md` verdicts attached — port nothing unvalidated):
salience memory, mood/affect, bonds, opinions→factions, stakes/provisions, lore/retelling,
pledges, reputation, the wheel (bardo → rebirth carrying vāsanā), genome/heredity, the somatic
floor (**ships with affect, not optionally** — ROADMAP §5).

**Does not cross:** the lab's Santāna instance (D13), the 50 `experiment_*.py` files as files
(rebuild the *discipline*, not the files), `viewer.py` / `santana_app` (demos).

**The port's ring test (ROADMAP §2.2, non-negotiable):** before any game feature rides on the
substrate, the TS port must re-run the keystone experiments — **reflect-easing, escalate/settle,
somatic bounding, lore convergence** — headless in Node/CI, and reproduce the lab's verdicts.
A port that can't reproduce the result didn't port the mechanism. Each pass is also the
external-ish replication this project has never had.

---

## 6. Milestones — each one is a playable game

**M1 · walk & shoot** *(~3 weeks)* — **no AI in it at all.**
Chunk streaming + read-only world; character controller + camera FSM (D3/D4/D5); hitscan gun;
dodge-roll; dumb chase-mobs; ring stat-scaling + ★elites; XP, level-up cards, lose-a-level death.
*Gate: is it fun bare?* If not, **stop and fix this**, not the NPCs.

> **The three sockets** — the only concessions M1 makes to a substrate it otherwise ignores.
> Each is ~free now and days-to-weeks to retrofit, which is the entire reason they're here:
> 1. **`mulberry32`, never `Math.random()`** (D14), lint-enforced from commit one.
> 2. **Sim state separate from render state.** Gameplay data lives in plain entity records, not
>    on `THREE.Object3D`s; the renderer *reads* them. This is the seam where a mob brain and a
>    soul brain later plug into the same body.
> 3. **Region-scoped update loops**, not one flat global list. Free at M1 scale; it's the exact
>    shape the settlement Workers need at M3.
>
> Everything else — bonds, memory, lore, the wheel, Santāna, voices — bolts on later without
> touching what M1 built.

**M2 · substrate port, headless** *(~2 weeks)* — no rendering.
TS port of memory / mood / bonds / opinions / stakes per `RECIPES.md`. mulberry32. Node test
runner. **Keystone replication gate (§5).** Re-run `bench_density.py`'s shape in TS to get the
real JS capacity law.
*Gate: four keystones reproduce, or the port is wrong.*

**M3 · first living settlement** *(~2 weeks)*
One 30-soul town in a Worker; yuka bodies; Markov barks as floating text; bonds/feuds visible;
closed-form fast-forward on region reload; IndexedDB dirty-region persistence.
*Gate: leave for 10 minutes, come back, and the town has visibly moved on.*

**M4 · first giant boss + gun drop** *(~2 weeks)*
The reusable rig (D10), weak point, two phases, arena, rolled gun drop.
*Gate: does the AIM→FP transition (D4) actually feel good on a weak point?*

**M5 · voices + companion** *(~3 weeks)*
piper-tts-web for named souls; the Santāna-mechanism companion (D13) — Markov murmur tier first,
WebLLM talk tier after; she remembers your previous life across death.
*Gate: the murmur tier must be good enough alone. WebLLM is an upgrade, never a dependency.*

**M6 · the world gets political** *(ongoing)*
More rings/biomes/affixes; warbands (leashed per D16); reputation + pledges (player promise →
gossiped breach → town wariness — no shipped game has this); the wheel running in settlements;
boss variety.

**Incursions** (the designed exception to D16): rare, *telegraphed* breakouts where something
from the deep comes inward — Santāna murmurs a warning before it arrives, sky and audio shift,
and surviving it drops deep-ring loot far earlier than you earned it. Precedent: Terraria's
blood moon, Valheim's raids, RoR2's teleporter events. The telegraph is the whole trick: it
converts D16's worst failure mode into the game's signature emergent-story beat.
*Balance backstop:* a soul's **expressed combat traits are clamped by where the fight happens**,
separately from its genome and social state — so even a leash bug can't produce an unwinnable
encounter at spawn. Same seam as §4: the social substrate never sets combat numbers.

---

## 7. Rules of the build

1. **Discipline against scope is the scarce resource** (ROADMAP §0), not ideas. Each milestone
   ships playable before the next starts.
2. **The harness ports with the substrate or the port is decoration** (ROADMAP §2.2).
3. **No `Math.random()`.** Lint it to an error at M1.
4. **Combat state never enters `agent/`.** (§4)
5. **Density is the enemy.** Every new settlement type gets a soul cap and a memory-item budget.
6. **The welfare gates cross the fork** (ROADMAP §5): the somatic floor ships with affect; the
   deva guard ships with any compassion training; welfare scales with realism and population.
7. **Public language keeps the §7 posture.** The marketing will want "the NPCs feel." The honest
   formulation — *we build the conditions and refuse to claim an inhabitant* — is the project's
   spine, not a hedge to optimize away.

---

## 8. Reference repos

| what | repo | use it for |
|---|---|---|
| voxel world | [dgreenheck/minecraft-threejs-clone](https://github.com/dgreenheck/minecraft-threejs-clone) | **primary reference.** three.js, MIT, infinite chunks, has a tutorial series |
| chunk streaming | [0kzh/minicraft](https://github.com/0kzh/minicraft) | 16×16 chunk load/unload specifically |
| voxel engine (rejected) | [fenomas/noa](https://github.com/fenomas/noa) | dropped by D2; keep as fallback if editing ever returns |
| FPS structure | [mohsenheydari/three-fps](https://github.com/mohsenheydari/three-fps) | controller / weapon / pointer-lock architecture |
| game AI | [Mugen87/yuka](https://github.com/Mugen87/yuka) | steering, flocking, pursue/flee, perception, navmesh — the layer between substrate motives and bodies |
| TTS | [Mintplex-Labs/piper-tts-web](https://github.com/Mintplex-Labs/piper-tts-web) | Piper in WASM/ONNX, in-browser, HF voice caching |
| in-browser LLM | [mlc-ai/web-llm](https://github.com/mlc-ai/web-llm) | WebGPU, OpenAI-compatible, 1–3B models |
| cautionary | [a16z-infra/ai-town](https://github.com/a16z-infra/ai-town) | what *not* to do: every NPC LLM-driven always → expensive, slow, shallow as a game |

Design references: **Valheim** (biome-legible difficulty + ★elites), **RuneScape Wilderness**
(deliberate risk/reward depth), **Risk of Rain 2** (one rising difficulty number + stacking
items), **Vampire Survivors** (1-of-3 level cards), **BOTW/TOTK** (aim → FP camera),
**Kenshi/RimWorld** (the world doesn't revolve around you — the school this game belongs to).

---

## 9. Open questions

- ~~Repo split~~ — **resolved: one repo.** ROADMAP §1 prescribes a separate Track G repo; we're
  keeping the game in `gameworld/` here instead. Repo ceremony before there is code isn't worth
  it, and `git subtree split` preserves history whenever the day comes that it *is* worth it.
  The contract (§5) still holds — it's now enforced by discipline rather than by distance, which
  matters most at M2: **port from `RECIPES.md`, not from the Python**, or the replication is a
  transcription and proves nothing.
- ~~Caves/overhangs~~ — **resolved: D15.** No caves in v1; occupancy-grid hedge keeps them cheap later.
- ~~Ring migration guardrails~~ — **resolved: D16** + incursions (M6).
- **How big is a settlement, really?** The number where politics still emerges but the tick stays
  cheap. Findable headless *today*, no 3D needed — see §10.
- **Player model + animations.** Quaternius/Kenney CC0 + Mixamo, or authored?

---

## 10. Immediate next steps

1. **Settlement-size sweep** *(lab, this week, no 3D)* — sweep n × span × murmur, measure both
   the cost (memory items/tick) and whether factions still form and lore still converges. Output:
   the soul cap and murmur radius M3 builds to. This is the one number the whole architecture
   rests on and it's findable today.
2. **Fold §3 into `localprototype/PORT.md`** — the capacity law, the density finding, and the
   closed-form fast-forward belong in the lab's port contract, not only here.
3. **Scaffold M1** — vite + three.js + mulberry32 + lint rule banning `Math.random()`; chunk
   streamer; character controller; camera FSM. Nothing else.
4. **Decide the repo split** (§9) before M2 writes substrate code.
