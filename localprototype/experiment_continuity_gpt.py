"""Does the SLOW GPT do more than dilute novelty? -- the follow-up FINDINGS §5.12 asks for.

§5.12 falsified the romantic "continuity digests novelty" reading FOR THE MARKOV: an order-2 chain
subordinates novelty purely by mass (out/in novelty ratio flat ~1.0). But the chain *structurally
cannot* re-contextualise. The GPT has attention + depth -- it COULD suppress novelty non-proportionally
by context. This tests it: the SAME materials as experiment_continuity.py (same anchor / memory pool /
marked novelty), but the voice is a from-scratch GPT (homegrown/gpt.py) trained per condition.

Design (identical logic to the markov test, so the two are directly comparable):
  - hold the marked NOVELTY fixed; vary ONLY the memory mass (0 = blank, up to heavy).
  - train a small GPT on anchor + memory + novelty at each level, several seeds.
  - measure out_frac (marker chars / generated chars) and in_frac (marker chars / training chars).
  - the DIAGNOSTIC is out/in across memory levels:
        FLAT   -> the GPT, like the markov, only DILUTES (romantic reading dead for good).
        FALLS  -> the GPT suppresses novelty BEYOND its mass share -> it does MORE than the chain.
                  (Honest: that could be contextual "digestion" OR just neural nets underweighting
                   rarer tokens -- a further test would separate them. We report the deviation.)

PRE-REGISTERED prediction: the GPT's out/in ratio FALLS with memory (unlike the markov's flat ~1.0);
if it is also flat, the null from §5.12 generalises to the GPT and the romantic reading is fully dead.

  python experiment_continuity_gpt.py                 # ~a few minutes on CPU
  python experiment_continuity_gpt.py --steps 800 --seeds 2   # quicker
"""
from __future__ import annotations

import argparse
import statistics
import time

import torch

from experiment_continuity import ANCHOR, MARKERS, MEMORY_POOL, NOVELTY
from homegrown.gpt import GPT

import random as _random


def _corpus(memory_n: int, seed: int) -> str:
    rng = _random.Random(seed)
    memory = [rng.choice(MEMORY_POOL) for _ in range(memory_n)]
    return "\n".join(ANCHOR + memory + NOVELTY) + "\n"


def marker_char_frac(text: str) -> float:
    if not text:
        return 0.0
    covered = 0
    for m in MARKERS:
        start = 0
        while (k := text.find(m, start)) >= 0:
            covered += len(m)
            start = k + len(m)
    return covered / len(text)


def train_gpt(text: str, seed: int, steps: int, block: int = 64,
              n_embd: int = 64, n_head: int = 4, n_layer: int = 3,
              batch: int = 32, lr: float = 1e-3):
    torch.manual_seed(seed)
    chars = sorted(set(text))
    stoi = {c: i for i, c in enumerate(chars)}
    itos = {i: c for i, c in enumerate(chars)}
    ids = torch.tensor([stoi[c] for c in text], dtype=torch.long)
    model = GPT(len(chars), block, n_embd, n_head, n_layer)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.1, betas=(0.9, 0.95))
    model.train()
    loss = torch.tensor(0.0)
    for _ in range(steps):
        ix = torch.randint(len(ids) - block - 1, (batch,))
        x = torch.stack([ids[i:i + block] for i in ix])
        y = torch.stack([ids[i + 1:i + block + 1] for i in ix])
        _, loss = model(x, y)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
    return model, stoi, itos, loss.item()


@torch.no_grad()
def sample_text(model, stoi, itos, n_chars: int, temp: float = 1.0,
                block: int = 64, n_seq: int = 16) -> str:
    """Generate n_seq sequences IN PARALLEL (n_seq x more text for the same forward passes)."""
    model.eval()
    idx = torch.full((n_seq, 1), stoi.get("\n", 0), dtype=torch.long)
    cols = []
    for _ in range(n_chars):
        logits, _ = model(idx[:, -block:])
        probs = torch.softmax(logits[:, -1, :] / temp, dim=-1)
        nxt = torch.multinomial(probs, 1)           # (n_seq, 1)
        cols.append(nxt)
        idx = torch.cat([idx, nxt], dim=1)
        if idx.size(1) > block + 1:
            idx = idx[:, -(block + 1):]
    mat = torch.cat(cols, dim=1).tolist()            # n_seq x n_chars
    return "\n".join("".join(itos[c] for c in row) for row in mat)


def run_condition(memory_n: int, seed: int, steps: int, n_chars: int):
    text = _corpus(memory_n, seed)
    model, stoi, itos, loss = train_gpt(text, seed, steps)
    gen = sample_text(model, stoi, itos, n_chars, temp=1.0)
    return marker_char_frac(gen), marker_char_frac(text), loss


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--steps", type=int, default=1500, help="train steps per condition")
    ap.add_argument("--seeds", type=int, default=3, help="seeds per memory level")
    ap.add_argument("--chars", type=int, default=10000, help="chars to sample when measuring")
    ap.add_argument("--levels", type=int, nargs="+", default=[0, 30, 180], help="memory-line counts")
    args = ap.parse_args()
    torch.set_num_threads(8)   # P-core sweet spot here; avoids oversubscription overhead

    print("=" * 82)
    print("CONTROLLED TEST (GPT): does the attention-bearing voice do MORE than dilute novelty?")
    print(f"  fixed novelty; only memory varies; from-scratch GPT trained per cell; "
          f"{args.seeds} seeds, {args.steps} steps")
    print("  compare against the MARKOV result (§5.12): out/in was FLAT ~1.0 = pure dilution")
    print("=" * 82)
    print(f"{'memory lines':>12} | {'out_frac':>9} | {'in_frac':>9} | {'out/in':>7} | {'loss':>6}")
    print("-" * 82)

    t0 = time.time()
    rows = []
    for m in args.levels:
        outs, ins, ratios, losses = [], [], [], []
        for s in range(args.seeds):
            c0 = time.time()
            o, i, ll = run_condition(m, s, args.steps, args.chars)
            outs.append(o); ins.append(i); ratios.append(o / i if i else 0.0); losses.append(ll)
            print(f"   . m={m} seed={s}: out={o:.4f} in={i:.4f} "
                  f"ratio={o / i if i else 0:.3f} loss={ll:.3f} ({time.time() - c0:.0f}s)", flush=True)
        rows.append((m, statistics.mean(outs), statistics.mean(ins),
                     statistics.mean(ratios), statistics.mean(losses)))
        print(f"{m:>12} | {statistics.mean(outs):>9.4f} | {statistics.mean(ins):>9.4f} "
              f"| {statistics.mean(ratios):>7.3f} | {statistics.mean(losses):>6.3f}", flush=True)

    print("-" * 82)
    outs = [r[1] for r in rows]
    ratios = [r[3] for r in rows]
    primary = all(outs[i] >= outs[i + 1] for i in range(len(outs) - 1))
    print("DOSE-RESPONSE (output novelty falls as memory grows):", "HELD ✓" if primary else "FAILED ✗")
    print(f"         blank out={outs[0]:.4f}  ->  heavy out={outs[-1]:.4f}")
    drop = ratios[0] - ratios[-1]
    flat = ratios[0] > 0 and abs(drop) < 0.15 * ratios[0]
    print(f"MECHANISM (out/in: blank={ratios[0]:.3f} -> heavy={ratios[-1]:.3f}, drop={drop:+.3f}):")
    if flat:
        print("         ~FLAT -> the GPT ALSO only dilutes. The §5.12 null GENERALISES: even with")
        print("         attention, novelty is subordinated by mass, not context. Romantic reading dead.")
    elif drop > 0:
        print("         FALLS -> the GPT suppresses novelty BEYOND mass, unlike the markov. Continuity")
        print("         does something the chain cannot. (Contextual digestion vs rare-token bias: a")
        print("         further test separates them -- but the GPT is NOT the markov here.)")
    else:
        print("         RISES -> memory makes the GPT emit novelty MORE than proportional (unexpected).")
    print(f"[{time.time() - t0:.0f}s total]")
    print("=" * 82)


if __name__ == "__main__":
    main()
