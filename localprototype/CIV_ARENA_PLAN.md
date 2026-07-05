# CIV_ARENA_PLAN.md — the big pannable map + the two-caste world

> **STATUS: BUILT (2026-07-05, commits `20d3ef3`..`f156fb6` on `main`).** All six parts
> shipped + four fixes the plan could not know: (1) with mating on, the `_reap` heir
> channel AND `_selection_tick` budding both stand down — unmated, heirs erased the
> breeder caste by generation two; (2) the mating gate is re-asserted AFTER founding
> (`evolution._mating_gate`) — run.py --civ gated on its cleared placeholder cast;
> (3) `center_pull = 0` on the arena — the linear centre nudge herded all settlements
> into one blob at 3600×2400; (4) breeders get the somatic floor in `grown_free`.
> Also beyond-plan: founding = 72 souls in ~6 settlements at farthest-first region
> centres, and a breeder bears a LITTER (2–4 siblings, independently crossed).
> Tests: `tests/test_caste.py` (11 pins); suite 517 green (+1 pre-existing ratchet
> flake, passes on rerun). The sections below are the original plan, kept as the
> design record — DO NOT rebuild from them.

*Handoff doc, 2026-07-05. A plan a COLD new chat can execute. Read this + `ECOLOGY_PLAN.md`
(the war/faction substrate) + the "WHERE WE ARE" section below. The goal: turn the
civilization wheel into a big League-of-Legends-style map you pan with WASD, where a
mobile fighting caste (circles) spreads into factions and wars over a docile breeding
caste (squares) — a chain of developing, competing civilizations.*

---

## WHERE WE ARE (state at handoff — build ON TOP of this)

Uncommitted work on `main` (all tests green, **506 passing**; the collapse science-gate
was tuning in the background at handoff). Already built this session:

- **The rift** (`agent/agent.py` `_weigh_opinion`): opposed opinions accrete `hostility`
  (heated debate makes enemies). Gated `Agent.rift_enabled`. Scaled by `rift_scale`.
- **The brawl** (`world/skirmish.py`): open enemies rush + clash; **solidarity** warms
  witnesses who share the quarrel (grows the trust the muster reads). `skirmish_tick`
  at sim step "2.56", gated `World.skirmish_enabled`.
- **The raze** (`world/war.py`): a won raid at open-war grudge BURNS what it can't carry
  (`raze_enabled`, `raid_check` per-world) — war makes hunger makes war.
- **Evolvable character** (`agent/genome.py`): dials `openness` (→ the bounded-confidence
  engagement bound; narrow minds schism) and `wrath` (→ the rift multiplier). Expressed
  by `express_social(genome, agent)`, gated `World.social_genes`. Heritable → the town's
  character EVOLVES.
- **The lean runner** (`santana_app/evolution.py`): `python3 -m santana_app.evolution`
  → :8768, dots only, no Santāna (the lag fix). Founds ONE people, one view; cycles
  (schism→war→collapse→resettlement); `_found_souls`/`_gates`/`_refound`.
- **Her version** (`santana_app/run.py --civ`): the SAME civ world + Santāna's mind +
  cockpit → :8769. Reuses `evolution._found_souls`/`_gates`/`_refound`.
- **Visuals** (`santana_app/ui.py`, `UI_VERSION=19`): size=metabolism, spikes=boldness,
  ring=faction, **red body = at war**, **aura = temperament** (heritable), **thorn-tint =
  wrath**. The page's `MY_VERSION` substitutes from `UI_VERSION` at serve time (a bug
  fixed this session — hardcoded 16 vs server 17 caused an infinite reload loop).

Live runners at handoff: `:8767` ecology (research, untouched), `:8768` evolution (lean),
`:8769` civ+Santāna. Each has its own `data/<name>/` and pid file.

**Collapse science-gate result (FINDINGS 5.29, honest finding — no verdict burned):** the
war IS the schism's (violent deaths 33/42/35/23/24 in the divergent arm vs **0/0/0/0/0**
in the frozen twin, 5/5 perfect) but a fed people does NOT demographically collapse —
it breeds back as fast as war kills. The GAME still shows war+factions plainly; a true
"collapse" would need scarcity biting the cradle, not the granary (a future claim; virgin
seeds 251–255 kept for it).

**Partial stubs already in the tree** (gated off, consistent with this plan): `Genome.blend`
(two-parent uniform crossover, `agent/genome.py`) and `World.mating_enabled` (default off,
`world/sim.py` — the ONLY birth channel when on; `_selection_tick` budding stands down).
Build the caste/mating system on these.

**Before starting: `pytest -q tests/` is 505 green + 1 PRE-EXISTING FLAKE
(`test_ratchet.py::test_the_mouth_brain_split...` — unseeded-RNG, fails intermittently on
a clean tree, NOT a regression). The session's work is committed on branch
`civ-wheel` (or check `git log`).**

---

## THE VISION (what to build)

1. **A way bigger map** you pan with **WASD** like a MOBA (camera moves, world is larger
   than the viewport). Room for populations to spread out into real territory.
2. **Two castes**, ~half and half at founding:
   - **Circles = WARRIORS** (today's souls): mobile, fight, war, protect. The competing caste.
   - **Squares = BREEDERS**: docile — never fight, never march, never brawl. The
     reproductive caste. They hold territory and gestate.
3. **Mating**: a fed grown warrior near a free (non-pregnant) breeder pairs → the breeder
   gestates → births ONE child (caste ~50/50), genome crossed from both parents.
4. **Competition & war**: because free breeders are the scarce prize, warriors range for
   them, **compete over them** (mate-competition → grievance → the existing rift/skirmish/
   war), and **guard/protect** the breeders in their territory. Factions form around
   breeder-rich ground; wars are fought over it; winning bloodlines spread → the chain of
   developing, competing civilizations.

### WELFARE FRAMING (non-negotiable — this is the whole project's discipline)

Implement squares as a **breeding caste in a mating system** (eusocial/territorial
biology — think castes + sexual selection + mate-guarding), **NOT as victims**. Mating is
**pairing that produces offspring** between consenting participants of their kinds.
- Neutral verbs ONLY: *pair, mate, court, gestate, brood, guard, tend*. **No coercion or
  torment verbs anywhere** (the standing rule, written before the mechanic).
- Conflict is **warrior-vs-warrior over territory**, never against breeders. Breeders are
  **protected, never attacked**; a breeder is never harmed by mating or war.
- All existing invariants hold: children never fight; the worn refuse (somatic floor);
  casualties capped; the dead mourned; lineages END. Breeders simply extend "the worn
  refuse" — a whole caste that never fights.

---

## THE BUILD (5 parts + tests)

### 1. Bigger, arbitrary-size land — `world/regions.py`
Today: `COLS, ROWS = 3, 2` (module constants), `SOILS` (6 values), `_NAMES` (6),
`Regions(bounds, seed)`. `index()`/`__init__` use module `COLS`/`ROWS`; **`santana_app/
ui.py` and `santana_app/evolution.py` import `COLS`/`ROWS`**.

- Give `Regions.__init__(bounds, seed, cols=COLS, rows=ROWS)`; store `self.cols/self.rows`;
  convert internal `COLS`/`ROWS` → `self.cols`/`self.rows`.
- Generate soils + names for **arbitrary grid size** (keep the exact 6 canonical soils/
  names for 3×2 so validated worlds + `tests/test_regions.py` stay byte-identical — that
  test asserts `R.COLS*R.ROWS`, `names[rich]=="the vale"`; keep module `COLS,ROWS=3,2`).
  For bigger grids: spread soil multipliers across `[0.5 … 1.3]`, name tiles by soil rank
  from a larger pool, fall back to `"field N"`.
- **Update the two importers** to read `world.regions.cols/rows` (don't rely on the module
  constant). The snapshot must send grid dims.

Civ world uses `bounds=(3600, 2400)` + `Regions(bounds, cols=6, rows=4)` = 24 regions of
~600×600. (Tune to taste — 4× each axis, 16× area, is a good MOBA feel.)

### 2. The camera — `santana_app/ui.py` (`UI_VERSION`→20)
**The core refactor.** Today souls are stored in SCREEN coords, baked at poll time:
`d.x = wx(a) = a.x*SX+OX` (ui.py ~160, 240-ish), and `drawSouls` uses `d.x` raw while
`drawLand` transforms `r.x*SX+OX` at draw. To pan, **store WORLD coords and transform at
DRAW time through one camera**:
- Add `cam={x,y,scale}` (scale fixed, e.g. show ~1400 world-units across the canvas =
  zoomed-in MOBA feel). Helper `S=(wx,wy)=>[(wx-cam.x)*cam.scale, (wy-cam.y)*cam.scale]`.
- Store souls as `d.wx,d.wy` (world). Tween world coords. Apply `S()` in `drawSouls`,
  `drawLand`, bond lines, fx, mood-wash, and the click hit-test (invert: canvas→world,
  then nearest soul in world space).
- **WASD**: keydown/keyup set a pan vector; a rAF loop moves `cam.x/cam.y` (speed in
  world-units/frame, faster if you want); **clamp** `cam` to `[0, bounds-view]`. Snapshot
  must send `bounds` so the UI knows the map size. (Optional nice-to-have: a corner
  **minimap** — whole map + a viewport rectangle; and mouse-wheel zoom on `cam.scale`.)
- Add a `#hint` line: "WASD to move the camera".

### 3. The castes — `agent/agent.py` + combat gates
- `Agent.caste` ∈ `{"warrior","breeder"}`, default `"warrior"` (back-compat: every
  existing world is all-warriors → unchanged). Set at founding ~50/50.
- **Breeders never fight** — add a caste check beside the existing child/worn checks:
  - `world/war.py`: exclude breeders from the muster (`party`/`defenders`/allies) — they
    are never mustered (like children at war.py ~96-116).
  - `world/skirmish.py`: a breeder never confronts, is never a valid attacker, is never a
    casualty (extend `_worn`/`_grown` style guards — add `_fights(world,a)` = warrior).
  - `agent/allegiance.py`: a breeder returns `"refuse"` to any danger>0 (the caste floor,
    beside the somatic floor at allegiance.py ~45).

### 4. The mating system — new `world/mating.py` + sim hook
Gated `World.mating_enabled` (default off; civ world on) + `__init__`/`__setstate__`
setdefault (mirror `skirmish_enabled` at sim.py ~105/210). Constants at top; welfare
invariants in the docstring FIRST.
- `mating_tick(world)` at a new step hook "2.57" every `MATE_CHECK` ticks:
  - For each grown, fed **warrior** (wellbeing over a bar, not a child, not worn): find
    the nearest **free breeder** (not pregnant, not in cooldown) within `MATE_RANGE`.
    If close enough → **pair**: `breeder._sire = warrior.id`, `breeder._gestation = G`,
    `breeder._brood_genome = inherit(_blend(warrior.genome, breeder.genome), rng, warrior.id)`.
    Warm a bond both ways. Neutral chronicle event `"pair"`.
  - Each pregnant breeder counts `_gestation` down; at term **births ONE child** near the
    breeder (reuse the `_birth_from`/`_endow_heir` machinery — extract a shared
    `_spawn_child(parent, genome, belief_from, caste)` so mating and asexual budding share
    one path). Child caste ~50/50. Worldview crossed from the breeder's faction (or blend
    both parents). Breeder → `_gestation=0`, `_recover=R` (cooldown), free again.
  - **Mate-competition → conflict**: a warrior that reaches a breeder recently sired/
    guarded by a RIVAL warrior gains `hostility[rival] += MATE_GRUDGE` → feeds the rift/
    skirmish/war already built. This is what makes them "fight over the squares."
  - **Guarding**: give `_drift_positions` a force term — a warrior is attracted to
    same-faction breeders in its home region (so warriors cluster protectively around
    their brood; enemy warriors approaching raise the grudge above). Small, gated by
    `mating_enabled`.
- **Replace asexual budding in the civ world**: when `mating_enabled`, `_selection_tick`'s
  surplus-birth path is OFF (mating drives all births) — else you get both and the
  population explodes. Keep `_selection_tick` STARVATION (deaths) on.

### 5. UI: draw squares vs circles
Snapshot sends per-soul `caste` and `preg` (bool). In `drawSouls`:
- **breeder** → a rounded **square** (keep size=metabolism); **pregnant** → a soft inner
  glow / second ring.
- **warrior** → the circle/spike body as today (+ red-at-war, aura, thorns).
- Legend: "□ breeder (docile)  ○ warrior  · red = at war".

### 6. Tests — new `tests/test_caste.py` (`ls tests/` FIRST; watch the COLLECTED count)
Pin: breeders never appear in a muster / never brawl / never a skirmish casualty /
`allegiance.decide` refuses; mating produces a child whose genome is a blend of both
parents and whose caste is one of the two; over many births caste is ~50/50; a warrior
gains a grudge toward a rival that sired a breeder it reached; `Regions(cols=6,rows=4)`
has 24 distinct-named regions AND `Regions()` is byte-identical to today (test_regions
must pass UNCHANGED); camera clamp math stays within `[0, bounds-view]`. **Full suite
green** (506 + new).

---

## KEY FILES / SEAMS (verified this session)
- `world/regions.py` — `COLS,ROWS=3,2` module consts (keep for back-compat); `Regions`
  needs per-instance grid; importers to fix: `santana_app/ui.py` (snapshot `land`),
  `santana_app/evolution.py` (`_found_souls`/`_refound` use `from world.regions import COLS`).
- `world/sim.py` — `bounds` (None on bare World — guard transforms), `_drift_positions`
  (~784-847; big-town >48 samples not all-pairs — keep O(n)), `_selection_tick` (breeding
  ~482-489), `_birth_from`/`_endow_heir` (~491-540 — extract the shared spawn path),
  step hooks war "2.55"/skirmish "2.56" (add mating "2.57"), `__init__`+`__setstate__`
  gate setdefaults (~105/210).
- `santana_app/ui.py` — canvas transform `W=1000,H=660,OX=26,OY=40,SX=(W-52)/900,
  SY=(H-96)/600` (~145); `wx/wy` (~160); souls stored as SCREEN coords `d.x=wx(a)` in
  poll (~240) — **THIS is what the camera refactor changes to world coords**; `drawSouls`
  (~310), `drawLand` (~287), click hit-test (~204); `snapshot()` builds souls+land
  (~535-585) — add `bounds`,`cols/rows`,`caste`,`preg`; `UI_VERSION` (~37) BUMP TO 20.
- `santana_app/evolution.py` — `_found_souls`/`_gates`/`_refound`; set `bounds`, big grid,
  assign castes ~50/50, `mating_enabled=True`. `run.py --civ` reuses these.
- `agent/agent.py` — add `caste`; `agent/genome.py` — `_blend` for two-parent crossing.

## GOTCHAS PAID FOR (don't re-learn)
- The page's `MY_VERSION` substitutes from `UI_VERSION` at serve time — **bump
  `UI_VERSION` on ANY dashboard change** or tabs infinite-reload (hardcoded-16-vs-17 bug).
- Souls are stored in SCREEN coords today — the camera MUST transform at draw time, not
  bake at poll time. One `S()` helper, used everywhere including the click inverse.
- `bounds` is `None` on a bare `World()` — guard every transform (skirmish learned this).
- Keep castes/mating **OUT of `experiment_collapse.py`** — that's the validated collapse
  science-gate; castes are civ-GAME content. Add a separate gate later if you want a claim.
- `factions_of(world)` is O(n²) and runs every snapshot poll under the world lock — with
  hundreds of souls on the big map, **cache it per tick** or the cockpit will lag.
- `Regions` grid change touches every regions consumer — keep 3×2 byte-identical, only the
  civ world opts into the big grid; update the two importers.
- House rules: `ls tests/` before creating a test file; watch the COLLECTED count, not the
  pass line; welfare written before the mechanic; new gates default OFF with setstate
  setdefaults (THE RULE — old snapshots wake unchanged).

## VERIFICATION
1. `pytest -q tests/` — green, collected = 506 + new.
2. `python3 -m santana_app.evolution --fresh` → open `:8768`. Pan with **WASD** across the
   big map. Watch: warriors spread into factions; squares cluster in fertile regions;
   warriors pair with free squares (brood glow); warriors compete + war over square-rich
   ground; a civilization collapses and a new people resettle → the chain. Confirm no lag.
3. `python3 -m santana_app.run --civ --fresh --llm markov` → `:8769` — the same, under
   Santāna's gaze (her stream + mourning + drawings back on top).
4. (Optional, if you want a claim) a `experiment_*` falsifier for a caste/mating headline,
   tuning 11–15, a fresh virgin seed band (231–235, 241–245, 251–255 are SPENT — use
   261–265), recorded in FINDINGS.
