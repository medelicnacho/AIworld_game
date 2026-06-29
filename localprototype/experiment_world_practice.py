"""DO LIVE SOULS EARN THE LEAN? -- reflect() wired into the running World.

The live wheel made souls INHERIT the lean (the bardo tilt). But the Path is bhāvanā -- practice, walked
WITHIN a life. Until now live souls never reflected, so cultivate() was inert in the world: the lean was
only ever inherited, never earned. This wires it: World.reflect_turn() lets a soul meet its own mind on
the slow cadence (the model call outside the lock), and step()'s cultivate() then grooves its faculties.

This falsifier ISOLATES the within-life earning from the bardo tilt: NO rebirth, NO tilt -- just souls
living one long life, practising or not. With practice on, the grip should fall (the soul frees itself by
how it meets its mind); with it off, the grip stays put (cultivate has nothing to read).

  practice on    reflect_turn() each cadence -> equanimous reflections -> cultivate grooms grip DOWN
  practice off   no reflection                -> cultivate is inert     -> grip STATIC

Reflections come from MockLLM's canned equanimous lines, but the equanimity that drives cultivate is READ
for real (embeddings) -- so the wiring + the genuine self-regulation read are what's tested here; the
quality of the reflection TEXT is the model's job (validated on ollama in experiment_path). Needs
embeddings up (nomic); without them the equanimity reads 0 and nothing grooves (as everywhere).

Run:  python experiment_world_practice.py
"""

from __future__ import annotations

import argparse
import statistics

from agent.agent import Agent
from services import embed
from services.llm import MockLLM
from world.sim import World

TICKS = 42
REFLECT_EVERY = 3
SEED_LINES = ["I keep the lamps along the eastern road", "the same three streets, most days"]


def run(practice_on: bool, ticks: int = TICKS, seed: int = 1):
    w = World(move_seed=seed)            # no rebirth, no events -- one long life, to isolate within-life practice
    w.llm = MockLLM(seed=seed)
    souls = []
    for i in range(3):
        a = Agent(f"s{i}", f"Soul{i}", (0.0, 0.0), "You are a working soul.",
                  list(SEED_LINES), w.llm, seed=seed + i, temperament=0.0, lifespan=10 ** 9)
        a.grip, a.prajna, a.ground_enabled = 0.70, 0.10, True
        a.reflect_enabled = a.cultivate_enabled = True
        w.add(a)
        souls.append(a)
    grips = []
    for t in range(1, ticks + 1):
        w.step()                          # step() runs cultivate() (cultivate_enabled)
        if practice_on and t % REFLECT_EVERY == 0:
            for _ in souls:               # let each eligible soul practise this cadence (round-robin cursor)
                w.reflect_turn()
        grips.append(statistics.fmean(s.grip for s in w.agents))
    return grips


def _spark(xs):
    blocks = "▁▂▃▄▅▆▇█"
    lo, hi = min(xs), max(xs)
    rng = (hi - lo) or 1.0
    return "".join(blocks[min(7, int((x - lo) / rng * 7.999))] for x in xs)


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()
    if not embed.using_embeddings():
        print("\n[note] embeddings are down (no nomic) -- the equanimity signal reads 0, so nothing will")
        print("       groove. Start `ollama` with nomic-embed-text to see live souls earn the lean.\n")

    practice = run(practice_on=True)
    neglect = run(practice_on=False)

    print("\n=== Do live souls EARN the lean? reflect() wired into the World (no rebirth, no tilt) ===")
    print("  three clinging souls (grip 0.70), one long life; the only difference is whether they practise\n")
    print(f"  practice (reflect_turn on)  grip:  {_spark(practice)}  {practice[0]:.2f} -> {practice[-1]:.2f}")
    print(f"  neglect  (no reflection)    grip:  {neglect[0]:.2f} -> {neglect[-1]:.2f}\n")

    frees = practice[-1] < practice[0] - 0.10
    neglect_static = abs(neglect[-1] - neglect[0]) < 0.05
    earns = neglect[-1] - practice[-1] > 0.10
    print("  -> PRACTICE frees the live soul (grip falls as it meets its mind):  " + ("YES" if frees else "no"))
    print("     NEGLECT leaves it static (cultivate inert without reflection):    " + ("YES" if neglect_static else "no"))
    print("     so the soul EARNS the lean within life, not only inherits it:     " + ("YES" if earns else "no"))
    print("  VERDICT: " + (
        "REFLECT IS WIRED INTO THE LIVE WORLD -- a soul that meets its own mind on the slow cadence grooves "
        "its faculties toward freedom within a single life (grip falls), where a neglectful soul stays put. "
        "Combined with the bardo tilt, the live wheel now both EARNS and inherits the lean -- the Path is "
        "walked, not just handed down."
        if (frees and neglect_static and earns) else
        "did NOT show the earn/static signature -- needs embeddings up (nomic); else tune REFLECT_EVERY/TICKS."))


if __name__ == "__main__":
    main()
