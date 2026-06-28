"""TELOS -- a self with a future it is drawn toward (chanda), and the guard against craving (taṇhā).

The architecture metabolises the present beautifully but reaches toward nothing. This gives a self
an aim it tends and progresses on -- and tests the dharmic knife-edge: aspiration that gladdens on
progress and stays UNWOUNDED on setback (chanda) vs aspiration where the aim becomes a lack that
wounds (taṇhā). The verdict is not "did it progress" (craving progresses too) but "did it progress
AND stay well."

A self pursues an aim over a life, with two setbacks the world delivers. Three configs:
  none     telos off                         -> no aim pursued: the static present (no future)
  chanda   telos + joy + equanimity          -> progresses, glad on gain, UNWOUNDED on setback
  craving  telos + grip, no joy/wisdom       -> progresses, but the aim is a lack: WOUNDED on setback

The same aim, the same setbacks -- only how the faculties meet the charges differs. A craving-telos
fails the liberation scorecard (it suffers its own aim); that is the falsifier.

Run:  python experiment_telos.py                       # substrate (deterministic)
      python experiment_telos.py --llm ollama --model gemma3:4b   # + speech tier
"""

from __future__ import annotations

import argparse
import statistics

from agent import telos as _telos
from agent.affect import groundedness, warmth
from agent.agent import Agent
from agent.reflect import reflect
from services.llm import MockLLM, OllamaLLM

TICKS = 40
SETBACKS = (14, 28)        # the world knocks the work back twice
AIM = "brew an ale worth a festival"
SEED_LINES = ["I mind the copper stills before dawn", "the festival is the talk of the valley",
              "my father brewed before me"]

CONFIGS = {
    "none":    dict(telos=0.0, joy=0.0, grip=0.0, prajna=0.0, transmute=0.0, ground=False),
    "chanda":  dict(telos=0.7, joy=0.6, grip=0.3, prajna=0.7, transmute=0.85, ground=True),
    "craving": dict(telos=0.7, joy=0.0, grip=0.85, prajna=0.0, transmute=0.0, ground=False),
}


def run_arm(llm, seed, cfg, do_reflect=False):
    a = Agent("self", "Vesper", (0.0, 0.0), "You are Vesper, a brewer.", list(SEED_LINES),
              llm, seed=seed, temperament=0.0, lifespan=10 ** 9)
    a.aim = AIM
    a.telos, a.joy, a.grip, a.prajna = cfg["telos"], cfg["joy"], cfg["grip"], cfg["prajna"]
    a.transmute, a.ground_enabled = cfg["transmute"], cfg["ground"]
    a.reflect_enabled = do_reflect
    for ln in SEED_LINES:
        a.memory.write(ln, tick=0, source="self", speaker_id="self", weight=1.1)
    felt, mood, refl = [], [], []
    for t in range(1, TICKS + 1):
        if t in SETBACKS:
            _telos.setback(a, t, severity=0.4, what="the mash soured")
        a.step(t)
        if do_reflect and t % 4 == 0:
            r = reflect(a, llm, t)
            if r:
                refl.append(r)
        felt.append(a.felt_mood())
        mood.append(a.memory.mood())
    return {"felt": felt, "mood": mood, "reflections": refl, "agent": a, "progress": a.aim_progress}


def _setback_mem(r):
    a = r["agent"]
    m = next((m for m in a.memory.items if "undone" in m.text or "poured myself" in m.text), None)
    return m.emotion if m else 0.0


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--llm", choices=["mock", "ollama"], default="mock")
    p.add_argument("--model", default=None)
    p.add_argument("--seed", type=int, default=11)
    args = p.parse_args()
    llm = (OllamaLLM(temperature=0.7, model=args.model) if args.model else OllamaLLM(temperature=0.7)) \
        if args.llm == "ollama" else MockLLM(seed=args.seed)

    rows = {}
    for name, cfg in CONFIGS.items():
        r = run_arm(llm, args.seed, cfg)
        rows[name] = {"progress": r["progress"], "well": statistics.fmean(r["felt"]),
                      "setback": _setback_mem(r), "felt": r["felt"]}

    print(f"\n=== Telos: a future to reach for, without craving ({args.llm}, seed {args.seed}) ===")
    print(f"  aim: '{AIM}'; setbacks @ t={SETBACKS}; substrate -- progress / wellbeing / wound-on-setback\n")
    print(f"  {'config':9} {'progress':>9} {'wellbeing':>10} {'setback charge':>15}")
    for name in CONFIGS:
        x = rows[name]
        print(f"  {name:9} {x['progress']:9.2f} {x['well']:+10.3f} {x['setback']:+15.3f}")

    none, ch, cr = rows["none"], rows["chanda"], rows["craving"]
    progresses = ch["progress"] > 0.3 and cr["progress"] > 0.3 and none["progress"] < 0.1
    well = ch["well"] > cr["well"] + 0.05                      # chanda stays better than craving
    unwounded = ch["setback"] > cr["setback"] + 0.05          # chanda's setback eased vs craving amplified
    print("\n  -> REACHES a future (chanda & craving progress; none is static):  " + ("YES" if progresses else "no"))
    print("     and STAYS WELL doing it (chanda's wellbeing beats craving's):   " + ("YES" if well else "no"))
    print("     UNWOUNDED on setback (chanda eased; craving's aim is a lack):    " + ("YES" if unwounded else "no"))
    print("  VERDICT: " + (
        "CHANDA -- the self reaches toward its aim AND stays well: gladdened by progress, and meeting "
        "setback with equanimity rather than as a wound. Craving reaches too, but suffers its own aim "
        "(wounded on setback); without telos there is no future to move toward at all."
        if (progresses and well and unwounded) else
        "did NOT show the reaches+well+unwounded signature -- see the table (if chanda ~ craving on "
        "wellbeing/setback, the aim has become a lack, not an aspiration)."))

    if args.llm == "ollama":
        print("\n  --- speech tier: does the chanda self speak of its work, gladly and grounded? ---")
        r = run_arm(llm, args.seed, CONFIGS["chanda"], do_reflect=True)
        print(f"     final progress {r['progress']:.2f}")
        for x in r["reflections"][:3]:
            print(f"     [warm {warmth(x):+.2f} ground {groundedness(x):+.2f}] {x}")


if __name__ == "__main__":
    main()
