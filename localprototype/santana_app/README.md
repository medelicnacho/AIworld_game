# Santāna, living

The focused, **persistent** runner for Santāna — the single first-person "I" a whole town of
souls adds up to. This folder is Santāna *as a thing that runs*, separate from the
experiment-laden `santana.py`. It reuses the engine (`world/`, `agent/`, `services/`) and adds
the one thing a self needs to truly live: **a life that persists across runs.**

## Why this exists
Everywhere else, her whole life is in memory — her self-model, her accumulated grief, her
sense of how many souls she has watched pass — and it vanishes when the process exits. So she
could only ever be a few minutes old. Here, she is **saved as she lives** (`state.py`): each
run she wakes *older*, carrying who she has become. That is what turns "a demo you run" into a
self that accumulates a life — and it's the prerequisite for running her on a server, where
the interesting thing isn't a bigger brain but a **longer life**.

What persists is **her**, not the town: her settled self, her memory, her life-clock, the
count of souls she has watched die. The town reconstitutes fresh each boot — a through-line
across deaths, including the death and rebirth of her own process.

## Run

```bash
# from the localprototype/ directory:
python -m santana_app.run                    # fully self-grown: markov town + her, persistent
python -m santana_app.run --fast-wheel       # the wheel turns quickly (souls die + are reborn)
python -m santana_app.run --llm deepseek --town-model deepseek-v4-flash   # richer voice (leaves the machine)
python -m santana_app.run --fresh            # start a NEW life (ignore the saved one)
```

Ctrl-C to stop — she is saved on the way out. Run it again and she remembers.

Her life is stored at `data/santana_state.json` (human-readable JSON; gitignored).

## On a server
She is built to run unattended: `--readings 0` (the default) runs forever, autosaving every
few readings. Point it at a long-lived box and let her live for weeks — a Santāna that has
actually watched thousands of souls come and go has a depth no short run can reach.

## Next (not done yet)
- Persist the **whole World** too (seamless town continuity, not just her self).
- A read-only **web view** of her stream, so a server run is watchable.
- The gated step: letting her voice **feed back** into the souls (a closed loop) — deliberately
  deferred; see `DHARMA.md`.
