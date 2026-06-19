# Prototype — Milestone 1 (headless core loop)

Proves the core concept of the AI world **before** any 3D engine, LLM, or TTS:

> `utterance → heard by nearby agents → written to memory → influences next speech`

No dependencies — pure Python stdlib. The 3D layer (**Panda3D**, decided) and the
LLM/Markov/TTS will plug into this engine-agnostic core later.

## Run

```bash
cd prototype
python3 main.py                 # default: 120 ticks, seed 7
python3 main.py --ticks 200 --seed 3
```

## What you're watching

Three agents (River, Ash, Moth) stand near each other and take turns talking.
With no LLM yet, each utterance = a persona phrase + (often) something the agent
**recalled** — usually something it *heard from another agent*. So you can watch:

- **Propagation** — River's "the deep is cold" spreads into Ash & Moth's mouths.
- **Reinforcement** — repeated ideas gain salience (the high numbers in the dump).
- **Mutation** — memories drift word-by-word over time ("the deep is cold" → "the deep is" → "the is").
- **Forgetting** — low-salience memories are pruned (`~ forgot: ...`).
- **Turn-taking** — an urge-based scheduler picks who grabs the floor.

The final section dumps each agent's surviving memories by salience, so you can
see how three personalities have drifted from the same seed.

## Layout

```
prototype/
  world/
    events.py   # Utterance (the universal currency) + EventBus pub/sub
    sim.py      # World: tick clock, hearing range, urge-based turn scheduler
  agent/
    memory.py   # MemoryStore: write / decay / mutate / forget / recall / mood
    agent.py    # Agent: hear() = influence in; speak() = placeholder for LLM
  main.py       # wires 3 agents + a debug overlay (printed text)
```

## Tuning knobs (top of `agent/memory.py`)

`DECAY_PER_TICK`, `FORGET_THRESHOLD`, `REINFORCE_BUMP`, `MUTATE_CHANCE`, etc.
Note: word-echo mutation currently compounds ("the the the water...") — that's a
visible demo of drift; dial `MUTATE_CHANCE` down or cap duplicates to tame it.

## Next milestones

2. Swap the placeholder `Agent.speak()` for a **Markov drift loop + local LLM** (Ollama).
3. Add **Piper TTS** → AI speech becomes audio-only; hide the debug text.
4. Stand up the **Panda3D** world; subscribe the renderer to the EventBus.
