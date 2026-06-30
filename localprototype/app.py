#!/usr/bin/env python3
"""Santāna -- the whole thing, in one command.

The spatial god-view town with its ambient music, the souls drifting their markov thoughts in
silence above their heads, and SANTĀNA -- the single collective 'I' they add up to -- reading
the whole town and speaking it ALOUD over all of it.

    python app.py                    # everything together: town + music + her voice
    python app.py --santana-interval 8   # she speaks more often
    python app.py --no-music         # drop the music
    python app.py --llm deepseek --town-model deepseek-v4-flash   # richer souls (leaves the machine)

Press  v  to mute/unmute her voice,  esc  to quit.

(This is viewer.py with --santana always on -- one launcher for the full experience.)
"""
import sys

import viewer

if __name__ == "__main__":
    if "--santana" not in sys.argv:
        sys.argv.append("--santana")   # the collective voice + music + town, all on
    viewer.main()
