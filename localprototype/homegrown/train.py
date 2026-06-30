"""Train the from-scratch char-RNN on the harvested corpus. CPU-only, numpy.

  python homegrown/train.py --iters 30000          # ~a couple minutes on CPU
It prints a smoothed loss and a sample every so often, so you can watch a voice form out
of noise, then writes homegrown/model.npz (loaded by the 'homegrown' LLM backend).
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # project root
from homegrown.charrnn import CharRNN

HERE = os.path.dirname(__file__)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--corpus", default=os.path.join(HERE, "corpus.txt"))
    p.add_argument("--out", default=os.path.join(HERE, "model.npz"))
    p.add_argument("--iters", type=int, default=30000)
    p.add_argument("--hidden", type=int, default=256)
    p.add_argument("--seq", type=int, default=25)
    p.add_argument("--lr", type=float, default=0.1)
    p.add_argument("--report", type=int, default=2000)
    args = p.parse_args()

    data = open(args.corpus, encoding="utf-8").read()
    chars = "".join(sorted(set(data)))
    print(f"corpus: {len(data)} chars, vocab {len(chars)}")
    model = CharRNN(chars, hidden_size=args.hidden)
    stoi = model.stoi
    ids = [stoi[c] for c in data]

    smooth = -np.log(1.0 / len(chars)) * args.seq   # loss of a uniform-random model
    hprev = np.zeros((args.hidden, 1))
    p_ptr = 0
    t0 = time.time()
    for it in range(1, args.iters + 1):
        if p_ptr + args.seq + 1 >= len(ids):
            p_ptr = 0
            hprev = np.zeros((args.hidden, 1))   # reset memory at the corpus wrap
        inputs = ids[p_ptr:p_ptr + args.seq]
        targets = ids[p_ptr + 1:p_ptr + args.seq + 1]
        loss, grads, hprev = model.loss_and_grads(inputs, targets, hprev)
        model.adagrad_step(grads, args.lr)
        smooth = smooth * 0.999 + loss * 0.001
        p_ptr += args.seq
        if it % args.report == 0 or it == 1:
            sample = model.generate("I am ", n=160, temp=0.8)
            print(f"\n[iter {it:>6}  loss {smooth/args.seq:.3f}  {time.time()-t0:.0f}s]")
            print(f"  > {sample}")
    model.save(args.out)
    print(f"\nsaved -> {args.out}")


if __name__ == "__main__":
    main()
