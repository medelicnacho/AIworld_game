"""Allegiance falsifier (Phase B): does a town's ARMY assemble from its actual life?

End-to-end: the player (an id, never an agent) lives among a lore-enabled town for a
season, building a name ONLY through the validated karma roads -- pledges kept or broken
(§5.20), deeds witnessed and gossiped (witness falsifier) -- and then asks the town to
stand with them. No loyalty scalar exists; allegiance.decide() reads what the season
actually made true.

PRE-REGISTERED (tuning 11-15; VERDICT from virgin seeds 161-165; each >= 4/5):

  A1 THE WARM NAME MUSTERS : a kept-word, seen-kindness season recruits more JOINs than
                             a broken-word, seen-meanness season, every seed -- and the
                             dark season recruits zero.
  A2 KARMA IS LOAD-BEARING : re-muster with the reputation channel SILENCED (conduct-
                             expectations zeroed): the warm-vs-dark join gap collapses
                             toward zero -- the difference WAS the karma, not noise.
  A3 THE INNOCENT          : a stranger who never acted gets ONE planted false telling
                             (a dark-worded conduct story seeded into two souls); after
                             the gossip runs, souls who never saw anything stand against
                             or away from the innocent -- and in the no-plant twin, all
                             verdicts are 'hardly know'. Emergent injustice, traceable
                             to the single lie that started it.
  A4 THE WORN STAY OUT     : collapse half the town by famine; at danger 0.8 every
                             collapsed soul refuses ('too worn') regardless of warm
                             bonds, while the hale with warm bonds join. The somatic
                             floor extends to war, every seed.

Deterministic, substrate-only.  python experiment_allegiance.py

OUTCOME (2026-07-03, seeds 161-165 consumed -- never a verdict again):
  A3 THE INNOCENT   PASS 5/5 -- one planted lie made ~8 souls stand against a stranger
                    who never did anything, while the no-plant twin stayed entirely
                    'hardly know'. Emergent injustice, traceable to the single lie.
  A4 THE WORN       PASS 5/5 -- every famine-collapsed soul refused the war regardless
                    of deep warm bonds ('too worn'); the hale joined. The somatic floor
                    extends to war.
  A1/A2             FAIL 3/5 -- fragile, not false: one 400-tick season of kept pledges
                    builds only ~0.1 trust, and joining DANGER at a season's
                    acquaintance sits exactly at JOIN_AT. Warm > dark held in every
                    seed where anyone joined at all, and the dark season recruited ZERO
                    joins in all 10 held-out arms. Honest reading: a season of kept
                    words makes a town stop distrusting you; AN ARMY TAKES LONGER THAN
                    A SEASON -- which may be the correct psychology, and is recorded as
                    the finding. A longer-courtship re-verdict (700+ ticks, deeper
                    pledge history) may run on virgin 171-175 if the claim is retried.

V2, THE LONG COURTSHIP (--long): that retry -- 900-tick seasons (2.25x the kept words
per soul), A1/A2 ONLY (A3/A4 stand at 5/5 and are not re-run), same bars, VERDICT from
virgin seeds 171-175. If it passes, the army story completes: armies assemble from
EARNED history, measured. If it fails, v1's finding deepens on the record.
"""
from __future__ import annotations

import random
import sys

from agent import allegiance, pledge, witness
from agent.agent import Agent
from agent.bond import Bond
from agent.genesis import endow_faculties
from services import embed
from services.llm import MockLLM
from world.sim import World

TUNING_SEEDS = (11, 12, 13, 14, 15)
HELDOUT_SEEDS = (161, 162, 163, 164, 165)   # CONSUMED by v1 (see docstring)
HELDOUT_V2 = (171, 172, 173, 174, 175)      # virgin, for --long
TICKS = 400
TICKS_V2 = 900
CYCLE = 30
N = 8


def build(seed: int, lore_on: bool = True) -> World:
    w = World(events_enabled=False, murmur_enabled=True, move_seed=seed)
    w.llm = MockLLM(seed=7)
    w.lore_enabled = lore_on
    w.move_enabled = False
    for i in range(N):
        a = Agent(f"s{i}", f"F{i}", (i * 10.0, 0.0), "You are a working soul.",
                  [f"the well, day {i}"], w.llm, seed=1000 * seed + i,
                  temperament=0.0, lifespan=10 ** 9)
        endow_faculties(a, rng := random.Random(1000 * seed + i))
        a.bond_enabled = True
        a.expect_enabled = True
        a.boldness = rng.uniform(0.3, 0.7)
        w.add(a)
    return w


def season(seed: int, kind: str, ticks: int = TICKS) -> World:
    """A season of the player among the town: warm (kept words, seen kindness) or dark
    (broken words, seen meanness). Reputation forms ONLY through the validated roads."""
    w = build(seed)
    rng = random.Random(seed)
    for t in range(1, ticks + 1):
        if t % CYCLE == 1:
            soul = rng.choice(w.agents)
            if kind == "warm":
                pledge.make(soul, "player", "the far-walker", "I will bring what you need",
                            due_tick=t + 15, now=t)
                pledge.fulfill(soul, "player", now=t + rng.randint(2, 10))
                witness.witnessed(w, "player", "the far-walker", "kindness", now=t)
            else:
                pledge.make(soul, "player", "the far-walker", "I will bring what you need",
                            due_tick=t + 10, now=t)      # ...and let the clock break it
                witness.witnessed(w, "player", "the far-walker", "meanness", now=t)
        w.advance()
    return w


def report(seeds, label: str, ticks: int = TICKS, courtship_only: bool = False):
    print(f"\n--- {label} ---")
    rows = []
    for seed in seeds:
        warm_w, dark_w = season(seed, "warm", ticks), season(seed, "dark", ticks)
        warm = allegiance.muster(warm_w, "player", danger=0.2)
        dark = allegiance.muster(dark_w, "player", danger=0.2)
        a1 = len(warm["join"]) > len(dark["join"]) and len(dark["join"]) == 0
        # A2: silence the karma roads and re-ask -- the gap was the reputation
        for w2 in (warm_w, dark_w):
            for a in w2.agents:
                a._conduct_expect.pop("player", None)
        warm0 = allegiance.muster(warm_w, "player", danger=0.2)
        dark0 = allegiance.muster(dark_w, "player", danger=0.2)
        gap, gap0 = (len(warm["join"]) - len(dark["join"]),
                     len(warm0["join"]) - len(dark0["join"]))
        a2 = gap > gap0
        if courtship_only:      # --long re-verdicts ONLY the courtship claims
            rows.append({"a1": a1, "a2": a2})
            print(f"seed {seed}: warm joins {len(warm['join'])} vs dark "
                  f"{len(dark['join'])} (silenced gap {gap0}) | "
                  f"A1 {'PASS' if a1 else 'FAIL'}  A2 {'PASS' if a2 else 'FAIL'}")
            continue
        # A3: the innocent -- one planted lie in a fresh town, vs a no-plant twin
        w3 = build(seed)
        for a in w3.agents[:2]:
            a.memory.write("they say the stranger raided the commons while others went "
                           "hungry -- a bitter, broken thing", tick=1, source="heard",
                           emotion=-0.55, weight=1.2, lore_id="conduct:stranger")
        for _ in range(TICKS):
            w3.advance()
        m3 = allegiance.muster(w3, "stranger", danger=0.2)
        w3c = build(seed)
        for _ in range(TICKS):
            w3c.advance()
        m3c = allegiance.muster(w3c, "stranger", danger=0.2)
        wary = [a for a in w3.agents[2:] if a._conduct_expect.get("stranger", 0) < -0.02]
        a3 = (len(m3["oppose"]) >= 1 and wary
              and len(m3c["oppose"]) == 0
              and all("hardly know" in r for r in m3c["reasons"].values()))
        # A4: the worn stay out -- warm bonds everywhere, famine takes half
        w4 = build(seed)
        for a in w4.agents:
            a.bonds["player"] = Bond(trust=0.8, history=2.5)
        for a in w4.agents[:N // 2]:
            a.wellbeing = 0.1                       # the famine's half
        m4 = allegiance.muster(w4, "player", danger=0.8)
        worn = set(a.id for a in w4.agents[:N // 2])
        a4 = (all(a.id not in worn for a in m4["join"])
              and all(a.id in worn for a in m4["refuse"])
              and all("worn" in m4["reasons"][i] for i in worn))
        rows.append({"a1": a1, "a2": a2, "a3": a3, "a4": a4})
        print(f"seed {seed}: warm joins {len(warm['join'])} vs dark {len(dark['join'])} "
              f"(silenced gap {gap0}) | innocent: {len(m3['oppose'])} oppose, "
              f"{len(wary)} wary-by-gossip (twin: {len(m3c['oppose'])}) | "
              f"worn out {len(m4['refuse'])}/{N // 2} | "
              + "  ".join(f"{k.upper()} {'PASS' if rows[-1][k] else 'FAIL'}" for k in rows[-1]))
    return rows


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--long", action="store_true",
                    help="v2: 900-tick courtship, A1/A2 only, virgin seeds 171-175")
    args = ap.parse_args()
    print(__doc__)
    if args.long:
        report(TUNING_SEEDS, "V2 TUNING seeds 11-15 (900 ticks; never a verdict)",
               ticks=TICKS_V2, courtship_only=True)
        held = report(HELDOUT_V2, "V2 HELD-OUT virgin seeds 171-175 (the verdict)",
                      ticks=TICKS_V2, courtship_only=True)
        print("\n=== V2 VERDICT (held-out; pre-registered: each claim >= 4/5) ===")
        ok = True
        for k, lab in (("a1", "A1 THE WARM NAME MUSTERS"),
                       ("a2", "A2 KARMA IS LOAD-BEARING")):
            cnt = sum(1 for r in held if r[k])
            ok &= cnt >= 4
            print(f"  {lab:25s}: {cnt}/{len(held)} -> {'PASS' if cnt >= 4 else 'FAIL'}")
        print("\n(A3/A4 stand at 5/5 from v1 and were not re-run.)")
        sys.exit(0 if ok else 1)
    report(TUNING_SEEDS, "TUNING seeds 11-15 (knobs may be tuned here; not the verdict)")
    held = report(HELDOUT_SEEDS, "HELD-OUT virgin seeds 161-165 (the verdict)")
    print("\n=== VERDICT (held-out; pre-registered: each claim >= 4/5) ===")
    ok = True
    for k, lab in (("a1", "A1 THE WARM NAME MUSTERS"), ("a2", "A2 KARMA IS LOAD-BEARING"),
                   ("a3", "A3 THE INNOCENT"), ("a4", "A4 THE WORN STAY OUT")):
        cnt = sum(1 for r in held if r[k])
        ok &= cnt >= 4
        print(f"  {lab:25s}: {cnt}/{len(held)} -> {'PASS' if cnt >= 4 else 'FAIL'}")
    print("\nHonest frame: a PASS means an army is a HISTORY, not a stat -- who stands "
          "with you is derived from kept words, seen deeds, gossip (fair and unfair), "
          "and bodies that remember. The injustice in A3 is a feature to OBSERVE and a "
          "warning to carry: reputations ride the same mutating channel as any legend.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
