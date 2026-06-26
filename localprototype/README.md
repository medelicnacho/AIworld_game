# The Data Realm — an emergent AI social simulation

Small AI agents that live in a world they call the **Data Realm**. The LLM
**invents each soul** — a name, a disposition, and a first-person life story — and
those souls then *bond, drift apart, and (sometimes) crystallize into factions
that nobody scripted*. You watch it as a god, with the dynamics quantified live on
screen. Everything runs **locally** on a small model — no API, free, offline.

The point isn't a chatbot diorama. It's a claim held to a standard: **measured,
not asserted** — that genuine group structure can *emerge* from simple social
dynamics + a language model rather than being read back out of labels you
assigned. A falsification harness (below) tests that claim, and has caught it
both when it held and when it didn't.

---

## Quick start

```bash
# from the repo root, one-time setup
python -m venv .venv && source .venv/bin/activate
pip install -r localprototype/requirements.txt          # pygame, piper-tts, etc.
ollama pull gemma3:4b                                    # the speaking brain
ollama pull nomic-embed-text                             # semantic similarity
bash localprototype/scripts/get_voices.sh                # Piper voices (~220MB, gitignored)

# watch the whole thing
cd localprototype
python viewer.py
```

`python viewer.py` with no arguments runs the **full embodied world** (and ollama
is the default backend). A window opens immediately with a "summoning the souls…"
screen; the first two souls are authored in ~20s and the world comes alive, with
the remaining four streaming in live over the next ~40s.

> **Use the venv's Python.** System `python3` lacks pygame unless the venv is
> active. If you see `No module named 'pygame'`, run `../.venv/bin/python …`.
> Run from the `localprototype/` directory — never from inside `world/`, `agent/`,
> or `services/` (those are modules; their imports only resolve from the root).

---

## What the full world is

`python viewer.py` (= `--world`) stacks every compatible piece at once:

- souls **procedurally authored** by the LLM, each with a first-person **life
  story** (where I came from, who I lost, what I long for);
- **emergent factions** that cluster by evolving opinion and **name their own
  banner word**, colouring in on the map as they form;
- the **conceptual mind** — coherent speech drawn from each soul's Markov
  subconscious;
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
```

`--collective` and the speech lenses (`--raw` / `--concept` / persona) are
*forks* — a soul speaks one way; the experiments rely on running them apart.

---

## What's actually simulated

- **Genesis** (`agent/genesis.py`) — the LLM authors each soul: name, nature, and
  a first-person backstory, anchored to a distinct preoccupation so the cast
  doesn't converge. The story seeds the soul's **Markov subconscious** *and* its
  identity, so it speaks about *itself*.
- **Subconscious** (`agent/thought.py`) — an order-1 **Markov chain** rebuilt each
  tick from the soul's memory; the drift floats above its head *and* is murmured
  aloud in its own voice (the actual fragment, synthesized on demand) under the
  clear speech.
- **Living memory** (`agent/memory.py`) — writes, decays, forgets, blurs, recalls.
  Everything a soul says or hears lands here, so speech continuously reshapes the
  subconscious (measured: ~⅓ of the Markov's material is lived conversation).
- **Emergent opinion dynamics** (`agent/agent.py`) — each soul carries a moving
  **opinion vector** grounded in the words it speaks. Bounded-confidence bonding
  (Deffuant–Weisbuch): drawn to those whose view is close, pushed from those too
  far — a continuous opinion-space splits into camps no fixed label predicts.
- **Banners & camp-grounded speech** (`services/factions.py`) — each camp's
  distinctive word is read off its members' speech and fed *back* into their
  prompts (measured effect ~+0.11), so a faction's talk leans toward its banner.
- **Rebirth/bardo** (`world/sim.py`) — death dissolves the self; only the vāsanā
  (blurred drift + perturbed opinion) ripens into a new identity-less stream.
- **The older faith layer** (`--collective`) — two authored religions, **grace**,
  conversion, **holy war**: the label-driven counterpart to emergence.

It's **safe to run**: an agent's words are only ever *data* (stored, drawn,
spoken) — never executed. No `eval`/`exec`/shell path from agent output, and all
model text is stripped of control/escape characters before printing.

---

## Measuring it (what makes this more than a demo)

A coherent conversation proves nothing — a good language model writes one
regardless. So the claims are tested with seeded, replicated A/Bs:

```bash
python experiment_factions.py      # do real factions form, or are they just labels?
python experiment_camp_voice.py    # does a camp's banner shape speech?           (needs ollama)
python experiment_drift_voice.py   # how load-bearing is the Markov, by mode?     (needs ollama)
python experiment_confound.py      # does the substrate change WHAT is said?      (ollama for signal)
python experiment_belief.py        # does a held belief change behaviour vs reality? (ollama)
```

`experiment_factions.py` runs replicates across arms (full / no-faith /
**substrate-ablated** / **emergent**): the legacy faith "factions" score
`bloc_purity ≈ 1.0` with zero cross-seed variance (**homophily on an assigned
label**), while the emergent arm forms clusters that don't reduce to any fixed
label and whose membership is *history-dependent* (**emergence**). The ablated
control collapses to ~0, proving the metric detects absence.

Tests: `python -m pytest` (99 passing).

---

## Status & known limitations (honest)

- **Emergence is confirmed in the harness; live runs were prone to consensus
  collapse, now mitigated.** The falsification arm confirms label-free,
  history-dependent clusters. Long live `--world` runs used to **collapse into one
  camp with a filler-word banner** ("sense", "yearning") because the concept voice
  homogenizes everyone's register and the lexical opinion space converged. Two
  fixes are in: the introspective register is filtered out of the opinion vector
  (so it keys on distinctive *content*), and bonding has an **individuation** term
  so souls hold their distinctness instead of collapsing into clones. A *semantic*
  opinion space and a one-line *creed* (instead of a single banner word) are the
  next, deeper improvements — and the live as-shipped config still needs a long
  run to *prove* it holds.
- **No stakes yet.** Factions form and *talk*, but nothing is contested; there is
  no action channel, so ideology is not yet *consequential*. This is the next
  frontier.

---

## Local-model notes & speed

`OllamaLLM` (`services/llm.py`): `num_thread=8`, `keep_alive=30m`, a trimmed
prompt, `num_predict` tuned so lines finish on a sentence. `gemma3:4b` runs ~7–8
tok/s on CPU here (no GPU); the world runs on its own threads so a slow model
never freezes the animation. Genesis runs on a background thread behind a loading
screen. Voices play through one shared mixer with a reserved channel so a flurry
of murmurs can't drop the clear voice.

Swap the brain with `--llm mock` (instant, no real talk) or point `OllamaLLM` at
any model in `ollama list`.
