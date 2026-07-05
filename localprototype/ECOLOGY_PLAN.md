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
| **W3.5 checkpoint** | cultural inheritance (children inherit worldview+noise — fixes blocs dissolving in 1 gen); children never march; **hostility-driven raids** (hatred feeds the next war) | ✅ committed `f975802` (substrate); **gate NOT passed** — see OPEN |
| **W4 EVOLUTION** | heredity + selection on in `--ecology` (rebirth off, lineages end, births carry genomes) | ✅ wired in `--ecology`; **no divergence gate written yet** |
| **W5 VISIBLE BODY** | cockpit v16 — metabolism=SIZE, boldness>0.55=SPIKES, bloc=tinted ring, the LAND rendered (soil tint + pool brightness + name/stores), raids in the chronicle | ✅ committed `db35452`; **no classifier gate yet** |
| **W6 PLAYER** | player acts through the bridge (deeds/pledges/muster already exist) | ⬜ not started |

Run it: `python3 -m santana_app.run --ecology --fresh --llm markov` → cockpit at
`http://127.0.0.1:8767`. (An instance may already be running — check
`data/ecology/runner.pid`.)

---

## THE OPEN PROBLEM — W3's gate (do this first)

`experiment_war.py` (tuning only so far; **no virgin seed consumed** — 231–235 untouched):

- **G1 WARS COME FROM WANT-BESIDE-PLENTY — passes clean in tuning.** Unequal arm
  (lean winters gnaw the crag beside a still-fat vale) raids ~3–4×; fed-for-all arm
  raids 0. The graded-scarcity band, now for war: *uniform* poverty raids nothing (no
  target worth marching for) — the arms are UNEQUAL vs FED, not scarce vs abundant.
- **G2 THE FEUD OUTLIVES ITS FOUNDERS — does NOT hold at a late tick.** Diagnosis is
  clean: the feud **does** cross the generational handoff (traced: t=400, 14 newborns
  carry it, 0 founders alive) but then **fades**, because (a) wars stop once population
  recovers to self-sufficiency, so no fresh grievances, and (b) `memory.py` has **no
  `salience_floor`** field, so a grievance decays unless retold. The W3.5 hostility-
  feedback (grudge lowers the hunger threshold; targets chosen by grudge×3+fatness) is
  the attempt to make feuds self-sustaining — **not yet verified in tuning.**

**Next actions on G2, in order:**
1. Re-run the tuning trace with the hostility-feedback: does war now RECUR (raids keep
   climbing past t=400 as grudges compound), keeping the feud fresh?
2. If war recurs but the feud still decays between raids, add a real **`salience_floor`**
   to `agent/memory.py` (decay never drops a memory below its floor) and give grievances
   ~0.5 — the §5.16 legend-keeper logic, made a first-class field. Small, principled.
3. Only when **G2 holds in tuning** (feud carried by non-founders at the FINAL tick,
   ≥4/5) run the held-out verdict on virgin **231–235** and record in FINDINGS as §5.28.
   If G2 can't be made to hold, record the honest finding instead: *"wars here are wars
   of desperation that end when desperation ends; a single raid's grievance crosses one
   generation but fades with the peace — perpetual feuds need continuous conflict."*

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
- A cooperative town is ONE blob (all-warm, zero enmity) — territory/war need the opinion
  dynamics' out-groups (§5.26). `--ecology` seeds opinions on every founder.
- War needs INEQUALITY (want beside plenty), not uniform scarcity — the graded-band lesson.
- `memory.py` has no `salience_floor` yet — grievances decay (the G2 blocker).
- `ls tests/` before creating a test file; check the **collected** count, not the pass line.
