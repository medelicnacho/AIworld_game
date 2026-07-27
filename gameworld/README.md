# War Parkour

**A blocky infinite frontier with three clans at war on it. You swear to one, and everything
you own is movement.**

Third-person shooter over read-only voxel terrain. The land climbs into a sky full of
islands, the horizon gets harsher the further you walk from spawn, and every camp, town and
dungeon in the world flies one of three colours. Choosing a colour is the first real decision
in the game, because it decides who you hunt — and it costs you the other two.

The name says what it is. **Parkour**: jumps, wall kicks, dashes, and a sky you climb. **War**:
three armies who shout at each other, towns you can sack, dungeons you can clear.

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

Other scripts: `npm run build` · `npm test` · `npm run lint` (ESLint, with `no-undef` **on** —
it catches missing imports that Vite builds cleanly and only explode at runtime).

## Controls

| | |
|---|---|
| **WASD** | move · **Shift** sprint |
| **Space** | jump — press again in the air, three jumps at level one and more as you level |
| **double-tap WASD** | dodge-roll in that direction · roll into a wall to **kick off it** |
| **LMB** | your faction weapon's main attack · **R** reload |
| **RMB** | its second trigger — the spin, the barrage, the sweep |
| **1–6** | the ability bar · **Q** heal · **E** grenade |
| **RMB (guns)** | aim — blends the camera to first person, tightens spread 10× |
| **F5** | sticky first-person toggle · **[** **]** look speed (saved between sessions) |
| **M** | music · **B** summon/dismiss a boss (dev) |

---

## The three pillars

### 1. Distance is the progression system

There are no zone gates and no level requirements on the map. The world simply gets harder
the further you walk, forever, and the experience worth having is always further out than
where you are standing. **The reward for getting stronger is permission to be somewhere.**

Six named rings — *the Commons · the Fallows · the Reach · the Waste · the Ashlands · the
Deep* — give the gradient a face, because a player has to be able to *see* "I am somewhere
worse now." Past the sixth the names run out and the difficulty does not: the frontier keeps
climbing so that an endless game never runs out of danger to sell you.

Levelling buys **mobility, not bulk**. Your maximum health never moves — a meteor is as lethal
at level forty as at level four — so survival stays a question of reading the fight rather
than of outgrowing it. What you gain is damage, speed, jump height, and another jump in the
air every ten levels. A high-level character is *faster*, not *safer*.

### 2. Everything is movement

Verticality is the second axis the frontier is measured on. The land throws up cliffs, mesas
and canyons; above it hangs a sky of islands, wedges and stepping stones that thickens as it
climbs, so "up" is a direction with content in it and not just a ceiling.

The kit that gets you there is deliberately a **rhythm you can drop, not a ladder you ride**:

- **Air jumps** — three at level one, another every ten levels.
- **The wall kick** — roll into a wall and you go up *and out*, thrown near forty degrees. It
  clears about three blocks and carries you fourteen across, so a wall becomes a way to cross
  a chasm or leave a fight. It spends your roll, which is what keeps it honest.
- **The dash**, which grows with every point of speed you own.

And the movement answers *combat* questions, not just terrain ones: a charge or a lunge can
be **jumped**. That is the seam where "parkour" and "shooter" stop being two words stuck
together.

### 3. The war, and the side you take

Three mob colours are already fighting each other out there. Three factions are sworn against
them in a triangle — no two share an ally or an enemy — and joining one puts you on a colour's
side:

| | |
|---|---|
| **your colour** | its camps and garrisons are your army. They fight beside you. |
| **your enemy** | the only colour that pays reputation when you cut it down. |
| **the third** | neither. Hostile, worth nothing. |

**Reputation is access; points are price.** Climbing the ladder does not hand you gear, it
earns you the *right to buy* it. Neither shortcuts the other — points alone is money-grinding,
reputation alone is kill-counting — so a full kit means playing the way your faction wants for
a long time.

**The cost is the other two.** Rival towns stay safe and still mend you; they simply will not
sell you their kit. You give up two thirds of the best gear in the game by choosing, and that
is the entire point. *A choice with no cost is a menu.*

Each faction's weapon asks a different **question**, which is what makes the choice change how
you fight rather than what you are called:

| | the question it asks |
|---|---|
| **Iron — the cleaver** | *range and commitment.* You have to be there. |
| **Vale — the lobber** | *prediction.* Travel time and splash: where will they be? |
| **Ash — the lance** | *lines.* Where can I stand so this crosses four of them? |

---

## What else is implemented

### The world
Seeded infinite terrain, a **pure function of (seed, coords)** — nothing about it is ever
saved, because it can always be re-derived. No digging or building, ever, which deletes the
hard 30% of a voxel engine. Face-culled blocky meshing with per-face shading: the low-poly
look comes from hard edges and flat shading, so there is no asset pipeline at all.

**Towns** are walled refuges placed by the same pure function. A round wall, one gateway, a
vendor, a healer, and a garrison in the town's war colour. Your own colour's garrison ignores
you. **A rival's garrison is a raid** — it hunts you inside the walls, its traders take up
arms as champions, and killing the last defender **sacks the town** for a boss-sized payout.

**Dungeons** are a different world entered in place: the world is a pure function behind one
door, so a dungeon is simply a *different* pure function behind that same door. Walk in and
the ground changes; movement, sight, meshing and every effect follow without being told.
Costs no memory, needs no difficulty plumbing — a dungeon in a ring-nine mountain is a
ring-nine dungeon — and never touches the chunk streamer.

### Energy — the bar that finally costs something
Eleven buttons was never eleven decisions, because nothing competed for anything. **A cooldown
is a delay, not a cost**: it stops you pressing the same button twice and says nothing about
whether pressing *this* one should mean not pressing *that* one.

So the abilities share one pool. The design is one line long: an opener of two spells leaves
you enough for a third and never enough to repeat the first. The failure state it is built
around is not the empty bar — nobody dies to an empty bar — it is **the plan that needed one
more cast**. Cooldowns survive only where the point is once-per-fight rather than
once-per-rotation.

**Escape is always free.** Sprint, dodge, heal and potions cost nothing. Being punished for a
misjudgement is the point; being punished by *also* losing the tool that would let you survive
it is a death sentence. The bar means exactly one thing: how much damage you can do right now.

And the bar is **six slots against ten abilities**, so carrying a spell costs leaving one home.

### Mobs and bosses
Stats roll from the tier they spawn in; **★elites** are bigger, gold and much tougher. Three
states: **chase** with a sideways bias so packs arrive as a spread rather than a stack,
**strafe** while the attack cools — the window you shoot into — and a **committed lunge** that
cannot course-correct, which is what makes dodging one a read rather than a coin flip.

One reusable boss rig, re-dressed per tier: a glowing core that takes extra, and a second
phase below half health with faster, bigger volleys. **Every source of damage is telegraphed**,
and the chain is long on purpose — roar, then a charge you can *see* because the core swells
and goes hot, then ground markers, then impact.

> Being hit is always "I didn't move", never "I couldn't have known."

That is the line between a boss and a damage tax, and it is what lets a fight be long without
being tedious. It is also a rule with teeth: the Dying Burst affix was cut for breaking it —
an explosion on death is not a difficulty, it is a tax on the one weapon that has to be in
close, and it punished a choice the game asked the player to make.

### The war has a voice
Camps shout. One voice raises a cry and the band takes it up, staggered and overlapping, each
throat pitched differently. Your own colour **hails** you as you pass, because an army that
only screams at enemies and says nothing to its own reads as texture rather than a side you
belong to.

The cries are **positional** — gain by distance, pan by angle — which makes a scream usable as
a telegraph: you can hear how *close* the thing charging you is, and which side it is on. All
of it is baked ahead of time into a cache, so nothing is ever synthesized during a fight and a
built copy speaks with no server behind it.

### Sound, otherwise synthesized
Roars are detuned sawtooths sliding *down* through a soft-clip curve — falling pitch is what
reads as "huge" — plus bandpassed noise for breath. Explosions are noise through a collapsing
lowpass and a sub thump. The charge cue is a rising alarm whose tremolo *accelerates*. No
asset pipeline, no licences, no megabytes in git.

### Minimap
Terrain baked north-up offscreen and rotated at draw time, shaded by elevation and tinted by
ring, with ring boundaries as circles centred on spawn. Mobs as dots, elites gold, the boss
always visible clamped to the rim. Every threat in this game is defined by distance from
spawn, so **which way home is should never be a guess**.

---

## Where this is going

The frontier, the war and the movement are built and they pass their fun gates. **What is
missing is the reason to do any of it twice** — and the plan from here is four steps long.
[`STAGES.md`](STAGES.md) has the tasks and the gate on each; [`PLAN.md`](PLAN.md) has the
decisions and their reasons.

**1. Dungeons pay in verbs.** *(next)*
A dungeon is already a sealed room with a fixed garrison you can genuinely finish. Clearing
one currently pays **nothing at all**. It should pay the one reward in this game that changes
how you play rather than what your numbers say: **a rank on a spell you own**.

The condition on a rank is that it has to change *where you stand*, not how big the number is.
A dash that punches *through* a body instead of stopping at it is a rank. A dash that goes
further is a stat with a roman numeral on it.

Gold buys numbers. Dungeons buy verbs. A player should learn that split in one run.

**2. Dungeons become places.** One room proved the door works. Layout, hazards and a shape
worth learning are what make it somewhere you go rather than an arena with a lid.

**3. Performance.** Measured on the *worst* frame, not the average — an average frame time is
a number that hides exactly the thing the player feels. The dungeon helps here rather than
hurting: an interior is a bounded space where streaming can stop, so it is the one venue in
the game where a good frame can be *guaranteed*, which makes it the right home for the
densest fights.

**4. Perfect what is here, and ship it.** Itch first, in the browser. Steam later, as a
desktop build.

---

## What was cut, and why

This project began as a frontier whose real content was going to be **settlements of NPCs
running a live social substrate** — souls who bond, feud, starve, remember you fallibly, and
get on with their lives while you are away — plus a companion who followed you and spoke.
That layer is **cut**, and the reasons are worth keeping written down.

**It could not ship to the audience the game is aimed at.** Live souls need a local Python
process and a local language model running beside the browser. An itch build has neither. The
war cries only speak in a built copy because they are *baked ahead of time*, and baking is
exactly the thing emergence cannot be. The feature would have been experienced by an audience
of one.

**The game had already voted.** The plan's own wager was that the shooting should stay
deliberately simple because the aliveness was the content. What actually got built over the
following month was three faction weapons that ask different questions, a shared energy
economy, a war with sides, sky islands and a wall kick. The shooting did not stay simple — it
became the game. That is discovery, not failure, but a plan that does not admit it keeps
charging rent: it justifies deferring reward work forever on the grounds that the *real*
content is still coming.

**And the two halves teach opposite habits.** A living town needs a player who slows down and
stays. War Parkour teaches you to never stop moving, read the colour, and choose the fight.
The town shape that *does* fit this game is the one already in it: a place with a garrison,
that you can raid, sack, or belong to.

**What survives the cut:** the war's voice. Baked cries, taunts and hails are authored content
that ships and does real telegraph work — they were never the emergent layer, they just used
the same pipe.

---

## Layout

```
src/
  rng.js          mulberry32, hash2, value noise, fbm — EVERY random number
  config.js       every tunable in the game, and the reasoning beside it
  state.js        sim state: plain entity records, region-bucketed
  main.js         fixed-step physics clock / per-frame render clock
  world/          gen · mesher · streamer · raycast · sanctuary · dungeon · events
  player/         controller · camera · gun · grenade · heal · abilities
  mobs/           mobs · boss · affixes · warcry
  town/           raid · villagers · chat · voice
  prog/           xp · gear · factions · save
  ui/             minimap · shop · inventory · healthbars · nameplates
  audio/          music · sfx (procedural)
```

### Three rules the code holds to

1. **No `Math.random()`** — lint-enforced. An unseedable world cannot be replayed, and a world
   that cannot be replayed cannot be tested.
2. **Sim state is not render state.** Gameplay lives in plain records; meshes only *read* them.
3. **Systems do not learn each other's names.** The gun takes spheres; grenades report a
   position and a radius. `main.js` decides what those touch — so bosses, dungeons and
   whatever comes next drop in without editing them.

Tuning is nearly all in `src/config.js`, where every number is written down beside the
argument for it. **When you change a number, change the argument** — a constant with a stale
essay beside it is worse than a bare constant, because the essay will be believed.

---

## Honest status

**Verified:** the full test suite and lint are green. The XP, damage and boss-health curves
check out numerically. Terrain generation was verified by transliterating the generator to
Python — heights land in range, nothing clamps, and adjacent columns never differ by more than
one block.

**Not verified:** how it *looks*. Almost every judgement about feel in this repo is the
author's, made in play. That is the right authority for feel and the wrong one for bugs, which
is why the lint rule that catches runtime-only crashes is switched on and stays on.
