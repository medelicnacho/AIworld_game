# gameworld

**An infinite low-poly frontier where the danger, the loot, and eventually the people all
scale with how far you dare to walk from spawn.**

Third-person shooter over read-only voxel-look terrain, endless levels, giant telegraphed
bosses. The long game — the reason this exists at all — is the layer that isn't built yet:
**settlements of NPCs running the soul substrate in [`../localprototype/`](../localprototype/)**,
who bond, feud, starve, remember you (fallibly), and get on with their lives while you're
away. Plus **Santāna**, a collective mind that follows you, speaks aloud, and is the only
thing in the world that remembers your last life.

Right now the game half is real and playable. The living half is next.

- **[`PLAN.md`](PLAN.md)** — the decisions with their reasons (D1–D16), the measured capacity
  law, the milestones and their gates. Read that for *why*; this file is *what and how*.

---

## Run it

```bash
npm install
npm run dev            # → http://localhost:5173/
```

Node 24 LTS lives at `~/.local/opt/node` on this machine (installed without root — delete
that folder to remove it). Put it on PATH:

```bash
export PATH="$HOME/.local/opt/node/bin:$PATH"
```

Other scripts: `npm run build` · `npm run lint` (ESLint, with `no-undef` **on** — it catches
missing imports that Vite builds cleanly and only explode at runtime).

## Controls

| | |
|---|---|
| **WASD** | move · **Shift** sprint |
| **Space** | jump — press again in the air to double jump |
| **double-tap WASD** | dodge-roll in that direction (0.22s i-frames) |
| **LMB** | fire (hold for auto) · **R** reload |
| **RMB** | aim — blends the camera to first person, tightens spread 10× |
| **E** | grenade · **Q** heal (1.5s channel, breaks if you move or get hit) |
| **F5** | sticky first-person toggle · **[** **]** look speed (saved between sessions) |
| **M** | music · **B** summon/dismiss a boss (dev) |

---

## What's implemented

### World
Seeded infinite terrain, a **pure function of (seed, coords)** — nothing about it is ever
saved, because it can always be re-derived. No digging or building, ever (D1), which deletes
the hard 30% of a voxel engine: no re-meshing on edit, no lighting propagation, no per-block
delta store.

Chunk generation fills a **3D occupancy grid** from a fill function and the mesher meshes the
grid. Today that function is `solid = y < height(x,z)`; adding caves later is 3D noise in
that one function and the mesher never changes (D15). Face-culled blocky meshing with
per-face shading — the low-poly look comes from hard edges and flat shading, so there's no
asset pipeline. Streaming loads a 7-chunk disc, builds 2 per frame, and drops with hysteresis
so walking a boundary doesn't thrash.

### Difficulty by distance (D8)
Two functions, deliberately different:

- **`tierAt()` is uncapped** and drives every stat, XP value, and elite rate. The world keeps
  getting harder forever — endless levels against finite difficulty means eventually
  outrunning the game.
- **`ringAt()` is capped** at six because we only wrote six names: *the Commons · the Fallows ·
  the Reach · the Waste · the Ashlands · the Deep*. Names and map tint only.

One ring is 260 world units (~32s of sprinting). Mobs gain **+55% HP, +40% damage, +6% speed**
per tier, and elites get a further **+15% HP** per tier on top.

### Camera (D3/D4/D5)
Three states: **EXPLORE** (third person, centred) → **AIM** (blends to first person over
~170ms) → **FP** (sticky toggle). Aiming pulls to first person because over-shoulder free-aim
upward clips the camera and runs the reticle off screen — the BOTW bow pattern.

Orientation comes from yaw/pitch directly, never `lookAt()`. Offsets move the camera's
*position*; they must never rotate it. That's what makes **one raycast — camera through
crosshair — exact in every state**, so third and first person share a single shooting path.

### Combat
- **Gun**: hitscan on a voxel DDA raycast (Amanatides–Woo — can't tunnel a block, cost scales
  with distance not precision). 12 damage, 7.5/s, 18-round mag. **Hip spread 0.022 vs 0.002
  aimed** — accuracy is what ADS buys, which makes D4's camera pull a tactical choice.
- **Dodge**: 0.30s roll, 0.22s i-frames, direction locked for the duration. Committing is what
  makes it a dodge instead of a speed boost. Cancels ADS.
- **Grenade**: ballistic arc, detonates on contact with the world (same `solidAt()` the player
  collides against), 90 damage falling off to 25% at 6.5 units — and **you take half**.
  Max 3, +1 per kill.
- **Heal**: 45 HP over a 1.5s channel that breaks on movement *or* damage. The root is the
  cost; the boss's volley gaps are where you pay it.

### Mobs (D7 — soulless on purpose)
Stats roll from the tier they spawn in; **★elites** at 6% + 6%/tier are bigger, gold, and
much tougher. Three-state brain: **chase** with a per-mob sideways bias so packs arrive as a
spread rather than a stack, **strafe** while the attack cools (the window you shoot into), and
a **committed lunge** that can't course-correct — which is what makes dodging one a read
rather than a coin flip. 14 alive at a time, so cost is bounded by count, not world size.

The substrate goes on settlements later, never on things you kill in three seconds.

### The giant boss (D10)
One reusable rig, re-dressed per tier. 850 HP × (1 + tier), a **glowing core that takes ×2.5**,
and a second phase below 50% with faster, bigger volleys.

**Every source of damage is telegraphed**, and the chain is long on purpose:

> roar → **1.25s charge** (a *state*, not just a sound — the core swells and goes hot, so it
> reads with audio off) → **1.3s ground markers** → impact

Being hit is always "I didn't move", never "I couldn't have known". That's the line between a
boss and a damage tax, and it's what lets the fight be long without being tedious. 60% of
meteors track you (standing still is never safe); the rest rain around the boss.

### Progression (D9)
Endless levels. Kill value scales with **tier**, level cost with **level^1.55**, and their
ratio is the entire curve:

| level | trash needed (tier 0 / 3 / 5) | elites needed (tier 0 / 3 / 5) |
|---|---|---|
| 1 | 4 / 1 / 1 | 1 / 0 / 0 |
| 10 | 148 / 40 / 27 | 21 / 6 / 4 |
| 20 | 433 / 118 / 79 | 62 / 17 / 11 |
| 35 | 1031 / 281 / 187 | 147 / 40 / 27 |

Trash near spawn becomes worthless while packs in the deep still add up, and elites go from
nice to essential. **To keep levelling you must walk further out** — distance *is* the
progression system.

**Levels buy mobility, not bulk.** Max HP never moves (a meteor is as lethal at level 40 as at
level 4 — survival stays about reading telegraphs), but you gain compounding **damage ×1.09**,
**speed ×1.02**, **jump ×1.015** per level, plus **an extra air jump every 10 levels**, and a
full heal on each level-up. Death costs your top level and drops you halfway to earning it
back.

### Sound — synthesized, zero asset files
No downloads, no licences, no megabytes in git. Roars are detuned sawtooths sliding *down*
through a soft-clip curve (falling pitch is what reads as "huge") plus bandpassed noise for
breath; explosions are noise through a collapsing lowpass plus a sub thump; the charge cue is
a rising alarm whose tremolo *accelerates*. All positional — gain by distance, pan by angle —
because with six rocks in the air, hearing which side they're on is how you read the volley.
The looping soundtrack (`public/audio/`) starts on pointer lock, since browsers refuse audio
before a gesture.

### Minimap
Terrain baked north-up offscreen and rotated at draw time (turning your head must not
re-sample the heightfield), shaded by elevation and tinted by ring. Ring boundaries drawn as
circles centred on spawn. Mobs as dots, elites gold, boss always visible clamped to the rim.
**Spawn compass**: a marker in range, a rim arrow with distance when out of range — every
threat is defined by distance from spawn, so which way home is should never be a guess.

---

## Layout

```
src/
  rng.js          mulberry32, hash2, value noise, fbm — EVERY random number
  config.js       every tunable in the game
  state.js        sim state: plain entity records, region-bucketed
  main.js         fixed-step physics clock / per-frame render clock
  world/          gen (the fill function) · mesher · streamer · raycast
  player/         controller · camera · gun · grenade · heal
  mobs/           mobs · boss
  prog/           xp — the curve and every level-scaled stat
  ui/             minimap
  audio/          music · sfx (procedural)
bench/            python: the substrate capacity benchmarks behind PLAN.md §3
```

### Three rules the code holds to

1. **No `Math.random()`** — lint-enforced (D14). An unseedable world can't be replayed, and a
   sim that can't be replayed can't be falsified.
2. **Sim state is not render state.** Gameplay lives in plain records; meshes only *read*
   them. That seam is where a soul brain plugs into the same body a mob uses.
3. **Systems don't learn each other's names.** The gun takes `{id,x,y,z,r}` spheres; grenades
   report a position and radius. `main.js` decides what those touch — so bosses, souls, and
   whatever comes next drop in without editing them.

Tuning is nearly all in `src/config.js`. Look speed is tunable live in-game and persists.

---

## Where this is going

Milestones and gates live in [`PLAN.md §6`](PLAN.md). **M1 is essentially complete** — the
game is playable end to end and has passed its gate ("is it fun bare, with no AI in it?").
The only M1 item outstanding is the **level-up card pick** (1-of-3, D9); levels currently
grant automatic stats as a deliberate stopgap.

The next stretch is the part this project actually exists for:

**1. The bridge + Santāna** *(next)*
`gemma3:4b` runs locally via Ollama and Piper is installed — the whole AI stack is already
here. Rather than porting 28k lines of validated substrate to TypeScript first, expose the
Python lab over localhost and let the browser be a *view* of it. Santāna arrives first: a
presence that follows you, murmurs about what you've both seen, and answers when you type.
She needs none of the substrate, and she de-risks the scariest unknown — voice latency, and
whether a talking companion feels good or annoying.

**2. One town in the Commons**
Ring 0 is already boss-free, so it's the natural home. 20–30 real souls with bonds and
opinions, a no-spawn radius making it a genuine safe space, Markov barks aloud through Piper.
This is where the project becomes the thing it set out to be.

**3. Reputation, pledges, factions**
The town remembers you — fallibly. Promises you type can be broken and gossiped into
wariness (`pledge.py`). Nothing shipped has this.

**4. The TypeScript port**, when other people should be able to play it. It doesn't
disappear, it moves later and gets smaller: by then you'll know which mechanisms the game
actually uses. The keystone-replication gate still stands — it gates *shipping* the port, not
prototyping the design.

**The scarce resource from here is discipline against scope, not ideas** (`ROADMAP.md` §0).
The town is not cheap, and it's the thing worth having.

---

## Honest status

**Verified:** lint and build green; the XP, damage, and boss-HP curves checked numerically;
terrain generation checked by transliterating `rng.js`/`gen.js` to Python (uniform hash,
heights 20–44, nothing clamped, adjacent columns never differ by more than 1 block); the dev
server reports zero client-side runtime errors.

**Not verified by the assistant:** none of it has ever been *looked at*. There was no browser
automation available while this was built — every judgement about how it looks and feels is
the author's. Two runtime crashes shipped and were caught only by reading Vite's client error
log, which is why `no-undef` is now on.

**Not a claim about anyone's inner life.** When the souls arrive, they build the *conditions*
of a self — continuity, memory, drift — and a learning, talking NPC is a more convincing
surface, so it warrants more care in how it's framed to players, not a stronger claim. See
`FINDINGS.md` §7 and `PLAN.md` §7.
