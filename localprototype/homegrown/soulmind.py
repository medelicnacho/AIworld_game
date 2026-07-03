"""SoulMind -- a tiny from-scratch GPT PER SOUL: born blank, grown by sleep, worn by forgetting.

The homegrown gpt.pt is ONE brain for the whole backend. This is the per-NPC version the
samsara design was always pointing at: every soul carries its OWN miniature transformer,
randomly initialized at birth (a newborn BABBLES -- it has not yet learned to speak), and
trained only ever on its OWN corpus: the memories it actually holds right now, the lines it
lately said and heard. Sleep (a short, bounded continuation of training) is when the day is
absorbed.

Forgetting is not simulated -- it is INHERITED from the memory store and the optimizer:
what decays out of memory simply stops appearing in the next sleep's corpus, and continued
training on the new days drifts the weights away from the old ones (catastrophic forgetting,
here doing honest work as the forgetting). A soul is therefore always mid-stream: learning
what it is living, losing what it no longer rehearses. At rebirth the wheel hands on karma,
never weights -- the new soul's mind is a fresh random init that must learn speech again.

Sized for CPU reality: ~0.1M params (block 48, width 64, 2 heads, 2 layers), a fixed shared
charset (so a life of sleeps never breaks the embedding), seconds per sleep. Nothing here
touches the network.
"""
from __future__ import annotations

import os

import torch

from homegrown.gpt import GPT

# politeness: a sleep is a background burst on a CPU that is ALSO running the wheel and
# (often) ollama for her voice -- torch must never grab every core. Two threads keeps a
# sleep in the seconds range without starving anyone.
torch.set_num_threads(min(2, max(1, (os.cpu_count() or 2))))

# The FIXED charset every soul shares -- per-soul corpora are tiny and ever-changing, so the
# vocabulary must not be derived from them (a new character would orphan the embedding
# mid-life). Unknown characters are simply dropped at encode: what cannot be spelled is
# not learned.
CHARSET = ("\n abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
           ".,'!?;:-()\"")
STOI = {c: i for i, c in enumerate(CHARSET)}
ITOS = {i: c for i, c in enumerate(CHARSET)}

# miniature: a soul's brain must sleep in seconds on a CPU that is also running the world
BLOCK, N_EMBD, N_HEAD, N_LAYER = 48, 64, 2, 2
SLEEP_STEPS = 120      # one sleep = this many optimizer steps, bounded by design
SLEEP_BATCH = 8
SLEEP_LR = 1e-3


def available() -> bool:
    return True   # importing this module at all proves torch is present


def _encode(text: str) -> torch.Tensor:
    ids = [STOI[c] for c in text if c in STOI]
    return torch.tensor(ids, dtype=torch.long)


class SoulMind:
    """One soul's private brain: fresh at birth, trained only by its own sleeps."""

    def __init__(self, soul_id: str, seed: int | None = None):
        self.soul_id = soul_id
        self.sleeps = 0
        torch.manual_seed(seed if seed is not None else (hash(soul_id) & 0x7FFFFFFF))
        self.model = GPT(len(CHARSET), BLOCK, N_EMBD, N_HEAD, N_LAYER)
        self.model.eval()

    # --- sleep: the bounded consolidation ------------------------------------------------
    def sleep(self, corpus: str, steps: int = SLEEP_STEPS, batch: int = SLEEP_BATCH,
              lr: float = SLEEP_LR) -> tuple[float, float] | None:
        """Absorb the current corpus (this soul's LIVING memory, nothing else) for a bounded
        number of steps. Returns (first_loss, last_loss), or None if there was too little to
        dream on. Learning and forgetting in one motion: no replay of past corpora."""
        ids = _encode(corpus)
        if ids.numel() < BLOCK + 2:
            return None
        opt = torch.optim.AdamW(self.model.parameters(), lr=lr,
                                weight_decay=0.1, betas=(0.9, 0.95))
        self.model.train()
        first = last = 0.0
        for step in range(steps):
            ix = torch.randint(ids.numel() - BLOCK - 1, (batch,))
            x = torch.stack([ids[i:i + BLOCK] for i in ix])
            y = torch.stack([ids[i + 1:i + BLOCK + 1] for i in ix])
            _, loss = self.model(x, y)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
            opt.step()
            if step == 0:
                first = float(loss.item())
            last = float(loss.item())
        self.model.eval()
        self.sleeps += 1
        return first, last

    # --- speech ---------------------------------------------------------------------------
    @torch.no_grad()
    def line(self, prompt: str = "", n: int = 110, temp: float = 0.9) -> str:
        """One spoken line, continued from the prompt. A newborn (zero sleeps) produces
        near-random babble -- that is not a bug, that is an infant."""
        ctx = (prompt or "\n")[-BLOCK:]
        ids = _encode(ctx)
        if ids.numel() == 0:
            ids = torch.tensor([STOI["\n"]], dtype=torch.long)
        out = self.model.generate(ids.unsqueeze(0), n, temp=temp)[0].tolist()[ids.numel():]
        text = "".join(ITOS[i] for i in out)
        return text.split("\n", 1)[0].strip()

    # --- persistence ----------------------------------------------------------------------
    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        tmp = path + ".tmp"
        torch.save({"model": self.model.state_dict(), "soul_id": self.soul_id,
                    "sleeps": self.sleeps}, tmp)
        os.replace(tmp, path)   # atomic: a reader never sees a half-written brain

    @classmethod
    def load(cls, path: str) -> "SoulMind":
        ck = torch.load(path, map_location="cpu", weights_only=False)
        mind = cls(ck.get("soul_id", "?"), seed=0)
        mind.model.load_state_dict(ck["model"])
        mind.model.eval()
        mind.sleeps = int(ck.get("sleeps", 0))
        return mind
