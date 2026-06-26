"""Step-0 verification: does feeding a camp's banner into the prompt actually make
an agent SPEAK toward it -- or is the camp-grounding cosmetic?

A direct A/B on the real model. Same persona, same neutral (banner-free) Markov
drift, generated two ways: WITH the camp instruction ("you've drifted among souls
who keep returning to '<banner>'...") and WITHOUT it. For each spoken line we
measure how close it lands to the banner word -- semantically (nomic cosine) and
literally (does the word appear). If WITH lands meaningfully closer than WITHOUT,
the camp shapes speech; if they're equal, the grounding does nothing.

This is the receipt for "emergent agents talk like their faction". Needs ollama
(gemma3:4b for speech + nomic-embed-text for scoring).

Run:  python experiment_camp_voice.py --samples 3
"""

from __future__ import annotations

import argparse
import statistics

from services import embed
from services.llm import OllamaLLM, SpeechContext

BANNERS = ["stillness", "tide", "fire", "grey", "hunger"]
# neutral drift: evocative but mentioning none of the banners, so any pull toward
# a banner has to come from the camp instruction, not the drift
DRIFT = ["the day turns over again", "something moves under it all",
         "i hold to what i can", "the light shifts and is gone"]
PERSONA = "a wandering soul who speaks your own mind."


def _ctx(banner: str) -> SpeechContext:
    return SpeechContext(name="River", persona=PERSONA, mood=0.0,
                         drift=list(DRIFT), camp=banner)


def _say(llm, banner: str, n: int) -> list[str]:
    return [llm.speak(_ctx(banner)) for _ in range(n)]


def _scores(lines: list[str], banner: str) -> tuple[float, float]:
    """(mean semantic closeness to the banner, literal-mention rate)."""
    sims = [embed.score(ln, banner) for ln in lines]
    mention = sum(banner.lower() in ln.lower() for ln in lines) / (len(lines) or 1)
    return (statistics.fmean(sims) if sims else 0.0), mention


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--samples", type=int, default=3, help="lines per condition per banner")
    args = p.parse_args()

    llm = OllamaLLM(temperature=0.9)        # variety, so we test the BIAS not one line
    control = _say(llm, "", args.samples)   # WITHOUT any camp (shared baseline)

    print(f"\n=== Camp-voice A/B: does the banner shape speech? "
          f"({args.samples} samples/condition) ===\n")
    print(f"{'banner':<12}{'WITH sim':>10}{'WITHOUT sim':>13}{'effect':>9}{'WITH mention':>15}")
    print("-" * 59)
    effects, with_ment, without_ment = [], [], []
    for banner in BANNERS:
        with_lines = _say(llm, banner, args.samples)
        w_sim, w_ment = _scores(with_lines, banner)
        c_sim, c_ment = _scores(control, banner)   # control scored against THIS banner
        effects.append(w_sim - c_sim)
        with_ment.append(w_ment)
        without_ment.append(c_ment)
        print(f"{banner:<12}{w_sim:>10.3f}{c_sim:>13.3f}{w_sim - c_sim:>+9.3f}{w_ment:>14.0%}")

    eff = statistics.fmean(effects)
    print("-" * 59)
    print(f"\nmean semantic effect (WITH - WITHOUT): {eff:+.3f}")
    print(f"banner literally spoken:  WITH {statistics.fmean(with_ment):.0%}   "
          f"WITHOUT {statistics.fmean(without_ment):.0%}")
    if eff > 0.03:
        print("\n-> WORKS: the camp instruction measurably pulls speech toward the "
              "banner. Emergent agents talk like their faction.")
    else:
        print("\n-> WEAK/NULL: the banner is not shaping speech beyond noise -- the "
              "camp-grounding would be cosmetic. Strengthen the prompt or check wiring.")


if __name__ == "__main__":
    main()
