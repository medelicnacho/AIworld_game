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
- **untouchable the whole time** — a guard that expires halfway through is a guard you cannot
  plan around, so however long it lasts, it lasts completely
- one shove on the opening beat, to clear room
- **very little damage** — deliberately the worst way to kill anything you own
- a short cooldown, flat, and **deaf to Haste**: a safety window that scales with gear is a
  telegraph deleter

### How the guard is paid for — and why it stopped being paid for with time

*(Revised 2026-07-27. The original argument is preserved below, because it was right about the
danger and wrong about the remedy.)*

The danger is real and unchanged: a defensive button with high uptime stops being something
you *time* and becomes a state you *live in*, and a player who is never hittable cannot be
reached by meteors, charges, telegraphs, or "being hit is always a failure to move."

The first remedy was to pay for the guard with **time** — stretch the gap until being
untouchable cost you a long, exposed wait. That works, and it charges the wrong currency.
Iron is the one kit that has to *stand in* the fight, so a long wait is spent backpedalling
out of the thing the whole weapon is built to do. It made the faction safe *and* passive.

The remedy now is to pay with **damage**. The spin is the clearly wrong button for killing
things — swinging beats it against anything you could have reached, and it does not make it
up on a crowd either. So it can come round often, because having it costs you your offence
for as long as it runs.

That is a better question to hand a player. *"Can I afford to be safe right now?"* is answered
by looking at a timer. *"Is this worth not attacking for?"* is answered by looking at the
fight.

And it gives the defensive faction the best identity available to it: not the one that cannot
be hurt, but **the one that is best at reading incoming damage** — because the guard is cheap
enough to use freely and useless enough that using it badly still costs you the kill.

> **The floor:** zero damage would be cleaner still, but a spin that does nothing reads as a
> bug the first time you catch something already nearly dead with it. It has to visibly hurt.
> It just must never be the reason anything died.

<details>
<summary>The original argument, kept for the record</summary>

The first proposal was three seconds untouchable on a four second cooldown. That is safe
three seconds out of every four, and with cooldown reduction it finishes *while you are still
spinning* — permanently invulnerable.

For scale, everything else in the game runs at roughly **a quarter uptime**: the dodge is
0.2s safe on a 0.7s cooldown, Whirlwind is 3.6s safe on a 13s cooldown.

Making the untouchable part a **window at the start** turns *press to be safe* into *press at
the right moment* — a skill, and specifically the skill the whole game already teaches.

*What play showed:* a guard that expires mid-spin is unplannable, and a long gap starves the
weapon. Both halves of that lesson are in the current design — the guard covers the whole
spin, and the gap is short. Damage is what pays for it now.

</details>

### Why the cone and the spin need each other

The cone forces you close. The spin is what lets you survive being close. Neither is a
complete kit alone — which is why they are one weapon rather than two features.

### The damage relationship

**Swinging out-damages spinning, and not narrowly.** The cone is bread and butter. The spin
is not a second way to deal damage that happens to be safe — it is a *guard you buy with your
damage*, and the price has to be visible or it is not a price.

The original version had the spin losing on a single target and winning when swamped, so that
the defensive use and the offensive use pointed the same way. That reads well on paper and in
play it meant the answer to being surrounded was always the same button. Now it loses in both
cases. What the spin wins is **the moment** — the shove that opens room, the seconds nothing
can touch you, the ground you cross while untouchable.

The clean read is no longer *cone for damage, spin for crowds.* It is:

> **Cone to kill. Spin to survive, to reposition, or to buy a second.**

Also: **well under Whirlwind.** That is a purchased spell on a long cooldown and it must stay
the heavier hitter, or a free weapon attack outclasses something you paid for.

### Iron needs a way in

Everything in this world lunges, charges from mid-range, or throws fire from a standoff.
Asking someone to close that distance with a melee weapon is a big ask, and if it feels bad
nobody picks the faction however good the spin is.

**Iron should get Dash Strike cheap, or start with it.** Gap-closer plus cone plus spin is a
complete kit; cone plus spin alone is a player who dies on the way in.

---

## Vale — the cannon

A big glowing shell, fired **one at a time** — bam, bam, bam — that bursts into a **wide
circle**. Where the lance clears a crowd along a *line*, this clears one in a *ring*: the
speed faction's answer to being surrounded, thrown from range. It arcs downward as it flies.

**It does NOT hurt you.**

That is deliberate and it is the opposite of the grenade rule. Grenades hurt you, and that is
what makes throwing one a decision. But an explosive you fire like a sidearm would kill you
constantly at close range — and it would punish the exact thing the speed faction is *for*:
being close, moving, taking risks. A weapon that fights its own faction's identity is a bad
weapon.

**So the cost lives entirely in the LEAD.** With no self-damage and a huge blast, travel time
is the only skill the weapon asks for — the shell is deliberately slow, and it curves as it
goes, so landing it on a moving crowd is about reading where they will be. Make it fast and
the whole thing collapses into point-and-delete; the slow speed is load-bearing, not flavour.

> **Design note (changed from the original small-radius plan):** the author chose a big AOE
> cannon on purpose. That makes it the strongest crowd-clear in the game — a fine identity for
> the speed faction — and the balance lever is the shell's *speed*, never its self-damage. If
> it ever feels oppressive, slow the shell further; do not make it hurt you.

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
