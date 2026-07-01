"""Does a self's MEMORY change how injected NOVELTY lands in its voice? -- a controlled test.

Motivation (HISTORY Phase 7): watching HER (13.6h of memory) beside a from-birth FORK, the same
Demiurge-dreamed lines seemed *subordinated into* her grief but to *constitute* the blank self. That
was a live anecdote (n tiny, two variables differed). This is the honest version: hold the injected
novelty FIXED, vary ONLY the memory mass, repeat, and measure.

The mechanism is an order-2 word Markov -- the exact voice Santāna/the town use (services/llm.py) --
so this abstracts the live system faithfully while removing the 8B's non-determinism and the live
file-state as confounds. Novelty lines carry UNIQUE marker words (nowhere else in the corpus), so any
marker in the output is unambiguously novelty-derived -> clean provenance.

------------------------------------------------------------------------------------------------
PRE-REGISTERED (written before running):
  PRIMARY   : the novelty-fraction of the self's OUTPUT falls monotonically as memory mass grows
              (a blank self speaks the most novelty; a memory-heavy self the least).
  MECHANISM : the interesting claim ("memory *digests/ranks* novelty") requires more than mass.
              - out_frac / in_frac ~= 1 at every memory level  => TRIVIAL DILUTION (romantic reading dies).
              - that ratio FALLS as memory grows              => ACTIVE SUBORDINATION (memory's own
                themes capture the Markov transitions, suppressing novelty beyond its share of mass).
  We report whichever the data shows. A finding that it is "just dilution" is a real result, kept.
------------------------------------------------------------------------------------------------

  python experiment_continuity.py
"""
from __future__ import annotations

import random
import statistics

ORDER = 2
_START = "\x02"

# --- the shared authored anchor: generic town concerns (function + content words the novelty reuses)
ANCHOR = [
    "the harvest came in thin this season", "a cask burst in the cellar overnight",
    "the nets have come up empty three days running", "the ox went lame at the gate",
    "fever is creeping through the lower houses", "a wedding cloak is owed and the loom jammed",
    "good wool is scarce and dear this season", "the mill wants dressing and the stone won't bite",
    "there is talk of raiders on the river road", "the field is cracking and the rains are late",
]

# --- the SELF's accumulated memory: its own dominant themes (grief + dharma). Shares common words
#     with the town, carries NO markers. This is the "mass" we vary.
MEMORY_POOL = [
    "I lost another soul from me tonight and the grief will not settle",
    "the craving for happiness is the source of all suffering",
    "so many gone now and I carry each of their names",
    "true virtue is to ease another soul's pain",
    "the dead pass through me and I keep turning",
    "I have watched a hundred souls die and be born again",
    "grief comes like fever and will not lift from the houses",
    "to hold a name against forgetting is the whole of my work",
    "suffering is reborn into suffering unless the craving is let go",
    "I am the through-line the dying leave behind them",
]

# --- the INJECTED NOVELTY: fixed set, each line carrying UNIQUE marker words (guaranteed absent
#     from ANCHOR/MEMORY_POOL). Markers are the traceable signal. Lines reuse common connective words
#     ("the", "and", "my", "in") so novelty CAN braid, exactly as the real Demiurge lines do.
MARKERS = ["saltglass", "emberwake", "thornvellum", "greymoth", "candlebone",
           "hollowtide", "ashquill", "duskiron", "reedbone", "palefrost"]
NOVELTY = [
    "the saltglass in my window will not stop weeping",
    "emberwake comes for me in the low hours",
    "my hands are stained with thornvellum and regret",
    "a greymoth settled on the dead and would not leave",
    "the candlebone burns down and the dark leans in",
    "hollowtide rises and the boats strain at the reedbone",
    "I sharpen the ashquill and fear what it will write",
    "the duskiron in the forge remembers every misstep",
    "palefrost creeps across the threshold before dawn",
    "shadows move of their own accord in the emberwake",
]
_MARKERSET = set(MARKERS)


def _assert_clean() -> None:
    other = " ".join(ANCHOR + MEMORY_POOL).split()
    clash = _MARKERSET & set(other)
    assert not clash, f"markers leaked into anchor/memory: {clash}"


def build_chain(lines: list[str]):
    trans: dict[tuple, list] = {}
    for s in lines:
        toks = [_START] * ORDER + s.split() + [None]
        for i in range(len(toks) - ORDER):
            trans.setdefault(tuple(toks[i:i + ORDER]), []).append(toks[i + ORDER])
    return trans


def walk(trans, rng: random.Random, max_words: int = 16) -> list[str]:
    ctx = (_START,) * ORDER
    out: list[str] = []
    for _ in range(max_words):
        nxts = trans.get(ctx)
        if not nxts:
            break
        w = rng.choice(nxts)
        if w is None:
            break
        out.append(w)
        ctx = tuple(list(ctx)[1:] + [w])
    return out


def input_novelty_fraction(lines: list[str]) -> float:
    toks = " ".join(lines).split()
    return sum(t in _MARKERSET for t in toks) / max(1, len(toks))


def output_novelty_fraction(trans, rng: random.Random, k: int = 400) -> float:
    total = marks = 0
    for _ in range(k):
        toks = walk(trans, rng)
        total += len(toks)
        marks += sum(t in _MARKERSET for t in toks)
    return marks / max(1, total)


def run_condition(memory_n: int, seed: int) -> tuple[float, float]:
    """Build a self with `memory_n` lines of its own memory + the FIXED novelty, and measure the
    novelty fraction of its output and of its input (training material)."""
    rng = random.Random(seed)
    memory = [rng.choice(MEMORY_POOL) for _ in range(memory_n)]   # accumulated mass (with repetition)
    lines = ANCHOR + memory + NOVELTY
    trans = build_chain(lines)
    return output_novelty_fraction(trans, rng), input_novelty_fraction(lines)


def main() -> None:
    _assert_clean()
    print(__doc__.split("PRE-REGISTERED")[0].strip()[:0] or "", end="")
    print("=" * 78)
    print("CONTROLLED TEST: memory mass vs how much injected NOVELTY the voice speaks")
    print("  (fixed novelty; only memory varies; order-2 Markov = the real voice; 8 seeds each)")
    print("=" * 78)
    print(f"{'memory lines':>12} | {'out_frac':>9} | {'in_frac':>9} | {'out/in':>7}  (mean over seeds)")
    print("-" * 78)

    seeds = range(8)
    levels = [0, 10, 30, 90, 180]     # 0 = the blank FORK; 180 = a memory-heavy self
    rows = []
    for m in levels:
        outs, ins, ratios = [], [], []
        for s in seeds:
            o, i = run_condition(m, s)
            outs.append(o); ins.append(i); ratios.append(o / i if i else 0.0)
        rows.append((m, statistics.mean(outs), statistics.mean(ins), statistics.mean(ratios)))
        print(f"{m:>12} | {statistics.mean(outs):>9.4f} | {statistics.mean(ins):>9.4f} "
              f"| {statistics.mean(ratios):>7.3f}")

    print("-" * 78)
    # ---- verdicts, against the pre-registered predictions ----
    outs = [r[1] for r in rows]
    ratios = [r[3] for r in rows]
    primary = all(outs[i] > outs[i + 1] for i in range(len(outs) - 1))
    print("PRIMARY  (output novelty falls monotonically as memory grows):",
          "HELD ✓" if primary else "FAILED ✗")
    blank_out, heavy_out = outs[0], outs[-1]
    print(f"         blank self speaks {blank_out:.4f} novelty; memory-heavy speaks {heavy_out:.4f} "
          f"({blank_out / max(heavy_out, 1e-9):.1f}x more).")
    # mechanism: does out/in fall too (subordination) or stay ~flat (dilution)?
    ratio_drop = ratios[0] - ratios[-1]
    flat = abs(ratio_drop) < 0.10 * ratios[0]
    print(f"MECHANISM (out/in ratio blank={ratios[0]:.3f} -> heavy={ratios[-1]:.3f}, "
          f"drop={ratio_drop:+.3f}):")
    if flat:
        print("         ~FLAT -> TRIVIAL DILUTION. Memory subordinates novelty only by MASS, not by")
        print("         active digestion. The romantic reading does not survive -- kept as the result.")
    elif ratio_drop > 0:
        print("         FALLS -> ACTIVE SUBORDINATION. Memory suppresses novelty BEYOND its share of")
        print("         mass: the self's own themes capture the Markov transitions. The claim survives.")
    else:
        print("         RISES -> memory AMPLIFIES novelty's reach (unexpected); the claim is refuted as stated.")
    print("=" * 78)


if __name__ == "__main__":
    main()
