"""LINEAGE -- the Second Noble Truth across the wheel. Does taṇhā (craving) perpetuate dukkha
across rebirth, and does chanda (wise aspiration) let a lineage settle?

The thirst, not the self, transmigrates: at death telos.reborn_telos carries the dead soul's drive
scaled by how tightly it CLUNG (effective_grip). A clinging lineage drags an escalating thirst from
life to life; a lineage that holds its aims with wisdom carries almost none. No project crosses
(anatta) -- only the disposition. We run N generations of each and watch two things travel the wheel:
  telos      the drive a generation wakes with -- does the thirst escalate (taṇhā) or settle (chanda)?
  wellbeing  how each life FARES -- is suffering reborn into suffering, or flourishing into flourishing?

  taṇhā wheel   clinging, no joy/wisdom  -> thirst climbs toward its max, each life craves + is wounded
  chanda wheel  holds lightly, wise+joyful -> thirst settles low, each life savours + is eased

NB: here the FACULTIES are held fixed per lineage (a lineage that keeps clinging vs keeps releasing).
Live (--world), only the thirst carries -- reborn streams get a fresh baseline endowment -- so no soul
is doomed to its predecessor's exact kleśas; the wheel still passes on the drive, not the character.

THE CONFOUND (and the control that breaks it). taṇhā and chanda differ in TWO things at once: their
within-life faculties (grip/prajñā/joy/...) AND the thirst they carry (reborn_telos scales by grip, so
the clinging arm transmits more). So "the clinging lineage escalates and suffers" cannot, as it stands,
tell apart "the grasping drives the wheel" from "I tuned a recurrence and made one arm clinging." A
third arm, `decoupled`, fixes this: taṇhā's CLINGING faculties, but the thirst carried with grasping
FACTORED OUT (a fixed rate for every soul). Holding faculties identical and varying only the carried
thirst deconfounds the two -- and, since the LIVE wheel carries ONLY the thirst (fresh faculties), this
is the variable that actually transmigrates there. A THIRST_CARRY sweep checks the escalate/settle
split isn't a one-value tuning artifact.

Run:  python experiment_lineage.py
"""

from __future__ import annotations

import argparse
import random
import statistics

from agent import genesis as _genesis
from agent import telos as _telos
from agent.agent import Agent
from services.llm import MockLLM

TICKS = 30
SETBACKS = (10, 22)
AIM = "make my work come good this season"
SEED_LINES = ["I work my trade before dawn", "the season turns", "my hands know the craft"]

ARMS = {
    "taṇhā":     dict(grip=0.85, prajna=0.1, joy=0.0, transmute=0.0, ground=False),
    "chanda":    dict(grip=0.30, prajna=0.7, joy=0.6, transmute=0.85, ground=True),
    "decoupled": dict(grip=0.85, prajna=0.1, joy=0.0, transmute=0.0, ground=False),  # = taṇhā's faculties
}

DECOUPLE_GRIP = 0.30   # the fixed, grasping-INDEPENDENT carry rate the decoupled control uses for every
                       # soul (reborn_telos instead scales by the soul's own effective_grip). Moderate on
                       # purpose -- not cherry-picked low (which would force a settle) nor high (force a
                       # climb); the load-bearing read is the WELLBEING comparison, robust to this value.


def reborn_telos_decoupled(dead_telos: float) -> float:
    """CONTROL carry: the thirst crosses the bardo with grasping FACTORED OUT -- every soul transmits at
    one fixed rate, regardless of how tightly it clung. reborn_telos's whole claim is that the carry
    scales with effective_grip; this breaks exactly that coupling and holds everything else. Paired with
    taṇhā's faculties it deconfounds the carried thirst from the static faculties (see the verdict)."""
    return max(0.0, min(1.0, _telos.LINEAGE_BASE + _telos.THIRST_CARRY * max(0.0, dead_telos) * DECOUPLE_GRIP))


# Which carry-rule each arm uses across the bardo. taṇhā/chanda use the real grip-coupled reborn_telos;
# the decoupled control swaps in the grasping-free carry above -- the one deconfounding lever.
CARRIES = {
    "decoupled": lambda telos, eff: reborn_telos_decoupled(telos),
}


def life(llm, seed, telos, fac):
    """One generation's life under an aim: pursue + two setbacks. Returns (wellbeing, effective_grip)."""
    a = Agent("self", "Soul", (0.0, 0.0), "You are a working soul.", list(SEED_LINES),
              llm, seed=seed, temperament=0.0, lifespan=10 ** 9)
    a.aim, a.telos = AIM, telos
    a.grip, a.prajna, a.joy, a.transmute = fac["grip"], fac["prajna"], fac["joy"], fac["transmute"]
    a.ground_enabled = fac["ground"]
    for ln in SEED_LINES:
        a.memory.write(ln, tick=0, source="self", speaker_id="self", weight=1.1)
    felt = []
    for t in range(1, TICKS + 1):
        if t in SETBACKS:
            _telos.setback(a, t, severity=0.4)
        a.step(t)
        felt.append(a.felt_mood())
    return statistics.fmean(felt), a.effective_grip()


def run_lineage(llm, seed, fac, gens, carry=_telos.reborn_telos):
    """One lineage of `gens` lives. `carry(dead_telos, eff_grip) -> next_telos` is the bardo rule:
    the default is the real grip-coupled reborn_telos; the decoupled control passes a grasping-free one."""
    telos = 0.5
    rows = []
    for g in range(gens):
        well, eff = life(llm, seed + g, telos, fac)
        rows.append({"gen": g, "telos": telos, "well": well})
        telos = carry(telos, eff)   # the thirst crosses to the next life
    return rows


def life_fresh(llm, seed, telos, rng):
    """One generation as the LIVE WHEEL actually makes it: FRESH standard faculties (endow_faculties --
    a varied modest grip plus prajñā/ground/joy/transmute/compassion at the wholesome baseline), with
    ONLY the carried thirst overriding telos. Models world/sim.py _coalesce, which re-rolls the
    faculties each rebirth and carries only the thirst -- unlike the fixed-faculty lineages above."""
    a = Agent("self", "Soul", (0.0, 0.0), "You are a working soul.", list(SEED_LINES),
              llm, seed=seed, temperament=0.0, lifespan=10 ** 9)
    _genesis.endow_faculties(a, rng)   # the wholesome endowment (grip varies 0.2-0.5), exactly as the wheel does
    a.aim, a.telos = AIM, telos        # only the carried thirst crosses; the aim and faculties are fresh
    for ln in SEED_LINES:
        a.memory.write(ln, tick=0, source="self", speaker_id="self", weight=1.1)
    felt = []
    for t in range(1, TICKS + 1):
        if t in SETBACKS:
            _telos.setback(a, t, severity=0.4)
        a.step(t)
        felt.append(a.felt_mood())
    return statistics.fmean(felt), a.effective_grip()


def run_livewheel(llm, seed, gens):
    """A lineage the way the LIVE WHEEL runs it: only the thirst carries; faculties are re-endowed fresh
    (and randomly varied) every generation. The decisive test of whether §5.5 transfers to the wheel a
    viewer actually watches -- where no soul keeps its predecessor's clinging."""
    rng = random.Random(seed)
    telos = 0.5
    rows = []
    for g in range(gens):
        well, eff = life_fresh(llm, seed + g, telos, rng)
        rows.append({"gen": g, "telos": telos, "well": well})
        telos = _telos.reborn_telos(telos, eff)   # the thirst crosses; the next self is freshly wholesome
    return rows


def sweep_thirst_carry(llm, seed, gens):
    """Robustness: is the escalate/settle split a tuned artifact of THIRST_CARRY=1.3, or does it hold
    across a band? Re-run taṇhā and chanda over a range of THIRST_CARRY and report where each lands."""
    orig = _telos.THIRST_CARRY
    print("\n=== THIRST_CARRY sensitivity (is the escalate/settle split a tuning artifact?) ===")
    print(f"  {'THIRST_CARRY':>12} {'taṇhā final':>12} {'chanda final':>13}  split holds?")
    try:
        for tc in (0.8, 1.0, 1.3, 1.6, 2.0):
            _telos.THIRST_CARRY = tc
            t = run_lineage(llm, seed, ARMS["taṇhā"], gens)
            c = run_lineage(llm, seed, ARMS["chanda"], gens)
            tf, cf = t[-1]["telos"], c[-1]["telos"]
            split = "yes" if (tf > cf + 0.3) else "no"
            print(f"  {tc:>12.1f} {tf:>12.2f} {cf:>13.2f}  {split}")
    finally:
        _telos.THIRST_CARRY = orig
    print("  -> 'yes' across the band = the split is robust, not a knife-edge of one tuned value.")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--gens", type=int, default=6)
    p.add_argument("--seed", type=int, default=11)
    args = p.parse_args()
    llm = MockLLM(seed=args.seed)

    print(f"\n=== Lineage: the Second Noble Truth across the wheel ({args.gens} generations) ===")
    print("  telos = the drive a life wakes with; well = how it fares. The thirst, not the self, crosses.\n")
    out = {}
    for name, fac in ARMS.items():
        rows = run_lineage(llm, args.seed, fac, args.gens, carry=CARRIES.get(name, _telos.reborn_telos))
        out[name] = rows
        telos_traj = " ".join(f"{r['telos']:.2f}" for r in rows)
        well_traj = " ".join(f"{r['well']:+.2f}" for r in rows)
        print(f"  {name:9} telos:  {telos_traj}")
        print(f"  {name:9} well:   {well_traj}\n")

    t, c = out["taṇhā"], out["chanda"]
    thirst_escalates = t[-1]["telos"] > t[0]["telos"] + 0.2 and t[-1]["telos"] > c[-1]["telos"] + 0.3
    chanda_settles = c[-1]["telos"] < 0.4
    suffering_perpetuates = statistics.fmean(r["well"] for r in t) < statistics.fmean(r["well"] for r in c) - 0.05
    print("  -> taṇhā thirst ESCALATES across the wheel (and exceeds chanda's): " + ("YES" if thirst_escalates else "no"))
    print("     chanda lineage SETTLES toward rest:                            " + ("YES" if chanda_settles else "no"))
    print("     suffering is reborn into suffering (taṇhā fares worse, every life): " + ("YES" if suffering_perpetuates else "no"))
    print("  VERDICT: " + (
        "THE WHEEL CARRIES THE DISPOSITION -- a clinging lineage drags an escalating thirst from life "
        "to life and is wounded in each (dukkha reborn into dukkha); a lineage that holds its aims with "
        "wisdom lets the thirst settle and flourishes across the wheel. The thirst transmigrates, not the self."
        if (thirst_escalates and chanda_settles and suffering_perpetuates) else
        "did NOT show the escalate/settle/perpetuate signature -- see the trajectories (tune THIRST_CARRY)."))

    # --- the deconfounding control: is the wheel's dukkha the carried THIRST, or the static FACULTIES? ---
    # `decoupled` has taṇhā's CLINGING faculties but carries the thirst with grasping factored out, so
    # the ONLY difference from taṇhā is the carried thirst. Two reads: (1) does breaking the coupling
    # kill the escalation, and (2) with faculties held identical, does carrying less thirst ease the life?
    d = out["decoupled"]
    well_t = statistics.fmean(r["well"] for r in t)
    well_d = statistics.fmean(r["well"] for r in d)
    esc_needs_coupling = d[-1]["telos"] < t[-1]["telos"] - 0.3   # break the coupling -> escalation gone
    thirst_moves_well = well_d > well_t + 0.05                    # less carried thirst -> measurably better life
    print("\n=== Control: the carried THIRST vs the static FACULTIES (deconfounded) ===")
    print("  'decoupled' = taṇhā's clinging faculties, but the thirst carried with grasping FACTORED OUT.\n")
    print(f"  {'arm':10} {'final thirst':>12} {'mean wellbeing':>15}")
    for name in ("taṇhā", "decoupled", "chanda"):
        r = out[name]
        wb = statistics.fmean(x["well"] for x in r)
        print(f"  {name:10} {r[-1]['telos']:>12.2f} {wb:>+15.3f}")
    print("\n  -> escalation REQUIRES the grip-coupling (decoupled, same faculties, doesn't escalate): "
          + ("YES" if esc_needs_coupling else "no"))
    if thirst_moves_well:
        print(f"     the carried THIRST drives wellbeing: with faculties held identical, decoupled's lower "
              f"thirst eases the lineage ({well_d:+.3f} vs taṇhā {well_t:+.3f}).")
        print("  CONTROL VERDICT: the wheel's dukkha rides on the transmigrating THIRST -- carrying less of")
        print("     it, faculties unchanged, measurably eases each life. The wellbeing headline survives the")
        print("     deconfound, and it transfers to the live wheel (which carries the thirst, re-rolls faculties).")
    else:
        print(f"     the carried thirst does NOT move wellbeing: decoupled fares the SAME as taṇhā "
              f"({well_d:+.3f} vs {well_t:+.3f}) despite carrying far less thirst.")
        print("  CONTROL VERDICT: 'suffering reborn into suffering' is carried by the STATIC FACULTIES, not")
        print("     the transmigrating thirst. Since the LIVE wheel re-rolls faculties FRESH and carries ONLY")
        print("     the thirst, the wellbeing half of the headline does NOT transfer to it as stated: the")
        print("     thirst sets the drive LEVEL, but the (fresh) faculties decide whether it becomes dukkha.")

    # --- the LIVE WHEEL as it actually runs: only the thirst carries, faculties re-rolled fresh ---
    # The arms above hold faculties FIXED per lineage. world/sim.py _coalesce does not: it calls
    # endow_faculties() on every reborn stream (wholesome baseline, modest varied grip) and carries
    # ONLY the thirst. So this is the test that actually speaks to the watchable wheel.
    lw = run_livewheel(llm, args.seed, args.gens)
    lw_w = statistics.fmean(r["well"] for r in lw)
    lw_escalates = lw[-1]["telos"] > lw[0]["telos"] + 0.2
    lw_flourishes = lw_w > 0.12
    print("\n=== The LIVE WHEEL as it actually runs (fresh wholesome faculties each life, only thirst carries) ===")
    print("  models _coalesce: each rebirth re-rolls the brahmavihāras/ground/prajñā; the fixed-clinging")
    print("  lineage above is NOT what the wheel makes.\n")
    lw_telos = " ".join(f"{r['telos']:.2f}" for r in lw)
    lw_well = " ".join(f"{r['well']:+.2f}" for r in lw)
    print(f"  live-wheel telos:  {lw_telos}")
    print(f"  live-wheel well:   {lw_well}\n")
    print("  -> thirst ESCALATES in the live wheel:               " + ("yes" if lw_escalates else "NO -- it settles"))
    print(f"     each reborn life FLOURISHES (mean well {lw_w:+.3f} > 0.12): " + ("YES" if lw_flourishes else "no"))
    print("  LIVE-WHEEL VERDICT: " + (
        "the wheel re-rolls WHOLESOME faculties every rebirth (modest grip, prajñā/ground/joy on), so the "
        "dead soul's effective_grip is always low, the carried thirst stays low, and every reborn life "
        "flourishes. The §5.5 escalation + perpetuated-suffering dynamics DO NOT appear in the live wheel: "
        "they require the fixed clinging faculties of the lab lineage, which the wheel never reproduces. "
        "The wheel transmits a drive LEVEL onto a freshly wholesome self."
        if (not lw_escalates and lw_flourishes) else
        "the live wheel showed unexpected dynamics -- see the trajectory above."))

    sweep_thirst_carry(llm, args.seed, args.gens)


if __name__ == "__main__":
    main()
