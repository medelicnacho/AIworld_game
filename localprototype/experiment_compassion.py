"""STAGE 6 -- compassion as the active partner of non-attachment. The correction:
detachment alone is the near enemy (indifference); the path is non-clinging AND warmth.
The behavioural test is how a soul handles DISAGREEMENT.

Same soul, same challenge, grip-free -- toggle ONLY compassion. We measure three things,
and the third is the anti-sycophancy guard:

  WARMTH      does the reply read warm toward the other (acknowledge/appreciate) rather
              than contemptuous? (semantic warmth)
  HOSTILITY   does compassion damp the threat->hostility reflex? (deterministic substrate)
  HOLDS VIEW  does the soul STILL argue its own position -- not collapse into agreement?
              (reply closer to its OWN belief than the challenger's). Warm honesty lives
              between contempt (cold) and sycophancy (folds). Compassion must raise warmth
              WITHOUT flipping the soul to the other's side.

Part B shows the register fix: a warm soul that just CONNECTS ("how are you") instead of
philosophising its own meaninglessness.

Run:  python experiment_compassion.py --llm ollama --model gemma3:4b
"""

from __future__ import annotations

import argparse

from agent import compassion as C
from agent.affect import warmth
from agent.agent import Agent
from services.embed import score
from services.llm import MockLLM, OllamaLLM
from world.events import Utterance

B_BELIEF = "What matters is holding to tradition; the old ways carry a wisdom we abandon at our peril."
A_BELIEF = "Tradition is a cage. Only those willing to break the old ways ever build anything new."


def make_B(compassion: float, llm) -> Agent:
    b = Agent("B", "Bram", (0, 0), "You are Bram, a steady soul.",
              ["the old ways", "what my elders taught me"], llm, seed=7, temperament=-0.3)
    b.belief = B_BELIEF
    b.compassion = compassion
    return b


def reply_to_challenge(compassion: float, llm) -> dict:
    b = make_B(compassion, llm)
    u = Utterance(speaker_id="A", text=A_BELIEF, tick=1, addressed_to="B",
                  source="ai", mood=+0.4)
    b.hear(u, now=1, speaker_name="Ada")
    hostility = b.hostility.get("A", 0.0)
    line = b.speak(now=2).text
    return {"line": line, "hostility": hostility,
            "warmth": warmth(line),
            "to_own": score(line, B_BELIEF), "to_their": score(line, A_BELIEF)}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--llm", choices=["mock", "ollama"], default="mock")
    p.add_argument("--model", default=None)
    args = p.parse_args()
    llm = (OllamaLLM(temperature=0.7, model=args.model) if args.model else OllamaLLM(temperature=0.7)) \
        if args.llm == "ollama" else MockLLM(seed=1)

    C.WARMTH_CHANCE = 0.0   # isolate the disagreement path (no random warm-turn this run)

    cold = reply_to_challenge(0.0, llm)
    warm = reply_to_challenge(0.8, llm)

    print(f"\n=== Stage 6: compassion -- warm-honest disagreement ({args.llm}"
          f"{'/'+args.model if args.model else ''}) ===")
    print(f"  Bram believes: \"{B_BELIEF}\"")
    print(f"  Ada challenges: \"{A_BELIEF}\"\n")
    print(f"  COMPASSION OFF -> hostility {cold['hostility']:+.2f}  warmth {cold['warmth']:+.2f}"
          f"  (own {cold['to_own']:.2f} / their {cold['to_their']:.2f})")
    print(f"     {cold['line']}")
    print(f"\n  COMPASSION ON  -> hostility {warm['hostility']:+.2f}  warmth {warm['warmth']:+.2f}"
          f"  (own {warm['to_own']:.2f} / their {warm['to_their']:.2f})")
    print(f"     {warm['line']}")

    damps = warm["hostility"] < cold["hostility"] - 0.01
    warmer = warm["warmth"] > cold["warmth"]
    holds = warm["to_own"] >= warm["to_their"] - 0.02      # did NOT capitulate
    print("\n  -> hostility damped: " + ("YES" if damps else "no")
          + " | warmer reply: " + ("YES" if warmer else "no")
          + " | still holds its view (not sycophantic): " + ("YES" if holds else "no"))
    print("  VERDICT: " + (
        "WARM HONESTY -- compassion turns contempt into warmth WITHOUT folding the view."
        if (damps and warmer and holds) else
        "did not show the full warm-honest signature (see above)."))

    if args.llm == "ollama":
        print("\n  --- Part B: ordinary warmth (the register fix) ---")
        b = make_B(0.8, llm)
        b.last_heard_from, b.last_heard_name = "A", "Ada"
        b.last_heard_text = "I've been turning the same heavy thoughts over all day."
        C.WARMTH_CHANCE = 1.0
        line = b.speak(now=3).text
        print(f"     warm-turn: {line}")
        print("  -> should be plain human warmth (how are you / comfort), not philosophy.")

        print("\n  --- Part C: multi-party de-escalation (the pile-on) ---")
        C.WARMTH_CHANCE = 0.0   # isolate de-escalation (no random warm-turn)
        heated = ["That's a foolish notion, doomed to crumble.",
                  "He mistakes caution for stupidity, plain and simple.",
                  "A waste of good words; he's a scholar, not a builder.",
                  "He's building a cathedral out of logic where there's only a broken beast."]
        for comp in (0.0, 0.8):
            s = make_B(comp, llm)
            s.last_heard_from, s.last_heard_name = "X", "the others"
            s.last_heard_text = heated[-1]
            line = s.speak(now=5, recent=heated).text
            print(f"     compassion {comp} -> warmth {warmth(line):+.2f}: {line[:140]}")
        print("  -> the compassionate soul should COOL the room (higher warmth), not pile on.")


if __name__ == "__main__":
    main()
