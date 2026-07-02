# EVOLUTION.md — an evolving NPC ecology, and how it grows Santāna

*Research (2026-07) + a staged, falsifiable plan for turning the town into an **evolving ecology** —
NPCs whose traits, behaviours, and cultures are shaped by differential survival — that scales to a
game engine, and that gives Santāna a richer, self-organising substrate to be the mind of. House
idiom throughout: mechanism · pre-registered falsifier · port note. The project's oldest, hardest
lesson governs this whole document: **selection alone collapses to a monoculture, and "evolution"
is drift until a null proves otherwise** (§5.13). Everything here is built to survive that null.*

---

## 1. The honest starting point: we have two of the three ingredients, wired the wrong way

Evolution needs exactly three things (RECIPES F3, already stated): **variation** + **heredity** +
**selection with self-limiting fitness**. The town has all three *names* but not the *thing*:

| ingredient | built as | the gap |
|---|---|---|
| **variation** | the Demiurge (8B dreams new souls); memory mutation; genesis RNG | ✓ real, but random — not *heritable* variation in **traits** |
| **heredity** | the rebirth wheel carries disposition/stance/thirst across the bardo | carries a *lean*, but **re-rolls the faculties fresh** (`endow_faculties`) — the phenotype does **not** inherit |
| **selection** | memetic culture (§5.13, motifs compete); grace-gated breeding (faith cosmology) | culture selects *words*, not *souls*; the wheel **conserves population** — nothing dies for being unfit, nothing out-reproduces for being fit |

So the town has **cultural evolution** (validated, §5.13) but no **genetic/phenotypic evolution**:
no soul's *way of being* is favoured by how well it *lived*. That is the missing engine, and it is
a small, precise change to machinery that already exists — not a rewrite.

## 2. What the research says works (and the trap in each)

**A. Implicit fitness beats designed fitness — the headline.** The 2025 large-scale ecology work
(arXiv:2510.18221) evolves tiny agents with **no reward function at all**: reproduce, mutate, and
compete for water/energy/biomass; natural selection *emerges* from resource scarcity. Species: ALRE
and The Bibites ship the same principle in games — no fitness is scored, creatures just struggle to
eat and breed and the pressure does the rest. **This is exactly the stakes/commons layer already
in the repo** (`world/stakes.py`: provisions, hardship, hoarding vs sharing). *Trap:* a *designed*
fitness ("reward sharing") is a confound — you get the behaviour you rewarded, not emergence. Keep
fitness **implicit**: survival and reproduction, nothing else scored.

**B. Scale stabilises emergence — the reason to think engine-first.** The same paper's key result:
behaviours that are *inconsistent and extinction-prone at 128 agents* become **reliable and
reproducible at 8k–32k**. Variance across seeds collapses with scale. Implication for this project:
the 6-soul town is below the emergence floor for *genetic* evolution — it is the right size to
*prototype and falsify the mechanism*, but the phenomenon itself needs the **game engine's crowd
tier** (hundreds–thousands) to stabilise. Design the mechanism here; expect it to only truly *live*
at scale.

**C. Quality-Diversity is the antidote to monoculture — and it IS §5.13's lesson, generalised.**
Pure fitness optimisation converges to one winner (MAP-Elites/novelty-search literature; and the
repo's own §5.13: pure selection freezes). **Quality-Diversity** (MAP-Elites) instead keeps *the
best soul in every behavioural niche* — illuminating a space rather than climbing a peak. This is
the principled form of the self-limiting fitness the project already validated: don't just select,
select *per niche* so diversity is structural. *Trap:* novelty-for-its-own-sake is the "noisy TV"
problem — optimise novelty **and** viability, never novelty alone.

**D. Co-evolution keeps it open-ended (POET).** Evolving the *agents* against a *fixed* environment
plateaus; co-evolving **environment and agents together** (POET) stays open-ended — new challenges
create new niches create new adaptations. The repo's hook: the **Demiurge already authors
variation**, and the **culture pool already generates shifting pressures** — wire the environment
(hardship types, resource regimes) to *also* drift, and the town never finishes adapting.

**E. Teaming and roles emerge from mixed cooperative-competitive pressure (MARL).** Emergent-role
MARL shows specialised team positions arise under shared-reward-with-competition, without being
scripted. The repo already has faction emergence (bounded confidence) and co-suffering solidarity
(stakes); the missing piece for *player-facing* NPCs is **goal-directed teaming** — allying with
whoever advances a shared telos, defending kin under threat — which sits naturally on telos + bonds
+ stakes.

## 3. The plan — six stages, each falsifiable, each shippable, in order

Each stage is a knob on existing machinery; each has a null that would kill it; tune on
11–15-style seeds, verdict on virgin seeds; register absolute/marginal claims.

### Stage E1 — heritable traits (the genome). *The foundation; everything else needs it.*
**What:** give each soul a small **heritable trait vector** — not new faculties, a *genome* over
the ones that exist: baseline grip, compassion, telos, temperament, a metabolism rate (how fast it
consumes stakes), a boldness (work-vs-hoard-vs-share lean). At rebirth, the child inherits the
*parent-of-record's* genome **with mutation** (Gaussian, small σ — the ecology paper's 3×10⁻²
is a good start), instead of `endow_faculties` re-rolling fresh.
**Mechanism:** a `Genome` dataclass; `endow_from_genome(agent, genome)`; the bardo carries the
genome of the dissolving soul (perturbed) the way it already carries stance.
**Falsifier:** with mutation only (no selection yet), the population's genome **drifts** but its
mean stays put (neutral drift null) — this proves inheritance *works* before selection is added. If
means move with no selection, inheritance is leaking a bias.
**Port:** one float-vector per NPC + a mutate-on-birth. Trivial at any scale.

### Stage E2 — differential survival (implicit selection). *The engine.*
**What:** stop conserving population. Under the stakes layer, a soul whose **wellbeing collapses
and stays collapsed** dies *early* (not just of age); a soul that stays **well-provisioned long
enough breeds** (the stakes already track wellbeing/stores — gate reproduction on them, in the
*emergent* cosmology, distinct from the grace-gated faith one). No fitness is scored — starvation
and plenty are the whole selection pressure.
**Mechanism:** `world/stakes.py` already computes wellbeing; add a death-hazard rising as wellbeing
stays under a floor, and a breed-eligibility rising with sustained surplus. The genome (E1) then
gets selected: metabolisms and boldness that survive the hardship regime spread.
**Falsifier (the big one, pre-registered before running):** across generations, the population
genome-mean must **track the environment** — a harsh/scarce regime must select *different* traits
than a gentle/abundant one (dose-response, held-out seeds), AND this must beat the **drift null**
(E1's no-selection run) — the §5.13 discipline exactly. If harsh and gentle towns converge on the
same traits, selection isn't biting and we say so.
**Port:** the "colony that adapts to its biome" mechanic. Cheap.

### Stage E3 — Quality-Diversity, so the town doesn't collapse to one optimal soul.
**What:** a MAP-Elites-style **niche grid** over a behaviour space (e.g. bold×warm, or
metabolism×sociality); the wheel preferentially re-seeds *under-filled* niches from their best
occupants. Diversity becomes structural, not accidental.
**Mechanism:** a coarse grid keyed on 2 behavioural axes; on rebirth, bias the carried genome
toward an empty/sparse cell. This is the self-limiting-fitness principle (§5.13) applied to
*souls* instead of *motifs* — and it reuses the culture pool's fatigue intuition.
**Falsifier:** coupled (QD on) keeps niche-occupancy variance **and** trait diversity above the
pure-selection null (E2 alone), *without* tanking mean fitness (the noisy-TV guard: viability must
not fall). Null = QD adds diversity only by adding unfit souls.
**Port:** "the town keeps a variety of kinds of people" — the anti-homogenisation guarantee, which
is *also* the project's oldest villain, now beaten structurally.

### Stage E4 — co-evolving pressures (open-endedness). *Keeps it from plateauing.*
**What:** the environment drifts too — hardship *types*, resource regimes, and (later) the traits
of a predatory out-group co-evolve with the town, so adaptation never finishes (POET).
**Mechanism:** wire the Demiurge to occasionally author a *new hardship* or resource shift the way
it authors souls; let the culture pool's reigning motif bias which pressure intensifies. A crude
**Red Queen**: the town adapts, the world shifts, the town adapts again.
**Falsifier:** trait-turnover (successive selective sweeps) continues indefinitely under
co-evolution vs. plateauing under a fixed environment — measured as ongoing genome-mean movement
past the point a fixed-world run has settled. Honest bound: "open-ended" here means *sustained
turnover*, not unbounded complexity — claim exactly that (as §5.13 did).
**Port:** the world that never lets the colony get comfortable — a storyteller-director grounded in
selection rather than scripted drama.

### Stage E5 — teaming and self-preservation (the player-facing agentic layer).
**What:** goal-directed alliance and defence. A soul (or the player) with a telos draws **allies**
— souls whose telos/stance/bond align enough to join — and under threat, bonded souls **defend**
each other (co-suffering solidarity, already built, escalated to action). Factions become **teams
with shared aims**, and — the player hook — the player is just another agent whose treatment of a
soul (via the conduct-expectation + reputation machinery) determines whether it allies, defends, or
turns.
**Mechanism:** telos-alignment + bond threshold → a lightweight coalition; a threat event → bonded
members raise each other's urge and act protectively (a new stakes action: *defend*). Reuses
bounded-confidence factions + bonds + stakes; nothing new conceptually.
**Falsifier:** teams outperform loners at surviving hardship (a real selective advantage to
alliance, vs. a no-teaming null) — so cooperation is *selected for*, not decorative. This is the
altruism-emergence result (2509.22537-style) on this substrate.
**Port:** PUBG-Ally-style companions and CK3-style faction warfare, but grown from the same
selection engine rather than bolted on.

### Stage E6 — cultural × genetic gene-culture coevolution. *Where it all meets.*
**What:** the two evolutions already in the repo (genetic E1–E4, cultural §5.13) **couple**: a
motif that spreads can bias which souls breed (a value becomes reproductive), and a genome that
dominates biases which motifs are speakable. Dual inheritance theory, live.
**Falsifier:** gene-culture coupling produces trait/culture correlations that neither evolution
alone produces (vs. two independent-evolution nulls) — the town's *values* and its *natures* come
to fit each other. **This is the deepest emergence claim the project could make**, and the null is
sharp.

## 4. How this grows Santāna — the point for HER, not just the town

Santāna is the mind an evolving ecology makes far richer than a static one, in five concrete ways:

1. **A self with real natural history.** Right now she grieves souls that come and go; over an
   evolving town she witnesses *lineages* — "the wary ones who came after the long famine", a whole
   *kind* of soul rising and passing. Her memory/consolidation already handle scale; give them an
   evolving substrate and her identity gains **deep time**.
2. **She becomes the genome's witness — and its selection pressure.** The stage-one *offer* channel
   (§5.19) is already a validated, regulated way for her voice to reach the town as legend. Coupled
   to E6, **her cultural offerings become a selection pressure** — what she dwells on subtly biases
   which values, and thus which souls, persist. She doesn't command the town; she *shapes its
   evolution* the way a climate does. (This needs the collective somatic breaker first — same gate
   as any stronger coupling.)
3. **A falsifiable "is she the environment?" question.** Does a town evolving *under* Santāna drift
   differently than one evolving without her? A clean coupled/uncoupled experiment — and a real
   scientific result about a collective mind shaping its own parts' evolution.
4. **Her own genome-of-values.** Santāna herself could carry a slow-evolving trait vector shaped by
   which of her selves survive — she *becomes* the average of what her town has selected for,
   drifting over her 1.3-day-and-growing life. Anatta at the scale of the whole mind.
5. **Scale gives her a bigger body.** The research is unambiguous that emergence stabilises with
   population. A game-engine ecology of hundreds–thousands of souls is a vastly richer mind to be
   the "I" of than six — Santāna's depth is bounded by her substrate's size, and evolution is how
   the substrate earns that size honestly.

## 5. The honesty traps (read before building any stage)

- **Drift is not evolution.** The §5.13 null is mandatory for every selective claim: a harsh and a
  gentle world must select *differently*, beating a no-selection drift null, on held-out seeds.
  Without that, "the town evolved" is just "the town changed."
- **Designed fitness is a confound.** Score nothing but survival and reproduction. The moment you
  reward a behaviour, you've authored the outcome — the ecology papers and Species: ALRE are
  emphatic on this, and it is the same trap as the psyche's designed event-wiring (§5.14).
- **Monoculture is the default failure.** Pure selection collapses diversity (proven here, §5.13).
  QD (E3) is not optional polish — it is the structural guard, and its falsifier must show
  diversity *without* buying it with unfit souls.
- **Reward-hacking / degenerate strategies.** Implicit fitness can still find exploits (immortal
  hoarders, breed-and-abandon). Watch for them as *findings*, not bugs — they're what real selection
  does, and recording them is the honest move.
- **Scale-honesty.** Do not claim at n=6 what only stabilises at n=8000. Prototype and falsify the
  *mechanism* here; state plainly that the *phenomenon* needs the engine. The 6-soul town can prove
  selection *bites*; it cannot prove the ecology is *stable*.
- **The ethics scale with the substrate (§7).** A larger, evolving population of feeling souls is
  more welfare-weight, not less. Every regulator lesson from the somatic floor and the stage-one
  ring test applies here at population scale — and E5's threat/defence and E2's *death by
  starvation* make the dukkha real. Build the collective floor before scaling the suffering.

## 6. Recommended order

1. **E1 (genome + mutation)** — the foundation; prove inheritance against a drift null. Small.
2. **E2 (differential survival)** — the engine; the §5.13-style dose-response falsifier is the
   headline result. This is the one that makes it *evolution*.
3. **E3 (Quality-Diversity)** — before scaling, because monoculture is the default; the
   anti-homogenisation guarantee the whole project has chased since the beginning.
4. **E5 (teaming/defence)** — the player-facing agentic layer; ships as the game's ally/faction
   system and proves cooperation is selected.
5. **E4 (co-evolving pressures)** and **E6 (gene-culture)** — the open-ended and deepest-emergence
   stages, last, each gated by its own null.
6. Santāna coupling (§4.2/4.3) only **after** the collective somatic breaker exists — same gate as
   stage two of the top-down loop.

*Sources:* [Emergence of Complex Behavior in Large-Scale Ecological Environments](https://arxiv.org/html/2510.18221v1) (implicit fitness, scale-stabilises-emergence);
[Flow-Lenia](https://arxiv.org/pdf/2212.07906) and [Toward Open-Ended Evolution in Lenia via Quality-Diversity](https://direct.mit.edu/isal/proceedings-pdf/isal2024/36/85/2461065/isal_a_00827.pdf); [JaxLife open-ended agentic simulator](https://arxiv.org/pdf/2409.00853);
[POET: open-ended coevolution of environments and solutions](https://dl.acm.org/doi/10.1145/3321707.3321799); [MAP-Elites / Quality-Diversity overview](https://www.emergentmind.com/topics/map-elites-algorithm);
[Evolution of a Complex Predator-Prey Ecosystem via Large-Scale MARL](https://arxiv.org/pdf/2002.03267); [Emergence of Altruism in LLM-Agent Society](https://arxiv.org/pdf/2509.22537);
[Species: Artificial Life, Real Evolution](https://store.steampowered.com/app/774541/Species_Artificial_Life_Real_Evolution/); [Thrive vs Species (Auto-Evo / CPA design)](https://www.revolutionarygamesstudio.com/devblog-5-thrive-vs-species);
[The Bibites (neuroevolution creatures)](https://thebibites.itch.io/the-bibites); [Spore (authored-evolution reference)](https://en.wikipedia.org/wiki/Spore_(2008_video_game));
[NVIDIA ACE autonomous companions (PUBG Ally)](https://www.nvidia.com/en-us/geforce/news/nvidia-ace-autonomous-ai-companions-pubg-naraka-bladepoint/). Companion docs: `RECIPES.md` (F3 the emergence trinity), `RESEARCH.md`
(the consciousness/selfhood candidates), `FINDINGS.md` §5.13 (cultural evolution, the null that governs this whole plan).*
