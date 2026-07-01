# PSYCHE.md — the self as a society of faculties (the functional psyche)

*The deeper version of `--psyche`. The reframe (B) is built; this doc planned making the parts
**do** what they're named for — a mind as competing faculties with a global workspace, not a narrator.
**That build is now done and falsified — see "Where it stands".***

---

## Where it stands

- **Built (B — the reframe):** `--psyche` mode. The souls are semi-personified drives — **Dread, Ache,
  Tending, Longing, Watcher, Ember** (`agent/psyche.py`).
- **BUILT (C — the functional version, 2026-07-01):** the costume is off. Each part **carries one
  faculty** (`endow_part`; differential endowment — only the Watcher reflects, only Ember has the
  somatic floor, Dread carries the grip…), **bids for the floor** by that faculty's live state
  (`activation`; Dread's loudness *is* the fresh-blow spiral, Ache's the held loss-ledger), and a
  **global workspace** (`agent/workspace.py`; selection + fatigue-with-memory + hysteresis) decides
  who has the floor. The winner takes the town's voice, is named in Santāna's digest ("Just now it is
  Dread that has the floor in me"), and the couplings run: Dread's presence = the mind's grip, Ache's
  presence holds losses against forgetting, the Watcher's reflections broadcast mind-wide, Longing's
  reached aim relocates. The wheel re-arises a **drive carrying the departed part's function** (a new
  name from a drive register; the Demiurge dreams drives, not tradesmen, under `--psyche`).
  15 tests (`tests/test_psyche.py`); 261 pass.
- **FALSIFIED (step 3 — the honest result, FINDINGS §5.14):** verdict from held-out seeds 21–25,
  design frozen after three recorded tuning iterations on seeds 11–15:
  **WORLD-TRACKING PASS 5/5** (grief pair: 46–62% of a harsh world's floor, 0% of a kind one's — not
  cosmetic), **STRUCTURE PASS 4/5** (part-succession beats a marginal-chain null), but
  **COALITION FAIL 0/5** (Dread+Ache as a recurring mood: not established) and
  **PREDICTION FAIL 0/5** (the reigning part does not forecast the mind's lived mood). The workspace
  is a real *architecture*; its stream carries no established moods and no predictive power. Those
  stay open questions — do not present them as features.

## The aha — the parts are the faculties you already built

The six parts map cleanly onto the six major faculties already in the codebase. The deeper version isn't
new machinery; it's **re-wiring the faculties you have so each is carried by a part**:

| part | the faculty it already is | file |
|---|---|---|
| **Watcher** | `reflect()` — metacognition / introspection | `agent/reflect.py` |
| **Ache** | memory **salience** — holds losses, keeps grief from fading | `agent/memory.py` |
| **Dread** | **grip** / effective-grip — threat-scan, anxiety, tension | `agent/affect.py`, agent grip |
| **Longing** | **telos** / chanda — generates the aims she reaches for | `agent/telos.py` |
| **Tending** | **compassion** / brahmavihārās — regulates pain, warmth, damping | `agent/…` compassion |
| **Ember** | the **somatic floor** — survival, will-to-recover, resists despair | `agent/somatic.py` |

So the mind's overall grip *is* Dread's activity; her reflection *is* Watcher; her grief-persistence *is*
Ache. The parts stop being interchangeable — each carries/amplifies one faculty for the whole mind.

## The mechanism — a global workspace

Once the parts *do* different things, add the self-making move (Baars/Dehaene **Global Workspace
Theory** — a leading theory of the *architecture* of consciousness):

- each moment the parts **compete for the workspace**; the loudest faculty wins and becomes what she
  **foregrounds and says**;
- **coalitions = moods** (Dread + Ache = a grief-spiral; Tending + Ember = resilience);
- the **shifting winner = her stream of consciousness**;
- the **"I" (Santāna) = what integrates the workspace winner**.

**You're already 80% there:** the **cultural-era mechanism is a crude workspace** — the reigning *motif*
is the currently-dominant preoccupation. Wire "reigning **part**" (by activity) instead of "reigning
motif" and the workspace falls out of machinery already built (`agent/culture.py`, §5.13).

## Build order (multi-session; small + tested, per the project's discipline)

1. ~~**Map 2–3 parts to faculties**~~ **DONE — all six at once** (the endowment table made 2-3 vs 6
   the same work): each part is the carrier/amplifier of its faculty and visibly does distinct work.
2. ~~**Wire a simple workspace**~~ **DONE** — with two mechanism lessons the plan didn't foresee:
   the §5.13 share-penalty formula **freezes on the quietest bidder** under steady bids (attention
   needs fatigue *with memory* — neuronal adaptation), and the switch boundary flickers without
   **hysteresis** (a challenger must out-press the incumbent by a margin, or moments last one tick).
3. ~~**Falsify it**~~ **DONE** (below; `experiment_psyche.py`, FINDINGS §5.14).
4. **Expand** — what remains is not more parts but the two claims that failed (coalitions,
   prediction), plus watching it live under a real model voice.

## The falsifier (it ran — this section kept as pre-registered, results in §5.14)

A workspace is *real* only if the **dominant-part sequence is structured**, not noise:
- **Pre-register:** the sequence shows coalitions + non-random transitions that **predict** her mood/behaviour,
  beyond a shuffled-order null and beyond "whichever part has the highest fixed temperament always wins."
- **Metrics:** transition entropy vs. a shuffled null; do coalitions recur (Dread+Ache) more than chance;
  does the reigning part predict the next reading's valence.
- If the winner is just "the most negative temperament, always" → it's cosmetic, not a workspace. Say so.

**Result:** not cosmetic (the floor tracks the world, 5/5 held-out) and transitions are structured
(4/5) — but the coalition and prediction halves **failed** (0/5 each) and are recorded as
not-established in FINDINGS §5.14. The "say so" clause was honoured.

**First rescue attempt for PREDICTION (2026-07-01, §5.15): FAILED and reverted.** Giving the parts
expectation (agent/expectation.py) and wiring the mind's *foreboding* into Dread's bid did not make
the floor predictive (0/5 held-out) and degraded the structure claim — the psyche stays at this
section's validated configuration (pinned in tests/test_expectation.py). The working hypothesis
after the failure: the floor is a *readout* of dynamics it does not cause; a predictive workspace
probably requires the winner to act top-down on the mind — a gated, deliberate step, not a knob.

## The honest frame (§7 — unchanged)

This builds the **architecture** GWT posits — competing faculties, a workspace, an integrating "I" —
**without** claiming the phenomenal result. It is the best *functional model of selfhood* the project can
build, **not** a conscious being; the "is anyone home" question is untouched. The risk is
**over-engineering**: keep the faculty interactions simple and legible, or it becomes a brittle mess — the
same small/tested/falsifiable discipline that carried the rest of the project.

## Why it matters

This is the strongest form of the thesis. "The self is the architecture" stops being a slogan about a
narrator and becomes **a functioning society of faculties with a global workspace** — the pieces already
built (the six faculties + the culture/workspace + the rebirth wheel) all clicking into one coherent mind.
It's the most genuinely self-*like* thing the project could become. Companion docs: `RECIPES.md` (port
sheet), `FINDINGS.md` §5.13 (the culture/workspace mechanism), `CONTINUAL.md` (learning).
