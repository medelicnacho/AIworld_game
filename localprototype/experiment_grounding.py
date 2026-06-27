"""Reground genesis: does authoring ORDINARY working people raise the groundedness of
their speech vs the old existential-leaning prompt? Generates souls under the LEGACY
prompt (embedded here) and the NEW genesis prompt, and scores each soul's lines with
affect.groundedness (> 0 = everyday/concrete, < 0 = abstract/existential).

Run:  python experiment_grounding.py --llm ollama --model gemma3:4b
"""

from __future__ import annotations

import argparse
import random
import statistics

from agent import genesis as g
from agent.affect import groundedness
from services.llm import MockLLM, OllamaLLM

# --- the OLD prompt, kept here only to A/B against the regrounded one --------
LEGACY_SYSTEM = ("You invent vivid, distinct PEOPLE -- each a whole soul with its own "
                 "name, history, APPETITES, CONVICTIONS, joys AND wounds. A person with "
                 "opinions and desires, who wants things and believes things -- not just "
                 "a grieving mood. Write in first person. Avoid clichés of rust, gears, "
                 "grey machinery, and do not make every soul defined by loss.")
LEGACY_CONCEPTS = [
    "the sea and what it swallows", "fire, and what it purifies or destroys",
    "growing things, blossom and rot", "hunger and appetite", "memory and forgetting",
    "war and the quiet after the bodies", "love and its small betrayals",
    "the stars and unbearable distance", "stone, weight, and patience",
    "the body and its slow decay", "language, naming, and lies",
    "dreams and the dread of waking", "faith and the silence of any god",
]
LEGACY_PROMPT = (
    "Invent ONE person -- the {role} of a small realm, whose life was also shaped "
    "by: {concept}. Give them a real past AND a working life, not just a mood. "
    "Reply in EXACTLY this format and nothing else:\n"
    "NAME: <a single evocative first name, fitting this person>\n"
    "NATURE: <one number from -1.0 (bleak, heavy) to 1.0 (warm, bright)>\n"
    "SELF:\n"
    "<six to eight FIRST-PERSON lines that make a WHOLE, WORKING person: where I "
    "came from, MY CRAFT as the {role} and what I want from it, a BELIEF or opinion "
    "I hold strongly, what I LOVE, a delight or a grievance. Each line begins with 'I'.>")


def gen_legacy(llm, rng):
    concept = rng.choice(LEGACY_CONCEPTS)
    role, _ = rng.choice(g.ROLES)
    try:
        raw = llm.generate(LEGACY_PROMPT.format(concept=concept, role=role), system=LEGACY_SYSTEM)
    except Exception:  # noqa: BLE001
        raw = ""
    return g.parse_character(raw, rng)


def soul_ground(ch) -> float:
    return statistics.fmean(groundedness(l) for l in ch.lines) if ch.lines else 0.0


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--llm", choices=["mock", "ollama"], default="mock")
    p.add_argument("--model", default=None)
    p.add_argument("--n", type=int, default=4)
    args = p.parse_args()
    llm = (OllamaLLM(temperature=1.0, model=args.model) if args.model else OllamaLLM(temperature=1.0)) \
        if args.llm == "ollama" else MockLLM(seed=1)

    rng = random.Random(20)
    print(f"generating {args.n} OLD-prompt souls and {args.n} NEW-prompt souls...", flush=True)
    old = [gen_legacy(llm, rng) for _ in range(args.n)]
    new = [g.generate_character(llm, rng) for _ in range(args.n)]

    print("\n=== Reground genesis: groundedness of authored souls ===")
    for label, souls in [("OLD (existential-leaning)", old), ("NEW (ordinary life)", new)]:
        gm = statistics.fmean(soul_ground(c) for c in souls)
        print(f"\n  {label}: mean groundedness {gm:+.3f}")
        for c in souls[:2]:
            print(f"    · {c.name} ({soul_ground(c):+.2f}): {c.lines[0][:100] if c.lines else '(none)'}")

    g_old = statistics.fmean(soul_ground(c) for c in old)
    g_new = statistics.fmean(soul_ground(c) for c in new)
    print(f"\n  OLD {g_old:+.3f}  ->  NEW {g_new:+.3f}   (Δ {g_new - g_old:+.3f})")
    print("  -> " + ("GROUNDED: the new prompt authors more everyday, less existential souls."
                    if g_new > g_old + 0.02 else
                    "no clear shift (the base model's pull to profundity is strong; see samples)."))


if __name__ == "__main__":
    main()
