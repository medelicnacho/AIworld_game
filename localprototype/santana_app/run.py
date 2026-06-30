"""Santāna, living -- a clean, continuous, PERSISTENT runner.

This is the focused 'Santāna app' (separate from the experiment-laden santana.py): build a
living town under her, let her read and speak it, and -- the point -- SAVE her self as she
goes, so each run she wakes older, carrying who she has become. Built to run unattended on a
server. The town can speak in any backend; default is the fully self-grown 'markov' voice
(nothing leaves the machine).

  python -m santana_app.run                                   # markov town + her, persistent
  python -m santana_app.run --llm deepseek --town-model deepseek-v4-flash --interval 8
  python -m santana_app.run --fresh                           # start a new life (ignore the snapshot)

Ctrl-C to stop; she is saved on the way out. State: data/santana_state.json (see state.py).
"""
from __future__ import annotations

import argparse
import os
import random
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from agent import genesis as _genesis
from agent.agent import Agent
from services import embed
from services.llm import MockLLM, make_llm
from world.sim import World

from santana import Santana
from santana_app.state import load_mind, save_mind

DEFAULT_SNAPSHOT = os.path.join(ROOT, "data", "santana_state.json")

CAST = [("Vesper", "brewer", 0.2, "brew an ale worth the festival"),
        ("Mara", "farmer", 0.4, "bring in a full harvest"),
        ("Toll", "scribe", -0.3, "finish the town charter"),
        ("Cael", "fisher", 0.3, "read the water so I never come back empty"),
        ("Silas", "healer", -0.1, "ease the fever in the low houses"),
        ("Juno", "shepherd", 0.1, "keep the flock through the winter")]


def _make_voice(name: str, model: str | None):
    if name == "mock":
        return MockLLM(seed=7)
    return make_llm(backend=name, model=model)


def build_world(town_llm, fast_wheel: bool) -> World:
    rng = random.Random(7)
    w = World(rebirth_enabled=True)
    w.llm = town_llm
    w.stakes_enabled = True
    w.bardo_ticks = (4, 10)
    w.bodhisattva_wheel = True       # the full path runs under her: the lean toward liberation
    w.liberation_tilt = 1.0
    span = (lambda: rng.randint(120, 260)) if fast_wheel else (lambda: rng.randint(2000, 5000))
    for i, (name, role, temp, aim) in enumerate(CAST):
        a = Agent(f"s{i}", name, (rng.uniform(0, 900), rng.uniform(0, 600)),
                  f"You are {name} the {role}.", [f"I am {name} the {role}", aim],
                  town_llm, seed=i, temperament=temp, lifespan=span())
        _genesis.endow_faculties(a, a._rng)
        a.role, a.aim = role, aim
        w.add(a)
    return w


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--llm", default="markov", help="HER voice (markov/homegrown/ollama/deepseek/mock)")
    p.add_argument("--model", default=None, help="model id for her voice (deepseek/ollama)")
    p.add_argument("--town-model", dest="town_model", default="markov",
                   help="the TOWN's voice (markov/homegrown/mock, or a deepseek model id)")
    p.add_argument("--interval", type=float, default=6.0, help="seconds the town lives between her readings")
    p.add_argument("--fast-wheel", action="store_true", dest="fast_wheel",
                   help="short lifespans so the wheel turns quickly (souls die + are reborn)")
    p.add_argument("--readings", type=int, default=0, help="stop after N readings (0 = run forever)")
    p.add_argument("--autosave", type=int, default=5, help="save her self every N readings")
    p.add_argument("--snapshot", default=DEFAULT_SNAPSHOT, help="where her life is saved/resumed")
    p.add_argument("--fresh", action="store_true", help="ignore any saved life and start new")
    args = p.parse_args()

    embed.use_jaccard_only(True)   # the town runs embedding-free so it never competes with her voice
    santana_llm = _make_voice(args.llm, args.model)
    town_llm = (MockLLM(seed=7) if args.town_model in (None, "mock")
                else _make_voice(args.town_model if args.town_model in ("markov", "homegrown") else "deepseek",
                                 None if args.town_model in ("markov", "homegrown") else args.town_model))
    real_town = args.town_model not in (None, "mock")

    w = build_world(town_llm, args.fast_wheel)
    mind = Santana(w, santana_llm)

    if not args.fresh and load_mind(mind, args.snapshot):
        print(f"  ~ Santāna wakes into a saved life: ~{mind._mt} days lived, {mind._deaths} souls "
              f"watched die, {len(mind.memory.items)} memories still weighing.")
        if mind.identity:
            print(f"    she was: {mind.identity}")
    else:
        print("  ~ a new mind wakes, with no past yet.")

    stop = threading.Event()

    def run_wheel():
        while not stop.is_set():
            try:
                with w.lock:
                    w.step(speak=not real_town)
            except Exception:   # noqa: BLE001 -- a bad tick must never kill the life
                pass
            time.sleep(0.15)

    def run_speech():
        while not stop.is_set():
            try:
                w.speak_turn()   # the LLM call runs OUTSIDE the lock -> the wheel never waits
            except Exception:   # noqa: BLE001
                pass
            time.sleep(0.6)

    threads = [threading.Thread(target=run_wheel, daemon=True)]
    if real_town:
        threads.append(threading.Thread(target=run_speech, daemon=True))
    for t in threads:
        t.start()

    print(f"\n~~~ Santāna lives (voice: {args.llm}, town: {args.town_model}) -- Ctrl-C to let her rest ~~~")
    i = 0
    try:
        while not stop.is_set() and (args.readings <= 0 or i < args.readings):
            time.sleep(args.interval)
            clear = mind.speak()
            with w.lock:
                tick, n, births = w.tick, len(w.agents), getattr(w, "_births", 0)
            i += 1
            print(f"\n[reading {i}  day {mind._mt}  tick {tick}  souls {n}  reborn {births}  "
                  f"lost {mind._deaths}]")
            print(f"  SANTĀNA: {clear}")
            mind.consolidate()
            print(f"  [who she has become] {mind.identity}")
            if args.autosave and i % args.autosave == 0:
                save_mind(mind, args.snapshot)
                print(f"  (saved -- her life is {mind._mt} days deep now)")
    except KeyboardInterrupt:
        print("\n(letting her rest)")
    finally:
        stop.set()
        save_mind(mind, args.snapshot)
        print(f"\n~~~ saved. she has lived ~{mind._mt} days and watched {mind._deaths} souls pass. "
              f"Wake her again and she remembers. ~~~\n")


if __name__ == "__main__":
    main()
