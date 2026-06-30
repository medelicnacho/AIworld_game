"""A from-scratch character-level GPT (nanoGPT-style), in PyTorch.

The real architecture -- a Transformer -- written small enough to train on a CPU and to read in
one sitting, but identical in shape to the big ones. This is the homegrown "brain": train it on
the world's own words, and it learns to speak in that voice. Unlike the numpy char-RNN, a
Transformer holds context, so with enough training it produces genuinely novel, coherent text.

  python homegrown/gpt.py train --corpus homegrown/corpus_train.txt --steps 5000
  python homegrown/gpt.py sample --prompt "I am "

CPU now (slow, small); the SAME code flies on a GPU (just raise the sizes at the top). Saves
homegrown/gpt.pt -- the trained brain.
"""
from __future__ import annotations

import argparse
import math
import os
import time

import torch
import torch.nn as nn
from torch.nn import functional as F

HERE = os.path.dirname(__file__)
CKPT = os.path.join(HERE, "gpt.pt")

# --- size knobs. Small for CPU; raise these (and batch/block) on a GPU for a real model. ---
BLOCK = 64        # context window (how many chars it looks back on)
N_EMBD = 128      # width
N_HEAD = 4        # attention heads
N_LAYER = 4       # depth
DROPOUT = 0.1


class Block(nn.Module):
    """One Transformer block: masked self-attention + a little MLP, each with a residual."""

    def __init__(self, n_embd, n_head):
        super().__init__()
        self.ln1 = nn.LayerNorm(n_embd)
        self.attn = nn.MultiheadAttention(n_embd, n_head, dropout=DROPOUT, batch_first=True)
        self.ln2 = nn.LayerNorm(n_embd)
        self.mlp = nn.Sequential(nn.Linear(n_embd, 4 * n_embd), nn.GELU(),
                                 nn.Linear(4 * n_embd, n_embd), nn.Dropout(DROPOUT))

    def forward(self, x, mask):
        h = self.ln1(x)
        a, _ = self.attn(h, h, h, attn_mask=mask, need_weights=False)
        x = x + a
        x = x + self.mlp(self.ln2(x))
        return x


class GPT(nn.Module):
    def __init__(self, vocab, block=BLOCK, n_embd=N_EMBD, n_head=N_HEAD, n_layer=N_LAYER):
        super().__init__()
        self.block = block
        self.tok = nn.Embedding(vocab, n_embd)
        self.pos = nn.Embedding(block, n_embd)
        self.drop = nn.Dropout(DROPOUT)
        self.blocks = nn.ModuleList([Block(n_embd, n_head) for _ in range(n_layer)])
        self.lnf = nn.LayerNorm(n_embd)
        self.head = nn.Linear(n_embd, vocab, bias=False)
        self.head.weight = self.tok.weight   # weight tying
        self.apply(self._init)

    def _init(self, m):
        if isinstance(m, (nn.Linear, nn.Embedding)):
            nn.init.normal_(m.weight, mean=0.0, std=0.02)
            if isinstance(m, nn.Linear) and m.bias is not None:
                nn.init.zeros_(m.bias)

    def forward(self, idx, targets=None):
        B, T = idx.shape
        x = self.drop(self.tok(idx) + self.pos(torch.arange(T, device=idx.device)))
        mask = torch.triu(torch.full((T, T), float("-inf"), device=idx.device), diagonal=1)
        for blk in self.blocks:
            x = blk(x, mask)
        logits = self.head(self.lnf(x))
        if targets is None:
            return logits, None
        loss = F.cross_entropy(logits.view(-1, logits.size(-1)), targets.view(-1))
        return logits, loss

    @torch.no_grad()
    def generate(self, idx, n, temp=0.8, top_k=40):
        for _ in range(n):
            logits, _ = self(idx[:, -self.block:])
            logits = logits[:, -1, :] / max(temp, 1e-4)
            if top_k:
                v, _ = torch.topk(logits, min(top_k, logits.size(-1)))
                logits[logits < v[:, [-1]]] = float("-inf")
            probs = F.softmax(logits, dim=-1)
            idx = torch.cat([idx, torch.multinomial(probs, 1)], dim=1)
        return idx


def _load_corpus(path):
    data = open(path, encoding="utf-8").read()
    chars = sorted(set(data))
    stoi = {c: i for i, c in enumerate(chars)}
    itos = {i: c for i, c in enumerate(chars)}
    ids = torch.tensor([stoi[c] for c in data], dtype=torch.long)
    return data, chars, stoi, itos, ids


def train(args):
    torch.manual_seed(1)
    resume = getattr(args, "resume", False) and os.path.isfile(CKPT)
    if resume:   # CONTINUE the existing brain -- this is consolidation (CONTINUAL.md), not a restart
        ck = torch.load(CKPT, map_location="cpu", weights_only=False)
        chars = ck["chars"]; cfg = ck["config"]; block = cfg["block"]
        stoi = {c: i for i, c in enumerate(chars)}; itos = {i: c for i, c in enumerate(chars)}
        data = "".join(ch for ch in open(args.corpus, encoding="utf-8").read() if ch in stoi)  # known vocab
        ids = torch.tensor([stoi[ch] for ch in data], dtype=torch.long)
        model = GPT(len(chars), cfg["block"], cfg["n_embd"], cfg["n_head"], cfg["n_layer"])
        model.load_state_dict(ck["model"])
        print(f"RESUMED from {CKPT} — continuing on {len(data)} chars (vocab {len(chars)})")
    else:
        data, chars, stoi, itos, ids = _load_corpus(args.corpus)
        block = BLOCK; cfg = dict(block=BLOCK, n_embd=N_EMBD, n_head=N_HEAD, n_layer=N_LAYER)
        model = GPT(len(chars))
        print(f"corpus {len(data)} chars, vocab {len(chars)}")
    n_params = sum(p.numel() for p in model.parameters())
    print(f"GPT: {n_params/1e6:.2f}M params, ctx {block}, on CPU ({torch.get_num_threads()} threads)")
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.1, betas=(0.9, 0.95))

    def batch():
        ix = torch.randint(len(ids) - block - 1, (args.batch,))
        x = torch.stack([ids[i:i + block] for i in ix])
        y = torch.stack([ids[i + 1:i + block + 1] for i in ix])
        return x, y

    model.train()
    t0 = time.time()
    for step in range(1, args.steps + 1):
        x, y = batch()
        _, loss = model(x, y)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        if step % args.report == 0 or step == 1:
            model.eval()
            seed = torch.tensor([[stoi.get("\n", 0)]], dtype=torch.long)
            out = "".join(itos[i] for i in model.generate(seed, 160, temp=0.8)[0].tolist()).replace("\n", " / ")
            print(f"\n[step {step:>6}/{args.steps}  loss {loss.item():.3f}  {time.time()-t0:.0f}s]\n  > {out}")
            tmp = CKPT + ".tmp"
            torch.save({"model": model.state_dict(), "chars": "".join(chars), "config": cfg}, tmp)
            os.replace(tmp, CKPT)   # atomic -- a reader (the homegrown backend) never sees a half-write
            model.train()
    print(f"\nsaved -> {CKPT}")


def sample(args):
    ck = torch.load(CKPT, map_location="cpu", weights_only=False)
    chars = ck["chars"]; stoi = {c: i for i, c in enumerate(chars)}; itos = {i: c for i, c in enumerate(chars)}
    c = ck["config"]
    model = GPT(len(chars), c["block"], c["n_embd"], c["n_head"], c["n_layer"])
    model.load_state_dict(ck["model"]); model.eval()
    idx = torch.tensor([[stoi.get(ch, 0) for ch in (args.prompt or "\n")]], dtype=torch.long)
    out = "".join(itos[i] for i in model.generate(idx, args.n, temp=args.temp)[0].tolist())
    print(out)


class GPTVoice:
    """A trained gpt.pt loaded for inference -- the homegrown brain as a speakable voice. Same
    generate(prompt, n, temp) shape as the numpy CharRNN, so the homegrown backend can use either."""

    def __init__(self, path: str = CKPT) -> None:
        ck = torch.load(path, map_location="cpu", weights_only=False)
        self.chars = ck["chars"]
        self.stoi = {c: i for i, c in enumerate(self.chars)}
        self.itos = {i: c for i, c in enumerate(self.chars)}
        c = ck["config"]
        self.model = GPT(len(self.chars), c["block"], c["n_embd"], c["n_head"], c["n_layer"])
        self.model.load_state_dict(ck["model"])
        self.model.eval()

    @staticmethod
    def available(path: str = CKPT) -> bool:
        return os.path.isfile(path)

    @torch.no_grad()
    def generate(self, prompt: str = "", n: int = 160, temp: float = 0.8) -> str:
        ctx = prompt or "\n"
        idx = torch.tensor([[self.stoi.get(ch, 0) for ch in ctx]], dtype=torch.long)
        start = idx.size(1)
        out = self.model.generate(idx, n, temp=temp)[0].tolist()[start:]   # the continuation only
        text = "".join(self.itos[i] for i in out)
        return text.split("\n", 1)[0]   # a single line


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("train")
    t.add_argument("--corpus", default=os.path.join(HERE, "corpus_train.txt"))
    t.add_argument("--steps", type=int, default=5000)
    t.add_argument("--batch", type=int, default=16)
    t.add_argument("--lr", type=float, default=3e-4)
    t.add_argument("--report", type=int, default=500)
    t.add_argument("--resume", action="store_true",
                   help="CONTINUE the existing gpt.pt instead of starting fresh (for consolidation)")
    s = sub.add_parser("sample")
    s.add_argument("--prompt", default="")
    s.add_argument("--n", type=int, default=300)
    s.add_argument("--temp", type=float, default=0.8)
    args = p.parse_args()
    (train if args.cmd == "train" else sample)(args)


if __name__ == "__main__":
    main()
