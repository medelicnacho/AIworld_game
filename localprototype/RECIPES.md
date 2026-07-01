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

### A7. Expectation + appraisal — the NPC's future tense *(the realism multiplier)*
- **what:** the NPC *expects*, so the same event does different things to different NPCs. Three floats
  of state: a fast and a slow EWMA of its lived mood (the gap = its felt trend), and arousal (a spike
  that settles). On every event, **appraise before writing**: unexpected loss → SHOCK (charge amplified,
  arousal spikes); braced-for loss → RESIGNATION (softened); unexpected good → RELIEF (brighter). Per
  bonded other, one more float: expected conduct — a cold act from someone expected warm is a
  **BETRAYAL** (a remembered wound, A3's `betray()`), the *same act* from someone expected cold is
  weather. This is the mechanic that makes players say "someone's home": the NPC who trusted you reacts
  differently to your betrayal than the one who always suspected you.
- **knobs (validated values):** fast EWMA `0.25`, slow `0.04`, arousal decay `0.90/tick` · surprise floor
  `0.25` (below = "about what I expected") · shock amplification `0.8×surprise`, resignation `−25%`,
  relief `0.4×surprise` · conduct EWMA `0.2`, betrayal gap `0.3` below an expectation `> 0.1`.
- **turning points (the self-model made causal):** a SLOW expectation of the NPC's *own* conduct
  (EWMA `0.02` — **identity must be stickier than adaptation**, measured: at 0.08 the self quietly
  becomes the new self with no story); sustained out-of-character action accrues dissonance (`0.08/act`
  beyond a `0.45` gap, easing `0.02` in character, turning at `1.0`) → ONE high-salience narrative
  memory ("something in me has turned: I was one who shared…") that enters identity recall. Fires on a
  real shift exactly once, never on noise, no oscillation — a character-arc chapter break for free.
- **validated:** `experiment_appraisal.py` 7/7 pre-registered claims 5/5 seeds (identical −0.7 loss:
  blindsided −1.00 vs braced −0.81, arousal 0.38 vs 0.10; identical cold act: 1 wound vs 0);
  `experiment_turning.py` 4/4 at 5/5 (FINDINGS §5.15).
- **port:** ~5 floats per NPC + one appraisal function at the event-write point. Crowd-tier cheap.
  Feed `arousal` to animation intensity and `foreboding` (slow − fast, when positive) to wary idle
  poses — free body language from state you already track.

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

## G2. The psyche — ONE deep NPC as a society of parts *(the companion/boss recipe)*

- **what:** the inverse of the crowd recipes: one character whose inner drives (Dread, Ache, Longing,
  Tending, Watcher, Ember) are cheap sub-agents, each **carrying one faculty** (threat-clutch, loss-ledger,
  wanting, care, metacognition, will-to-recover), competing in a **global workspace** for "the floor" —
  the current dominant drive. The floor-holder is a single discrete state per tick: drive it into
  animation, dialogue tone, and behaviour selection directly. Crowd-tier cheap (a handful of floats);
  the LLM is only needed for the integrating voice.
- **knobs (validated values):** activation = `sat(gain × faculty signal)` — the **saturation
  (x/(1+x)) is load-bearing** (unbounded memory-load bids otherwise swamp bounded drives; measured).
  Split the aversive signals: the fear-drive reads **fresh** charge (window ~20 ticks), the grief-drive
  the **accumulated ledger** — same fuel and they move as one part (measured). Workspace: leaky presence
  `decay 0.80` + **fatigue-with-memory** (`build 0.06` while holding the floor, `recover ×0.95` while
  resting) + **hysteresis** (`challenger > 1.25× incumbent`). Two traps, both measured: an
  *instantaneous* share-penalty (the F1 formula) freezes on the QUIETEST bidder under steady bids, and
  no-hysteresis flickers the floor every tick. Fatigue-with-memory is also free game design: it's why a
  boss can't stay Enraged forever.
- **validated (held-out seeds, FINDINGS §5.14):** the floor **tracks the world** (grief-drives hold
  ~half a harsh world's floor, none of a kind one's — it cannot be faked by a fixed ranking) and the
  drive-succession is **structured** vs chance. That's exactly what a game needs: a mood system that
  responds to what the player does, with non-random texture.
- **NOT validated — don't ship these claims (see H):** recurring drive-*coalitions* ("moods") and the
  floor *predicting* the character's emotional trajectory both failed falsification (0/5).
- **port:** per-drive: a handful of floats + one activation formula reading the NPC's existing
  memory/mood state. Workspace: ~30 lines. One bonus dynamic worth keeping: score the loss-ledger only
  from **world events**, not the NPC's own generated lines — otherwise dark flavour text feeds back as
  grief and the character sinks regardless of what happens (rumination-by-rehearsal; measured, and it
  will happen in any engine that writes generated dialogue back into memory).

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
- **The psyche's "moods" and "foreshadowing" are not established** (§5.14, held-out 0/5 both): drive
  coalitions (Dread+Ache as a recurring pair) don't beat a shift null, and the reigning drive does NOT
  predict where the character's felt life goes next. The workspace is a world-tracking *readout* — ship
  it as reactive mood display, not as an inner life that anticipates. Also a measurement trap for your
  own tests: aperiodic event schedules only — periodic ones hand a circular-shift null the structure
  you're testing for.
- **Expectation does NOT rescue the psyche's foreshadowing** (§5.15): wiring the mind's worsening trend
  into the fear-drive's bid left prediction at 0/5 held-out and *degraded* the validated succession
  structure — reverted. The floor is a readout of dynamics it doesn't cause. Use A7 (appraisal) at the
  individual-NPC level, where it's fully validated; don't expect the G2 workspace to forecast. And note
  the overfit warning it produced: the coalition claim hit 4/5 on tuning seeds and fell to 2/5 held-out
  — always keep held-out seeds.

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
