# WAR PARKOUR — the plan

*The decisions, with the reasons recorded so they can be re-opened honestly. This file is
**why**; [`README.md`](README.md) is **what**; [`STAGES.md`](STAGES.md) is **when**.*

---

## 1. The game, in one paragraph

A blocky infinite frontier. Third person. The land climbs into a sky you can reach, and the
danger climbs with distance from spawn, forever. Three clans are at war on it; you swear to
one, which decides who you hunt and costs you the other two's gear. Everything you own is
movement — jumps, a dash, a wall kick, a roll — and everything you cast comes out of one
shared bar, so a fight is a budget rather than a rotation. Towns can be raided and sacked.
Dungeons are sealed rooms you can genuinely finish, and finishing one is how you get a spell
that changes what you can do.

**The wager:** the moment-to-moment — moving and fighting — has to be fun on a bare hillside
with nothing else in the game. It is, and that was tested in play rather than assumed. What
the game is missing is not depth of verb. It is a **reason to do it again**.

---

## 2. Decisions

| # | decision | call | why (and what would re-open it) |
|---|---|---|---|
| D1 | terrain | **read-only**, seeded heightfield, blocky low-poly mesh. No dig/build, ever. | Editing is the hard 30% of a voxel engine — re-meshing on change, light propagation, per-block delta storage. Read-only makes terrain a *pure function of (seed, coords)*, so nothing about it is ever saved. Re-opens only if building becomes a core verb, which is a different game. |
| D2 | engine | **pure three.js**, chunk streaming. | The alternative's value was solved *editing*. D1 deleted its reason to exist. |
| D3 | camera | **third person over-shoulder** default. | Boss legibility, dodge spacing needs body-awareness, telegraph reading. Every giant-boss game is third person for these reasons. |
| D4 | aiming | **three camera states: EXPLORE → AIM → (optional) FP toggle**, blending over ~170ms. | Over-shoulder free-aim upward clips the camera and runs the reticle off screen. Snapping to first person on aim is the shipped BOTW bow pattern. |
| D5 | aiming math | **one raycast, camera → crosshair, in every state.** | Not two shooting systems — one raycast, a camera offset, and a cone width. |
| D6 | combat | **hitscan guns + a dodge-roll with i-frames**, then a faction weapon that is not a gun. | Hitscan is a raycast: no ballistics, no projectile pooling. Enemies need only chase / strafe / lunge. |
| D7 | mobs | **soulless.** Stats scale from the tier they spawn in; ★elites; rollable affixes at depth. | A brain on a thing you kill in three seconds is pure waste — memory, CPU, and design surface. |
| D8 | difficulty | **legible named rings**, not an invisible gradient. | Players must be able to *see* "I am somewhere worse now." Valheim's real lesson: even it scales by biome, not by raw distance. |
| D9 | progression | **endless levels**, buying mobility rather than bulk. Death costs your top level. | Max HP that never moves keeps survival about reading the fight. A high-level character should be *faster*, not *safer*, or the telegraph rules quietly stop mattering. |
| D10 | bosses | **one reusable giant rig**, re-dressed per ring — scale, texture, affix, arena. | Procedurally generating boss *mechanics* is a tarpit. Procedurally generating *dressing* over a hand-authored skeleton is how you get variety without authoring twelve fights. |
| D11 | loot | field kills are lottery tickets; **bosses are the guarantee** and never drop something you would sell unread. | A ticket that never pays is a wasted slot; one that pays about once an evening turns every ordinary kill into a small held breath. That feeling is worth more than the item. |
| D14 | PRNG | **seeded, everywhere, from commit 1.** `Math.random()` is banned by lint. | An unseedable world cannot be replayed, and a world that cannot be replayed cannot be tested. |
| D15 | caves | **no caves or overhangs.** Verticality is cliffs, mesas, canyons — and the **sky**. Interiors are **instanced scenes behind a door**, never terrain features. | Caves are *depth*; the whole progression axis is *distance*, so caves compete with the ring gradient instead of serving it. They are also the worst possible venue for a giant boss, which needs open, lit, legible arenas. Instanced dungeons buy most of what caves buy at a fraction of the cost and never touch the chunk streamer. |
| D16 | mob leashing | hostile bands are **free within their ring and one ring either side**, never further inward on their own. Breakouts are **telegraphed events** only. | Free migration breaks D8's legibility promise: a deep-ring warband at spawn kills a new player who had no way to read the threat, and that reads as a bug rather than as a story. |
| **D17** | **factions** | **three, in a triangle. Sworn against one mob colour each. Chosen at character creation.** | This is the only *subtractive* decision in a game where everything else is additive — the first thing you have ever had to give up to get something else, which is what makes a character sheet into a build. Hanging it on a mob colour means joining does not change what you are called, it changes **who you hunt**: you start reading camps at a distance and choosing fights instead of killing whatever is nearest. |
| **D18** | **ability cost** | **one shared energy pool**, replacing per-spell cooldowns rather than sitting behind them. | A cooldown is a *delay*, not a cost. A cost behind a longer cooldown is invisible — whichever is longer is the only one anyone feels. Long cooldowns survive only where the point is once-per-fight. **Escape is always free**, because being punished by losing the tool that would let you survive a mistake is a death sentence. |
| **D19** | **dungeon rewards** | **dungeons are the only source of spell ranks. Gold buys numbers; dungeons buy verbs.** | A dungeon sharing the field's loot table is a room with mobs in it, and the field already has mobs. The reward has to be something the frontier structurally *cannot* give, or the door is decoration. See §4. |

### Cut, and kept here on purpose

| # | was | why it is gone |
|---|---|---|
| D12 | substrate on settlements — 20–40 souls per town who bond, feud, starve, migrate and remember | **Could not ship.** Live souls need a local Python process and a local language model beside the browser; a browser build has neither. The war cries only speak in a built copy because they are *baked ahead of time*, and baking is precisely what emergence cannot be. It would have been a feature with an audience of one. **Also:** a living town needs a player who slows down and stays, and this game teaches the opposite. The town shape that fits is the one already built — a place with a garrison, that you can raid, sack, or belong to. |
| D13 | Santāna — a companion who follows you, speaks aloud, and remembers your last life | Same dependency, same reason. |

**What survived both:** the voice *pipeline*. Baked cries, taunts and hails are authored
content that ships and does real telegraph work — you can hear how close a charging thing is
and which side it is on. They were never the emergent layer; they only used the same pipe.

---

## 3. Architecture

```
main thread    three.js render · player controller · camera FSM (EXPLORE/AIM/FP)
               · mob brains · hitscan raycasts · the fixed-step physics clock
worldgen       a pure function of (seed, x, y, z) behind ONE door: blockAt
               — terrain, mountains, sky islands and DUNGEONS are all the same door
offline        Piper bakes the war-cry cache once; the game only ever plays what is baked
```

The single load-bearing idea: **everything the world is, is a pure function behind one door.**
A dungeon is not a parallel voxel store with its own collider and its own mesher — that would
be four systems taught to work a second way, which is four chances for them to disagree. It is
a *different fill function* behind the same door. Walk in and the streamer rebuilds; movement,
sight, meshing and every effect follow without being told, because none of them ever knew
where blocks came from.

Two things fall out for free: an instance costs one small object and no memory, and a dungeon
generated at its gate's own coordinates is automatically the difficulty of the ring it was
found in, with no special case anywhere.

---

## 4. The open problem: reward

Everything in §2 is built and passes its gate. The frontier is legible, the movement is fun
bare, the combat asks real questions. **The game still has no reason to do any of it twice**,
and that is now the whole problem.

The reward structure today pays in **numbers**: armour, damage percentages, another level.
Numbers do not change a single decision a player makes — they change how long the same
decision takes. The one reward in the game that changes *how you play* is a spell, and it is
currently the rarest thing a boss can give.

**That ratio is backwards, and correcting it is the plan.**

Dungeons are the vehicle because a dungeon is the one place in this world that can offer
something the frontier structurally cannot: a **sealed, finishable, fixed-size** fight. The
frontier is endless by construction, so it can never say *you finished*. A room can.

### The rule a spell rank has to obey

> **A rank changes where you stand. A stat changes how long you stand there.**

A dash that punches *through* a body instead of stopping at it is a rank — it changes the
geometry of every fight you use it in. A dash that travels further is a stat wearing a roman
numeral. If a rank cannot be described without naming a number, it is not a rank yet.

This is the same instinct that made the three faction weapons work. Those weapons are good
because they ask different *questions*, not because they have different damage figures. Ranks
should be pointed at the half of the game that is still paying in adjectives.

### And ranks live in exactly one place

Ranks currently come from the vendor. If they also come from dungeons, both sources are
diluted and neither teaches anything. **Pull them out of the shop.** Gold buys numbers,
dungeons buy verbs — a split a player learns in one run and never has to be told.

---

## 5. Milestones

Each is a playable game, and each has a **gate**: a question that can fail. If a gate fails,
stop and fix it rather than building the next thing on top of it.

| | milestone | gate |
|---|---|---|
| **M1** | the frontier — terrain, guns, dodge, mobs, boss, levels | *Is it fun bare, with nothing else in it?* — **PASSED** |
| **M2** | verticality — the sky, air jumps, the wall kick | *Is going up worth doing for its own sake?* — **PASSED** |
| **M3** | the war — three factions, faction weapons, camps, raids, sacking | *Does choosing a side change how you play, not just what you are called?* — **PASSED** |
| **M4** | **the dungeon pays** — clearing one grants a spell rank | *Do you walk past a fight you could win, because you would rather get to the door?* |
| **M5** | **the dungeon is a place** — layout, hazards, a shape worth learning | *Would you re-enter one you had already cleared?* |
| **M6** | **it runs** — the worst frame, not the average | *Does it hold up on a machine that is not this one?* |
| **M7** | **it ships** — itch, in the browser | *Does a stranger get to their first sacked town without being told how?* |

M4's gate is the sharp one and it is worded that way on purpose. A reward is only real if it
**changes what a player chooses to do**. If a dungeon rank is nice-to-have, players will keep
killing whatever is nearest and the door will be scenery.

---

## 6. Rules of the build

1. **One number, one argument.** Every constant lives beside the reasoning for it. When you
   change the number, change the argument — a stale essay is worse than a bare constant,
   because the essay will be believed.
2. **Ratios must be re-derived, not re-tuned.** Some numbers are pinned to other numbers
   rather than to a feel. When their partner moves, they move, or the design they encode
   quietly inverts.
3. **A gate that passed is closed.** Feel work has no natural end and there is always one more
   number. When something passes, protect it and go build the next thing.
4. **Cut things that fail their own rules.** An affix that taxes one weapon's required range is
   not difficulty. A reward nobody re-reads is not a reward. The log should have removals in it.
5. **Measure the worst, not the mean.** An average frame time hides exactly the thing a player
   feels.

---

## 7. Open questions

- **How many ranks per spell, and do they stack or replace?** Replacing is legible and cheap;
  stacking is the thing players screenshot. Undecided until M4 has one rank in play.
- **Does a cleared dungeon stay cleared forever?** Permanent means the world runs out of them.
  Resetting means "cleared" meant nothing. A middle answer probably exists in *what* it pays
  the second time.
- **Does the neutral third colour earn its place?** It is hostile and worth nothing, which
  teaches a player to route around it — avoidance, in a game about choosing fights. Either it
  pays something, or it fights differently, or it should go.
- **Is character creation too early for the faction choice?** The player has held nothing. Ring
  0 is boss-free and safe by design, which is a tutorial asking to exist: carry all three
  through it, swear at the first gate. The cost of giving up two only lands if you have felt
  what you are giving up.
