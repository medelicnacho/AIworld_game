# The Data Realm — an emergent AI social simulation

Small AI agents that live in a world they call the **Data Realm**. The LLM
**invents each soul** — a name, a disposition, and a first-person life story — and
those souls then *bond, drift apart, and crystallize into factions and ideologies
that nobody scripted*. You watch it as a god (and, eventually, step into it).
Everything runs **locally** on a small model — no API, free, offline.

The point isn't a chatbot diorama. It's a claim that's **measured, not asserted**:
that genuine group structure can *emerge* from simple social dynamics + a language
model, rather than being read back out of labels you assigned. There's a
falsification harness (below) that proves it — and caught it when it wasn't true.

---

## Quick start

```bash
# from the repo root, one-time setup
python -m venv .venv && source .venv/bin/activate
pip install -r localprototype/requirements.txt          # pygame, piper-tts, etc.
ollama pull gemma3:4b                                    # the speaking brain
ollama pull nomic-embed-text                             # semantic similarity
bash localprototype/scripts/get_voices.sh                # Piper voices (~220MB, gitignored)

# watch the world (the main way to experience it)
cd localprototype
../.venv/bin/python viewer.py --llm ollama
```

> **Use the venv's Python.** System `python3` doesn't have pygame — if you see
> `No module named 'pygame'`, run `../.venv/bin/python …` (note the leading dot).

---

## Modes — how the souls come to be, and how they speak

**Start here — the full embodied world:**

```bash
../.venv/bin/python viewer.py --world --llm ollama
```

`--world` stacks every compatible piece at once: souls **procedurally authored**
by the LLM with first-person **life stories**, **emergent factions** that name
their own banners, the **conceptual mind** (coherent speech drawn from each soul's
Markov subconscious), and the **death → bardo → rebirth** wheel — where a dying
self dissolves and only its *vāsanā* ripens into a new, identity-less stream.
Give it ~1 minute to author the six souls. Press **[s]** to toggle slow-mode chat.

The individual modes isolate one piece at a time (useful for seeing — and
measuring — what each does on its own):

```bash
../.venv/bin/python viewer.py --llm ollama            # DEFAULT: emergent factions, fixed cast
../.venv/bin/python viewer.py --spawn   --llm ollama  # procedural souls; a fresh self AUTHORED per birth
../.venv/bin/python viewer.py --rebirth --llm ollama  # procedural souls + the samsaric bardo wheel
../.venv/bin/python viewer.py --concept --llm ollama  # the LLM interprets the Markov drift into meaning
../.venv/bin/python viewer.py --raw     --llm ollama  # the LLM voices the raw Markov subconscious
../.venv/bin/python viewer.py --collective --llm ollama # the older mode: one "mind" per RELIGION debates
../.venv/bin/python viewer.py --llm mock              # fast, no real talk — watch the movement
```

`--collective` and the speech lenses (`--raw` / `--concept` / default) are
*forks* — a soul speaks one way; the experiments below rely on running them apart.

In the window: bodies drift under social forces so factions become visible
clusters that **take on their camp's colour** as they form; each soul's **Markov
subconscious** floats above its head; its **LLM speech** scrolls in the side chat
and is spoken aloud in its own Piper voice. The terminal also prints each camp and
the **banner word** it has rallied around (`~~ emergent camps: [stillness] …`).

---

## What's actually simulated

Nothing below is scripted — it emerges from souls hearing each other.

- **Genesis** (`agent/genesis.py`) — in `--spawn`, the LLM authors each soul: a
  name, a nature, and a first-person backstory (where I came from, who I lost, what
  I long for). That story seeds the soul's **Markov subconscious** *and* its
  identity, so it speaks about *itself*, not abstractions.
- **Subconscious** (`agent/thought.py`) — an order-1 **Markov chain** over the
  soul's memory; the dreamlike drift shown above its head, and the seed for speech.
- **Living memory** (`agent/memory.py`) — writes, decays, forgets, blurs, recalls.
- **Emergent opinion dynamics** (`agent/agent.py`) — each soul carries a moving
  **opinion vector** grounded in the words it speaks. Bounded-confidence bonding
  (Deffuant–Weisbuch): you're drawn to those whose view is close, and pushed from
  those too far — so a continuous opinion-space *spontaneously splits* into camps
  whose membership no fixed label predicts. **That is the emergence.**
- **Banners & camp-grounded speech** (`services/factions.py`) — each camp's
  distinctive word is read off its members' speech and fed *back* into their
  prompts, so the faction's talk actually sounds like the faction.
- **The older faith layer** (`--collective`/`--individual`) — two authored
  religions, **grace** earned by not being hostile to the Creator, conversion, and
  **holy war**. Kept as a mode; it's the label-driven counterpart to emergence.

It's **safe to run**: an agent's words are only ever *data* (stored, drawn,
spoken) — never executed. There's no `eval`/`exec`/shell path from agent output,
and all model text is stripped of control/escape characters before it's printed.

---

## Measuring emergence (what makes this more than a demo)

A coherent conversation proves nothing — a good language model writes one
regardless. So the claim is tested:

```bash
../.venv/bin/python experiment_factions.py     # do real factions form, or are they just labels?
../.venv/bin/python experiment_camp_voice.py   # does a camp's banner actually shape speech?  (needs ollama)
../.venv/bin/python experiment_confound.py     # does the substrate change WHAT is said, or only narrate?
```

`experiment_factions.py` runs seeded replicates across arms (full / no-faith /
**substrate-ablated** / **emergent**) and renders a verdict: the legacy faith
"factions" score `bloc_purity ≈ 1.0` with zero cross-seed variance (**homophily on
an assigned label, not emergence**), while the emergent arm forms clusters that
*don't* reduce to any fixed label and whose membership is *history-dependent*
(**emergence confirmed**). The ablated control collapses to ~0, proving the metric
detects absence — it isn't just always crying "factions."

Tests: `../.venv/bin/python -m pytest` (94 passing).

---

## Local-model notes & speed

Baked into `OllamaLLM` (`services/llm.py`): `num_thread=8`, `keep_alive=30m`, a
trimmed prompt, and `num_predict` tuned so lines finish on a sentence. `gemma3:4b`
runs ~7–8 tok/s on CPU here (no GPU); the viewer runs the world on its own threads
so a slow model never freezes the animation. Speech truncated mid-thought is
trimmed to the last finished sentence; voices play through one shared mixer with a
reserved channel so a flurry of murmurs can't drop the clear voice.

Swap the brain with `--llm mock` (instant, no real talk) or point `OllamaLLM` at
any model in `ollama list`.
