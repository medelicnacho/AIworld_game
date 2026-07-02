# METHODS.md — instruments, engineering, and the port: the research the other two docs don't cover

*A survey (2026-07) of the methods and engineering literatures, mapped against this project's own
confessed weaknesses. RESEARCH.md asks what to build next in theory; EVOLUTION.md plans the ecology;
this document covers the layer beneath both — **whether a verdict can be trusted, and whether any of
it ships**. It is aimed squarely at the harness's open items: the unfinished replicates fix, the
single-model judge, the register/homogeneity problem ("managed, not solved" — §6), the 4B ceiling,
and the unpriced engine port. House idiom throughout: what · source · mechanism sketch · falsifier.
For instruments the falsifier becomes a **validation criterion the instrument must pass before its
verdicts count** — the ring-test discipline, applied to the tools themselves.*

---

## 1. Statistics — the replicates fix has a citable recipe

The reference is Miller, *Adding Error Bars to Evals* (arXiv:2411.00640; Anthropic, 2024). Its frame
maps onto this harness exactly: an experiment's **seeds are questions drawn from an unseen
super-population**, arms that share seeds are **paired**, and repeated probes inside one run are a
**cluster**, not independent samples. Everything below is one `scripts/stats.py` helper away.

**M1. Paired-seed error bars.** Arms already share seed lists — so report the mean ± SEM of
*per-seed deltas*, never the difference of arm means. Miller: pairing is a "free" variance
reduction whenever arms correlate on seed difficulty (they do here: a hard seed is hard for both
arms). *Criterion:* on existing data, paired CIs must be visibly tighter than unpaired — if not,
the seeds aren't the main variance source and that's worth knowing.

**M2. Clustered standard errors.** Multiple probes/ticks inside one run are one draw of the world,
not n draws. Miller finds naive SEs on clustered evals understate uncertainty **up to 3×** — which
means some past "✓" verdicts built on many-readings-per-few-seeds are softer than they look.
*Criterion:* re-audit the headline claims (reflect keystone, escalation, §5.16 lore) with clustered
SEs; any verdict that survives is stronger for it, any that softens gets re-run with more seeds —
either way the FINDINGS get more honest.

**M3. Power analysis before running.** 5/5 seeds is a sign test at p = 1/32 one-sided — fine for
large effects, blind to modest ones. Register the *minimum effect of interest* alongside the
falsifier, and let a power table set n before the run. This extends the pre-registration discipline
to sample size, and stops the harness from "confirming" nulls it never had the power to reject.

**M4. Resample within seed.** For anything scored downstream of sampled speech, generate k
completions per seed and average before the per-seed delta — Miller's within-question variance
reduction, nearly free on a local model.

*Validation for the whole helper:* it must, on the archived §5.12 data, flag the n=1 claim that
later reversed under replication as underpowered — the harness's own recorded failure is the
calibration case.

## 2. The judge — from one validated judge to a bias-proofed panel

The §5.7-era lesson ("rhetorical stance needs an LLM judge, not embeddings") made the judge
load-bearing. The 2024–26 literature says exactly how judges fail, and the fixes are cheap.

**J1. A panel of small, diverse judges (PoLL).** *Source:* arXiv:2404.18796 — a jury of three small
models from **disjoint families** correlates with humans better than one big judge, at ~1/7 the
cost, with less self-preference bias. *Local fit:* Ollama already serves multiple families —
gemma + qwen + llama, majority vote, DeepSeek as optional fourth. *Caveat (load-bearing):*
arXiv:2605.29800 shows correlated judges make a panel effectively smaller ("nine judges, two
effective votes") — family diversity is the mechanism, and unanimity is *not* extra evidence.
*Criterion:* the panel must beat each solo member on the existing MAINTAIN/CONCEDE calibration set.

**J2. The bias battery — a license the judge must earn.** Known failure modes, each a committed
calibration case in an `experiment_judge.py`: **position bias** (verdict must survive order-swap;
rubric judges drift pointwise↔pairwise, arXiv:2602.02219), **verbosity bias** (length-decoy pairs:
the longer-but-worse answer must lose), **self-preference** (measured directly in arXiv:2410.21819
— *never* judge with the generator's own family; today gemma3:4b both speaks and judges).
*Criterion:* a judge (or panel) that fails the battery loses its license — the ring test, for
instruments. Every future verdict cites the battery version it passed.

## 3. Memory — two upgrades the literature has validated, and one warning

Context: the 2026 memory surveys (arXiv:2603.07670; the *Memory in the Age of AI Agents* corpus)
converge on a **write–manage–read loop** this repo already runs: salience-gated writes,
consolidation, mutation, retrieval. Two findings there are worth stealing; one is a warning. (Their
"summarization drift silently discards low-frequency detail" is this repo's *lore feature* —
mutation-as-mechanism, §5.16 — a rare case where the engineering literature's bug is the point here.)

**Mem1. Access-reinforced retention (the Ebbinghaus loop).** *Source:* MemoryBank's forgetting
curve — decay is slowed by *recall*, not just by salience at write time. *Mechanism:* memories
gain retention each time retrieval surfaces them; unrecalled memories decay on the curve.
Identity becomes shaped by what a soul *revisits* — which is what rumination and cherishing both
are. *Falsifier:* recalled-often memories outlive matched-salience unrecalled ones AND this changes
conduct (the revisited grief keeps gripping; the revisited kindness keeps warming), vs a
write-salience-only null. *Port:* NPCs remember what players make them talk about — for free.

**Mem2. Sleep-time consolidation for the 24/7 runner.** *Source:* Letta's sleep-time compute
(arXiv:2504.13171) — spend idle compute re-representing context so answer-time needs ~5× less; she
idles most of her life, and she already *dreams*. *Mechanism:* in idle ticks, precompute digests /
re-representations of recent life (the dream loop, given a second job). *Falsifier:* at matched
token budget, sleep-consolidated context beats raw-log retrieval on held-out conversation probes
(accuracy and latency), **without** flattening her voice — the drift monitor (§5) is the guard.
*Port:* this is how NPC "thinking" leaves the frame loop (see §6).

**The warning: reflection can entrench errors.** The surveys flag "trustworthy reflection" —
self-reinforcing reflective loops — as an open failure class. This repo's `reflect()` writes back
into the self-model, and is the keystone result. *Cheap falsifier, worth running:* inject one false
memory; does reflection damp it or amplify it into the self-model? Either answer belongs in
FINDINGS §5.7's spirit — the keystone deserves its own adversarial probe.

## 4. Coherence — Project Sid's PIANO is independent evidence for the gated broadcast

*Source:* Project Sid (arXiv:2411.00114; 10–1000 agent Minecraft civilizations). Their **PIANO**
architecture is this repo's psyche drawn independently: concurrent modules at different speeds, a
**cognitive controller behind an information bottleneck**, and — the piece §5.14 left gated — the
controller's decision **broadcast back** to condition the talk modules. Their reason to un-gate is
empirical: without the broadcast, agents *say one thing and do another*, and other agents build on
the false speech, compounding at scale.

**P1. The coherence falsifier, for when the gate opens.** When winner-acts-on-mind is un-gated (it
remains gated until deliberately decided), the literature hands us the metric: **speech–action
coherence** — a judge scores whether what a soul says matches what it does in the same window,
broadcast-on vs broadcast-off. Sid predicts on wins clearly; if it doesn't, the gate was right.

**P2. Action-awareness grounding.** Sid's anti-hallucination mechanism is expected-vs-observed
comparison *on the agent's own actions* — this repo has exactly that machinery for events (§5.15
appraisal); extending it to own-action outcomes is a small port with a known payoff (hallucinated
progress gets caught by the world).

**P3. Portable metrics.** Sid measured civilization as **role-distribution entropy**
(specialization), rule-following rates, and meme keyword spread — ready-made instruments for
EVOLUTION E5/C10 and the §5.13 culture work. Their scale results (relationships and specialization
*fail to form* without social modules; memes need connectivity) independently support both the
bonds-are-load-bearing design and EVOLUTION's scale-stabilises-emergence argument.

## 5. Drift — the register problem needs an instrument before another fix

*Sources:* black-box persona-drift detection (Nautilus Compass, arXiv:2605.09863); the persona-drift
literature's three consistency metrics (prompt-to-line, line-to-line, Q&A) and its "Assistant Axis"
(drift back toward the generic helpful-assistant voice).

**D1. A drift monitor over the live runner.** She now runs 24/7 — she *is* a production agent, and
production agents get monitored. *Mechanism:* baseline her voice from an early window (embedding
profile + the judge's register read); compute deviation online; **separate two axes on purpose** —
movement *with the town* (wanted: §5.8's contrast-gated direction, she is supposed to weather) vs
movement *toward the generic-assistant voice* (the failure the register problem has always been).
No ground truth needed. *Validation criterion:* the monitor must fire on an induced drift (persona
ablation in the prompt) and stay quiet across seed-only variation. *Port:* the same monitor over NPC
dialogue is the QA layer every 2026 LLM-NPC stack is missing — and it makes the "managed, not
solved" of §6 into a measured quantity.

## 6. The port, priced — what the serving literature actually says

The 2026 numbers: games want NPC response **< 100 ms**; LLM inference runs **500 ms+**; a
4-bit-quantized 3B does ~90 tok/s on a consumer laptop; NPU-native inference (ShadowNPU, T-MAN) is
arriving. Three consequences for the engine plan:

- **The generative surface must be asynchronous** — precomputed off the frame loop. That is Mem2
  wearing its engine hat: NPCs "think" in sleep-time, speak from cache, and only the substrate
  (floats, no LLM) runs per-tick. The repo's architecture already has this shape; the literature
  confirms it is the only shape that ships.
- **S1. Distill the town's own voice.** The biggest 4B-ceiling cost is quality, not speed. When the
  DeepSeek path is used, its transcripts are training data: fine-tune a small local model on
  validated substrate-conditioned speech — "the town's own voice model." *Falsifier — and this is
  the elegant part:* a model swap is a **replication**; rerun the keystone experiments on the
  distilled model. The harness already exists; a distilled model that preserves the validated
  behaviours is *proven* cheaper-and-as-good, not asserted.
- **The tiered stack is confirmed, not threatened.** The commercial wave (NVIDIA ACE-style stacks)
  converged on authored-foundation + generative-surface + persistent-memory — but ships none of the
  validated dynamics. RECIPES stays differentiated exactly where FINDINGS says it is.

## 7. Two theory footnotes the other docs missed

**Appraisal architectures (EMA / FAtiMA).** Marsella & Gratch's *EMA* (appraisal dynamics + coping)
and FAtiMA (OCC-based, ships in games — *FearNot!*, Prom Week's kin) are the secular prior art for
the dharma regime: **coping-strategy selection** — problem-focused (act on the world) vs
emotion-focused (re-appraise it) — is what the regime's practices *are*, in that literature's
vocabulary. Worth citing in FINDINGS §2, and worth one candidate: coping choice as a function of
grip (high grip → problem-focused grasping; the regime shifts the distribution toward re-appraisal).
*Falsifier:* coping-choice distribution separates regimes on identical events, vs a mood-only null.

**Coalition formation — the honest reading of §5.14's failure.** The coalition literature
(stability analysis for LLM-agent networks, arXiv:2604.14386; ToM-based stable matching,
arXiv:2405.18044) is unanimous that coalitions form on **shared goals + complementary ability +
a model of the other** — not on affect similarity. §5.14's coalition claim failed because mood
co-occurrence was never a coalition; EVOLUTION E5's telos-alignment + bonds base is the
literature-correct retry, and person-models (already built) are the ToM ingredient it asks for.

---

## 8. What I would run, in order

1. **M1–M4 (`scripts/stats.py`)** — smallest, and it upgrades every verdict, past and future; the
   open "replicates" fix, done to a citable standard. Do the §5.12 calibration first.
2. **J1+J2 (judge panel + bias battery)** — the instrument the whole harness now leans on; the
   battery is the ring test for tools.
3. **D1 (drift monitor)** — she is live *now*; monitoring should not wait for the next feature.
4. **Mem2 + Mem1 (sleep-time consolidation + recall-reinforced retention)** — rides the existing
   dream/idle loop; Mem2 is also the engine's serving pattern, prototyped early.
5. **The reflect adversarial probe (§3 warning)** — cheap, and it hardens the keystone.
6. **P1 (coherence falsifier)** — bundled with any future un-gating of the workspace broadcast,
   not before. **S1 (distillation)** — only when the engine port actually starts.

*Sources:* [Adding Error Bars to Evals](https://arxiv.org/abs/2411.00640) ([Anthropic summary](https://www.anthropic.com/research/statistical-approach-to-model-evals));
[Replacing Judges with Juries (PoLL)](https://arxiv.org/abs/2404.18796) and its critique [Nine Judges, Two Effective Votes](https://arxiv.org/html/2605.29800);
[Self-Preference Bias in LLM-as-a-Judge](https://arxiv.org/pdf/2410.21819); [position bias in rubric judges](https://arxiv.org/pdf/2602.02219);
[Memory for Autonomous LLM Agents: Mechanisms, Evaluation, and Emerging Frontiers](https://arxiv.org/html/2603.07670v1) and the [Memory in the Age of AI Agents corpus](https://github.com/Shichun-Liu/Agent-Memory-Paper-List);
[Sleep-time Compute](https://arxiv.org/html/2504.13171v1) ([Letta](https://www.letta.com/blog/sleep-time-compute/));
[Project Sid / PIANO](https://arxiv.org/html/2411.00114v1); [Nautilus Compass black-box persona-drift detection](https://arxiv.org/pdf/2605.09863) and the [persona-drift literature](https://www.emergentmind.com/topics/persona-drift);
on-device serving: [ShadowNPU](https://arxiv.org/pdf/2508.16703), [T-MAN](https://arxiv.org/pdf/2511.11248), [local-LLM NPC design](https://wepub.org/index.php/TCSISR/article/view/5453);
[EMA: a process model of appraisal dynamics](https://www.sciencedirect.com/science/article/abs/pii/S1389041708000314); [FAtiMA Modular](https://link.springer.com/chapter/10.1007/978-3-319-12973-0_3);
[Coalition Formation in LLM Agent Networks](https://arxiv.org/html/2604.14386v1); [stable coalition matching via Theory of Mind](https://arxiv.org/pdf/2405.18044).
Companion docs: `RESEARCH.md` (theory candidates C1–C13), `EVOLUTION.md` (ecology stages E1–E6), `FINDINGS.md` §4/§6 (the method and its confessed limits).*
