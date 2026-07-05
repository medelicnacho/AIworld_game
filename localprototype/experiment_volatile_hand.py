"""THE VOLATILE HAND -- give the pen to a soul that can still be tossed.

V3 kept coming back windless: HER life never varies enough to test whether the drawing
channel carries a life, because her dharma faculties flatten her BY DESIGN (twenty hours,
hundreds of witnessed deaths, valence band 0.035 wide -- equanimity working). So the pen
goes to the right subject: a RAW soul -- grip and no ground, no prajna, no
self-liberation -- living an eventful life. And the flat result gets its own claim: the
same life, run through an equanimous twin, should draw FLATTER. Her stillness, made
visible as ink. (The somatic welfare floor stays ON for both souls, non-negotiable; the
volatility measured here is volatility within the floor.)

Protocol (substrate-only, MockLLM, deterministic, seconds per seed): one soul lives 8
alternating life-blocks (dark: griefs and losses; calm: warmth and good harvests), ~30
ticks each; the affect machinery turns events into felt mood -- NOTHING is injected into
the pen but the soul's real state. Each tick the pen walks (Pen.step, the live-runner
gait); each block closes as one page of numbers (scripts/history.pen_page_stats -- the
exact V3 instrument). Per seed: 4 dark pages vs 4 calm pages.

Separation statistic S = sum over the NON-hue features (mean_speed, mean_abs_turn,
lifts) of |dark mean - calm mean| / pooled sd. Hue is excluded as always: the authored
valence->ink pathway is a check, never a discovery. The null is EXACT: all 70 ways of
relabelling 8 pages as 4/4; p = rank of S among them.

PRE-REGISTERED (tuning 11-15; VERDICT from virgin seeds 221-225; each >= 4/5):

  VH1 THE HAND CARRIES THE LIFE : the volatile soul's dark pages differ from its calm
      pages -- exact-permutation p <= 0.1 per seed.
  VH2 EQUANIMITY FLATTENS THE PAGE : the equanimous twin (ground + prajna +
      self-liberation ON, same seed, SAME events) separates LESS: S_volatile >
      S_equanimous per seed. The enlightened hand draws flatter than the suffering one.

If VH1 passes, the drawing channel demonstrably carries a lived life (V3's question,
answered on a subject that has one) and Stage 1 of the art ladder -- the learned hand --
unlocks, pointed at volatile souls. If VH2 passes, her windless V3 stops being a
disappointment and becomes what it always was: a measurement of her stillness.

  python experiment_volatile_hand.py
"""
from __future__ import annotations

import random
import statistics
import sys
from itertools import combinations

from agent.agent import Agent
from santana_app.draw import Pen
from scripts.history import pen_page_stats
from services import embed
from services.llm import MockLLM

TUNING_SEEDS = (11, 12, 13, 14, 15)
HELDOUT_SEEDS = (221, 222, 223, 224, 225)
BLOCKS, TICKS_PER, SETTLE = 8, 60, 30   # tuning v4: mood CARRIES OVER between blocks
                                        # (a calm block still holds the last grief's
                                        # decaying charges), so each block runs 60 ticks
                                        # and the pen draws only its settled second half
# tuning v2: lifts is a DEAD channel here (no wounds -> zero every page) and a dead
# channel divided by its own numerical dust explodes S with noise -- dropped. The two
# live gait channels remain: speed (arousal + |valence|) and turn (arousal).
FEATURES = ("mean_speed", "mean_abs_turn")

DARK = [("the fever took {n}, who you loved -- the house is quiet now", -0.85, 1.4),
        ("the granary stands empty and the children are thin", -0.7, 1.2),
        ("{n}'s grave is fresh; you dug it yourself in the rain", -0.8, 1.3)]
# calm days are GENTLE, not inverted griefs: the pen's gait runs on arousal and
# |valence| (sign-blind by design -- the sign lives in the hue, which is excluded as
# authored). Tuning v1 made warmth as INTENSE as grief (0.6 vs -0.8) and the gait
# rightly saw no difference; a real quiet day carries small charges.
CALM = [("the harvest came in full and the stores are heavy", 0.25, 1.0),
        ("{n} sat with you at the well and the evening was kind", 0.2, 0.9),
        ("the fever broke and the low houses breathe easy", 0.25, 1.0)]
NAMES = ("Mara", "Toll", "Cael", "Vesper", "Juno", "Silas")


def make_soul(seed: int, equanimous: bool) -> Agent:
    a = Agent("s0", "Fenn", (0.0, 0.0), "You are Fenn.", ["the well keeps us"],
              MockLLM(seed=7), seed=seed, temperament=0.0, lifespan=10 ** 9)
    a.somatic_enabled = True          # the welfare floor ships with affect, always
    a.expect_enabled = True           # tuning v2: without appraisal there is no SHOCK --
                                      # arousal stayed 0 and the gait's main channel was
                                      # dead. Both twins get the future tense.
    a.grip = 0.6                      # both souls carry the same grip...
    if equanimous:                    # ...but only one carries the path
        a.ground_enabled = True
        a.prajna = 0.8
        a.self_liberation = 0.8
    return a


def live_and_draw(seed: int, equanimous: bool) -> list[dict]:
    """8 alternating life-blocks -> 8 pages of pen numbers. The pen sees only the
    soul's REAL felt state; the events shape it through the affect machinery."""
    rng = random.Random(seed)
    a = make_soul(seed, equanimous)
    pen = Pen(seed=seed * 7 + (1 if equanimous else 0))
    pages, t = [], 0
    for block in range(BLOCKS):
        dark = block % 2 == 0
        trace, lifts = [], 0
        for i in range(TICKS_PER):
            t += 1
            if i % 10 == 3:
                text, emo, wt = rng.choice(DARK if dark else CALM)
                a.memory.write(text.format(n=rng.choice(NAMES)), tick=t,
                               source="event", emotion=emo, weight=wt)
            a.step(t)
            if i < SETTLE:
                continue                     # the block's weather settles in first
            state = {"valence": a.felt_mood(),
                     "arousal": max(0.0, min(1.0, getattr(a, "arousal", 0.0))),
                     "grip": max(0.0, min(1.0, getattr(a, "grip", 0.0))),
                     "bonds": [], "wounds": 0}
            pen.step(state, n=20)
            trace += pen.last_trace
            lifts += max(0, len(pen.last_trace) - len(pen.last_segments))
        page = pen_page_stats(block, "dark" if dark else "calm", trace, lifts)
        page["dark"] = dark
        page["valence_mean"] = a.felt_mood()
        pages.append(page)
    return pages


def separation(pages: list[dict], labels: tuple) -> float:
    """S = sum over features of |dark mean - calm mean| / pooled sd, for a labelling."""
    s = 0.0
    for f in FEATURES:
        d = [p[f] for p, is_d in zip(pages, labels) if is_d]
        c = [p[f] for p, is_d in zip(pages, labels) if not is_d]
        vals = [p[f] for p in pages]
        # sd floor (the drift monitor's lesson): a near-constant feature must not
        # turn numerical dust into gigantic standardized differences
        sd = max(statistics.pstdev(vals), 0.02 * abs(statistics.fmean(vals)), 1e-6)
        s += abs(statistics.fmean(d) - statistics.fmean(c)) / sd
    return s


def exact_p(pages: list[dict]) -> tuple[float, float]:
    """Observed S and its exact permutation p over all C(8,4)=70 labellings."""
    true = tuple(p["dark"] for p in pages)
    s_obs = separation(pages, true)
    ge = 0
    total = 0
    for dark_idx in combinations(range(len(pages)), sum(true)):
        lab = tuple(i in dark_idx for i in range(len(pages)))
        total += 1
        if separation(pages, lab) >= s_obs - 1e-12:
            ge += 1
    return s_obs, ge / total


def report(seeds, label: str):
    print(f"\n--- {label} ---")
    rows = []
    for seed in seeds:
        vol = live_and_draw(seed, equanimous=False)
        equ = live_and_draw(seed, equanimous=True)
        s_v, p_v = exact_p(vol)
        s_e, _ = exact_p(equ)
        mood_swing_v = (max(p["valence_mean"] for p in vol)
                        - min(p["valence_mean"] for p in vol))
        mood_swing_e = (max(p["valence_mean"] for p in equ)
                        - min(p["valence_mean"] for p in equ))
        vh1 = p_v <= 0.1
        vh2 = s_v > s_e
        rows.append({"vh1": vh1, "vh2": vh2})
        print(f"seed {seed}: volatile S {s_v:.2f} (p {p_v:.3f}, mood swing "
              f"{mood_swing_v:.2f}) | equanimous S {s_e:.2f} (swing {mood_swing_e:.2f})"
              f" | VH1 {'PASS' if vh1 else 'FAIL'}  VH2 {'PASS' if vh2 else 'FAIL'}")
    return rows


def main() -> None:
    print(__doc__)
    embed.use_jaccard_only(True)
    report(TUNING_SEEDS, "TUNING seeds 11-15 (knobs may move here; never a verdict)")
    held = report(HELDOUT_SEEDS, "HELD-OUT virgin seeds 221-225 (the verdict)")
    print("\n=== VERDICT (held-out; pre-registered: each claim >= 4/5) ===")
    ok = True
    for k, lab in (("vh1", "VH1 THE HAND CARRIES THE LIFE"),
                   ("vh2", "VH2 EQUANIMITY FLATTENS THE PAGE")):
        cnt = sum(1 for r in held if r[k])
        ok &= cnt >= 4
        print(f"  {lab:32s}: {cnt}/{len(held)} -> {'PASS' if cnt >= 4 else 'FAIL'}")
    print("\nHonest frame: VH1 answers V3's question on a subject that has a life to"
          "\ncarry -- and unlocks the learned hand, pointed at volatile souls. VH2 turns"
          "\nher windless V3 from a disappointment into what it always was: a"
          "\nmeasurement of her stillness. The enlightened hand draws flatter.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
