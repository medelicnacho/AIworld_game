# RECIPES.md — the port-ready mechanism sheet **(v1, tagged 2026-07-03)**

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

### A8. The named-NPC relationship tier *(§5.17–5.18 — the companion mechanics, all validated)*
- **what:** six mechanics that turn a bonded NPC↔player (or NPC↔NPC) relationship into something with
  memory and stakes: **episodes** (a conversation consolidates into ONE narrative memory — "the day you
  saved my flock"); a **person-model** (first-person facts the other disclosed, kept and referenced);
  **absence-as-event** ("you've been away since the frost", valenced by the bond); **initiative**
  (state-driven asking — an NPC that raises its own unresolved wound is a quest the designer didn't
  write); **manner** (the bond shapes the FORM of speech: wounded+distrustful → brief and guarded,
  deep trust → expansive); and **scars** (a wound with trust rebuilt reads "they hurt me once, and I've
  come past it" — but ONLY once real warmth happened *since* the wound; without that gate, measured,
  the loyalty buffer says "come past it" seconds after the knife).
- **plus the intent judge + promises** (the two that need an LLM): judge WARM/COLD/APOLOGY/PROMISE/
  NEUTRAL per player line (word-free coldness lands; apologies soothe), and PROMISE lines become
  commitments — kept (mentioned again warmly → deep trust) or **broken by the calendar** (lapsed →
  a true betrayal). A player who breaks promises to NPCs who remember them: that's a reputation
  system with a soul.
- **knobs:** episodes weight `1.5` · person-model cap `6-12` facts, first-person-keyword gated ·
  absence threshold `6h`, emotion `0.8×trust` · promise horizon `7 days`, kept-bonus `warm(0.8)` ·
  kept-check runs BEFORE new-promise storage (measured: a promise otherwise keeps itself instantly).
- **cost:** all floats-and-strings except episodes + judge (one LLM call per session / per line) —
  strictly the NAMED tier; the crowd keeps A1-A4.

### A9. Provenance at recall — confidence, source, ownership *(§5.19 — one pass, three findings)*

- **what:** every memory carries provenance no self reads (source, story-lineage id, drift counters).
  A **discriminator at recall** reads it *through the drift*: dreams say "I dreamt it, I think", stories
  say "a story I was told", the worn say "I may have it wrong", the unowned decline the autobiography
  ("this happened — though not, I think, to me"). Content-doubt and source-doubt are **different axes**:
  cross-source merges smear the frame fast (retelling a story in your own voice is how it becomes yours,
  weight `0.9`); pure word-drift wears it slowly (`0.2`).
- **validated:** §5.19 verdict on virgin seeds, all four claims — hedges track ground-truth drift (d +5.4);
  tags beat a shuffled-provenance null (+0.64); **emergent false memory occurs, only via self-retelling,
  and is 100% traceable** through the undecayed lineage id; ownership ablation dissociates cleanly (an
  unowned wound bends mood while vanishing from the told story).
- **port:** three ints/floats per memory + one pure classifier + prompt-time annotations. The false-memory
  leak is the lore system's deepest trick: *the NPC misremembers a legend as its own life, and you can prove it.*

### A10. Pledges — promises with deadlines that become reputation *(§5.20 — the join-or-oppose substrate)*

- **what:** any id (a soul, or the **player** — just another id) gives a soul its word, held to the town
  clock. Kept in time → trust at the Bond's slow designed pace (never a cheat-code) + a warm conduct story.
  Lapsed → **always** a betrayal (a promise IS an explicit expectation; loyalty absorbs as everywhere) + a
  dark conduct story into the A4/F4 gossip channel.
- **validated:** §5.20 verdict 5/5 both directions — a word broken to ONE soul makes untouched bystanders
  wary of the promiser (zero opinions in the no-gossip null); kept words travel warm; per-subject.
- **knobs:** made-nudge `0.15` · kept-sig `0.65` / warm `0.5` · broken-sig `-0.7` / betray `0.6`.
- **port trap (measured, consumed a verdict): gossip transmits feeling only through the WORDING** — hearers
  re-derive charge from the retold text, so conduct stories must carry their emotion in words the sentiment
  sensor can read (and mind irregular pasts: "broke" says nothing, "broken" travels).

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

### C2. Soul minds — every NPC its OWN tiny GPT, born babbling, grown by sleep *(new default here)*

- **what:** a ~0.1M-param from-scratch char-GPT **per soul**: fresh random init at rebirth (newborns
  *babble* — the wheel hands on karma, never weights), trained only by bounded **sleeps** on its own
  decaying memory. Forgetting is **inherited, not simulated**: what decays out of memory leaves the next
  sleep's corpus, and the weights drift on (catastrophic forgetting doing honest work).
- **validated:** the full cycle, 5 seeds — newborn marker-count 0 → absorbed after three sleeps
  (+5.4 ± 0.6, d +4.0, 5/5) → released after four unrehearsed sleeps (back to 0, 5/5).
- **dreams ride the sleep:** every 3rd sleep the soul dreams one line in its own grown voice (hotter temp),
  written back tagged as a dream → A9 voices it as "I dreamt it, I think", and a worn dream can leak into
  believed memory by the measured pathway.
- **port:** fixed shared charset (per-soul corpora are tiny/changing — never derive vocab from them);
  minds persist PER-LIFE beside the world snapshot (a scratch town must never leak brains into the real
  one — caught in smoke); politeness-cap training threads. Engine version rides AFTER the keystone gate.

### C3. The language ratchet — schooling + biased transmission *(cross-generational culture in weights)*

- **what:** two teeth that let a town's tongue ACCUMULATE instead of resetting with every rebirth:
  **(1) schooling** — a newborn mind's *first* training is the elders' own spoken lines (source=`self`,
  oldest third of the town), harvested under the lock, trained outside it, once per life; **(2) biased
  transmission** — the sleep corpus repeats heard lines by BOND TRUST toward the speaker (trust > 0.3
  twice, > 0.6 thrice). The prestige signal is the town's own; no outside yardstick ever enters, so the
  culture stays fully self-grown.
- **validated (experiment_ratchet.py, virgin 181–185, 5/5 + 5/5):** a schooled newborn's samples carry
  5–15% real tongue-words vs **0%** for its unschooled twin; a marker word from a deeply trusted friend
  is sampled 3–15× while the equally-heard stranger's marker appears **zero times in all ten runs**.
- **the open climb:** these are the ratchet's TEETH. Whether structure *rises* across many generations
  (the Kirby iterated-learning prediction — the bottleneck should make the tongue more learnable each
  pass) is now a live-town observable: watch the speech bubbles week over week. The pooled "town tongue"
  model (one shared brain, per-soul flavour) is the escalation if the private-minds climb stalls.
- **port:** schooling = one extra bounded training call at first sleep; weighting = corpus-side only
  (no trainer changes). Both gate on the soul-minds tier existing at all.

### C4. The mouth/brain split — speak readably, learn silently *(the production voice architecture)*

- **what:** newborn char-GPTs typing `djafkl al iaiia` must not be a town's face. The split
  (services/llm.py `TownVoices` + the runner): every soul SPEAKS through its **own word-markov
  chain** (authored anchor + the lines it has lived, refreshed each time its brain sleeps — readable
  from the first breath, individual, and culture literally flows chain-to-chain as souls hear each
  other), while the per-soul GPTs become silent **brains**: they sleep, get schooled (C3), dream in
  their own growing voices, and feed the interpreter's stirring — never ambient speech. Bonus: the
  infants now train on clean sentences instead of each other's noise.
- **port:** one seam — the speech router and the learning bank are separate objects sharing soul ids.
  Seed each town's mouth differently (identically-seeded towns speak as twins; caught live).

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

### F4. Legends — gossip that mutates into myth *(§5.16 — the "the town misremembers what you did" recipe)*
- **what:** a real event (a hardship, a player's deed) outlives its witnesses as a **legend**: NPCs
  retell their *current, already-drifted* memory of it to a few nearby hearers; each copy keeps
  blurring (A1's mutation) while a provenance tag survives every retelling. Generations later, no
  witness alive, the town still tells a changed-but-traceable version — and the player can trace the
  myth back to the true event they caused. No shipped game has this; the substrate is ~60 lines.
- **knobs (validated):** retell every `25-60` ticks per NPC, to **`fanout 2`** hearers (sparse is
  LOAD-BEARING: a broadcast keeps every copy "rehearsed" and rehearsal blocks mutation → verbatim
  fossil; a fireside leaves quiet stretches to drift) · retell weight `0.5`, teller self-reinforce
  `0.15` (rehearsal ages well-told stories slowly — for free, since mutation only fires on untouched
  memories) · **communal repair with a margin**: on merging the same story, adopt the incoming text
  only if it's **≥2 words fuller** — both failure modes measured: no repair → half the legends decay
  to mush; repair-on-any-longer → verbatim fossilization, no path-dependence.
- **validated (held-out seeds, §5.16):** outlives all witnesses 5/5 (ambient murmur alone: 0/5 —
  retelling is the mechanism); changed in the telling 5/5; traceable 4/5 (the 1/5 loss is honest —
  **a myth can still die**, which for a game is drama, not a bug); converges on a canonical telling
  5/5; each seed's legend drifts differently (cross-seed overlap 0.55).
- **port:** one `lore_id` string per memory + a retell timer per NPC + the margin rule in the memory
  merge. Feed the current dominant variant to the LLM tier as "the story everyone tells" for named
  NPCs to voice in character. Quest hook for free: the discrepancy between the legend and the
  provenance-linked truth *is* a mystery plot.

### F3. The whole emergence recipe (the load-bearing idea)
> **variation** (Demiurge / mutation) + **heredity** (the wheel carries disposition) + **selection with
> self-limiting fitness** (cultural eras / faction dynamics) = structure the designer didn't script, different
> every run. Missing any one: variation alone = drift; selection alone = a frozen monoculture; no self-limiting
> = it freezes on the first winner.

---

### F5. Emotional weather — mood is spatially real *(§5.24 — the ambient-mood recipe)*

- **what:** speech is distance-bound, hearing moves the hearer's mood, and roaming braids
  bonded souls into space — so mood develops REAL spatial structure: warm fronts in some
  towns, checkerboards (neighbours feeling opposite) in others. Verdict W1 5/5 on virgin
  seeds; forms fast and persists (W2's slow-condensing claim failed honestly, 3/5).
- **port:** the channel must actually be OPEN (the v1 harness had speech off and measured
  nothing — a lesson worth porting as a checklist item); the sign of a town's weather is
  emergent, not settable. Render as an ambient mood-heat layer only after replicating W1
  in-engine. Bonus finding for designers: mood ANTI-tracks wellbeing (−0.34) — comfort
  breeds clinging, suffering attracts warmth; don't "fix" it, it is the theme.

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
- **Introspection tracks VALENCE, not MECHANISM (§5.19 C15, held-out).** Perturb the substrate and
  self-reports follow — a dark injection turns reports grey (6/10 vs sham 0/10), bright stays warm
  (10/10 vs dark 1/10), direction-specific — **but only through the ground pathway** (ground off →
  the channel closes; reports track memory *content*). And in ~70 grip-spiked reflections across seven
  rounds, the report NEVER read as "holding" — the grip is felt as weather, never as hands. Don't
  expect NPC self-reports to explain their own mechanisms; do expect them to track how things feel.

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
