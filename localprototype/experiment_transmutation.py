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

Run:  python experiment_transmutation.py
"""

from __future__ import annotations

import argparse

from services.llm import MockLLM, OllamaLLM

from experiment_affect import run_arm


def grief_salience_and_mood(r: dict):
    a = r["agent"]
    gm = next((m for m in a.memory.items if "Wren" in m.text or "died" in m.text), None)
    sal = gm.salience if gm else 0.0
    return sal, r["mood"][-1]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--llm", choices=["mock", "ollama"], default="mock")
    p.add_argument("--model", default=None)
    p.add_argument("--seed", type=int, default=11)
    args = p.parse_args()
    llm = (OllamaLLM(temperature=0.7, model=args.model) if args.model else OllamaLLM(temperature=0.7)) \
        if args.llm == "ollama" else MockLLM(seed=args.seed)

    clinging = run_arm(llm, args.seed, do_reflect=False, grip=1.0)
    release = run_arm(llm, args.seed, do_reflect=False, grip=1.0, prajna=0.85)
    transmute = run_arm(llm, args.seed, do_reflect=False, grip=1.0, transmute=0.85)
    c_sal, c_mood = grief_salience_and_mood(clinging)
    r_sal, r_mood = grief_salience_and_mood(release)
    t_sal, t_mood = grief_salience_and_mood(transmute)

    print(f"\n=== Transmutation: the third path ({args.llm}, seed {args.seed}) ===")
    print("  the grief memory after the protocol -- salience (engagement) vs lived mood (suffering):\n")
    print(f"  clinging  (grip)            salience {c_sal:.2f}   mood {c_mood:+.3f}   (engaged, suffering)")
    print(f"  release   (grip + prajñā)   salience {r_sal:.2f}   mood {r_mood:+.3f}   (disengaged, eased)")
    print(f"  transmute (grip + transmute) salience {t_sal:.2f}   mood {t_mood:+.3f}   (?)")

    engaged = t_sal > r_sal + 0.05               # stays present, unlike release which lets go
    unwounded = t_mood > c_mood + 0.02           # not suffering, unlike clinging
    print("\n  -> transmute stays ENGAGED (salience high, unlike release): " + ("YES" if engaged else "no")
          + "\n     transmute is UNWOUNDED (mood eased, unlike clinging): " + ("YES" if unwounded else "no"))
    print("  VERDICT: " + (
        "THE THIRD PATH: transmutation stays in full contact with the charge (engaged like "
        "clinging) yet is not wounded by it (eased like release) -- the energy turned to "
        "clarity, neither suppressed nor indulged."
        if (engaged and unwounded) else
        "did not show the engaged-AND-unwounded signature (see numbers above)."))


if __name__ == "__main__":
    main()
