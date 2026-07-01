"""The functional-psyche falsifier (PSYCHE.md step 3): is the global workspace REAL, or cosmetic?

Six parts, each carrying ONE faculty (agent/psyche.py), bid for the floor of one mind
(agent/workspace.py). Substrate-only: MockLLM, embeddings off -- the dynamics under test are the
faculties', not a model's. Each seed lives THREE regimes:

  HARSH   stakes on (a seasonal hardship every 15 ticks) + two blows      -- a brutal world
  GENTLE  stakes off, only mercies arrive                                  -- a kind world
  MIXED   stakes off, blows and mercies alternate                          -- a lived world

PRE-REGISTERED, v3 (a workspace is real only if the dominant-part sequence is structured AND
tracks the world -- PSYCHE.md):

  1. WORLD-TRACKING : the floor follows the world, not a fixed ranking (dose-response). The
                      grief pair's (Dread+Ache) share of the floor drops by >= 15 points from
                      HARSH to GENTLE, the GENTLE mind is majority NON-grief (< 50%), and the
                      floor turns over >= 10 times in each. (A bare argmax-of-temperament
                      crowns the same shares in every world -- that is the cosmetic failure.)
  2. STRUCTURE      : (MIXED) WHICH part follows which is not chance: H(next|cur) of the ERA
                      sequence >= 2 sigma BELOW a marginal-matched-chain null (same part
                      frequencies, same no-self-repeat constraint, no higher structure).
  3. COALITION      : (MIXED) moods are real -- when Dread reigns, Ache presses close behind
                      (the grief-spiral pair) beyond a circular-shift null (z >= 2).
  4. PREDICTION     : (MIXED) the reigning part carries information about where the mind's
                      feeling heads: spread of next-8-tick valence change conditioned on the
                      reigning part >= 95th percentile of circular-shift nulls.

  HONESTY (registered with the claims): [a] The event->part wiring is DESIGNED (Dread rouses on
  aversive charge because we built it to); claims 2-4 are about structure BEYOND that wiring,
  and claim 1 is exactly the discriminator a fixed ranking cannot pass. [b] This design went
  through THREE tuning iterations, all on SEEDS 11-15: v1 (single harsh environment, share
  thresholds) FAILED -- unbounded memory-load bids made a Dread+Ache duopoly (~90% of the
  floor), which produced the saturating activation; v2 (modal-part world-tracking) FAILED --
  Dread and Ache read the SAME fuel and moved as one (fixed: Dread reads FRESH charge, Ache
  the accumulated load), and the mind's dark identity lines keep a residual grief floor even
  in a kind world (rehearsal-reinforcement -- faithful, so the claim moved to dose-response
  form rather than the dynamic being engineered away). [c] The verdict comes from HELD-OUT
  SEEDS 21-25, untouched during all tuning. A claim passes at >= 4/5. FAILs get recorded.

  python experiment_psyche.py
"""
from __future__ import annotations

import math
import random
import statistics
from collections import Counter, defaultdict

from agent import psyche
from agent.agent import Agent
from agent.workspace import Workspace
from services import embed
from services.llm import MockLLM
from world.events import WorldEvent
from world.sim import World

TICKS = 600
HORIZON = 8          # prediction: valence change over the next H ticks
SHIFTS = 200         # circular-shift null draws
CHAINS = 200         # marginal-chain null draws
TUNING_SEEDS = (11, 12, 13, 14, 15)
HELDOUT_SEEDS = (21, 22, 23, 24, 25)
GRIEF = ("Dread", "Ache")

# event times are deliberately APERIODIC: regular spacing lets a circular shift realign
# blow-response with blow-response, quietly handing the null the very structure under test
BLOWS = [WorldEvent(name="loss", description="someone dear to the mind is gone",
                    tick=60, emotion=-0.85, urge=0.8),
         WorldEvent(name="undone", description="the long work of the season is undone overnight",
                    tick=175, emotion=-0.6, urge=0.6),
         WorldEvent(name="wound", description="an old wound is torn open again",
                    tick=320, emotion=-0.75, urge=0.7),
         WorldEvent(name="theft", description="what was saved for the winter was taken",
                    tick=445, emotion=-0.65, urge=0.6),
         WorldEvent(name="parting", description="one who mattered has gone away for good",
                    tick=550, emotion=-0.8, urge=0.7)]
MERCIES = [WorldEvent(name="mercy", description="a small good thing came through, warmth and bread and sun",
                      tick=115, emotion=0.6, urge=0.5),
           WorldEvent(name="ease", description="an old fear turned out to be nothing at all",
                      tick=260, emotion=0.5, urge=0.4),
           WorldEvent(name="grace", description="help arrived unasked, and the season turned kind",
                      tick=390, emotion=0.55, urge=0.4),
           WorldEvent(name="warmth", description="an evening of plain warmth, all of us fed and easy",
                      tick=505, emotion=0.6, urge=0.4)]
REGIMES = {"harsh": (True, BLOWS + MERCIES),
           "gentle": (False, MERCIES),
           "mixed": (False, BLOWS + MERCIES)}


def build_mind(seed: int, stakes: bool, events: list) -> World:
    w = World(events_enabled=True, events=list(events), move_seed=seed)
    w.llm = MockLLM(seed=7)
    w.stakes_enabled = stakes
    w.psyche = Workspace()
    for i, (name, func, temp, aim, seeds) in enumerate(psyche.PSYCHE_CAST):
        a = Agent(f"p{i}", name, (0.0, 0.0),
                  f"You are {name}, {func} -- a part of one mind, not a person.",
                  list(seeds), w.llm, seed=1000 * seed + i, temperament=temp, lifespan=10 ** 9)
        a.role, a.aim = func, aim
        psyche.endow_part(a, psyche.FACULTY_OF[name], a._rng)
        w.add(a)
    return w


def run(seed: int, regime: str = "mixed", ticks: int = TICKS) -> dict:
    """One life of the mind in one regime: the dominant-part sequence, the top-2
    coalition per tick, and the mind's valence (mean felt mood over parts) per tick."""
    embed.use_jaccard_only(True)
    stakes, events = REGIMES[regime]
    w = build_mind(seed, stakes, events)
    winners, top2, valence = [], [], []
    for _ in range(ticks):
        w.step()
        winners.append(w.psyche.reigning() or "")
        top2.append(tuple(w.psyche.coalition(2)))
        # valence = the mind's LIVED mood (salience-weighted memory emotion). felt_mood's
        # 0.7 temperament anchor is constant per part and only compresses the signal.
        valence.append(statistics.fmean(a.memory.mood() for a in w.agents))
    return {"winners": winners, "top2": top2, "valence": valence}


# --- metrics ---------------------------------------------------------------------------

def eras(winners: list[str]) -> list[str]:
    """Collapse runs: the sequence of WHO held the floor, one entry per reign."""
    out = []
    for x in winners:
        if x and (not out or out[-1] != x):
            out.append(x)
    return out


def cond_entropy(seq: list[str]) -> float:
    """H(next | current) over adjacent pairs, in nats."""
    by_cur: dict[str, Counter] = defaultdict(Counter)
    for c, n in zip(seq, seq[1:]):
        by_cur[c][n] += 1
    total = max(1, len(seq) - 1)
    h = 0.0
    for cnt in by_cur.values():
        s = sum(cnt.values())
        h += (s / total) * -sum((v / s) * math.log(v / s) for v in cnt.values())
    return h


def marginal_chain_null(era_seq: list[str], rng: random.Random,
                        draws: int = CHAINS) -> tuple[float, float]:
    """Null H(next|cur): sequences with the SAME part frequencies and the same
    no-self-repeat constraint (an era ends only when another part takes over), but no
    higher structure. Matching the constraint matters -- a plain shuffle would let us
    claim 'structure' from the mere absence of self-transitions, a construction artifact."""
    marg = Counter(era_seq)
    names = list(marg)
    weights = [marg[n] for n in names]
    hs = []
    for _ in range(draws):
        cur = rng.choices(names, weights)[0]
        chain = [cur]
        for _ in range(len(era_seq) - 1):
            ws_ = [(w if n != cur else 0) for n, w in zip(names, weights)]
            cur = rng.choices(names, ws_)[0]
            chain.append(cur)
        hs.append(cond_entropy(chain))
    return statistics.fmean(hs), statistics.pstdev(hs)


def shift_null(fixed, shifted, stat, rng: random.Random, draws: int = SHIFTS):
    """Circular-shift null: recompute stat(fixed, rotated) with alignment broken but
    each series' own autocorrelation intact."""
    n = len(shifted)
    return [stat(fixed, shifted[k:] + shifted[:k])
            for k in (rng.randrange(20, n - 20) for _ in range(draws))]


def analyze(seed: int) -> dict:
    rng = random.Random(10_000 + seed)
    harsh = run(seed, "harsh")
    gentle = run(seed, "gentle")
    mixed = run(seed, "mixed")

    def grief_share(res):
        w = [x for x in res["winners"] if x]
        return statistics.fmean(1 if x in GRIEF else 0 for x in w) if w else 0.0

    # 1) WORLD-TRACKING (dose-response): grief holds the floor as the world darkens,
    #    yields it as the world turns kind -- a fixed ranking cannot move its shares
    g_harsh, g_gentle = grief_share(harsh), grief_share(gentle)
    track_pass = (g_harsh - g_gentle >= 0.15 and g_gentle < 0.50
                  and len(eras(harsh["winners"])) >= 10
                  and len(eras(gentle["winners"])) >= 10)

    winners, top2, valence = mixed["winners"], mixed["top2"], mixed["valence"]
    era_seq = eras(winners)

    # 2) STRUCTURE beyond marginals (mixed)
    h_real = cond_entropy(era_seq)
    h_mu, h_sd = marginal_chain_null(era_seq, rng)
    structure_pass = h_sd > 0 and h_real < h_mu - 2 * h_sd

    # 3) COALITION: Dread reigns with Ache close behind, vs circular-shift null (mixed)
    a_series = [1 if w == "Dread" else 0 for w in winners]
    b_series = [1 if "Ache" in t else 0 for t in top2]
    co_rate = lambda a, b: statistics.fmean(x * y for x, y in zip(a, b))  # noqa: E731
    real_co = co_rate(a_series, b_series)
    null_co = shift_null(a_series, b_series, co_rate, rng)
    mu, sd = statistics.fmean(null_co), statistics.pstdev(null_co)
    co_z = (real_co - mu) / sd if sd > 0 else 0.0
    coalition_pass = co_z >= 2.0

    # 4) PREDICTION: reigning part -> where valence heads next (mixed)
    def spread(val, win):
        deltas = defaultdict(list)
        for t in range(len(win) - HORIZON):
            if win[t]:
                deltas[win[t]].append(val[t + HORIZON] - val[t])
        means = [statistics.fmean(v) for v in deltas.values() if len(v) >= 15]
        return (max(means) - min(means)) if len(means) >= 2 else 0.0
    real_spread = spread(valence, winners)
    null_spread = shift_null(valence, winners, spread, rng)
    pct = sum(1 for x in null_spread if x < real_spread) / len(null_spread)
    predict_pass = pct >= 0.95

    # designed-wiring sanity (reported, NOT claimed as emergence)
    neg_ticks = [ev.tick for ev in BLOWS]
    after_neg = [w for ev in neg_ticks for w in winners[ev:ev + 30]]
    base = statistics.fmean(1 if w in GRIEF else 0 for w in winners if w)
    aft = (statistics.fmean(1 if w in GRIEF else 0 for w in after_neg if w)
           if any(after_neg) else 0.0)

    return {"g_harsh": g_harsh, "g_gentle": g_gentle,
            "eras_h": len(eras(harsh["winners"])), "eras_g": len(eras(gentle["winners"])),
            "gentle_share": dict(Counter(x for x in gentle["winners"] if x)),
            "track": track_pass,
            "h_real": h_real, "h_null": (h_mu, h_sd), "structure": structure_pass,
            "co_rate": real_co, "co_z": co_z, "coalition": coalition_pass,
            "spread": real_spread, "spread_pct": pct, "predict": predict_pass,
            "designed_base": base, "designed_after_neg": aft}


def report(seeds, label: str) -> list[dict]:
    print(f"\n--- {label} ---")
    rows = []
    for seed in seeds:
        m = analyze(seed)
        rows.append(m)
        print(f"\nseed {seed}:")
        print(f"  1 world-tracking : grief-pair floor-share harsh {m['g_harsh']:.0%} -> "
              f"gentle {m['g_gentle']:.0%} ({m['eras_h']}/{m['eras_g']} reigns) "
              f"-> {'PASS' if m['track'] else 'FAIL'}")
        print(f"  2 structure      : H(next|cur) {m['h_real']:.3f} vs null "
              f"{m['h_null'][0]:.3f} +/- {m['h_null'][1]:.3f} "
              f"-> {'PASS' if m['structure'] else 'FAIL'}")
        print(f"  3 coalition      : P(Dread reigns & Ache top-2) {m['co_rate']:.3f}, "
              f"z={m['co_z']:.1f} -> {'PASS' if m['coalition'] else 'FAIL'}")
        print(f"  4 prediction     : conditional-valence spread {m['spread']:.3f} "
              f"(pct {m['spread_pct']:.2f}) -> {'PASS' if m['predict'] else 'FAIL'}")
        print(f"  (designed wiring, not claimed: grief pair holds the floor "
              f"{m['designed_after_neg']:.0%} after a blow vs {m['designed_base']:.0%} overall)")
    print(f"\n  {label} tally:")
    for key, lab in (("track", "1 WORLD-TRACKING"), ("structure", "2 STRUCTURE"),
                     ("coalition", "3 COALITION"), ("predict", "4 PREDICTION")):
        k = sum(1 for m in rows if m[key])
        print(f"    {lab:17s}: {k}/{len(rows)}")
    return rows


def main() -> None:
    print(__doc__)
    report(TUNING_SEEDS, "TUNING seeds 11-15 (knobs were fit here; not the verdict)")
    held = report(HELDOUT_SEEDS, "HELD-OUT seeds 21-25 (the verdict)")
    print("\n=== VERDICT (held-out seeds; pre-registered: a claim passes at >= 4/5) ===")
    for key, lab in (("track", "1 WORLD-TRACKING"), ("structure", "2 STRUCTURE"),
                     ("coalition", "3 COALITION"), ("predict", "4 PREDICTION")):
        k = sum(1 for m in held if m[key])
        print(f"  {lab:17s}: {k}/{len(held)} -> {'PASS' if k >= 4 else 'FAIL'}")
    print("\nHonest frame: PASSes mean the dominant-part sequence is structured beyond its designed "
          "event wiring and tracks the world -- a functioning workspace ARCHITECTURE, not anyone "
          "home (§7). FAILs are recorded as-is; do not tune on the held-out seeds.")


if __name__ == "__main__":
    main()
