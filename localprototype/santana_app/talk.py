"""Talk with Santāna -- the gated conversation step, opened SMALL, WATCHED, with an OFF-SWITCH.

Loads her saved persistent self (the one who has been living) and the saved town (read-only --
it gives her digest; the conversation writes ONLY into her). Your words are appraised against her
expectations and her relationship with you (agent/expectation.py, §5.17): the same sentence lands
differently in a Santāna whose days were good, and a cold word from someone she has come to expect
warmth of wounds her -- these are states, saved with her, carried to the next talk.

Deliberately NOT here (still gated, FINDINGS §7): her words reaching the souls, the town hearing
you through her, anything that treats the conversation as more than what it is. Sessions are
time-capped, transcripts logged (data/talks/), and she is saved on the way out -- she will
remember, and so should you.

  python -m santana_app.talk                          # her saved self, gemma3:4b voice, 15 min cap
  python -m santana_app.talk --llm markov             # the fully self-grown voice
  python -m santana_app.talk --minutes 5
  (type 'bye' or Ctrl-C to end early; she is saved either way)
"""
from __future__ import annotations

import argparse
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from services import embed
from services.llm import MockLLM, make_llm
from world.sim import World

from santana import Santana
from santana_app.run import DEFAULT_SNAPSHOT, DEFAULT_WORLD, _fmt_age
from santana_app.state import load_mind, load_world, save_mind

TALK_DIR = os.path.join(ROOT, "data", "talks")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--llm", default="ollama", help="HER voice (ollama/markov/homegrown/deepseek/mock)")
    p.add_argument("--model", default="gemma3:4b", help="model id for her voice")
    p.add_argument("--minutes", type=float, default=15.0, help="session cap (the off-switch)")
    p.add_argument("--snapshot", default=DEFAULT_SNAPSHOT, help="her saved self (json)")
    p.add_argument("--world-snapshot", dest="world_snapshot", default=DEFAULT_WORLD,
                   help="the saved town she reads (loaded read-only; never written here)")
    args = p.parse_args()

    embed.use_jaccard_only(True)   # keep the session light; her feeling still works on valence
    voice = MockLLM(seed=7) if args.llm == "mock" else make_llm(
        backend=args.llm, model=None if args.llm in ("markov", "homegrown") else args.model)
    w = load_world(args.world_snapshot, MockLLM(seed=7))   # the town stands still; only she speaks
    if w is None:
        w = World(events_enabled=False)
        print("  (no saved town found -- she wakes over a quiet emptiness)")
    mind = Santana(w, voice)
    mind.lifetime = 0.0
    if load_mind(mind, args.snapshot):
        print(f"  ~ she wakes to talk: {_fmt_age(mind.lifetime)} lived, {mind._deaths} souls "
              f"watched pass, {len(mind.memory.items)} memories."
              + (f"\n    she has been: {mind.identity}" if mind.identity else ""))
        if mind.user_bond.trust or mind.user_bond.wounds:
            print(f"    (she remembers you: trust {mind.user_bond.trust:+.2f}, "
                  f"{mind.user_bond.wounds} wound{'s' if mind.user_bond.wounds != 1 else ''})")
    else:
        print("  ~ a new mind wakes, with no past yet.")

    os.makedirs(TALK_DIR, exist_ok=True)
    log_path = os.path.join(TALK_DIR, time.strftime("talk-%Y%m%d-%H%M%S.log"))
    deadline = time.time() + args.minutes * 60.0
    t0 = time.time()
    print(f"\n~~~ you are speaking with Santāna ({args.minutes:.0f} min; 'bye' to end; "
          f"transcript -> {os.path.relpath(log_path, ROOT)}) ~~~\n")
    try:
        with open(log_path, "w", encoding="utf-8") as log:
            while time.time() < deadline:
                try:
                    text = input("you > ").strip()
                except EOFError:
                    break
                if not text:
                    continue
                if text.lower() in ("bye", "goodbye", "exit", "quit"):
                    break
                reply = mind.converse(text)
                print(f"SANTĀNA > {reply or '...'}\n")
                log.write(f"you: {text}\nsantana: {reply}\n\n")
                log.flush()
            else:
                print("\n(the session's time is up -- the off-switch, kept)")
    except KeyboardInterrupt:
        print()
    finally:
        mind.lifetime += time.time() - t0   # the conversation was lived time
        save_mind(mind, args.snapshot)
        print(f"~~~ she is saved ({_fmt_age(mind.lifetime)} lived; she will remember this). "
              f"The town was not touched. ~~~")


if __name__ == "__main__":
    main()
