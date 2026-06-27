"""Step-0 verification for the signed stance: does the stance lean fed into the
prompt actually make a soul SPEAK toward its pole -- or is the lean decorative?

The companion to experiment_camp_voice, for stance instead of banner. A stance is
an AXIS (mastery vs surrender, ...), not a single word, so the metric is SIGNED:
for each axis we lean a soul fully toward one pole and measure whether its speech
lands closer to THAT pole than to the opposite one, relative to a lean-free control.

  semantic effect = [sim(line, leant_pole) - sim(line, opposite_pole)]  (WITH - WITHOUT)
  lexical lean    = net pole-words in the intended direction (stance.AXES word-sets)

Same persona, same neutral (pole-free) Markov drift, generated WITH the stance
clause and WITHOUT. If WITH leans measurably toward the intended pole, the stance
is voiced (not decorative) and the grounding loop has something real to bite on.

Needs ollama (gemma3:4b speech + nomic-embed-text scoring).

Run:  python experiment_stance_voice.py --samples 3
"""

from __future__ import annotations

import argparse
import statistics

from agent import stance
from services import embed
from services.llm import OllamaLLM, SpeechContext

# pole-free drift: any pull toward a pole must come from the stance clause, not here
DRIFT = ["the day turns over again", "something moves under it all",
         "i hold to what i can", "the light shifts and is gone"]
PERSONA = "a wandering soul who speaks your own mind."


def _ctx(lean: str) -> SpeechContext:
    return SpeechContext(name="River", persona=PERSONA, mood=0.0,
                         drift=list(DRIFT), stance_lean=lean)


def _lexical_lean(line: str, axis_idx: int, sign: int) -> int:
    """Net pole-words in the intended direction: +1 per intended-pole word, -1 per
    opposite-pole word (sign = +1 if leaning to the positive pole, else -1)."""
    _pos, _neg, pos_words, neg_words = stance.AXES[axis_idx]
    words = set(line.lower().split())
    intended, opposite = (pos_words, neg_words) if sign > 0 else (neg_words, pos_words)
    return len(words & intended) - len(words & opposite)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--samples", type=int, default=3, help="lines per condition per axis")
    args = p.parse_args()

    llm = OllamaLLM(temperature=0.9)          # variety: test the BIAS, not one line
    control = [llm.speak(_ctx("")) for _ in range(args.samples)]   # no stance (baseline)

    print(f"\n=== Stance-voice A/B: does the lean shape speech? "
          f"({args.samples} samples/condition) ===\n")
    print(f"{'axis (leant pole)':<24}{'WITH dir':>10}{'WITHOUT':>10}{'effect':>9}{'lex lean':>10}")
    print("-" * 63)
    effects, lex = [], []
    for i, (pos, neg, _pw, _nw) in enumerate(stance.AXES):
        lean = f"{pos} over {neg}"                 # lean fully to the positive pole
        with_lines = [llm.speak(_ctx(lean)) for _ in range(args.samples)]

        def directional(lines):
            # closeness to the leant pole MINUS closeness to its opposite
            return statistics.fmean(embed.score(ln, pos) - embed.score(ln, neg) for ln in lines)

        w_dir, c_dir = directional(with_lines), directional(control)
        lex_lean = statistics.fmean(_lexical_lean(ln, i, +1) for ln in with_lines)
        effects.append(w_dir - c_dir)
        lex.append(lex_lean)
        print(f"{pos+' over '+neg:<24}{w_dir:>+10.3f}{c_dir:>+10.3f}{w_dir-c_dir:>+9.3f}{lex_lean:>+10.2f}")

    eff = statistics.fmean(effects)
    print("-" * 63)
    print(f"\nmean semantic effect (WITH - WITHOUT, toward leant pole): {eff:+.3f}")
    print(f"mean lexical lean (net intended pole-words/line): {statistics.fmean(lex):+.2f}")
    if eff > 0.02 or statistics.fmean(lex) > 0.1:
        print("\n-> WORKS: the stance lean measurably pulls speech toward its pole. The "
              "signed stance is VOICED, not decorative, and the grounding loop bites.")
    else:
        print("\n-> WEAK/NULL: the lean is not shaping speech beyond noise -- the stance "
              "would be decorative for output. Strengthen the clause or check wiring.")


if __name__ == "__main__":
    main()
