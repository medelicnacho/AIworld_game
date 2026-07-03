"""VAJRAYĀNA BRICK -- transmutation: the grip's energy met and TURNED to clarity.

The grip has two known exits already -- stay gripped (suffer) or RELEASE (prajñā lets it
fade). Transmutation is a THIRD path: you stay fully PRESENT to the charged memory (you do
not let it go) and yet it does not wound you -- the aversive energy is metabolized into
clear seeing. Engaged AND unwounded.

The discriminator is salience (engagement) vs lived mood (suffering), read off the grief
memory itself after the protocol:
  clinging  (grip, no transmute, no prajñā) -> salience HIGH, mood LOW   (engaged, suffering)
  release   (grip + prajñā)                 -> salience LOW,  mood OK    (disengaged, eased)
  transmute (grip + transmute)              -> salience HIGH, mood OK    (engaged, unwounded) <-

If transmute is both as ENGAGED as clinging and as UNWOUNDED as release, it's the third
path -- not suppression, not withdrawal. Deterministic substrate; runs under mock.

Run:  python experiment_transmutation.py                # 5 seeds, error-barred verdict
      python experiment_transmutation.py --replicates 1 # the old single-seed read
"""

from __future__ import annotations

import argparse

from services.llm import MockLLM, OllamaLLM

from experiment_affect import run_arm
from scripts.stats import paired, verdict


def grief_salience_and_mood(r: dict):
    a = r["agent"]
    gm = next((m for m in a.memory.items if "Wren" in m.text or "died" in m.text), None)
    sal = gm.salience if gm else 0.0
    return sal, r["mood"][-1]


def run_seed(args, seed: int):
    """One seed, three arms -> ((salience, mood) x clinging/release/transmute)."""
    llm = (OllamaLLM(temperature=0.7, model=args.model) if args.model else OllamaLLM(temperature=0.7)) \
        if args.llm == "ollama" else MockLLM(seed=seed)
    clinging = run_arm(llm, seed, do_reflect=False, grip=1.0)
    release = run_arm(llm, seed, do_reflect=False, grip=1.0, prajna=0.85)
    transmute = run_arm(llm, seed, do_reflect=False, grip=1.0, transmute=0.85)
    return (grief_salience_and_mood(clinging), grief_salience_and_mood(release),
            grief_salience_and_mood(transmute))


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
    (c_sal, c_mood), (r_sal, r_mood), (t_sal, t_mood) = runs[0]

    print(f"\n=== Transmutation: the third path ({args.llm}, seeds {seeds[0]}..{seeds[-1]}) ===")
    print(f"  the grief memory after the protocol (seed {seeds[0]} shown) -- "
          "salience (engagement) vs lived mood (suffering):\n")
    print(f"  clinging  (grip)            salience {c_sal:.2f}   mood {c_mood:+.3f}   (engaged, suffering)")
    print(f"  release   (grip + prajñā)   salience {r_sal:.2f}   mood {r_mood:+.3f}   (disengaged, eased)")
    print(f"  transmute (grip + transmute) salience {t_sal:.2f}   mood {t_mood:+.3f}   (?)")

    # the two claims, each a PAIRED per-seed comparison (arms share the seed list):
    engaged_cmp = paired([t[2][0] for t in runs], [t[1][0] for t in runs])   # transmute vs release salience
    unwound_cmp = paired([t[2][1] for t in runs], [t[0][1] for t in runs])   # transmute vs clinging mood
    print("\n  ENGAGED -- transmute salience vs release (stays present, unlike letting go):")
    print(verdict("salience delta", engaged_cmp))
    print("  UNWOUNDED -- transmute lived mood vs clinging (not suffering, unlike the grip):")
    print(verdict("mood delta", unwound_cmp))

    engaged = engaged_cmp.effect.mean > 0.05 and engaged_cmp.sign[0] == engaged_cmp.sign[1]
    unwounded = unwound_cmp.effect.mean > 0.02 and unwound_cmp.sign[0] == unwound_cmp.sign[1]
    n = len(seeds)
    print(f"\n  -> transmute stays ENGAGED (all {n} seeds, mean above threshold): "
          + ("YES" if engaged else "no")
          + f"\n     transmute is UNWOUNDED (all {n} seeds, mean above threshold): "
          + ("YES" if unwounded else "no"))
    print("  VERDICT: " + (
        "THE THIRD PATH: transmutation stays in full contact with the charge (engaged like "
        "clinging) yet is not wounded by it (eased like release) -- the energy turned to "
        "clarity, neither suppressed nor indulged."
        if (engaged and unwounded) else
        "did not show the engaged-AND-unwounded signature (see numbers above)."))


if __name__ == "__main__":
    main()
