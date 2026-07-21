"""Dyadic bonds: a self's RELATIONSHIP to another self.

The scalar `affinity` in agent.py moves (near-)symmetrically and forgets -- it
cannot hold the three things that make a relationship readable as drama:

  ASYMMETRY  A may love B more than B loves A (a bond is directional, mine→them).
  INERTIA    loyalty resists a single contradicting event -- a deep bond discounts
             one betrayal instead of collapsing.
  MEMORY     a betrayal is REMEMBERED: it erodes the very buffer that softened it,
             so repeated betrayals eventually shatter even a loyal bond.

A `Bond` adds those. The mechanics are pure, deterministic state (no LLM) -- the
falsifiable substrate, like the affect trajectory in experiment_affect. An optional
speech layer (`describe`) can voice the bond so it is legible, but the core is here.

This is the minimal Stage-2 unit -- relating to ANOTHER self -- on top of the
proven Stage-1 self (affect + self-regulation). Built as an opt-in layer
(Agent.bond_enabled, Agent.bonds) so the existing affinity graph, viewer, and tests
are untouched.
"""

from __future__ import annotations

from dataclasses import dataclass

BOND_WARM = 0.15        # trust gained per warm interaction (toward the +1 ceiling)
HISTORY_GAIN = 0.10     # shared positive history accrued per warm interaction (the buffer)
LOYALTY = 1.5           # how strongly history buffers a betrayal (resists evidence)
BETRAYAL_ERODES = 0.5   # a betrayal damages the very buffer that softened it (memory)

# --- bonding on a SHARED VIEW (Agent.bond_creed, default off) -------------------------------
# The bond signal in hear() is `0.3 * their_mood * my_mood + semantic_warmth`, and a big town
# forces the Jaccard fallback (santana_app/run.py), which zeroes the warmth term outright. So
# in the arena a bond accretes on MOOD PRODUCT ALONE: two souls who are both in decent spirits
# warm to each other no matter what either believes. Most souls are in decent spirits most of
# the time, so nearly every pair warms -- measured on the live arena, a median 114 warm bonds
# per soul out of 162, which is §5.26's "every soul ends up loving every other" arriving by
# a route nobody was watching.
#
# That universal warmth is what makes the kin-pull an inescapable gravity well (the schism
# walk's post-mortem: a leaver's escape push was 0.37x the summed pull holding it in). Rather
# than fight that force downstream in the movement physics -- two attempts, both failed and
# recorded in world/sim.py -- this makes disagreement matter where the pull is BORN: you do
# not come to love someone you fundamentally disagree with, however cheerful you both are.
CREED = 0.30            # how hard a shared/opposed view moves the bond signal, against the
                        # mood-product term's own 0.30 ceiling -- equal footing, not a veto


def creed_lean(sim: float, bound: float) -> float:
    """Signed agreement in [-1, 1]: +1 could not agree more, 0 exactly at my engagement
    bound, -1 opposites. Same shape the schism walk uses on the movement side, so a soul's
    bonding and its bearing read the SAME line the same way."""
    gap = sim - bound
    lean = gap / (1.0 - bound) if gap >= 0 else gap / (1.0 + bound)
    return max(-1.0, min(1.0, lean))


@dataclass
class Bond:
    """One self's directional bond toward another. The other keeps its own."""
    trust: float = 0.0      # -1 (enmity) .. +1 (love); MINE toward them
    history: float = 0.0    # accumulated shared warmth -> inertia / loyalty buffer
    wounds: int = 0         # remembered betrayals
    last_event: str = ""

    def warm(self, amount: float = 1.0) -> None:
        """A warm / cooperative exchange: trust rises toward the ceiling (slower the
        closer it already is) and shared history -- the loyalty buffer -- accrues."""
        a = max(0.0, amount)
        self.trust = max(-1.0, min(1.0, self.trust + BOND_WARM * a * (1.0 - self.trust)))
        self.history += HISTORY_GAIN * a
        self.last_event = "warmth"

    def feel(self, signal: float) -> None:
        """A continuous, ambient update from one heard line's warmth (live sim). A
        warm line builds trust + history like a small warm exchange; a cold line
        cools trust WITHOUT the wound/erosion of a true betrayal (betray() is the
        discrete, remembered event). This is how a bond accretes over a conversation."""
        if signal > 0.05:
            self.warm(signal)
        elif signal < 0.0:
            self.trust = max(-1.0, self.trust + 0.10 * signal)   # mild cooling, no wound
            self.last_event = "coolness"
        # a NEUTRAL line is no event at all -- it must not stamp warmth (a wound would
        # otherwise read as "come past" after one indifferent exchange)

    def betray(self, severity: float = 0.6) -> float:
        """A betrayal. Loyalty (accumulated history) ABSORBS part of the blow, so a
        deep bond barely flinches at one betrayal while a shallow one shatters. But
        the betrayal is REMEMBERED -- it halves the buffer and tallies a wound, so
        a second and third betrayal land progressively harder until even a loyal
        bond breaks into enmity. Returns the effective trust drop."""
        buffered = severity / (1.0 + LOYALTY * self.history)
        self.trust = max(-1.0, self.trust - buffered)
        self.history *= (1.0 - BETRAYAL_ERODES)
        self.wounds += 1
        self.last_event = "betrayal"
        return buffered


def describe(bond: Bond, name: str) -> str:
    """Voice the bond for a prompt, so a self can SPEAK its relationship (the
    legibility layer -- proves the bond isn't decorative when fed to a model)."""
    t = bond.trust
    if t >= 0.5:
        s = f"You deeply trust and love {name}"
    elif t >= 0.15:
        s = f"You feel warmly toward {name}"
    elif t > -0.15:
        s = f"You feel little toward {name}, either way"
    elif t > -0.5:
        s = f"You are wary of {name} and carry a hurt from them"
    else:
        s = f"You feel betrayed by {name} and want nothing to do with them"
    if bond.wounds:
        if bond.trust >= 0.25 and bond.last_event == "warmth":
            # a wound met and moved past reads as a SCAR, not an open charge -- but only once
            # real warmth has happened SINCE it (caught by the falsifier: without that, the
            # loyalty buffer made her read "come past it" seconds after the knife)
            times = "once" if bond.wounds == 1 else f"{bond.wounds} times"
            s += f" (they hurt you {times} before, and you have come past it)"
        else:
            s += f" (they have wounded you {bond.wounds} time{'s' if bond.wounds > 1 else ''})"
    return s + "."


# --- the person-model gate: what counts as someone speaking OF THEMSELVES ----------------
FIRST_PERSON = (" i am ", " i'm ", " im ", " i like ", " i love ", " i enjoy ", " i want ",
                " i hope ", " i feel ", " i work ", " i live ", " my name ", " i made ",
                " i built ", " i lost ", " i keep ")


def about_themselves(text: str) -> bool:
    """True when a line is first-person self-disclosure -- the raw material of coming to
    KNOW someone (the person-model in Agent.known_of / Santana.known_of_them)."""
    low = f" {text.lower()} "
    return any(k in low for k in FIRST_PERSON)
