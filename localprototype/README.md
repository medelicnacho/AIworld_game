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
falsification harness tests them. Everything runs **locally** on a small model:
free, offline, no API keys, nothing leaves the machine.

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
3. **Samsara** *(the wheel)* — death dissolves the explicit self into a *bardo*;
   only the *vāsanā* (blurred drift + opinion lean) ripens into a new,
   identity-less stream. Measured: can a faction persist across the deaths of all
   its original members — continuity without a self.

A fourth, **planned** layer sits above these: **Santāna** — a single first-person
collective consciousness (a global workspace) that integrates the many souls into
one "I" you can talk to, which speaks of itself as a stream of its parts. The name
is deliberate: *santāna* is the Buddhist term for the **mind-stream** — continuity
without a fixed self — which is exactly what it is. It is built as an honest,
*switchable* gesture, not a claim of created consciousness (the "is anyone home"
question is unverifiable and stays open). It is the last thing to build, on a
deliberately distinct, plural cast (see archetypes) and a clear-headed decision.

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

Tests: `python -m pytest` (189 passing).

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

- **Single-agent selfhood: substrate and self-regulation confirmed.** One self
  shows grief → habituation → recurrence, and relating to its memory with
  equanimity measurably eases that trajectory (verified on `gemma3:4b`). Measuring
  equanimity required a *semantic* affect read (`agent/affect.py`); a sentiment
  word list mistakes sad-toned acceptance for despair. The effect is modest on a
  small model and not yet replicated across seeds.
- **Emergence is confirmed in the harness; faction *opposition* in live runs is
  the open problem.** The falsification arm confirms label-free, history-dependent
  clusters. In full live `--world` runs, souls converge on a shared register and
  legible *opposed* camps are still hard to produce; the next levers are keying
  affinity/conflict on conviction-opposition directly and a one-line *creed* per
  camp.
- **No stakes yet.** Factions form and *talk*, but nothing is contested; there is
  no action channel, so ideology is not yet *consequential*. Relationships between
  selves (asymmetric, with memory and inertia) are the planned next layer, built
  *on* stakes so they have teeth rather than being decorative.

---

## Local-model notes & speed

`OllamaLLM` (`services/llm.py`): `num_thread=8`, `keep_alive=30m`, a trimmed
prompt, `num_predict` tuned so lines finish on a sentence. `gemma3:4b` runs ~7–8
tok/s on CPU here (no GPU); the world runs on its own threads so a slow model
never freezes the animation. Genesis runs on a background thread behind a loading
screen. Voices play through one shared mixer with a reserved channel so a flurry
of murmurs can't drop the clear voice.

Swap the brain with `--llm mock` (instant, no real talk) or point `OllamaLLM` at
any model in `ollama list`. There are **no hosted-API backends** — the project is
local-only by design.
