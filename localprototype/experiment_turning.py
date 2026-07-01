"""Turning-point falsifier: does the load-bearing self-model produce CHAPTER BREAKS -- and only
when the self actually changes?

The claim (agent/expectation.py): a running expectation of one's OWN conduct makes the self-model
causal -- sustained out-of-character action accrues dissonance until the self TURNS: a high-salience
narrative memory ("something in me has turned: I was one who shared...") that enters identity
recall, so change becomes part of the story. This is the digestion §5.12 showed accumulation alone
cannot do: a pile dilutes; only a self with an expectation of itself can register a break.

PRE-REGISTERED (nulls first -- a turning mechanism that fires on noise, or without the faculty,
is decoration):

  1. SENSITIVITY : a sustained conduct flip (60 ticks sharing -> 60 ticks hoarding) turns the
                   self EXACTLY ONCE, and the turning memory sits in identity recall (top-3
                   recall_self) at the end of the life -- the break entered the story.
  2. SPECIFICITY : a stable self with ordinary variation (9 shares : 1 work, 120 ticks) NEVER
                   turns. (Fires-on-noise = decoration.)
  3. MECHANISM   : the identical flip with expect_enabled OFF never turns.
  4. RE-ANCHOR   : after the turning, the self settles into its NEW conduct without turning
                   again (no oscillation) -- one flip, one chapter break.

  A claim passes at >= 4/5 seeds. FAILs get recorded.

  python experiment_turning.py
"""
from __future__ import annotations

from agent.agent import Agent
from services import embed
from services.llm import MockLLM

SEEDS = (11, 12, 13, 14, 15)


def _soul(seed: int, expect: bool = True) -> Agent:
    a = Agent("s", "Soul", (0.0, 0.0), "You are a working soul.", ["the same streets"],
              MockLLM(seed=1), seed=seed, temperament=0.0, lifespan=10 ** 9)
    a.expect_enabled = expect
    return a


def live(a: Agent, actions) -> None:
    for t, act in enumerate(actions, start=1):
        a._last_action = act
        a.step(t)


def run(seed: int) -> dict:
    embed.use_jaccard_only(True)
    flip = _soul(seed)
    live(flip, ["share"] * 60 + ["hoard"] * 60)
    turning_mems = [m for m in flip.memory.items if m.source == "turning"]
    in_identity = any(m.source == "turning" for m in flip.memory.recall_self(k=3))

    stable = _soul(seed)
    live(stable, (["share"] * 9 + ["work"]) * 12)

    off = _soul(seed, expect=False)
    live(off, ["share"] * 60 + ["hoard"] * 60)

    return {"flip_turnings": flip._turnings, "flip_mems": len(turning_mems),
            "in_identity": in_identity, "stable_turnings": stable._turnings,
            "off_turnings": off._turnings,
            "text": turning_mems[0].text if turning_mems else ""}


def main() -> None:
    print(__doc__)
    tallies = {k: 0 for k in ("sensitivity", "specificity", "mechanism", "reanchor")}
    for seed in SEEDS:
        r = run(seed)
        ok = {"sensitivity": r["flip_turnings"] >= 1 and r["in_identity"],
              "specificity": r["stable_turnings"] == 0,
              "mechanism": r["off_turnings"] == 0,
              "reanchor": r["flip_turnings"] == 1}
        for k, v in ok.items():
            tallies[k] += int(v)
        print(f"seed {seed}: flip turned {r['flip_turnings']}x (memory in identity: "
              f"{r['in_identity']}) | stable {r['stable_turnings']}x | off {r['off_turnings']}x")
        if r["text"]:
            print(f"          \"{r['text']}\"")
    n = len(SEEDS)
    print("\n=== VERDICT (pre-registered; a claim passes at >= 4/5 seeds) ===")
    for k, lab in (("sensitivity", "1 SENSITIVITY (flip -> one turning, in identity)"),
                   ("specificity", "2 SPECIFICITY (noise never turns)"),
                   ("mechanism", "3 MECHANISM (off never turns)"),
                   ("reanchor", "4 RE-ANCHOR (exactly once, no oscillation)")):
        print(f"  {lab:47s}: {tallies[k]}/{n} -> {'PASS' if tallies[k] >= 4 else 'FAIL'}")
    print("\nHonest frame: a PASS means identity change is rare, event-shaped, and narrated -- "
          "a functional chapter-break, not anyone home (§7). Whether the VOICE weaves the turning "
          "into its themes needs a real model and is not claimed here.")


if __name__ == "__main__":
    main()
