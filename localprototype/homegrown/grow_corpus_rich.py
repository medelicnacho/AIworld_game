"""Grow a RICHER, cleaner corpus from the project's own authored substrate -- still NO external
model. The order-1 ThoughtLoop emits choppy fragments; here we gather the clean authored
in-world sentences (each trade's concerns, the genesis themes, the religions' creeds and
scripture) and recombine them with an ORDER-2 word Markov, which reproduces 2-word chunks
verbatim -> fuller, more coherent lines. A char-RNN grown on this learns clean words.

  python homegrown/grow_corpus_rich.py --lines 16000   -> homegrown/corpus_rich.txt
"""
from __future__ import annotations

import argparse
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent.genesis import ROLES, _THEMES
from agent.religion import RELIGIONS

HERE = os.path.dirname(__file__)
START, END = "\x02", "\x03"


def authored_sentences() -> list[str]:
    """Every clean, hand-written in-world line the project already contains."""
    out: list[str] = list(_THEMES)
    for _role, tasks in ROLES:
        out += tasks
    for rel in RELIGIONS.values():
        out.append(rel.creed)
        out += list(rel.scripture)
    return [s.strip() for s in out if s.strip()]


def build(sentences: list[str], order: int):
    """An order-N word chain (context = the last N words). Order-2 reproduces clean 2-word
    chunks (coherent); order-1 recombines more freely (varied, choppier)."""
    trans: dict[tuple[str, ...], list[str]] = {}
    for s in sentences:
        toks = [START] * order + s.split() + [END]
        for i in range(len(toks) - order):
            ctx = tuple(toks[i:i + order])
            trans.setdefault(ctx, []).append(toks[i + order])
    return trans


def walk(trans, order: int, rng, max_words: int = 18) -> str:
    ctx = (START,) * order
    out: list[str] = []
    for _ in range(max_words):
        nxts = trans.get(ctx)
        if not nxts:
            break
        c = rng.choice(nxts)
        if c == END:
            break
        out.append(c)
        ctx = tuple(list(ctx)[1:] + [c])
    return " ".join(out)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", default=os.path.join(HERE, "corpus_rich.txt"))
    p.add_argument("--chars", type=int, default=200000, help="target corpus size in characters")
    args = p.parse_args()

    sents = authored_sentences()
    t2 = build(sents, 2)
    rng = random.Random(7)
    # ORDER-2 ONLY (+ the authored sentences). Order-1 recombination re-introduced choppy word
    # boundaries that a char-RNN learns as garbled non-words; order-2 reproduces clean 2-word chunks,
    # so the text stays low-entropy and the net learns real spelling. Fewer distinct lines, but CLEAN.
    pool: list[str] = []
    seen: set[str] = set()
    tries = 0
    while tries < 80000:
        tries += 1
        line = walk(t2, 2, rng)
        if len(line.split()) >= 3 and line not in seen:
            seen.add(line); pool.append(line)
    pool += [s for s in sents if s not in seen]
    # bulk to the target size by shuffling the pool repeatedly (the net sees clean words often)
    lines: list[str] = []
    size = 0
    while size < args.chars:
        rng.shuffle(pool)
        for ln in pool:
            lines.append(ln); size += len(ln) + 1
            if size >= args.chars:
                break
    text = "\n".join(lines) + "\n"
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"authored base: {len(sents)} sentences -> pool {len(pool)} unique lines, "
          f"corpus {len(text)} chars -> {args.out}")
    print("--- a taste ---")
    for ln in lines[:8]:
        print("  " + ln[:90])


if __name__ == "__main__":
    main()
