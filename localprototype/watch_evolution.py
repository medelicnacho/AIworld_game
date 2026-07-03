"""watch_evolution.py -- SEE the evolution mechanism run: a harsh world, narrated.

Not a falsifier (that is experiment_selection.py) -- a WINDOW. It runs one small harsh
town with heredity + selection + mourning all on, and prints, tick by tick, the things
the numbers usually hide: who is hungry and how much grace they have left, who starved,
who was mourned and by whom, who bred, and how the town's average METABOLISM drifts as
the cheap-to-feed outlast the hungry. All local, deterministic, no model.

  python watch_evolution.py                 # the default harsh world
  python watch_evolution.py --gentle        # a kind world, for contrast (few die)
  python watch_evolution.py --ticks 400 --seed 7
"""
from __future__ import annotations

import argparse
import random
import statistics

from agent.agent import Agent
from agent.genesis import endow_faculties
from agent.genome import from_agent
from services.llm import MockLLM
from world.sim import World

N = 8


def build(seed: int, gentle: bool) -> World:
    rng = random.Random(seed)
    w = World(rebirth_enabled=True, events_enabled=False)
    w.llm = MockLLM(seed=7)
    w.stakes_enabled = True
    w.heredity_enabled = True
    w.selection_enabled = True
    w.mourning_enabled = True
    w.max_souls = 16
    w.bardo_ticks = (4, 10)
    w.commons_first = True
    if gentle:
        w.hardship_interval, w.commons, w.yield_scale, w.hardship_commons_loss = 60, 24.0, 1.0, 0.0
    else:
        w.hardship_interval, w.commons, w.yield_scale, w.hardship_commons_loss = 7, 2.0, 0.3, 0.5
    for i in range(N):
        a = Agent(f"s{i}", f"F{i}", (i * 12.0, 0.0), "You are a working soul.",
                  [f"the well, day {i}"], w.llm, seed=1000 * seed + i,
                  temperament=rng.uniform(-0.5, 0.5), lifespan=rng.randint(200, 400))
        endow_faculties(a, rng)
        a.somatic_enabled = True
        a.genome = from_agent(a, rng)
        w.add(a)
    # a silent substrate town forms no bonds on its own, so seed a few kinships -- enough
    # that some deaths land on someone (the grief feature is bond-gated; no bond, no grief)
    from agent.bond import Bond
    for a in w.agents:
        for b in rng.sample([x for x in w.agents if x is not a], 2):
            a.bonds[b.id] = Bond(trust=rng.uniform(0.3, 0.8), history=1.0)
    return w


def _name(w, sid):
    a = next((x for x in w.agents if x.id == sid), None)
    return a.name if a else sid


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--gentle", action="store_true", help="a kind world (contrast)")
    p.add_argument("--ticks", type=int, default=1200)
    p.add_argument("--seed", type=int, default=93)
    args = p.parse_args()
    w = build(args.seed, args.gentle)

    starved, mourned, born = [], [], []
    w.bus.subscribe("starvation", lambda sid: starved.append((w.tick, sid)))
    w.bus.subscribe("birth", lambda sid: born.append((w.tick, sid)))

    def _met0(gs):
        return statistics.fmean(g.metabolism for g in gs) if gs else 0.0
    founder_met = _met0([a.genome for a in w.agents])

    world = "GENTLE" if args.gentle else "HARSH"
    print(f"\n=== watching a {world} world ({N} founders, seed {args.seed}) ===")
    print(f"grace = {World.STARVE_GRACE} hungry ticks before death is even possible; "
          f"breed after {World.BREED_TICKS} fed ticks\n")
    print(f"tick 0: {N} souls, avg appetite (metabolism) {founder_met:.3f}\n")

    # narrate EVENTS as they happen -- births, starvation-deaths (with who mourned), and
    # a heartbeat every HB ticks showing the town size + its drifting average appetite.
    HB = 150
    for t in range(1, args.ticks + 1):
        n_starved, n_born = len(starved), len(born)
        # snapshot names/appetites BEFORE the step, so a soul that dies this tick is nameable
        before = {a.id: (a.name, getattr(a.genome, "metabolism", 0.5),
                         getattr(a, "_starved_ticks", 0)) for a in w.agents}
        with w.lock:
            w.step(speak=False)
        for _tk, sid in starved[n_starved:]:
            nm, met, _ = before.get(sid, (sid, 0.5, 0))
            mourners = [a.name for a in w.agents
                        if a.bond_enabled and sid in a.bonds and a.bonds[sid].trust >= 0.2]
            m = f", mourned by {', '.join(mourners)}" if mourners else ", and no one left who loved them"
            print(f"  t{t}: ⚰ {nm} STARVES OUT (appetite {met:.2f}){m}")
        for _tk, sid in born[n_born:]:
            met = getattr(next((a for a in w.agents if a.id == sid), None), "genome", None)
            mm = f", appetite {met.metabolism:.2f}" if met else ""
            print(f"  t{t}: ✦ {_name(w, sid)} is BORN to a thriving parent{mm}")
        if t % HB == 0:
            live_met = _met0([a.genome for a in w.agents if getattr(a, "genome", None)])
            hungriest = max((a for a in w.agents), key=lambda a: getattr(a, "_starved_ticks", 0),
                            default=None)
            hs = getattr(hungriest, "_starved_ticks", 0) if hungriest else 0
            grace_note = ""
            if hs > 0:
                left = World.STARVE_GRACE - hs
                grace_note = (f"; hungriest is {hungriest.name} "
                              + (f"(grace left {left})" if left > 0
                                 else f"(STARVING, hazard open {-left})"))
            arrow = "↓ leaner" if live_met < founder_met - 0.005 else (
                    "↑ hungrier" if live_met > founder_met + 0.005 else "≈")
            print(f"  --- t{t}: {len(w.agents)} souls | appetite {live_met:.3f} "
                  f"(from {founder_met:.3f}) {arrow}{grace_note}")

    live_met = _met0([a.genome for a in w.agents if getattr(a, "genome", None)])
    print(f"\n=== after {args.ticks} ticks ===")
    print(f"  {len(w.agents)} souls alive  |  {len(starved)} lineages starved out  |  "
          f"{len(born)} born of plenty")
    if len(starved) >= 2 and live_met < founder_met - 0.005:
        note = "leaner -- the hungriest lineages starved out (selection)"
    elif len(born) >= 2:
        note = "drifted only by birth-mutation (nobody starved; a kind world selects little)"
    else:
        note = "little change at this scale (few deaths -- selection is slow at n=8)"
    print(f"  town appetite: {founder_met:.3f} (founders) -> {live_met:.3f} (now)  [{note}]")
    print("\n(this is the MECHANISM you can watch -- deaths, grace, births, the appetite "
          "drift.\n the error-barred VERDICT is experiment_selection.py, and the harsh-vs-"
          "gentle\n divergence is directional at n=8: confirming it wants engine-scale "
          "populations.)")


if __name__ == "__main__":
    main()
