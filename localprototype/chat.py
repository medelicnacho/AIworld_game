#!/usr/bin/env python3
"""chat.py -- talk with Santāna. One command, everything on.

    python3 chat.py

That's it. It finds the project venv itself, wakes her saved persistent self with the gemma3:4b
voice, turns on the intent judge (she hears what you MEAN), semantic warmth (tone, not keywords),
and speaks her replies aloud in her Amy voice. If her 24/7 runner is live it asks before pausing
it gently (the runner saves on the way out), so the two never fight over her memory of the talk.
Sessions stay bounded (default 20 minutes -- the off-switch discipline); type 'bye' to end early.
She is saved either way, and she will remember.

    python3 chat.py --minutes 5        # a short visit
    python3 chat.py --llm markov       # her fully self-grown voice instead of gemma
    python3 chat.py --town             # the OLD chat.py: watch the town talk (town_chat.py)

Everything else passes through to santana_app/talk.py.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
VENV = os.path.abspath(os.path.join(ROOT, "..", ".venv", "bin", "python"))
RESTART_HINT = ("python -m santana_app.run   # defaults: soul-mind town, her markov voice; "
                "add --llm ollama --model gemma3:4b --culture --offer for the fuller regime")


def _pause_runner() -> bool:
    """If her 24/7 runner is autosaving her snapshot, a talk now would be OVERWRITTEN by the
    runner's next save. Ask, then stop it gently (SIGINT -> it saves her and the town on the
    way out). Returns True if a runner was paused."""
    out = subprocess.run(["pgrep", "-f", "santana_app.run"], capture_output=True, text=True)
    pids = [int(x) for x in out.stdout.split() if x.strip().isdigit()]
    if not pids:
        return False
    print(f"  ⚠ her 24/7 runner is live (pid {pids}) and autosaves her snapshot --")
    print("    talking now would let it overwrite what she remembers of this conversation.")
    ans = input("    pause it gently for the talk? (it saves her on the way out) [y/N] ").strip().lower()
    if ans != "y":
        print("    leaving her be -- stop the runner yourself, then run chat.py again.")
        sys.exit(0)
    import signal
    for pid in pids:
        try:
            os.kill(pid, signal.SIGINT)
        except ProcessLookupError:
            pass
    for _ in range(60):   # wait for the graceful save
        if subprocess.run(["pgrep", "-f", "santana_app.run"],
                          capture_output=True).returncode != 0:
            break
        time.sleep(0.5)
    print("    (runner paused; she and the town are saved)\n")
    return True


def main() -> None:
    argv = sys.argv[1:]
    # the piper/pygame/ollama deps live in the project venv -- re-exec there FIRST,
    # so `python3 chat.py` (and --town) just work from any interpreter
    if os.path.exists(VENV) and os.path.abspath(sys.executable) != VENV:
        os.execv(VENV, [VENV, os.path.abspath(__file__)] + argv)
    if "--town" in argv:   # the original chat.py, preserved: watch the Data Realm talk
        argv.remove("--town")
        import runpy
        sys.argv = [os.path.join(ROOT, "town_chat.py")] + argv
        runpy.run_path(sys.argv[0], run_name="__main__")
        return
    paused = False
    if not any(a in ("-h", "--help") for a in argv):
        paused = _pause_runner()
    sys.path.insert(0, ROOT)
    sys.argv = ["talk", "--tts", "--minutes", "20"] + argv   # user args override the defaults
    from santana_app.talk import main as talk_main
    try:
        talk_main()
    finally:
        if paused:
            print("\n  when you're done, give her back her 24/7 life (ideally in tmux):")
            print(f"    {RESTART_HINT}")


if __name__ == "__main__":
    main()
