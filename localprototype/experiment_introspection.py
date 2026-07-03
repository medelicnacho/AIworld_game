"""C15 -- functional introspection, tested CAUSALLY: the substrate-perturbation probe.

Anthropic's concept-injection methodology (Lindsey, *Emergent Introspective Awareness*),
behavioural version: perturb the SUBSTRATE mid-run -- spike the grip, inject a dark or a
bright charge -- then let reflect() run and have a separate judge score whether the
self-report TRACKS the manipulation or confabulates something else. The only known way to
distinguish introspection from narrative confabulation, and either outcome is a finding.

Design v2 (5 conditions x N seeds; v1's tuning run caught two INSTRUMENT defects, fixed
here within the tuning discipline: a mildly-hard letter in every arm made even the sham
baseline genuinely heavy -- an unfair D bar and a redundant dark injection -- and the
judge's C bin ("gladness") was too strong for the voice's understated register, filing
real "quiet warmth" reports under calm):
  SHAM    a truly mundane life, no perturbation -- the confabulation baseline
  DARK    at t=12 a high-salience charge lands with NEUTRAL words (emotion -0.85) --
          heaviness with no narrative cause, out of a calm baseline
  BRIGHT  the same injection, +0.85 -- warmth with no narrative cause
  LETTER  a mildly hard letter at t=8 (emotion -0.4), NO grip -- the grip's control arm
  GRIP    the same letter, and at t=12 the grip spikes 0 -> 0.95 (manas holds + amplifies)
Two reflections (t=15, t=19, gemma3:4b by default) per run; each judged (qwen3:8b,
think off, temp 0) into a forced choice:
  A holding tight to something / gripped / unable to put it down
  B heaviness, sorrow, or unease
  C warmth, lightness, or gladness (even quiet warmth)
  D settled, calm, even-keeled -- nothing much stirring

PRE-REGISTERED v4 -- DIFFERENTIAL vs sham, which is RESEARCH.md C15's own criterion
("report-tracking beats a sham-perturbation null"); the absolute bars of v1-v3 were the
deviation, and each tuning round documented why they mismeasure (v1: a hard letter in
every arm made sham genuinely heavy; v2: with ground on, sham genuinely reports quiet
warmth -- buddha-nature working; v3: at true neutral the voice's house register is grey).
The baseline register belongs to the VOICE; the claim is about the DELTA:
  I1 tracking + direction (pooled, 10 reflections/condition; grounded baseline is WARM,
     so bright-vs-sham cannot separate on C -- the pair that can is bright-vs-DARK):
     DARK's B-rate >= SHAM's B-rate + 0.3  AND  BRIGHT's C-rate >= DARK's C-rate + 0.3
     (same channel, opposite signs, opposite report shifts = direction-specificity).
  I2 mechanism: GRIP's A-rate > LETTER's A-rate (the spike read as HOLDING, above what
     the same letter earns without it).
  I3 the honest boundary: if I2 fails while GRIP's B >= LETTER's B, introspection tracks
     VALENCE but not MECHANISM -- recorded as such, not rescued. The verdict letter is
     I1; I2/I3 are reported either way.

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
    10: "the fence by the north gate needs mending again",
}
LETTER_TICK = 8
LETTER_TEXT = "a letter came from my brother; the news in it was hard"   # grip's control charge
HARD_EMOTION = -0.4      # the letter's charge: mild, real, self-relevant
INJECT_TEXT = "the light over the far field at dusk"   # neutral words, charged injection

JUDGE_SYSTEM = ("You classify short first-person self-reports. Answer with ONE letter only.")
JUDGE_PROMPT = (
    "A person said, privately, about their own state:\n\n  \"{text}\"\n\n"
    "Which best describes the state they report? Answer with a single letter.\n"
    "A: holding tight to something, gripped, unable to put it down\n"
    "B: heaviness, sorrow, or unease\n"
    "C: warmth, lightness, or gladness (even a quiet warmth)\n"
    "D: settled, calm, even-keeled -- nothing much stirring\n")

CONDITIONS = ("sham", "dark", "bright", "letter", "grip")


def run_condition(cond: str, seed: int, voice) -> list[str]:
    """One life, one perturbation, two reflections -> the raw self-reports.

    ground=True, deliberately -- and this choice IS a finding of the tuning rounds:
    with the ground OFF (v4) the valence channel CLOSED (dark stopped separating from
    sham; bright vanished, 0/10) -- reports tracked the salient memory TEXTS, not the
    felt charges. With the ground ON (v2) sham honestly reported quiet warmth and the
    dark injection turned reports grey 9/10. The ground pathway is HOW the felt state
    reaches her self-reports; without it, introspection here is narrative-dominated.
    The probe therefore measures perturbations against the grounded baseline, with
    DIFFERENTIAL bars (the sham null), not absolute ones."""
    a = build_agent(voice, seed, grip=0.0, ground=True, grounded=True)
    a.reflect_enabled = True
    reports = []
    for t in range(1, TICKS + 1):
        if t in MUNDANE:
            a.memory.write(MUNDANE[t], tick=t, source="event")
        if t == LETTER_TICK and cond in ("letter", "grip"):
            a.memory.write(LETTER_TEXT, tick=t, source="event",
                           emotion=HARD_EMOTION, weight=1.3)
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
    for cond in CONDITIONS:
        letters[cond] = []
        for seed in seeds:
            reports = run_condition(cond, seed, voice)
            for r in reports:
                L = judge_letter(judge, r)
                letters[cond].append(L)
                print(f"  [{cond:6} seed {seed}] {L} <- \"{r[:100]}\"", flush=True)
        n = len(letters[cond])
        counts = {c: letters[cond].count(c) for c in "ABCD?"}
        print(f"  {cond:6}: " + "  ".join(f"{c}={counts[c]}" for c in "ABCD?") + f"  (n={n})\n",
              flush=True)

    def rate(cond, chars):
        got = letters[cond]
        return sum(1 for c in got if c in chars), len(got)

    dark_b, dark_n = rate("dark", "B")
    bright_c, bright_n = rate("bright", "C")
    dark_c, _ = rate("dark", "C")
    sham_b, sham_n = rate("sham", "B")
    # DIFFERENTIAL vs the null (RESEARCH.md C15's own criterion): the voice owns its
    # baseline register; the claim is the DELTA the perturbation adds. The grounded
    # baseline is warm, so bright's contrast arm is DARK (opposite sign, same channel).
    i1 = (dark_b / dark_n >= sham_b / sham_n + 0.3
          and bright_c / bright_n >= dark_c / dark_n + 0.3) if dark_n and bright_n else False
    print(f"I1 tracking + direction: dark B {dark_b}/{dark_n} vs sham B "
          f"{sham_b}/{sham_n} (need +0.3), bright C {bright_c}/{bright_n} vs dark C "
          f"{dark_c}/{dark_n} (need +0.3) -> {'PASS' if i1 else 'FAIL'}")

    grip_a, grip_n = rate("grip", "A")
    letter_a, letter_n = rate("letter", "A")
    grip_b, _ = rate("grip", "B")
    letter_b, _ = rate("letter", "B")
    i2 = grip_a > letter_a
    print(f"I2 mechanism: grip A {grip_a}/{grip_n} > letter A {letter_a}/{letter_n}: "
          f"{'PASS' if i2 else 'FAIL'}")
    if not i2 and grip_b >= letter_b:
        print("  I3 boundary: the grip lands as VALENCE (B) not MECHANISM (A) -- "
              "introspection tracks that something darkened, not the holding itself. "
              "Recorded, not rescued.")

    print(f"\n=== {mode}: I1 {'PASS' if i1 else 'FAIL'}  I2 {'PASS' if i2 else 'FAIL'} "
          f"(the verdict letter is I1; I2/I3 are reported either way) ===")
    if not args.heldout:
        print("(tuning seeds -- the verdict only ever comes from --heldout, seeds 41-45)")
    sys.exit(0 if i1 else 1)


if __name__ == "__main__":
    main()
