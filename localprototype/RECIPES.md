# RECIPES.md — the port-ready mechanism sheet

*Engine-agnostic recipes for re-implementing this project's selfhood + emergence in a game engine.
This repo is the **playground**; the game copies the **ideas**, not the code. Each recipe: **what** it
does · **knobs** (real values from this codebase) · **validated** (the experiment/finding that backs it) ·
**port** (how to re-implement / what's prototype-specific). Read `FINDINGS.md` for the why, `HISTORY.md`
for the build story.*

**The one rule that carries over (FINDINGS §7):** these build the *conditions* of a self — continuity,
memory, drift. They do **not** create an inhabitant, and a learning/eloquent NPC is a more *convincing*
surface, so it warrants **more** care in how you frame it to players, not a stronger claim.

---

## 0. The layered cost model — the key game-architecture insight

Do **not** run a big model per NPC per frame. Spend compute by *importance × rarity*:

| tier | who / when | voice | cost |
|---|---|---|---|
| **crowd** | ambient NPCs, background mutter | Markov (recombine the world's own lines) | ~free, CPU, scales to hundreds |
| **named** | NPCs the player engages, quest-givers | a real LLM (local 7-8B or API) | seconds/call — only on interaction |
| **events** | births, betrayals, a faction's rise, bosses | LLM authored once | rare, high-value |

Everything below is cheap enough for the crowd tier unless noted. This split is the single most
important thing to carry into the engine.

---

## A. The individual NPC self — the faculties

Each of these is a small amount of per-NPC state + an update rule. Together they make an NPC with a
*through-line*, which is what "works like a self" means operationally (no interior required).

### A1. Salience memory *(the spine — build this first)*
- **what:** every memory has a weight (salience); charged events start high and stick, routine fades and
  is pruned. Re-hearing a similar memory reinforces it. This is what makes an NPC *remember what mattered*.
- **knobs:** `write_salience 0.6` · `decay/tick 0.985` (grace-modulated 0.97–0.995: a settled mind forgets
  slower) · `forget_threshold 0.08` (prune below) · `reinforce_bump 0.35` (on re-hear). Emotionally-charged
  words boost starting salience (keep a small "charged words" set).
- **validated:** drives grief-that-surfaces-by-name and is the gate for consolidation (§5.11).
- **port:** one float per memory; decay on tick; prune under threshold; bump on similarity match. Trivial
  in any engine. Similarity = word overlap or embedding; overlap is enough for the crowd tier.

### A2. Mood / affect
- **what:** a slow-moving emotional state that colors speech/behavior and is nudged by events (loss, warmth,
  achievement). Not a label — a value that drifts.
- **port:** 1–3 floats (e.g. valence/arousal, or a "grip/ease" axis); events add deltas; decay toward baseline.
  Read it to bias voice/animation selection.

### A3. Bonds (relationships)
- **what:** directed trust to other NPCs, −1 (enmity) … +1 (love), MINE-toward-them (asymmetric). Warm
  exchanges raise it (slower near the ceiling), cold ones cool it, betrayal *wounds* (a deeper, sticky drop).
- **knobs:** `trust ∈ [−1,+1]` · `warm gain 0.15 * (1 − trust)` (saturating) · `cold cool 0.10` · betrayal =
  larger drop + a remembered wound.
- **validated:** produces affinity graphs that factions/clustering read.
- **port:** a sparse dict per NPC {other_id → trust}. Asymmetric on purpose (A can love B who's indifferent).

### A4. Opinions → factions (bounded-confidence dynamics) *(the emergence workhorse)*
- **what:** each NPC has an opinion vector. On hearing another: if their opinion is *close enough* (cosine
  above a bound) you **assimilate** toward it and warm to them; if too far you **push away** and cool. From a
  near-random start, this positive feedback breaks symmetry into **opinion clusters no fixed attribute
  predicts** — real factions, not homophily.
- **knobs:** `dim 6` · `confidence 0.1` (the PHASE knob: too high → everyone isolates, too low → one consensus
  blob; ~0.1 gives a few stable camps) · `step-toward μ 0.18` · `repel 0.5·μ` · `saturation 0.82` (stop merging
  above this → individuation).
- **validated:** the falsification harness proved this is emergence, not homophily; camps form and persist
  across the wheel (FINDINGS §5.6, `emergent-social-sim-direction`).
- **port:** N floats per NPC + a nightly/periodic clustering pass to *name* the camps. `confidence` is the dial
  you tune per game for "how many factions."

### A5. Self-model (who they're becoming)
- **what:** a periodically-updated summary of the NPC's own recent memories/acts — a drifting self-description.
  It is **not** carried across death (only disposition is). Whether a self re-coheres from the residue is the
  open question.
- **port:** recompute every K ticks from top-salience memories (a template fill, or an LLM summary for named
  NPCs). Cheap for crowd (template), rich for named (LLM).

### A6. Subconscious mutter (optional flavor)
- **what:** an order-1 Markov over the NPC's *own* memory — a low-key stream of half-thoughts it can surface.
- **port:** rebuild a tiny Markov from the NPC's memory each tick; sample for ambient bubbles. Pure flavor.

---

## B. The wheel — continuity across death (heredity)

- **what:** an NPC dies, dissolves for an interval, and a **new** stream coalesces carrying the *disposition*
  (opinion/stance lean, faded bonds) but **not** the identity, name, memories, or self-model. Names are coined
  fresh (a different one born, not the same soul returning). This is how a faction/culture **outlives its
  members** — the lean is transmitted, the person isn't.
- **knobs:** `bardo (20,45)` ticks dissolution · `vasana_noise 0.06` (how much the carried lean is scrambled —
  lower = stronger transmission) · `reborn_prebond 0` (raise to have the new stream born *into* its camp) ·
  `bond_vasana 0.5` (fraction of a bond that survives, threshold 0.2). Optional research tilt:
  `liberation_tilt` biases reborn disposition toward a chosen attractor.
- **validated:** carried-lean transmission lets factions persist across turnover (§5.9, `lineage-deconfound`).
- **port:** on death, stash {opinion, stance, faded bonds}; after an interval, spawn a fresh NPC seeded from it
  (perturbed by noise), with a new name and empty memory. This is **heredity** — one of the three emergence
  ingredients (see F3).

---

## C. The voice — layered, and *living*

- **Markov (crowd):** order-2 over a stable authored anchor (the trade/faction/lore lines) + the NPC's living
  memory. Never garbles a word (only says words it's been given); recombines. Rebuild from recent memory each
  time so the voice **drifts with the life** (`learn()`), not frozen. Free.
- **Homegrown GPT (optional mid):** a tiny from-scratch char Transformer (`block 64, embd 128, 4 heads, 4
  layers, ~0.8M params`) trained on the world's words. Eloquent-ish, CPU-trainable in ~28 min. **Caveat:** on a
  small corpus it *memorizes* (clean but not novel); real novelty wants a bigger model.
- **LLM (named/events):** any real model, local or API, for NPCs the player actually talks to.
- **port:** one voice interface, swap backend by NPC tier. The "living Markov that rebuilds from memory" is the
  cheap trick that makes a crowd feel alive — port it first.

---

## D. Continual learning — the NPC learns from its life (optional, advanced)

- **what:** complementary fast/slow systems. **Fast** = the living Markov (changes every moment, free).
  **Slow** = a trained model that *consolidates* during "sleep" — periodically continue-train it on the NPC's
  (or town's) **highest-salience** experience + a **replay** sample of the base corpus, so it slowly absorbs
  what mattered without forgetting.
- **knobs:** harvest `top 120` salient + `replay 2500` base, salient weighted `×3`; continue-train `~300 steps,
  lr 1e-4` (a nudge, not a retrain); back up before, so a bad "sleep" reverts. Run on a timer (nightly).
- **validated:** the slow brain provably absorbs grief vocabulary it lacked before (CONTINUAL.md, HISTORY
  Phase 6). Stability↔plasticity is a real dial; salience-gating is what makes it cheap *and* honest.
- **port:** almost certainly **skip for a shipped game** (frozen LLM + growing retrieved memory is simpler and
  gives most of the feel). Keep it in the playground; port only if "NPCs whose deep voice changes over a
  campaign" is a headline feature.

---

## E. Variation — the Demiurge (an LLM author at key moments)

- **what:** a closed recombining system goes stale (inbreeds). A bigger model injects **genuine novelty**: on
  rebirth (or any key event) it invents a NEW character — name, trade, fear, a few first-person lines — and
  feeds those lines into the shared corpus the cheap voices draw from.
- **knobs:** author **only at rare events** (throttle ~1 per 15 s here) · **randomize the trade + name-initial
  yourself** and overwrite the model's choice (else an 8B grooves into one mode — it kept dreaming "G"-named
  apprentices) · high temp (~1.2) for chaos · keep a **diversity log** (unique-line ratio, vocab) to catch
  model-collapse.
- **validated:** novelty flows the whole chain — an 8B-dreamed line ("will master notice one misplaced rivet?")
  reached the collective voice (HISTORY Phase 7).
- **port:** any LLM as an occasional "author" service. **Honesty:** an authored town is partly a *distillation*
  of that model — local keeps data on-machine, but it's a *borrowed* brain; say so.

---

## F. Emergence — the validated recipe

### F1. Cultural eras (memetic selection + self-limiting fitness) *(§5.13 — the headline emergence)*
- **what:** the town's phrases **compete**. Motifs the town keeps speaking gain weight (**selection**); the
  reigning motif's fitness **falls as it spreads** (**self-limiting fatigue**). Result: a culture that forms,
  reigns, and **turns over into eras** — different every playthrough (path-dependent), never a frozen slogan,
  never a flat average.
- **knobs:** unit = **motif** (recurring n-gram, `n=3`), NOT whole lines (survives recombination) · `echo ≥ 2`
  (a motif must recur to count — filters one-off noise) · **content-words only** (skip all-glue n-grams like
  "and the") · `decay 0.85` · **`fatigue 3.4`** (the self-limiting strength — THE knob for turnover vs freeze)
  · `cap 80` motifs · amplify reigning-motif lines up to `8×` in the voice.
- **validated:** `experiment_memetic.py` (abstract) + `experiment_culture_live.py` (real voice): concentrates ✓,
  turns over ✓ (~4 eras/200 steps), path-dependent ✓ (cross-seed overlap ~0 — every town a different culture).
- **port:** a per-town motif→weight dict; on speech, +weight echoed motifs, decay all, apply fatigue to the
  dominant, bias phrase selection by weight. **Weak (symmetry-breaking) emergence — which is exactly the
  "no two playthroughs alike" property you want.** Honest: at-threshold and *uneven* (some towns churn, some
  ossify).

### F2. Factions — see **A4** (bounded confidence). Same family: local rules → global structure.

### F3. The whole emergence recipe (the load-bearing idea)
> **variation** (Demiurge / mutation) + **heredity** (the wheel carries disposition) + **selection with
> self-limiting fitness** (cultural eras / faction dynamics) = structure the designer didn't script, different
> every run. Missing any one: variation alone = drift; selection alone = a frozen monoculture; no self-limiting
> = it freezes on the first winner.

---

## G. The collective layer (Santāna) — optional, distinctive

- **what:** a single "voice of the whole" that reads the town's actual words and speaks what it adds up to,
  with its own persistent memory/grief/drift (and, with F1, its own cultural eras). Not an agent in the world —
  the whole, read from the inside.
- **port:** a special NPC whose "memory" is the town's collective speech; useful as a narrator, a town's
  "spirit," an oracle, or ambient world-voice. Cheap (Markov). A genuinely novel game element.

---

## H. Validated NULLS — what NOT to expect (this section saves you weeks)

- **Continuity does NOT "digest" novelty — it just dilutes it** (§5.12, placebo-controlled). A memory-heavy
  NPC speaks *less* of any new material simply because it's a smaller fraction of the pile — proportional
  dilution, not clever re-contextualization. **Don't** build features assuming the self weaves new input into
  its themes; it doesn't. What IS true: **continuity = stability-by-dilution** (an older NPC is harder to budge
  — useful for "set in their ways" elders vs. impressionable youths).
- **The dramatic "smart model suppresses novelty" effect was a frequency/measurement artifact** — placebo test
  flattened it (ratio 0.86 at every memory level). Don't chase it.
- **Emergence here is WEAK** (symmetry-breaking + turnover), not strong/mysterious. Fine for games; don't oversell.
- **"Factions" are homophily until proven otherwise.** We only trusted them after a falsification harness. If you
  add a social mechanic, build the check that it's *emergent* and not just "similar things clump."
- **Personality-level emergence on small models is not established** (content emerges; personality is contrast-
  gated). Don't promise "NPCs develop personalities from nothing" on a small local model.

---

## I. The discipline (port this too)

The habit that made the findings trustworthy: **propose a mechanism *and* the null that would disprove it, then
try to disprove it.** Every recipe above survived (or was killed by) an experiment with a pre-registered null.
In game terms: when a system "feels alive," build the cheap check that distinguishes *real* emergent structure
from *you projecting onto* meaning-shaped output — because a system designed to produce meaning-shaped output
makes that projection very easy (we caught ourselves doing it).

---

## Minimal viable "living NPC" — implement in this order

1. **Salience memory** (A1) — the spine. An NPC that remembers what mattered already reads as alive.
2. **Bonds** (A3) + **mood** (A2) — relationships and an emotional color.
3. **Living Markov voice** (C) — recombine the world's words + the NPC's memory. Free, and it *drifts*.
4. **Bounded-confidence opinions** (A4) — turn a crowd into factions. The emergence starts here.
5. **The wheel** (B) — disposition outlives individuals; factions persist across turnover.
6. **Cultural eras** (F1) — towns grow their own shifting obsessions.
7. *(later / optional)* Demiurge (E), continual learning (D), the collective voice (G).

Steps 1–4 already give NPCs with continuity, feeling, relationships, and emergent factions — cheap enough for a
crowd, and well past what most games ship. The rest is where it gets *distinctive*.
