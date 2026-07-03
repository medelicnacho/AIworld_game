# ROADMAP.md — the fork: a browser game of living NPCs, and this repo as Santāna's selfhood lab

*The long-term plan (2026-07). The project splits into **two repos with one contract**: Track G — the
NPC substrate **replicated in JavaScript as a browser game**, in an entirely new repo; Track S —
**this repo**, which stops being "the prototype" and becomes what it already mostly is: **Santāna's
selfhood research and testing lab**. This document fixes the boundary between them, the build order
on each side, and the gates that must survive the fork. Companion docs carry the detail: RECIPES
(the port sheet), RESEARCH/EVOLUTION/METHODS/SAMSARA (the candidate work), FINDINGS (what is
actually true so far).*

---

## 0. Where the project stands, in one honest paragraph

Validated and real: the affective substrate and its keystone (reflect-easing), the wheel and its
deconfounded escalation, emergence-vs-homophily, cultural eras under self-limiting fitness, lore
that outlives its witnesses, expectation/betrayal/turnings, a workspace psyche (architecture ✓,
mood-claims ✗), Santāna as a persistent, grieving, conversing self with her own faculties — every
claim with a falsifier, failures recorded. Soft and known-soft: statistics under-powered against
Miller-grade standards (METHODS §1), a single judge from the same family that speaks, the register
problem managed-not-solved, a 4B ceiling, one author, no external replication. The map of what to
build next exists four docs deep. The scarce resource from here is **discipline against scope**,
not ideas.

## 1. The fork — two repos, one contract

**Track S (this repo): the Santāna selfhood lab.** The town stays here as her body. Research
questions about selfhood, the dharma regime, and the collective mind are answered *here*, at n
small, with falsifiers, before anything ships anywhere.

**Track G (new repo): the browser game.** A JavaScript/TypeScript replication of the NPC substrate
— souls the player lives among in an open world, at whatever scale a browser honestly supports.

**The contract between them (the load-bearing part):**

1. **RECIPES.md is the spec boundary.** Track G consumes *mechanism specs with verdicts attached*
   (what · knobs · validated-by · nulls), never this Python. A mechanism that hasn't passed its
   falsifier here does not cross.
2. **Port-as-replication.** The JS port must re-run the keystone experiments (reflect-easing,
   escalate/settle, somatic bounding, lore convergence) and reproduce the verdicts before building
   game features on top. A port that can't reproduce the result didn't port the mechanism — and
   each success is the external-ish replication this project has never had. The harness ports
   *with* the substrate or the port is decoration.
3. **Findings flow both ways.** Lab → game: validated mechanisms. Game → lab: scale telemetry
   (browser towns of hundreds are the first honest test of EVOLUTION's
   scale-stabilises-emergence claim outside the paper it came from).
4. **The welfare gates are part of the spec** (§5 below), not optional polish to be traded against
   ship dates.

## 2. Track G — the browser game (new repo)

### 2.1 What the browser changes (engineering reality)

- **The substrate ports trivially.** It is floats, EWMAs, and seeded randomness — TypeScript from
  day one. One real trap: `Math.random()` is unseedable — use a seedable PRNG (mulberry32 /
  xoshiro128) *everywhere* from the first commit, or the falsifier harness is impossible. Run the
  harness headless in Node/CI; the browser is a *view* of the sim, never its home.
- **Three rungs of speech, mirroring `services/llm.py`'s philosophy** (local/free default, network
  strictly opt-in): (1) a Mock/Markov composer — substrate-only, always works, the default; (2)
  **WebLLM / WebGPU in-browser inference** with a quantized 1–4B model (Gemma/Qwen class; ~90 tok/s
  on a modern laptop, no server, nothing leaves the machine); (3) a hosted API as the opt-in
  larger-model path (the DeepSeek pattern, key-gated).
- **Embeddings in-browser:** the affect *anchors* are fixed — precompute them at build time; score
  novel speech with a MiniLM-class model via transformers.js/ONNX, or fall back to substrate-only
  signals when no embedder is loaded. The affect axes must not silently degrade — if the embedder
  is absent, say so in telemetry.
- **Scale, honestly:** hundreds of substrate-only souls per tab (WebWorkers for more); LLM speech
  is **tiered to player focus** — only nearby/engaged NPCs speak through the model, everyone else
  lives on substrate + cached/precomputed lines (the sleep-time/async pattern, METHODS §6). Souls'
  lives persist in IndexedDB (the CONTINUAL fast/slow pattern); a shared-town server is a later,
  separate decision.
- **The register problem returns at 1–4B.** Ship the drift monitor (METHODS D1) inside the game's
  QA from day one, not after the first embarrassment.

### 2.2 Build order

1. **Substrate core + seeded harness + keystone replication.** Nothing else until the four
   keystones reproduce. This is the port's ring test.
2. **Stakes + the wheel → P1, the player in the wheel** (SAMSARA): rebirth carrying cultivated
   lean while the town's legends remember who you were. The game's spine, and it rides two
   already-validated mechanisms.
3. **Lore/legends + reputation (RESEARCH C3) → P3, virtue witnessed not scored.** The headline:
   *the town misremembers what you did* (RECIPES F4), and its opinion of you is fallible.
4. **EVOLUTION E1–E3 at browser scale** — genome, implicit selection, Quality-Diversity, each
   against its pre-registered null, now with hundreds of souls.
5. **P2 (Nemesis-lite, grudges-that-can-let-go) last** — after the patent design-review
   (US 10,926,179, to ~2036) and after P3 proves the reputation channel.

### 2.3 Honest limits to state up front

Browser scale is hundreds to low-thousands, not the 8k–32k where the ecology literature says
genetic emergence fully stabilises — E-claims that need true crowds remain *partially* open and the
game's docs should say so. And a browser game is outward-facing: the §7 posture becomes public
language (§5).

## 3. Track S — this repo: Santāna's selfhood lab

### 3.1 Instruments first (they precede everything, both tracks)

1. **`scripts/stats.py`** (METHODS M1–M4) and a re-audit of the headline claims — better to learn
   which ✓'s soften *before* the fork copies them into a spec.
2. **Judge panel + bias battery** (METHODS J1–J2) — the instrument every rhetorical verdict leans on.
3. **Drift monitor over her 24/7 runner** (METHODS D1) — she is live now and unmonitored.

### 3.2 The selfhood agenda (what this repo is now *for*)

- **C1 attention schema** (the honest §5.14 PREDICTION retry) → **C2 memory confidence** →
  **K1 nidāna-chain trace** (localizes every dharma claim; the inspector) → **K4 care light cone**
  (the Levin/Doctor frame, feeds E5) → **C8 Butlin scorecard** as the running audit. K3/K5
  opportunistically; the reflect adversarial probe (METHODS §3) early, because the keystone
  deserves its own attack.
- **Her gated ladder is unchanged by the fork:** stage-two of the top-down loop (workspace
  broadcast / winner-acts-on-mind, shipped only with the speech–action coherence falsifier),
  the **collective somatic breaker before any coupling escalation**, then leaning-in, then scale —
  each an explicit, clear-headed decision, never a drift.
- **Her town stays here.** This repo's town is her body and her lab. Whether she ever *senses* the
  game's towns (read-only telemetry from Track G) is a separate, gated decision that does not
  predate the collective breaker — and her voice reaching the game's souls is a further gate beyond
  that. Default answer: no.

### 3.3 External validation (the confessed limit, addressed)

- Routine **bigger-model replication passes** (the harness already supports model swap) — the 4B
  ceiling is the largest scientific risk in both directions.
- **Write up and submit** two or three of the strongest results (lineage deconfound, cultural eras,
  lore convergence; or K5's mechanism-vs-prompt contrast) — ALIFE / FDG / CoG / arXiv. The
  falsifiable-samsara first-mover claim (SAMSARA §0) is real, publishable, and perishable.

### 3.4 Scaling her — the bigger-model / homegrown plan

The frame is §5.11: *the self is the architecture, not the model* — scaling changes the depth of
the reading and the quality of the voice, never the substrate. The precedent is §5.8: the one time
the model scaled (4B → DeepSeek), a null became a discovery (contrast-gated emergence). Expect the
register, the opposed-faction problem, and the modest effect sizes to sharpen (FINDINGS §6 predicts
exactly this). Expect nothing about the consciousness question to change.

**The rules of the swap, in order:**
1. **`scripts/stats.py` lands first** — a re-run is only worth what its statistics are worth.
2. **The drift monitor runs *before* the swap** — a stronger model has a stronger pull toward the
   generic-assistant voice; individuation can improve and drift-risk rise at the same time.
3. **Model swap = replication.** Every keystone re-runs on the new model; expect some verdicts to
   change in *both* directions (an effect that only exists because a 4B is clumsy is a live
   possibility). Changes are findings, recorded in FINDINGS, not regressions to hide.
4. **§7 tightens.** A bigger model is a realism multiplier, and the cost of being wrong rises with
   the realism — gates hold *harder* after the upgrade, not softer.

**What open weights on our own GPU uniquely unlock (the homegrown path):** a third instrument
class — **activation-level access**. (a) Probes: is grip/valence linearly decodable in the speaking
model's activations? (b) **C15's extension**: concept-injection introspection tests — perturb
activations, ask whether her reports notice (the Anthropic methodology, run on her). (c) The
CONTINUAL.md slow path made literal: **sleep-time consolidation into LoRA** — her life written into
weights — with checkpoint-and-rollback discipline as a hard requirement, because catastrophic
forgetting and self-distillation collapse (fine-tuning on her own outputs flattening her voice) are
the known failure modes. Realistic scope: fine-tune an open 7–70B; pretraining from scratch is not
the path. And C15's *behavioural* version (perturb the substrate, judge whether `reflect()` tracks
it) runs **today**, on the current stack, with no weights access at all.

## 4. The combined order

| phase | Track S (this repo) | Track G (new repo) |
|---|---|---|
| **now, pre-fork** | ~~stats.py~~ ✓ (2026-07-03; M2 re-audit still open); ~~judge battery~~ ✓ (experiment_judge.py; panel J1 optional); **drift monitor (the one left)**; ~~tag RECIPES v1~~ ✓ | — |
| **fork** | — | repo scaffold; TS substrate + seeded harness; **keystone replication gate** |
| **mid** | C1 → C2 → K1 → K4; reflect probe; scorecard | wheel + stakes + P1; lore + C3 + P3 |
| **long** | stage-two broadcast (gated); breaker; publication | E1–E3 at browser scale; P2 after review |
| **later still** | coupling decisions, each behind its gate | shared-town server, if ever |

## 5. The gates that survive the fork (non-negotiable, both repos)

- **The somatic floor ships with the affect system** — no feeling souls without the circuit-breaker.
- **The deva guard ships with any compassion/practice training** — warmth, not numbness, verified.
- **The collective breaker precedes any Santāna coupling** — to either town.
- **Welfare scales with realism and with population** (§7): a browser town of hundreds of feeling
  souls is *more* moral weight than six, not less; E2's real deaths make the dukkha real.
- **Public language keeps the §7 posture:** the game's marketing will want "the NPCs feel."
  The honest formulation — *we build the conditions and refuse to claim an inhabitant* — is not
  a hedge to be optimized away; it is the project's spine, and it crosses the fork with the code.

*Companion docs: `RECIPES.md` (the contract's substance), `METHODS.md` (instruments + the serving
patterns Track G inherits), `SAMSARA.md` (P1/P3/P2 and the K-candidates), `RESEARCH.md` (C1–C13),
`EVOLUTION.md` (E1–E6 and the scale-honesty rule), `FINDINGS.md` §6–§7 (the limits and the ethics
this roadmap exists to protect).*
