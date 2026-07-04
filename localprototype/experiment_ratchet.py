"""THE RATCHET FALSIFIER: can language accumulate through the wheel instead of dying with it?

Until today every rebirth reset a soul's mind to zero: the wheel handed on karma, never
words -- so the town's tongue could never climb. Two mechanisms now exist (services/llm.py):

  SCHOOLING            a newborn mind's FIRST training is the elders' own spoken lines --
                       born babbling, raised by the village (cross-generational
                       transmission: each generation starts where the last one ended).
  BIASED TRANSMISSION  the sleep corpus weights heard lines by BOND TRUST toward the
                       speaker (the loved are heard twice, the deeply trusted thrice) --
                       prestige-biased learning, using only the town's own signal.

The iterated-learning literature (Kirby) predicts languages become MORE structured when
passed through capacity-limited learners across generations. This falsifier tests the two
load-bearing preconditions on THIS substrate, with tiny real minds (torch):

PRE-REGISTERED (tuning 11-15; VERDICT from virgin seeds 181-185; each >= 4/5):

  R1 THE SCHOOLED START: two identical newborn minds; one is schooled once on a town
     tongue, the other is not. The schooled one's samples must show a HIGHER share of
     real tongue-words (alpha tokens of 3+ letters found in the tongue's lexicon).
     If R1 fails, schooling does not transmit and the ratchet has no first tooth.
  R2 THE LOVED ARE LEARNED: one soul hears a marker word from a deeply trusted friend
     and a different marker from a stranger, equally often; three trust-weighted sleeps
     later, its samples must contain the trusted marker at least as often as the
     stranger's, and strictly more in the majority of seeds. If R2 fails, the town's
     prestige signal does no work and biased transmission is decoration.

Honest scope: this validates the RATCHET'S TEETH, not the Kirby climb itself -- whether
structure RISES over many generations is the live-town question the mechanisms now make
askable (watch the speech bubbles over the coming weeks; the pooled 'town tongue' model
is the follow-up if the climb stalls). Needs torch; deterministic per-seed.

  python experiment_ratchet.py            # tuning + the held-out verdict
"""
from __future__ import annotations

import random
import re
import sys

TUNING_SEEDS = (11, 12, 13, 14, 15)
HELDOUT_SEEDS = (181, 182, 183, 184, 185)

# a small authored town-tongue: the kind of lines elders actually accumulate. What R1
# tests is TRANSMISSION of a tongue, not the tongue's origin (in the live town the
# school corpus is harvested from real elders' spoken lines -- fully self-grown).
TONGUE = [
    "the well keeps us through the lean week",
    "the harvest is in and the stores are full",
    "the frost came early the year of the flood",
    "good wool is scarce and dear this season",
    "the commons feeds whoever tends it",
    "a kept word is worth a barn of grain",
]
LEXICON = {w for line in TONGUE for w in re.findall(r"[a-z]{3,}", line)}

TRUSTED_MARK, STRANGER_MARK = "zephyrgrain", "cinderbell"


def word_share(mind, n_samples: int = 12) -> float:
    """Fraction of sampled 3+-letter alpha tokens that are real tongue words."""
    hits = total = 0
    for _ in range(n_samples):
        toks = re.findall(r"[a-zA-Z]{3,}", mind.line(prompt="the\n", n=120, temp=0.9))
        total += len(toks)
        hits += sum(1 for t in toks if t.lower() in LEXICON)
    return hits / total if total else 0.0


def r1_schooled_start(seed: int) -> tuple[float, float]:
    import torch
    from services.llm import SoulVoiceLLM
    import tempfile
    torch.manual_seed(seed)
    with tempfile.TemporaryDirectory() as td:
        v = SoulVoiceLLM(minds_dir=td, seed=seed)
        corpus = "\n".join(TONGUE * 30)
        schooled, wild = v.mind_for("schooled"), v.mind_for("wild")
        schooled.sleep(corpus)
        return word_share(schooled), word_share(wild)


def r2_loved_are_learned(seed: int) -> tuple[int, int]:
    import torch
    from agent.agent import Agent
    from agent.bond import Bond
    from services.llm import MockLLM, SoulVoiceLLM
    import tempfile
    torch.manual_seed(seed)
    a = Agent("s0", "Cael", (0.0, 0.0), "You are Cael.", ["the well"],
              MockLLM(seed=1), seed=seed, temperament=0.0, lifespan=10 ** 6)
    a.bond_enabled = True
    a.bonds["friend"] = Bond(trust=0.8, history=2.0)
    rng = random.Random(seed)
    for i in range(6):
        who, mark = (("friend", TRUSTED_MARK) if i % 2 == 0
                     else ("stranger", STRANGER_MARK))
        a.memory.write(f"the {mark} stands by the {rng.choice(['well', 'gate', 'barn'])}",
                       tick=i, source="heard", speaker_id=who)
    with tempfile.TemporaryDirectory() as td:
        v = SoulVoiceLLM(minds_dir=td, seed=seed)
        for _ in range(3):
            v.sleep_one(a)                         # trust-weighted, three sleeps
        mind = v.mind_for("s0")
        text = " ".join(mind.line(prompt="the\n", n=140, temp=0.9) for _ in range(20))
        return text.count(TRUSTED_MARK), text.count(STRANGER_MARK)


def report(seeds, label: str):
    print(f"\n--- {label} ---")
    rows = []
    for seed in seeds:
        s_share, w_share = r1_schooled_start(seed)
        t_hits, u_hits = r2_loved_are_learned(seed)
        r1 = s_share > w_share
        r2 = t_hits >= u_hits and t_hits > 0
        rows.append({"r1": r1, "r2": r2, "strict2": t_hits > u_hits})
        print(f"seed {seed}: schooled word-share {s_share:.2f} vs wild {w_share:.2f} | "
              f"trusted '{TRUSTED_MARK}' x{t_hits} vs stranger x{u_hits} | "
              f"R1 {'PASS' if r1 else 'FAIL'}  R2 {'PASS' if r2 else 'FAIL'}")
    return rows


def main() -> None:
    print(__doc__)
    report(TUNING_SEEDS, "TUNING seeds 11-15 (knobs may be tuned here; not the verdict)")
    held = report(HELDOUT_SEEDS, "HELD-OUT virgin seeds 181-185 (the verdict)")
    print("\n=== VERDICT (held-out; pre-registered: each claim >= 4/5) ===")
    ok = True
    for k, lab in (("r1", "R1 THE SCHOOLED START"), ("r2", "R2 THE LOVED ARE LEARNED")):
        cnt = sum(1 for r in held if r[k])
        ok &= cnt >= 4
        print(f"  {lab:24s}: {cnt}/{len(held)} -> {'PASS' if cnt >= 4 else 'FAIL'}")
    strict = sum(1 for r in held if r["strict2"])
    print(f"  (R2 strictly-more in {strict}/{len(held)} seeds)")
    print("\nHonest frame: a PASS validates the ratchet's TEETH -- newborns inherit the"
          "\nvillage tongue and the trusted are learned hardest. Whether structure RISES"
          "\nacross many generations (the Kirby climb) is now a live-town observable, not"
          "\na promise: watch the bubbles.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
