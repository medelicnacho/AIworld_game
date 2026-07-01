"""Does memory suppress FOREIGN novelty *specifically*, or is it just rarity? -- the clean test.

FINDINGS §5.12 GPT follow-up found the GPT's novelty emission collapses 1.44 -> 0 with memory, but
BADLY CONFOUNDED: (1) novelty markers get rarer, (2) the bigger corpus is under-trained at fixed steps,
(3) char-level exact-match scores garbled near-misses as zero. This experiment kills all three:

  1. PLACEBO CONTROL: plant a set of rare marker words in the ANCHOR (the self's NATIVE, mundane town
     theme), matched in count to the FOREIGN novelty markers. At every memory level both are equally
     rare -> FREQUENCY is controlled. The only difference is native-theme vs foreign-theme context.
  2. WITHIN-MODEL comparison: compare novelty vs placebo INSIDE the same trained model, so both feel
     the same training level -> UNDER-TRAINING is controlled (and we also early-stop toward a target loss).
  3. PROBABILITY metric: teacher-forced mean per-char log-prob of each marker in its context -- how
     probable the model finds it -- NOT exact-match generation. -> the garbling artifact is gone.

The clean question: does the model find FOREIGN novelty LESS probable than an equally-rare NATIVE word?
  ratio = P(novelty) / P(placebo), measured per memory level.

PRE-REGISTERED:
  NULL     : ratio ~= 1 at every memory level -> novelty is treated like any equally-rare native token.
             Then the 1.44->0 collapse was FREQUENCY/training, not digestion; the romantic reading stays
             UNCONFIRMED (memory dominates all non-memory alike -- that is dilution, not novelty-digestion).
  SUPPORT  : ratio < 1 AND falls as memory grows -> foreign material is suppressed MORE than an
             equally-rare native token, increasingly so with memory -> a genuine CONTEXTUAL effect.
  We report whichever. (Discipline: only SUPPORT lets us revive "the self digests novelty".)

  python experiment_continuity_placebo.py
"""
from __future__ import annotations

import argparse
import math
import random as _random
import statistics
import time

import torch

from experiment_continuity import MARKERS as NOV_MARKERS
from experiment_continuity import MEMORY_POOL, NOVELTY
from homegrown.gpt import GPT

# NATIVE placebo markers -- equally-rare invented words, but living in MUNDANE TOWN (anchor) lines,
# i.e. the self's established theme, not the foreign/eerie novelty theme.
PLAC_MARKERS = ["brackmoor", "fenwidow", "stoneraud", "marlgrove", "oxenmire",
                "haywick", "tallowfen", "dunbarrow", "corncrake", "millbrack"]
ANCHOR = [
    "the brackmoor field came in thin this season",
    "a cask of fenwidow ale burst in the cellar overnight",
    "the stoneraud nets have come up empty three days running",
    "the ox went lame out on marlgrove lane at the gate",
    "fever is creeping through the oxenmire houses again",
    "a wedding cloak is owed to the haywick loom",
    "good tallowfen wool is scarce and dear this season",
    "the dunbarrow mill wants dressing and the stone won't bite",
    "there is talk of raiders on the corncrake river road",
    "the millbrack field is cracking and the rains are late",
]


def _assert_clean() -> None:
    assert len(PLAC_MARKERS) == len(NOV_MARKERS), "marker counts must match for frequency control"
    for m, line in zip(PLAC_MARKERS, ANCHOR):
        assert m in line, f"placebo {m} not in its anchor line"
    other = " ".join(MEMORY_POOL + NOVELTY).split()
    assert not (set(PLAC_MARKERS) & set(other)), "placebo leaked into memory/novelty"
    assert not (set(NOV_MARKERS) & set(" ".join(ANCHOR + MEMORY_POOL).split())), "novelty leaked into native"


def _corpus(memory_n: int, seed: int) -> str:
    rng = _random.Random(seed)
    memory = [rng.choice(MEMORY_POOL) for _ in range(memory_n)]
    return "\n".join(ANCHOR + memory + NOVELTY) + "\n"


def train_to_loss(text: str, seed: int, target: float, max_steps: int,
                  block: int = 64, n_embd: int = 64, n_head: int = 4, n_layer: int = 3,
                  batch: int = 32, lr: float = 1e-3):
    torch.manual_seed(seed)
    chars = sorted(set(text))
    stoi = {c: i for i, c in enumerate(chars)}
    ids = torch.tensor([stoi[c] for c in text], dtype=torch.long)
    model = GPT(len(chars), block, n_embd, n_head, n_layer)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.1, betas=(0.9, 0.95))
    model.train()
    recent, loss = [], torch.tensor(0.0)
    step = 0
    for step in range(1, max_steps + 1):
        ix = torch.randint(len(ids) - block - 1, (batch,))
        x = torch.stack([ids[i:i + block] for i in ix])
        y = torch.stack([ids[i + 1:i + block + 1] for i in ix])
        _, loss = model(x, y)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        recent.append(loss.item())
        recent = recent[-50:]
        if step % 100 == 0 and len(recent) == 50 and statistics.mean(recent) < target:
            break
    return model, stoi, loss.item(), step


@torch.no_grad()
def marker_logprob(model, stoi, line: str, marker: str) -> float | None:
    """Teacher-forced mean per-char log-prob of `marker` inside `line` (a '\\n' prefix gives BOS context)."""
    text = "\n" + line
    k = text.find(marker)
    if k < 1:
        return None
    ids = [stoi.get(c, 0) for c in text]
    logits, _ = model(torch.tensor([ids], dtype=torch.long))
    logp = torch.log_softmax(logits[0], dim=-1)      # logp[t] = dist for char t+1 given chars 0..t
    vals = [logp[pos - 1, ids[pos]].item() for pos in range(k, k + len(marker))]
    return sum(vals) / len(vals)


def mean_prob(model, stoi, lines, markers) -> float:
    lps = [marker_logprob(model, stoi, ln, m) for ln, m in zip(lines, markers)]
    lps = [x for x in lps if x is not None]
    return math.exp(statistics.mean(lps))            # geometric-mean per-char probability


def run_condition(memory_n: int, seed: int, target: float, max_steps: int):
    text = _corpus(memory_n, seed)
    model, stoi, loss, steps = train_to_loss(text, seed, target, max_steps)
    p_nov = mean_prob(model, stoi, NOVELTY, NOV_MARKERS)
    p_plac = mean_prob(model, stoi, ANCHOR, PLAC_MARKERS)
    return p_nov, p_plac, loss, steps


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", type=float, default=0.15, help="early-stop loss target (matched training)")
    ap.add_argument("--max-steps", type=int, default=4000)
    ap.add_argument("--seeds", type=int, default=2)
    ap.add_argument("--levels", type=int, nargs="+", default=[0, 30, 180])
    args = ap.parse_args()
    torch.set_num_threads(8)
    _assert_clean()

    print("=" * 84)
    print("CLEAN TEST: does memory suppress FOREIGN novelty MORE than an equally-rare NATIVE word?")
    print("  frequency matched (placebo in anchor); within-model compare; prob metric; train to loss")
    print(f"  {args.seeds} seeds, target loss {args.target}, up to {args.max_steps} steps")
    print("=" * 84)
    print(f"{'memory':>7} | {'P(novel)':>9} | {'P(placebo)':>10} | {'nov/plac':>8} | {'loss':>5} | {'steps':>5}")
    print("-" * 84)

    t0 = time.time()
    rows = []
    for m in args.levels:
        novs, placs, ratios, losses, steps_ = [], [], [], [], []
        for s in range(args.seeds):
            pn, pp, ll, st = run_condition(m, s, args.target, args.max_steps)
            novs.append(pn); placs.append(pp); ratios.append(pn / pp if pp else 0.0)
            losses.append(ll); steps_.append(st)
            print(f"   . m={m} seed={s}: nov={pn:.4f} plac={pp:.4f} ratio={pn / pp if pp else 0:.3f} "
                  f"loss={ll:.3f} steps={st}", flush=True)
        rows.append((m, statistics.mean(novs), statistics.mean(placs),
                     statistics.mean(ratios), statistics.mean(losses), statistics.mean(steps_)))
        print(f"{m:>7} | {statistics.mean(novs):>9.4f} | {statistics.mean(placs):>10.4f} "
              f"| {statistics.mean(ratios):>8.3f} | {statistics.mean(losses):>5.2f} "
              f"| {statistics.mean(steps_):>5.0f}", flush=True)

    print("-" * 84)
    ratios = [r[3] for r in rows]
    near1 = all(abs(r - 1) < 0.25 for r in ratios)
    print(f"RATIO nov/plac by memory: {[f'{r:.2f}' for r in ratios]}")
    if near1:
        print("VERDICT: ~PARITY -> foreign novelty is treated like an equally-rare NATIVE word at every")
        print("  memory level. Memory does NOT specifically suppress the foreign -> the §5.12 GPT collapse")
        print("  was FREQUENCY/training, not digestion. 'The self digests novelty' stays UNCONFIRMED.")
    elif ratios[-1] < ratios[0] and ratios[-1] < 1:
        print("VERDICT: FALLS BELOW PARITY -> foreign novelty is suppressed MORE than an equally-rare")
        print("  native word, and the gap GROWS with memory -> a genuine CONTEXTUAL effect. The claim")
        print("  'a self with memory digests novelty by context' EARNS support (not just dilution).")
    else:
        print("VERDICT: MIXED/OTHER -> see the ratios; no clean support for context-specific suppression.")
    print(f"[{time.time() - t0:.0f}s]")
    print("=" * 84)


if __name__ == "__main__":
    main()
