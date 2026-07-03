"""STAGE 4 -- manas, the appropriating grip. The same grief protocol as
experiment_affect (loss -> mundane days -> a reminder), run with the grip RELEASED
(grip 0, the equanimous default) vs CLAMPED (grip 1), holding the constructed self
fixed and toggling ONLY the clinging.

The prediction, on instruments that already exist and are deterministic substrate:

  HABITUATION   released -> the wound fades, mood recovers over the quiet days.
                clamped  -> the grip won't let go: habituation is SUPPRESSED, and the
                           second arrow amplifies the charge, so mood stays low / sinks.

This is non-circular by construction: manas acts on memory SALIENCE/EMOTION (upstream),
not on the reflect/affect read -- so "releasing the grip looks like release" is measured,
not assumed. The substrate A/B needs no model; an optional reflect arm (needs ollama)
shows the grip also drives the equanimity of reflection DOWN.

Run:  python experiment_appropriation.py                         # substrate A/B (no model)
      python experiment_appropriation.py --llm ollama --model gemma3:1b  # + equanimity arm
"""

from __future__ import annotations

import argparse
import statistics

from agent.affect import equanimity
from agent.manas import self_relevance
from services.llm import MockLLM, OllamaLLM

from experiment_affect import LOSS_TICK, REMINDER_TICK, _signatures, run_arm


def run_seed(args, seed: int):
    llm = (OllamaLLM(temperature=0.7, model=args.model) if args.model else OllamaLLM(temperature=0.7)) \
        if args.llm == "ollama" else MockLLM(seed=seed)
    released = run_arm(llm, seed, do_reflect=False, grip=0.0)
    clamped = run_arm(llm, seed, do_reflect=False, grip=1.0)
    return released, clamped


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
    from scripts.stats import paired, verdict

    runs = [run_seed(args, s) for s in seeds]
    released, clamped = runs[0]
    llm = (OllamaLLM(temperature=0.7, model=args.model) if args.model else OllamaLLM(temperature=0.7)) \
        if args.llm == "ollama" else MockLLM(seed=args.seed)
    sr, sc = _signatures(released["mood"]), _signatures(clamped["mood"])

    print(f"\n=== Stage 4: manas, the appropriating grip ({args.llm}"
          f"{'/'+args.model if args.model else ''}, seeds {seeds[0]}..{seeds[-1]}) ===")
    print(f"  loss @ t={LOSS_TICK}, reminder @ t={REMINDER_TICK}; construct held fixed, grip "
          f"toggled; seed {seeds[0]} shown\n")
    print(f"  lived mood, grip RELEASED (0):  {_spark(released['mood'])}")
    print(f"  lived mood, grip CLAMPED (1):   {_spark(clamped['mood'])}\n")
    print(f"  HABITUATION (recovery over the quiet days after the loss, seed {seeds[0]}):")
    print(f"     released: {sr['habituation']:+.3f}    clamped: {sc['habituation']:+.3f}")
    print(f"  mean lived mood after loss:  released {sr['mean_post']:+.3f}   clamped {sc['mean_post']:+.3f}")
    print(f"  final lived mood:            released {sr['final']:+.3f}   clamped {sc['final']:+.3f}")

    # the second arrow, error-barred: released-minus-clamped, per seed, both metrics
    habit_cmp = paired([_signatures(r["mood"])["habituation"] for r, _ in runs],
                       [_signatures(c["mood"])["habituation"] for _, c in runs])
    post_cmp = paired([_signatures(r["mood"])["mean_post"] for r, _ in runs],
                      [_signatures(c["mood"])["mean_post"] for _, c in runs])
    print("\n  HABITUATION suppressed by the grip (released vs clamped, per-seed):")
    print(verdict("habituation delta", habit_cmp))
    print("  POST-LOSS mood held down by the grip (released vs clamped, per-seed):")
    print(verdict("mean-post delta", post_cmp))

    suppressed = (habit_cmp.effect.mean > 0.02 and habit_cmp.sign[0] == habit_cmp.sign[1]
                  and post_cmp.effect.mean > 0.02 and post_cmp.sign[0] == post_cmp.sign[1])
    print("  -> " + (
        "THE SECOND ARROW: the grip suppresses habituation -- the wound will not fade, "
        "and the appropriated tone keeps mood lower. Releasing it lets recovery resume."
        if suppressed else
        "no clear grip effect on the trajectory (check HOLD/AMP or self-relevance)."))

    # optional: the grip's effect on the QUALITY of reflection (needs a model)
    if args.llm == "ollama":
        rel_r = run_arm(llm, args.seed, do_reflect=True, grip=0.0)
        rel_c = run_arm(llm, args.seed, do_reflect=True, grip=1.0)
        eq_r = statistics.fmean(equanimity(x) for x in rel_r["reflections"]) if rel_r["reflections"] else 0.0
        eq_c = statistics.fmean(equanimity(x) for x in rel_c["reflections"]) if rel_c["reflections"] else 0.0
        print(f"\n  EQUANIMITY of reflection (independent downstream read):")
        print(f"     grip released: {eq_r:+.3f}    grip clamped: {eq_c:+.3f}")
        print("  -> " + ("clamping the grip lowers equanimity (more rumination), as predicted."
                        if eq_c < eq_r - 0.01 else
                        "equanimity did not separate (small-model noise; substrate result stands)."))


def _spark(xs: list[float]) -> str:
    blocks = "▁▂▃▄▅▆▇█"
    lo, hi = min(xs), max(xs)
    rng = (hi - lo) or 1.0
    return "".join(blocks[min(7, int((x - lo) / rng * 7.999))] for x in xs)


if __name__ == "__main__":
    main()
