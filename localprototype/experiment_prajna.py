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
Run:  python experiment_prajna.py                # 5 seeds, error-barred verdict
      python experiment_prajna.py --replicates 1 # the old single-seed read
"""

from __future__ import annotations

import argparse

from services.llm import MockLLM, OllamaLLM

from experiment_affect import LOSS_TICK, _signatures, _spark, run_arm
from scripts.stats import paired, verdict


def run_seed(args, seed: int):
    llm = (OllamaLLM(temperature=0.7, model=args.model) if args.model else OllamaLLM(temperature=0.7)) \
        if args.llm == "ollama" else MockLLM(seed=seed)
    clinging = run_arm(llm, seed, do_reflect=False, grip=1.0, ground=True, prajna=0.0)
    wisdom = run_arm(llm, seed, do_reflect=False, grip=1.0, ground=True, prajna=0.8)
    return clinging, wisdom


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
    clinging, wisdom = runs[0]
    # Wing 1 (clinging) reads on the LIVED wound = memory.mood; Wing 2 (warmth) on FELT mood.
    c_cling, w_cling = _signatures(clinging["mood"]), _signatures(wisdom["mood"])
    c_warm, w_warm = _signatures(clinging["felt"]), _signatures(wisdom["felt"])

    print(f"\n=== Prajñā: seeing the constructs as empty ({args.llm}, seeds {seeds[0]}..{seeds[-1]}) ===")
    print(f"  grief @ t={LOSS_TICK}, grip clamped, ground on; toggling only prajñā; "
          f"seed {seeds[0]} shown\n")
    print(f"  lived wound (memory.mood)  clinging:  {_spark(clinging['mood'])}")
    print(f"  lived wound (memory.mood)  wisdom:    {_spark(wisdom['mood'])}")
    print(f"  warmth (felt mood)         clinging:  {_spark(clinging['felt'])}")
    print(f"  warmth (felt mood)         wisdom:    {_spark(wisdom['felt'])}\n")
    print(f"  WING 1 -- clinging (lived wound, higher = held less), seed {seeds[0]}:")
    print(f"     clinging {c_cling['final']:+.3f}   wisdom {w_cling['final']:+.3f}")
    print(f"  WING 2 -- warmth (felt mood, higher = ground shows, NOT nihilist cold), seed {seeds[0]}:")
    print(f"     clinging {c_warm['final']:+.3f}   wisdom {w_warm['final']:+.3f}")

    wing1_cmp = paired([_signatures(w["mood"])["final"] for _, w in runs],
                       [_signatures(c["mood"])["final"] for c, _ in runs])
    wing2_cmp = paired([_signatures(w["felt"])["final"] for _, w in runs],
                       [_signatures(c["felt"])["final"] for c, _ in runs])
    print("\n  WING 1 -- wisdom vs clinging on the lived wound (loosened, per-seed):")
    print(verdict("wound delta", wing1_cmp))
    print("  WING 2 -- wisdom vs clinging on felt warmth (rose, NOT nihilist, per-seed):")
    print(verdict("warmth delta", wing2_cmp))

    n = len(seeds)
    wing1 = wing1_cmp.effect.mean > 0.02 and wing1_cmp.sign[0] == wing1_cmp.sign[1]
    wing2 = wing2_cmp.effect.mean > 0.02 and wing2_cmp.sign[0] == wing2_cmp.sign[1]
    print(f"\n  -> Wing 1 clinging loosens (all {n} seeds): " + ("YES" if wing1 else "no")
          + f" | Wing 2 warmth holds/grows (all {n} seeds): " + ("YES" if wing2 else "no"))
    print("  VERDICT: " + (
        "PRAJÑĀ (the two wings): seeing the construct as empty loosens the grip AND lets "
        "warmth show -- wisdom and compassion from one seeing, not cold nihilism."
        if (wing1 and wing2) else
        "did not show both wings -- if warmth fell, that's the nihilist near-enemy, not wisdom."))


if __name__ == "__main__":
    main()
