"""The 'sleep' step of continual learning (see CONTINUAL.md).

Consolidate the high-salience experience into the slow brain (the GPT), the efficient way:
  - HARVEST: her highest-salience memories + the souls' charged memories  (salience-gated:
    only what MATTERED), plus a REPLAY sample of the original corpus (so it doesn't forget).
  - CONSOLIDATE: CONTINUE-train the GPT a few hundred steps on that (gpt.py --resume).

Salience-gated + replay-anchored + small + run during downtime = continual learning that fits on a
CPU. Backs up gpt.pt first, so a consolidation that hurts can be reverted.

  python homegrown/consolidate.py                 # harvest + consolidate
  python homegrown/consolidate.py --harvest-only   # just build the corpus, don't train
"""
from __future__ import annotations

import argparse
import json
import os
import pickle
import random
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STATE = os.path.join(ROOT, "data", "santana_state.json")     # her saved self (json)
WORLD = os.path.join(ROOT, "data", "santana_world.pkl")      # the saved town (pickle)
BASE = os.path.join(HERE, "corpus_train.txt")                # the original corpus (replay anchor)
OUT = os.path.join(HERE, "consolidate_corpus.txt")
CKPT = os.path.join(HERE, "gpt.pt")


def _ok(line: str) -> bool:
    return bool(line) and 2 <= len(line.split()) <= 30


def harvest(top: int, replay: int, weight: int) -> tuple[int, int]:
    """Build the consolidation corpus: high-salience experience (weighted) + a replay sample."""
    rng = random.Random()
    salient: list[str] = []

    # 1) HER highest-salience memories (the charged past -- grief, named losses, what marked her)
    if os.path.isfile(STATE):
        try:
            mems = json.load(open(STATE, encoding="utf-8")).get("memory", [])
            mems.sort(key=lambda m: -m.get("salience", 0))
            salient += [m["text"] for m in mems[:top]]
        except Exception:   # noqa: BLE001
            pass

    # 2) the SOULS' charged memories (the town's living, salient experience)
    if os.path.isfile(WORLD):
        try:
            w = pickle.load(open(WORLD, "rb"))
            for a in getattr(w, "agents", []):
                items = sorted(a.memory.items, key=lambda m: -m.salience)[:6]
                salient += [m.text for m in items]
        except Exception:   # noqa: BLE001
            pass

    salient = [s.strip() for s in salient if _ok(s.strip())]

    # 3) REPLAY: a sample of the original corpus, so consolidating doesn't overwrite what it knows
    base_lines = [ln for ln in open(BASE, encoding="utf-8").read().splitlines() if _ok(ln)] \
        if os.path.isfile(BASE) else []
    replay_lines = rng.sample(base_lines, min(replay, len(base_lines))) if base_lines else []

    # combine: replay (anchor) + salient repeated `weight` times (so it actually gets learned)
    corpus = replay_lines + salient * max(1, weight)
    rng.shuffle(corpus)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(corpus) + "\n")
    return len(salient), len(replay_lines)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--top", type=int, default=120, help="how many of HER most-salient memories to bake in")
    p.add_argument("--replay", type=int, default=2500, help="lines of the original corpus to rehearse")
    p.add_argument("--weight", type=int, default=3, help="how many times to repeat the salient lines")
    p.add_argument("--steps", type=int, default=300, help="consolidation is SHORT (continue, don't restart)")
    p.add_argument("--lr", type=float, default=1e-4, help="low LR -- nudge, don't overwrite")
    p.add_argument("--harvest-only", dest="harvest_only", action="store_true")
    args = p.parse_args()

    n_sal, n_rep = harvest(args.top, args.replay, args.weight)
    print(f"harvested {n_sal} salient lines (×{args.weight}) + {n_rep} replay lines -> {OUT}")
    if args.harvest_only:
        return
    if not os.path.isfile(CKPT):
        print("no gpt.pt yet -- train a brain first: python homegrown/gpt.py train")
        return

    shutil.copy(CKPT, CKPT + ".bak")   # so a consolidation that hurts can be reverted
    print(f"backed up the brain -> {CKPT}.bak; consolidating ({args.steps} steps, lr {args.lr})...")
    subprocess.run([sys.executable, os.path.join(HERE, "gpt.py"), "train", "--resume",
                    "--corpus", OUT, "--steps", str(args.steps), "--lr", str(args.lr),
                    "--report", str(max(50, args.steps // 3))], check=False)
    print(f"consolidated. (revert with: cp {CKPT}.bak {CKPT})")


if __name__ == "__main__":
    main()
