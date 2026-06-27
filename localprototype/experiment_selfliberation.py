"""VAJRAYĀNA BRICK -- self-liberation (rang drol): a charge frees itself AS IT ARISES.

Distinct from the other paths: clinging holds+amplifies, release lets fade, transmutation
works a held charge over time. Self-liberation acts at the INSTANT of arising -- the
feeling is felt fully as it comes (full contact, not suppression) and then dissolves over
the next few ticks, like a line drawn on water, before it can accrue.

Same grief protocol, measured on lived mood:
  normal           -> the loss lands and STAYS low through the quiet days (it accrued)
  self-liberation  -> the loss is FELT at the instant it arrives (a real dip = contact),
                      then settles back to baseline within a few ticks (it self-freed)

The signature is CONTACT (a real dip at the loss -- not numb) followed by FAST settling
(recovered far sooner than normal). Deterministic substrate; runs under mock.

Run:  python experiment_selfliberation.py
"""

from __future__ import annotations

import argparse

from services.llm import MockLLM, OllamaLLM

from experiment_affect import LOSS_TICK, _spark, run_arm


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--llm", choices=["mock", "ollama"], default="mock")
    p.add_argument("--model", default=None)
    p.add_argument("--seed", type=int, default=11)
    args = p.parse_args()
    llm = (OllamaLLM(temperature=0.7, model=args.model) if args.model else OllamaLLM(temperature=0.7)) \
        if args.llm == "ollama" else MockLLM(seed=args.seed)

    normal = run_arm(llm, args.seed, do_reflect=False)
    selflib = run_arm(llm, args.seed, do_reflect=False, self_liberation=0.85)
    nm, sm = normal["mood"], selflib["mood"]

    base = nm[LOSS_TICK - 2]
    print(f"\n=== Self-liberation: a charge frees itself as it arises ({args.llm}, seed {args.seed}) ===")
    print(f"  loss @ t={LOSS_TICK}; lived mood\n")
    print(f"  normal:           {_spark(nm)}")
    print(f"  self-liberation:  {_spark(sm)}\n")
    n_contact = base - nm[LOSS_TICK]          # the dip at the instant of arising
    s_contact = base - sm[LOSS_TICK]
    # recovery a few ticks after arising
    after = LOSS_TICK + 4
    n_after, s_after = nm[after], sm[after]
    print(f"  CONTACT -- dip at the instant the loss arrives (t={LOSS_TICK}):")
    print(f"     normal {n_contact:+.3f}   self-liberation {s_contact:+.3f}   (both should dip -> it is FELT)")
    print(f"  SETTLING -- lived mood {4} ticks later (t={after}):")
    print(f"     normal {n_after:+.3f}   self-liberation {s_after:+.3f}   (self-lib should be back near baseline)")

    felt = s_contact > 0.05                    # a real dip happened -> contact, not numbness
    freed = s_after > n_after + 0.05           # but settled far sooner than normal
    print("\n  -> felt at arising (contact, not suppression): " + ("YES" if felt else "no")
          + " | then self-freed (settled sooner than normal): " + ("YES" if freed else "no"))
    print("  VERDICT: " + (
        "RANG DROL: the charge is felt fully as it arises and then frees itself -- a line "
        "drawn on water. Not suppression (it was felt), not mere clinging (it did not stay)."
        if (felt and freed) else
        "did not show the felt-then-freed signature (see numbers above)."))


if __name__ == "__main__":
    main()
