"""MAHĀYĀNA BRICK -- buddha-nature as GROUND. The positive pole as an *uncovering*, not
an injection: basic warmth is the soul's default, OBSCURED by clinging (the grip),
revealed as clinging subsides.

Same grief protocol, three arms, measured on the FELT mood (where the ground shows):
  no-ground (baseline)        -> recovers only to ~neutral / temperament
  ground + released (grip 0)  -> recovers toward BASIC GOODNESS -- the ground shows through
  ground + clinging (grip 1)  -> the grip VEILS the ground; stays in the dark it grips

The claim it tests: the warmth was always there. Non-clinging reveals it; clinging hides
it. Deterministic substrate -- runs under mock (no model needed).

Run:  python experiment_ground.py
"""

from __future__ import annotations

import argparse

from services.llm import MockLLM, OllamaLLM

from experiment_affect import LOSS_TICK, REMINDER_TICK, _signatures, _spark, run_arm


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--llm", choices=["mock", "ollama"], default="mock")
    p.add_argument("--model", default=None)
    p.add_argument("--seed", type=int, default=11)
    args = p.parse_args()
    llm = (OllamaLLM(temperature=0.7, model=args.model) if args.model else OllamaLLM(temperature=0.7)) \
        if args.llm == "ollama" else MockLLM(seed=args.seed)

    base = run_arm(llm, args.seed, do_reflect=False, grip=0.0, ground=False)
    revealed = run_arm(llm, args.seed, do_reflect=False, grip=0.0, ground=True)
    veiled = run_arm(llm, args.seed, do_reflect=False, grip=1.0, ground=True)
    sb, sr, sv = (_signatures(base["felt"]), _signatures(revealed["felt"]),
                  _signatures(veiled["felt"]))

    print(f"\n=== Buddha-nature as ground ({args.llm}, seed {args.seed}) ===")
    print(f"  loss @ t={LOSS_TICK}, reminder @ t={REMINDER_TICK}; FELT mood (where the ground shows)\n")
    print(f"  no ground (baseline):        {_spark(base['felt'])}")
    print(f"  ground + released (grip 0):  {_spark(revealed['felt'])}")
    print(f"  ground + clinging (grip 1):  {_spark(veiled['felt'])}\n")
    print(f"  resting felt mood after the loss:")
    print(f"     no-ground   {sb['mean_post']:+.3f}   (recovers only to ~neutral)")
    print(f"     released    {sr['mean_post']:+.3f}   (the ground shows -> warmth)")
    print(f"     clinging    {sv['mean_post']:+.3f}   (the grip veils the ground)")
    print(f"  final felt mood:  no-ground {sb['final']:+.3f}   released {sr['final']:+.3f}   clinging {sv['final']:+.3f}")

    reveals = sr["mean_post"] > sb["mean_post"] + 0.02
    veils = sr["mean_post"] > sv["mean_post"] + 0.02
    print("\n  -> ground reveals warmth (released > no-ground): " + ("YES" if reveals else "no")
          + " | clinging veils it (released > clinging): " + ("YES" if veils else "no"))
    print("  VERDICT: " + (
        "BUDDHA-NATURE: the warmth was always the ground -- non-clinging reveals it, the "
        "grip obscures it. The positive pole is an uncovering, not an injection."
        if (reveals and veils) else
        "the ground signature did not fully hold (see numbers above)."))


if __name__ == "__main__":
    main()
