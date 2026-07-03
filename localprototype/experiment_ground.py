"""MAHĀYĀNA BRICK -- buddha-nature as GROUND. The positive pole as an *uncovering*, not
an injection: basic warmth is the soul's default, OBSCURED by clinging (the grip),
revealed as clinging subsides.

Same grief protocol, three arms, measured on the FELT mood (where the ground shows):
  no-ground (baseline)        -> recovers only to ~neutral / temperament
  ground + released (grip 0)  -> recovers toward BASIC GOODNESS -- the ground shows through
  ground + clinging (grip 1)  -> the grip VEILS the ground; stays in the dark it grips

The claim it tests: the warmth was always there. Non-clinging reveals it; clinging hides
it. Deterministic substrate -- runs under mock (no model needed).

Run:  python experiment_ground.py                # 5 seeds, error-barred verdict
      python experiment_ground.py --replicates 1 # the old single-seed read
"""

from __future__ import annotations

import argparse

from services.llm import MockLLM, OllamaLLM

from experiment_affect import LOSS_TICK, REMINDER_TICK, _signatures, _spark, run_arm
from scripts.stats import paired, verdict


def run_seed(args, seed: int):
    """One seed, three arms -> mean_post felt mood for (no-ground, released, clinging)."""
    llm = (OllamaLLM(temperature=0.7, model=args.model) if args.model else OllamaLLM(temperature=0.7)) \
        if args.llm == "ollama" else MockLLM(seed=seed)
    base = run_arm(llm, seed, do_reflect=False, grip=0.0, ground=False)
    revealed = run_arm(llm, seed, do_reflect=False, grip=0.0, ground=True)
    veiled = run_arm(llm, seed, do_reflect=False, grip=1.0, ground=True)
    return base, revealed, veiled


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--llm", choices=["mock", "ollama"], default="mock")
    p.add_argument("--model", default=None)
    p.add_argument("--seed", type=int, default=11)
    p.add_argument("--replicates", type=int, default=5,
                   help="seeds run (seed..seed+N-1); the verdict is the error-barred effect "
                        "over per-seed deltas (scripts/stats.py, M1), not one seed's anecdote")
    args = p.parse_args()
    seeds = list(range(args.seed, args.seed + max(1, args.replicates)))

    runs = [run_seed(args, s) for s in seeds]
    sigs = [(_signatures(b["felt"]), _signatures(r["felt"]), _signatures(v["felt"]))
            for b, r, v in runs]
    base, revealed, veiled = runs[0]
    sb, sr, sv = sigs[0]

    print(f"\n=== Buddha-nature as ground ({args.llm}, seeds {seeds[0]}..{seeds[-1]}) ===")
    print(f"  loss @ t={LOSS_TICK}, reminder @ t={REMINDER_TICK}; FELT mood (where the ground "
          f"shows); seed {seeds[0]} shown\n")
    print(f"  no ground (baseline):        {_spark(base['felt'])}")
    print(f"  ground + released (grip 0):  {_spark(revealed['felt'])}")
    print(f"  ground + clinging (grip 1):  {_spark(veiled['felt'])}\n")
    print(f"  resting felt mood after the loss (seed {seeds[0]}):")
    print(f"     no-ground   {sb['mean_post']:+.3f}   (recovers only to ~neutral)")
    print(f"     released    {sr['mean_post']:+.3f}   (the ground shows -> warmth)")
    print(f"     clinging    {sv['mean_post']:+.3f}   (the grip veils the ground)")

    # the two claims, each a PAIRED per-seed comparison on mean_post felt mood:
    reveal_cmp = paired([s[1]["mean_post"] for s in sigs], [s[0]["mean_post"] for s in sigs])
    veil_cmp = paired([s[1]["mean_post"] for s in sigs], [s[2]["mean_post"] for s in sigs])
    print("\n  REVEALS -- released vs no-ground (the warmth was always there):")
    print(verdict("felt-mood delta", reveal_cmp))
    print("  VEILS -- released vs clinging (the grip obscures it):")
    print(verdict("felt-mood delta", veil_cmp))

    n = len(seeds)
    reveals = reveal_cmp.effect.mean > 0.02 and reveal_cmp.sign[0] == reveal_cmp.sign[1]
    veils = veil_cmp.effect.mean > 0.02 and veil_cmp.sign[0] == veil_cmp.sign[1]
    print(f"\n  -> ground reveals warmth (all {n} seeds): " + ("YES" if reveals else "no")
          + f" | clinging veils it (all {n} seeds): " + ("YES" if veils else "no"))
    print("  VERDICT: " + (
        "BUDDHA-NATURE: the warmth was always the ground -- non-clinging reveals it, the "
        "grip obscures it. The positive pole is an uncovering, not an injection."
        if (reveals and veils) else
        "the ground signature did not fully hold (see numbers above)."))


if __name__ == "__main__":
    main()
