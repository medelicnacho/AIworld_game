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
