# STAGES — the executable build order

*The next stretch, broken into stages you can actually start on a given evening. Each has a
goal, a task list, and a **gate** — a question that can fail. If a gate fails, stop and fix
it rather than building the next stage on top of it.*

*Companions: [`PLAN.md`](PLAN.md) (decisions + milestones), [`README.md`](README.md) (what
exists today). Stage numbering here is independent of PLAN's M-milestones; the mapping is
noted per stage.*

---

## Stage 0 — the voice spike ⏱ ~2 days · **do this first**

**Goal:** one number. Can a Piper line, generated from a real `gemma3:4b` response, reach the
game fast enough to feel like speech rather than a loading screen?

Everything downstream assumes local AI is fast enough to be diegetic. That assumption is
untested and it is the cheapest thing in the project to falsify.

- [ ] `bash ../localprototype/scripts/get_voices.sh` — no Piper voices are downloaded yet
- [ ] Throwaway Python script: prompt → `services/llm.py` → `services/tts.py` → `out.wav`.
      Print time-to-first-token, total generate time, TTS time.
- [ ] Minimal HTTP endpoint serving that wav; fetch and play it in the game on a keypress.
- [ ] Measure with the game running: does audio decode hitch the frame?

**Gate:** a spoken line lands in **under ~2.5s** end to end, and playback costs no visible
frame time.
**If it fails:** the tiering changes shape — pre-generate lines during quiet moments, cache
aggressively, or drop the LLM tier for ambient speech and keep it only for direct
conversation. Better to learn this now than after the bridge is built around it.

---

## Stage 1 — the bridge ⏱ ~3–4 days *(replaces PLAN M2's ordering)*

**Goal:** the browser can see and talk to the Python lab over localhost.

Keep the lab **dependency-free** (stdlib only, per its posture): SSE for the server→browser
stream, plain POST for browser→server. No websocket library, no FastAPI.

- [ ] `localprototype/bridge.py` — stdlib `http.server`, threaded, CORS for `localhost:5173`
- [ ] `GET /health` → `{ok, model, voices, world: null}`
- [ ] `GET /stream` → SSE, ~10 Hz: `{tick, souls:[{id,name,x,z,mood,speaking}], events:[…]}`
- [ ] `POST /say {text}` → `world.inject_user(text)`
- [ ] `POST /speak {text, voice}` → wav bytes (or an id + `GET /audio/<id>.wav`)
- [ ] Browser `src/net/bridge.js` — reconnecting SSE client, POST helpers, **offline-safe**:
      if the bridge is down the game must run exactly as it does today
- [ ] HUD indicator: bridge connected / offline

**Gate:** kill the Python process mid-game and the game keeps running, no errors, no hitches.
Restart it and the connection recovers on its own.

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

## Stage 3 — the first town ⏱ ~2 weeks *(PLAN M3)*

**Goal:** a place with people in it, in ring 0.

- [ ] Bridge hosts a real `World`: 20–30 souls, `bond_enabled`, stakes, lore, murmur;
      ticking at 10 Hz in its own thread, model calls off the lock (as `sim.py` already does)
- [ ] Fixed anchor in the Commons (~150m from spawn, inside the boss-free zone)
- [ ] Coordinate mapping: substrate 2D → game world, ground-snapped browser-side via
      `groundY()`; the substrate proposes movement, the engine owns the body (PLAN §4)
- [ ] `src/town/souls.js` — bodies, name labels, bark text, Piper audio when near
- [ ] **Safe space:** no mob spawns within the town radius; bosses already can't reach ring 0
- [ ] Simple huts so it reads as a settlement, not a crowd standing in a field
- [ ] Talk to a specific soul: your line enters the world through `inject_user`, and the
      souls near you actually *hear* it
- [ ] Cost guard: log memory-items/tick against the ~14 µs/item law (PLAN §3). Bound the
      soul count to whatever keeps a settlement affordable.

**Gate:** leave for ten minutes, come back, and the town has visibly moved on — someone has
died, bonded, or fallen out with someone.

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
