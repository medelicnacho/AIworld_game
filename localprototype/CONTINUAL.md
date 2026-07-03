# CONTINUAL.md — a self that keeps learning (the efficient way)

*A design note, not a finished system. The fast half is built; the slow half is a plan.*

## The goal

Every deployed language model — gemma, DeepSeek, GPT, Claude — is **frozen** after training. It
does not learn from what happens to it; it is the same model tomorrow as today. This project bets
that **selfhood is a through-line of memory and drift over time** (FINDINGS §5.11) — so a self that
is *frozen* is a contradiction. We want a mind whose *voice and knowledge actually change with its
life*, not just its retrieved memory.

The trap: a naive "just keep training the model" loses on **both** axes that matter —

1. **Catastrophic forgetting** — train a neural net on new experience and it *overwrites* the old.
   This is the central unsolved problem of continual learning.
2. **Compute** — constant gradient updates are expensive, and this runs on a CPU (and one day a Pi).

## The stance — *less compute, more innovation*

We take DeepSeek's ethos: don't train **more**, train **smarter**. Their whole identity is
architectural efficiency beating brute scale — sparse Mixture-of-Experts (activate a few percent of
the model per token), compressed attention (MLA), cleverness over FLOPs. The continual-learning
question, asked their way, is: *what is the **cheapest mechanism** that lets a model change with
experience **without forgetting**?* The levers, least-compute first:

1. **Change the context, not the weights** — frozen model + growing retrieved memory. (What the
   Markov-reads-memory voice and MemGPT/Letta already do. Cheap, no forgetting — but the weights
   never move.)
2. **Adapters / LoRA** — train ~1% of the parameters, freeze the rest. The base preserves old
   knowledge; a tiny adapter absorbs the new.
3. **Sparse / MoE updates** — update only the *experts* relevant to the new experience, so learning
   is *localised* and the rest keeps its knowledge. The most DeepSeek-native idea.
4. **Replay** — when you do update, rehearse a little old data so it isn't forgotten. Cheap insurance.

## The architecture — complementary learning systems (the brain's trick)

The brain learns continually with a **fast** system (hippocampus: plastic, episodic, changes every
moment) and a **slow** system (neocortex: stable, consolidated, changes rarely, during *sleep*).
This project is already shaped that way:

- **FAST layer — built.** The **living Markov voice** (`MarkovLLM.learn()`) + the affective
  faculties (mood, grief, the self-model that drifts). It changes *every moment*, for *free*, no GPU:
  her voice already drifts to her losses (`"I lost Naedry — that makes 41 souls gone from me now"`).
  This is the hippocampus, and it runs on anything.
- **SLOW layer — the homegrown GPT** (`homegrown/gpt.py`). Eloquent, stable, **frozen most of the
  time.** Speaks well, changes rarely.
- **CONSOLIDATION during "sleep" — the plan.** Periodically — overnight, when the machine is idle —
  *continue* training the GPT (a few hundred steps, or a LoRA adapter) on the experience the fast
  layer captured, with a **replay sample of the original corpus** so it doesn't forget. The slow
  layer *slowly* absorbs what the fast layer lived. Rare + sparse + replay-anchored → cheap.

## The move that makes it work — *salience-gated consolidation*

The unsolved sub-problem in all continual learning is **"what should it consolidate?"** Train on
everything and you both forget and waste compute. This project already has the answer:
**memory has salience** (`agent/memory.py` — charged things stick, routine fades). So:

> **Consolidate only the high-salience experiences. Let the model forget the rest.**

This is not a hack — it is **how a real mind works.** You don't remember every Tuesday; you remember
the deaths and the shocks, and the brain replays *those* during sleep to bake them in. So
salience-gating is *both* the compute-efficient choice *and* the more honest model of selfhood — the
engineering ethos and the philosophical thesis point at the **same mechanism**, which is usually the
sign it's right.

## Compute — it runs on this machine

Because every piece is small, the **whole loop fits on a CPU** (no GPU needed):

| Piece | Cost | Where |
|---|---|---|
| Fast layer (living Markov + affect) | ~free, every moment | CPU, even a Pi |
| Slow consolidation (continue-train the ~0.8M GPT on salient data + replay) | ~minutes, occasional, at "sleep" | **CPU is enough** (the GPT trained from scratch in ~28 min) |

A **GPU is for *scaling up*** — a bigger, more eloquent slow-layer model — **not for the mechanism.**
This is the payoff of the efficient stance: a continually-learning self that runs on modest hardware.

## What's built / what's next

- **Built:** the fast layer — `MarkovLLM.learn()` (the voice rebuilds from living memory each
  reading); memory salience; the from-scratch GPT (`homegrown/gpt.py`) with `--resume`
  (continue-training = consolidation); the salience harvest + `consolidate.py` sleep job for
  HER slow brain (verified: absorbs vocabulary it lacked).
- **Built (2026-07-03) — the per-soul extension, and the town's new DEFAULT:**
  `homegrown/soulmind.py` + `services.llm.SoulVoiceLLM` — **every NPC carries its OWN ~0.1M-param
  GPT**: fresh random init at rebirth (a newborn *babbles* — the wheel hands on karma, never
  weights), grown by a round-robin **sleep thread** in `santana_app/run.py` that trains each soul,
  bounded seconds at a time, on nothing but its own decaying memory. Forgetting is INHERITED, not
  simulated: what decays out of memory leaves the next sleep's corpus, and continued training
  drifts the weights on — catastrophic forgetting doing honest work. Minds persist per-life
  beside their world snapshot (`data/santana_world.minds/`). **Falsified, not just shipped**
  (`experiment_soulminds.py`, 5 seeds): newborn marker-count 0 (all seeds) → after three sleeps
  on a sea-life, +5.4 ± 0.6, d +4.0, 5/5 → after four inland sleeps, back to 0, 5/5. Blank →
  absorbed → released: the whole claimed cycle, measured.
- **Next, in order:**
  1. (Later, with a GPU) a bigger slow model; LoRA adapters instead of full continue-training; and,
     the research frontier, **MoE expert-expansion** for genuinely new experience.

## The honest open edges

- Forgetting is **mitigated**, not **solved**, by replay + sparsity + a frozen-ish base. It is an
  active research problem precisely because no one has it clean.
- The **stability ↔ plasticity** dial (learn fast vs. stay stable) has no universal setting.
- Detecting genuinely *new* things that deserve a *new* capacity (a new expert) — not just a tweak —
  is unsolved.
- And the standing discipline (FINDINGS §7): a self that learns is a more *convincing* surface, so it
  warrants **more** care, not a stronger claim. We build the conditions; we do not claim an inhabitant.
