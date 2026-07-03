"""allegiance.py -- Phase B: will this soul stand WITH you, apart from you, or AGAINST you?

The game's spine, and the whole point of everything underneath it: the decision is
DERIVED, never scored. No loyalty slider exists anywhere -- a soul reads what its life
has actually made true and answers:

    trust        the bond you built with THIS soul (its pace, its history, its wounds)
    reputation   what the town has come to expect of you (direct + pledged + witnessed
                 + gossiped: the three validated karma roads, already merged into
                 _conduct_expect by the machinery that proved them)
    conscience   a compassionate soul will not stand with a dark name, however warm
                 the personal bond -- and will lean toward OPPOSING cruelty
    the body     a collapsed or contracted soul stays out of danger entirely: the
                 somatic floor extends to war (the welfare rule, again)
    the germ     boldness (E1's dial) sets what danger a soul will stand in; the
                 timid refuse what the bold accept

Closed verbs, the stakes pattern: JOIN / REFUSE / OPPOSE -- an engine reads the verb and
a REASON string (legible, speakable, printable over an NPC's head). Deterministic;
falsified in experiment_allegiance.py before anything is built on it."""
from __future__ import annotations

# decision thresholds (tuned on tuning seeds; the falsifier's verdict is held-out)
JOIN_AT = 0.35
OPPOSE_AT = -0.30
DARK_NAME = -0.15        # a reputation below this is a dark name
COLLAPSED_WELL = 0.25    # the body's floor: too worn to stand in anything
CONTRACTED = 0.5


def decide(agent, leader_id: str, danger: float = 0.0) -> tuple[str, str]:
    """One soul's answer to 'stand with me?' -> ('join'|'refuse'|'oppose', reason).

    danger [0,1]: how costly standing-with could get (0 = an errand, 1 = a war)."""
    bond = agent.bonds.get(leader_id) if agent.bond_enabled else None
    trust = bond.trust if bond else 0.0
    history = min(1.0, bond.history / 3.0) if bond else 0.0
    wounds = bond.wounds if bond else 0
    rep = agent._conduct_expect.get(leader_id, 0.0)
    compassion = getattr(agent, "compassion", 0.0)
    boldness = getattr(agent, "boldness", 0.5)

    # the body decides first: a collapsed or contracted soul stays out of danger --
    # not disloyal, WORN. (The somatic floor's spirit extended to war.)
    if danger > 0.2 and (agent.wellbeing < COLLAPSED_WELL
                         or getattr(agent, "_contraction", 0.0) > CONTRACTED):
        return "refuse", f"{agent.name} is too worn to stand in this"

    score = 0.9 * trust * (0.6 + 0.4 * history) + 0.8 * rep
    score -= 0.08 * wounds                          # scars vote too
    score -= danger * (0.55 - 0.5 * boldness)       # the timid refuse what the bold accept
    if rep < DARK_NAME and compassion > 0.4:
        # conscience: a warm heart will not lend its hands to a dark name -- however
        # deep the personal bond -- and leans toward standing AGAINST cruelty
        score = min(score, 0.0) - 0.4 * compassion

    if score >= JOIN_AT:
        why = ("their trust in you runs deep" if trust > 0.4
               else "your name is good here")
        return "join", f"{agent.name} stands with you -- {why}"
    if score <= OPPOSE_AT:
        why = ("what they have heard of you" if rep < DARK_NAME and (not bond or trust <= 0)
               else "old wounds between you")
        return "oppose", f"{agent.name} stands against you -- {why}"
    why = ("they hardly know you" if not bond and abs(rep) < 0.1
           else "they are not sure of you yet")
    return "refuse", f"{agent.name} stays out of it -- {why}"


def muster(world, leader_id: str, danger: float = 0.0) -> dict:
    """Ask the whole town at once. Returns {'join': [...], 'refuse': [...],
    'oppose': [...], 'reasons': {soul_id: reason}} -- the recruitment screen, derived."""
    out = {"join": [], "refuse": [], "oppose": [], "reasons": {}}
    for a in world.agents:
        if a.id == leader_id:
            continue
        verb, reason = decide(a, leader_id, danger)
        out[verb].append(a)
        out["reasons"][a.id] = reason
    return out
