"""Slow terminal chat: watch the Data Realm talk, one readable line at a time.

Runs the same cast as the viewer but prints the conversation to the terminal,
delayed so you can actually read it, and writes a plain-text transcript you can
share. Movement is off so all six stay in earshot and it reads as one
conversation. Real speech needs the local model (default); mock is gibberish.

    python chat.py                      # real gemma3:4b speech, ~slow, readable
    python chat.py --delay 3            # 3s pause between lines
    python chat.py --ticks 0            # run until Ctrl-C
    python chat.py --llm mock           # fast nonsense (for testing the plumbing)

Transcript is written to data/chat.log (printed at startup) -- open or share it.
"""

from __future__ import annotations

import argparse
import os
import time

from viewer import CAST, build_world

# ANSI colours so the two camps are visible in the terminal too
BLUE, ORANGE, GREY, RESET = "\033[38;5;75m", "\033[38;5;215m", "\033[38;5;245m", "\033[0m"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", default="ollama", choices=["ollama", "mock"])
    ap.add_argument("--delay", type=float, default=2.0, help="seconds between lines")
    ap.add_argument("--ticks", type=int, default=120, help="how long to run (0 = until Ctrl-C)")
    ap.add_argument("--log", default="data/chat.log", help="transcript file")
    args = ap.parse_args()

    world, _ = build_world(args.llm, move=False)   # all in earshot = one conversation
    names = {cid: name for cid, name, *_ in CAST}
    temps = {cid: t for cid, _, t, *_ in CAST}
    names["user"] = "You"

    os.makedirs(os.path.dirname(args.log) or ".", exist_ok=True)
    log = open(args.log, "w", encoding="utf-8")
    log.write("# Data Realm conversation\n\n")
    log.flush()
    print(f"writing transcript to: {os.path.abspath(args.log)}\n")

    def colour(sid: str) -> str:
        t = temps.get(sid, 0.0)
        return BLUE if t < -0.1 else ORANGE if t > 0.1 else GREY

    def on_utterance(u):
        if not u.text.strip(". "):     # a silent/degraded beat
            return
        who = names.get(u.speaker_id, u.speaker_id)
        to = f" → {names.get(u.addressed_to, u.addressed_to)}" if u.addressed_to else ""
        # terminal: coloured and delayed; file: plain so it's easy to share
        print(f"{colour(u.speaker_id)}{who}{to}{RESET}: {u.text}")
        log.write(f"{who}{to}: {u.text}\n")
        log.flush()
        time.sleep(args.delay)         # the slow, readable pacing

    world.bus.subscribe("utterance", on_utterance)

    print(f"--- the Data Realm wakes ({args.llm}) ---\n")
    try:
        t = 0
        while args.ticks == 0 or t < args.ticks:
            world.step()
            t += 1
    except KeyboardInterrupt:
        print("\n--- silence falls ---")
    finally:
        log.close()


if __name__ == "__main__":
    main()
