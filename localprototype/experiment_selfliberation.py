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


def run_seed(args, seed: int):
    llm = (OllamaLLM(temperature=0.7, model=args.model) if args.model else OllamaLLM(temperature=0.7)) \
        if args.llm == "ollama" else MockLLM(seed=seed)
    normal = run_arm(llm, seed, do_reflect=False)
    selflib = run_arm(llm, seed, do_reflect=False, self_liberation=0.85)
    return normal["mood"], selflib["mood"]


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
    from scripts.stats import paired, summary, verdict

    runs = [run_seed(args, s) for s in seeds]
    nm, sm = runs[0]
    after = LOSS_TICK + 4

    base = nm[LOSS_TICK - 2]
    print(f"\n=== Self-liberation: a charge frees itself as it arises ({args.llm}, "
          f"seeds {seeds[0]}..{seeds[-1]}) ===")
    print(f"  loss @ t={LOSS_TICK}; lived mood; seed {seeds[0]} shown\n")
    print(f"  normal:           {_spark(nm)}")
    print(f"  self-liberation:  {_spark(sm)}\n")
    n_contact = base - nm[LOSS_TICK]          # the dip at the instant of arising
    s_contact = base - sm[LOSS_TICK]
    n_after, s_after = nm[after], sm[after]
    print(f"  CONTACT -- dip at the instant the loss arrives (t={LOSS_TICK}, seed {seeds[0]}):")
    print(f"     normal {n_contact:+.3f}   self-liberation {s_contact:+.3f}   (both should dip -> it is FELT)")
    print(f"  SETTLING -- lived mood {4} ticks later (t={after}, seed {seeds[0]}):")
    print(f"     normal {n_after:+.3f}   self-liberation {s_after:+.3f}   (self-lib should be back near baseline)")

    # FELT is a one-arm claim (the self-lib dip exists at all); FREED is the paired claim.
    contacts = summary([(n[LOSS_TICK - 2] - s[LOSS_TICK]) for n, s in runs])
    freed_cmp = paired([s[after] for _, s in runs], [n[after] for n, _ in runs])
    print(f"\n  CONTACT across seeds (self-lib dip at arising -- must EXIST, or it's numbness):")
    print(f"     {contacts}")
    print("  FREED -- self-lib vs normal lived mood at t+4 (settled sooner, per-seed):")
    print(verdict("settling delta", freed_cmp))

    n = len(seeds)
    felt = contacts.mean > 0.05 and all((nn[LOSS_TICK - 2] - ss[LOSS_TICK]) > 0 for nn, ss in runs)
    freed = freed_cmp.effect.mean > 0.05 and freed_cmp.sign[0] == freed_cmp.sign[1]
    print(f"\n  -> felt at arising (contact, all {n} seeds): " + ("YES" if felt else "no")
          + f" | then self-freed (settled sooner, all {n} seeds): " + ("YES" if freed else "no"))
    print("  VERDICT: " + (
        "RANG DROL: the charge is felt fully as it arises and then frees itself -- a line "
        "drawn on water. Not suppression (it was felt), not mere clinging (it did not stay)."
        if (felt and freed) else
        "did not show the felt-then-freed signature (see numbers above)."))


if __name__ == "__main__":
    main()
