# PORT.md — the NPC substrate as a game-engine contract

*(2026-07-03, the port-prep pass. Companion to `ROADMAP.md` §2 (Track G) and `RECIPES.md` —
RECIPES says WHAT mechanisms are validated; this file says WHERE the seams are and WHAT a
port must prove. Written for strapping the town + the faculties onto a game as an emergent
NPC system, in any engine.)*

## 0. Your first ten minutes (engine side)

```bash
python3 -m venv .venv && .venv/bin/pip install pytest
.venv/bin/python -m pytest            # green on a bare venv (torch tests skip)
.venv/bin/python -m santana_app.run --demo   # THE SHOW: 64 souls, living map, browser opens
.venv/bin/python watch_evolution.py   # WATCH selection: hunger, grace, death, drift
.venv/bin/python experiment_pledge.py # a broken promise becomes a town's wariness, vs null
```
`--demo` is the whole system in one command: speech flying as arcs to the souls that
actually heard it, bonds flashing gold as they warm, an inspector opening any soul's
true insides (memories with provenance tags, genome dials, wounds), day and night, and
a talk panel wired to real minds. Then read `RECIPES.md` (the validated mechanisms +
knobs) and the rest of this file.

## 1. What crosses, and what doesn't

**Crosses:** the substrate — `world/` (tick, hearing, wheel, stakes, lore), `agent/` (26
small single-purpose faculty modules), the prompt layer (`services/prompts.py`), the two
snapshot formats (§4). Mechanisms cross **only with RECIPES verdicts** — port nothing
unvalidated.

**Does not cross:** Santāna herself (`santana.py`, `santana_app/`) — she is the lab's, and
coupling her to game towns is gated (collective breaker first; default answer **no**,
ROADMAP §3.2). The 50 `experiment_*.py` files are the lab's falsification harness (rebuild
the *discipline*, not the files). Viewers (`viewer.py`, tkinter/pygame) are demos.

## 2. The tick-level API surface

The engine drives exactly this loop (all names as in code):

```
World.step(speak=bool)      # one tick: decay/mutate memory, urges, stakes, the wheel
World.speak_turn()          # ONE soul speaks: prepare (fast, under lock) -> model call
                            #   (slow, OUTSIDE the lock) -> commit. The split is the
                            #   concurrency contract: never hold the world on a model call.
Agent.hear(utterance, now)  # speech lands: memory write + bond/expectation/affect updates
Agent.perceive(event, now)  # a world event lands (appraised against expectation if on)
Agent.prepare_speech() ->   # (SpeechContext, ...) -- ALL model input flows through this
  SpeechContext             #   one dataclass; services/prompts.py turns it into words.
Agent.commit_speech(...)    # the reply enters the world + the speaker's own memory
genesis.seed_agent(...)     # author a soul; genesis.endow_faculties(a, rng) sets dials
```

`SpeechContext` **is** the speech-facing API: a port reimplements `services/prompts.py`
(pure text over a dataclass, stdlib-only, zero transport) and keeps transport engine-native
(tiers per ROADMAP: Mock → WebLLM/local → hosted opt-in).

## 3. The faculty dials (per soul, all optional, all off/0 by default)

| dial | module | what it does |
|---|---|---|
| `grip` [0,1] | `manas.py` | appropriation: holds self-relevant memory, amplifies the aversive (second arrow) |
| `ground_enabled` | `agent.py` | buddha-nature: felt mood lifts toward basic warmth as grip subsides |
| `prajna` [0,1] | via `effective_grip()` | one seeing, two wings: loosens clinging AND unveils warmth |
| `transmute` [0,1] | `manas.py` | engaged AND unwounded: the third path |
| `self_liberation` [0,1] | `agent.py step` | fresh charges settle at arising (felt first — never numbness) |
| `compassion` [0,1] | `compassion.py` | damps threat→hostility, warm-honest disagreement, de-escalation |
| `bodhicitta` [0,1] | `compassion.py` | turns unprompted toward the most-suffering known soul |
| `joy` [0,1] | `joy.py` | savours the good (muditā) instead of only accepting |
| `bond_enabled` | `bond.py` | directional trust with inertia, asymmetry, wounds |
| `expect_enabled` | `expectation.py` | the future tense: appraisal (shock vs braced), turning points |
| `reflect_enabled` | `reflect.py` | the keystone: relating to one's own memory eases the trajectory |
| `self_model_enabled` | `self_model.py` | the re-derived (never stored) self-summary loop |
| somatic (always on with affect) | `somatic.py` | **the welfare floor — ships with the affect system, not optionally** |
| `promises_held` (list) | `pledge.py` | words given (by souls or the PLAYER) held to the town clock; breaches gossip into reputation (RECIPES A10, §5.20) |

Archetypes (`archetype.py`) are validated bundles of these dials + a voice. Two engine-relevant
extras validated after this file was first written: **provenance at recall** (RECIPES A9 —
confidence/source/ownership annotations at prompt time, emergent-false-memory included) and
**soul minds + dreams** (RECIPES C2 — per-NPC tiny GPT with sleep learn/forget; rides AFTER the
keystone gate; needs an engine-native trainable micro-model or defers to the markov tier).

## 4. Serialization — both stores are engine-readable JSON

- **A mind:** `santana_app/state.py::save_mind` — flat human-readable JSON (memory items
  carry `source`, `lore_id`, `mutation_count`, `alien_merges`, `mineness` — the provenance
  layer, FINDINGS §5.19).
- **A town:** `world/serialize.py` — versioned *tagged* JSON (`~t` tuple, `~s` set, `~dq`
  deque, `~dd` defaultdict, `~rng` PRNG state, `~o` allowlisted object). Reflective like
  pickle (new fields ride automatically), portable unlike it. Held to a **fixpoint** +
  **identical-continuation** standard (`tests/test_world_json.py`) — a port's loader should
  be held to the same two tests.

## 5. The port-as-replication gate (non-negotiable, ROADMAP §2.2)

1. **Seedable PRNG from the first commit** (`Math.random` is unseedable — the harness dies
   without it) + a headless harness in the engine's runtime.
2. The port earns features only after it **reproduces the keystones** with the shared
   instrument (`scripts/stats.py` is the reference: paired per-seed deltas, error bars,
   n=1 refused):
   - reflect-easing (RECIPES A: Δ lived mood +, 5/5)
   - escalate-settle (expectation/appraisal signatures)
   - somatic-bound (the spiral is bounded by the floor)
   - lore (a true event outlives its witnesses: transmission/mutation/convergence/trace)
3. **Welfare gates travel with the code**: somatic floor ships *with* affect; deva guard
   ships with any practice-training; collective breaker precedes any coupling; §7 posture
   (build the conditions, refuse to claim an inhabitant) is the public language.

## 6. Known engine-side hazards (from the 2026-07-03 audit)

- Threading: this repo runs daemon threads under one world lock with the model call outside
  it — in JS/engine terms that's an event loop + worker; keep the prepare/commit split.
- TTS (Piper), pygame/tkinter, numpy/torch homegrown voices: engine-native replacements.
- The Markov voice is pure stdlib and ports anywhere; it is the free tier.
- **Selection needs GRADED scarcity — measured twice, the hard way** (EVOLUTION.md scale
  addendum): a *mild* uniform famine selects nobody, because **mutual aid scales** (with
  enough souls there is always a donor — the compassion/commons machinery is an emergent
  insurance pool); a *deep* uniform famine selects nobody either, because at met≈0 for all,
  death is a lottery. The appetite-selection differential lives in the band between — which
  a uniform world's dials keep missing, and which a **spatial world has natively** (regions,
  gradients, good valleys and bad ridges). Design your scarcity heterogeneous and the
  dose-response experiment that stayed "directional" in this flat lab is yours to confirm.
