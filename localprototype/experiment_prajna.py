"""MAHĀYĀNA BRICK -- prajñā (wisdom / śūnyatā): seeing the constructs as empty loosens
the grip at its SOURCE. The decisive test is the TWO WINGS: real wisdom drops clinging
WHILE warmth holds or grows. If clinging drops but warmth drops too, that's the nihilist
near-enemy ('nothing matters'), not prajñā.

Same grief protocol, grip clamped (clinging arises), ground on. Toggle only prajñā:
  clinging (prajna 0)  -> the grip holds the wound; ground veiled
  wisdom   (prajna .8) -> sees the construct as empty -> the grip has little to clutch:
                          the wound is held less (Wing 1) AND the ground shows -> warmth
                          rises (Wing 2). Both wings = wisdom; warmth-down would be nihilism.

Deterministic substrate -- runs under mock.
Run:  python experiment_prajna.py
"""

from __future__ import annotations

import argparse

from services.llm import MockLLM, OllamaLLM

from experiment_affect import LOSS_TICK, _signatures, _spark, run_arm


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--llm", choices=["mock", "ollama"], default="mock")
    p.add_argument("--model", default=None)
    p.add_argument("--seed", type=int, default=11)
    args = p.parse_args()
    llm = (OllamaLLM(temperature=0.7, model=args.model) if args.model else OllamaLLM(temperature=0.7)) \
        if args.llm == "ollama" else MockLLM(seed=args.seed)

    clinging = run_arm(llm, args.seed, do_reflect=False, grip=1.0, ground=True, prajna=0.0)
    wisdom = run_arm(llm, args.seed, do_reflect=False, grip=1.0, ground=True, prajna=0.8)
    # Wing 1 (clinging) reads on the LIVED wound = memory.mood; Wing 2 (warmth) on FELT mood.
    c_cling, w_cling = _signatures(clinging["mood"]), _signatures(wisdom["mood"])
    c_warm, w_warm = _signatures(clinging["felt"]), _signatures(wisdom["felt"])

    print(f"\n=== Prajñā: seeing the constructs as empty ({args.llm}, seed {args.seed}) ===")
    print(f"  grief @ t={LOSS_TICK}, grip clamped, ground on; toggling only prajñā\n")
    print(f"  lived wound (memory.mood)  clinging:  {_spark(clinging['mood'])}")
    print(f"  lived wound (memory.mood)  wisdom:    {_spark(wisdom['mood'])}")
    print(f"  warmth (felt mood)         clinging:  {_spark(clinging['felt'])}")
    print(f"  warmth (felt mood)         wisdom:    {_spark(wisdom['felt'])}\n")
    print(f"  WING 1 -- clinging (lived wound, higher = held less):")
    print(f"     clinging {c_cling['final']:+.3f}   wisdom {w_cling['final']:+.3f}")
    print(f"  WING 2 -- warmth (felt mood, higher = ground shows, NOT nihilist cold):")
    print(f"     clinging {c_warm['final']:+.3f}   wisdom {w_warm['final']:+.3f}")

    wing1 = w_cling["final"] > c_cling["final"] + 0.02     # clinging loosened
    wing2 = w_warm["final"] > c_warm["final"] + 0.02       # warmth rose (not nihilism)
    print("\n  -> Wing 1 clinging loosens: " + ("YES" if wing1 else "no")
          + " | Wing 2 warmth holds/grows: " + ("YES" if wing2 else "no"))
    print("  VERDICT: " + (
        "PRAJÑĀ (the two wings): seeing the construct as empty loosens the grip AND lets "
        "warmth show -- wisdom and compassion from one seeing, not cold nihilism."
        if (wing1 and wing2) else
        "did not show both wings -- if warmth fell, that's the nihilist near-enemy, not wisdom."))


if __name__ == "__main__":
    main()
