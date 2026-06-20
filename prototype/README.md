# Prototype

Builds the AI world bottom-up. The core sim runs on the Python **stdlib alone**;
two optional backends (Claude speech, Piper TTS) need a venv. The 3D layer
(**Panda3D**, decided) plugs into this engine-agnostic core later via the EventBus.

## Milestones

- **M1 ✅ Headless core loop** — `utterance → heard → memory → influence`, with
  memory that decays, blurs/forgets, reinforces. No LLM/TTS/3D.
- **M2 ✅ Subconscious + LLM** — a Markov drift over each agent's memory feeds an
  LLM (Claude or local Ollama) that talks and replies to whoever spoke.
- **M3 ✅ TTS** — every line is spoken aloud with a distinct per-agent Piper voice.
  AI speech is **audio-only** by default (you hear the agents, you don't read them).
- M4 ⬜ Panda3D world; renderer subscribes to the EventBus.

## Setup

```bash
# from repo root
python3 -m venv .venv
.venv/bin/pip install -r prototype/requirements.txt

# voice models for TTS (~190MB, gitignored)
bash prototype/scripts/get_voices.sh

# API speech (real-time): put a key in prototype/.env (either or both)
echo 'DEEPSEEK_API_KEY=sk-...'   >> prototype/.env   # cheapest + default
echo 'ANTHROPIC_API_KEY=sk-ant-...' >> prototype/.env # higher quality option
```

The core loop also runs with **no setup** (stdlib only) using `--backend mock` or a
local Ollama server — see backends below.

## Run

```bash
cd prototype
../.venv/bin/python main.py                 # Claude if key set, else Ollama/Mock; audio on
../.venv/bin/python main.py --show-text      # also print the lines (debug overlay)
../.venv/bin/python main.py --no-audio        # silent (text only)
../.venv/bin/python main.py --backend mock --no-audio --ticks 20   # zero-dep smoke test
../.venv/bin/python main.py --think           # print memory mutation/forget events
```

## What happens each turn

1. **Subconscious** (`agent/thought.py`): a salience-weighted Markov chain over the
   agent's memory drifts out short fragments.
2. **Speech** (`services/llm.py`): on its turn the agent packs drift + recalled
   memories + whoever just spoke into a `SpeechContext`; the LLM returns one short line.
3. **Voice** (`services/tts.py`): the line is synthesized in the agent's Piper voice
   and played — turns are paced to the audio.
4. **Hearing**: the line is written into listeners' memory → reshapes their drift.
   Memory keeps decaying, blurring, forgetting underneath.

## Backends (swappable, set with `--backend`)

| LLM backend | What | Needs |
|---|---|---|
| `deepseek` | DeepSeek v4-flash — ~1.2s/line, ~10x cheaper than Haiku, scales | `DEEPSEEK_API_KEY` (stdlib) |
| `claude` | Claude Haiku 4.5 — ~1.1s/line, real-time, higher quality | `anthropic` + `ANTHROPIC_API_KEY` |
| `ollama` | local model over HTTP — free, offline | Ollama running + a pulled model |
| `mock`   | composes from drift, no model | nothing (stdlib) |
| `auto`   | DeepSeek if key present, else Claude, else Ollama, else Mock | — |

Measured (4 calls each): DeepSeek v4-flash ~$0.00003/line, Claude Haiku ~$0.00031/line
— roughly tied on latency, DeepSeek ~10x cheaper, both fine quality for short lines.
DeepSeek v4-flash defaults to *thinking mode* (returns empty content under a tight
token cap), so the backend sends `thinking:{type:disabled}` for fast one-liners.

TTS is `PiperTTS` (local, offline, free) when voices + `piper-tts` are present,
else `NullTTS` (silent). Disable with `--no-audio`.

## Voices

Three distinct voices, mapped in `main.py`'s `PERSONAS`:
River = `en_GB-alan-medium` (slow), Ash = `en_US-ryan-medium`, Moth = `en_US-amy-medium`
(quicker). Swap models or tweak `length_scale` there.

## Layout

```
prototype/
  world/      events.py (Utterance + EventBus), sim.py (tick, hearing, scheduler)
  agent/      memory.py, thought.py (Markov drift), agent.py
  services/   llm.py (Claude/Ollama/Mock), tts.py (Piper/Null)
  scripts/    get_voices.sh
  data/voices/  (gitignored Piper .onnx models)
  main.py     personas, voices, backend + audio flags
```

## Known next step

Speech is currently **blocking** (a line plays fully before the next is generated),
so there's a ~1s gap before each line while the LLM responds. M4+ will **pipeline**
— generate the next line while the current one is playing — to hide that latency.
