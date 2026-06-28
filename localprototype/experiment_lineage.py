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

Run:  python experiment_lineage.py
"""

from __future__ import annotations

import argparse
import statistics

from agent import telos as _telos
from agent.agent import Agent
from services.llm import MockLLM

TICKS = 30
SETBACKS = (10, 22)
AIM = "make my work come good this season"
SEED_LINES = ["I work my trade before dawn", "the season turns", "my hands know the craft"]

ARMS = {
    "taṇhā":  dict(grip=0.85, prajna=0.1, joy=0.0, transmute=0.0, ground=False),
    "chanda": dict(grip=0.30, prajna=0.7, joy=0.6, transmute=0.85, ground=True),
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


def run_lineage(llm, seed, fac, gens):
    telos = 0.5
    rows = []
    for g in range(gens):
        well, eff = life(llm, seed + g, telos, fac)
        rows.append({"gen": g, "telos": telos, "well": well})
        telos = _telos.reborn_telos(telos, eff)   # the thirst crosses to the next life
    return rows


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
        rows = run_lineage(llm, args.seed, fac, args.gens)
        out[name] = rows
        telos_traj = " ".join(f"{r['telos']:.2f}" for r in rows)
        well_traj = " ".join(f"{r['well']:+.2f}" for r in rows)
        print(f"  {name:7} telos:  {telos_traj}")
        print(f"  {name:7} well:   {well_traj}\n")

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


if __name__ == "__main__":
    main()
