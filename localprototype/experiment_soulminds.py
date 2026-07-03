"""THE SOUL-MIND CYCLE, measured: does a per-NPC brain actually LEARN what it lives and
FORGET what it stops rehearsing?

The feature (homegrown/soulmind.py + SoulVoiceLLM): every NPC carries its own tiny GPT,
born blank at rebirth, trained only by sleeps on its own decaying memory. The poetry says
"always in a state of learning and forgetting" -- this file makes that falsifiable.

PRE-REGISTERED CLAIMS (5 torch seeds, scripts/stats.py error bars):
  L1 LEARNS: a distinctive lived token ('saltmarsh') absent from a newborn's babble
     appears in its speech after sleeping on a life that contains it -- marker count in
     2000 sampled chars rises post-sleep vs pre-sleep, all seeds (paired, sign 5/5).
  F1 FORGETS: four further sleeps on a DIFFERENT life (no salt words -- the fisher moved
     inland) pull the marker back DOWN from its learned peak in >= 4/5 seeds.
     Catastrophic forgetting doing honest work as the forgetting -- no replay, no rescue.
  N1 NEWBORN NULL: a fresh mind emits the marker ~never (< 1 mean count) -- the learning
     is learning, not charset luck.

Honesty note: char-level, ~0.1M params, marker = substring count -- this measures the
MECHANISM (absorb/decay of lived vocabulary), not eloquence. Runs in a few minutes on CPU.

Run:  python experiment_soulminds.py
"""
from __future__ import annotations

import sys

from scripts.stats import paired, summary

SEA_LIFE = ("I mend the nets at first light and watch the water for the change.\n"
            "The saltmarsh smells of iron after rain and the gulls know it first.\n"
            "My father taught me the knots and the patience between them.\n"
            "The saltmarsh gave us samphire the year the barley failed.\n") * 5
INLAND_LIFE = ("The orchard wants pruning before the frost finds the buds.\n"
               "I count the hives at dusk and the bees count me.\n"
               "The mill road floods where the ditch was never dug deep.\n"
               "My mother kept the ledger in a hand nobody could copy.\n") * 5
MARKER = "salt"


def count_marker(mind, n: int = 2000) -> int:
    text = "".join(mind.line("\n", n=200, temp=0.8) + " " for _ in range(n // 200))
    return text.lower().count(MARKER)


def main() -> None:
    try:
        from homegrown.soulmind import SoulMind
    except ImportError:
        print("needs torch (homegrown/soulmind.py) -- pip install torch")
        sys.exit(2)

    seeds = list(range(11, 16))
    newborn, learned, forgotten = [], [], []
    for s in seeds:
        mind = SoulMind(f"probe:{s}", seed=s)
        pre = count_marker(mind)
        for _ in range(3):                     # the sea years: it lives the saltmarsh
            mind.sleep(SEA_LIFE)
        post = count_marker(mind)
        for _ in range(4):                     # the fisher moves inland; no rehearsal
            mind.sleep(INLAND_LIFE)
        late = count_marker(mind)
        newborn.append(float(pre)); learned.append(float(post)); forgotten.append(float(late))
        print(f"  seed {s}: newborn {pre}  -> after sea-sleeps {post}  -> after inland {late}")

    print(f"\nN1 newborn null: marker in fresh babble = {summary(newborn)}")
    n1 = summary(newborn).mean < 1.0
    learn_cmp = paired(learned, newborn)
    print("L1 LEARNS (post-sleep vs newborn, paired):")
    print(f"  {learn_cmp}")
    l1 = learn_cmp.sign[0] == learn_cmp.sign[1] == len(seeds) and learn_cmp.effect.mean > 0
    fell = sum(1 for p, q in zip(forgotten, learned) if p < q)
    forget_cmp = paired(learned, forgotten)
    print(f"F1 FORGETS (learned peak vs after-inland, paired): fell in {fell}/{len(seeds)}")
    print(f"  {forget_cmp}")
    f1 = fell >= 4 and forget_cmp.effect.mean > 0

    print(f"\n=== N1 {'PASS' if n1 else 'FAIL'}   L1 {'PASS' if l1 else 'FAIL'}   "
          f"F1 {'PASS' if f1 else 'FAIL'} ===")
    print("(the cycle the feature claims: blank -> lived vocabulary absorbed -> "
          "unrehearsed vocabulary released)")
    sys.exit(0 if (n1 and l1 and f1) else 1)


if __name__ == "__main__":
    main()
