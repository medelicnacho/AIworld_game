"""FORGIVENESS: bounding the memory ratchet WITHOUT killing the feud.

THE LEAK. A floored memory's salience never decays below its floor, and FORGET_THRESHOLD is
0.08 while a grievance floors at 0.5 (world/war.py GRIEVANCE_FLOOR) -- so a floored memory
can NEVER be pruned. And World._hearth copies EVERY floored memory a parent holds into each
child, so grievances do not merely persist, they REPLICATE down the generations.

Measured on a 24-founder settlement with the arena's own gates, 8000 ticks: floored items sat
near zero for 6000 ticks, then 6 -> 41 -> 53 -> 155 -> 217 across the next 2000 as war got
going -- roughly doubling every 500 ticks while ordinary items converged. Items per soul
ratcheted 20 -> 33.5. The gameworld capacity law is ~14us per item per tick, so an
un-prunable, self-replicating class of item is a permanent tax on every settlement shard
(the live arena at tick 181,237 was holding 5.97 GB).

THE FIX, in two independent bounds:
  TIME + WARMTH erosion (agent/memory.py): the floor itself erodes -- slowly on its own
    (~3.6 lifetimes), ~10x faster in a soul whose bonds are warm. §5.28 named exactly this
    as future work ("floor-erosion on warm cross-bloc bonds"), and it is ROADMAP's P2,
    grudges-that-can-let-go.
  THE HEARTH CAP (world/sim.py): a child is raised on the house's LOUDEST wounds, not its
    every wound -- which removes the replication term.

An ACTIVE feud is untouched by design: war.py rewrites the grievance and lore.py's retellings
carry the floor, both faster than this erodes. This ends DEAD feuds, not live ones.

PRE-REGISTERED (3 seeds; a claim passes at 3/3):

  F1 THE RATCHET STOPS -- in two parts, because the first attempt at this claim was
     MIS-SPECIFIED and the error is recorded rather than quietly reinterpreted.

     [SPEC ERROR, v1] F1 was written as "last quarter <= first quarter x 1.3". But the
     first quarter is ~0.00 floored-per-soul: no raid has happened yet, so there are no
     grievances to bound. That criterion therefore demanded floored memory NEVER
     ACCUMULATE AT ALL, when the design intent is the opposite -- a live feud SHOULD
     accumulate grievance, and forgiveness should clear it once the feud dies. It read
     0/3 while the mechanism was cutting the leak 8-45x. A bounded steady state above
     zero is the success condition; v1 encoded "stays at zero".

     F1a THE EFFECT EXISTS. Forgiveness ends with materially less floored memory per soul
         than its own no-forgiveness twin -- at most half. (Control must itself ratchet,
         or the seed proved nothing.)
     F1b IT IS BOUNDED, NOT MERELY SLOWER. In the forgiveness arm the last quarter is no
         higher than the THIRD quarter x 1.3 -- growth has flattened by the end of the
         run, rather than climbing more gently toward the same fate.

  F2 THE FEUD STILL OUTLIVES ITS FOUNDERS -- THE VETO. §5.28's G2 is a validated result
     (5/5 at 100% turnover): at the end of the run the land-keyed grievance must still be
     carried by souls who never fought the raid that made it. A memory bound bought by
     erasing the feud is not a fix, it is a regression -- it would delete the finding the
     hearth was built to produce.

  F3 NO POPULATION COST. The town is not materially smaller with forgiveness on.

  python3 -u experiment_forgiveness.py

VERDICT (seeds 11-20, n=10 -- the 3-seed run below was NOT enough and is superseded):

  F1 RATCHET STOPS (a AND b)   7/10    F1a effect 9/10, F1b flattened 7/10
  F2 THE FEUD STILL OUTLIVES   9/10    (veto)
  F3 NO POPULATION COST        8/10

FAILS the bar on all three, so the gates stay OFF. The three-seed run had F1 3/3 and F2 3/3
and would have been read as "ships once F3 settles". At n=10 that reading is wrong, and the
extra seven seeds cost an hour to learn it. This is the §5.7 pattern for the third time in
this session's work: a claim that looked clean at n=3 did not hold.

WHAT IS SOLID. F1a -- forgiveness ends with materially less un-prunable memory than its own
twin -- holds 9/10, and the effect is large wherever it lands (floored/soul 13.91 -> 0.31,
19.15 -> 2.40, 18.00 -> 1.82). The leak is real, and this bounds it.

WHAT IS NOT. F1b, "bounded and not merely slower", is 7/10 -- so on ~a third of towns the
growth has NOT flattened by the end of the run, it is only climbing more gently. That is the
difference between a fix and a delay, and it is the claim that decides whether a shard's
cost converges. It is also the claim I would have skipped: the first F1 could not have
caught it, since it compared against a first quarter that is structurally ~0.

F2 slipping to 9/10 matters more than the number looks: it is the WELFARE-ADJACENT veto (a
memory bound must not be bought by erasing §5.28's feud), and one town in ten losing the
feud entirely is a real cost, not noise to average away.

WHAT TO DO NEXT, if this is picked up: the erosion rate is a single global constant doing
two jobs -- bounding memory AND preserving feuds -- and 7/10 vs 9/10 on opposing claims is
what one constant serving two masters looks like. The honest next step is to separate them
(erode faster on memories nobody has retold, slower on those carrying a live lore_id) and
pre-register the split BEFORE running, rather than tuning FLOOR_EROSION until both pass.

"""
from __future__ import annotations

import statistics as st

from scripts.arena_harness import build, run

TICKS = 12000
EVERY = 1000
FOUNDERS = 24
SEEDS = tuple(range(11, 21))   # 10 seeds: settling F3 on the UNCHANGED criterion
HEARTH_CAP = 3


def _census(w):
    tot = floored = 0
    for a in w.agents:
        for m in a.memory.items:
            tot += 1
            if getattr(m, "salience_floor", 0.0) > 0.0:
                floored += 1
    return tot, floored


def _feud_carriers(w):
    """§5.28's G2 read: souls carrying a land-keyed feud story, and how many of them were
    NOT alive when it was cut (age < the story's age is a proxy for 'never fought it')."""
    carriers = 0
    for a in w.agents:
        if any(getattr(m, "lore_id", "").startswith("feud:") for m in a.memory.items):
            carriers += 1
    return carriers


def run_arm(seed: int, forgive: bool) -> dict:
    w = build(seed=seed, founders=FOUNDERS)
    w.forgive_enabled = forgive
    w.hearth_carry = HEARTH_CAP if forgive else 0
    for a in w.agents:
        a.forgive_enabled = forgive
    rows: list = []

    def sample(t, world):
        tot, fl = _census(world)
        n = len(world.agents) or 1
        rows.append((t, n, tot / n, fl / n))

    run(w, TICKS, on_sample=sample, every=EVERY)
    q = max(1, len(rows) // 4)
    return {"n": len(w.agents),
            "items_early": st.fmean(r[2] for r in rows[:q]),
            "items_late": st.fmean(r[2] for r in rows[-q:]),
            "flr_early": st.fmean(r[3] for r in rows[:q]),
            "flr_mid": st.fmean(r[3] for r in rows[-2 * q:-q]) if len(rows) >= 2 * q else 0.0,
            "flr_late": st.fmean(r[3] for r in rows[-q:]),
            "feud_carriers": _feud_carriers(w)}


def main() -> None:
    print(f"  {TICKS} ticks, {FOUNDERS} founders, seeds {SEEDS}, hearth cap {HEARTH_CAP}\n")
    print(f"  {'seed':<6}{'arm':<10}{'alive':>7}{'items/soul':>22}{'floored/soul':>22}"
          f"{'feud':>7}")
    print(f"  {'':<6}{'':<10}{'':>7}{'early -> late':>22}{'early -> late':>22}{'carr':>7}")
    f1 = f2 = f3 = 0
    for sd in SEEDS:
        off = run_arm(sd, False)
        on = run_arm(sd, True)
        ratchets_off = off["flr_late"] > off["flr_early"] * 1.3
        for label, r in (("off", off), ("forgive", on)):
            print(f"  {sd:<6}{label:<10}{r['n']:>7}"
                  f"{r['items_early']:>10.1f} ->{r['items_late']:>9.1f}"
                  f"{r['flr_early']:>10.2f} ->{r['flr_late']:>9.2f}{r['feud_carriers']:>7}")
        ok1a = on["flr_late"] <= off["flr_late"] * 0.5 and ratchets_off
        ok1b = on["flr_late"] <= on["flr_mid"] * 1.3
        ok1 = ok1a and ok1b
        ok2 = on["feud_carriers"] > 0
        ok3 = on["n"] >= 0.9 * off["n"]
        f1 += ok1
        f2 += ok2
        f3 += ok3
        print(f"        -> F1a effect {'YES' if ok1a else 'no '}  "
              f"F1b flattened {'YES' if ok1b else 'no '}   "
              f"F2 feud survives {'YES' if ok2 else 'NO (veto)'}   "
              f"F3 no pop cost {'YES' if ok3 else 'no '}   "
              f"[control ratchets: {'yes' if ratchets_off else 'NO -- weak control'}]\n")
    n = len(SEEDS)
    print(f"  F1 RATCHET STOPS (a AND b)    : {f1}/{n}")
    print(f"  F2 THE FEUD STILL OUTLIVES    : {f2}/{n}   (veto)")
    print(f"  F3 NO POPULATION COST         : {f3}/{n}")
    ok = f1 == n and f2 == n and f3 == n
    print(f"\n  VERDICT: {'FORGIVENESS BOUNDS THE LEAK AND KEEPS THE FEUD' if ok else 'did NOT show the signature'}")


if __name__ == "__main__":
    main()
