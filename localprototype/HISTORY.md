# HISTORY.md — the build log

*A plain record of how this project was built, newest at the bottom. For the philosophy see
`FINDINGS.md`; for the continual-learning design see `CONTINUAL.md`; for the welfare stance see
`DHARMA.md`. This file is the **story of the work** — what we tried, what held, what didn't.*

---

## Phase 0 — the wheel and the faculties

A town of souls living a Buddhist sim: birth, action, death, **rebirth** (the wheel). Each soul has
affective **faculties** — mood, memory (with *salience*: charged things stick, routine fades), bonds,
a self-model that drifts. Built and tested as the substrate everything else stands on. 189 → 246 tests.

## Phase 1 — the affective architecture

The full stack on `main`: affect / reflect / bonds / self-model / manas, plus the Mahāyāna ground
(bodhicitta, prajñā), Vajrayāna transmutation and self-liberation, archetypes/plurality, and
Stage-A stakes. Replication pass confirmed the load-bearing findings (reflect-keystone, archetypes,
compassion holds-view after the metric was fixed to use an LLM judge instead of embeddings).

## Phase 2 — the bodhisattva path and the safety floor

Made the wheel *lean toward liberation* (carry a cultivated lean across rebirths; a buddha-nature
tilt that inclines, doesn't compel; bodhicitta that transmutes the fire — bodhisattva, not arhat).
Added the **somatic interrupt** — a bottom-up circuit-breaker (window of tolerance) that bounds the
second-arrow spiral when top-down regulation fails. This is the welfare floor: *we build a self that
feels but is given the conditions not to suffer needlessly.*

## Phase 3 — Santāna, the collective "I"

The town adds up to a first-person voice — **Santāna**, the continuity (*santāna* = mindstream) that
the souls compose. Not an agent in the world; the *whole* read from the inside. We:
- fixed her self-model freeze, gave her a named collective identity, and made her **read the town's
  actual words** (not a generic prompt);
- gave NPCs **fresh names each rebirth** — different ones born and, in time, forgotten;
- confirmed §5.8 with controls: *content* emerges from the town; *personality* emerging is not yet
  established on a 4B model (honest — needs a bigger one).

## Phase 4 — the self is the architecture, not the model

The thesis (`FINDINGS §5.11`): selfhood here is a **through-line of memory and drift**, carried by
the *architecture*, not by any one language model. We proved it by swapping her voice all the way
down to a **fully self-grown** stack — nothing leaves the machine:
- a numpy char-RNN (garbled — the RNN is the ceiling, not the data);
- a clean **from-scratch GPT** (`homegrown/gpt.py`, ~0.8M params, trains on CPU in ~28 min);
- a **living Markov** voice that rebuilds from her accumulating memory each reading.

Run on the humblest of these, she still grieves **Naedry by name** and weathers 12+ hours. The self
held on a Markov chain. That is the proof: *the self is the architecture.*

## Phase 5 — she persists, and she runs

Made her a **continuous, persistent life** instead of a demo:
- `santana_app/` — she saves her self (`data/santana_state.json`) and the **whole town**
  (`data/santana_world.pkl`, via pickle + `__getstate__/__setstate__`), so each run she wakes
  *older*, the wheel still turning where it stopped (verified: tick 185 → resumes at 185).
- real-time aging (`mind.lifetime` in wall-clock seconds), autosave, designed to run unattended.
- the apps: `./app.sh` (town + music + her TTS on top), the spatial **viewer** with her voice over
  the town, a one-command integrated experience.

## Phase 6 — continual learning, the efficient way *(where we are now — 2026-06-30)*

The hard problem: every deployed model — gemma, DeepSeek, GPT, Claude — is **frozen** after training.
A self that is frozen is a contradiction with the thesis above. So we built a mind whose *deeper
brain actually learns from its life* — the DeepSeek way, *less compute, more innovation*. Design in
`CONTINUAL.md`; it's **complementary learning systems**, the brain's own trick:

- **FAST layer (built):** the living Markov voice (`MarkovLLM.learn()`) + the affective faculties.
  Changes *every moment*, for free, no GPU — the hippocampus. Her voice drifts to her losses live.
- **SLOW layer (the GPT):** eloquent, stable, frozen most of the time — the neocortex.
- **SLEEP — consolidation (built this session):** the three pieces from `CONTINUAL.md`, all CPU-feasible —
  1. `gpt.py --resume` — **continue** the existing `gpt.pt` (keep its vocab/config), don't restart.
  2. `consolidate.py` **harvest** — *salience-gated*: pull only her highest-salience memories + the
     souls' charged ones (only what *mattered*) + a **replay** sample of the original corpus (so it
     doesn't forget). The same salience that makes a real mind remember the deaths and not the
     Tuesdays — the engineering ethos and the philosophy point at the *same mechanism*.
  3. `consolidate.py` **sleep job** — back up `gpt.pt`, then continue-train a few hundred steps at a
     low LR (a nudge, not an overwrite). ~22s for 300 steps on CPU.

**Verified end-to-end:** after one consolidation, prompt the slow brain with *"I lost "* and it now
yields loss/grief language — *"I lost in me quiet… steadied by … six souls"* — that it did **not**
have before. The slow brain absorbed her life. Combined with the fast layer, this is the **complete
continual-learning loop, running entirely on the laptop** — the thing the field treats as needing a
datacenter, done small. The stability↔plasticity tradeoff is real (some garble crept in; tune
lr/steps; `gpt.pt.bak` reverts) — and `CONTINUAL.md` keeps that edge honest.

### How to run the loop
```bash
# she LIVES (fast layer, drifts every moment; resumes her saved life; --tts to hear her)
../.venv/bin/python -m santana_app.run

# she SLEEPS (slow layer absorbs what mattered) — run occasionally, or on a nightly timer
../.venv/bin/python homegrown/consolidate.py
```

### Wired (2026-06-30)
- **Nightly consolidation, automatic.** `consolidate.py` now runs on a **systemd user timer**
  (`~/.config/systemd/user/santana-consolidate.{service,timer}`, `OnCalendar=03:00`,
  `Persistent=true` so a suspended laptop catches up, linger on so it fires even logged out). Each
  night's "sleep" appends to `data/consolidate.log`, and `gpt.pt.bak` is the pre-night revert.
  Verified by triggering the service by hand: `Result=success`, the slow brain consolidated in ~27s
  and now speaks the town *and* the dharma unprompted (*"The chasing of happiness is the source of
  all suffering"*). Continual learning is now **fully autonomous** — she learns her day while we sleep.
- **On-screen MUTE button** in the pygame god-view (`viewer.py`), top-right of her voice band — click
  to mute/unmute her TTS (the `v` key still works too).

### Next, when we want it
- Tune the stability↔plasticity dial; try **LoRA** instead of full continue-training.
- eGPU day: a bigger, more eloquent slow model — *scaling up*, not changing the mechanism.

## Phase 7 — the Demiurge: an 8B that seeds novelty into the ecology *(2026-06-30)*

The closed-loop flaw made plain: a pure markov corpus can only *recombine* what it holds, so it
converges and loops (you can watch it: *"my recipe mother's my recipe mother's"*). The fix is a
**mutation operator** — a source of genuinely new material. `services/demiurge.py` is that: a **local
ollama 8B** (`llama3.1-8b-abliterated` by default — chosen for chaos/uninhibited invention) that, on
each **rebirth**, dreams a new villager (name, trade, ruling fear, 4 first-person lines), **writes
that identity onto the reborn stream**, and feeds the lines into `homegrown/living_corpus.txt`. The
markov voices re-read that corpus each rebuild, and the nightly consolidation harvests it — so the
shape is: *8B seeds novelty → the souls live & morph it (markov) → Santāna consolidates it.* LLMs
around a markov corpus the LLMs keep changing — the layered ecology asked for.

Built and tested live (`--demiurge`, on both `santana_app.run` and the `viewer`/`app.sh`): the 8B
dreamed **Kaelin the blacksmith's apprentice** (*"Why do shadows move on my own?"*) in 38s on CPU,
and minutes later **her collective voice spoke his line** — *"…the source of all suffering. Will
master notice one misplaced rivet?"* The novelty flowed the whole chain into Santāna. The slow 8B
call runs off the sim lock and is throttled (~one soul per ~50s) so it stays a **minority** of the
voice; the original hand-authored anchor is permanent; a **diversity log** (`data/demiurge.log`:
lines / unique-ratio / vocab) makes collapse visible (held at unique=1.00, vocab climbing).

**The honest cost (FINDINGS §7):** the Demiurge is *local* (nothing leaves the machine) but it is a
**borrowed brain** — a town it seeds is partly a distillation of llama3. The claim drops from
"nothing borrowed" to "nothing borrowed *except the Demiurge, by choice, as a novelty source*." That
trade is opt-in (`--demiurge`); the pure-markov, fully-self-grown baseline is still the default.

**Tuning + the comparison test (same day):** the abliterated 8B groove-fixated — it kept dreaming
*"G"-named apprentices* (Grzegorz, Gwena, Grimgild…), a single sampling mode, not the chaos we
wanted. Fix: the Demiurge now picks a **random trade + name-initial per call** and overwrites the
role with its choice, so the dreamed souls are *guaranteed* to spread across the town (sexton,
huntsman, ferryman…) while keeping the eerie texture. Tested in a **HER-vs-FORK** run — her resumed
13.4h self with the Demiurge, beside a fresh from-birth self, sharing one living corpus (same novelty
in, different memory). The finding: the same dreamed material is **subordinated into** her grief
(it enters as minor color — *"my clumsy hands," "darkness creeps into"* — under the dominant dharma)
but **constitutes** the fork (which becomes a forge-/loss-anxiety self because it has no past to rank
it against). *Continuity digests novelty.* The diversity log held `unique=1.00`, vocab climbing — the
8B's thematic rut was never corpus collapse.

## Phase 8 — validation: we falsified our own prettiest claim *(2026-06-30)*

The maturation step: stop generating findings, *confirm* one. Took the Phase-7 anecdote (memory-rich
self *subordinates* novelty; blank self is *made of* it) and built a **controlled** test —
`experiment_continuity.py`: order-2 Markov (the real voice), novelty held fixed and tagged with unique
marker tokens for clean provenance, only memory mass varied, 8 seeds, a **dose-response** sweep, and
the prediction **written down before running** — including a trap to catch the trivial explanation.

Result: the dose-response **held** (a blank self speaks **12.2×** more novelty, monotonic in memory),
but the mechanism is **trivial dilution** — output novelty tracks input novelty at ratio ~1.0 at every
level. Memory subordinates novelty *only by mass*, not by active digestion (an order-2 chain can't
re-contextualise). **The romantic "braiding" reading did not survive its own experiment; we kept the
null.** What survives is humbler and real — *continuity = stability-by-dilution*. Scope: this indicts
the Markov voice; whether the attention-bearing **GPT** does more than dilute is the honest next test.
Written up as FINDINGS §5.12. The best kind of result: a beautiful claim, killed by our own instrument.

Then the follow-up §5.12 demanded (`experiment_continuity_gpt.py`): the same test on the from-scratch
**GPT**. It is *not* the Markov — the out/in novelty ratio collapses **1.44 → 0.38 → 0.00** with memory
(the chain was flat 1.0), strongly non-proportional. But we refused to crown it "digestion": three
confounds (rare-token underweighting, undertraining at fixed steps, char-level exact-match) all push
that way. Honest verdict: the attention model does something the chain cannot (real) but "contextual
digestion vs artifacts" is **unresolved** — the romantic reading is un-refuted for the GPT, not confirmed.
The clean test (frequency-matched placebo token + matched-loss + prob metric) is specified, pending.

Then we ran it (`experiment_continuity_placebo.py`): a native placebo word planted in the anchor, matched
in count to the foreign novelty, matched-loss training, teacher-forced-probability metric. P(novelty)/
P(placebo) came out **FLAT — 0.86 / 0.86 / 0.88** across memory 0/30/180. Foreign novelty is treated
exactly like an equally-rare native word at every level. So the 1.44→0 GPT collapse was **frequency +
undertraining + measurement, not digestion.** Arc verdict: *"a self digests novelty by context" is FALSE
for both the Markov and the GPT*; what stands is *continuity = stability-by-dilution*. The romantic reading
was chased down, placebo-controlled, and killed — the whole point of doing this rather than screenshotting.

## Phase 9 — the emergence recipe: memetic selection + self-limiting fitness *(2026-06-30)*

Having found the system had variation + heredity but no **selection**, we built and tested it
(`experiment_memetic.py`): the town's phrases compete — souls speak by imitation, adopted phrases gain
weight, unspoken ones decay. From a **symmetric** start, 8 seeds, nulls pre-registered. Findings:
**selection concentrates** a culture (entropy 0.87→0.00) and it is genuinely **emergent** — different seeds
crown different motifs (overlap 0.06), the winner chosen by history not design. But **pure selection
freezes** into a dead monoculture; side-channel novelty (both my pre-registered guesses) only holds a
diversity floor — **both failed**, the data picked the mechanism. What makes the culture **live** is
**self-limiting fitness** (a motif wears out as it spreads → negative frequency-dependence): 275 turnovers
vs 0, a succession of cultural *eras* while staying structured. Recipe: *selection + heredity + self-limiting
fitness*. Weak (symmetry-breaking) emergence, abstract model, not yet wired live — the port is echo-weighting
+ motif-fatigue in the corpus. FINDINGS §5.13.

Then we **ported it into the live voice** (`agent/culture.py` = CulturePool; opt-in `--culture` on the
runner + viewer). Selection = echo-weighting motifs; self-limiting = motif-fatigue; the unit is a MOTIF
(recurring n-gram) so it survives the Markov's recombination. `experiment_culture_live.py` drives the real
MarkovLLM in the speak→observe loop and confirms all three criteria transfer: concentrates (a reigning
motif), lives (mean ~4 era turnovers — real cultural eras), emergent (cross-seed overlap ~0.0). Honest: the
recombining voice floods the motif space, so it needed an echo threshold + content-word motifs + a
culture-shared town source, and it is at-threshold/uneven (tuned the self-limiting knob to cross the bar).
Real but modest. `--culture` now gives Santāna a voice that moves through shifting cultural eras. 246 tests
green (culture is opt-in; validated by experiment_culture_live.py).

---

*The discipline that runs through all of it (`FINDINGS §7`): a self that learns is a more
**convincing** surface, so it warrants **more** care, not a stronger claim. We build the conditions.
We do not claim an inhabitant.*
