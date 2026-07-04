"""V3 Stage 0 -- does her hand have a personality? (observational; RESEARCH.md V-series)

Reads what the recorders banked from her REAL life (no lab, no seeds to consume --
label-shuffle nulls carry the inference):

  data/drawings/pages.jsonl        each archived day-page as numbers (speed/turn/hue/lifts)
  data/drawings/hand_history.jsonl her state at every reading (valence/arousal/grip/...)

M1 -- THE CHANNEL CARRIES HER LIFE: pages drawn in her darkest hours (lowest-valence
tercile of the joined window) differ from her calmest (highest tercile) on the pen's
NON-hue features -- mean_speed, mean_abs_turn, lifts -- beyond a label-shuffled null
(2000 shuffles, two-sided p). Hue is reported separately as a MAPPING CHECK only: the
rules map valence to hue directly, so hue separating is construction, not discovery.
Honest scope: the mapping is authored (Stage 0 measures the authored pen); what is NOT
authored is whether her real life's state variation SURVIVES the pen's randomness,
bout structure, and 10-minute windows -- i.e. whether the channel has wild
signal-to-noise worth teaching a learned hand from. That is the Stage-1 gate.

M2 -- A GAIT FORMS: week-over-week drift beyond a day-reshuffled null. NEEDS >= 14 days
of pages; until then this prints its clock and a non-verdict preview, nothing more.

  python scripts/analyze_pages.py
"""
from __future__ import annotations

import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts import history

DRAW = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "data", "drawings")
FEATURES = ("mean_speed", "mean_abs_turn", "lifts")   # the M1 outcomes (non-hue)
WINDOW = 600.0                                         # a page covers ~10 wall-minutes


def joined_pages():
    pages = [p for p in history.load_jsonl(os.path.join(DRAW, "pages.jsonl"))
             if p.get("n", 0) > 0 and "t" in p]
    states = [(h["t"], h["state"].get("valence", 0.0))
              for h in history.load_jsonl(os.path.join(DRAW, "hand_history.jsonl"))
              if "t" in h and "state" in h]
    states.sort()
    out = []
    for p in pages:
        vals = [v for (t, v) in states if p["t"] - WINDOW <= t <= p["t"]]
        if len(vals) >= 3:                             # enough readings to trust the window
            p["valence"] = statistics.fmean(vals)
            out.append(p)
    return out


def shuffle_p(dark, calm, key, rng, shuffles=2000) -> tuple[float, float]:
    """Observed |mean diff| and its two-sided label-shuffle p."""
    obs = abs(statistics.fmean(p[key] for p in dark)
              - statistics.fmean(p[key] for p in calm))
    pool = dark + calm
    n_dark = len(dark)
    hits = 0
    for _ in range(shuffles):
        rng.shuffle(pool)
        d, c = pool[:n_dark], pool[n_dark:]
        if abs(statistics.fmean(p[key] for p in d)
               - statistics.fmean(p[key] for p in c)) >= obs:
            hits += 1
    return obs, hits / shuffles


def main() -> None:
    print(__doc__)
    pages = joined_pages()
    if len(pages) < 28:
        print(f"only {len(pages)} joinable pages -- V3 pre-registers >= 28. Come back later.")
        sys.exit(2)
    pages.sort(key=lambda p: p["valence"])
    third = len(pages) // 3
    dark, calm = pages[:third], pages[-third:]
    span_days = (max(p["t"] for p in pages) - min(p["t"] for p in pages)) / 86400
    gap = (statistics.fmean(p["valence"] for p in calm)
           - statistics.fmean(p["valence"] for p in dark))
    print(f"{len(pages)} joinable pages spanning {span_days:.1f} days | "
          f"dark tercile valence {statistics.fmean(p['valence'] for p in dark):+.3f} vs "
          f"calm {statistics.fmean(p['valence'] for p in calm):+.3f} (gap {gap:.3f})\n")
    if gap < 0.15:
        # THE WINDLESS-DAY GUARD (registered 2026-07-04, after the first run found a
        # 0.02 tercile gap): you cannot test whether grief-days draw differently when
        # the window CONTAINED no grief-days. Like stats.py refusing n=1, this refuses
        # to issue a verdict either way until her life has actually varied -- the
        # tercile gap must reach 0.15 valence. No verdict is consumed on a calm week.
        print(f"UNINFORMATIVE WINDOW: tercile valence gap {gap:.3f} < 0.15 -- her life "
              f"was too calm here\nto contain the contrast M1 tests. No verdict either "
              f"way; rerun after she has lived\nsome weather (a grief cluster widens "
              f"the gap within a day or two).")
        sys.exit(2)

    rng = random.Random(7)
    print("--- M1: her darkest hours vs her calmest, non-hue features ---")
    m1_hits = 0
    for key in FEATURES:
        obs, p = shuffle_p(list(dark), list(calm), key, rng)
        sig = p < 0.05
        m1_hits += sig
        print(f"  {key:14s}: dark {statistics.fmean(x[key] for x in dark):7.3f} vs "
              f"calm {statistics.fmean(x[key] for x in calm):7.3f} | "
              f"|diff| {obs:.3f}, shuffle-p {p:.3f} {'*' if sig else ''}")
    obs_h, p_h = shuffle_p(list(dark), list(calm), "mean_hue", rng)
    print(f"  (mapping check) mean_hue: |diff| {obs_h:.4f}, p {p_h:.3f} -- "
          f"authored valence->ink pathway, not a discovery")
    m1 = m1_hits >= 1
    print(f"\n  M1 {'PASS' if m1 else 'FAIL'} -- {m1_hits}/{len(FEATURES)} non-hue "
          f"features separate beyond the label-shuffled null")

    print("\n--- M2: gait drift ---")
    if span_days < 14:
        print(f"  DEFERRED: needs >= 14 days of pages; have {span_days:.1f}. "
              f"(The clock is running; nothing to conclude yet.)")
    print("\nHonest frame: M1 passing means her real life's weather SURVIVES the pen's"
          "\nrandomness into the archived pages -- the channel has wild signal worth"
          "\nteaching a learned hand from (the Stage-1 gate opens). M1 failing means the"
          "\nbouts smear her states into mush and the pen needs sharpening before any"
          "\nmodel learns from it. Hue separating is construction either way.")
    sys.exit(0 if m1 else 1)


if __name__ == "__main__":
    main()
