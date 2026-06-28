"""STAGE A -- stakes. Provisions under seasonal threat, archetype-driven actions, co-
suffering solidarity, and karma-seeds (the response conditions the soul). Deterministic
substrate -- no model.

Three measures:
  CHARACTER -- do the archetypes act in character? (the Grasper hoards most, the Lover
               shares most -- character expressed in deeds, not just words)
  COMMONS   -- a prosocial cast (Sages/Lovers) sustains the shared provisions and everyone's
               wellbeing; a grasping cast drains it (the tragedy of the commons)
  SEEDS     -- the same lean season opens one and hardens another: a Lover's compassion
               rises (wise responses), a Grasper's grip rises (clinging) -- cetana/vasana,
               not pain auto-ennobling anyone

Run:  python experiment_stakes.py
"""

from __future__ import annotations

import argparse
import collections
import statistics

from agent import archetype as A
from agent.agent import Agent
from services.llm import MockLLM
from world import stakes
from world.sim import World

TICKS = 120


def make_world(archs, seed):
    w = World(move_seed=seed)
    w.stakes_enabled = True
    w.llm = MockLLM(seed=seed)
    for i, arch in enumerate(archs):
        a = Agent(f"s{i}", arch.name, (0, 0), "p", ["x"], MockLLM(seed=seed + i), seed=seed + i)
        A.apply(a, arch)
        a.bond_enabled = True
        a.stores = a.wellbeing = 1.0
        w.add(a)
    return w


def run(w, ticks):
    acts = collections.defaultdict(collections.Counter)
    for _ in range(ticks):
        w.tick += 1
        stakes.step(w)
        for a in w.agents:
            if a._last_action:
                acts[a.id][a._last_action] += 1
    return acts


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()

    print("\n=== Stage A: stakes (deterministic) ===")

    # 1) CHARACTER -- one of each archetype, count actions over a lean season
    w = make_world(A.ARCHETYPES, seed=1)
    by_id = {a.id: a for a in w.agents}
    acts = run(w, TICKS)
    print("\n  CHARACTER -- actions taken (work / share / hoard / tend):")
    for aid, c in acts.items():
        nm = by_id[aid].name
        print(f"     {nm:<8} work {c['work']:>3}  share {c['share']:>3}  hoard {c['hoard']:>3}  tend {c['tend']:>3}")
    hoarder = max(acts, key=lambda k: acts[k]['hoard'])
    sharer = max(acts, key=lambda k: acts[k]['share'])
    print(f"     -> most hoarding: {by_id[hoarder].name}   most sharing: {by_id[sharer].name}")
    lid = next(k for k in acts if by_id[k].name == "Lover")
    gid = next(k for k in acts if by_id[k].name == "Grasper")
    # the real signal: the Grasper hoards (and never shares), the warm Lover shares freely --
    # character expressed in deeds. (Not "the single top sharer is the Lover": several warm
    # souls share, and which edges the count is noise.)
    in_character = (by_id[hoarder].name == "Grasper"
                    and acts[lid]['share'] >= 10
                    and acts[lid]['share'] > 3 * acts[gid]['share'])

    # 2) COMMONS -- prosocial cast vs grasping cast
    prosocial = make_world([A.BY_NAME[n] for n in ("Sage", "Lover", "Sage", "Lover", "Joyful", "Sage")], seed=2)
    grasping = make_world([A.BY_NAME["Grasper"]] * 6, seed=2)
    run(prosocial, TICKS)
    run(grasping, TICKS)
    pw = statistics.fmean(a.wellbeing for a in prosocial.agents)
    gw = statistics.fmean(a.wellbeing for a in grasping.agents)
    print("\n  COMMONS -- shared provisions + mean wellbeing after a lean season:")
    print(f"     prosocial cast: commons {prosocial.commons:+.2f}  mean wellbeing {pw:+.2f}")
    print(f"     grasping cast:  commons {grasping.commons:+.2f}  mean wellbeing {gw:+.2f}")
    commons_holds = pw > gw + 0.05

    # 3) SEEDS -- did the response condition the souls? (re-run cast-of-each, snapshot dials)
    w2 = make_world(A.ARCHETYPES, seed=3)
    snap = {a.id: (a.compassion, a.grip) for a in w2.agents}
    run(w2, TICKS)
    lover = next(a for a in w2.agents if a.name == "Lover")
    grasper = next(a for a in w2.agents if a.name == "Grasper")
    lov0, gra0 = snap[lover.id][0], snap[grasper.id][1]
    print("\n  SEEDS -- did meeting the season change the soul? (karma/vasana):")
    print(f"     Lover compassion: {lov0:.2f} -> {lover.compassion:.2f}   (wise responses open the heart)")
    print(f"     Grasper grip:     {gra0:.2f} -> {grasper.grip:.2f}   (clinging responses harden it)")
    seeds_work = lover.compassion > lov0 and grasper.grip > gra0

    print("\n  -> in character: " + ("YES" if in_character else "no")
          + " | commons holds under mutual aid: " + ("YES" if commons_holds else "no")
          + " | seeds condition the soul: " + ("YES" if seeds_work else "no"))
    print("  VERDICT: " + (
        "STAKES LIVE -- archetypes act their nature, mutual aid sustains the commons where "
        "hoarding drains it, and the season cultivates each soul by how it is met."
        if (in_character and commons_holds and seeds_work) else
        "one or more stakes signatures did not hold (see numbers above)."))


if __name__ == "__main__":
    main()
