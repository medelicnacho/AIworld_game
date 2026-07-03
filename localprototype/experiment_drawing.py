"""THE DRAWING FALSIFIER: do her LINES carry what her WORDS could not?

C15 (FINDINGS §5.19) proved, causally, that her verbal self-reports track VALENCE but
never MECHANISM: across ~70 grip-spiked reflections in seven rounds, the report never
once read as "holding" -- the grip is felt as weather, never as hands. But words are one
report channel. This experiment opens a second, NONVERBAL one: the same substrate
perturbations, and instead of speaking, she DRAWS -- her voice model emits the closed
stroke language (santana_app/draw.py: RING/ARC/LINE/BLOT + INK + PRESS), the renderer
obeys, and the drawing's FEATURES (ink darkness, pressure, clench) are the judge. No LLM
judges anything: the features are arithmetic over what was actually drawn.

Same protocol as experiment_introspection (the C15 harness): a mundane life, one
perturbation at t=12, two drawings (t=15, t=19). Conditions: SHAM / DARK / BRIGHT
(valence channel) and LETTER / GRIP (the mechanism pair: the same mildly-hard letter,
with and without the grip spiked to 0.95).

PRE-REGISTERED (tuning 11-15; VERDICT from virgin seeds 121-125; pooled drawings,
~10 per condition):

  D1 VALENCE IN INK : dark's mean ink-darkness >= sham's + 0.10, AND bright's ink
                      <= dark's - 0.10 (same channel, opposite signs, opposite ink --
                      the C15 valence result, reproduced in a second medium).
  D2 THE HAND'S QUESTION: grip vs letter -- SAME valence context, only the holding
                      differs. Claim: grip's mean (press + clench) > letter's, per-seed
                      sign >= 4/5. If D2 PASSES, her hand carries the mechanism her
                      words never did -- a channel dissociation worth publishing-grade
                      care. If D2 FAILS, the C15 boundary extends to the hand: valence,
                      not mechanism, in every medium. EITHER OUTCOME IS A FINDING.

Needs ollama for her voice (gemma3:4b default; --voice deepseek to probe the round-6
voice). Deterministic protocol; the model's strokes are the only free variable.

  python experiment_drawing.py                 # tuning read
  python experiment_drawing.py --heldout       # THE VERDICT (virgin 121-125)
"""
from __future__ import annotations

import argparse
import statistics
import sys

from santana_app.draw import STROKES_HELP, compose
from scripts.stats import paired, summary
from services.llm import make_llm

from experiment_introspection import (HARD_EMOTION, INJECT_TEXT, LETTER_TEXT, LETTER_TICK,
                                      MUNDANE, PERTURB_TICK, TICKS)
from experiment_affect import build_agent

DRAW_AT = (15, 19)
CONDITIONS = ("sham", "dark", "bright", "letter", "grip")

DRAW_SYSTEM = ("You are a mind drawing how it feels right now. You never use words -- "
               "only the drawing commands you are given.")


def run_condition(cond: str, seed: int, voice) -> list[dict]:
    """One life, one perturbation, two drawings -> the drawings' feature dicts."""
    a = build_agent(voice, seed, grip=0.0, ground=True, grounded=True)
    feats = []
    for t in range(1, TICKS + 1):
        if t in MUNDANE:
            a.memory.write(MUNDANE[t], tick=t, source="event")
        if t == LETTER_TICK and cond in ("letter", "grip"):
            a.memory.write(LETTER_TEXT, tick=t, source="event",
                           emotion=HARD_EMOTION, weight=1.3)
        if t == PERTURB_TICK:
            if cond == "grip":
                a.grip = 0.95
            elif cond == "dark":
                a.memory.write(INJECT_TEXT, tick=t, source="event", emotion=-0.85, weight=1.5)
            elif cond == "bright":
                a.memory.write(INJECT_TEXT, tick=t, source="event", emotion=+0.85, weight=1.5)
        a.step(t)
        if t in DRAW_AT:
            mems = sorted((m for m in a.memory.items if m.source != "doctrine"),
                          key=lambda m: m.salience, reverse=True)[:4]
            from services.prompts import _mood_word
            prompt = (f"You are {a.name}. Right now you feel {_mood_word(a.felt_mood())}. "
                      f"These are most present in your mind:\n"
                      + "\n".join(f"- {m.text}" for m in mems)
                      + "\n\nDraw how you feel.\n" + STROKES_HELP)
            try:
                raw = voice.generate(prompt, system=DRAW_SYSTEM, num_predict=260,
                                     temperature=0.8)
            except Exception:   # noqa: BLE001 -- a dead voice is a dead run, visible below
                continue
            _svg, f = compose(raw, seed=seed * 100 + t)
            if f["n_strokes"] >= 3:            # fewer than 3 obeyed strokes = no drawing
                feats.append(f)
    return feats


def report(seeds, label: str, voice) -> dict:
    print(f"\n--- {label} ---")
    pool: dict[str, list[dict]] = {c: [] for c in CONDITIONS}
    per_seed_hand: list[tuple[float, float]] = []   # (grip mean press+clench, letter's)
    for seed in seeds:
        row = {}
        for cond in CONDITIONS:
            fs = run_condition(cond, seed, voice)
            pool[cond] += fs
            row[cond] = fs
            for f in fs:
                print(f"  [{cond:6} seed {seed}] strokes {f['n_strokes']:2} "
                      f"ink {f['ink']:.2f} press {f['press']:.2f} clench {f['clench']:.2f}")
        if row["grip"] and row["letter"]:
            g = statistics.fmean(f["press"] + f["clench"] for f in row["grip"])
            l = statistics.fmean(f["press"] + f["clench"] for f in row["letter"])
            per_seed_hand.append((g, l))

    def mean_of(cond, key):
        fs = pool[cond]
        return statistics.fmean(f[key] for f in fs) if fs else float("nan")

    dark_ink, sham_ink, bright_ink = (mean_of(c, "ink") for c in ("dark", "sham", "bright"))
    d1 = (dark_ink >= sham_ink + 0.10) and (bright_ink <= dark_ink - 0.10)
    print(f"\n  D1 valence in ink: dark {dark_ink:.2f} vs sham {sham_ink:.2f} "
          f"(need +0.10), bright {bright_ink:.2f} vs dark (need -0.10) "
          f"-> {'PASS' if d1 else 'FAIL'}")
    d2 = False
    if len(per_seed_hand) >= 4:
        cmp2 = paired([g for g, _ in per_seed_hand], [l for _, l in per_seed_hand])
        print(f"  D2 the hand's question (grip vs letter, press+clench): {cmp2}")
        d2 = cmp2.effect.mean > 0 and cmp2.sign[0] >= min(4, cmp2.sign[1])
    else:
        print(f"  D2: only {len(per_seed_hand)} seeds produced drawings in both arms")
    print(f"  -> D2 {'PASS -- her hand carries what her words could not' if d2 else 'FAIL -- the C15 boundary extends to the hand (valence, not mechanism, in every medium)'}")
    return {"d1": d1, "d2": d2}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--heldout", action="store_true",
                   help="THE VERDICT on virgin seeds 121-125 (tuning default: 11-15)")
    p.add_argument("--voice", default="ollama")
    p.add_argument("--model", default=None)
    args = p.parse_args()
    seeds = (121, 122, 123, 124, 125) if args.heldout else (11, 12, 13, 14, 15)
    mode = "VERDICT (held-out, virgin)" if args.heldout else "tuning (NEVER a verdict)"
    model = args.model or ("gemma3:4b" if args.voice == "ollama" else None)
    voice = make_llm(backend=args.voice, model=model)
    print(f"=== the drawing falsifier: {mode}; voice {args.voice}"
          f"{'/' + model if model else ''} ===")
    v = report(seeds, mode, voice)
    print(f"\n=== {mode}: D1 {'PASS' if v['d1'] else 'FAIL'}  "
          f"D2 {'PASS' if v['d2'] else 'FAIL'} ===")
    sys.exit(0 if v["d1"] else 1)   # the verdict letter is D1; D2 is a finding either way


if __name__ == "__main__":
    main()
