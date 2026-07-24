# Faction weapons

*The design record for the three faction weapons, settled in conversation before any of it
was built. Written down because the reasoning is the part that gets lost — the numbers are
easy to re-derive and the arguments are not.*

---

## Why these exist

The four starting guns are all the same verb. Point at the thing, click, a number happens.
They differ by rate, magazine and damage — which are adjectives, not verbs. A player who
switches from the Repeater to the Ripper is doing the same thing slightly faster.

These three ask genuinely different questions:

| | the question it asks |
|---|---|
| **Iron — the cleaver** | *range and commitment.* You have to be there. |
| **Vale — the lobber** | *prediction.* Travel time and splash: where will they be? |
| **Ash — the lance** | *lines.* Where can I stand so this crosses four of them? |

That is what makes the faction choice change how you **fight** rather than what you are
called. It is the whole reason the faction layer was built.

**They are sold by your quartermaster at the bottom rung**, for a heavy price in points. Not
gated behind reputation — the weapon IS the identity, and it should land the day you join,
not three hours later.

---

## Iron — melee cleaver, and the spin

**Left click.** A cone in front of you. Hits everything inside it, knocks them back. Your
main damage.

**Right click.** A spin, on a cooldown.

- ~2.5 seconds of spinning
- **untouchable for the first ~0.6s only**
- decent damage all around you, but **less per second than swinging**
- one shove on the opening beat, to clear room
- 5s cooldown, floored at 2.5s no matter how much Haste is stacked

### Why the invulnerability is a window, not the whole spin

The first proposal was three seconds untouchable on a four second cooldown. That is safe
three seconds out of every four, and with cooldown reduction it finishes *while you are still
spinning* — permanently invulnerable. That deletes the game: meteors, charges, telegraphs and
"being hit is always a failure to move" cannot reach a player who is never hittable.

For scale, everything else in the game runs at roughly **a quarter uptime**: the dodge is
0.2s safe on a 0.7s cooldown, Whirlwind is 3.6s safe on a 13s cooldown.

Making the untouchable part a **window at the start** turns *press to be safe* into *press at
the right moment* — a skill, and specifically the skill the whole game already teaches: read
the thing coming at you and answer it. Miss the timing and you have spent the move, you are
mid-spin, and the meteor still lands.

That also gives the defensive faction the best identity available to it: not the one that
cannot be hurt, but **the one that is best at reading incoming damage**.

### Why the cone and the spin need each other

The cone forces you close. The spin is what lets you survive being close. Neither is a
complete kit alone — which is why they are one weapon rather than two features.

### The damage relationship

**Swinging must out-damage spinning over time.** The cone is bread and butter; the spin costs
a cooldown, so if it also paid more damage it would become the whole rotation.

But the cone hits **in front** and the spin hits **all around**. So the spin loses on a single
target and wins when you are swamped — which is exactly when you also want it for the
knockback and the untouchable window. The defensive use and the offensive use point the same
way, which makes it a clean read: *cone for damage, spin for crowds and for the moment
something is about to land on you.*

Also: **well under Whirlwind.** That is a purchased spell on a long cooldown and it should
stay the heavier hitter, or a free weapon attack outclasses something you paid for.

### Iron needs a way in

Everything in this world lunges, charges from mid-range, or throws fire from a standoff.
Asking someone to close that distance with a melee weapon is a big ask, and if it feels bad
nobody picks the faction however good the spin is.

**Iron should get Dash Strike cheap, or start with it.** Gap-closer plus cone plus spin is a
complete kit; cone plus spin alone is a player who dies on the way in.

---

## Vale — the lobber

A big red ball, fired **one at a time like a pistol** — bam, bam, bam. Explodes on impact for
splash damage. Aiming tightens the accuracy.

**It does NOT hurt you.**

That is deliberate and it is the opposite of the grenade rule. Grenades hurt you, and that is
what makes throwing one a decision. But an explosive you fire like a sidearm would kill you
constantly at close range — and it would punish the exact thing the speed faction is *for*:
being close, moving, taking risks. A weapon that fights its own faction's identity is a bad
weapon.

**So the cost has to live somewhere else.** Not danger — *difficulty*. A small blast radius
and real travel time, so hitting a moving target is about **prediction** rather than about
bravery. If it ends up feeling like a strictly better grenade, that is the dial to turn: make
the ball slower and the splash tighter, never make it hurt you.

---

## Ash — the lance

A sustained beam. **Pierces** — it does not stop at the first thing it touches. Hold it down
and it burns everything in a line. Stronger while aiming.

### It needs a cost or it eats every other weapon

Sustained damage that hits everything in a line is already the best crowd answer in the game —
better than Ring of Fire, better than the MG. If it also just *runs*, nobody uses anything
else, including the other two faction weapons.

**It overheats.** Hold it and heat builds; hold it too long and it cuts out and has to cool.
That turns "hold the button" into **managing the beam**, which is a skill, and it keeps the
weapon exciting rather than dominant.

---

## The interface

Right click is now a real ability on some weapons, so **its cooldown has to be visible** —
shown beside the ammo readout, where your eyes already are for weapon state. A cooldown you
cannot see is a cooldown you do not use.

---

## What was deliberately deferred

- **The mount and the legendary weapon.** They sit on top of the reputation ladder and cannot
  be priced sensibly until the ladder has been climbed once and its pace is known.
- **Making faction weapons upgrade.** One version each first. Ranks are cheap to add later and
  impossible to tune before the base has been played.
