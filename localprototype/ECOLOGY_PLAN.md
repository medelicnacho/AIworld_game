# ECOLOGY_PLAN.md — the evolution game (factions, war, evolving bodies)

*Handoff doc, 2026-07-04. The plan for turning the validated NPC substrate into an
actual ecology game: emergent factions that fight and ally over scarce land, real
death, heredity, and stats worn on the body so you watch bloodlines diverge. Every
stage has a falsifiable gate. Read this + `WRITEUP.md` (what the project is) +
`RECIPES.md`/`FINDINGS.md` (the validated mechanisms) to resume cold.*

## The vision (one paragraph)

A spatial world of scarce **regions** (rich vales, harsh crags). Souls with heritable
bodies (the genome) live, bond, and split into **emergent factions** (opinion dynamics —
never assigned). Factions take **territory** (validated, V2 5/5), compete for food, **raid**
each other when a lean granary faces a fat one, **ally** against a shared enemy, and carry
**grievances across generations** as land-keyed legends. Selection acts through real famine
and real war, so faction **bloodlines diverge**. Every stat is worn on the **body**, so
evolution is something you *watch happen*. The player enters last, through the karma roads
that already exist (deeds witnessed, pledges, the muster).

## Standing rules (travel with every stage)

- **Welfare in war:** somatic floor stays on (the worn refuse to fight — verdict 5/5);
  war dead are mourned and their lineages END (the E2 death, no bardo); casualties capped;
  **no cruelty verbs** — conflict is over food and grievance, never torment. Written before
  the mechanic, not after.
- **Isolation:** the ecology runs as its own world (`--ecology`, cockpit :8767, life at
  `data/ecology/`), never touching her town (:8765) or the group town (:8766) or the live
  long-experiments.
- **The house discipline:** pre-registered claims, tuning seeds 11–15 vs virgin verdict
  seeds, failures recorded as findings, `ls` before creating any file in `tests/` (a
  `cat >`/Write clobbered `test_factions.py` once — see the never-clobber memory).

---

## STATUS (what's built)

| stage | what | state |
|---|---|---|
| **W1 LAND** | `world/regions.py` — COLS×ROWS grid, seed-shuffled soils (1.3 vale … 0.5 crag), per-region commons pools; stakes economy routed through the ground underfoot | ✅ committed `d35912c`, 4 tests |
| **W2 FACTIONS** | `world/factions.py` — pure reads over the opinion dynamics: `factions_of` (union-find on cosine≥0.45), `leader_of` (most trusted by its own), `home_region`, `banner_of` ("the folk of the vale") | ✅ committed `bbe8d09`, 3 tests (`test_faction_groups.py`) |
| **W3 WAR (mechanic)** | `world/war.py` — raids over lean granaries; the muster decides who marches; allies join; bodies fight; dead mourned + lineages end; land-keyed grievances gossip | ✅ mechanic committed `d8379ca`, 4 tests |
| **W3.5 checkpoint** | cultural inheritance (children inherit worldview+noise — fixes blocs dissolving in 1 gen); children never march; **hostility-driven raids** (hatred feeds the next war) | ✅ committed `f975802`; **GATE PASSED 2026-07-05** — G1 5/5 ×20, G2 5/5 (FINDINGS §5.28); took the heir fix + salience_floor + the hearth (see RESOLVED below) |
| **W4 EVOLUTION** | heredity + selection on in `--ecology` (rebirth off, lineages end, births carry genomes) | ✅ wired in `--ecology`; **no divergence gate written yet** |
| **W5 VISIBLE BODY** | cockpit v16 — metabolism=SIZE, boldness>0.55=SPIKES, bloc=tinted ring, the LAND rendered (soil tint + pool brightness + name/stores), raids in the chronicle | ✅ committed `db35452`; **no classifier gate yet** |
| **W6 PLAYER** | player acts through the bridge (deeds/pledges/muster already exist) | ⬜ not started |

Run it: `python3 -m santana_app.run --ecology --fresh --llm markov` → cockpit at
`http://127.0.0.1:8767`. (An instance may already be running — check
`data/ecology/runner.pid`.)

---

## RESOLVED — W3's gate (2026-07-05, FINDINGS §5.28)

**Verdict on virgin 231–235: G1 PASS (20 scarce raids vs 0 abundant pooled, ×20, every
seed) and G2 PASS 5/5 at 100% turnover** — at t=1500 (~8 generations) ~43/44 souls
carry the feud, none of whom fought it. What the plan's step-1 trace actually found:

- **War does NOT recur** — the hostility-feedback cannot outlive the founders because
  hostility is keyed to soul ids, never decays, and is never inherited: after full
  turnover the grudge points at the dead. Wars of desperation END here (the crag bloc
  starves below muster strength — differential survival working). The feud persists
  anyway; the two claims decoupled cleanly.
- **The real G2 killer was the heir gap**: with rebirth OFF, `Agent.reproduce()` heirs
  carried NO genome and NO belief_vec — blocs starved to loners in 3 generations and
  selection silently reset on the age-death channel (a W4 bug too). Fixed:
  `World._endow_heir` (germ line heredity-gated + noisy worldview), pinned in tests.
- **`salience_floor` was necessary but not sufficient**: the floored feud survived in
  its holders, who died with it — `lore.pick()` tells only each soul's TOP story, and
  fresh mourning-lore (~0.78) always outbids a floored grievance (0.5), so generation
  three never heard it. The missing channel is **the hearth** (`World._hearth`): floored
  stories cross AT BIRTH in the parent's current words (source="lore", provenance
  honest). The validated §5.16 square-retelling is untouched.

Left deliberately unbuilt (recorded as caveats in §5.28): a memory-derived grudge
(floored feud-tags read as standing hostility toward whoever holds that land) if
recurring generational war is ever wanted; a forgiveness path (floor-erosion on warm
cross-bloc bonds) — today a grievance never fades in a living line.

---

## THE REMAINING GATES (after W3)

- **W4 evolution gate** (`experiment_ecology_evolution.py`, new): warring/harsh-region
  lineages diverge genetically from peaceful/valley ones beyond a drift null; the
  Quality-Diversity check (EVOLUTION.md) — harsh vs valley bodies reach DIFFERENT
  answers, not one super-soul. Virgin seeds 241–245.
- **W5 visible-body gate**: a blind classifier reads genome/faction from the drawn shape
  alone (size/spikes/ring) beyond chance — the visuals carry real information or they
  don't ship as "you can see evolution." Can reuse the drawing-stats approach.
- **W6 player**: `/bridge/act` already lands deeds/pledges on validated roads; add
  `join_faction`/`raid_with` verbs that route through the muster. Gate: a player's
  warband assembles from earned history (loyalty's measured price, already 5/5).

---

## KEY FILES / SEAMS

- `world/regions.py` — the land (pools, soils, `pool_level/add/take/scale_all`)
- `world/factions.py` — seeing blocs (all pure reads; `from agent.agent import _cosine`)
- `world/war.py` — `war_tick(world)`, called by the wheel every `RAID_CHECK=40` ticks when
  `war_enabled`; **welfare invariants live in its docstring**
- `world/sim.py` — gates `regions_enabled/regions`, `war_enabled/_war_log` (both default
  off, snapshot-compat defaults = THE RULE); cultural inheritance in `_birth_from`; war
  hook at "2.55" in `step()`
- `santana_app/run.py` — `--ecology` mode (founders get germ lines + opinions; seasons +
  mourning + heredity + selection; rebirth OFF)
- `santana_app/ui.py` — snapshot carries `land`/`bold`/`metab`/`fac`; `drawLand()` +
  shaped bodies; raid bus hook → chronicle; **cockpit UI_VERSION=16** (bump on any
  dashboard change or stale tabs won't self-reload)
- `experiment_war.py` — the G1/G2 falsifier (tuning only)

## GOTCHAS PAID FOR (don't re-learn)

- Blocs dissolve in one generation without cultural inheritance (fixed in `_birth_from`).
- **Age-death heirs (`Agent.reproduce`) crossed NO genome and NO worldview** — the
  invisible channel that undid both W3 and W4 for two commits; `_endow_heir` now closes
  it (heredity-gated germ line, THE RULE). If a lineage looks "reset", check the heirs.
- A cooperative town is ONE blob (all-warm, zero enmity) — territory/war need the opinion
  dynamics' out-groups (§5.26). `--ecology` seeds opinions on every founder.
- War needs INEQUALITY (want beside plenty), not uniform scarcity — the graded-band lesson.
- `salience_floor` keeps a wound in its holder but NOT in the town: the retell lottery
  (top-1 story) starves old wounds under a steady drumbeat of fresh mourning-lore. Feuds
  cross generations at the HEARTH (`_hearth`, at birth), not in the square.
- An "ally" threshold ≥ `factions.ALIGN_AT` is unsatisfiable (union-find has already
  merged such blocs) — allies live BELOW the same-bloc line (`war.ALLY_AT=0.2`).
- `run.py --ecology` used to refill all granaries on EVERY restart (now only `--fresh`
  or tick 0) and never enabled `lore_enabled` (now it does — feuds need the channel).
- Hostility is id-keyed, never decays, never inherited — it cannot carry a feud across
  turnover; the feud's carrier is the floored memory, not the hostility dict.
- `ls tests/` before creating a test file; check the **collected** count, not the pass line.
