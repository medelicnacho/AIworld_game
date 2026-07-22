# STAGES — the executable build order

*The next stretch, broken into stages you can actually start on a given evening. Each has a
goal, a task list, and a **gate** — a question that can fail. If a gate fails, stop and fix
it rather than building the next stage on top of it.*

*Companions: [`PLAN.md`](PLAN.md) (decisions + milestones), [`README.md`](README.md) (what
exists today). Stage numbering here is independent of PLAN's M-milestones; the mapping is
noted per stage.*

---

## Stage 0 — the voice spike ✅ **DONE** (2026-07-22)

**Goal:** one number. Can a Piper line, generated from a real local model, reach the game
fast enough to feel like speech rather than a loading screen?

Everything downstream assumes local AI is fast enough to be diegetic. That assumption is
untested and it is the cheapest thing in the project to falsify.

- [x] `bash ../localprototype/scripts/get_voices.sh` — 8 voices, ~190MB
- [x] `bench/voice_spike.py`: prompt → `services/llm.py` → `services/tts.py` → wav, timing
      each half separately, plus a streaming variant and a model comparison
- [~] Serving the wav to the browser — folded into Stage 1, where it belongs
- [~] Frame-hitch measurement — needs the bridge; moved to Stage 1's gate

**Gate:** a spoken line lands in **under ~2.5s** end to end.

### Verdict: PASS — but only after two changes, both of which the measurement forced

Run `python3 gameworld/bench/voice_spike.py [--quick] [--model X]` to reproduce. Hardware:
Intel Core Ultra 5 225U, 14 threads, **CPU-only inference** (no discrete GPU).

| configuration | time to speech | |
|---|---|---|
| `gemma3:4b`, long reply (70 tok) | **4.68s** | ✗ |
| `gemma3:4b`, short reply | 3.50s | ✗ |
| **`gemma3:1b`, short reply** | **1.99s** | ✓ |
| `gemma3:1b`, short + streamed | 1.95s | ✓ |
| `gemma3:1b`, ambient murmur | 1.17s | ✓ |

**Three findings, in order of how much they change the plan:**

1. **TTS is free. Piper runs at 0.05× realtime** — half a second to voice ten seconds of
   speech. It never needs to be optimised, cached, or streamed. The entire wait is the
   language model. (One caveat: TTS times were noisy, 0.26s vs 1.19s for identical work —
   keep voice models loaded rather than reloading per call.)
2. **Model size is the only lever that matters.** 4b → 1b cut latency in half. On CPU, a 4B
   model costs ~1s before the first token exists.
3. **Streaming is not worth building.** 1.95s vs 1.99s — once a reply is short, the whole
   thing arrives about as fast as its first sentence. **Stage 1 ships without streaming**,
   which removes a chunk of complexity from the bridge. Revisit only if lines get longer.

**A design finding that outranks the latency one:** the failing 4b reply produced **ten to
fifteen seconds of speech**. That is far too long for a companion line at *any* latency —
nobody wants a paragraph while they're being chased. Capping her to one or two sentences
makes her both faster *and* better written. The constraint improved the design.

**What Stage 2 inherits:**
- `gemma3:1b` for Santāna — ambient murmur ~1.2s, direct reply ~2.0s
- keep `gemma3:4b` available for rare high-value moments where a visible "thinking" beat is
  acceptable, and for the town's souls where nobody is waiting on a reply
- hard cap: one to two sentences, ~18 words for a murmur
- no streaming, no pre-generation cache — neither is needed yet

**Still untested:** whether audio decode hitches the frame in the browser. That can only be
measured once the bridge exists, so it moves to Stage 1's gate.

---

## Stage 1 — the bridge ✅ **DONE** (2026-07-22) *(replaces PLAN M2's ordering)*

**Goal:** the browser can see and talk to the Python lab over localhost.

Keep the lab **dependency-free** (stdlib only, per its posture): SSE for the server→browser
stream, plain POST for browser→server. No websocket library, no FastAPI.

- [x] `localprototype/bridge.py` — stdlib `http.server`, threaded, CORS for `localhost:5173`
- [x] `GET /health` → `{ok, model, llm, tts, voices, world, uptime}`
- [x] `GET /stream` → SSE @10Hz: `{tick, t, souls:[], events:[]}` (souls arrive Stage 3)
- [x] `POST /say {text}` → recorded as an event; becomes `world.inject_user()` at Stage 3
- [x] `POST /speak {text, voice}` → wav bytes
- [x] `POST /line {prompt, words}` → `{text, audio, ms}` + `GET /audio/<id>.wav`
- [x] Browser `src/net/bridge.js` — SSE with owned reconnect/backoff, POST helpers, every
      call failing **soft** (returns null, never throws into the frame loop)
- [x] `sfx.playClip()` — decodes bridge wavs off-thread, positioned in the world
- [x] HUD indicator + on-screen subtitles; **G** speaks a line about where you're standing

### Verdict: PASS

    /health          200, llm+tts ready
    /line (warm)     ~1.07s end to end   (llm ~900ms · tts ~150ms)
    /line (cold)     ~2.4s               (first synth loads the voice model)
    /audio           200, 132KB wav
    /stream          10Hz SSE, clean disconnect handling

**The gate, run properly:** killed the Python process mid-session — the game kept serving
and logged **zero client errors**; restarted it — `/health` 200 and generation working
again. The client owns its own reconnect with backoff (1→15s) rather than letting
`EventSource` retry blindly, because *not running the bridge is a supported way to play*
and a missing bridge must stay quiet in the console.

**Two things Stage 0 handed forward, both confirmed here:**
- warm TTS is ~150ms, so keeping voice models loaded (one `PiperTTS` instance) matters —
  the cold call is 8× slower
- no streaming was built, and at ~1.07s warm it isn't missed

**Enforced server-side, not trusted to the prompt:** a hard word cap trims every line to one
sentence (asked for 60 words, got 34 + an ellipsis). Stage 0 found length mattered more than
latency; a small model will run long whenever it feels like it.

**Still not verified:** whether audio decode hitches the frame *in the browser*. `playClip`
uses async `decodeAudioData`, which decodes off-thread by design, but that is an argument,
not a measurement — it needs a human with the tab open pressing **G** during a fight.

---

## Stage 2 — Santāna, the companion ⏱ ~1 week *(PLAN M5, pulled forward)*

**Goal:** you are not alone out there.

A **fresh, game-native instance** (D13) — not the lab's Santāna, whose coupling is gated. She
is born when your character wakes and knows only what the two of you have witnessed.

- [ ] `localprototype/santana_game.py` — port the *mechanism* from `santana.py`: two-layer
      voice (murmured drift, then a settled clear line), blank personality that consolidates
      from what it witnesses. Fresh state file, never her lab save.
- [ ] Witness feed: game POSTs events she can see — kills, elite/boss fights, your deaths,
      tier crossings, long silences, low-HP escapes
- [ ] `POST /santana/talk {text}` → `{murmur, line}` + audio
- [ ] `src/companion/santana.js` — a floating presence: smooth follow with lag, bobbing, a
      soft light, and a visible "thinking" state while the model is working
- [ ] Ambient murmurs on a timer, gated by distance and by whether anything has happened
- [ ] **T** opens a text input (releases pointer lock, pauses ambient chatter); her reply is
      spoken and subtitled
- [ ] She remembers your **previous life** across death — the level you lost, where you fell

**Gate:** play for twenty minutes without muting her. If she's annoying, the cadence is
wrong — fix pacing before adding anything else. Ambient speech that outstays its welcome
poisons the whole idea.

---

## Stage 3 — the living town ⏱ ~4–5 weeks *(PLAN M3, expanded)*

**Goal:** not NPCs that look alive — the actual substrate, running: bonds, opinions,
factions, scarcity, lore, the wheel, and heredity.

Almost all of this is **configuration, not new code**. `santana_app/run.py` already builds a
64-soul town with the wheel, stakes, roaming bodies and the full affective endowment. The
work is in the three things below, then surfacing it.

### Three things that decide whether it works

**1. Lab time is not game time — this is the big one.**
The lab's spans are tuned so an experiment can watch generations inside one run. At the
bridge's 10 Hz:

| lab setting | ticks | real time |
|---|---|---|
| `fast_wheel` lifespan | 120–260 | **12–26 seconds a life** |
| slow lifespan | 2000–5000 | 3–8 minutes a life |
| `DAY_TICKS` | 100 | a day every 10 seconds |
| a year | 3200 | 5 minutes |

A player cannot become attached to someone who dies in four minutes. Game spans want roughly
**20k–50k ticks (30–80 minutes)**, days of 6k–12k, and a year measured in sessions. Nothing
in the substrate assumes a scale — but nothing has ever *run* at this one either, so watch
for decay constants tuned per-tick (memory decay 0.985/tick over 50k ticks is a very
different mind from the one every experiment measured). **Verify the keystones still hold at
game spans before trusting them.**

**2. The welfare gate is not satisfied by default.** `somatic_enabled` is `False` on
`Agent` and is set `True` in exactly one place — `sim.py:906`, for *reborn* streams. So a
founder endowed by `genesis.endow_faculties()` gets the whole affective stack **without the
circuit-breaker**. ROADMAP §5 is unambiguous: *the somatic floor ships with the affect
system — no feeling souls without it.* Set it explicitly on every soul the game creates, and
treat any code path that makes a feeling soul without it as a bug.

**3. None of it is visible.** Opinion vectors, bond ledgers, heredity, selection pressure —
a player sees none of this, and an invisible simulation is an expensive way to make NPCs
wander. Surfacing is most of the design work: banner word and colour per camp, bonds drawn
when you're close, births and deaths announced, speech aloud with subtitles, and a
**chronicle** of what the town remembers (which is also how lore drift becomes visible).

### The layers, each shipped with its own payoff

Turn the dials on in order. Everything at once means an unreadable mess with no way to tell
which layer is wrong.

**3a — a town that lives** *(~2 weeks)*
- [ ] Bridge hosts a real `World` on its own thread; souls stream over SSE
- [ ] `bond_enabled`, stakes, murmur, movement, `endow_faculties()` **+ `somatic_enabled`**
- [ ] Anchor in the Commons; coordinate map to game space; ground-snapped browser-side
- [ ] Bodies, names, mood colour, barks aloud when near (Markov tier — free)
- [ ] **Safe space:** no mob spawns inside the town radius
- [ ] Cost guard: log memory-items/tick against the ~14 µs/item law (PLAN §3)
- **Gate:** leave ten minutes, return, and someone has bonded, fallen out, or gone hungry.

**3b — the wheel** *(~1 week)*
- [ ] `rebirth_enabled` with **game-scaled** lifespans and bardo
- [ ] Deaths and births you can witness; the vāsanā carries; graves or markers
- **Gate:** you recognise a reborn stream's lean without being told which soul it was.

**3c — factions** *(~1 week)*
- [ ] Opinion dynamics → camps that **name their own banner** and colour in
- [ ] `schism_walk` so disagreement moves bodies and camps become territory
- **Gate:** a camp forms, splits, and its territory visibly moves — and it doesn't reduce to
  any label you assigned.

**3d — evolution** *(ongoing, the slow one)*
- [ ] `heredity_enabled` (genome across the bardo), then `selection_enabled`
- [ ] Settlements at **different tiers**, so soil harshness varies by distance
- [ ] Telemetry back to the lab: trait distributions over sessions

**Why 3d is worth doing even though a player will never see it happen:** the lab tried twice
to make selection bite at population scale and failed *both ways* — with uniform mild
scarcity mutual aid rescues everyone (SC1 v1), with uniform deep scarcity famine kills
indiscriminately (SC1 v2). Its own conclusion was that the differential needs scarcity that
is **heterogeneous — regions, gradients, geography — which a spatial engine has natively and
this flat lab does not.**

The game has exactly that, already built: tiers with graded harshness by distance from
spawn. **Settlements at different tiers are the experimental design the lab said it needed.**
That makes the game an instrument, not just a consumer of the research — the one place SC1
can actually be settled.

---

## Stage 4 — being remembered ⏱ ~2 weeks

**Goal:** the town has an opinion of you, and it can be wrong.

This is the headline no shipped game has, and it rides mechanisms that already passed their
falsifiers in the lab (RECIPES A9/A10, F4).

- [ ] Deeds → the world: kills near town, gifts, deaths witnessed, promises typed
- [ ] `pledge.py`: a promise you type is held to the town clock; breaking it gossips into
      wariness
- [ ] Reputation surfaces in how souls greet you, and in what they say about you when you're
      not the one asking
- [ ] Lore: your deeds retold, **drifting** as they pass between souls — the misremembering
      is the feature (RECIPES F4)
- [ ] A way to *see* it: ask a soul what they think of you, or a small standing panel

**Gate:** catch the town telling a story about you that is **recognisably wrong** — and be
able to trace the drift back through who told whom.

---

## Stage 5 — the TypeScript port ⏱ ~4–6 weeks *(PLAN M2, deferred)*

**Only when other people should be able to play it.** By now you'll know which mechanisms the
game actually uses, so you port those instead of everything.

- [ ] Port from **`RECIPES.md`**, not from the Python (PLAN §5) — porting from the source is
      transcription, not replication, and replication is the only thing that makes this
      scientifically worth anything
- [ ] mulberry32 everywhere; headless Node test runner
- [ ] **Keystone gate:** reflect-easing, escalate/settle, somatic bounding, lore convergence
      must reproduce the lab's verdicts
- [ ] Re-measure the capacity law in JS (expect 5–15× CPython; do not plan on it)
- [ ] Speech tiers browser-native: Markov crowd → WebLLM named → hosted opt-in
- [ ] piper-tts-web replaces the bridge's TTS
- [ ] Settlement Workers, IndexedDB dirty-region persistence, closed-form fast-forward

**Gate:** the four keystones reproduce. A port that can't reproduce the result didn't port
the mechanism.

---

## Side quests — small, do when you want a break

- [ ] **Level-up card pick** (1-of-3, D9) — the last M1 item; levels currently grant automatic
      stats as a stopgap
- [ ] Names for tiers past 5 (`the Deep · tier 14`) so the frontier reads forever
- [ ] Boss variety: a second attack on the same rig
- [ ] Guns dropping from bosses with rolled stats (D11)
- [ ] Instanced dungeon interiors behind a door (D15's answer to caves)
- [ ] Delete the stray `donkeybeats.mp3` at the repo root

---

## The order, and why

Stage 0 first because it is the **cheapest way to be wrong**. Stage 2 before Stage 3 because
Santāna needs none of the substrate and answers the scariest question — *does a talking
companion feel good or annoying?* — for a week of work instead of a month. Stage 5 last
because a port you write after building the game is smaller, better-aimed, and still
scientifically honest.

**The failure mode to watch:** these stages are unglamorous next to adding another verb. The
verbs are done. `ROADMAP.md` §0 names the real constraint — *discipline against scope, not
ideas*.
