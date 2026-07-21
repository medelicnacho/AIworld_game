"""THE ATTENTION SCHEMA FALSIFIER (WORKSPACE_NEXT W1 / RESEARCH C1).

§5.14 asked the FLOOR to forecast the MIND'S MOOD and it could not -- PREDICTION 0/5,
"the floor is a readout, not a forecaster." This does not ask more of the floor. It builds
a separate small model whose only job is to predict the floor (agent/schema.py), and asks
whether THAT model earns its place. Graziano's AST: awareness is a caricature of one's own
attention, useful because it predicts.

PRE-REGISTERED (tuning on seeds 11-15; VERDICT from virgin seeds 41-45; a claim passes at
>= 4/5 seeds):

  A1 THE SCHEMA PREDICTS. Next-reign accuracy beats the MARGINAL BASE RATE -- the accuracy
     of always guessing the single most common floor-holder. This is the right null and a
     hard one: a mind dominated by one part is trivially predictable, so the schema must
     beat that, not merely score high.

  A2 SURPRISE IS ABOUT HERSELF. Ticks where the schema is violated carry higher mean
     AROUSAL than unviolated ticks -- being wrong about oneself is felt.

  NULL (the integrity check): the same schema fed a SHUFFLED floor log must NOT beat its
  own base rate. Shuffling destroys the succession structure while preserving every part's
  share, so anything left is bookkeeping, not modelling.

The hardship schedule is JITTERED, never periodic -- §5.14's own null-integrity lesson: a
periodic schedule hands a shift null the very structure under test.

  python3 experiment_schema.py                # tuning read (seeds 11-15)
  python3 experiment_schema.py --heldout      # THE VERDICT (virgin seeds 41-45)
"""
from __future__ import annotations

import argparse
import random
import statistics

from agent.agent import Agent
from agent.psyche import FACULTY_OF, PSYCHE_CAST, endow_part
from agent.schema import AttentionSchema
from agent.workspace import Workspace
from scripts.stats import summary
from services.llm import MockLLM
from world.events import WorldEvent
from world.sim import World

TICKS = 600
HARDSHIP_P = 0.06          # per-tick chance of a blow -- JITTERED, not a period


def build(seed: int) -> World:
    rng = random.Random(seed)
    w = World(rebirth_enabled=False, events_enabled=False)
    w.llm = MockLLM(seed=seed)
    w.psyche = Workspace()
    w.schema_enabled = True
    for i, (name, persona, temp, _aim, phrases) in enumerate(PSYCHE_CAST):
        a = Agent(f"p{i}", name, (rng.uniform(0, 300), rng.uniform(0, 300)), persona,
                  list(phrases), w.llm, seed=seed + i, temperament=temp, lifespan=10 ** 9)
        endow_part(a, FACULTY_OF[name], rng)
        # A2 reads AROUSAL, which lives in the expectation faculty -- without appraisal
        # there is no surprise and arousal is dead flat at 0.0 (§5.27's recorded lesson,
        # paid for once already: "arousal is dead without appraisal (no expectation, no
        # shock)"). The first run of this experiment measured 0.000 on every tick.
        a.expect_enabled = True
        w.add(a)
    return w


def run(seed: int) -> dict:
    """One mind, TICKS long. Records the floor log and, per tick, whether the schema was
    violated and what the mind's arousal was."""
    w = build(seed)
    rng = random.Random(seed * 7 + 1)
    rows = []
    for t in range(1, TICKS + 1):
        if rng.random() < HARDSHIP_P:
            ev = WorldEvent("hardship", "the winter bites and something is lost", t,
                            emotion=-0.8, urge=0.5)
            for a in w.agents:
                a.perceive(ev, t)
        before = len(w.psyche.schema.violations) if w.psyche.schema else 0
        w.step(speak=False)
        sch = w.psyche.schema
        if sch is None:
            continue
        arousal = statistics.fmean([max(0.0, min(1.0, getattr(a, "arousal", 0.0)))
                                    for a in w.agents]) if w.agents else 0.0
        rows.append({"violated": len(sch.violations) > before, "arousal": arousal})
    return {"schema": w.psyche.schema, "log": list(w.psyche.log), "rows": rows}


def persistence(log: list) -> float:
    """Always guess "the same as now". The HARD null: reigns last ~4 ticks, so this is
    right ~77% of the time and any sequence model must clear it before its transition
    structure has been shown to add anything at all. Not the pre-registered A1 bar (that
    is the marginal base rate, as written); reported beside it because a claim that only
    beats the easy null should never be read as if it beat this one."""
    if len(log) < 2:
        return 0.0
    return sum(1 for a, b in zip(log, log[1:]) if a == b) / (len(log) - 1)


def base_rate(log: list) -> float:
    """Always guess the most common floor-holder. The null A1 must beat."""
    if not log:
        return 0.0
    counts: dict = {}
    for x in log:
        counts[x] = counts.get(x, 0) + 1
    return max(counts.values()) / len(log)


def replay(log: list) -> float | None:
    """Feed a log to a fresh schema and report its accuracy -- used for the shuffled null."""
    s = AttentionSchema()
    for i, x in enumerate(log):
        s.observe(x, tick=i)
    return s.accuracy()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--heldout", action="store_true", help="the VERDICT seeds (41-45)")
    args = p.parse_args()
    seeds = [41, 42, 43, 44, 45] if args.heldout else [11, 12, 13, 14, 15]
    print(f"=== the attention schema: does a model of the floor predict it? "
          f"({'HELD-OUT VERDICT' if args.heldout else 'tuning'} seeds {seeds[0]}..{seeds[-1]}) ===\n")
    print(f"  {'seed':<6}{'acc':>8}{'base':>8}{'gain':>8}{'persist':>9}{'shuf':>8}"
          f"{'arous+':>9}{'arous-':>9}{'viol':>7}")
    a1, a1b, a2, nulls, gains, lifts = [], [], [], [], [], []
    for sd in seeds:
        r = run(sd)
        sch = r["schema"]
        acc, base = sch.accuracy(), base_rate(r["log"])
        shuf_log = list(r["log"])
        random.Random(sd).shuffle(shuf_log)
        shuf = replay(shuf_log) or 0.0
        hot = [x["arousal"] for x in r["rows"] if x["violated"]]
        cold = [x["arousal"] for x in r["rows"] if not x["violated"]]
        mh = statistics.fmean(hot) if hot else float("nan")
        mc = statistics.fmean(cold) if cold else float("nan")
        gains.append((acc or 0.0) - base)
        lifts.append((mh - mc) if hot and cold else 0.0)
        pers = persistence(r["log"])
        a1.append((acc or 0.0) > base)
        a1b.append((acc or 0.0) > pers)
        a2.append(bool(hot) and bool(cold) and mh > mc)
        nulls.append(shuf > base_rate(shuf_log))
        print(f"  {sd:<6}{(acc or 0.0):>8.3f}{base:>8.3f}{gains[-1]:>+8.3f}{pers:>9.3f}"
              f"{shuf:>8.3f}{mh:>9.3f}{mc:>9.3f}{len(hot):>7}")
    print(f"\n  A1 gain over base rate: {summary(gains)}")
    print(f"  A2 arousal lift on violated ticks: {summary(lifts)}")
    print(f"\n  -> A1 SCHEMA PREDICTS (beats base rate):        {sum(a1)}/{len(seeds)}"
          f"  {'PASS' if sum(a1) >= 4 else 'FAIL'}")
    print(f"     A1b ... and beats PERSISTENCE (the hard null): {sum(a1b)}/{len(seeds)}"
          f"  {'PASS' if sum(a1b) >= 4 else 'FAIL -- it models that the floor STAYS, not where it GOES'}")
    print(f"     A2 SURPRISE IS FELT (arousal higher):        {sum(a2)}/{len(seeds)}"
          f"  {'PASS' if sum(a2) >= 4 else 'FAIL'}")
    print(f"     NULL shuffled log beats its base rate:       {sum(nulls)}/{len(seeds)}"
          f"  {'(BAD -- structure is not what is being read)' if sum(nulls) >= 2 else '(good: 0-1)'}")
    ok = sum(a1) >= 4 and sum(a2) >= 4 and sum(nulls) <= 1
    print(f"\n  VERDICT: {'THE SCHEMA EARNS ITS PLACE' if ok else 'did NOT show the signature'}"
          f" -- see the table.")


if __name__ == "__main__":
    main()
