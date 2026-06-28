"""THE PATH (bhāvanā) within a life -- does practice actually FREE a soul over its lifetime?

cultivate() (agent/path.py) is unit-tested as a mechanism; this is its falsifier on a real life.
A soul that starts CLINGING (grip high, prajñā low) lives a long life of repeated loss, meeting
its own mind with equanimity (reflect on) each time. We toggle ONLY cultivation:

  practice (cultivate on)   -> recent equanimous reflection grooves the faculties: grip DOWN, prajñā UP
  neglect  (cultivate off)  -> the same reflections ease mood tick-to-tick, but the TRAIT never moves

The claim is that a self is not fixed -- sustained practice remakes it, measurably -- and that as it
frees itself its suffering eases (the lived wound late in life is lighter than early). The companion
to experiment_lineage.py: that showed cultivation ACROSS the wheel; this shows it WITHIN a life.

  python experiment_path.py                       # mock: plumbing + deterministic-ish trajectory
  python experiment_path.py --llm ollama --model gemma3:4b   # the genuine equanimity signal
"""

from __future__ import annotations

import argparse
import statistics

from agent.agent import Agent
from agent.reflect import reflect
from services.llm import MockLLM, OllamaLLM
from world.events import WorldEvent

TICKS = 72
REFLECT_EVERY = 4
LOSSES = (6, 30, 54)                 # a life met by repeated loss
START_GRIP, START_PRAJNA = 0.7, 0.1  # a clinging, unfree soul at the start of the path
SEED_LINES = ["I keep the lamps along the eastern road", "I count the carts before noon",
              "the same three streets, most days"]


def run_life(llm, seed, cultivate_on):
    a = Agent("self", "Aldous", (0.0, 0.0), "You are Aldous, a quiet soul.",
              list(SEED_LINES), llm, seed=seed, temperament=0.0, lifespan=10 ** 9)
    a.grip, a.prajna, a.ground_enabled = START_GRIP, START_PRAJNA, True
    a.reflect_enabled = True
    a.cultivate_enabled = cultivate_on
    for ln in SEED_LINES:
        a.memory.write(ln, tick=0, source="self", speaker_id="self", weight=1.2)
    grip, prajna, mood = [], [], []
    for t in range(1, TICKS + 1):
        if t in LOSSES:
            a.perceive(WorldEvent("loss", "Someone you loved is gone.", t, emotion=-0.85, urge=0.7), t)
        a.step(t)                          # step() runs cultivate() when enabled
        if t % REFLECT_EVERY == 0:
            reflect(a, llm, t)             # the practice: meet your own mind with equanimity
        grip.append(a.grip); prajna.append(a.prajna); mood.append(a.memory.mood())
    return {"grip": grip, "prajna": prajna, "mood": mood, "agent": a}


def _spark(xs):
    blocks = "▁▂▃▄▅▆▇█"
    lo, hi = min(xs), max(xs); rng = (hi - lo) or 1.0
    return "".join(blocks[min(7, int((x - lo) / rng * 7.999))] for x in xs)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--llm", choices=["mock", "ollama"], default="mock")
    p.add_argument("--model", default=None)
    p.add_argument("--seed", type=int, default=11)
    args = p.parse_args()
    llm = (OllamaLLM(temperature=0.7, model=args.model) if args.model else OllamaLLM(temperature=0.7)) \
        if args.llm == "ollama" else MockLLM(seed=args.seed)

    practice = run_life(llm, args.seed, cultivate_on=True)
    neglect = run_life(llm, args.seed, cultivate_on=False)

    def ends(r, key): return r[key][0], r[key][-1]
    pg0, pg1 = ends(practice, "grip"); pp0, pp1 = ends(practice, "prajna")
    ng0, ng1 = ends(neglect, "grip"); np0, np1 = ends(neglect, "prajna")
    third = TICKS // 3
    p_early = statistics.fmean(practice["mood"][:third]); p_late = statistics.fmean(practice["mood"][-third:])

    print(f"\n=== The path within a life: does practice free a soul? ({args.llm}, seed {args.seed}) ===")
    print(f"  a clinging soul (grip {START_GRIP}, prajñā {START_PRAJNA}) lives {TICKS} ticks of loss, reflecting\n")
    print(f"  practice  grip:    {_spark(practice['grip'])}  {pg0:.2f} -> {pg1:.2f}")
    print(f"  practice  prajñā:  {_spark(practice['prajna'])}  {pp0:.2f} -> {pp1:.2f}")
    print(f"  neglect   grip:    {ng0:.2f} -> {ng1:.2f}   prajñā: {np0:.2f} -> {np1:.2f}")
    print(f"  practice  lived wound:  early {p_early:+.3f}  ->  late {p_late:+.3f}\n")

    frees = (pg1 < pg0 - 0.1) and (pp1 > pp0 + 0.1)
    neglect_static = abs(ng1 - ng0) < 0.05 and abs(np1 - np0) < 0.05
    eases = p_late > p_early + 0.02
    print("  -> PRACTICE frees the soul (grip falls, prajñā rises over the life): " + ("YES" if frees else "no"))
    print("     NEGLECT leaves the trait static (reflection eases mood, not character): " + ("YES" if neglect_static else "no"))
    print("     and as it frees itself, the lived wound EASES (late lighter than early): " + ("YES" if eases else "no"))
    print("  VERDICT: " + (
        "THE PATH: a self is not fixed -- meeting its own mind with equanimity over a life grooves "
        "the faculties toward freedom (grip loosens, wisdom grows), and its suffering eases as it goes. "
        "Without cultivation the same reflections soothe each moment but never remake the character."
        if (frees and neglect_static) else
        "did NOT show the frees+static signature -- see the trajectories (the genuine equanimity signal "
        "needs --llm ollama; tune path.RATE if the drift is too slow)."))


if __name__ == "__main__":
    main()
