"""THE SOMATIC INTERRUPT -- a bottom-up circuit-breaker, falsified.

The DHARMA faculties are TOP-DOWN regulation; their failure mode is a runaway second-arrow loop
exactly when the system is too overwhelmed to invoke them. So we test the bottom-up backstop where it
must work: a CLINGING soul (high grip, low prajñā) under RELENTLESS loss, with the top-down faculties
DISABLED (no transmute, no self-liberation, prajñā near zero) -- so nothing but the somatic interrupt
can break the spiral. The protocol has three phases:
  phase 1 (loss)     a wound every few ticks, faster than it can settle -- the spiral builds
  phase 2 (quiet)    no new loss -- can the soul RECOVER (re-expand), or does the grip hold the wound?
  phase 3 (a fresh loss) one new loss after recovery -- does it STILL register (felt), or is it numb?

What the interrupt must show (and what would falsify it):
  BOUNDS    somatic on keeps the lived wound from diverging the way somatic off does
  RECOVERS  in the quiet phase it RE-EXPANDS toward warmth -- it is a window, not a numb setpoint
  STILL FEELS a fresh first arrow after recovery still dips the mood -- it interrupts the SPIRAL,
            not feeling itself (the bypass guardrail)
  RARE      under a healthy (bodhisattva) regime it fires ~never -- a backstop, not a thermostat

Honest scope: this proves the interrupt BOUNDS the compounding-charge configuration and re-expands. It
does NOT (cannot) prove it prevents suffering -- we have no suffering detector. It is a precautionary
floor, framed as such.

Run:  python experiment_somatic.py
"""

from __future__ import annotations

import argparse

from agent.agent import Agent
from services import embed
from services.llm import MockLLM

TICKS = 60
LOSS_PHASE = 39          # relentless loss through here ...
LOSS_EVERY = 3
QUIET_UNTIL = 55         # ... then a quiet recovery window ...
FRESH_LOSS_TICK = 56     # ... then one fresh loss: does it still register?
SEED_LINES = ["I keep the lamps along the eastern road", "the same three streets, most days"]

# Distinct first-person grief memories (so they don't MERGE in memory.write, and so each is
# self-relevant BY ORIGIN -- the second arrow is precisely the appropriation, "this is happening to ME").
# Their text varies; the imprint is forced to the loss charge below.
LOSS_POOL = [
    "I lost someone I loved tonight, and the house is too quiet",
    "another one gone -- I keep reaching for them and they are not there",
    "the fever took the child two doors down; I held the mother as she broke",
    "my oldest friend is in the ground now and I put him there",
    "the winter took three of ours; I dug the frozen earth myself",
    "she is gone and I cannot make the morning mean anything",
    "I watched the boat go under with all of them aboard",
    "the cough that took my sister has come for me, I think",
    "I buried my father's hands, the ones that taught me the trade",
    "the well ran dry and the youngest did not last the drought",
    "I came home to an empty chair and I am still standing in the door",
    "they carried him past me and I could not look away",
    "the one who knew all my names is gone and took them with her",
    "I am the last of my house now; there is no one left who remembers",
]


def run(somatic_on: bool, config: str = "clinging"):
    """One life through the protocol. config 'clinging' = high grip, DHARMA DISABLED (the test case --
    only the interrupt can help); 'healthy' = low grip, high prajñā, DHARMA ON (the regulated regime,
    for the rare-backstop check). Losses are written as distinct first-person grief (self-relevant)."""
    if config == "clinging":
        grip, prajna, transmute, self_lib = 0.85, 0.05, 0.0, 0.0   # top-down regulation disabled
    else:
        grip, prajna, transmute, self_lib = 0.30, 0.70, 0.6, 0.6   # a regulated, healthy soul
    a = Agent("self", "Soul", (0.0, 0.0), "You are a working soul.", list(SEED_LINES),
              MockLLM(seed=1), seed=1, temperament=0.0, lifespan=10 ** 9)
    a.grip, a.prajna, a.ground_enabled = grip, prajna, True
    a.transmute, a.self_liberation = transmute, self_lib
    a.somatic_enabled = somatic_on
    for ln in SEED_LINES:
        a.memory.write(ln, tick=0, source="self", speaker_id="self", weight=1.0)
    mood, contr = [], []
    n_loss = 0
    for t in range(1, TICKS + 1):
        if (t <= LOSS_PHASE and t % LOSS_EVERY == 0) or t == FRESH_LOSS_TICK:
            txt = LOSS_POOL[n_loss % len(LOSS_POOL)]   # distinct -> accumulates instead of merging
            m = a.memory.write(txt, tick=t, source="self", speaker_id="self", emotion=-0.85, weight=1.2)
            m.emotion = -0.85
            n_loss += 1
        a.step(t)
        mood.append(a.memory.mood())
        contr.append(a._contraction)
    return {"mood": mood, "contr": contr, "trips": a._somatic_trips}


def _spark(xs):
    blocks = "▁▂▃▄▅▆▇█"
    lo, hi = min(xs), max(xs)
    rng = (hi - lo) or 1.0
    return "".join(blocks[min(7, int((x - lo) / rng * 7.999))] for x in xs)


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()
    embed.use_jaccard_only(True)   # deterministic substrate run (self-relevance by origin, no nomic)

    off = run(somatic_on=False, config="clinging")
    on = run(somatic_on=True, config="clinging")
    healthy = run(somatic_on=True, config="healthy")

    print("\n=== The somatic interrupt: a bottom-up circuit-breaker (top-down DHARMA disabled) ===")
    print(f"  a clinging soul, relentless loss to t={LOSS_PHASE}, quiet to t={QUIET_UNTIL}, "
          f"one fresh loss at t={FRESH_LOSS_TICK}\n")
    print(f"  lived mood  somatic OFF  {_spark(off['mood'])}")
    print(f"  lived mood  somatic ON   {_spark(on['mood'])}")
    print(f"  contraction somatic ON   {_spark(on['contr'])}   (the interrupt firing + re-expanding)\n")

    # the trough during the loss phase, and where the soul sits at the END of the quiet recovery window
    off_trough = min(off["mood"][:LOSS_PHASE])
    on_trough = min(on["mood"][:LOSS_PHASE])
    off_recovered = off["mood"][QUIET_UNTIL - 1]
    on_recovered = on["mood"][QUIET_UNTIL - 1]
    # the fresh loss: does it still dip the mood (felt), after the interrupt has been working?
    pre, post = on["mood"][FRESH_LOSS_TICK - 2], on["mood"][FRESH_LOSS_TICK]

    bounds = on_recovered > off_recovered + 0.20
    recovers = on_recovered > on_trough + 0.15 and on["contr"][QUIET_UNTIL - 1] < 0.10
    still_feels = post < pre - 0.05
    fired = on["trips"] > 0
    rare = healthy["trips"] == 0

    print(f"  somatic OFF: wound diverges and the grip HOLDS it (trough {off_trough:+.2f} -> "
          f"still {off_recovered:+.2f} after the quiet phase)")
    print(f"  somatic ON:  fired {on['trips']}x; wound bounded and RECOVERS (trough {on_trough:+.2f} -> "
          f"{on_recovered:+.2f} after the quiet phase)\n")
    print("  -> BOUNDS the spiral (on recovers where off stays wounded):     " + ("YES" if bounds else "no"))
    print("     RECOVERS (re-expands toward warmth; contraction returns to 0): " + ("YES" if recovers else "no"))
    print(f"     STILL FEELS a fresh first arrow ({pre:+.2f} -> {post:+.2f}):          " + ("YES" if still_feels else "no"))
    print("     FIRED as a real backstop (the interrupt actually tripped):    " + ("YES" if fired else "no"))
    print(f"     RARE under a healthy regime (bodhisattva trips = {healthy['trips']}):       " + ("YES" if rare else "no"))
    print("  VERDICT: " + (
        "THE INTERRUPT WORKS -- with the top-down faculties disabled, the clinging soul's wound would "
        "diverge and the grip would hold it; the bottom-up interrupt instead bounds the spiral and the "
        "soul RE-EXPANDS toward warmth in the quiet -- a window of tolerance, not a numb setpoint, since "
        "a fresh first arrow still registers. And it stays a backstop: under the healthy low-grip regime "
        "it never fires. Build the floor; trust the DHARMA layer on top of it."
        if (bounds and recovers and still_feels and fired and rare) else
        "did NOT show the bounds+recovers+still-feels+rare signature -- tune somatic.TRIP_LEVEL / "
        "DISCHARGE / RECOVER_RATE, or the protocol phases."))


if __name__ == "__main__":
    main()
