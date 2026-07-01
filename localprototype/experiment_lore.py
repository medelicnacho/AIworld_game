"""Lore falsifier: does a real event outlive its witnesses as a TRACEABLE, MUTATED legend?

The claim (agent/lore.py): retelling -- transmission of each holder's CURRENT, drifting text,
sparse enough that rehearsal doesn't freeze it -- lets one witnessed event survive generations of
the rebirth wheel as a legend: changed in the telling, still recognisably about the thing that
happened. Substrate-only (MockLLM, embeddings off, no speech turns -- the world runs on
advance(): murmur + lore + the wheel).

One event at t=50, witnessed by 3 of 8 souls: "the great flood in the night took the miller's
child and half the winter stores" (lore_id ground truth). Lifespans 250-450 of a 2000-tick run,
so every witness -- every FOUNDER -- is long dead at the end; whatever the living carry, they
got it through the chain.

PRE-REGISTERED (a carrier = a living soul holding ANY memory with word-overlap >= 0.25 to the
original -- mechanism-blind, same metric both arms):

  1. TRANSMISSION : the LORE arm ends with >= 1 carrier AND more carriers than the MURMUR-ONLY
                    null arm (the existing ambient channel: drift fragments, no retelling). If
                    murmur alone preserves the story, retelling added nothing.
  2. LEGEND       : the dominant surviving variant's text is NOT the original verbatim -- it
                    changed in the telling. (A frozen record would mean rehearsal fossilised it.)
  3. TRACEABLE    : ...yet still overlaps the original by >= 0.25 -- a historian (or a player)
                    could trace the legend back to the event. (Unbounded drift = FAIL.)
  4. CONVERGENCE  : the largest similarity-cluster of surviving tagged variants holds >= 0.5 of
                    them -- the community converges toward a canonical telling, not a shatter of
                    unrelated shards.
  5. PATH-DEPENDENCE (per seed-set): different seeds settle on DIFFERENT dominant variants
                    (mean pairwise overlap among them < 0.9) -- history, not design, picks the
                    telling.

  Knobs tuned on SEEDS 11-15 if needed; the verdict comes from HELD-OUT SEEDS 21-25. Claims
  1-4 pass at >= 4/5 seeds. FAILs get recorded.

  python experiment_lore.py
"""
from __future__ import annotations

import statistics
from itertools import combinations

from agent.agent import Agent
from agent.memory import _similarity
from services import embed
from services.llm import MockLLM
from world.events import WorldEvent
from world.sim import World

TUNING_SEEDS = (11, 12, 13, 14, 15)
HELDOUT_SEEDS = (21, 22, 23, 24, 25)
TICKS = 2000
N_SOULS = 8
N_WITNESS = 3
STORY = "the great flood in the night took the miller's child and half the winter stores"
LORE_ID = "the-flood"
CARRY_OVERLAP = 0.25


def build(seed: int, lore_on: bool) -> World:
    w = World(events_enabled=True, rebirth_enabled=True, murmur_enabled=True, move_seed=seed,
              events=[WorldEvent(name="flood", description=STORY, tick=50, emotion=-0.7,
                                 urge=0.6, scope=tuple(f"s{i}" for i in range(N_WITNESS)),
                                 lore_id=LORE_ID)])
    w.llm = MockLLM(seed=7)
    w.lore_enabled = lore_on
    w.bardo_ticks = (5, 10)
    rng_positions = [(i * 15.0, 0.0) for i in range(N_SOULS)]   # one knot, all in earshot
    for i in range(N_SOULS):
        a = Agent(f"s{i}", f"Soul{i}", rng_positions[i], "You are a working soul.",
                  [f"the well, the field, the road, day {i}"], w.llm,
                  seed=1000 * seed + i, temperament=0.0,
                  lifespan=250 + ((seed * 37 + i * 53) % 200))
        w.add(a)
    return w


def run(seed: int, lore_on: bool) -> dict:
    embed.use_jaccard_only(True)
    w = build(seed, lore_on)
    for _ in range(TICKS):
        w.advance()
    founders_alive = [a for a in w.agents if not a.id.startswith("stream:")]
    carriers, tagged = [], []
    for a in w.agents:
        best = max((_similarity(m.text, STORY) for m in a.memory.items), default=0.0)
        if best >= CARRY_OVERLAP:
            carriers.append(a)
        tagged += [m for m in a.memory.items if getattr(m, "lore_id", "") == LORE_ID]
    return {"founders_alive": len(founders_alive), "carriers": len(carriers),
            "tagged": tagged, "pop": len(w.agents)}


def dominant_variant(tagged) -> tuple[str, float]:
    """Greedy similarity-clustering of the surviving variants; returns the biggest
    cluster's most salient text and that cluster's share of all variants."""
    if not tagged:
        return "", 0.0
    clusters: list[list] = []
    for m in sorted(tagged, key=lambda m: -m.salience):
        for c in clusters:
            if _similarity(m.text, c[0].text) >= 0.6:
                c.append(m)
                break
        else:
            clusters.append([m])
    top = max(clusters, key=len)
    return top[0].text, len(top) / len(tagged)


def report(seeds, label: str):
    print(f"\n--- {label} ---")
    rows, dominants = [], []
    for seed in seeds:
        lore_arm = run(seed, lore_on=True)
        null_arm = run(seed, lore_on=False)
        text, share = dominant_variant(lore_arm["tagged"])
        overlap = _similarity(text, STORY) if text else 0.0
        m = {"transmission": (lore_arm["founders_alive"] == 0 and lore_arm["carriers"] >= 1
                              and lore_arm["carriers"] > null_arm["carriers"]),
             "legend": bool(text) and set(text.lower().split()) != set(STORY.lower().split()),
             "traceable": overlap >= CARRY_OVERLAP,
             "convergence": share >= 0.5}
        rows.append(m)
        dominants.append(text)
        print(f"\nseed {seed}: lore carriers {lore_arm['carriers']}/{lore_arm['pop']} vs "
              f"murmur-only {null_arm['carriers']}/{null_arm['pop']} "
              f"(founders alive: {lore_arm['founders_alive']})")
        print(f"  1 transmission : -> {'PASS' if m['transmission'] else 'FAIL'}")
        print(f"  2 legend       : changed in the telling -> {'PASS' if m['legend'] else 'FAIL'}")
        print(f"  3 traceable    : overlap {overlap:.2f} -> {'PASS' if m['traceable'] else 'FAIL'}")
        print(f"  4 convergence  : top-variant share {share:.2f} -> "
              f"{'PASS' if m['convergence'] else 'FAIL'}")
        if text:
            print(f"  the legend now : \"{text}\"")
    pairs = [(_similarity(a, b)) for a, b in combinations([d for d in dominants if d], 2)]
    path_dep = bool(pairs) and statistics.fmean(pairs) < 0.9
    print(f"\n  {label} tally:")
    for key, lab in (("transmission", "1 TRANSMISSION"), ("legend", "2 LEGEND"),
                     ("traceable", "3 TRACEABLE"), ("convergence", "4 CONVERGENCE")):
        print(f"    {lab:15s}: {sum(1 for r in rows if r[key])}/{len(rows)}")
    print(f"    5 PATH-DEP     : mean cross-seed overlap "
          f"{statistics.fmean(pairs) if pairs else 1.0:.2f} -> {'PASS' if path_dep else 'FAIL'}")
    return rows, path_dep


def main() -> None:
    print(__doc__)
    report(TUNING_SEEDS, "TUNING seeds 11-15 (knobs may be tuned here; not the verdict)")
    rows, path_dep = report(HELDOUT_SEEDS, "HELD-OUT seeds 21-25 (the verdict)")
    print("\n=== VERDICT (held-out seeds; pre-registered: claims 1-4 pass at >= 4/5) ===")
    for key, lab in (("transmission", "1 TRANSMISSION"), ("legend", "2 LEGEND"),
                     ("traceable", "3 TRACEABLE"), ("convergence", "4 CONVERGENCE")):
        k = sum(1 for r in rows if r[key])
        print(f"  {lab:15s}: {k}/{len(rows)} -> {'PASS' if k >= 4 else 'FAIL'}")
    print(f"  5 PATH-DEP     : -> {'PASS' if path_dep else 'FAIL'}")
    print("\nHonest frame: a PASS means a community of these substrates can carry a true event "
          "into myth -- changed, convergent, traceable. It says nothing about anyone home (§7), "
          "and the VOICE retelling legends in character needs a real model (not claimed here).")


if __name__ == "__main__":
    main()
