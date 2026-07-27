# STAGES — the build order

*Each stage has a goal, a task list, and a **gate**: a question that can fail. If a gate fails,
stop and fix it rather than building the next stage on top of it. [`PLAN.md`](PLAN.md) holds
the decisions behind these; this file is the order they happen in.*

**Where we are: Stage 2.** The frontier, the movement and the war are built and passed their
gates. The reward layer does not exist.

---

## Done

### Stage 0 — the voice spike ✅ *(2026-07-22)*
Proved a spoken line could land fast enough to be part of a fight rather than an interruption.

### Stage 1 — the bridge ✅ *(2026-07-22)*
A local pipe from the browser to the voice tooling, built to the rule that **the bridge is an
enhancement, never a dependency** — if it is not running, the game behaves exactly as it did
before it existed.

That rule is why both stages survived the substrate cut. What they left behind is the **bake
pipeline**: the war's cries, taunts and hails are synthesized once, cached, and played from the
cache forever after. Nothing is synthesized during a fight, and a built copy speaks with no
server behind it.

### Stage A — the frontier ✅
Terrain, streaming, guns, the dodge, mobs, the boss rig, endless levels.
**Gate: is it fun bare, with nothing else in it?** — passed in play.

### Stage B — verticality ✅ *(2026-07-26)*
The sky filled with islands, wedges and stepping stones; air jumps; the wall kick.
**Gate: is going up worth doing for its own sake?** — passed.

### Stage C — the war ✅ *(2026-07-27)*
Three factions in a triangle, each sworn against one mob colour. A faction weapon per side,
each asking a different question. Camps, garrisons, town raids, sacking. The shared energy bar
that turned ten buttons into a budget.
**Gate: does choosing a side change how you play, not just what you are called?** — passed.

---

## Stage 2 — the dungeon pays ⏱ ~1 week ← **HERE**

**The hole this fills:** a dungeon is already a sealed room holding a fixed garrison you can
genuinely finish — and clearing it pays **nothing at all**. The code that knows you finished is
written and never called. Everything else in the game rewards you in numbers, and numbers do
not change what a player decides to do; they change how long the same decision takes.

This is the smallest change in the project with the largest effect on whether anyone plays it
twice.

- [ ] **Wire the clear.** When the last defender falls, the game should say so, loudly. A
      finishable fight that ends in silence teaches the player that finishing it did not matter.
- [ ] **One spell rank, granted on clear.** Start with a single one, in play, before designing a
      table of them. The first one in a real fight answers questions the table cannot.
- [ ] **Pull ranks out of the vendor.** Two sources for one reward dilute both and teach
      neither. Gold buys numbers; dungeons buy verbs — a split a player should learn in one run
      and never have to be told.
- [ ] **Price the door from outside it.** A dungeon a player cannot price is a dungeon they walk
      past. The gate should say what ring it is and that a rank is behind it.
- [ ] **Decide what a second clear pays.** Not necessarily nothing — but not the same thing.

### The rule every rank has to obey

> **A rank changes where you stand. A stat changes how long you stand there.**

A dash that punches *through* a body rather than stopping at it is a rank: it changes the
geometry of every fight you spend it in. A dash that travels further is a stat wearing a roman
numeral. **If you cannot describe the rank without naming a number, it is not a rank yet.**

This is the same instinct that made the three faction weapons good. They differ by the
*question* they ask, not by their damage figures — and that is exactly what the reward half of
the game is still missing.

**Gate:** *do you walk past a fight you could win, because you would rather get to the door?*

That wording is deliberate. A reward is only real if it changes what a player **chooses to do**.
If the rank is merely nice to have, players keep killing whatever is nearest and the door is
scenery.

---

## Stage 3 — the dungeon is a place ⏱ ~1–2 weeks

One room proved the door works. A room is not a destination.

- [ ] **Layout** — more than one space, connected, with a shape you can learn and later
      remember. It does not need to be large. It needs to be *somewhere*, not *a lid*.
- [ ] **A reason to move through it** rather than hold one corner. The garrison already arrives
      in knots, which makes it a series of fights; the room should make position matter between
      them.
- [ ] **Verticality inside.** This is a parkour game and its interiors are flat. The one place
      with a guaranteed frame budget is the wrong place to stop jumping.
- [ ] **Hazards that are read, not absorbed** — the same telegraph rule as everything else in
      the game. Being hit is always "I didn't move", never "I couldn't have known".
- [ ] **An end that feels like an end.** Something at the back.

**Gate:** *would you re-enter one you had already cleared?*

---

## Stage 4 — it runs ⏱ ~1 week

- [ ] **Measure the worst frame, not the average.** An average frame time hides exactly the
      thing a player feels. This is already the standing rule; make it the standing *number*.
- [ ] **Find the spikes and name them.** Streaming, meshing, mob counts, effects. A spike with a
      name is a bug; a spike without one is a mood.
- [ ] **Use the dungeon as the control.** An interior is a bounded space where streaming can
      stop entirely — the one venue where a good frame can be *guaranteed*. That makes it both
      the right home for the densest fights and the cleanest baseline to measure the open world
      against.
- [ ] **Test on a machine that is not this one.**

**Gate:** *does it hold up somewhere other than the machine it was written on?*

---

## Stage 5 — perfect it, and ship ⏱ ~2–3 weeks

The polish stage is the one with no natural end, so it gets its finish line written **before**
it starts rather than after.

- [ ] **A stranger's first hour.** Watch someone who has never seen it play. Every place they
      stop, hesitate, or ask a question is the list — and here it is the only list that counts.
- [ ] **The faction choice, reconsidered.** It is made before the player has held anything, and
      the current fix is longer descriptions. Reading three paragraphs about weapons you have
      never fired is a quiz, not a choice. Ring 0 is boss-free and safe by design, which is a
      tutorial asking to exist: carry all three through it, swear at the first gate. Giving up
      two only means something if you have felt what you gave up.
- [ ] **The difficulty picker, moved.** Asking someone to rate their own skill before they have
      touched the controls is a test. The same question offered after a few deaths is a
      kindness.
- [ ] **The level-up card pick** (1-of-3). Levels currently grant automatic stats as a stopgap,
      which makes levelling the one place progression hands you something without asking
      anything.
- [ ] **Names for rings past the sixth**, so the frontier reads forever instead of running out
      of language before it runs out of danger.
- [ ] **Build, package, itch.**

**Gate:** *does a stranger get to their first sacked town without being told how?*

> **The finish line, stated now:** when that gate passes, the game is done, and the next thing
> is a desktop build — not another pass on the numbers. This project's standing failure mode is
> re-tuning a system that already passed its gate, because feel work is the most rewarding
> thing to keep touching and it has no natural end. **Stage 5 ends when a stranger can play it,
> not when it stops being improvable.**

---

## Side quests — small, do when you want a break

- [ ] Boss variety: a second attack set on the same rig
- [ ] Guns dropping from bosses with rolled stats
- [ ] More elite affixes — each must change *how* you fight it, never just its numbers
- [ ] The neutral third mob colour: make it pay something, make it fight differently, or cut it.
      Hostile and worth nothing teaches players to route around it, which trains avoidance in a
      game about choosing fights.

---

## The order, and why

**Reward before layout.** A dungeon with the field's loot table is a room with mobs in it, and
the field already has mobs — so drawing rooms before deciding what they pay is building a
container for something that does not exist yet. Decide what a dungeon gives that the frontier
structurally *cannot*, then build the place worth going there for.

**Layout before performance.** Optimising a room you are about to redesign measures the wrong
room.

**Performance before polish**, because polish on a game that stutters is paint on a car with no
engine — and because frame rate is the one problem a player cannot be talked out of.

**The failure mode to watch:** every stage here is less immediately fun to build than adding
another verb. The verbs are done. The scarce resource from here is discipline against scope,
not ideas.
