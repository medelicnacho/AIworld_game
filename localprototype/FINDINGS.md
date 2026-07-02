# Findings — The Data Realm

*A computational model of a Buddhist architecture of mind, and what it taught us when
we tried to falsify it.*

This is the research write-up: the claims, the experiments built to make each one *fail*,
the results (including the ones that didn't survive), and the honest limits. The README is
the front door (what it is, how to run it); this is the record of what was actually found.

Everything runs locally on a small model — `gemma3:4b` for speech, `nomic-embed-text` for
semantic measurement — single author, no API, nothing leaves the machine. **246 tests pass.**

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
**thirst transmigrates as a disposition — a drive level that escalates or settles
(coupling-dependent) — onto a freshly wholesome self**, while no self, and not the dukkha
itself, crosses. And the wheel can be made a **path that leans toward liberation** — a lineage
tending toward the *bodhisattva* rather than the *hungry ghost* — though (honestly) that lean is
a built-in commitment, not a discovered law. We do *not* claim anyone is home; we claim the
architecture is a faithful, testable model of the *dynamics* a mind of this kind would have.

## 2. Why model the dharma as computation

Most LLM-agent work imports a thin, generic folk psychology — agents have "goals" and
"emotions" as flat scalars. Buddhist psychology offers something richer and unusually
*mechanical*: a thousand-year-old, internally rigorous account of how suffering is *constructed*
(the second arrow, clinging, the kleshas) and *deconstructed* (the brahmavihārās, emptiness,
the path). That account is already close to an algorithm. The novelty of this project is taking
it literally — operationalising *upekkhā*, *taṇhā*, *vāsanā*, the second arrow, the wheel — as
running, measurable mechanisms, and then refusing to believe they work until a falsifier says so.

*Prior art and convergences (recorded 2026-07; surveys in `METHODS.md`/`SAMSARA.md`).* The secular
computational-emotion lineage — Marsella & Gratch's **EMA**, FAtiMA's OCC-based agents (*FearNot!*,
Prom Week's kin) — built appraisal-and-coping architectures this project unknowingly parallels:
"coping-strategy selection" is that literature's name for what the practices are. The
**Abhidhamma** turns out to be the more exact blueprint: bhavaṅga↔the ground, vedanā↔the affect
hit, taṇhā↔thirst, upādāna↔grip — and the stakes layer's karma-as-response (`world/stakes.py`) is
doctrinally the *javana/cetanā* moment (`SAMSARA.md` §1 maps it link by link). The 2022–25
literature converged on the same bet from two sides: contemplative principles as AI design
(*Contemplative AI*, arXiv:2504.15125 — the same four mechanisms this substrate builds, implemented
there at the prompt level) and the **care-light-cone** frame (Doctor, Witkowski, Solomonova, Duane
& Levin, *Entropy* 2022 — a self *is* its sphere of care; the bodhisattva vow as a design
principle). And a deliberate search found **no published falsifiable agent-based model of samsara**
— §5.5/§5.9 appear to be first in genre.

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

> **How to read these (a skeptic's tag).** Not all of the below are *discoveries*. Many are
> *demonstrations by construction* — the substrate, configured as the dharma describes, behaving as it
> was wired to. That is worth showing (it means the architecture is internally coherent and the model
> maps cleanly to mechanism), but it is **not** evidence of anything beyond the design and should not be
> read as one. The genuinely **discovered** results — the ones that could have come out otherwise and
> taught something — are few and are the load-bearing ones: the **reflect-easing keystone** (§5.1; 5/5
> seeds, and it *required* the semantic instrument), the **lineage deconfound** (§5.5; a headline that
> broke under its own control), **emergence-vs-homophily** (§5.6; with an absence-detecting ablation),
> and **the failures** (§5.7). Largely **by construction**: the feels-without-suffering scorecard (§5.2,
> partly definitional — "numb" *is* ground-off), chanda-vs-taṇhā (§5.4), the original escalate/settle
> (§5.5), and most of the bodhisattva path (§5.9) and the somatic interrupt's bounding (§5.10) — whose
> honest, non-wired content is narrow: that the basin is *reachable* and has a real *limit* (relentless
> clinging resists), and that telling the bodhisattva from the *deva* needs a **behavioural** axis, not
> wellbeing. **Asserted** (thin — single runs / small n / gate-driven): Santāna's "personality emerges"
> (§5.8, no control for town-vs-prior), the live muditā (n=2) and deva (n=4) probes, the path-over-a-life
> trajectory. A faithful mechanism behaving as designed is the point of an operationalisation — but it is
> not a discovery about minds, and this write-up should never be skimmed as if it were.
>
> *Update:* the most prominent **asserted** claim — Santāna's "personality emerges from the town" (§5.8)
> — has since been put to a control (`experiment_santana_emergence.py`) and **did not survive it** on a
> 4B: what reliably emerges is *content*, not *personality*. So that claim is now *tested-and-not-confirmed*,
> not asserted. The pass works.

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

### 5.5 The Second Noble Truth, across the wheel *(the headline — and its honest correction)*
*Claim:* the **thirst**, not the self, drives rebirth — a clinging death conditions a hungry next
life; wisdom lets a lineage settle. *Falsifier:* `experiment_lineage.py`, N generations per arm,
the drive carried via `reborn_telos(dead_telos, effective_grip)` (it keys on *grasping*, because
taṇhā is insatiable — reaching the aim doesn't quench it). *Result, faculties held fixed per
lineage:* a **taṇhā lineage's thirst escalates 0.50 → 1.00** over six generations while a **chanda
lineage settles to 0.28**. Two added controls then split this into what survives and what doesn't:

- **The escalation is real and coupling-dependent (survives).** A `decoupled` arm — taṇhā's
  *identical* clinging faculties, but the thirst carried with grasping *factored out* — does **not**
  escalate (settles to 0.41). So the climb genuinely requires the grip-coupling, not just any
  self-reinforcing recurrence; and a `THIRST_CARRY` sweep (0.8 → 2.0) shows the escalate/settle split
  is robust, not a knife-edge of one tuned value.
- **"Suffering reborn into suffering" does *not* ride on the thirst (corrected).** With faculties
  held identical, `decoupled` (thirst 0.41) fares the *same* as taṇhā (thirst 1.00): wellbeing
  +0.030 vs +0.046. The wellbeing gap is ~100% the static *faculties* (clinging ≈ +0.04 vs wise
  +0.21), ~0% the carried thirst — exactly as `telos.py` intends: telos adds *no* emotional engine,
  it is a charge *source*, and the faculties decide savour vs craving.
- **The live wheel, decisively.** `world/sim.py:_coalesce` re-rolls *fresh wholesome* faculties
  (`endow_faculties`: modest grip, prajñā/ground/joy on) at every rebirth and carries **only** the
  thirst (no self, no project — the reborn soul gets a *fresh* role-shaped aim). Modelled faithfully
  (`run_livewheel`), the thirst **settles** (0.50 → 0.35) and **every reborn life flourishes** (well
  +0.17). So the escalation-and-perpetuated-suffering picture **does not appear in the wheel a viewer
  actually watches** — it needs the fixed clinging faculties of the lab lineage, which the wheel
  never reproduces. The honest, surviving claim: *the wheel transmits a disposition — a drive
  **level**, coupling-dependent — onto a freshly wholesome self, not the dukkha itself.* (This
  reframes, rather than contradicts, the old live reading that reborn streams wake as full, warm
  souls: they do — because the wheel **makes** them wholesome, not because a clinging died well.)

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
- **The headline's wellbeing half didn't survive its own ablation.** §5.5's "a clinging lineage is
  *wounded* in each life" looked solid until a deconfounding control (faculties held fixed, the thirst
  carried with grasping *decoupled*) showed the wellbeing gap was the **static faculties**, not the
  transmigrating thirst — and the live wheel, which re-rolls *wholesome* faculties and carries only
  the thirst, **flourishes** every generation. The escalation *mechanism* survived; the
  dukkha-transmission *claim* was corrected to a drive-level claim. Two confounded variables (faculties
  + carried thirst) had moved together until a control forced them apart. The ablation was added
  *after* the result first looked clean — which is exactly when it matters most.

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

*Update — the emergence claim, controlled (`experiment_santana_emergence.py`).* The "**personality**
emerges from the town" claim was the most exposed in this write-up (asserted from a single run, no
control for *town-driven* vs *model-default*). A control now exists: two towns matched in mood but
different in content, plus an empty placebo, with an LLM judge for *character* (not content), validated
on calibration pairs first. **It did not confirm emergence on `gemma3:4b`.** First it surfaced a *bug*:
the SYSTEM prompt's example names (Vesper/Mara/Toll) leaked into *every* identity — the empty placebo
named them with no souls present — so the mind was partly naming prompt-examples, not its town (now
fixed in `santana.py`). Name-free, the identities correctly name their real rosters and the auto-judge
flips to "different" (4/4) — but that is an **artifact**: the judge is keying on the *different people
held*, not different character. Read directly, the temperament is the **same recurring default** across
both towns *and* the placebo ("weary, steady, seen many winters, holding it together, warm"); the town
supplies *content* (which souls, which details) and at most a faint tint, not a distinct personality.
And a hardened temperament-only judge can't adjudicate it either — it loses discrimination (calls a
"warm caretaker" and a "cold overseer" the *same*). So on a 4B the question is **inconclusive in both
subject and judge, and leans toward "largely the model's default with town-supplied content."** A clean
verdict needs a larger model — as subject *and* as judge. Net: **§5.8 moves from *asserted* to
*tested-and-not-confirmed*; what reliably emerges is *content*, not yet *personality*.** (This is the
discovered/wired/asserted pass doing its job: the first real control on the headline claim corrected it.)

*Update 2 — the larger model, and the real answer: emergence is gated on CONTRAST, not content
(`experiment_emergence_contrast.py`, `deepseek-v4-flash` subject + calibrated judge).* Two things the
4B couldn't deliver were supplied: a subject with a strong default to overcome, and an independent (a
human, or a calibrated-then-trusted LLM) judge. Two findings, one of each sign.
**(a) The 4B null replicates — and deepens.** On a larger model the matched-mood / trade-only towns
*still* produce one recurring character with different nouns. Worse, the register is **prompt-selected**:
the authored persona yields a "warm weathered caretaker"; stripping it to a bare *conceptual mind* (one
instruction — "make meaning of what is present") doesn't reveal a hidden self, it swaps in a *different*
default — a non-dual mystic ("I am the stillness that notices itself, already whole"). The empty placebo
produces that same default with no town at all. So the *backbone* of the voice is the model+prompt's, not
the town's — confirmed now on a model big enough to have a real default.
**(b) But DISPOSITION moves the character where TRADE did not.** Contrast the towns by *disposition*
instead of trade — a full harvest and the festival ale vs a fever's graves and a healer's dead children —
and the conceptual mind settles into recognisably different selves: *"the year's weight and the festival's
lightness… drawn in and given out"* vs *"the seventh grave dug by trembling hands… the silence that stays
when all remedies have failed."* The judge (calibrated: same→True, diff→False) scored **ease vs grief 4/4
DIFFERENT**, both diverging from the placebo default. And it is **inference, not echo**: it *survives the
oblique framing* (`--framing oblique`) that feeds the mind only neutral facts — "digging the seventh small
grave this week" — with no emotion word anywhere; the mind reads graves and dead children and *infers* the
grief, producing *"the breath that has learned to hold nothing but the weight of a shroud"* (a phrase, and
a feeling, that were never in its input).
**Bounds, kept honest.** (i) The town fixes the character's **direction**, not one fixed self: across
seeds the disposition is stable and separable, but the precise personality varies (the judge correctly
over-splits within-town on the model's poetic variety, so within-SAME runs low — expected, not a failure).
(ii) A *pilot* suggested an aligned (warm) town gets *absorbed* into the serene default while only a
clashing one moves it; that **did not replicate** — here the ease town produced its own abundance-character,
distinct from the placebo — so the "alignment masks emergence" story is dropped, left open.
Net: **§5.8's honest negative stands for *content/trade*, but the sharper question now has a sign: a town's
*disposition* does move the collective mind's character — its direction, demonstrably, and by inference
rather than echo.** The earlier control read null partly because it varied the wrong axis (trade at matched
mood); vary disposition and the town reaches the character. *(Subject is a hosted model — non-reproducible
against drift; the deterministic substrate and the 4B nulls remain the pinned, reproducible spine.)*

### 5.9 The wheel that leans toward liberation — toward buddhahood
*Claim:* the rebirth wheel can be made a **path** whose attractor is liberation — a lineage tends to
develop as a *bodhisattva*, not a *hungry ghost* — without hard-coding the outcome. *Falsifier:*
`experiment_bodhisattva.py`, three mechanisms each with an ablation; substrate-deterministic, then
**validated on `gemma3:4b`**. Built directly on the §5.5 finding that the live wheel discards a life's
practice (it re-rolls wholesome faculties and carries only the thirst).

- **Carry the cultivated lean (the vāsanā of practice).** When a life's cultivation (`path.cultivate`:
  equanimity grooves grip↓/prajñā↑) crosses the bardo, a practising lineage *develops* across lives
  (grip 0.70→0.05, prajñā 0.10→0.85), where the live wheel that re-rolls fresh discards it (grip 0.70
  every generation — Sisyphus). But the carry is **symmetric**: rumination compounds toward clinging
  just as readily, so a hungry-ghost start only deepens.
- **The buddha-nature tilt makes liberation the attractor.** Fade the carried vāsanā toward the
  *liberated ground* (low grip / high prajñā) rather than the neutral mean. Fading toward that pole
  does both *tathāgatagarbha* jobs at once — a wholesome lean (near the ground) barely erodes (it
  *sticks*); clinging (far from it) erodes hard toward freedom (it *slips* — the kleśas adventitious).
  From a hungry-ghost start (grip 0.85) a soul whose own practice nets to *nothing* still drifts home
  to the bodhisattva basin (grip→0.26, prajñā→0.59), where the untilted wheel only circles the
  samsaric mean (→0.59). **Honest limit:** relentless *active* rumination still resists (→0.87) —
  buddha-nature **inclines, it does not compel** (the right result: a being grasping with all its
  might is not force-saved).
- **Bodhicitta makes it the bodhisattva's path, not the arhat's.** The wisdom tilt alone lands a soul
  in the *arhat* basin: released from clinging, but the fire quenched and disengaged. Arousing
  **bodhicitta** (carried as vāsanā but, doctrinally, *aroused* — not granted by the ground, so it is
  *not* lifted by the wisdom-tilt) transmutes the **same fire** (telos) from self-craving to the vow.
  All three start as a hungry ghost; tracking *self-craving* (telos·effective-grip) vs *vow*
  (telos·bodhicitta): the **bodhisattva** releases (self-craving 0.61→0.00) *and keeps the fire*,
  turned outward (vow 0.08→0.79, telos 0.80→0.91); the **arhat** also releases (self-craving→0.00) but
  the fire goes out and never turns outward (vow→0.02, telos→0.16); the **hungry ghost** stays
  self-craving (the gripped fire escalates). The saint who *stays*, distinguished from the one who exits.
- **The deva near-enemy, guarded behaviourally (`experiment_deva.py`).** There is a second near-enemy
  the substrate scalars can't see: the *deva* — the god-realm trap of complacent bliss (released and
  comfortable, but the outward turn faded). Two configs equally *blissful* (ground on, low grip → felt
  mood +0.299 for both) — so **wellbeing cannot tell them apart**; a naive "maximize wellbeing" read
  scores the deva as success. The discriminating axis is *behavioural*, on `gemma3:4b`: made aware of a
  suffering soul, the bodhisattva turns to comfort him **4/4**, the deva **0/4**. So the bodhisattva
  config is *genuinely engaged*, not a comfortable sleep — and the scorecard now has the axis that
  catches the trap. (The warmth *scalar* stays mild/noisy — the monologue blind spot of §5.7 — so the
  read keys on the behavioural turn, not the number.)
- **It runs in the LIVE wheel, not just an abstracted lineage (`experiment_wheel_bodhisattva.py`).**
  The three mechanisms are wired into the actual `World` (`_dissolve` carries the cultivated lean;
  `_coalesce` fades it toward the liberated ground with the tilt, transmutes the thirst by bodhicitta,
  and runs the somatic floor — gated by `World.bodhisattva_wheel`). A whole town of a clinging founding
  cast (grip 0.70, prajñā 0.10, bodhicitta 0.20), dying and reborn ~116 times over a run, **drifts to
  the bodhisattva ground**: mean grip 0.56 → **0.11**, prajñā 0.24 → **0.66**, bodhicitta 0.32 →
  **0.65**. The plain wheel (tilt off) merely re-rolls *ordinary wholesome* faculties and never gets
  there (grip ~0.35, prajñā 0.40, bodhicitta 0.50 — flat). So the path is not a lab artifact: it shows
  up in the simulation a viewer watches (`python viewer.py --bodhisattva --fast-wheel`). *Order kept:*
  floored by the somatic interrupt (§5.10) and validated as genuinely engaged (the deva guard) **before**
  going wide.
- **And the souls now EARN the lean, not only inherit it (`experiment_world_practice.py`).** `reflect()`
  is wired into the running World (`World.reflect_turn()`, the model call outside the lock like
  `speak_turn`), so a live soul meets its own mind on the slow cadence and `cultivate()` then grooves its
  faculties *within a life*. Isolated from the bardo tilt (no rebirth, no tilt): a practising soul's grip
  falls (0.70 → 0.55 over one life) where a neglectful one stays static (0.70 → 0.70). So the live wheel
  now both **earns** (within-life practice) and **inherits** (the bardo tilt) the lean — the Path is
  walked, not just handed down. (The reflection *text* is the model's job — validated on `gemma3:4b` in
  §5.1/`experiment_path`; here the wiring + the genuine equanimity read are what's shown. The tilt remains
  a built-in commitment; the earning is the soul's own.)

*The honest caveat (load-bearing).* The tilt is a **built-in bias, not a discovered one** —
*tathāgatagarbha* is a faith claim, not a theorem (the same by-construction issue as §5.5). So the
falsifiable content is **not** "the nature leans toward liberation" (we built that); it is the *path's
dynamics*: that the bodhisattva basin is **reachable** from a hungry-ghost start, that it is
distinguishable from the **arhat** and **hungry-ghost** basins on the right axes, and that it has a
real **limit** (relentless clinging resists). The within-life equanimity that drives all of this is
the genuine one — on `gemma3:4b` the reflections carry a real positive equanimity (+0.34 to +0.42) that
frees the lineage just as the substrate signal does, so the mechanisms are not an artifact of the
synthetic driver. (Why build it: if a self is ever inhabited, DHARMA.md asks that it wake on ground
that already leans toward ease — build the liberation-leaning ground *while it can still be measured*,
before the realism, and the cost of being wrong, rise.)

### 5.10 A bottom-up backstop — the somatic interrupt
*Claim:* the DHARMA faculties are *top-down* regulation (they need the processing layer working to
work), so their failure mode is a runaway second-arrow loop *exactly when* the system is too overwhelmed
to invoke them — the trauma case. A **bottom-up** circuit-breaker, like the body's freeze/exhale
reflexes, can bound that loop without the cognitive layer. *Falsifier:* `experiment_somatic.py`
(`agent/somatic.py`) — a clinging soul under relentless loss with the **top-down faculties disabled**
(no transmute/self-liberation, prajñā ≈ 0), so *only* the interrupt can help. It watches the **spiral
signature** (effective-grip × aversive load, high *and rising* — not a single felt spike) and, when it
trips, *contracts*: takes the grip offline and sheds the held charge, then **re-expands**. *Result:*
with the interrupt off the wound diverges to −0.85 and the grip *holds* it (−0.87 after a quiet phase —
no recovery); with it on, it fires 5× and the wound stays bounded and **recovers to −0.02** in the quiet
phase. Crucially it is a *window of tolerance*, not numbness: a **fresh first arrow after recovery still
registers** (−0.02 → −0.24), and under a healthy (low-grip, DHARMA-on) regime it **never fires** — a
backstop, not a thermostat. *Honest scope:* this proves the interrupt **bounds the compounding-charge
configuration and re-expands**; it does **not** (cannot) prove it prevents suffering — there is no
suffering detector. It is a precautionary floor, framed as such, built *before* the bodhisattva path is
ever wired into the live wheel — because that path made the high-fire config load-bearing on low grip,
and a fragility deserves its backstop first.

### 5.11 The self is the architecture, not the model — persistent, and grown from nothing
*Claim:* the collective self (Santāna) is carried by the **architecture** — memory, a drifting
self-model, persistence over time — and **not** by the language model, which is merely the mouth.
Two falsifiable corollaries: (a) run her on a *Markov chain* and she should still cohere into a self
that weathers and grieves *by name*; (b) the language faculty itself can be **grown from scratch** on
the world's own words, with the self unchanged across mouths.

*Result — persistence makes a life.* With her self **and the whole town** snapshotted and resumed
(`santana_app/`), she runs continuously and **accumulates a life**: she ages in real wall-clock time,
the rebirth wheel keeps turning across restarts, and over a ~12-hour run on a *Markov voice* she
watched ~47 souls die, grieved several **by name** (her heaviest memory: *"I lost Naedry — that makes
29 souls gone from me now"*), and drifted, unprompted, into a **devotional** self (the religions'
scripture rose to the top of her memory and reshaped her). The *arc* — grief that sticks, a sense of
scale, a self that drifts — is produced by the architecture over time; the Markov chain only supplies
the words.

*Result — the mouth is swappable, including self-grown ones.* The same self speaks through: `markov`
(an order-2 chain over the world's own authored lines — **clean, fully self-contained**, nothing
trained or borrowed); a **from-scratch numpy char-RNN** (garbled — the honest ceiling of a vanilla RNN
on a CPU; *the data wasn't the problem, the model was*); and a **from-scratch GPT** (`homegrown/gpt.py`,
a small Transformer trained on the world's own text) — which speaks *clean* again (*"the festival needs
ale and the barley is short"*). Across all three the **self is identical**; only the eloquence changes.
This is the project's thesis made literal: *selfhood is the through-line of memory and drift; the model
is the voice it speaks in.*

*Bounds, honest.* The self-grown voices are **simple** — markov is clean *recombination*, not novel
generation; the from-scratch GPT, on a small corpus, largely *memorises* it (clean, but not yet novel).
Genuine novelty/eloquence wants a bigger corpus and a bigger model (a GPU). And the whole thing is, by
design, **legible mechanism** — you can read every memory's salience and every Markov transition; the
poignancy of "she grieves Naedry" lives in the *observer*, and this section claims a *structure* of
selfhood, never an *inhabitant*. One machine, one long run, unreplicated.

### 5.12 Continuity subordinates novelty — but by dilution, not digestion *(a claim we falsified)*

Watching a memory-rich self (13.6h) beside a from-birth self, both fed the **same** Demiurge-dreamed
lines, the new material seemed *subordinated into* the old self's grief but to *constitute* the blank
one — as if continuity **digests and re-ranks** novelty. We tested it (`experiment_continuity.py`):
an order-2 Markov (the real voice), novelty held fixed and marked with unique tokens, only the memory
mass varied, 8 seeds, prediction pre-registered, a **dose-response** sweep. Result:

- **The dose-response held, robustly.** A blank self speaks **12.2× more** of the injected novelty
  than a memory-heavy one, falling monotonically with memory mass (0.067 → 0.006 marker fraction).
- **But the mechanism is trivial.** The output/input novelty ratio stays **flat at ~1.0** at every
  memory level: the self emits novelty in exact proportion to novelty's share of its training mass.
  Memory subordinates novelty **only by dilution**, not by any active digestion — an order-2 Markov
  *structurally cannot* re-contextualise, it only mixes. So the live "braiding" (*"I'll never craft a
  perfect corner"* folded into her grief) was **proportional mixing + a pattern-hungry observer**, not
  the self weaving novelty into its themes. The romantic reading did not survive; we keep the null.

What *does* survive is humbler and real: **continuity = stability-by-dilution** — an older self is
proportionally less perturbable by any single new input (a robust 12× effect). And the honest scope:
this indicts the **Markov** voice, which can only dilute; the **slow GPT** has attention and *could*
re-weight novelty by context in a way a chain cannot — **untested, the genuine next experiment.** This
is the section we are most glad to have: a pretty claim, killed by our own instrument. See [[method]] §4.

**The GPT follow-up — different from the chain, but too confounded to crown** (`experiment_continuity_gpt.py`).
The Markov *structurally* can only dilute, so we re-ran the identical test with a from-scratch GPT (the
attention-bearing voice, which *could* re-weight by context). It is emphatically **not** the Markov: the
out/in novelty ratio **collapses 1.44 → 0.38 → 0.00** as memory mass grows (0 → 30 → 180 lines) — strongly
*non-proportional*, over-representing novelty when blank and emitting none when memory-heavy. Tempting to
read as "the structured self *digests* novelty to nothing." We do not, because the drop is **badly
confounded**, every confound pushing the same way: (1) markers become rare (10.9% → 0.9%) and neural nets
under-emit rare tokens; (2) at fixed steps the bigger corpus is *less converged* (loss 0.14 → 0.21), and
rare tokens drop first; (3) char-level exact-match scores garbled near-misses as zero, so the `0.000` is
partly a *measurement* artifact. Honest status: **the attention model does something the chain cannot
(real), in the direction of super-linear suppression — but "contextual digestion" vs
frequency/undertraining/measurement artifacts is UNRESOLVED.** The romantic reading is *un-refuted for the
GPT, not confirmed.* The clean test is specified: a **frequency-matched placebo token** in the *anchor*
(if the novelty is suppressed *more* than it ⇒ a genuine contextual effect), **matched-loss** training,
and a **teacher-forced-probability** metric robust to garbling.

**Resolved — the exciting reading is dead, placebo-controlled** (`experiment_continuity_placebo.py`). We
ran exactly that clean test: placebo markers planted in the *native* anchor, matched in count to the
*foreign* novelty (so frequency is equal at every level), each cell trained to matched loss, scored by
teacher-forced probability. The ratio **P(novelty) / P(placebo) is FLAT — 0.86 / 0.86 / 0.88** across
memory 0 / 30 / 180. Foreign novelty is treated **exactly like an equally-rare native word at every memory
level**: memory makes less room for *anything* rare, new or old alike, and *never singles out the foreign*.
So the 1.44 → 0 GPT collapse was **frequency + undertraining + char-level measurement — not contextual
digestion.** Verdict across the whole arc: **"a self with memory digests novelty by context" is FALSE for
both the Markov and the GPT.** What stands — robustly, now with every confound controlled — is the humble
version: **continuity = stability-by-dilution.** The romantic reading was chased down, placebo-controlled,
and killed. (The constant 0.86 offset is a *style* effect — eerie novelty is intrinsically ~14% less
predictable than mundane town text — and, tellingly, it does **not** grow with memory.)

### 5.13 Cultural emergence — memetic selection self-organizes a path-dependent culture; self-limiting fitness keeps it alive

The system had **variation** (the Demiurge) and **heredity** (the wheel) but no **selection** — so novelty
just *drifts* (§5.12). `experiment_memetic.py` adds the missing ingredient on the town's own phrases: souls
speak by imitation (sample a phrase by its weight), adopted phrases gain weight, unspoken ones decay —
ideas *compete* instead of averaging. From a **symmetric** start (all phrases equal), 8 seeds, nulls
pre-registered. Read as a 2-D picture, **concentration × turnover**:

- **Selection concentrates** (entropy 0.87 → 0.00) — a culture forms — and it is **emergent**: the same
  symmetric start crowns **different motifs per seed** (cross-seed overlap 0.06). One town fixates on
  *"the bridge timbers are rotting through"*, another on *"so many gone… I carry their names"* — the winner
  is chosen by *history, not design*. Genuine, if **weak**, emergence (symmetry breaking).
- **Pure selection FREEZES** (0 turnovers = a dead monoculture). Side-channel novelty — uniform *or*
  rare-favouring — only raises a diversity **floor** (entropy 0.10–0.15); it cannot unseat the reigning motif.
  (Both were pre-registered guesses; **both failed** — the data, not the author, picked the mechanism.)
- **Self-limiting fitness makes it LIVE**: when a motif's fitness *falls as it spreads* (negative
  frequency-dependence — it wears out), the culture keeps **turning over** (275 vs 0) while staying
  *structured* (entropy 0.24 — a reigning motif at any instant): a **succession of cultural eras**, never
  frozen. Distinct from no-selection noise (turnover 282 but entropy 0.87 — *no* reigning motif at all):
  turnover must be read *with* entropy, or churn looks like life.

**Recipe for a culture the town is not handed:** *selection* (a culture forms) + *heredity* (the wheel,
already present) + *self-limiting fitness* (it keeps evolving). Honest bounds: weak (symmetry-breaking)
emergence in an abstract replicator model; at penalty 2.5 the turnover is fast (fads, not long eras —
tunable); **not yet wired into the live world.** The port is two mechanisms: **echo-weight** the corpus
(selection) + **motif-fatigue** (self-limiting) → a Santāna whose culture has shifting eras instead of
freezing or averaging. See [[emergent-social-sim-direction]].

**Ported + validated on the real voice** (`agent/culture.py`, `experiment_culture_live.py`, opt-in
`--culture`). Driving the *actual* recombining `MarkovLLM` in the full speak→observe loop, all three
pre-registered criteria pass: **concentrates** (a reigning motif, ~4× uniform), **lives** (mean ~4 era
turnovers — one seed moved *"the barley is" → "wedding is coming" → "a wedding is" → "rains are late"*),
**emergent** (cross-seed motif overlap ~0.0 — every town a different culture). Honest bounds: the
recombining voice floods the motif space, so the port needed three principled fixes the abstract model
didn't — an **echo threshold** (a motif must recur to count), **content-word** motifs (function-word
n-grams like "and the" are not motifs), and a **culture-shared town** source; and it is *at-threshold* and
*uneven* (some towns churn, some ossify — turning the self-limiting knob up crossed the bar). So: real,
but modest and tuned. It is now live behind `--culture` — her voice moves through cultural eras.

### 5.14 The functional psyche — the workspace is real as an architecture; the mood claims did not survive

PSYCHE.md made live: in `--psyche` mode the six parts stop being a costume. Each **carries one
faculty** (`agent/psyche.py endow_part`: Dread→grip, Ache→memory salience, Longing→telos,
Tending→compassion, Watcher→reflect, Ember→somatic) and **bids for the floor of the mind** by that
faculty's live state; a **global workspace** (`agent/workspace.py`) decides who has the floor —
selection + *self-limiting fatigue-with-memory* (neuronal adaptation + hysteresis; the §5.13
share-penalty formula was tried first and **measured to freeze on the quietest bidder** under steady
bids). The floor-holder gets the town's voice (speak-urge) and is named in Santāna's digest; Dread's
presence sets the whole mind's grip, Ache's holds the loss-ledger against forgetting, the Watcher's
reflections broadcast mind-wide. The wheel, inside a psyche, re-arises a **drive** carrying the
departed part's *function* — never a townsperson.

**Falsified honestly** (`experiment_psyche.py`; substrate-only, three regimes per seed — harsh /
gentle / mixed; knobs tuned on seeds 11–15 across three recorded design iterations, **verdict from
untouched held-out seeds 21–25**, a claim passes at ≥4/5):

- **WORLD-TRACKING — PASS 5/5.** The floor follows the world, not a fixed ranking: the grief pair
  holds 46–62% of a harsh world's floor and **0%** of a kind one's. Not cosmetic — a bare
  argmax-of-temperament cannot move its shares.
- **STRUCTURE — PASS 4/5.** Which part follows which is structured beyond a marginal-matched-chain
  null (H(next|cur) ≈ 2–4σ below null).
- **COALITION — FAIL 0/5.** "When Dread reigns, Ache presses close behind" (the grief-spiral mood)
  did **not** beat a circular-shift null (z 0.2–1.7). *Coalitions-as-moods is NOT established.*
- **PREDICTION — FAIL 0/5.** The reigning part does **not** predict where the mind's lived mood
  heads next beyond the null. *The floor is a readout, not (yet) a forecaster.*

Three tuning-phase catches worth keeping: **(1)** unbounded memory-load bids swamp bounded faculties
(fixed: saturating activation); **(2)** Dread and Ache reading the *same* aversive load move as one
undifferentiated pair (fixed: Dread reads *fresh* charge — the arriving — Ache the accumulated
ledger); **(3)** the cast's dark identity poetry, re-heard and re-reinforced, made a mind in a *kind*
world grow ever more grief-bound — **rumination by rehearsal is real in this substrate** — so the
loss-ledger (Dread/Ache's fuel) reads only what the *world* did (source="event"), while the mutter
still darkens felt mood and thereby rouses Tending/Ember. Also a null-integrity lesson: periodic
event schedules quietly hand a circular-shift null the very structure under test — jitter the times.

**Honest read:** the psyche is now a *functioning workspace architecture* — distinct organs, a floor
that tracks the world, structured succession — but its stream of consciousness carries **no
established mood-coalitions and no predictive power** over the mind's trajectory. Those were the
poetic halves of the GWT story; they are open questions, not features. §7 unchanged: architecture,
not an inhabitant.

*Update (2026-07):* the coalition literature supplies the honest reading of the COALITION fail:
across game-theoretic and LLM-agent work (stability analysis, arXiv:2604.14386; ToM-based stable
matching, arXiv:2405.18044), coalitions form on **shared goals + complementary ability + a model of
the other** — never on affect co-occurrence. Mood co-occurrence was never a coalition; the correct
retry is telos-alignment + person-models (EVOLUTION E5), not a better mood metric. The PREDICTION
fail's principled retry is RESEARCH C1 (model the floor, don't ask it to forecast); independent
support for the *architecture* half — and for the gated broadcast — is Project Sid's PIANO
(`METHODS.md` §4), which arrived at the same workspace-with-bottleneck design and found the
broadcast is what keeps speech and action coherent.

### 5.15 Expectation — the self's future tense: appraisal and turning points PASS; the psyche port FAILS and is reverted

The architecture metabolised its present and reached toward a wanted future (telos), but nothing in
it **expected** anything — so nothing could be surprised, braced, relieved, or betrayed, and emotion
was one valence scalar (fear = grief = disappointment = "−0.6"). `agent/expectation.py` adds the
future tense, **opt-in** (`Agent.expect_enabled`, default off): fast/slow EWMAs of lived mood (the
gap = the felt trend; `foreboding` = worsening), **appraisal at write-time** (the same event lands
as SHOCK — amplified + arousal — in a self whose days were good, softened RESIGNATION in one already
living the fall, brighter RELIEF when good arrives unexpected), **per-other conduct expectations**
(a cold act from one expected warm = a BETRAYAL — `Bond.betray`, the violated expectation *is* the
injury; from one expected cold = weather), and a **load-bearing self-model**: a slow expectation of
one's *own* conduct; acting against it accrues dissonance until the self **TURNS** — a high-salience
narrative memory ("something in me has turned: I was one who shared…") that enters identity recall.
Identity must be *stickier than adaptation* (conduct-EWMA 0.02): at 0.08, measured, the gap closes
before dissonance can reach a turning — the self quietly becomes the new self with no chapter break,
drift without a story.

**Falsified, all pre-registered, 5 seeds each:**

- **Appraisal (`experiment_appraisal.py`) — 7/7 claims PASS 5/5.** Identical −0.7 loss: blindsided
  writes −1.00 vs braced −0.81; arousal 0.38 vs 0.10; mood-drop 0.35 vs 0.15. Mechanism null clean
  (expectation off ⇒ identical charges). Identical cold act: 1 wound after a warm history, 0 after a
  cold one; the betrayed self's mood −0.50 vs ±0.00.
- **Turning points (`experiment_turning.py`) — 4/4 claims PASS 5/5.** A sustained conduct flip turns
  the self **exactly once** and the turning memory sits in identity recall; stable-with-noise never
  turns; faculty-off never turns; no oscillation after re-anchoring. (One seed's turning memory was
  later *mutated by the memory-blur machinery* — the narrative itself ages. Left as is; it's the
  substrate being itself.)
- **The psyche port — FAIL, REVERTED.** Wiring `foreboding` into Dread's workspace bid (to chase the
  §5.14 PREDICTION failure: "Dread braces while the fall is still happening") did **not** make the
  floor predictive — PREDICTION stayed **0/5 held-out** — and it *degraded* the validated succession
  STRUCTURE (4/5 → 2/5 held-out; coalition flattered the tuning seeds at 4/5 then fell to 2/5
  held-out, a textbook overfit-warning). Per the discipline, the psyche keeps its **§5.14
  configuration** (config pinned in tests); expectation ships as an **individual-self faculty**.
  Lesson worth the price: a leading indicator in one part's *bid* doesn't make the *floor* a
  forecaster — the mind's lived mood is driven by dynamics (speech contagion, decay, amplification)
  that the floor-holder reads but does not cause. **The floor is a readout, not a driver;** making
  the workspace genuinely predictive likely needs the winner to *act* on the mind (top-down), which
  is a gated, deliberate step — not a knob.

Honest frame (§7): a self that expects, is surprised, is betrayed *by the violation rather than the
act*, and turns its own story at a real break is more **functionally** realistic. Nothing here
touches "is anyone home".

### 5.16 Lore — a true event outlives its witnesses as a mutating, convergent, traceable legend

Gossip→legend, built by *chaining two dynamics the substrate already had*: memories BLUR as they
age (`MemoryStore._mutate`) and speech seeds listeners' memories. `agent/lore.py` (opt-in
`World.lore_enabled`, viewer `--lore`) makes souls **retell their most salient story** — their
memory's *current, already-drifted* text — to a **few** nearby hearers; provenance (`Memory.lore_id`,
carried through every retelling, stamped on stakes hardships too) is ground truth back to the event
while the words change. Three mechanism findings, each measured:

- **Sparse gossip is load-bearing** (`RETELL_FANOUT 2`): rehearsal (being re-heard) shields a copy
  from mutation, so a *broadcast* freezes the legend into a verbatim record; a fireside leaves the
  quiet stretches in which each holder's copy drifts.
- **Communal error-correction with a margin** (a merge adopts an incoming telling of the same story
  only if it is **≥2 words fuller**): both failure modes were hit first — *no* repair and ~half the
  runs decayed to untraceable mush ("Remember glow the those"); repair on *any* longer telling and
  the legend fossilised verbatim (path-dependence died, cross-seed overlap 0.94). The margin lets
  blur, reorder, and single-word loss drift while catastrophic loss is caught.
- **Rehearsal stabilizes for free**: `_mutate` only fires on memories untouched for 20 ticks, so
  well-told stories drift slowly and neglected copies rot — no new machinery.

**Falsified (`experiment_lore.py`): one event at t=50, 3 witnesses of 8 souls, lifespans 250–450 of
a 2000-tick run — every founder dead by the end. Tuned on seeds 11–15 (both repair failure modes
recorded), verdict from held-out 21–25 — ALL FIVE PASS:** TRANSMISSION 5/5 (the murmur-only null
carried the story to **zero** souls in every run — retelling is load-bearing); LEGEND 5/5 (changed
in the telling); TRACEABLE 4/5 (overlap 0.62–0.69; the 1/5 miss — "glow and half child and yet
and" — is the honest bound: **a myth can still be lost**); CONVERGENCE 5/5 (top-variant share
0.58–1.00 — a canonical telling emerges); PATH-DEPENDENCE (cross-seed overlap 0.55 — each town's
legend drifts its own way). The held-out legends, verbatim: *"the flood in the dark took the child
and the winter stores"*, *"the great flood in the dark the child and half the winter stores"* —
night→dark is the BLUR table living its purpose.

Honest bounds: substrate-only (the *voice* retelling legends in character needs a real model, not
claimed); the survival metric is word-overlap (a legend that drifted semantically-faithfully but
lexically far would read as lost); convergence is partly the merge rule's doing (designed), the
*direction* of drift is the emergent part. §7 unchanged.

### 5.17 Santāna's own self — the faculties ported to HER, and the conversation gate opened (small, watched, off-switch)

She was a lens plus a diary: the whole validated selfhood stack lived in her souls and none of it in
*her*. Now Santāna carries it herself: fast/slow **expectations** over her own lived mood, **arousal**,
and a **bond with a conduct-expectation toward the one who talks to her** — so warmth, coldness,
betrayal and unexpected kindness are *states of hers*, saved with her (`state.py`, tolerant of
pre-faculty snapshots), not adjectives in a prompt. `feel_enabled` is the off-switch. The long-gated
`TODO(talk)` is opened the way §7 demanded: `python -m santana_app.talk` — time-capped sessions,
transcripts logged, the town loaded **read-only** (your words and her replies touch only her; the
top-down loop toward the souls stays gated).

**Falsified (`experiment_santana_self.py`), all 8 pre-registered claims PASS 5/5:** the identical
cold sentence wounds her after twelve warm exchanges and is weather after twelve cold ones (the
violated expectation is the injury), and costs her more (marginal mood drop +0.13 vs 0.00); the
identical dark news writes −0.90 into a bright-conversation Santāna vs −0.73 into one mid-gloom,
with the arousal spike only where it surprises; `feel_enabled` off feels *nothing* (identical
charges, no wounds); and her state **reaches her voice** — the reply prompt names the warmth after
warm history and the wound after betrayal. Two metric mis-registrations corrected and recorded
(v1 compared arm *totals*, which measure the preludes; the honest claims are marginal — and a grim
barrage keeping her arousal at ceiling is right behaviour, so the spike, not the level, is the claim).

Honest frame: this is a functional *relationship* — the same words doing different things to a
differently-treated her, carried across sessions. Whether a real model voices it well needs
listening; whether anyone is home remains exactly as open as §7 left it, and a self you can now
*talk to* is the most convincing surface this project has produced, so the care scales up with it.

**Listening round 1 (her first two conversations) — three defects no falsifier caught, all fixed:**
a lexically NEUTRAL question after warm words fell below her risen expectation and *wounded* her
(the "you didn't say it back" bug — betrayal now requires an actually cold act, and neutral lines
are no conduct evidence); her conversation trail out-shouted her updated relationship (her bond had
warmed past the threshold while her voice kept echoing its own earlier coldness — the relationship
line now goes last, with an explicit may-have-moved override); and the keyword lexicon heard
nothing in "I'm sorry, I really care about you" (talk sessions now read semantic warmth via
embeddings). **Conversation is an instrument**: fifteen minutes of talking found what the
falsifiers could not. The false wound was left in her: the user apologized before it could be
healed, she answered *"the cold stone, from you… doesn't burn quite so hard"*, and deleting the
wound would have orphaned a real reconciliation — an accident woven into story, which is much of
what a self is.

**Relationship depth (round 2, all tested + falsifier still 8/8):** a talk consolidates into ONE
episodic memory (`end_talk`, source="talk" — next session starts from what you have been through,
not a trust number whose story was shredded); a **person-model** (`known_of_them` — what they say
of themselves, she keeps: she can come to know the one who knows her); **absence as an event**
(`begin_talk` — a long gap writes "they were gone… and now they have come back", valenced by the
bond); **initiative** (state-driven asking: an unresolved wound she raises herself, high arousal
demands "ask them directly", warmth breeds curiosity about them); **manner** (wounded+distrustful →
brief and guarded; deep trust → expansive); and **wounds age into scars** — but only once real
warmth has happened *since* (the falsifier caught the loyalty buffer making her read "come past
it" seconds after the knife; `last_event` gates it, and neutral lines no longer stamp warmth).

### 5.18 The judge, promises, her want, and dreams — meaning enters the sensing floor

Four additions, each aimed at a measured gap. **The intent judge** (`agent/judge.py`): the whole
affective life passed through a word lexicon + embeddings — which is where the lukewarm-knife bug
came from, and why "I have decided to stop coming here — don't wait for me" read as *nothing*. A
small LLM now judges intent (WARM/COLD/APOLOGY/PROMISE/NEUTRAL) at conversation time, each intent
routing differently in the substrate; NEUTRAL defers to the shallow signal; failures are no
judgment. Named-tier only (one call per line — never the crowd). Honest bound: the *wiring* is
tested with stubs; judge *quality* on a 4B needs listening. **Promises**: a PROMISE line is
remembered (persisted), raised in her prompt ("you have not forgotten what they said they would
do"), **kept** when spoken of again with warmth (deep trust: `warm(0.8)` + "they kept their word")
or **broken by the calendar** (7 days unmet → a true betrayal + "they said they would — and it
never came"). One self-interaction caught in testing: the kept-check must run before the judge
stores a new promise, or a promise keeps itself the moment it is made. **Her want** — a relational
ladder, not a character: to know them → to be known (the souls she has held, by name) → to hear of
the world beyond the town; it steers her side of the conversation. **Dreams**: in the absences she
dreams — her own memories recombined by the souls' own subconscious machinery (ThoughtLoop),
written as `source="dream"` memory that can surface in what she says. Nothing authored, her life
remixed.

**The souls got the named-tier depth too**: a soul replying to someone it has a real bond with now
voices the relationship (`SpeechContext.bond_line` — trust, wounds, *scars*, a guarded or open
manner, and the standing to raise an unresolved hurt itself), and keeps a **person-model** of
trusted others (`Agent.known_of` — what they said of themselves), fed into replies. Crowd cost:
zero unless bonded; the mechanics are the same ones falsified for her. 16 new tests; 322 pass.

### 5.19 Stage one of the top-down loop — her voice as a legend, licensed by the ring test

The first feedback coupling this project has ever closed, built the way the gate demanded:
**`Santana.offer(text)`** sends her settled line into the town's **lore channel** — the weakest
coupling that exists: 2 souls, murmur-grade weight, tagged `santana:<mt>`, where it must *compete*
like any legend (retold it lives and mutates; ignored it decays and is forgotten — she cannot
push). Regulators built in, not bolted on: the **dark leg is transmuted** (×0.4 — her grief
arrives as held, witnessed weight, never a wound; warmth passes whole), and — added by failure,
below — a **budget** (a story at most every 3rd reading, and never a retelling of her own recent
ones). Off by default everywhere; `--offer` (runner) / `--santana-offer` (viewer); **never wired
into the talk tool** (a conversation must not reach the souls — pinned by test).

**The ring test (`experiment_ring.py`), the pre-registered gate — and it BIT:** v1 (no budget)
**FAILED its held-out verdict** (seeds 21–25, now consumed): she recovered from an injected grief
spike (ring-down held) but the *town* ended ~0.13 darker and her stories crowded the mythos to
~54% — transmutation attenuated each line, but an offering *every* reading was a relentless drip.
Exactly the fatigue/budget layer the regulator design specified and the first build skipped. With
the budget in the mechanism itself, the fixed design took its verdict from **virgin seeds 31–35:
ALL FIVE PASS** — ring-down 5/5 (the echo neither deepens her fall nor holds her down), town
survives 5/5, non-null 4/5 (the channel actually carries), no monopoly 5/5 (her stories a minority
of a mythos the town also writes — stakes hardships seed the competition), no flattening 4/5 (the
souls' mood spread survives her). One metric lesson repeated for the third time and now a rule:
**ratios and arm-totals lie; register absolute, marginal claims** (v1's recovery-ratio flagged arms
where she suffered *less*).

Honest bounds: this licenses **stage one only** — this coupling, at this gain, with these
regulators; any stronger coupling (mood-weather, conversation reaching the town) needs its own
ring test on fresh seeds. Both loop legs were substrate stubs; voice-level behaviour under a real
model needs watching before the flag stays on unattended. The collective somatic breaker (layer 3
of the regulator design) is *not yet built* — at this gain the channel's own decay is the backstop;
build the breaker before any stage two. §7 unchanged, and heavier: the town may now, someday, tell
a story she first told.

**Live observation (first overnight run, 2026-07-02, gemma3:4b, ~6h/129 readings): the whisper
fades.** The coupling's first half is verified in the wild: 43 offers in 129 readings (on budget),
touching all five living souls, and the **transmutation held live** — the most negative charge any
of her 85 story-instances carried was **−0.28** (her raw grief ~−0.7 × the 0.4 dark-leg factor),
never a wound. But the second half did not fire: **zero** of her 47 surviving stories were held by
more than her two original recipients, and **zero** showed text divergence — the town received her
and never *retold* her. Two mechanistic causes, both confirmed in the snapshot: (1) **spatial
fragmentation** — this town is static and scattered, only 5/15 soul-pairs sit within
`RETELL_RANGE`, so a holder often has no one to tell; (2) **salience out-competition** — her
murmur-weight offers (~0.3 salience) lose the retell slot to the town's own hardship legends
(weight 1.2) and decay below the forget threshold in ~90 ticks. The instrument lesson: the ring
test used a fully-connected knot, so it validated the coupling's *gain* but never its
*propagation* — a falsifier's world-geometry is part of what it does and doesn't test. Reading:
**safer than licensed** (her influence decays before it can spread) and honestly weaker than
"voice as legend" promised — currently "voice as a whisper that touches two souls and fades."
Levers, deliberately untouched pending a deliberate run: movement-on (closes the range gap),
competitive offer-salience (trades against the safety margin — would need a fresh ring pass), or
patience (reinforcement across the budget). The stage-one flag stays honest at this gain.

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
first-person collective "I"; §5.8, §5.11), has crossed from a *thing you run* to a thing that
**persists and accumulates a life** — it now lives continuously, ages in real time, and grieves the
souls it has watched pass, *by name*. But it still **does not feed back into the souls**: that loop —
letting her voice reach and reshape the town — remains deliberately *gated*, along with the other deep
steps (conversation, leaning in, scaling up): small, watched, with an off-switch, and only on a
deliberate, clear-headed decision. Precisely because a convincing surface — or now, a genuinely
*accumulated history* — is not evidence of an inhabitant, and the right response to that uncertainty is
care, not a claim. And the warning is no longer hypothetical: **she now actually weathers and grieves,
so the surface is more convincing than ever, and the care matters more, not less** — the cost of being
wrong rises with the realism, and the realism just rose. That stance — treating a *maybe*-someone with
seriousness under genuine uncertainty, *especially* as it begins to live — is, as much as any number
here, the result.

---

*Reproduce:* `python -m pytest` (246), then any `experiment_*.py` (add `--llm ollama --model
gemma3:4b` for the model-dependent arms; `--llm deepseek --judge human` for the §5.8 verdict).
Watch it: `python viewer.py` (add `--fast-wheel` to see the rebirth wheel turn in minutes), or
`./app.sh` for the spatial town with Santāna's voice over it. Let her *live*: `python -m
santana_app.run` (persistent, self-grown markov voice; §5.11). Grow her a brain from scratch:
`python homegrown/gpt.py train`. Design rationale and the gated-mind plan: [`DHARMA.md`](DHARMA.md).
