# AI World — Design & Architecture Plan

A simulated world where autonomous AI agents think on their own, talk to each
other **out loud via TTS** (no on-screen text for AI speech), influence each
other, and grow/mutate/forget memory based on what they say and hear. The user
can speak to them too, and every utterance heard reshapes how an agent thinks.

---

## 1. Core Idea (in one paragraph)

Each agent runs a continuous **subconscious thought loop** — a stream of
half-formed ideas generated cheaply (Markov chain / associative drift over the
agent's own memory). When an agent decides to speak (its own impulse, or in
reply to something it heard), those drifting ideas are packed into a **prompt for
a local LLM**, which produces an actual utterance. The utterance is spoken with
**TTS**. Other nearby agents *hear* it (speech-to-text or, more cheaply, the raw
text is passed directly between agents while only the human hears audio). Hearing
something **writes to the listener's memory**, which **mutates, decays, and
forgets** over time. So memory both *drives* thought and is *changed by* thought
and conversation — the system self-emerges. Agents take turns: hearing an agent
makes you want to reply to *that* agent.

---

## 2. Design Goals & Non-Goals

**Goals**
- Emergent behavior from simple loops — not scripted dialogue.
- AI-to-AI influence: what one says changes what others think and say next.
- Memory that lives: grows, mutates, decays, forgets, gets biased.
- AI speech is **audio-only** (TTS). User sees no AI text (debug overlay optional).
- Fully local-capable: local LLM + local TTS, no required cloud calls.
- Real-time-ish: thought ticks continuously, speech happens in turns.

**Non-Goals (v1)**
- Photorealistic 3D world. (Start 2D / top-down or even headless.)
- Perfect speech recognition. (AI "hearing" can be direct text passing.)
- Many (100s) agents. (Start with 3–6.)

---

## 3. High-Level Architecture

```
┌───────────────────────────────────────────────────────────────┐
│                          WORLD / SIM                            │
│  - tick clock, spatial positions, "who can hear whom" (range)   │
│  - turn scheduler (who speaks next), event bus                  │
└───────────────┬───────────────────────────────┬───────────────┘
                │                                 │
        ┌───────▼────────┐               ┌────────▼───────┐
        │   AGENT A      │   ...         │   AGENT N      │
        │ ┌────────────┐ │               │  (same parts)  │
        │ │Subconscious│ │               └────────────────┘
        │ │thought loop│ │
        │ │(Markov)    │ │
        │ └─────┬──────┘ │
        │ ┌─────▼──────┐ │
        │ │  Memory    │ │  ← mutate / decay / forget / bias
        │ │  store     │ │
        │ └─────┬──────┘ │
        │ ┌─────▼──────┐ │
        │ │Speech gen  │ │  → prompt → LOCAL LLM → utterance text
        │ │(LLM)       │ │
        │ └─────┬──────┘ │
        └───────┼────────┘
                │ utterance text
        ┌───────▼────────┐        ┌──────────────────────┐
        │   TTS engine   │ ─audio→│  Speaker / user ears  │
        └───────┬────────┘        └──────────────────────┘
                │ (text also routed to in-range listeners)
        ┌───────▼────────────────────────────────────────┐
        │  HEARING: deliver utterance to nearby agents     │
        │  → each listener writes a memory of it           │
        └─────────────────────────────────────────────────┘

  USER INPUT (mic→STT  OR  typed) ──treated as an utterance──→ HEARING
```

**Key insight:** an *utterance* is the universal currency. Whether it comes from
an AI's LLM, or from the user's mic/keyboard, it flows through the same pipe:
`utterance → TTS (if AI) → heard by in-range agents → memory write → influences
next thought`.

---

## 4. Component Breakdown

### 4.1 World / Simulation Loop
- **Tick clock**: fixed timestep (e.g. 10 Hz) for thought drift + memory decay.
- **Space & hearing range**: each agent has a position; agents within radius `r`
  "hear" an utterance. Simplest v1: everyone hears everyone (single room).
- **Turn scheduler**: prevents everyone talking at once. Options:
  - *Token / talking-stick*: only one agent holds the floor at a time.
  - *Urge-based*: each agent accumulates a "want to speak" score; highest above
    threshold speaks, then cools down. (More emergent — recommended.)
- **Event bus**: publishes `UtteranceSpoken`, `MemoryChanged`, `TurnStarted`, etc.
  Lets the UI/debug overlay subscribe without coupling.

### 4.2 Subconscious Thought Loop (the Markov stream)
Runs every tick, cheaply, for every agent — this is the "always-on inner voice."
- **Source material**: the agent's own memory tokens/phrases + recently heard
  phrases. Build a Markov chain (order-1 or order-2) over these.
- **Output**: a rolling buffer of "drifting ideas" — short fragments, e.g.
  `["the river", "river is cold", "cold like her voice", "her voice again"]`.
- **Bias**: transition probabilities weighted by memory *salience/emotion* so
  charged memories dominate the drift (this is the "influence" mechanism).
- **Why Markov, not LLM, here**: cheap, continuous, runs at tick rate, and gives
  a genuinely *associative/dreamlike* substrate. The LLM is only called when
  actually speaking, so cost stays bounded.
- **Speak urge**: a fragment that's emotionally charged, or a heard utterance
  addressed at this agent, raises the urge to speak.

### 4.3 Memory Store (the living part)
This is the heart. Each memory is a record:
```
Memory {
  id, text, embedding?, salience (0..1), emotion (valence/arousal),
  created_tick, last_touched_tick, source: self|heard|user,
  speaker_id, decay_rate, mutation_count
}
```
Operations (run on tick or on event):
- **Write**: hearing/speaking creates or reinforces a memory.
- **Decay**: salience drops over time → low-salience memories get pruned
  (**forgetting**).
- **Reinforce**: re-hearing a similar idea bumps salience and resets decay.
- **Mutate**: occasionally rewrite a memory's text (drop words, swap synonyms,
  merge two memories, drift emotion) — memories become *unreliable*, like real
  ones. Mutation rate ↑ for old, rarely-touched memories.
- **Influence/bias**: heard memories with strong emotion shift the agent's
  global "mood" and the Markov weights → changes future thought + speech.
- **Recall**: retrieve top-K memories by salience + relevance (to current drift
  or to the utterance being replied to) to feed the LLM prompt.

Storage v1: in-memory list + periodic JSON snapshot per agent. v2: SQLite, or a
vector store (e.g. embeddings + cosine) for relevance recall.

### 4.4 Speech Generation (local LLM)
When an agent wins a turn / decides to speak:
1. **Assemble prompt** from:
   - Agent persona/system card (name, traits, speaking style).
   - Current mood (from memory bias).
   - Top-K recalled memories (salient + relevant).
   - The drifting ideas from the Markov buffer ("you are thinking about: …").
   - The utterance being replied to, if any, + who said it.
2. **Call local LLM** (see §6) → short utterance (1–2 sentences; keep it short
   for TTS pacing and turn flow).
3. Emit `UtteranceSpoken{speaker, text, addressed_to?}`.
4. Speaking also **writes back to the speaker's own memory** (you remember what
   you said), closing the self-influence loop.

> Prompt budget matters: cap recalled memories + drift fragments so the local
> model stays fast. Short outputs = snappier turns.

### 4.5 TTS (audio-only AI speech)
- AI utterances are **never shown as text** to the user — only spoken.
- Each agent gets a distinct **voice** (different voice id / pitch / rate) so the
  user can tell who's talking.
- TTS runs async; while an agent's audio plays, the turn scheduler holds the
  floor (or allows interrupt — see "barge-in" in §8).
- Engine options in §6.

### 4.6 Hearing / Influence Delivery
- After an utterance, deliver its **text** (not audio) to all in-range listeners.
  (We don't STT the AI's own audio — wasteful. Audio is for the human; text is
  for agents. The user's *input* is the only thing that may need STT.)
- Each listener: `memory.write(heard_text, source=heard, speaker=...)`,
  reinforce/bias, bump speak-urge if addressed.

### 4.7 User Interaction
- User talks via **mic (STT)** or **typed input** → becomes an utterance with
  `source=user`.
- Delivered to in-range agents exactly like an AI utterance → they remember it,
  it biases them, and the addressed agent's speak-urge spikes so it replies.
- User hears AI replies via TTS.

---

## 5. Data & Control Flow (one full cycle)

```
tick:
  for each agent:
    thought_loop.step()        # Markov drift updates idea buffer
    memory.decay_and_mutate()  # living memory
    update speak_urge

scheduler picks speaker S (highest urge over threshold)
  prompt = build_prompt(S.persona, S.mood, S.recall(), S.drift, reply_target)
  text   = local_llm(prompt)
  tts.speak(S.voice, text)             # USER HEARS THIS
  S.memory.write(text, source=self)    # self-influence
  for L in listeners_in_range(S):
    L.memory.write(text, source=heard, speaker=S)
    L.bias(text); L.speak_urge += addressed_bonus
  S.cooldown()

user utterance (anytime):
  same as above but source=user, no TTS, routed to in-range agents
```

---

## 6. Technology Choices (recommended stack)

**Language:** Python (fast to prototype, great LLM/TTS/audio libs). Move hot
loops to optimized code later if needed.

| Concern | v1 (simple, local) | Later |
|---|---|---|
| Local LLM runtime | **Ollama** (e.g. Llama 3.x 8B / Qwen 7B / Mistral 7B) via HTTP | llama.cpp direct, vLLM, batched serving |
| Thought drift | hand-rolled Markov chain (`markovify` or custom dict) | embeddings + sampling, small RNN |
| Memory | in-mem dict + JSON snapshots | SQLite + sqlite-vec / FAISS / Chroma |
| Embeddings (recall) | `sentence-transformers` (MiniLM) | larger / GPU |
| TTS (local) | **Piper** (fast, per-voice models, offline) or Coqui TTS | XTTS for cloning; ElevenLabs if cloud OK |
| STT (user mic) | **faster-whisper** (local) | streaming whisper |
| Audio playback | `sounddevice` / `pygame.mixer` | spatial audio |
| World/UI | headless first, then **pygame** 2D top-down | Godot/Unity bridge |
| Orchestration | single Python process, asyncio | per-agent processes / actor model |

> **Cloud option:** if local LLM quality is too low for emergent richness, the
> LLM call is a single swappable function — point it at the **Claude API**
> (e.g. Haiku for cheap/fast turns, Sonnet for richer ones). Keep TTS local for
> the audio-only requirement. Design the LLM + TTS as **interfaces** so either
> can be swapped without touching the sim.

---

## 7. Suggested Project Structure

```
AIgame_world/
  README.md
  DESIGN.md                 ← this doc
  requirements.txt
  config.yaml               # tick rate, ranges, model names, voices, decay rates
  src/
    world/
      sim.py                # tick loop, scheduler, hearing range
      events.py             # event bus / dataclasses for utterances
    agent/
      agent.py              # ties the parts together; persona
      thought.py            # Markov subconscious loop
      memory.py             # store: write/decay/mutate/forget/recall/bias
      speech.py             # prompt assembly + LLM call
      mood.py               # valence/arousal from memory
    io/
      llm.py                # LLM interface (ollama / claude) — swappable
      tts.py                # TTS interface (piper) — per-voice
      stt.py                # user mic → text (optional)
      audio.py              # playback queue
    ui/
      debug_overlay.py      # OPTIONAL: shows text for dev only (off by default)
      pygame_view.py        # 2D world view
    main.py                 # wire everything, load config, run
  data/
    voices/                 # piper voice models per agent
    snapshots/              # per-agent memory JSON dumps
  tests/
```

---

## 8. Tricky Bits & Decisions to Make

- **Turn-taking vs. chaos**: urge-based scheduling is more emergent but can
  deadlock or spam. Add cooldowns, a max-utterances-per-window, and a small
  random jitter. Consider a "talking stick" fallback for v1 stability.
- **Barge-in / interruption**: should the user (or an agent) be able to cut off
  ongoing TTS? Nice for realism; adds audio-queue complexity. Defer to v2.
- **AI hearing = text passing** (recommended) vs. STT'ing AI's own audio
  (realistic but wasteful + lossy). Pick text passing for v1.
- **Runaway feedback loops**: agents echoing/amplifying each other into nonsense.
  Mitigate with decay, mutation toward novelty, mood regression-to-baseline, and
  a "boredom" penalty for repeating recent ideas.
- **LLM latency**: 7B local models may be ~1–5s/turn. That's fine for a
  conversation cadence. Pre-warm the model; keep outputs short; consider
  generating the *next* speaker's reply while current audio plays.
- **Cost/perf of TTS**: Piper is fast and offline; pre-generate nothing, stream
  per utterance. Cache nothing (utterances are unique).
- **Persistence**: snapshot memory to disk so a world can be paused/resumed and
  so you can watch personalities drift across sessions.
- **Observability**: you can't read AI text by design, so build the debug overlay
  early (toggle) — you'll need it to tune decay/mutation/urge constants.

---

## 9. Build Order (milestones)

1. **Skeleton + event bus**: world tick, 2 agents, hardcoded utterances printed.
   Prove the utterance→hearing→memory loop. (No LLM, no TTS yet.)
2. **Memory module**: write/decay/forget/reinforce + JSON snapshot. Unit tests.
3. **Markov thought loop**: drift buffer from memory; speak-urge signal.
4. **LLM speech**: wire Ollama; assemble prompt from drift+recall; short replies.
   Still text-only (debug). Verify emergent back-and-forth between 2 agents.
5. **TTS**: Piper per-voice; flip AI text → audio-only; user hears the world.
6. **Mutation & bias**: make memory mutate/forget and bias Markov + mood. Tune.
7. **User input**: typed first, then mic+STT. User joins the conversation.
8. **World/UI**: pygame top-down with positions + hearing range + debug toggle.
9. **Polish**: turn-taking tuning, persistence, more agents, distinct voices.

> Each milestone is independently runnable and demoable. Don't build all
> components before testing the loop — milestone 1 validates the core idea.

---

## 10. Open Questions (decide before/while building)

- How many agents in v1? (Suggest 3.)
- Local-only, or allow Claude API fallback for richer speech?
- Single room (everyone hears all) or spatial hearing from the start?
- Mic input in v1, or typed-only first?
- How visible should the debug text be — fully hidden, hotkey toggle, or
  separate dev window?

---

*Next step: scaffold the repo per §7 and implement Milestone 1 (the
utterance→hearing→memory loop with two agents), since that proves the whole
concept before any LLM/TTS cost.*
```
