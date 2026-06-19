# Prototype

Builds the AI world bottom-up. Pure Python stdlib — **no pip dependencies** (the
LLM is reached over HTTP via `urllib`). The 3D layer (**Panda3D**, decided) plugs
into this engine-agnostic core later by subscribing to the `EventBus`.

## Milestones

- **M1 ✅ Headless core loop** — `utterance → heard → memory → influence`, with
  memory that decays, blurs/forgets, reinforces. No LLM/TTS/3D.
- **M2 ✅ Subconscious + local LLM** — a Markov drift over each agent's memory
  feeds a local LLM (Ollama) that actually *talks* and replies to whoever spoke.
- M3 ⬜ TTS (Piper) → AI speech becomes audio-only; hide debug text.
- M4 ⬜ Panda3D world; renderer subscribes to the EventBus.

## Run

```bash
cd prototype
python3 main.py --backend mock              # instant, no model (wiring demo)
python3 main.py                             # auto-detect Ollama
python3 main.py --backend ollama --ticks 20
python3 main.py --model dolphin-mistral:latest --ticks 20
python3 main.py --think                     # also print memory mutation/forget
```

Requires [Ollama](https://ollama.com) running locally for real speech
(`ollama serve`), with a model pulled. Default model:
`mannix/llama3.1-8b-abliterated:q5_K_M`. Without Ollama it falls back to a
`MockLLM` so the sim always runs.

## What you're watching (M2)

Three agents — **River** (watery, melancholic), **Ash** (burnt-out, wry),
**Moth** (restless, drawn to light) — think and talk. Each tick:

1. **Subconscious** (`agent/thought.py`): a Markov chain over the agent's memory
   (transitions weighted by salience) drifts out short fragments.
2. **Speech** (`services/llm.py`): on its turn, the agent packs drift + recalled
   memories + whoever just spoke into a `SpeechContext` and the LLM replies in
   one or two spoken sentences.
3. **Hearing**: the utterance is written into listeners' memory → reshapes their
   future drift. Memory keeps decaying, blurring, forgetting underneath.

Example (llama3.1-8b):

```
River:        The darkness pulls me under, won't let go.
Ash  @river:  I know that feeling. Can't shake the chill.
Moth @ash:    Why can't I escape? It's like flying blind.
River @moth:  Shadows claim me too often... Can't find my way back up.
```

## Performance note ⚠️

CPU inference is ~2 tokens/sec here, so each utterance takes ~15–75s depending on
model/prompt size. Fine for batch runs, **too slow for a real-time game.** Paths
to real-time, in order: a smaller model (e.g. `llama3.2:3b`, `qwen2.5:3b`), a
GPU, and **async generation** — produce the next reply while the current line's
TTS is playing (planned for M3+). The LLM call is one swappable function
(`services/llm.py`), so a cloud model (Claude API) drops in without touching the
sim.

## Layout

```
prototype/
  world/
    events.py   # Utterance (universal currency) + EventBus
    sim.py      # tick clock, hearing range, urge-based turn scheduler
  agent/
    memory.py   # write / decay / reinforce / recall + blur-forget mutation
    thought.py  # Markov subconscious drift (salience-weighted)
    agent.py    # hear()=influence in; speak()=drift+recall -> LLM
  services/
    llm.py      # swappable LLM backends (Ollama / Mock) + SpeechContext
  main.py       # personas, backend selection, debug overlay
```

> Note: the design doc called this folder `io/`; renamed to `services/` because
> `io` shadows Python's built-in `io` module.

## Tuning knobs

- `agent/memory.py`: `DECAY_PER_TICK`, `FORGET_THRESHOLD`, `MUTATE_CHANCE`, `BLUR`
- `agent/thought.py`: `SEED_WEIGHT`, `MAX_FRAGMENT`, `BUFFER`
- `services/llm.py`: model, `temperature`, `num_predict` (utterance length)
- `world/sim.py`: `HEARING_RANGE`, `SPEAK_THRESHOLD`
