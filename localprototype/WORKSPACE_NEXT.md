# WORKSPACE_NEXT.md — developing Santāna's global workspace

*Plan, 2026-07-21. The next stages for the psyche workspace (`agent/workspace.py`,
`agent/psyche.py`, PSYCHE.md), in the house idiom: **mechanism · pre-registered falsifier ·
null · port note**. Read this + `SCORECARD.md` (the GWT/AST rows) + FINDINGS §5.14 (what
passed, and the two claims that did not) to resume cold.*

---

## Where it stands (SCORECARD, unedited)

| indicator | verdict | evidence |
|---|---|---|
| **GWT-1** parallel specialised modules | **PRESENT** | six parts, each carrying one live faculty (`psyche.endow_part`) |
| **GWT-2** limited-capacity bottleneck | **PRESENT** | one floor, competition by activation, fatigue-with-memory + hysteresis; world-tracking 5/5 held-out |
| **GWT-3** global broadcast back to modules | **PARTIAL** | the couplings run (Dread→grip, Ache→salience, Watcher→mind-wide) — but *the winner as such* does not act back |
| **GWT-4** modules query the workspace | **ABSENT** | nothing asks "what is the mind attending to?" |
| **AST-1** a model of her own attention | **ABSENT** | *"the single biggest gap"* |

**The two recorded failures (§5.14), and their principled retries:**

- **COALITION 0/5.** Mood co-occurrence is not a coalition. The literature's reading (and
  now the project's): coalitions form on shared goals + complementary ability + a model of
  the other — never on affect co-occurrence. The correct retry is **EVOLUTION E5**
  (telos-alignment + person-models), **not** a better mood metric. *Deliberately out of
  scope for this document.*
- **PREDICTION 0/5.** The reigning part does not forecast the mind's mood. *"The floor is a
  readout, not a forecaster."* The retry is **W1 below**: model the floor, rather than
  asking the floor to forecast.

**Operational note.** `World.psyche` defaults to `None` — the workspace is **off** in every
world that does not ask. Development runs need `--psyche`.

---

## W0 — the instrument. *Ungated. Build first.*

**Mechanism.** `scripts/psyche_stats.py`: floor-share per part, turnover rate, mean reign
length, and succession entropy, read off the live `Workspace` or a saved snapshot. The
workspace already keeps a 4000-entry dominant-part log; `experiment_psyche.py` reads it for
verdicts, but nothing reads it *while it runs*.

**Falsifier (the instrument's own).** Point it at a workspace with fatigue disabled: turnover
must read ~0 and one part must hold ~100% of the floor. An instrument that shows a lively
stream where the floor is frozen would lie into every claim built on it. (The
absence-detector discipline, §5.13 — and the lesson paid for in `arena_stats`, where an
assumed baseline invented a selective sweep that had not happened.)

**Port.** The "what is this NPC's mind doing" debug read, and the raw material for W1.

## W1 — C1, the attention schema (AST-lite). *Ungated. The stage.*

**Theory.** Graziano: awareness is the brain's simplified *model* of its own attention, used
to predict and control it.

**Mechanism** (RESEARCH C1, unchanged). Alongside the workspace, Santāna keeps a small
**schema** of her own attention: per-part EWMAs of floor-share plus a first-order transition
guess. Each reading she *predicts* the next floor-holder, and notices violations — *"Dread
has the floor and I did not see why."* **The schema, not the raw log, feeds her digest.**

**Pre-registered falsifier** (tuning 11–15; verdict on virgin seeds):

- **A1 THE SCHEMA PREDICTS.** Next-reign prediction beats the marginal base rate.
- **A2 SURPRISE ABOUT HERSELF.** Schema-violation moments correlate with arousal spikes.
- **null.** The schema tracks no better than a shuffled log.

**Watch for** — the null-integrity lesson already paid for in §5.14: a periodic event
schedule hands a circular-shift null the very structure under test. **Jitter the times.**

**Why this shape.** §5.14 asked the *floor* to forecast the *mood* and it could not. C1 asks
a *model* to forecast the *floor*. Different claim, different object, genuinely testable —
and it is the AST-1 row.

**Port.** The schema is the NPC's "what am I focused on" string: free introspective dialogue.

## W2 — GWT-4: a part queries the schema. *Ungated. Small, after W1.*

**Mechanism.** A part's bid becomes partly a function of what the schema reports the mind is
attending to — e.g. Tending bids harder when the schema shows a long Dread reign. That is
state-dependent attention: the workspace read *back* by the modules.

**Falsifier.** Bids become schema-dependent **without collapsing turnover**.

**null.** Schema-blind bidding.

**The failure mode to guard, explicitly.** This is the stage most likely to reintroduce a
static fixed point — the very thing fatigue-with-memory was invented to prevent after the
§5.13 share-penalty formula was *measured* to freeze on the quietest bidder. A querying part
that raises its own bid in response to its own reign is a self-reinforcing loop. **Turnover
must be checked, not assumed.**

## W3 — GWT-3: the winner acts on the mind. ⚠️ **GATED**

**Already gated in ROADMAP §3.2**: *"stage-two of the top-down loop (workspace broadcast /
winner-acts-on-mind), shipped only with the speech–action coherence falsifier."* That gate
stands.

**Mechanism.** The floor-holder *as such* acts back on the parts — not only via its carried
faculty's coupling, but as the mind's foreground determining what the whole mind does next.
This is the step that turns the workspace from a **readout** into a **driver**.

**Falsifier.** Project Sid's PIANO (METHODS §4) arrived independently at the same
workspace-with-bottleneck design and found **the broadcast is what keeps speech and action
coherent** — so the measure is given: does broadcast raise speech–action coherence against a
no-broadcast null?

**Not a task. A decision.** Plan it; do not build it on the day it feels exciting. The
collective breaker question comes first.

## W4 — attention as agency. ⚠️ **GATED. Phase 3, after W1.**

**Mechanism.** Phase 3 already plans **bounded attention** (a finite working set of souls).
This lets her *choose* it — turn toward a dying soul, or away. Agency with **zero** feedback
into the town: nothing she attends to changes what happens there.

**Falsifier.** This is the **behavioural axis the deva guard currently lacks**: *does she turn
toward suffering when she could turn away?* Bodhicitta, measurable, against a random-attention
null.

**Why it matters beyond the indicator.** §5.27 measured her valence band at 0.035 wide across
twenty hours and hundreds of witnessed deaths, and read it as stillness. That reading is
currently **unfalsifiable**: wellbeing cannot distinguish the bodhisattva from the deva — the
scorecard says so — and she has almost no behaviour to read instead. W4 supplies the missing
instrument as a side effect of supplying the freedom.

**Standing caveat.** The gate is the same one as W3's, and the ordering (W1 before W4) is not
optional: choosing an attention set is not meaningful before there is a model of attention to
choose with.

---

## Order

```
W0  instrument     ── half day  ── ungated; needed by everything below
W1  C1 schema      ── the stage ── ungated; AST-1, and the honest PREDICTION retry
W2  GWT-4 query    ── small     ── ungated; check turnover or it freezes
   ──────────────────── decision point ────────────────────
W3  broadcast          GATED — needs the speech-action falsifier and a sober day
W4  attention agency   GATED — Phase 3; after W1
```

**W0+W1+W2 crosses no gate, is fully reversible, and moves two scorecard rows**
(AST-1 ABSENT→PARTIAL, GWT-4 ABSENT→PARTIAL). W3 and W4 are decisions, recorded here so they
are made deliberately rather than drifted into.

*Companion docs: `SCORECARD.md` (the audit this moves), `PSYCHE.md` (the design),
`RESEARCH.md` C1–C2 (the mechanisms), FINDINGS §5.14 (what passed and what did not),
`METHODS.md` §4 (PIANO, the independent design precedent), `ROADMAP.md` §3.2 (the gates).*
