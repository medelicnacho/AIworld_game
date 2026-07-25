# VOICE.md — light emergent speech in friendly towns

*The plan for the first thing in this world that talks. Written before any of it is built,
because the arguments are the part that gets lost — the cadence numbers are easy to re-derive
and the reasons a whole class of design was refused are not.*

**Scope, decided up front: friendly towns only.** Not mobs, not rival war-camps, not the
frontier. The reasons are D1 and D2 below and they are the spine of the whole document.

---

## 0. The one insight that pays for everything else

**Silence is the resource, not speech.**

Every other system in this game adds. This one is worth having only if it *subtracts* — if
the world is quiet enough that a voice means something when it arrives. The failure mode is
not "too little talking", it is a world where everything chatters and therefore nothing said
is worth hearing. Every decision below is a way of spending silence carefully.

The corollary, and the reason this is cheap: **the murmur layer does not need the LLM.**
`localprototype`'s voice is two-layer — a Markov drift underneath, a settled deliberate line
on top. For ambient muttering the drift *is* the product. Half-formed is not a compromise
here, it is the correct texture for someone talking to themselves. So the whole feature is a
74-line Markov port plus a TTS call, with no model, no prompt, and no inference latency.

---

## 1. Locked decisions

| # | decision | why (and what would re-open it) |
|---|---|---|
| **D1** | **Friendly towns only.** Never mobs. | Voice is spent the first time it is used: the first thing that speaks defines what speech *means* here. Spend it on a body you delete in three seconds and you have taught the player that talking is wallpaper — permanently. This is D7 ("mobs are soulless on purpose") applied to audio. Re-opens only if towns are voiced, land well, and the world still feels under-populated. |
| **D2** | **Never during combat, and never in a hostile town.** | `audio/sfx.js` is explicit that hearing *which side* a meteor is on is how you read a volley. The telegraph doctrine — "being hit is always 'I didn't move', never 'I couldn't have known'" — runs on a clean audio channel. Chatter over combat is not a mixing problem to EQ around; it is two systems competing for the one channel the fairness promise depends on. A rival's war-camp holds its tongue for the same reason: that is a fight, not a place. |
| **D3** | **Markov drift only. No LLM in this loop.** *Amended in play (2026-07-25): the murmur stays pure Markov, but when the lab reports a model up, a minority of slots (`VOICE.lineChance`) SETTLE into one clear LLM line grown from the drift — the lab's own two-layer voice, arrived early. With no model running the layer is inert and every slot is a murmur, so the no-dependency property survives.* | §0's corollary. Also removes the scariest unknown (model latency) from the first thing players hear, and keeps the feature working when `ollama` is not running. Santāna keeps what is actually hers: her voice (lessac, D7) and her *register* — a settled line here is a villager surfacing for one sentence, not a companion conversing. |
| **D4** | **Hearing writes memory.** The drift is seeded by what happened, not by a static phrase list. | The single most important line in this document. A Markov chain over a fixed list is a phrase generator, and players clock it inside two minutes. What makes `localprototype` feel alive is the *loop*: an utterance is heard → it writes a memory → memory biases the next drift. Port the loop, not just the chain. In game terms the memories are written by **things the player caused**. |
| **D5** | **One voice at a time per town, on a long cooldown.** *Cadence re-tuned in play (2026-07-25): the drafted ~40s budget read as a MUTE town — the feature registered as broken, not restrained. Shipped at ~12-20s (`VOICE.cooldown/jitter`), tested against both extremes (~5-9s reads as a lobby). The principle held; the number was wrong.* | §0 as a number. One voice at a time is the part that never moved: two villagers talking over each other is the chatbot farm, whatever the interval. |
| **D6** | **Voice is cast per ROLE, not per individual.** Distinctness comes from `model × length_scale`, not from one model per person. | Eight models exist (§2) and a town holds ~14 people. Per-person models are impossible *and* wrong: a herbalist should sound like a herbalist across every town you ever enter, the same way the trade colours already work. Pace jitter gives individuality inside a role. |
| **D7** | **`en_US-lessac` is RESERVED for Santāna.** Never cast on a shopkeeper. | It is the collective-mind voice in the lab (`viewer.py`: "devout"). Spending it on a vendor is spending the one voice that is supposed to arrive later and be unlike everything else. Same argument as D1, one level up. |
| **D8** | **Fails soft, exactly like the bridge already does.** Lab not running → the town is silent → the game is what it is today. | `net/bridge.js`'s existing rule: *the bridge is an enhancement, never a dependency.* Nothing here may throw into the frame loop or block it. |
| **D9** | **Subtitles ON for the town layer — provisionally, and against `DESIGN.md`.** | The lab's rule is that AI speech is audio-only; agents are heard, not read. That is beautiful in a quiet room. In a third-person shooter with a soundtrack and gunfire, an unsubtitled murmur is a line nobody heard, and a line nobody heard is a line you did not ship. Ship them on, then try turning them off — this is a measurement, not a principle. |

### Rejected, and why (so it is not re-argued from scratch)

- **Mob barks.** D1/D2. The proposal that started this document; refused on the grounds that it spends the scarcest resource in the game on its cheapest target, and fights the telegraph doctrine for the same ears.
- **An LLM in the murmur loop.** D3. Latency on the critical path, a hard dependency on `ollama`, and it makes the town speak *clearly* — which is Santāna's job.
- **A unique voice model per villager.** D6. ~63 MB each; 14 per town is not a memory budget, it is a leak.
- **Speech in rival towns.** D2. Also: a war-camp with no civilians (by design, `town/raid.js`) has nobody to do the talking.

---

## 2. Measured facts (checked on this machine, 2026-07-25)

Everything this feature needs already exists. That is the argument for doing it now.

| fact | evidence |
|---|---|
| **Eight Piper voices installed**, ~500 MB | `localprototype/data/voices/*.onnx` — alan, ryan, northern_english_male, amy, cori, joe, kristin, lessac |
| **`POST /speak {text, voice}` → WAV bytes, no model involved** | `localprototype/bridge.py:247` |
| **The game client already calls it** | `src/net/bridge.js:136` — `async speak(text, voice)` returns an `ArrayBuffer` |
| **Synth time is already reported** | `/speak` returns an `X-Synth-Ms` header — pacing can be tuned against measurement, not guesswork |
| **The Markov drift is 74 lines** | `localprototype/agent/thought.py` — order-1 chain over memories weighted by salience, plus persona seeds |
| **Faction identity provably shapes speech** | `experiment_camp_voice.py` — feeding a camp's banner into speech makes lines land measurably closer to it, semantically and literally |
| **Positional audio machinery exists** | `src/audio/sfx.js` — gain by distance, pan by angle |

### Three gaps that must be closed (all small, all named here so none is a surprise)

1. **`/speak` drops `length_scale`.** `bridge.py:107` builds `Voice(model=voice)` and discards
   pace and volume — which is exactly the axis D6 relies on for making two townsfolk sound
   like two people. One-line change: accept `length_scale` and `volume` in the body.
2. **The bridge is DEV-only.** `src/net/bridge.js:39` refuses to connect in a built copy, on
   purpose (the lab is on *your* machine; a stranger's would fail forever on a backoff). So
   **voice is a local-only feature** — itch.io players get today's silent towns. That is the
   correct call and it is not a bug, but it means this layer is for you and playtesters at
   your desk until audio is pre-baked into the build. Decide that later, not now.
3. **Piper is CPU-heavy and serialized** (`tts_lock`, "don't let requests thrash"). Synthesis
   must never sit on the frame path, and repeated fragments should be cached by text hash.

---

## 3. The casting

Trade colours already teach the player who is who by sight. Voice should teach the same
lesson by ear, and agree with it.

| role | model | pace | why this voice |
|---|---|---|---|
| **Herbalist** | `en_GB-cori` | 1.05 | warm British female — the one who mends you |
| **Smith** | `en_GB-northern_english_male` | 1.10 | bleak, gruff, unhurried; sounds like the trade |
| **Adept** | `en_GB-alan` | 1.18 | calm and slow — sells you the strange things, should sound like it knows more than it says |
| **Keeper** (the townsfolk) | `amy` / `joe` / `kristin` / `ryan`, chosen by a per-villager hash | ±0.12 jitter | four models × pace jitter = a town of individuals from four files |
| **Quartermaster — Iron** | `en_US-ryan` | 1.00 | dry, hard, outlasts things |
| **Quartermaster — Ash** | `en_US-joe` | 0.95 | open and forward; hits first |
| **Quartermaster — Vale** | `en_US-amy` | 0.92 | quick and light; never where the blow lands |
| **Santāna** *(Stage 2, reserved)* | `en_US-lessac` | — | D7 |

The three quartermaster voices are the faction characters read aloud, and they cost nothing
extra — `factions.js` already carries `focus: damage | speed | survival`.

---

## 4. Slices, each with the gate that decides it

House rule from `STAGES.md`: a slice is done when its gate is answered **in play**, not when
it compiles. And the standing gate over all of them, stolen verbatim from Stage 2:

> **Play for twenty minutes without muting it.** If it is annoying, the cadence is wrong —
> fix pacing before adding anything else. Ambient speech that outstays its welcome poisons
> the whole idea.

### V1 — the murmur ⏱ ~a day
Port `agent/thought.py` to `src/town/drift.js` (order-1 chain, salience-weighted, ~74 lines,
seeded from `rng.js` so it stays replayable and lint-clean). Give one town's villagers a
static seed vocabulary. On a long cooldown, the nearest villager in a **friendly** town
drifts a fragment → `bridge.speak()` → played positionally through `sfx.js`.

**Gate:** stand in the spawn town for five minutes. Does it feel like a place where people
live, or like a radio left on? If the second, cut the rate before anything else.

### V2 — the casting ⏱ ~half a day
Per-role voices and pace jitter (§3), plus the `length_scale` fix in `bridge.py`.

**Gate:** with your eyes closed, can you tell the herbalist from the smith? Can you tell two
keepers apart?

### V3 — the memory ⏱ ~1–2 days *(the one that matters)*
D4, made real. A tiny per-villager memory (text + salience + decay — a ~30-line shim, not
`memory.py`'s 576) written by **events the player caused nearby**: a camp sacked, a boss
felled in this ring, the colours you are wearing, how many times you have walked through.
Salience decays, so the town forgets.

**Gate:** sack a rival camp within a few hundred metres, walk into a friendly town, and hear
something half-about it inside a few minutes. **If this gate fails, the whole feature is
flavour text and should be cut rather than expanded.**

### V4 — the town's own character ⏱ ~half a day
Seed each town's shared vocabulary from its faction banner, using `experiment_camp_voice.py`'s
finding. An Iron town's talk circles endurance; Vale's circles not being caught.

**Gate:** can you tell which faction's town you are in from the murmuring alone, before you
see a colour?

---

## 5. What this is really for

It is not content. It is the **cheapest possible test of the thesis the whole project rests
on** — that a settlement running simple local loops reads as alive — in the safest venue in
the game, where nothing is trying to kill you and the audio channel is empty.

If a murmuring town feels good, Stage 2 (Santāna) and Stage 3 (the living town) are de-risked
for a weekend's work instead of a month's. If it feels annoying, you have learned the most
important thing in the project for a weekend's work instead of a month's.

That is the same argument `STAGES.md` already makes for doing Santāna before the town. This
is one rung cheaper again.
