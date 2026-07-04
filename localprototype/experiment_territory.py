"""V2 -- FELLOWSHIPS TAKE TERRITORY: do emergent opinion-blocs become neighbourhoods?

V1 proved mood is spatially real (§5.24). This asks the companion question -- does the
SOCIAL graph become GEOGRAPHY? -- and the tuning found the honest form of it: a plain
cooperative town is one undifferentiated blob (every soul ends up loving every other,
zero enmity, so bond-attraction pulls them all into one clump -- nothing to take
territory). The real question needs DIFFERENTIATION, which the emergent opinion dynamics
supply (bounded confidence: aligned views warm and cluster, distant views cool and
repel). With those on, kin stand close and foes push apart -- and THAT is where "does a
fellowship take territory" can actually be asked.

Protocol (substrate-only, MockLLM, deterministic): a roaming town of n=32 with EMERGENT
opinion vectors (seed_opinion; no assigned faith), 2000 ticks, sampled every 10 after a
500-tick warm-up.

PRE-REGISTERED (tuning 11-15; VERDICT from virgin seeds 201-205; each >= 4/5):

  T1 KIN CLUSTER, FOES PART: pairs a soul feels KIN toward (affinity > 0.1) stand closer
     than an AFFINITY-SHUFFLED null (the same affinities reassigned to random pairs, 200
     shuffles). The social graph reaches into space. Per seed.
  T2 A SOUL LIVES SOMEWHERE: a soul's k-nearest-neighbour set one window later overlaps
     (Jaccard) with its own set MORE than with a random OTHER soul's set a window later
     (identity-shuffled null) -- it keeps ITS neighbours, not just any. Per seed.

Wild replication registered on the live towns' town_history.jsonl once a week of samples
exists (lab verdict plus wild confirmation).

  python experiment_territory.py
"""
from __future__ import annotations

import random
import statistics
import sys

from agent.agent import Agent
from agent.genesis import coined_name, endow_faculties
from services import embed
from services.llm import MockLLM
from world.sim import World

TUNING_SEEDS = (11, 12, 13, 14, 15)
HELDOUT_SEEDS = (201, 202, 203, 204, 205)
N, TICKS, WARMUP, EVERY, KNN = 32, 2000, 500, 10, 5


def build(seed: int) -> World:
    embed.use_jaccard_only(True)
    rng = random.Random(seed)
    w = World(events_enabled=False, murmur_enabled=True, move_seed=seed)
    w.llm = MockLLM(seed=7)
    w.move_enabled = True
    w.bounds = (900, 600)
    for i in range(N):
        name = coined_name(rng)
        a = Agent(f"s{i}", name, (rng.uniform(0, 900), rng.uniform(0, 600)),
                  f"You are {name}.", [f"I am {name}", "the world turns"], w.llm,
                  seed=1000 * seed + i, temperament=rng.uniform(-0.6, 0.6),
                  lifespan=10 ** 9)
        endow_faculties(a, a._rng)
        a.bond_enabled = True
        a.seed_opinion(random.Random(seed * 1000 + i))   # EMERGENT out-groups
        w.add(a)
    return w


def _dist(p, q) -> float:
    return ((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2) ** 0.5


def t1_kin_cluster(world, rng: random.Random, shuffles: int = 200) -> tuple[float, float]:
    pos = {a.id: a.position for a in world.agents}
    ids = list(pos)
    kin = [(a.id, oid) for a in world.agents
           for oid, v in a.affinity.items() if oid in pos and v > 0.1]
    if len(kin) < 5:
        return 0.0, 0.0
    obs = statistics.fmean(_dist(pos[x], pos[y]) for x, y in kin)
    nulls = []
    for _ in range(shuffles):
        fake = [(rng.choice(ids), rng.choice(ids)) for _ in kin]
        nulls.append(statistics.fmean(_dist(pos[x], pos[y]) for x, y in fake if x != y))
    return obs, statistics.fmean(nulls)


def _knn_sets(sample) -> dict:
    out = {}
    for i, (sid, x, y) in enumerate(sample):
        near = sorted((((x - x2) ** 2 + (y - y2) ** 2, oid)
                       for j, (oid, x2, y2) in enumerate(sample) if j != i))[:KNN]
        out[sid] = frozenset(oid for _, oid in near)
    return out


def _jac(a: frozenset, b: frozenset) -> float:
    u = a | b
    return len(a & b) / len(u) if u else 0.0


def t2_lives_somewhere(samples, rng: random.Random) -> tuple[float, float]:
    """Own-neighbourhood persistence vs an IDENTITY-shuffled null (does soul X keep ITS
    neighbours a window later, more than it matches a random other soul's neighbours)."""
    knn = [_knn_sets(s) for s in samples]
    if len(knn) < 4:
        return 0.0, 0.0
    lag = max(1, len(knn) // 4)
    real, null = [], []
    for t in range(len(knn) - lag):
        a, b = knn[t], knn[t + lag]
        others = list(b)
        for sid in a:
            if sid in b:
                real.append(_jac(a[sid], b[sid]))
                r = others[rng.randrange(len(others))]
                null.append(_jac(a[sid], b[r]))
    return (statistics.fmean(real) if real else 0.0,
            statistics.fmean(null) if null else 0.0)


def run(seed: int) -> dict:
    w = build(seed)
    late = []
    for t in range(TICKS):
        with w.lock:
            w.step(speak=True)
        if t >= WARMUP and t % EVERY == 0:
            late.append([(a.id, a.position[0], a.position[1]) for a in w.agents])
    rng = random.Random(seed * 17 + 3)
    obs, null1 = t1_kin_cluster(w, rng)
    j_real, j_null = t2_lives_somewhere(late, rng)
    return {"t1_obs": obs, "t1_null": null1, "t2_real": j_real, "t2_null": j_null}


def report(seeds, label: str):
    print(f"\n--- {label} ---")
    rows = []
    for seed in seeds:
        o = run(seed)
        t1 = o["t1_obs"] > 0 and o["t1_obs"] < o["t1_null"]
        t2 = o["t2_real"] > o["t2_null"]
        rows.append({"t1": t1, "t2": t2})
        print(f"seed {seed}: kin dist {o['t1_obs']:6.1f} vs null {o['t1_null']:6.1f} | "
              f"own-nbhd {o['t2_real']:.3f} vs other-soul {o['t2_null']:.3f} | "
              f"T1 {'PASS' if t1 else 'FAIL'}  T2 {'PASS' if t2 else 'FAIL'}")
    return rows


def main() -> None:
    print(__doc__)
    report(TUNING_SEEDS, "TUNING seeds 11-15 (knobs may move here; never a verdict)")
    held = report(HELDOUT_SEEDS, "HELD-OUT virgin seeds 201-205 (the verdict)")
    print("\n=== VERDICT (held-out; pre-registered: each claim >= 4/5) ===")
    ok = True
    for k, lab in (("t1", "T1 KIN CLUSTER, FOES PART"),
                   ("t2", "T2 A SOUL LIVES SOMEWHERE")):
        cnt = sum(1 for r in held if r[k])
        ok &= cnt >= 4
        print(f"  {lab:26s}: {cnt}/{len(held)} -> {'PASS' if cnt >= 4 else 'FAIL'}")
    print("\nHonest frame: the cooperative town is ONE blob (nothing to zone). With"
          "\nemergent out-groups, T1 asks whether the social graph reaches space at all,"
          "\nand T2 whether a soul KEEPS its own neighbours -- lives in a place, not a"
          "\ncrowd. T1+T2 means emergent factions became emergent territory; nobody"
          "\ndrew the map.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
