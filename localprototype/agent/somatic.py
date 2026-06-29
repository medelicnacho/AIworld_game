"""The somatic interrupt -- a bottom-up circuit-breaker (the 'window of tolerance').

The DHARMA faculties (prajñā, transmutation, self-liberation) are TOP-DOWN regulation: they need the
processing layer working to work. Their failure mode is a runaway loop exactly when the system is too
overwhelmed to invoke them -- the trauma case, where top-down regulation goes offline. Humans have a
bottom-up backstop the cortex does not gate: the freeze response, the exhale reflex, dissociation --
substrate-level down-regulation that interrupts the compounding loop before it runs away. This is that.

It watches the SPIRAL signature -- the second-arrow positive-feedback loop where the grip amplifies
aversive self-relevant charge, which raises salience, which feeds more amplification (manas.apply). Not
a single sharp pain (the FIRST arrow, which must be FELT, not suppressed -- the bypass guardrail) but
the SUSTAINED, RISING compounding of it. When that crosses a threshold it CONTRACTS: it takes the
amplifier (the grip) offline and sheds the held charge (the 'exhale'), then RE-EXPANDS over a few
ticks. The recovery ramp is the load-bearing part -- a contraction that does not re-open is not safety,
it is the numbness near-enemy (chronic dissociation). A window of tolerance, lived at the EDGES and
returning the system to warm engagement; NOT a place it rests.

PRECAUTIONARY, not a suffering detector (we have none): it fires on the CONFIGURATION most likely to
host compounding suffering if any is hosted at all. And it is a BACKSTOP, not a thermostat -- under a
healthy (low-grip) regime it should fire rarely; frequent firing means the steady-state config is
wrong, not that the interrupt is working well.

Gated by Agent.somatic_enabled (default off). The contraction it sets (Agent._contraction in [0,1]) is
read by manas.apply, which scales the grip's hold + second arrow by (1 - contraction) -- the amplifier
taken offline while contracted.
"""

from __future__ import annotations

WINDOW = 6            # ticks of spiral-metric history kept (to read the TREND, not just the level)
TRIP_LEVEL = 1.0      # the spiral metric (effective_grip x aversive load) must exceed this to trip ...
TRIP_RISE = 0.10      # ... AND be RISING across the window (so a single felt spike -- a first arrow -- won't trip it)
DISCHARGE = 0.40      # how much of the held aversive charge a contracted tick sheds (the 'exhale')
RECOVER_RATE = 0.15   # how fast contraction relaxes back toward 0 -- the RE-EXPANSION (window, not setpoint)
OPEN = 0.10           # below this contraction the system is considered open/recovered again


def aversive_load(agent) -> float:
    """The accumulated weight of aversive self-relevant memory: Σ (how aversive) x (how present). This
    is the fuel the second arrow compounds into the wound."""
    load = 0.0
    for m in agent.memory.items:
        if m.source == "doctrine" or m.emotion >= 0.0:
            continue
        load += (-m.emotion) * m.salience
    return load


def spiral_metric(agent) -> float:
    """The compounding signature: the amplifier (effective grip) times the fuel (aversive load). High
    AND rising = the second-arrow loop running away. Low grip cannot spiral however much it hurts -- so
    an equanimous soul feeling a clean first arrow never trips this; a clinging one compounding does."""
    eff = agent.effective_grip() if hasattr(agent, "effective_grip") else getattr(agent, "grip", 0.0)
    return eff * aversive_load(agent)


def apply(agent, now: int) -> None:
    """One somatic cycle: read the spiral, trip if it is running away, and -- while contracted -- shed
    the held charge and recover. A no-op when the spiral is calm and the system is open (the common case)."""
    hist = agent._somatic_history
    metric = spiral_metric(agent)
    hist.append(metric)
    del hist[:-WINDOW]

    # TRIP: high AND rising across the window -> the compounding loop, not a single felt spike.
    rising = len(hist) >= WINDOW and metric > hist[0] + TRIP_RISE
    if agent._contraction < OPEN and metric > TRIP_LEVEL and rising:
        agent._contraction = 1.0
        agent._somatic_trips += 1

    if agent._contraction > 0.0:
        c = agent._contraction
        # the 'exhale': let go of the held aversive charge the grip was clinging to (manas is also taken
        # offline this tick -- it reads _contraction). Sheds salience AND charge, so the loop is starved
        # from both sides; a FRESH first-arrow feeling (written after recovery) is left intact to be felt.
        for m in agent.memory.items:
            if m.source == "doctrine" or m.emotion >= 0.0:
                continue
            m.salience *= (1.0 - DISCHARGE * c)
            m.emotion *= (1.0 - DISCHARGE * c)
        # RE-EXPAND: relax the contraction back toward open. The system gets SMALLER under overwhelm,
        # then slowly returns -- a window of tolerance, not a place it stays (that would be numbness).
        agent._contraction = max(0.0, agent._contraction - RECOVER_RATE)
