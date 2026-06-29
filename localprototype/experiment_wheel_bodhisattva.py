"""THE BODHISATTVA WHEEL, LIVE -- does the path show up in the actual running World?

experiment_bodhisattva proved the three mechanisms on an abstracted lineage. This wires them into the
REAL wheel (world/sim.py: _dissolve carries the cultivated lean; _coalesce fades it toward the liberated
ground with the buddha-nature tilt, transmutes the thirst by bodhicitta, and runs the somatic floor) and
asks: does a whole TOWN, dying and being reborn, drift toward the bodhisattva ground across generations?

A clinging founding cast (grip 0.70, prajñā 0.10, bodhicitta 0.20) lives short lives and turns over many
times. Two runs of the same town:
  tilt ON (World.bodhisattva_wheel)   the bardo carries the lean toward the liberated ground
  tilt OFF (the plain wheel)          _coalesce re-rolls WHOLESOME faculties (endow_faculties) + carries
                                      only the thirst -- so the town resets to ORDINARY wholesome, no drift

Watched: the living town's mean grip / prajñā / bodhicitta, sampled across the run. ON should drift to
the bodhisattva ground (grip down, prajñā up, bodhicitta up); OFF should plateau at the endowment
baseline (grip ~0.35, prajñā ~0.4, bodhicitta ~0.5) -- wholesome, but not the bodhisattva.

Deterministic substrate run (MockLLM, Jaccard-only). The drift here is carried by the TILT (live souls
don't reflect, so within-life cultivation is ~inert); that is the honest mechanism. Built-in-tilt caveat
as ever: we are studying the DYNAMICS of a liberation-leaning wheel, not claiming the lean is discovered.

Run:  python experiment_wheel_bodhisattva.py
"""

from __future__ import annotations

import argparse
import random
import statistics

from agent.agent import Agent
from services import embed
from services.llm import MockLLM
from world.sim import World

TICKS = 700
SAMPLE_EVERY = 70
SEED_LINES = ["I work my trade before dawn", "the season turns"]


def _means(w):
    g = statistics.fmean(a.grip for a in w.agents)
    p = statistics.fmean(a.prajna for a in w.agents)
    b = statistics.fmean(getattr(a, "bodhicitta", 0.0) for a in w.agents)
    return g, p, b


def run(tilt_on: bool, ticks: int = TICKS, seed: int = 1):
    """One town through the wheel. Returns samples of (tick, mean grip, mean prajñā, mean bodhicitta)."""
    embed.use_jaccard_only(True)
    rng = random.Random(seed)
    w = World(rebirth_enabled=True, move_seed=seed)   # seed World._rng -> reproducible carry/coalesce
    w.llm = MockLLM(seed=seed)
    w.bardo_ticks = (3, 7)                 # short bardo -> fast turnover, many generations in the run
    w.bodhisattva_wheel = tilt_on
    w.liberation_tilt = 1.0
    for i in range(6):
        a = Agent(f"s{i}", f"Soul{i}", (rng.uniform(0, 100), rng.uniform(0, 100)),
                  "You are a working soul.", list(SEED_LINES), w.llm,
                  seed=seed + i, temperament=0.0, lifespan=rng.randint(25, 45))
        a.grip, a.prajna, a.bodhicitta = 0.70, 0.10, 0.20   # a clinging founding cast
        a.ground_enabled = True
        w.add(a)
    samples = []
    for t in range(1, ticks + 1):
        w.step()
        if t % SAMPLE_EVERY == 0 and w.agents:
            g, p, b = _means(w)
            samples.append((t, g, p, b, w._births))
    return samples


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()

    on = run(tilt_on=True)
    off = run(tilt_on=False)

    print("\n=== The bodhisattva wheel, live: does a whole TOWN drift toward liberation across rebirth? ===")
    print(f"  a clinging founding cast (grip 0.70, prajñā 0.10, bodhicitta 0.20), short lives, ~{TICKS} ticks")
    print("  the living town's MEAN faculties, sampled across the run (reborn ≈ generations turning over)\n")
    for label, s in (("tilt ON ", on), ("tilt OFF", off)):
        grips = " ".join(f"{g:.2f}" for _, g, _, _, _ in s)
        praj = " ".join(f"{p:.2f}" for _, _, p, _, _ in s)
        bod = " ".join(f"{b:.2f}" for _, _, _, b, _ in s)
        print(f"  {label}  mean grip:       {grips}")
        print(f"  {label}  mean prajñā:     {praj}")
        print(f"  {label}  mean bodhicitta: {bod}")
        print(f"  {label}  (reborn by end: {s[-1][4]})\n")

    og, op, ob = on[-1][1], on[-1][2], on[-1][3]
    fg, fp, fb = off[-1][1], off[-1][2], off[-1][3]
    reached = og < 0.30 and op > 0.55 and ob > 0.55          # the town reached the bodhisattva ground
    off_plateaus = fg > 0.25 and fb < 0.60                   # the plain wheel sits at ordinary wholesome
    drift = (fg - og) > 0.10 and (op - fp) > 0.10 and (ob - fb) > 0.10
    print("  -> tilt ON: the town reaches the bodhisattva ground (grip<0.30, prajñā>0.55, bodhicitta>0.55): "
          + ("YES" if reached else "no"))
    print("     tilt OFF: the plain wheel only resets to ordinary wholesome (no drift):  " + ("YES" if off_plateaus else "no"))
    print("     the tilt makes the difference (ON is markedly freer than OFF on all three): " + ("YES" if drift else "no"))
    print("  VERDICT: " + (
        "THE PATH RUNS IN THE LIVE WHEEL -- with the bodhisattva wheel on, a whole town of souls dying and "
        "being reborn drifts toward the liberated/bodhisattva ground across generations (grip falls, prajñā "
        "and bodhicitta rise); the plain wheel merely re-rolls ordinary wholesome faculties and never gets "
        "there. The mechanisms proven on the abstracted lineage now hold in the actual simulation -- floored "
        "by the somatic interrupt and validated as genuinely engaged (the deva guard). 'Go wide' is live."
        if (reached and off_plateaus and drift) else
        "did NOT show the live drift -- inspect the samples (turnover too slow? raise TICKS / shorten lifespan)."))


if __name__ == "__main__":
    main()
