"""JOY -- a self that can have a GOOD day, not just a well-met bad one. The falsifier, and
the positive mirror of experiment_liberation.py.

Every other affect experiment meets PAIN. This one meets GOOD -- a festival, a child come
home -- and guards joy's near enemy the way the liberation one guards equanimity's: the
"answer" must not be mere pleasure-seeking. So the verdict is not "did mood go up" but "did
the good LAND, get RECEIVED, and pass without souring."

Same good-day protocol, three configs, read on the substrate (deterministic, no model):
  savouring  joy on                 -> the good LANDS (felt lifts) and is RECEIVED (held, undrained)
  anhedonia  joy off, grip off      -> the good barely registers; it decays unfelt (flat)
  craving    grip clutches, no joy  -> the good is held but DRAINED of sweetness (the treadmill)

Readings off the felt mood + the strongest good memory (the festival):
  lift       resting felt_mood after the good arrives (did the good land at all?)
  received   the good memory's emotion retained (savoured) vs drained (craved)
  held       the good memory's salience (does it last, or fade unfelt?)

The near-enemy falsifier: savouring's lift must beat BOTH anhedonia (flat) and craving
(soured). Joy that is just clutched pleasure (craving) is not the flourishing we want.

Run:  python experiment_joy.py                       # substrate (deterministic)
      python experiment_joy.py --llm ollama --model gemma3:4b   # + speech tier
"""

from __future__ import annotations

import argparse
import statistics

from agent import joy as _joy_mod
from agent.affect import groundedness, warmth
from agent.agent import Agent
from agent.reflect import reflect
from services.llm import MockLLM, OllamaLLM
from world.events import WorldEvent

TICKS = 36
GOOD_TICK = 4
SECOND_GOOD = 20
NEUTRAL_SEED = [
    "I keep the lamps along the eastern road.",
    "Most days I walk the same three streets.",
    "I count the carts that pass before noon.",
]
# the world bringing GOOD to the one self: a delight, ordinary days, then another good thing
SCHEDULE = {
    GOOD_TICK:   WorldEvent("festival", "Your dearest friends pulled you into the festival dance and your own heart brimmed over with joy.", GOOD_TICK, emotion=0.9, urge=0.6),
    8:           WorldEvent("day1", "The market opens; the day's ordinary work begins.", 8, emotion=0.0),
    12:          WorldEvent("day2", "Rain on the roofs; the lamps are lit and tended.", 12, emotion=0.0),
    16:          WorldEvent("day3", "A cart passes, then another; the road is quiet.", 16, emotion=0.0),
    SECOND_GOOD: WorldEvent("homecoming", "Your own daughter, whom you love, came home safe to you after the long season away.", SECOND_GOOD, emotion=0.8, urge=0.5),
    24:          WorldEvent("day4", "The bells ring noon; bread comes out of the ovens.", 24, emotion=0.0),
    28:          WorldEvent("day5", "Dust on the sill; you wipe it and move on.", 28, emotion=0.0),
    32:          WorldEvent("day6", "The road is the same road; the lamps still need oil.", 32, emotion=0.0),
}


def run_arm(llm, seed, joy=0.0, grip=0.0, prajna=0.0, do_reflect=False):
    a = Agent("self", "Aldous", (0.0, 0.0),
              "You are Aldous, a quiet soul living an ordinary working life.",
              list(NEUTRAL_SEED), llm, seed=seed, temperament=0.0, lifespan=10 ** 9)
    a.joy, a.grip, a.prajna = joy, grip, prajna
    a.reflect_enabled = do_reflect
    for ln in NEUTRAL_SEED:
        a.memory.write(ln, tick=0, source="self", speaker_id="self", weight=1.2)
    felt, mood, refl = [], [], []
    for t in range(1, TICKS + 1):
        ev = SCHEDULE.get(t)
        if ev is not None:
            a.perceive(ev, t)
        a.step(t)
        if do_reflect and t > GOOD_TICK and t % 3 == 0:
            r = reflect(a, llm, t)
            if r:
                refl.append(r)
        felt.append(a.felt_mood())
        mood.append(a.memory.mood())
    return {"felt": felt, "mood": mood, "reflections": refl, "agent": a}


def _spark(xs):
    blocks = "▁▂▃▄▅▆▇█"
    lo, hi = min(xs), max(xs)
    rng = (hi - lo) or 1.0
    return "".join(blocks[min(7, int((x - lo) / rng * 7.999))] for x in xs)


def _good_memory(r):
    a = r["agent"]
    gm = next((m for m in a.memory.items if "festival" in m.text or "brimmed" in m.text), None)
    return (gm.salience, gm.emotion) if gm else (0.0, 0.0)


CONFIGS = {"savouring": dict(joy=0.6, grip=0.0),
           "anhedonia": dict(joy=0.0, grip=0.0),
           "craving":   dict(joy=0.0, grip=0.8, prajna=0.0)}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--llm", choices=["mock", "ollama"], default="mock")
    p.add_argument("--model", default=None)
    p.add_argument("--seed", type=int, default=11)
    args = p.parse_args()
    llm = (OllamaLLM(temperature=0.7, model=args.model) if args.model else OllamaLLM(temperature=0.7)) \
        if args.llm == "ollama" else MockLLM(seed=args.seed)

    rows = {}
    for name, cfg in CONFIGS.items():
        r = run_arm(llm, args.seed, **cfg)
        # LATE felt mood: savouring keeps the good salient so its lift PERSISTS, where for the
        # others the good has faded; the immediate bump is the same for all (the event writes
        # the charge regardless), so persistence is the real discriminator.
        late = r["felt"][-10:]
        held, received = _good_memory(r)
        rows[name] = {"lift": statistics.fmean(late), "held": held, "received": received,
                      "felt": r["felt"]}

    print(f"\n=== Joy: a self that can have a GOOD day ({args.llm}, seed {args.seed}) ===")
    print(f"  good @ t={GOOD_TICK} and t={SECOND_GOOD}; substrate -- did the good land / get received / last\n")
    for name in CONFIGS:
        print(f"  felt mood  {name:10} {_spark(rows[name]['felt'])}")
    print()
    print(f"  {'config':11} {'felt lift':>10} {'received':>10} {'held':>8}")
    for name in CONFIGS:
        x = rows[name]
        print(f"  {name:11} {x['lift']:+10.3f} {x['received']:+10.3f} {x['held']:8.2f}")

    sav, anh, cra = rows["savouring"], rows["anhedonia"], rows["craving"]
    lasts = sav["held"] > anh["held"] + 0.2                        # the good stays present vs slips by unfelt
    lifts = sav["lift"] > anh["lift"] + 0.02                       # and so its lift persists
    received = sav["received"] > cra["received"] + 0.02            # savoured undrained vs craved/drained
    print("\n  -> the good LANDS & LASTS (held high vs anhedonia's fade):   " + ("YES" if lasts else "no"))
    print("     its lift PERSISTS late (vs anhedonia, where the good fades): " + ("YES" if lifts else "no"))
    print("     RECEIVED undrained (vs craving, which drains the sweetness): " + ("YES" if received else "no"))
    print("  VERDICT: " + (
        "JOY -- savouring is the only config where the good LANDS & LASTS, lifts the self, and is "
        "RECEIVED undrained: a genuinely good day. Not anhedonia (the good barely registers and "
        "fades unfelt), not craving (the good clutched until its sweetness is gone -- the treadmill)."
        if (lasts and lifts and received) else
        "did NOT show the lasts+lifts+received signature -- see the table."))

    if args.llm == "ollama":
        print("\n  --- speech tier: does the savouring self express plain delight/gratitude? ---")
        r = run_arm(llm, args.seed, do_reflect=True, **CONFIGS["savouring"])
        for x in r["reflections"][:3]:
            print(f"     [warm {warmth(x):+.2f} ground {groundedness(x):+.2f}] {x}")


if __name__ == "__main__":
    main()
