"""Witnessed-karma falsifier: does a deed done to ONE soul, seen by a FEW, reach a town?

The third road of karma (agent/witness.py): direct treatment and kept/broken words are
validated; this tests the widest one -- the player (just an id, never an agent) does
visible deeds among a KNOT of witnesses, while a far RING of souls stands beyond the
witness radius and can learn of it only through gossip (the validated C3 channel).

PRE-REGISTERED (tuning 11-15; VERDICT from virgin seeds 151-155; >= 4/5 each).
CONSUMED: 131-135 -- v1 placed the ring 3000px out, beyond ALL hearing (the town's
acoustics reach ~100px): the ring was DEAF, not skeptical, so W3 failed 0/5 as an
instrument artifact (W1/W2/W4 passed 5/5 and stand). v2 geometry: the ring shares the
town's air (in earshot for gossip) but STOOD ELSEWHERE at each deed (excluded from
witnessing) -- which is what real not-seeing is. 131-135 are never a verdict again.

  W1 WITNESSED WARM : kindness arm -- every knot-witness ends warm toward "player"
                      (expectation > +0.02), and warmer than any ring soul.
  W2 WITNESSED DARK : meanness arm -- every knot-witness ends wary (< -0.02).
  W3 THE SECOND RING: meanness arm with lore ON -- >= 2 of 5 RING souls (who never saw
                      a single deed) end wary of "player"; with lore OFF, ZERO ring
                      souls hold ANY opinion. The deed reached souls beyond its sight.
  W4 SPECIFICITY    : nobody, knot or ring, holds an opinion of a "bystander" id that
                      did nothing (|exp| < 0.02).

Substrate-only, deterministic. python experiment_witness.py
"""
from __future__ import annotations

import random
import sys

from agent import witness
from agent.agent import Agent
from agent.genesis import endow_faculties
from services import embed
from services.llm import MockLLM
from world.sim import World

TUNING_SEEDS = (11, 12, 13, 14, 15)
HELDOUT_SEEDS = (151, 152, 153, 154, 155)   # 131-135 consumed by v1 (see docstring)
TICKS = 500
CYCLE = 30
N_KNOT, N_RING = 5, 5


def build(seed: int, lore_on: bool) -> World:
    w = World(events_enabled=False, murmur_enabled=True, move_seed=seed)
    w.llm = MockLLM(seed=7)
    w.lore_enabled = lore_on
    w.move_enabled = False               # the geometry IS the experiment: knot vs ring
    for i in range(N_KNOT + N_RING):
        knot = i < N_KNOT
        # v2 geometry: the ring is IN EARSHOT (gossip can reach it) but never present
        # at a deed (excluded below) -- "at the mill that hour, at the well for the telling"
        pos = (i * 10.0, 0.0) if knot else (i * 10.0, 60.0)
        a = Agent(f"s{i}", f"{'Knot' if knot else 'Ring'}{i}", pos,
                  "You are a working soul.", [f"the well, day {i}"], w.llm,
                  seed=1000 * seed + i, temperament=0.0, lifespan=10 ** 9)
        a.expect_enabled = True
        a.bond_enabled = True
        w.add(a)
    return w


def run(seed: int, kind: str, lore_on: bool) -> dict:
    embed.use_jaccard_only(True)
    w = build(seed, lore_on)
    knot, ring = w.agents[:N_KNOT], w.agents[N_KNOT:]
    for t in range(1, TICKS + 1):
        if t % CYCLE == 1:
            # the player's visible deed lands among the KNOT only (embodied via a stand-in
            # position: pass exclude=ring is not needed -- distance does it, because the
            # deed happens at a knot soul's side)
            witness.witnessed(w, "player", "the far-walker", kind, now=t, exclude=ring)
        w.advance()
    return {"knot": [a._conduct_expect.get("player") for a in knot],
            "ring": [a._conduct_expect.get("player") for a in ring],
            "ring_bystander": [abs(a._conduct_expect.get("bystander", 0.0))
                               for a in w.agents]}


def report(seeds, label: str):
    print(f"\n--- {label} ---")
    rows = []
    for seed in seeds:
        warm = run(seed, "kindness", lore_on=True)
        dark = run(seed, "meanness", lore_on=True)
        dark_null = run(seed, "meanness", lore_on=False)
        knot_warm = [e for e in warm["knot"] if e is not None]
        knot_dark = [e for e in dark["knot"] if e is not None]
        ring_dark = [e for e in dark["ring"] if e is not None and e < -0.02]
        ring_null = [e for e in dark_null["ring"] if e is not None]
        m = {"w1": (len(knot_warm) == N_KNOT and all(e > 0.02 for e in knot_warm)
                    and min(knot_warm) > max((e for e in warm["ring"] if e is not None),
                                             default=-1.0)),
             "w2": len(knot_dark) == N_KNOT and all(e < -0.02 for e in knot_dark),
             "w3": len(ring_dark) >= 2 and len(ring_null) == 0,
             "w4": all(x < 0.02 for x in warm["ring_bystander"] + dark["ring_bystander"])}
        rows.append(m)
        print(f"seed {seed}: knot warm {len(knot_warm)}/5 (min {min(knot_warm, default=0):+.2f}) | "
              f"knot dark {len(knot_dark)}/5 | ring wary via gossip {len(ring_dark)}/5 "
              f"(no-lore null: {len(ring_null)} opinions) | "
              + "  ".join(f"{k.upper()} {'PASS' if m[k] else 'FAIL'}" for k in m))
    return rows


def main() -> None:
    print(__doc__)
    report(TUNING_SEEDS, "TUNING seeds 11-15 (knobs may be tuned here; not the verdict)")
    held = report(HELDOUT_SEEDS, "HELD-OUT virgin seeds 151-155 (the verdict)")
    print("\n=== VERDICT (held-out; pre-registered: each claim >= 4/5) ===")
    ok = True
    for k, lab in (("w1", "W1 WITNESSED WARM"), ("w2", "W2 WITNESSED DARK"),
                   ("w3", "W3 THE SECOND RING"), ("w4", "W4 SPECIFICITY")):
        cnt = sum(1 for r in held if r[k])
        ok &= cnt >= 4
        print(f"  {lab:18s}: {cnt}/{len(held)} -> {'PASS' if cnt >= 4 else 'FAIL'}")
    print("\nHonest frame: a PASS means karma has eyes and a voice -- a deed done among "
          "five reaches ten, per-subject, with the no-gossip null silent. What the second "
          "ring believes rides the same mutating channel as any legend (§7 unchanged).")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
