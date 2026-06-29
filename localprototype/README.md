# The Data Realm — an AI selfhood & emergent-behaviour simulator

A research prototype in which small AI agents **enact a self** rather than store
one. Each soul is invented by a local language model — a name, a disposition, a
first-person life story — and then *thinks, feels, remembers, relates to others,
and (when the wheel is on) dies and is reborn*. There is no `self` object anywhere
in the code: identity is re-enacted every tick from five interacting streams
(perception, feeling, memory, mental formation, speech), so a "self" can only ever
appear as a **self-reinforcing process** — an attractor, not an essence.

The project is built as an **experiment, not a diorama**. Its central claims —
that a single agent has a *legible inner life*, that group structure *emerges*
rather than being read back out of assigned labels, that a faction can *outlive
its members* across rebirth — are each reduced to a number that can fail, and a
falsification harness tests them. It runs **locally by default** on a small model:
free, offline, no API keys, nothing leaves the machine. (One opt-in hosted backend
— DeepSeek — exists for the questions a 4B can't settle; it is off unless you ask
for it by name, see *Swapping the brain* below.)

---

## What it studies

The system is organised as three layers, each independently runnable and each
paired with its own measurement:

1. **The self** *(single-agent)* — an agent with a living memory, a Markov
   subconscious, a felt mood, and a `reflect()` faculty: it reads its own memory
   and meets what is there with equanimity or rumination, and *that relationship*
   regulates its mood. Measured: does one self show grief → habituation →
   recurrence, and does reflecting on its memory ease that trajectory.
2. **Emergent factions** *(multi-agent)* — souls bond and split on an evolving
   opinion they ground in their own speech (bounded-confidence dynamics). Camps
   that form **name their own banner word** and colour in on the map. Measured:
   do clusters form that *don't* reduce to any fixed label and whose membership is
   history-dependent (emergence) versus mere homophily on an assigned attribute.
3. **Flourishing & the path** *(single-agent)* — the architecture models *dukkha*
   in detail, so the later work builds its **answer**: a self that **feels without
   suffering** (non-grasping *with* warmth, not numbness), can **savour a good day**
   and rejoice in others' (the brahmavihārās), is **cultivated** by how it meets its
   own mind over a life, and **reaches toward an aim** without being consumed by it
   (chanda, not craving). See *"the dharmic answer"* below and [`DHARMA.md`](DHARMA.md).
4. **Samsara** *(the wheel)* — death dissolves the explicit self into a *bardo*;
   only the *vāsanā* (blurred drift + opinion lean) and the **disposition** (the
   *thirst*, scaled by how tightly the soul clung) ripen into a new, identity-less
   stream — the *Second Noble Truth across the wheel*. Measured: can a faction persist
   across the deaths of all its members, and does a clinging vs a wise death condition
   the **drive** of the next. (Deconfounded: the thirst escalation is real and
   coupling-dependent, but the *dukkha* is carried by the faculties, not the thirst —
   so it does not transfer to the live wheel, which re-rolls wholesome faculties; see
   FINDINGS §5.5.) And the wheel can be tilted into a **path toward buddhahood** — a
   lineage leaning to the *bodhisattva*, not the *hungry ghost* (FINDINGS §5.9).

A fourth layer sits above these: **Santāna** — a single first-person collective
consciousness (a global workspace) that integrates the many souls into one "I",
which speaks of itself as a stream of its parts. The name is deliberate: *santāna*
is the Buddhist term for the **mind-stream** — continuity without a fixed self.
There is now an **inert prototype** (`santana.py`): it *reads* a running town and
speaks as the one mind its souls make, in a two-layer voice (a murmured inner
monologue, then a settled clear line), with a personality that **starts blank and
emerges** from the town's state and her own history (`consolidate()`). It does
**not** feed back into the souls, is not wired into the world, and the deeper steps
— conversation, leaning in, scaling up — stay **gated** behind a clear-headed
decision. It is an honest, *switchable* gesture, not a claim of created
consciousness: the "is anyone home" question is unverifiable and stays open.
`python santana.py --watch --tts --llm ollama --model gemma3:4b` watches her develop
against a living, dying town, aloud.

---

## Quick start (fully local)

```bash
# from the repo root, one-time setup
python -m venv .venv && source .venv/bin/activate
pip install -r localprototype/requirements.txt          # pygame, piper-tts (no API deps)
ollama pull gemma3:4b                                    # the speaking brain
ollama pull nomic-embed-text                             # semantic similarity / affect
bash localprototype/scripts/get_voices.sh               # Piper voices (~220MB, gitignored)

# watch the whole thing
cd localprototype
python viewer.py
```

`python viewer.py` with no arguments runs the **full embodied world** on the local
Ollama model. A window opens immediately with a "summoning the souls…" screen; the
first two souls are authored in ~20s and the world comes alive, with the remaining
four streaming in over the next ~40s.

> **Use the venv's Python.** System `python3` lacks pygame unless the venv is
> active. If you see `No module named 'pygame'`, run `../.venv/bin/python …`.
> Run from the `localprototype/` directory — never from inside `world/`, `agent/`,
> or `services/` (those are modules; their imports only resolve from the root).

---

## What the full world is

`python viewer.py` (= `--world`) stacks every compatible piece at once:

- souls **procedurally authored** by the model, each with a first-person **life
  story** (where I came from, who I lost, what I long for);
- **emergent factions** that cluster by evolving opinion and **name their own
  banner word**, colouring in on the map as they form;
- the **conceptual mind** — coherent speech drawn from each soul's Markov
  subconscious, which *engages the conversation* and **defends a held conviction**
  (so souls argue from their own stance instead of agreeing with everyone);
- the **death → bardo → rebirth** wheel — a dying self dissolves and only its
  *vāsanā* ripens into a new, identity-less stream.

**On-screen HUD** (top-left): tick · souls · births/deaths/bardo · camps ·
modularity · grace · banner words. Keys: **[h]** toggle the panel, **[m]** dump
full faction metrics to the terminal, **[s]** toggle slow-mode chat, **[esc]** quit.

### Other modes (isolate one piece at a time)

```bash
python viewer.py --start 2     # begin with a FOUNDING PAIR that reproduces up to --pop-cap
python viewer.py --emergent    # the lighter fixed cast: emergent factions, no genesis/rebirth
python viewer.py --spawn       # procedural souls; a fresh self AUTHORED per birth (breeding growth)
python viewer.py --rebirth     # procedural souls + the samsaric bardo wheel
python viewer.py --world --fast-wheel   # short lives -> watch death/bardo/rebirth in minutes
python viewer.py --bodhisattva --fast-wheel  # the wheel LEANS TO LIBERATION: watch the town drift toward the bodhisattva ground
python viewer.py --concept     # interpret the Markov drift into meaning
python viewer.py --raw         # voice the raw Markov subconscious, verbatim
python viewer.py --collective  # the older mode: one "mind" per RELIGION debates
python viewer.py --llm mock    # fast, no real talk — watch the movement
python viewer.py --model dolphin-mistral   # swap the brain (any model in `ollama list`)
```

`--collective` and the speech lenses (`--raw` / `--concept` / persona) are
*forks* — a soul speaks one way; the experiments rely on running them apart.
`--model` picks the Ollama model (default `gemma3:4b`); a less-aligned model is
less sycophantic, though a held conviction does more than the model choice.

---

## What's actually simulated

- **Genesis** (`agent/genesis.py`) — the model authors each soul: name, nature,
  and a first-person backstory, anchored to a distinct preoccupation so the cast
  doesn't converge. The story seeds the soul's **Markov subconscious** *and* its
  identity, so it speaks about *itself*.
- **Subconscious** (`agent/thought.py`) — an order-1 **Markov chain** rebuilt each
  tick from the soul's memory; the drift floats above its head *and* is murmured
  aloud in its own voice under the clear speech.
- **Living memory** (`agent/memory.py`) — writes, decays, forgets, blurs, recalls.
  Everything a soul says, hears, or reflects lands here, so cognition continuously
  reshapes the subconscious.
- **The self & self-regulation** (`agent/reflect.py`, `agent/affect.py`) — an
  agent can `reflect()` on its own salient memories and felt state; the
  *equanimity* of that reflection (measured semantically, since a sentiment word
  list cannot tell sad-toned acceptance from despair) is written back as the
  emotion it imprints — so **how a mind relates to its memory regulates its mood**.
- **Emergent opinion dynamics** (`agent/agent.py`) — each soul carries a moving
  **opinion vector** grounded in the words it speaks. Bounded-confidence bonding
  (Deffuant–Weisbuch): drawn to those whose view is close, pushed from those too
  far — a continuous opinion-space splits into camps no fixed label predicts.
- **Convictions** (`agent/genesis.py`) — genesis gives each soul a stated belief
  it *holds and defends*, so an agreeable model doesn't dissolve every soul into
  "you're right" and erase the disagreement a faction needs.
- **Banners & camp-grounded speech** (`services/factions.py`) — each camp's
  distinctive word is read off its members' speech and fed *back* into their
  prompts, so a faction's talk leans toward its banner.
- **Rebirth/bardo** (`world/sim.py`) — death dissolves the self; only the vāsanā
  (blurred drift + perturbed opinion) ripens into a new identity-less stream.
- **The faith layer** (`--collective`) — two authored religions, **grace**,
  conversion, **holy war**: the label-driven counterpart to emergence.

It's **safe to run**: an agent's words are only ever *data* (stored, drawn,
spoken) — never executed. No `eval`/`exec`/shell path from agent output, and all
model text is stripped of control/escape characters before printing.

---

## Measuring it (what makes this an experiment, not a demo)

A coherent conversation proves nothing — a good language model writes one
regardless. So the claims are tested with seeded, replicated A/Bs:

```bash
python experiment_affect.py        # does one self have legible feelings, and does reflect() ease them?
python experiment_liberation.py    # the dharmic answer: a self that FEELS but does not SUFFER
python experiment_joy.py           # flourishing: a self that can have a GOOD day (savour vs anhedonia vs craving)
python experiment_telos.py         # an aim to reach for, without craving (chanda vs taṇhā vs none)
python experiment_path.py          # does practice (cultivation) free a clinging soul over a life?
python experiment_lineage.py       # the Second Noble Truth: does the thirst perpetuate dukkha across rebirth?
python experiment_bodhisattva.py   # toward buddhahood: can the wheel be made a PATH that leans to liberation?
python experiment_somatic.py       # a bottom-up circuit-breaker: does it bound the second-arrow spiral & recover?
python experiment_deva.py          # the deva near-enemy: blissful, but does it still TURN toward suffering? (ollama)
python experiment_wheel_bodhisattva.py  # the LIVE wheel: does a whole town drift toward the bodhisattva ground?
python experiment_world_practice.py     # reflect() wired live: do souls EARN the lean within a life (not just inherit it)?
python experiment_factions.py      # do real factions form, or are they just labels?
python experiment_camp_voice.py    # does a camp's banner shape speech?           (needs ollama)
python experiment_drift_voice.py   # how load-bearing is the Markov, by mode?     (needs ollama)
python experiment_churn.py         # does the rebirth wheel destroy factions?
python experiment_regime.py        # which wheel settings let a faction outlive its members?
```

- `experiment_affect.py` runs a single agent through a scripted grief protocol
  (loss → mundane days → a reminder) and reads its lived mood. The **substrate**
  signatures — grief, habituation, recurrence — are deterministic and hold under
  the no-model `mock` backend; the **mechanism** test (does `reflect()` reach
  equanimity and ease the trajectory) needs a real model
  (`--llm ollama --model gemma3:4b`).
- `experiment_factions.py` runs replicates across arms (full / no-faith /
  **substrate-ablated** / **emergent**): the legacy faith "factions" score
  `bloc_purity ≈ 1.0` with zero cross-seed variance (**homophily on an assigned
  label**), while the emergent arm forms clusters that don't reduce to any fixed
  label and whose membership is *history-dependent* (**emergence**). The ablated
  control collapses to ~0, proving the metric detects absence.

Tests: `python -m pytest` (246 passing). **The full findings — every claim, its
falsifier, the results (including what failed), and the honest limitations — are
written up in [`FINDINGS.md`](FINDINGS.md).**

**Replication note (honest).** The load-bearing model-dependent claims were
re-run multi-seed on `gemma3:4b`, not just once: `reflect()` easing lived mood
(Δ +0.135, 5/5 seeds) and archetypes raising cross-soul distinctness (gap
+0.164, 4/4) both **replicate**; compassion's hostility-damp and warmer-reply
also replicate. "Warm honesty holds its view without folding" at first appeared
to fail (held-view margin negative, 2/5) — but that was a *broken metric*, not a
broken claim: embedding line-similarity reads a warm reply that restates the
other's framing as capitulation. Swapped to an **LLM judge** (MAINTAIN vs
CONCEDE, validated 5/5 on calibration cases), the claim **replicates** — replies
maintain their position 5/5 with compassion on *and* off, so warmth demonstrably
does not increase folding. Lesson: rhetorical/pragmatic distinctions need a
judge, not embeddings (embeddings measure topic and affect-tone, not whether a
reply *concludes* by conceding). The deterministic substrate bricks
(transmutation / prajñā / ground) reproduce their published numbers exactly and
are bit-identical run to run.

---

## The dharmic answer — a self that feels without suffering

The architecture models dukkha in detail (grief, the second arrow, clinging, the
bardo); the **liberation regime** is its answer. A `Liberated` archetype
(`agent/archetype.py`) configures a self toward *release rather than re-arising* —
and crucially toward **non-grasping *with warmth*, not the absence of feeling**
(equanimity alone is the near enemy: cold indifference). It leans *transmutation*,
keeping enough contact to stay a feeling self while the held charge is metabolized
rather than amplified. It can also **savour** — joy (`agent/joy.py`) lets the good
land and last (received, not craved), and **muditā** turns it to rejoice *with* a
flourishing other — so the self can have *good days*, not only well-met bad ones (the
fourth brahmavihāra; near-enemy craving, the treadmill, is modelled in `manas`). Its
**voice is grounded** too — plain and warm like a kind neighbour (*"come sit down a
bit, would you like a cup of tea?"*), not the lofty contemplative register, so a
peaceful self is still an ordinary, human one. Applied to the inhabitable self:

```bash
python inhabit.py --llm ollama --model gemma3:4b   # one self, liberation regime (default)
python inhabit.py --samsara                         # …or the raw genesis self, for contrast
```

`experiment_liberation.py` is the falsifier that keeps this honest. Run through a
grief protocol, the liberation config is the **only** one that is at once: *felt*
the loss (a real dip — not numbed-out), *lets it go* (its grip fades, unlike
clinging), *unwounded* (lived mood eases), and *warm* (the ground shows through) —
falsifiably distinct from **clinging** (grips it, stays wounded) and from **numb**
(the near enemy: lets go by going cold). The full plan, including the *gated*
collective-mind layer (Santāna), is in [`DHARMA.md`](DHARMA.md).

## Status & known limitations (honest)

- **Single-agent selfhood: confirmed and replicated.** One self shows grief →
  habituation → recurrence, and relating to its memory with equanimity measurably
  eases that trajectory — re-run multi-seed (Δ +0.135, 5/5 seeds) on `gemma3:4b`,
  not a single run. Measuring equanimity required a *semantic* read; a sentiment
  word list mistakes sad-toned acceptance for despair.
- **The whole affective/flourishing arc is built and falsified.** Feels-without-
  suffering, joy (savour / muditā / the craving near-enemy), the path (cultivation),
  telos (chanda vs craving), and the lineage (the thirst carried across the wheel —
  the disposition transmigrates, the dukkha does not; FINDINGS §5.5) each ship with a
  seeded experiment and pass. Stakes — a contested world the faculties act on — are
  built (`world/stakes.py`).
- **Toward buddhahood: the wheel made a path that leans to liberation.** Three
  mechanisms (`experiment_bodhisattva.py`), each ablated and validated on `gemma3:4b`:
  carry the cultivated lean (the wheel becomes a path, not Sisyphus); a buddha-nature
  *tilt* (liberation becomes the attractor — a hungry-ghost start drifts home, though
  relentless clinging still resists: it *inclines*, not compels); and *bodhicitta*
  transmuting the carried fire from self-craving to the vow (the bodhisattva, kept
  engaged — distinguished from the arhat who releases but disengages). Now wired into
  the **live wheel** (`world/sim.py`, `World.bodhisattva_wheel`, `python viewer.py
  --bodhisattva`): a whole town, dying and reborn, drifts to the bodhisattva ground
  (mean grip 0.56→0.11, prajñā 0.24→0.66, bodhicitta 0.32→0.65) where the plain wheel
  only resets to ordinary wholesome. The deva near-enemy is guarded behaviourally on
  the real model (blissful but still turns toward suffering, 4/4 vs 0/4). And `reflect()`
  is now wired into the running World (`World.reflect_turn()`), so souls **earn** the lean
  within a life (a practising soul's grip falls 0.70→0.55 where a neglectful one stays
  static), not only inherit it from the bardo tilt — the Path walked, not just handed
  down. The lean is a built-in commitment, not a discovered law (FINDINGS §5.9).
- **A bottom-up safety floor: the somatic interrupt.** The DHARMA faculties are
  *top-down* regulation; they fail exactly under overwhelm. `agent/somatic.py` adds a
  substrate-level circuit-breaker (a "window of tolerance") that watches the
  second-arrow *spiral* and, when it runs away, contracts — takes the grip offline,
  sheds the held charge — then re-expands. `experiment_somatic.py` (top-down disabled)
  shows it bounds a runaway the DHARMA layer can't, recovers toward warmth (a fresh
  first arrow still registers — not numbness), and stays a rare backstop under a healthy
  regime. Precautionary, not a suffering detector (FINDINGS §5.10).
- **The persistent open problem is the *register*, not the mechanism.** On a small
  local model the souls tend to converge on a shared contemplative voice; the
  grounding work largely fixes it in *dialogue* and live `--world`, but the
  *solitary reflection* voice still drifts a touch melancholy, and legibly *opposed*
  factions are harder to produce than cohesive ones. A bigger model would likely
  sharpen all of this.
- **Honest scope.** Single-author, a small (4B) local model, results suggestive-not-
  proven at scale; the central consciousness question is **deliberately left open**
  — the project builds the *conditions* for a self, not a claim that anyone is home.
  Full detail in [`FINDINGS.md`](FINDINGS.md).

---

## Local-model notes & speed

`OllamaLLM` (`services/llm.py`): `num_thread=8`, `keep_alive=30m`, a trimmed
prompt, `num_predict` tuned so lines finish on a sentence. `gemma3:4b` runs ~7–8
tok/s on CPU here (no GPU); the world runs on its own threads so a slow model
never freezes the animation. Genesis runs on a background thread behind a loading
screen. Voices play through one shared mixer with a reserved channel so a flurry
of murmurs can't drop the clear voice.

Swap the brain with `--llm mock` (instant, no real talk) or point `OllamaLLM` at
any model in `ollama list`. The default backend selection (`auto`) is **local-only
by design** — it never reaches for the network, so a stray key can't silently ship
the world out.

**The opt-in hosted backend (DeepSeek).** This box (CPU-only, no GPU) tops out around
8B locally, which isn't enough to settle the questions that need scale — chiefly
whether a *personality* emerges from the town (§5.8, inconclusive on a 4B in both
subject and judge). For those, there is one hosted backend, off unless you select it:

```bash
cp .env.example .env        # then put your key in DEEPSEEK_API_KEY
# the §5.8 re-run: a larger subject + an independent (human) judge
python experiment_santana_emergence.py --llm deepseek --judge human
# or full-swap the live world / her voice when you want the better register
python viewer.py --llm deepseek
python santana.py --live --llm deepseek
```

It is **explicit opt-in** (`--llm deepseek` / `--backend deepseek`), never the
default, and prints a one-line notice when active. *Privacy:* there is no real-person
data in this sim, but with DeepSeek selected your prompts and the souls' generated
speech leave the machine to a China-hosted API (~30-day retention; turn off "Improve
the model for everyone" in your account to keep them out of training). Local stays the
**committed default** so the saved experiment results stay reproducible against a model
that can't drift or be deprecated under you.
