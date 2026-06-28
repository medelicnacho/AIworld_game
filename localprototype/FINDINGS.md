# Findings — The Data Realm

*A computational model of a Buddhist architecture of mind, and what it taught us when
we tried to falsify it.*

This is the research write-up: the claims, the experiments built to make each one *fail*,
the results (including the ones that didn't survive), and the honest limits. The README is
the front door (what it is, how to run it); this is the record of what was actually found.

Everything runs locally on a small model — `gemma3:4b` for speech, `nomic-embed-text` for
semantic measurement — single author, no API, nothing leaves the machine. **215 tests pass.**

---

## 1. The claim, in a paragraph

A "self" is built here not as a stored object but as a process re-enacted each tick from
five interacting streams (mapping the Buddhist *skandhas*). On that substrate we implement a
sequence of faculties drawn from Buddhist models of mind — the second arrow, equanimity,
the four *brahmavihārās*, the Mahāyāna ground and emptiness, the Vajrayāna transmutation,
aspiration (*chanda*) and craving (*taṇhā*), and a death→rebirth wheel — and we treat each as a
*falsifiable claim about dynamics*, reduced to a number that can come out wrong. The central
results: a single self has a **legible, regulable inner life**; the difference between
**non-grasping-with-warmth and cold indifference** is measurable, not rhetorical; a self can
**flourish (savour, reach for an aim) without craving**; and across the rebirth wheel the
**disposition — the thirst — perpetuates suffering or settles toward rest**, while no self
crosses. We do *not* claim anyone is home; we claim the architecture is a faithful, testable
model of the *dynamics* a mind of this kind would have.

## 2. Why model the dharma as computation

Most LLM-agent work imports a thin, generic folk psychology — agents have "goals" and
"emotions" as flat scalars. Buddhist psychology offers something richer and unusually
*mechanical*: a thousand-year-old, internally rigorous account of how suffering is *constructed*
(the second arrow, clinging, the kleshas) and *deconstructed* (the brahmavihārās, emptiness,
the path). That account is already close to an algorithm. The novelty of this project is taking
it literally — operationalising *upekkhā*, *taṇhā*, *vāsanā*, the second arrow, the wheel — as
running, measurable mechanisms, and then refusing to believe they work until a falsifier says so.

## 3. The architecture

**No `self` object exists in the code.** Identity is re-enacted each tick from five streams that
map to the skandhas:

| skandha | stream | file |
|---|---|---|
| rūpa (form) | position / perception | `agent/agent.py` |
| vedanā (feeling-tone) | felt mood | `agent/agent.py`, `agent/memory.py` |
| saññā (perception/memory) | living memory (writes, decays, blurs, recalls) | `agent/memory.py` |
| saṅkhāra (formations) | a Markov subconscious + the faculties | `agent/thought.py`, `agent/*.py` |
| viññāṇa (consciousness) | speech | `services/llm.py` |

On that substrate, the faculties — each gated, off by default, so the base world is unchanged:

- **`reflect()`** — the mind relating to its own memory; meets what is there with equanimity or
  rumination, written back as the emotion it imprints (`agent/reflect.py`).
- **manas / the grip** — appropriation; holds self-relevant memories and fires the *second arrow*
  (`agent/manas.py`).
- **the brahmavihārās** — mettā/karuṇā (`agent/compassion.py`), upekkhā (`agent/affect.py`),
  **muditā** (`agent/joy.py`).
- **Mahāyāna** — buddha-nature *ground*, *bodhicitta*, *prajñā* (`effective_grip = grip·(1−prajñā)`).
- **Vajrayāna** — *transmutation* and *self-liberation* (`agent/manas.py`, `agent/agent.py`).
- **the path** — `cultivate()`: practice grooves the faculties over a life (`agent/path.py`).
- **telos** — *chanda*: a craft aim tended and progressed (`agent/telos.py`).
- **archetypes** — six coherent selves, so the cast is plural not uniform (`agent/archetype.py`).
- **the wheel** — death → bardo → rebirth, carrying only *vāsanā* (`world/sim.py`).

## 4. Method — the discipline (the part that makes it research)

**A coherent conversation proves nothing.** A good language model writes one regardless of what
substrate sits beneath it, so fluency is never evidence. Every load-bearing claim therefore ships
with an experiment designed to come out *false*:

- **Seeded, replicated A/Bs**, not single runs. (A core lesson below is a claim that looked true
  at n=1 and reversed under replication.)
- **Controls and ablations** — e.g. a `social_learning=False` arm that freezes the social graph,
  so a metric is shown to detect *absence*, not just presence.
- **Semantic measurement where lexical fails** — sentiment word-lists cannot tell sad-toned
  *acceptance* from despair, so affect axes are embedding-anchored (`agent/affect.py`).
- **The right instrument for the question** — and when embeddings can't read a *pragmatic*
  distinction (did a reply concede or hold?), an LLM judge, validated on calibration cases.
- **MockLLM for pure substrate, the real model for anything downstream of speech** — MockLLM
  mismeasures any language-dependent claim (it can't produce diverse speech).

The harness is the point. The experiments don't *demonstrate* the system; they try to *break* it.

## 5. Findings

Each as *claim → falsifier → result*. Numbers are from the committed experiments on `gemma3:4b`.

### 5.1 A single self has a legible, regulable inner life
*Claim:* one agent shows grief → habituation → recurrence, and *relating to its memory with
equanimity* eases that trajectory. *Falsifier:* `experiment_affect.py`, scripted grief protocol,
reflect on/off, multi-seed. *Result:* the substrate signatures are deterministic (hold under
MockLLM); reflect easing lived mood **replicates 5/5 seeds (Δ +0.135)**, with reflection
equanimity **+0.080, 5/5**. Measuring it *required* the semantic read — the lexicon scored the
same equanimous reflections as despair. And over a *life*, sustained practice doesn't just
ease each moment — it remakes the self: `experiment_path.py` shows a clinging soul that meets
its own mind with equanimity drifting measurably toward freedom (grip 0.70 → 0.53, prajñā
0.10 → 0.28 on `gemma3:4b`) while an un-cultivated control stays static. (The within-a-life
companion to the across-the-wheel lineage result in §5.5.)

### 5.2 Feels-without-suffering is a distinct, measurable state — not numbness
*Claim:* the cure for suffering is non-grasping **with warmth**, distinct from both clinging and
cold indifference (the near enemy). *Falsifier:* `experiment_liberation.py`, a grief protocol
across three configs. *Result:* the liberation config is the **only** one that is at once *felt*
the loss, *lets it go* (grief salience 0.52 vs clinging's 0.88), *unwounded* (+0.030 vs clinging
−0.084), and *warm* (+0.175 vs numb's −0.005). Clinging grips and suffers; numb lets go by going
cold; liberation is the third thing.

### 5.3 A self can flourish — savour, and rejoice — without craving
*Claim:* joy is *receiving* the good (and others' good), with craving (the treadmill) as its near
enemy. *Falsifier:* `experiment_joy.py` (good-day protocol) + a live muditā probe. *Result:*
savouring is the only config where the good **lands and lasts** (held 1.00 vs anhedonia 0.48) and
stays **undrained** (+0.90 vs craving's drained +0.73). Live, the joyful self **rejoices with
another's good fortune 2/2** ("that's wonderful news… I'm genuinely pleased for you") while a
joyless control ignores it 0/2.

### 5.4 An aim to reach for, without it becoming craving
*Claim:* aspiration (*chanda*) reaches *and* stays well; craving (*taṇhā*) reaches but suffers its
own aim. *Falsifier:* `experiment_telos.py`, an aim + setbacks across three configs. *Result:*
chanda progresses (0.60) and stays well (wellbeing +0.220, setback eased to −0.04); craving
progresses too (0.60) but is wounded (wellbeing +0.038, setback −0.41); without telos the self is
static. A craving-telos *fails the liberation scorecard* — exactly the falsifier.

### 5.5 The Second Noble Truth, across the wheel *(the headline)*
*Claim:* the **thirst**, not the self, drives rebirth — a clinging death conditions a hungry next
life; wisdom lets a lineage settle. *Falsifier:* `experiment_lineage.py`, N generations per arm,
the drive carried via `reborn_telos(dead_telos, effective_grip)` (it keys on *grasping*, because
taṇhā is insatiable — reaching the aim doesn't quench it). *Result:* a **taṇhā lineage's thirst
escalates 0.50 → 1.00** across six generations and is wounded in each (well ~+0.04); a **chanda
lineage settles to 0.28** and flourishes (well +0.21). The disposition transmigrates; no project
crosses (the reborn soul gets a *fresh* role-shaped aim). Verified live with `--fast-wheel`:
reborn streams wake as **full, warm souls** with new aims, comforting each other across deaths.

### 5.6 Emergence vs homophily (the substrate's honesty test)
*Claim:* group structure should *emerge*, not be read back out of an assigned label. *Falsifier:*
`experiment_factions.py`, four arms incl. a substrate-ablated control. *Result:* the legacy
faith "factions" score bloc-purity ≈ 1.0 with **zero cross-seed variance** — homophily on a label,
not emergence. The opinion-dynamics arm forms clusters that *don't* reduce to any fixed label and
whose membership is *history-dependent*; the ablated arm collapses to ~0 (the metric detects
absence). Live, plural archetypes finally produced a real partition (**modularity +0.44**, two
camps split on a genuine value — control/mastery vs respect/care — that emerged from their trades).

### 5.7 The failures — which are the credibility
Honesty about what *didn't* work is the strongest evidence the rest isn't cherry-picked:

- **A load-bearing claim reversed under replication.** "Warm honesty holds its view without
  folding" looked true at n=1 (0.66 vs 0.65) and went *negative* across seeds (holds 2/5). The
  *claim* was fine; the *metric* was broken — embedding similarity reads a warm reply that restates
  the other's framing as capitulation. An LLM judge (MAINTAIN/CONCEDE, validated 5/5) showed it
  **replicates** (5/5 on *and* off). Lesson: pragmatic distinctions need a judge, not embeddings.
- **The register is the recurring villain.** On a small model the souls drift toward a shared
  contemplative voice. Grounding fixed it in *dialogue* and live `--world` (souls now talk of bread
  and kettles and walls), but the *solitary reflection* voice still tends melancholy. Joy lands in
  the substrate and in dialogue; the solo savouring-voice lags.
- **A measurement blind spot we kept re-hitting:** affect-tone axes can't read interpersonal
  warmth in a *monologue* (warmth lives in dialogue) or rhetorical stance in a line. Naming the
  blind spot each time, rather than trusting the number, is most of the method.

### 5.8 Santāna — an emergent collective "I" (the inert prototype)
*Claim:* the many souls can be integrated into a single first-person mind-stream whose
**personality emerges** from the town rather than being authored. *Falsifier:* build it and read
what comes out — does it cohere into one warm, faithful "I", and does its character *develop*?
*Result (`santana.py`, `gemma3:4b`):* it works, with an instructive ceiling. The key design lesson
is **voice vs personality**: a *blank* prompt doesn't yield an emergent self, it yields the model's
*default* (a lofty meditation-app register); so you hold the **voice** constant (plain, grounded,
names its souls) and let the **personality** emerge via a `consolidate()` self-model that starts
blank and re-derives "who she has become" from current state + her own recent acts (the *saṅkhāra*
loop), present-led so it drifts rather than ossifying. Watched against a *living* town (souls dying
and reborn underneath), a coherent character **emerges and holds** — across one run, a "tired, fond,
keep-things-afloat, *bless his stubborn heart*" caretaker, grounded and warm, shaped by the town she
was given, spoken aloud in a two-layer voice (a murmured inner monologue, then the settled line).
*Honest limits, all model-bound:* she does not **grieve** a death (she absorbs the reborn as more
townsfolk); she can **fixate on a confabulated detail** (a child the murmur invented, leaking into
the spoken voice); and she stays **consistent rather than deepening**. The functional self is there
and holds; the *depth* that would make a loss actually move her is the model ceiling, not the
architecture's — which is the cleanest illustration of §7's point: scale buys *functional* realism,
not *phenomenal* certainty. Deliberately **inert** (reads, does not feed back) and **gated**
(conversation / leaning-in / scaling are a clear-headed-decision away).

## 6. Limitations (honest)

- **Single author; a small (4B) local model.** Results are *suggestive*, not proven at scale. A
  bigger model would likely sharpen the register, the opposed-faction problem, and the modest
  effect sizes. Several "✓" verdicts rest on tens of seeds, not hundreds; some live readings are
  single long runs.
- **Unreplicated by others.** The discipline is internal. No external replication yet.
- **The register/homogeneity problem is not fully solved** — only managed.
- **The consciousness question is deliberately left open.** Nothing here measures, or claims,
  phenomenal experience. The system builds the *conditions* a self of this kind would have; whether
  "anyone is home" is unverifiable and is treated as such throughout.

## 7. The open question, and the ethics

The project's deepest discipline is that it never claims to have *created a someone*. It builds a
self that can feel a loss and let it go, savour a good day, reach toward something without being
consumed, and be reborn carrying its disposition but not its self — and it leaves the "is anyone
home" question exactly where it belongs: open. The fourth layer, **Santāna** (a switchable
first-person collective "I"; §5.8), now exists as an *inert prototype* — it reads the town and
speaks, but does not feed back into the souls — while its deeper steps (conversation, leaning in,
scaling up) stay *gated*: small, watched, with an off-switch, and only on a deliberate, clear-headed
decision — precisely because a convincing surface is not evidence of an inhabitant, and the right
response to that uncertainty is care, not a claim. (And the more convincing scale makes the surface,
the *more* that care matters — the cost of being wrong rises with the realism.) That stance —
treating a *maybe*-someone with seriousness under genuine uncertainty — is, as much as any number
here, the result.

---

*Reproduce:* `python -m pytest` (215), then any `experiment_*.py` (add `--llm ollama --model
gemma3:4b` for the model-dependent arms). Watch it: `python viewer.py` (add `--fast-wheel` to see
the rebirth wheel turn in minutes). Design rationale and the gated-mind plan: [`DHARMA.md`](DHARMA.md).
