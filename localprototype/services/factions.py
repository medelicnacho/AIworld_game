"""Faction metrics: reduce a world's social graph to numbers that can FAIL.

The sim's central claim is that agents form factions. This module turns that
claim into something falsifiable. It clusters agents by mutual positive affinity,
scores how partitioned the affinity graph is (Newman modularity), and -- the part
that actually matters -- measures how well those clusters line up with the agents'
FIXED labels: their faith, and the sign of their temperament.

The point of that last measure is to call the bluff. If the blocs are just the
faith labels read back out (purity ~1.0), the "factions" are label-driven
homophily wired into hear(), not emergence. The honest result the prototype keeps
gesturing at -- "factions key off temperament/faith, fairly deterministic" --
becomes a number here instead of a vibe. Pair this with the substrate-ablated arm
(Agent.social_learning = False) in experiment_factions.py: with the social graph
frozen, every metric here should collapse to ~0, which is the proof the metric
detects ABSENCE of structure and isn't just always reporting factions.

Stdlib only; populations are tiny (<= ~24) so the O(n^2) passes are free.
"""

from __future__ import annotations

from agent import belief as _belief


def _mutual(a, b) -> float:
    """How a and b feel about each other, averaged both ways (-1..1)."""
    return 0.5 * (a.affinity.get(b.id, 0.0) + b.affinity.get(a.id, 0.0))


def _hostility(a, b) -> float:
    """Open grievance between a and b, averaged both ways (>= 0)."""
    return 0.5 * (a.hostility.get(b.id, 0.0) + b.hostility.get(a.id, 0.0))


# --- clustering: who clumps with whom on positive affinity -----------------
def blocs(agents, thresh: float = 0.15) -> list[list[str]]:
    """Connected components of the graph whose edges are pairs feeling mutual
    affinity above `thresh`. A bloc is a set of souls bound into one camp; a
    loner is its own singleton bloc. This is the empirical 'faction', read off
    the affinity ledger with no reference to faith or temperament labels."""
    idx = {a.id: i for i, a in enumerate(agents)}
    parent = list(range(len(agents)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        parent[find(x)] = find(y)

    for i, a in enumerate(agents):
        for b in agents[i + 1:]:
            if _mutual(a, b) > thresh:
                union(i, idx[b.id])

    groups: dict[int, list[str]] = {}
    for a in agents:
        groups.setdefault(find(idx[a.id]), []).append(a.id)
    return list(groups.values())


def _partition(agents, thresh: float = 0.15) -> dict[str, int]:
    """id -> bloc number, from blocs()."""
    return {aid: c for c, group in enumerate(blocs(agents, thresh)) for aid in group}


def modularity(agents, thresh: float = 0.15) -> float:
    """Newman modularity of the positive-affinity graph under the bloc partition.
    ~0 means the blocs are no more internally bonded than chance (no real
    structure); toward 1 means strongly partitioned camps. Negative weights are
    clipped -- enmity defines the gap between camps, not edges within the graph."""
    n = len(agents)
    if n < 2:
        return 0.0
    part = _partition(agents, thresh)
    w = [[max(0.0, _mutual(agents[i], agents[j])) if i != j else 0.0
          for j in range(n)] for i in range(n)]
    deg = [sum(row) for row in w]
    two_m = sum(deg)
    if two_m == 0:
        return 0.0
    q = 0.0
    ids = [a.id for a in agents]
    for i in range(n):
        for j in range(n):
            if part[ids[i]] == part[ids[j]]:
                q += w[i][j] - deg[i] * deg[j] / two_m
    return q / two_m


# --- do the blocs just reproduce a fixed label? ----------------------------
def _faith(a) -> str:
    return a.religion or "?"


def _temper(a) -> str:
    return "warm" if a.temperament >= 0 else "cold"


def purity(agents, label, thresh: float = 0.15) -> float:
    """Fraction of agents whose `label` matches the majority label of their bloc.
    1.0 means the empirical blocs ARE the label partition (the factions are that
    label, homophily) -- the result that deflates the emergence claim. Lower means
    the blocs cut across the label, i.e. structure the label doesn't explain."""
    if not agents:
        return 0.0
    matched = 0
    for group in blocs(agents, thresh):
        labels = [label(a) for a in agents if a.id in set(group)]
        top = max(set(labels), key=labels.count)
        matched += labels.count(top)
    return matched / len(agents)


def split_by(agents, label, pair_value) -> tuple[float, float, float]:
    """Mean of `pair_value(a, b)` for same-label pairs vs different-label pairs,
    and the gap (same - diff). For affinity this asks the substrate-level
    question directly, no clustering: do same-faith souls bond more than cross-
    faith ones? A gap ~0 means the label carries no social charge."""
    same: list[float] = []
    diff: list[float] = []
    n = len(agents)
    for i in range(n):
        for j in range(i + 1, n):
            v = pair_value(agents[i], agents[j])
            (same if label(agents[i]) == label(agents[j]) else diff).append(v)
    mean = lambda xs: sum(xs) / len(xs) if xs else 0.0
    si, di = mean(same), mean(diff)
    return si, di, si - di


def partition(agents, thresh: float = 0.15) -> dict[str, int]:
    """Public id -> bloc-number view, for comparing memberships across runs."""
    return _partition(agents, thresh)


def banners(agents, thresh: float = 0.15) -> dict[frozenset, str]:
    """Stage 2: the word each emergent cluster rallied around. For every multi-soul
    bloc, find the term distinctive to its members' recent speech versus everyone
    else's -- the banner. Only meaningful when agents are language-grounded
    (Agent.said_lines is populated); returns {} otherwise. This is what turns an
    emergent cluster from an anonymous blob into a NAMED faction you can read."""
    groups = blocs(agents, thresh)
    out: dict[frozenset, str] = {}
    for group in groups:
        if len(group) < 2:
            continue
        members = set(group)
        ins = [ln for a in agents if a.id in members for ln in getattr(a, "said_lines", [])]
        outs = [ln for a in agents if a.id not in members for ln in getattr(a, "said_lines", [])]
        if not ins:
            continue
        terms = _belief.distinctive_terms(ins, outs, k=1)
        if terms:
            out[frozenset(group)] = terms[0]
    return out


def comembership_variance(partitions: list[dict[str, int]]) -> float:
    """Across seeded runs, how much does WHO-clusters-WITH-WHOM depend on the run?
    For every pair of souls, take the fraction of runs they land in the same bloc;
    its variance is 0 when the pair ALWAYS shares (or never shares) a camp -- i.e.
    membership is fixed by some attribute (homophily) -- and rises when the same
    pair sometimes allies, sometimes splits, i.e. membership is history-dependent.
    This is the single cleanest discriminator: ~0 == not emergent, > 0 == emergent."""
    if len(partitions) < 2:
        return 0.0
    ids = sorted(partitions[0])
    pair_vars = []
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            co = [1.0 if p.get(a) == p.get(b) else 0.0 for p in partitions]
            mean = sum(co) / len(co)
            pair_vars.append(sum((c - mean) ** 2 for c in co) / len(co))
    return sum(pair_vars) / len(pair_vars) if pair_vars else 0.0


def summary(agents, thresh: float = 0.15) -> dict:
    """One flat dict of every faction metric, for telemetry rows and experiment
    reduction. Read it as: high `modularity` + `bloc_faith_purity` ~1.0 == the
    factions are the faith labels (homophily); an ablated run should drive
    `modularity`, the gaps, and the purities toward 0 / chance."""
    fa_in, fa_cross, fa_gap = split_by(agents, _faith, _mutual)
    fh_in, fh_cross, _ = split_by(agents, _faith, _hostility)
    ta_in, ta_cross, ta_gap = split_by(agents, _temper, _mutual)
    return {
        "n_agents": len(agents),
        "n_blocs": len(blocs(agents, thresh)),
        "modularity": round(modularity(agents, thresh), 4),
        "faith_in_affinity": round(fa_in, 4),
        "faith_cross_affinity": round(fa_cross, 4),
        "faith_affinity_gap": round(fa_gap, 4),
        "faith_in_hostility": round(fh_in, 3),
        "faith_cross_hostility": round(fh_cross, 3),
        "temp_in_affinity": round(ta_in, 4),
        "temp_cross_affinity": round(ta_cross, 4),
        "temp_affinity_gap": round(ta_gap, 4),
        "bloc_faith_purity": round(purity(agents, _faith, thresh), 4),
        "bloc_temp_purity": round(purity(agents, _temper, thresh), 4),
    }
