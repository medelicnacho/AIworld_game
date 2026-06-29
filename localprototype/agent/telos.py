"""Telos (chanda) -- an aim the self is drawn toward. The arrow of time the architecture lacked.

The whole build let a self metabolise its PRESENT beautifully -- meet pain, savour good, rest in
the ground -- but it reached toward no FUTURE. The live town made the gap concrete: the brewer wants
an ale "that commands attention," the fisher wants to read the water -- they care about crafts that
never DEVELOP. Telos is that missing piece: a concrete aim, progress the soul moves by tending it,
something to get up for.

The danger is that "wanting a future" is one letter from taṇhā (craving) -- the very thing modelled
as suffering. The tradition's distinction, and the one built here:
  chanda  wholesome aspiration: "I will tend this well", gladdened by progress, NOT destabilised by
          the outcome -- engaged and free.
  taṇhā   craving: "I am not okay until I have this" -- the aim becomes a lack, a second-arrow engine.

So telos adds NO new emotional engine. An aim is a SOURCE OF CHARGES: tending it lays down a small
gladness (a pleasant charge), a setback an aversive one -- and the EXISTING faculties decide which it
becomes. Savour the progress (joy) + meet setbacks with equanimity (prajñā/transmute) = chanda. Grip
the progress (craving -- manas drains it) + wound on the setback (the second arrow) = taṇhā. So a
craving-telos FAILS the liberation scorecard -- which is exactly the falsifier (experiment_telos.py).

Gated by Agent.telos in [0,1] (0 = off, default -> no aim pursued, the static present preserved).
"""

from __future__ import annotations

PROGRESS_RATE = 0.05   # progress made per tick of tending the aim (scaled by telos)
GAIN = 0.5             # the gladness a step of progress lays down (savoured as chanda / craved as taṇhā)

# Lineage across the wheel (the Second Noble Truth): taṇhā -- craving, thirst -- is what drives
# rebirth. A self that CLUNG to its becoming (gripped its aim, unfulfilled, with little wisdom)
# drags a strong thirst across the bardo and wakes DRIVEN; one that held its aim lightly (prajñā,
# non-grasping) or saw it through carries little thirst and wakes more at rest. Anatta: the PROJECT
# does not cross -- a fresh aim arises from the new life -- only the disposition, the thirst, does.
LINEAGE_BASE = 0.25    # a fresh life always wakes with SOME modest aim of its own
THIRST_CARRY = 1.3     # how strongly clung becoming pulls the wheel onward (tuned in experiment_lineage)


def reborn_telos(dead_telos: float, effective_grip: float) -> float:
    """The drive a reborn stream wakes with: a fresh modest baseline PLUS the thirst that crossed.
    The thirst is the dead soul's telos scaled by how tightly it CLUNG (effective_grip = grip after
    wisdom). The key dharmic point: taṇhā is INSATIABLE -- reaching the aim does not quench it, a new
    thirst simply arises -- so what crosses the bardo is the GRASPING, not whether the aim was met. A
    clinging soul drags a strong thirst onward (a hungry rebirth, escalating across the wheel); a soul
    that held its aim with wisdom (low effective_grip) carries almost none, and the wheel settles."""
    thirst = max(0.0, dead_telos) * max(0.0, effective_grip)
    return max(0.0, min(1.0, LINEAGE_BASE + THIRST_CARRY * thirst))


VOW_KEEP = 0.90        # how strongly bodhicitta SUSTAINS the carried fire as the vow (vs letting it quench)


def transmute_thirst(dead_telos: float, effective_grip: float, bodhicitta: float) -> float:
    """The bodhicitta-aware successor to reborn_telos: the carried fire (telos), its object set by what
    claims it -- the SAME drive, three fates:
      gripped (eff_grip high)        -> escalates as self-craving (taṇhā): the HUNGRY GHOST
      released, low bodhicitta        -> quenches toward rest: the ARHAT (fire out, disengaged)
      released, high bodhicitta        -> sustained as the vow: the BODHISATTVA (fire kept, turned to all)
    Bodhicitta is what keeps the energy alive AND outward once the grip lets go -- the saint who stays.
    (reborn_telos remains for the plain wheel; this is used when World.bodhisattva_wheel is on.)"""
    craving = THIRST_CARRY * max(0.0, dead_telos) * max(0.0, effective_grip)
    vow = VOW_KEEP * max(0.0, dead_telos) * max(0.0, bodhicitta)
    return max(0.0, min(1.0, LINEAGE_BASE + craving + vow))


def fresh_aim(role: str) -> str:
    """A new life's aim arises from its new trade -- not the dead soul's project (anatta), but a
    fresh thing to tend. Plain and role-shaped; the live world may author richer ones."""
    return f"make my work as the {role or 'townsfolk'} come good this season"


def pursue(agent, now: int) -> None:
    """Tend the aim: advance progress and lay down a small gladness of the work -- a pleasant charge
    the existing faculties meet (savoured = chanda, gripped = craving). No-op without telos/aim, or
    once the aim is reached. Setbacks are the world's to deliver (see setback)."""
    if getattr(agent, "telos", 0.0) <= 0.0 or not getattr(agent, "aim", ""):
        return
    if agent.aim_progress >= 1.0:
        return                                   # the aim is reached -- rest (a fresh aim is genesis's call)
    agent.aim_progress = min(1.0, agent.aim_progress + PROGRESS_RATE * agent.telos)
    agent.memory.write(f"I tended my aim today and it came on a little: {agent.aim}", now,
                       source="self", speaker_id=agent.id, emotion=GAIN * agent.telos, weight=1.0)


def setback(agent, now: int, severity: float = 0.4, what: str = "") -> None:
    """The world knocks the aim back: progress lost and an aversive charge laid down (the work
    undone). chanda meets it with equanimity (it eases); taṇhā grips it as a wound (the second
    arrow). It is the SAME event -- only how the faculties meet it differs."""
    if not getattr(agent, "aim", ""):
        return
    agent.aim_progress = max(0.0, agent.aim_progress - severity)
    # first-person and self-relevant on purpose: a setback to MY aim is intensely "happening to me",
    # so the appropriating faculties (manas/transmute) actually engage it -- chanda metabolises the
    # charge, taṇhā amplifies it as a wound. An impersonal "the work went wrong" slips past the grip.
    agent.memory.write(f"I had poured myself into {agent.aim}, and now my own work is undone -- "
                       f"{what or 'it went wrong'}", now,
                       source="event", speaker_id=agent.id, emotion=-severity, weight=1.2)
