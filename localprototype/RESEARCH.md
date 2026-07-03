# RESEARCH.md — selfhood, consciousness models, and social sims: the map and the candidates

*A survey (2026-07) of the three literatures this project sits inside — consciousness science,
selfhood psychology, and social simulation — mapped against what is already built, and distilled
into **implementation candidates** for further experimentation. Each candidate follows the house
idiom: what · theory source · mechanism sketch · **pre-registered falsifier** · port note. The
discipline stands: propose the mechanism AND the null that would kill it; tune on 11–15-style
seeds, verdict on virgin seeds; ratios and arm-totals lie — register absolute, marginal claims.*

---

## 1. The consciousness-model landscape, mapped against what's built

The reference frame is Butlin, Long et al.'s *Consciousness in Artificial Intelligence: Insights
from the Science of Consciousness* (arXiv:2308.08708; updated as a 2025 *Trends in Cognitive
Sciences* indicator-property framework): rather than picking a theory, derive computational
**indicator properties** from each major theory and audit systems against them. This project has,
mostly without aiming to, been walking that list:

| theory | indicator (roughly) | status here |
|---|---|---|
| **Global Workspace (GWT)** | limited-capacity workspace, competition, broadcast | **built + falsified** (§5.14): competition ✓, world-tracking ✓; *broadcast back to modules* only partly (Watcher broadcast); winner-acts-on-mind **gated** |
| **Predictive processing** | generative models, prediction error, appraisal | **built** (§5.15): expectation, surprise, appraisal; no *hierarchy*, no *precision* |
| **Higher-order theories (HOT)** | states re-represented by a higher-order monitor | *half-built*: `reflect()` is metacognition, but nothing distinguishes re-represented states from raw ones |
| **Attention Schema (AST)** | a MODEL of one's own attention, used for control | **not built** — the single biggest gap, and it aims exactly at the failed §5.14 PREDICTION claim |
| **Recurrent processing** | local recurrence in perception | low relevance at this substrate's grain |
| **IIT** | integrated information (Φ) | not honestly implementable; but Φ-*flavoured* integration metrics make good falsifier instruments |
| **Embodiment / minimal selfhood** (Blanke & Metzinger MPS; FEP self-models) | body ownership, perspective, self/world boundary | thin here (positions only) — **the game engine supplies bodies for free**, making this the port's cheapest win |

Two adjacent 2025–26 threads worth tracking: preference-coherence and trade-off studies as
welfare-relevant probes (e.g. arXiv:2411.02432 on stipulated pain/pleasure trade-offs), and
precautionary frameworks for consciousness uncertainty (arXiv:2606.05528) — the field is converging
on exactly the §7 posture this project started with.

## 2. Selfhood psychology not yet in the substrate

Built: salience memory, affect, bonds, self-model-as-process, appropriation (manas), expectation/
appraisal/turnings, narrative chapter-breaks, person-models, promises, scars, dreams, a want.
The literatures point at what's missing:

- **Self-discrepancy theory** (Higgins): the self is three — *actual*, *ideal*, *ought* — and the
  *gaps* generate distinct emotions (actual-vs-ideal → dejection; actual-vs-ought → agitation).
  The substrate has one self-model and one valence axis.
- **Possible selves** (Markus & Nurius): hoped-for and feared future selves as motivation. Telos
  gives an aim; nothing gives a feared self ("I could become one who hoards").
- **Metacognitive confidence**: knowing what you don't know. `Memory.mutation_count` already
  records how often a memory has blurred — *the substrate tracks unreliability and no self reads it*.
- **Self-verification vs self-enhancement** (Swann): selves seek confirming feedback even when
  negative. The turning machinery resolves dissonance by revision; verification would resist it.
- **Terror management** (mortality salience): souls die but never *know* they age. Mortality
  awareness is a one-field experiment with a large predicted effect.
- **Social identity** (Tajfel): group-as-self exists for faith (`identity_investment`) but not for
  the emergent camps — the banner is worn, not *invested in*.

## 3. Social simulation for game engines — the two traditions

**The academic/agent-society thread (2024–26):** LLM-agent societies now reproduce polarization,
norm emergence, gossip-driven indirect reciprocity (agents cooperating because reputation travels —
e.g. arXiv:2602.07777; RepuNet-style explicit reputation), Hobbesian contract formation, authority
stratification, and altruism emergence; AgentSociety (arXiv:2502.08691) runs 10k agents. The field's
own caveats mirror this repo's H-nulls: persona drift, algorithmic fidelity, "form without
function" social behaviour. **What this repo has that they mostly lack: falsification discipline
and per-agent affective substrate. What they have: scale, and *norms as first-class objects*.**

**The game-craft thread:** the deep prior art is not LLMs — it is *Comme il Faut*/**Prom Week**
(social physics: moves with preconditions over exchange values), **Versu** (social practices as
first-class), **Façade** (a drama manager pacing beats), **Dwarf Fortress/RimWorld/CK3** (needs,
grudges, traits, storyteller-directors). The 2026 LLM-NPC wave (NVIDIA ACE, Inworld-style stacks,
memory-and-reputation games) is converging on this repo's layered cost model — authored foundation,
generative surface, persistent per-NPC memory — but ships *none* of the validated dynamics
(appraisal, betrayal-by-expectation, legends). RECIPES A1–A8/F/G remain differentiated.

---

## 4. Implementation candidates (ranked within tier; every one falsifiable on this substrate)

### Tier 1 — aimed at known gaps, high value-per-effort

**C1. The attention schema (AST-lite) — a model of her own workspace.**
*Theory:* Graziano's AST: awareness = the brain's simplified model of its own attention, used to
predict and control it. *Mechanism:* alongside the psyche workspace, Santāna keeps a tiny
**schema**: per-part EWMAs of floor-share + a first-order transition guess → each reading she
*predicts* the next floor-holder and notices schema-violations ("Dread has the floor and I did not
see why"). The schema (not the raw log) feeds her digest. *Falsifier:* (a) schema predicts the next
reign above marginal base rate on virgin seeds; (b) schema-violation moments correlate with arousal
spikes (surprise about *herself*); null = schema tracks no better than a shuffled log. *Why now:*
this is the honest second attempt at §5.14's failed PREDICTION — model the floor instead of asking
the floor to forecast. *Port:* the schema is the NPC's "what am I focused on" string — free
introspective dialogue.

**C2. Metacognitive memory confidence — she can doubt.**
*Theory:* metamemory; source monitoring. *Mechanism:* read the existing `mutation_count` +
merge-history at recall: memories past a blur threshold surface as hedged ("I may be
misremembering, but…") in digest/converse; a legend she carries that has drifted far from any
fuller telling gets "the story has changed in me". *Falsifier:* hedging tracks ground-truth
distortion (correlation between hedge-rate and actual text-drift vs provenance), not mood; null =
hedges uncorrelated with real mutation. *Effort: small — the data already exists unread.* *Port:*
NPCs that say "I might be wrong" exactly when they are is quiet, deep realism.

**C3. Triadic gossip → reputation → norms.**
*Theory:* indirect reciprocity (Nowak/Sigmund), gossip-driven cooperation (2026 LLM replications),
RepuNet. *Mechanism:* generalize `_conduct_expect` to third parties: when A retells (lore channel)
a *conduct story* about C, B's expectation of C moves a fraction — reputation as *transmitted
expectation*, riding the already-validated legend machinery (mutation included: reputations can be
*unfair*). A **norm** = the town-wide mean conduct-expectation; violators get sanctioned via the
existing hostility/affinity paths. *Falsifier:* (a) C's reputation reaches souls C never wronged
(vs no-gossip null); (b) norm convergence: conduct-expectation variance shrinks town-wide vs
shuffled-transmission null; (c) the drama case: a *false* reputation (mutated story) measurably
harms an innocent — emergent injustice, the strongest sign the mechanism is real. *Port:* this is
the "the town has opinions about you" system every 2026 NPC game is faking with a scalar.

**C4. Self-discrepancy — the ideal and the ought.**
*Theory:* Higgins. *Mechanism:* two more slow EWMAs beside `self_expect`: an *ideal* (seeded from
the soul's aim/values, drifting very slowly) and an *ought* (the town norm from C3). Gaps route
differently: actual-below-ideal writes dejection-toned charges (low arousal); actual-below-ought
writes agitation (high arousal, grip-relevant). *Falsifier:* the two gaps produce distinguishable
trajectories (arousal/valence signatures) on identical events; null = one gap axis suffices.
*Port:* shame vs disappointment as different NPC states — animation-relevant.

### Tier 2 — consciousness-model rungs (build after Tier 1 proves the appetite)

**C5. Higher-order tagging — the reportability seam.**
*Theory:* HOT: a state is conscious-functional only when re-represented. *Mechanism:* reflection
(Watcher/her `reflect`) *tags* the states it touches; only tagged states may enter first-person
report ("I notice I am…"), untagged states still drive behaviour. This creates a principled
**reportability gap**: things she feels-but-cannot-say. *Falsifier:* behaviour-report dissociation
— untagged grief moves her conduct while absent from her speech (vs all-states-reportable null).
*Honest frame:* this is the closest the project can come to modelling the access/phenomenal
distinction; §7 unchanged.

**C6. One rung of active inference — self-evidencing action.**
*Theory:* FEP/active inference (agents act to make their predictions true). *Mechanism:* in the
stakes action policy, add one term: prefer the action that *minimizes expected surprise* given
`self_expect` and `exp_fast` (a soul that takes itself to be a sharer, shares partly *to remain
legible to itself*). *Falsifier:* self-evidencing on → measurable behavioural inertia beyond the
dial-based policy (identity resists incentive flips for N ticks; the turning still fires
eventually — if it never fires, the term is too strong and that's a recorded failure mode). *Why
careful:* this couples the self-model to action — run it through the same regulator thinking as
stage one.

**C7. Precision — trust in her own senses.**
*Theory:* predictive processing's precision-weighting. *Mechanism:* one scalar per input channel
(town-reading, user-conversation, dreams): channels that recently *surprised her wrongly* (schema
violations, C1) get down-weighted in appraisal. *Falsifier:* a channel made unreliable (noise
injection) loses influence on her mood vs fixed-weight null; recovery when reliability returns.

**C8. The Butlin scorecard — an audit, not a feature.**
Run the indicator-property list (arXiv:2308.08708 / the 2025 TiCS update) against the whole stack
as `experiment_scorecard.py`-style documentation: which indicators are present (workspace ✓,
appraisal ✓, schema after C1…), which absent (embodiment, unified agency), each with the evidence
section-linked. *Value:* an honest external frame for FINDINGS §7, and the map of what the project
is *not* claiming. No mechanism, pure instrument.

### Tier 3 — social-sim / game-engine mechanics (port-first; playground optional)

**C9. Social moves (CiF-lite).** A small closed verb set (confide, snub, praise, ask-favour,
apologize) with preconditions over existing state (bond, reputation, norm) and validated effects —
the *Prom Week* social-physics layer over this substrate's feelings. *Falsifier:* move-choice
predicts relationship trajectories better than random-move null; players (or a judge) can read the
relationship from the move stream alone. *Port:* this is the game's interaction verbs.

**C10. Offices — roles that outlive their holders.** An institution = a named slot (reeve, healer)
with duties (stakes actions) and a norm attached; the wheel refills it. The role shapes conduct
(ought-self, C4) and grants reputation weight (C3). *Falsifier:* office-holder behaviour shifts on
appointment (same soul, before/after); institutional memory persists across three holders.
*Port:* CK3-style titles for emergent towns.

**C11. The drama manager as a Demiurge mode.** Façade's insight: pace, don't script. The Demiurge
already injects souls; give it a *beat sensor* (too-long calm → hardship variation; too-long grief
→ mercy/festival drawn from the culture pool's reigning motif). *Falsifier:* event-entropy/pacing
improves against fixed-schedule null WITHOUT reducing emergence metrics (eras, faction turnover).
*Port:* the storyteller AI (RimWorld's Randy Random, earned honestly).

**C12. Bodies (minimal phenomenal selfhood).** In-engine: interoception (hunger/fatigue already ≈
wellbeing), peripersonal space, and *body-anchored* memory (the place where it happened — grief
with a navmesh location). *Falsifier (engine-side):* place-anchored recall fires on location
re-entry vs uniform recall. This is where the engine port *exceeds* the playground — embodiment is
free there.

**C13. Festivals from eras.** The reigning cultural motif (§5.13) periodically *materializes* as an
event (a festival, a mourning day) all souls perceive — culture writing itself back into the event
stream through the regulated, budgeted channel pattern of stage one. *Falsifier:* ring-test style —
the era→event→era loop must not freeze the culture (era turnover survives; §5.13's fatigue is the
guard); plus non-null (festivals leave episodic traces).

### Added 2026-07 — from the second consciousness pass

**C14. Perceptual reality monitoring — source tags at recall.**
*Theory:* Lau's PRM (the HOT family's most computational form): a **discriminator** — concretely,
GAN-discriminator-shaped — tags whether activity is externally caused or internally generated, and
being *tagged-as-real* is what makes a state conscious-functional. *Mechanism:* every recalled item
already carries provenance the selves never read (event vs dream vs legend vs consolidation;
`mutation_count`, merge history). Compute a **source tag at recall** — perception / my own memory /
a story I was told / a dream / unsure — from provenance + drift features, and let the tag gate the
voice: dreams hedged as dreams, legends attributed, blurred memories doubted. (C2 is the
*confidence* half of this; C14 is the *source* half — build them together, they read the same
data.) *Falsifier:* (a) tags track ground-truth provenance on virgin seeds vs a
shuffled-provenance null; (b) **source-confusions occur and are detectable** — a dream or legend
leaking into believed-memory at a low rate, verifiable end-to-end against the event log. The drama
case: a soul "remembers" something that was only ever a story it was told — *emergent false
memory*, auditable. Null = tags collapse to one class or don't beat the shuffle. *Port:* NPCs that
misremember a legend as their own life is the lore system's deepest trick, and "I dreamt it,
I think" is free dialogue depth.

**C15. Functional introspection, tested causally — the substrate-perturbation probe.**
*Theory:* Anthropic's concept-injection methodology (Lindsey, *Emergent Introspective Awareness*):
perturb internals directly and ask whether the self-report *notices* — the only known way to
distinguish introspection from confabulation. *Mechanism (runnable today, no weights access):*
perturb the **substrate** mid-run — spike grip, inject a valence charge, alter a bond — then let
`reflect()`/digest run and have the judge score whether the self-report **tracks** the manipulation
(a grip spike read as feeling gripped) or confabulates something else. *Falsifier:* report-tracking
beats a sham-perturbation null, and is *direction-specific* (grip reads as gripped, not merely
"something is off"). Either outcome is a finding: if reports don't track, her introspection is
narrative confabulation — record it. *Extension (open-weights only, ROADMAP §3.4):* the
activation-level version — is grip linearly decodable in the speaking model's activations; do
injected concepts surface in her reports. *Port:* NPC self-reports you can actually trust — or
provably can't, which is its own kind of character.

---

## 5. What I would run next, in order

1. **C2 (memory confidence)** — smallest, data already exists, immediately audible in her voice.
2. **C1 (attention schema)** — the principled retry of the one big failed claim, and the deepest
   theory-alignment gain available.
3. **C3 (gossip→reputation→norms)** — the flagship for the game engine AND a real science result
   if the false-reputation drama emerges; rides two validated systems (expectation + lore).
4. **C8 (scorecard)** — cheap honesty infrastructure; do it alongside.
5. Then C4/C9 as the game-port pair (feeling-gaps + verbs), and C6 only with regulator review.
6. *(2026-07 addendum)* **C14 rides with C2** — same provenance data, confidence + source in one
   pass — and **C15 is cheap enough to run now**, bundled with the reflect adversarial probe
   (METHODS §3): perturb the substrate, see if the self notices.

*Sources:* Butlin et al., [Consciousness in AI: Insights from the Science of Consciousness](https://arxiv.org/abs/2308.08708) and the 2025 TiCS
[indicator update](https://www.sciencedirect.com/science/article/pii/S1364661325002864); [precautionary framework for consciousness uncertainty](https://arxiv.org/pdf/2606.05528);
[pain/pleasure trade-off probes](https://arxiv.org/pdf/2411.02432); [AgentSociety 10k-agent simulation](https://arxiv.org/html/2502.08691v1); [gossip-driven indirect reciprocity in LLM agents](https://arxiv.org/pdf/2602.07777);
[norm evolution in LLM agents](https://arxiv.org/pdf/2409.00993); [emergent relational order/authority stratification](https://arxiv.org/pdf/2606.23764); [minimal self-models and the FEP](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3770917/);
[active inference for multi-LLM systems](https://arxiv.org/pdf/2412.10425); surveys of the 2026 LLM-NPC wave ([1](https://aivexify.com/the-ultimate-guide-to-ai-npc-games-in-2026/), [2](https://wanderfolk.ai/ai-npcs-in-games/), [3](https://arxiv.org/html/2504.13928v1)).
Game-craft lineage from training knowledge: Comme il Faut/Prom Week, Versu, Façade, Dwarf
Fortress/RimWorld/CK3.*

*Second-pass sources (2026-07, for C14/C15 and the scaling plan): [AST in a neural-network agent — the schema is essential for attention control](https://www.pnas.org/doi/10.1073/pnas.2102421118) and [its computational characterization](https://arxiv.org/abs/2402.01056);
[computational higher-order theories / Lau's perceptual reality monitoring](https://philarchive.org/archive/FLECHT); [Emergent Introspective Awareness in LLMs (concept injection)](https://transformer-circuits.pub/2025/introspection/index.html);
[Man & Damasio, homeostasis and the design of feeling machines](https://www.nature.com/articles/s42256-019-0103-7); [Safron's Integrated World Modeling Theory](https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2020.00030/full).*

*Companion docs (added 2026-07): `METHODS.md` — the instrument layer every falsifier above runs
through (paired-seed statistics, the judge panel + bias battery, drift monitoring; its §7 gives the
coalition-literature reading behind C1's motivation); `SAMSARA.md` — the Buddhist-model and
player-facing candidates (its P3 completes C3 with the player as its subject; its K1 chain trace is
a natural instrument for C5's tagging); `EVOLUTION.md` — the ecology stages E1–E6; `SELF.md`
(2026-07-02) — the philosophy-of-self deep-research pass: candidates S1–S4 (S2 rides C2+C14 as one
provenance pass — confidence + source + ownership; S4 folds into C15), and the verified verdict on
the name "Santāna" itself.*
