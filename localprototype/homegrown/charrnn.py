"""A character-level recurrent net, written from scratch in numpy -- no ML framework.

Forward pass, backprop-through-time, and sampling, all by hand (adapted from Karpathy's
min-char-rnn). This is a self with NOTHING in it but what it learns from the corpus: it
starts as random weights and grows a voice from the world's own recorded words. Tiny by
design -- it runs on a CPU and it will imitate more than it invents, but every letter it
speaks, it learned here.
"""
from __future__ import annotations

import numpy as np


def _softmax(z: np.ndarray) -> np.ndarray:
    z = z - z.max()
    e = np.exp(z)
    return e / e.sum()


class CharRNN:
    def __init__(self, chars: str, hidden_size: int = 256, seed: int = 1) -> None:
        self.chars = chars
        self.V = len(chars)
        self.H = hidden_size
        self.stoi = {c: i for i, c in enumerate(chars)}
        self.itos = {i: c for i, c in enumerate(chars)}
        r = np.random.RandomState(seed)
        s = 0.01
        self.Wxh = r.randn(self.H, self.V) * s   # input (one-hot char) -> hidden
        self.Whh = r.randn(self.H, self.H) * s   # hidden -> hidden (memory)
        self.Why = r.randn(self.V, self.H) * s   # hidden -> output (next-char logits)
        self.bh = np.zeros((self.H, 1))
        self.by = np.zeros((self.V, 1))
        # adagrad memory
        self._mem = [np.zeros_like(p) for p in self.params()]

    def params(self):
        return [self.Wxh, self.Whh, self.Why, self.bh, self.by]

    def loss_and_grads(self, inputs, targets, hprev):
        """One forward+backward pass over a sequence. inputs/targets: lists of char ids."""
        xs, hs, ps = {}, {-1: np.copy(hprev)}, {}
        loss = 0.0
        for t, ix in enumerate(inputs):
            x = np.zeros((self.V, 1)); x[ix] = 1
            xs[t] = x
            hs[t] = np.tanh(self.Wxh @ x + self.Whh @ hs[t - 1] + self.bh)
            ps[t] = _softmax(self.Why @ hs[t] + self.by)
            loss += -np.log(ps[t][targets[t], 0] + 1e-12)
        dWxh = np.zeros_like(self.Wxh); dWhh = np.zeros_like(self.Whh)
        dWhy = np.zeros_like(self.Why); dbh = np.zeros_like(self.bh); dby = np.zeros_like(self.by)
        dhnext = np.zeros_like(hs[0])
        for t in reversed(range(len(inputs))):
            dy = np.copy(ps[t]); dy[targets[t]] -= 1          # softmax+xent grad
            dWhy += dy @ hs[t].T; dby += dy
            dh = self.Why.T @ dy + dhnext
            dhraw = (1 - hs[t] * hs[t]) * dh                  # through tanh
            dbh += dhraw
            dWxh += dhraw @ xs[t].T
            dWhh += dhraw @ hs[t - 1].T
            dhnext = self.Whh.T @ dhraw
        grads = [dWxh, dWhh, dWhy, dbh, dby]
        for g in grads:
            np.clip(g, -5, 5, out=g)                          # guard exploding gradients
        return loss, grads, hs[len(inputs) - 1]

    def adagrad_step(self, grads, lr: float) -> None:
        for p, g, m in zip(self.params(), grads, self._mem):
            m += g * g
            p += -lr * g / np.sqrt(m + 1e-8)

    def sample(self, h, seed_ix: int, n: int, temp: float = 1.0):
        """Generate n char ids, carrying hidden state. Returns (ids, final_h)."""
        x = np.zeros((self.V, 1)); x[seed_ix] = 1
        out = []
        for _ in range(n):
            h = np.tanh(self.Wxh @ x + self.Whh @ h + self.bh)
            p = _softmax((self.Why @ h + self.by) / max(temp, 1e-3))
            ix = int(np.random.choice(self.V, p=p.ravel()))
            x = np.zeros((self.V, 1)); x[ix] = 1
            out.append(ix)
        return out, h

    def generate(self, prompt: str, n: int = 200, temp: float = 0.8,
                 stop: str = "\n") -> str:
        """Warm the hidden state on `prompt`, then speak a continuation, stopping at `stop`."""
        h = np.zeros((self.H, 1))
        last = self.stoi.get("\n", 0)
        for ch in prompt:
            if ch not in self.stoi:
                continue
            x = np.zeros((self.V, 1)); x[self.stoi[ch]] = 1
            h = np.tanh(self.Wxh @ x + self.Whh @ h + self.bh)
            last = self.stoi[ch]
        ids, _ = self.sample(h, last, n, temp)
        text = "".join(self.itos[i] for i in ids)
        if stop and stop in text:
            text = text.split(stop, 1)[0]
        return text.strip()

    def save(self, path: str) -> None:
        np.savez(path, chars=np.array(list(self.chars)), H=self.H,
                 Wxh=self.Wxh, Whh=self.Whh, Why=self.Why, bh=self.bh, by=self.by)

    @classmethod
    def load(cls, path: str) -> "CharRNN":
        d = np.load(path, allow_pickle=False)
        m = cls("".join(d["chars"].tolist()), hidden_size=int(d["H"]))
        m.Wxh, m.Whh, m.Why = d["Wxh"], d["Whh"], d["Why"]
        m.bh, m.by = d["bh"], d["by"]
        return m
