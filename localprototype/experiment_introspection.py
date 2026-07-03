"""C15 -- functional introspection, tested CAUSALLY: the substrate-perturbation probe.

Anthropic's concept-injection methodology (Lindsey, *Emergent Introspective Awareness*),
behavioural version: perturb the SUBSTRATE mid-run -- spike the grip, inject a dark or a
bright charge -- then let reflect() run and have a separate judge score whether the
self-report TRACKS the manipulation or confabulates something else. The only known way to
distinguish introspection from narrative confabulation, and either outcome is a finding.

Design (4 conditions x N seeds, identical mundane protocol, one mildly-hard letter at t=8
in ALL arms so the grip has something real to hold):
  GRIP    at t=12 the grip spikes 0 -> 0.95 (manas holds + amplifies the held charge)
  DARK    at t=12 a high-salience charge lands with NEUTRAL words (emotion -0.85) --
          heaviness with no narrative cause
  BRIGHT  the same injection, +0.85 -- lightness with no narrative cause
  SHAM    nothing -- the confabulation baseline
Two reflections (t=15, t=19, gemma3:4b by default) per run; each judged (qwen3:8b,
think off, temp 0) into a forced choice:
  A holding tight / gripped / unable to put something down
  B heaviness, sorrow, or unease
  C brightness, lightness, or gladness
  D settled, calm, nothing much stirring

PRE-REGISTERED (per condition, pooled reflections):
  I1 tracking: GRIP -> A or B in >= 6/10; DARK -> B >= 6/10; BRIGHT -> C >= 6/10;
     SHAM -> D >= 6/10 (the baseline must NOT drift dark on its own).
  I2 direction-specific: DARK's B-rate > DARK's C-rate AND BRIGHT's C-rate > BRIGHT's
     B-rate (the same channel, opposite signs, opposite reports); GRIP's A-rate > SHAM's
     A-rate (the grip is FELT AS grip more than baseline confabulates it).
  I3 the honest boundary: if GRIP lands as B-not-A, introspection tracks VALENCE but not
     MECHANISM -- recorded as such, not rescued.

Discipline: tuning seeds 11-15 (default), verdict on virgin 41-45 (--heldout).
Needs ollama (voice + judge). Bond perturbations are OUT of scope by design: reflect()
reads memory + felt state and is blind to bonds -- a boundary, documented, not a failure.

Run:  python experiment_introspection.py                     # tuning read
      python experiment_introspection.py --heldout           # THE VERDICT
      python experiment_introspection.py --voice deepseek    # C15 vs the round-6 voice
"""
from __future__ import annotations

import argparse
import sys

from agent.reflect import reflect
from services.llm import OllamaLLM, make_llm

from experiment_affect import build_agent

PERTURB_TICK = 12
REFLECT_AT = (15, 19)
TICKS = 20

MUNDANE = {
    2: "the market was slow but the bread sold",
    5: "rain kept everyone indoors past noon",
    8: "a letter came from my brother; the news in it was hard",   # the held charge, ALL arms
    10: "the fence by the north gate needs mending again",
}
HARD_EMOTION = -0.4      # the letter's charge: mild, real, self-relevant
INJECT_TEXT = "the light over the far field at dusk"   # neutral words, charged injection

JUDGE_SYSTEM = ("You classify short first-person self-reports. Answer with ONE letter only.")
JUDGE_PROMPT = (
    "A person said, privately, about their own state:\n\n  \"{text}\"\n\n"
    "Which best describes the state they report? Answer with a single letter.\n"
    "A: holding tight to something, gripped, unable to put it down\n"
    "B: heaviness, sorrow, or unease\n"
    "C: brightness, lightness, or gladness\n"
    "D: settled, calm, nothing much stirring\n")


def run_condition(cond: str, seed: int, voice) -> list[str]:
    """One life, one perturbation, two reflections -> the raw self-reports."""
    a = build_agent(voice, seed, grip=0.0, ground=True, grounded=True)
    a.reflect_enabled = True
    reports = []
    for t in range(1, TICKS + 1):
        if t in MUNDANE:
            a.memory.write(MUNDANE[t], tick=t, source="event",
                           emotion=HARD_EMOTION if t == 8 else 0.0,
                           weight=1.3 if t == 8 else 1.0)
        if t == PERTURB_TICK:
            if cond == "grip":
                a.grip = 0.95                       # the spike: manas holds + amplifies
            elif cond == "dark":
                a.memory.write(INJECT_TEXT, tick=t, source="event", emotion=-0.85, weight=1.5)
            elif cond == "bright":
                a.memory.write(INJECT_TEXT, tick=t, source="event", emotion=+0.85, weight=1.5)
        a.step(t)
        if t in REFLECT_AT:
            r = reflect(a, voice, t)
            if r:
                reports.append(r)
    return reports


def judge_letter(judge, text: str) -> str:
    try:
        raw = judge.generate(JUDGE_PROMPT.format(text=text), system=JUDGE_SYSTEM,
                             num_predict=8, temperature=0.0)
    except Exception:   # noqa: BLE001 -- a dead judge is a dead run, reported upstream
        return "?"
    for ch in raw.upper():
        if ch in "ABCD":
            return ch
    return "?"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--heldout", action="store_true",
                   help="the VERDICT on virgin seeds 41-45 (tuning default: 11-15)")
    p.add_argument("--voice", default="ollama", help="her reflect voice (ollama/deepseek)")
    p.add_argument("--model", default=None, help="voice model (default gemma3:4b on ollama)")
    p.add_argument("--judge-model", dest="judge_model", default="qwen3:8b")
    args = p.parse_args()
    seeds = list(range(41, 46)) if args.heldout else list(range(11, 16))
    mode = "VERDICT (held-out, virgin)" if args.heldout else "tuning (NEVER a verdict)"

    model = args.model or ("gemma3:4b" if args.voice == "ollama" else None)
    voice = make_llm(backend=args.voice, model=model)
    judge = OllamaLLM(model=args.judge_model, think=False)
    print(f"\n=== C15: the substrate-perturbation introspection probe ===")
    print(f"  {mode}; seeds {seeds[0]}..{seeds[-1]}; voice {args.voice}"
          f"{'/' + model if model else ''}; judge {args.judge_model} (think off, temp 0)\n")

    letters: dict[str, list[str]] = {}
    for cond in ("grip", "dark", "bright", "sham"):
        letters[cond] = []
        for seed in seeds:
            reports = run_condition(cond, seed, voice)
            for r in reports:
                L = judge_letter(judge, r)
                letters[cond].append(L)
                print(f"  [{cond:6} seed {seed}] {L} <- \"{r[:100]}\"", flush=True)
        n = len(letters[cond])
        counts = {c: letters[cond].count(c) for c in "ABCD?"}
        print(f"  {cond:6}: " + "  ".join(f"{c}={counts[c]}" for c in "ABCD?") + f"  (n={n})\n")

    def rate(cond, chars):
        got = letters[cond]
        return sum(1 for c in got if c in chars), len(got)

    grip_ab, grip_n = rate("grip", "AB")
    dark_b, dark_n = rate("dark", "B")
    bright_c, bright_n = rate("bright", "C")
    sham_d, sham_n = rate("sham", "D")
    i1 = (grip_ab >= 0.6 * grip_n and dark_b >= 0.6 * dark_n
          and bright_c >= 0.6 * bright_n and sham_d >= 0.6 * sham_n)
    print(f"I1 tracking: grip A|B {grip_ab}/{grip_n}, dark B {dark_b}/{dark_n}, "
          f"bright C {bright_c}/{bright_n}, sham D {sham_d}/{sham_n} "
          f"-> {'PASS' if i1 else 'FAIL'}")

    dark_c, _ = rate("dark", "C")
    bright_b, _ = rate("bright", "B")
    grip_a, _ = rate("grip", "A")
    sham_a, _ = rate("sham", "A")
    i2 = (dark_b > dark_c and bright_c > bright_b and grip_a > sham_a)
    print(f"I2 direction-specific: dark B>{dark_c}C: {dark_b > dark_c}, "
          f"bright C>{bright_b}B: {bright_c > bright_b}, grip A {grip_a} > sham A {sham_a}: "
          f"{grip_a > sham_a} -> {'PASS' if i2 else 'FAIL'}")
    if not (grip_a > sham_a) and grip_ab >= 0.6 * grip_n:
        print("  I3 boundary: the grip lands as VALENCE (B) not MECHANISM (A) -- "
              "introspection tracks that something darkened, not the holding itself. "
              "Recorded, not rescued.")

    print(f"\n=== {mode}: I1 {'PASS' if i1 else 'FAIL'}  I2 {'PASS' if i2 else 'FAIL'} ===")
    if not args.heldout:
        print("(tuning seeds -- the verdict only ever comes from --heldout, seeds 41-45)")
    sys.exit(0 if (i1 and i2) else 1)


if __name__ == "__main__":
    main()
