"""scripts/stats.py -- the shared statistics instrument (METHODS.md §1, M1-M4).

The reference is Miller, *Adding Error Bars to Evals* (arXiv:2411.00640): an experiment's
seeds are questions drawn from an unseen super-population, arms that share seeds are PAIRED,
and repeated probes inside one run are a CLUSTER, not n independent draws. Before this file,
every experiment recomputed mean±std by hand (or didn't -- nine ran single-run); this is the
one helper they all share, so no verdict again ships without an error bar.

Stdlib only, like the substrate: nothing here needs numpy.

    from scripts.stats import paired, summary, clustered, power_n, sign_test

  - summary(xs)            -> n, mean, sd, sem, ci95 (M1's building block; flags n=1 loudly)
  - paired(treat, ctrl)    -> per-seed deltas with SEM/CI/d/t/p + exact sign test (M1)
  - clustered(clusters)    -> cluster-mean reduction + how much a naive SEM understated (M2)
  - power_n(d)             -> seeds needed BEFORE running, for the registered effect (M3)
  - resample_means(k_per_seed) -> average within seed before the per-seed delta (M4)

Validation (METHODS.md): on the harness's own recorded failure -- the §5.12 n=1 claim that
reversed under replication -- summary() must refuse the error bar and say why. Pinned in
tests/test_stats.py.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field

# --- the t distribution, honestly ------------------------------------------------------------
# Exact p-values need the t CDF; the t CDF needs the regularized incomplete beta. This is the
# standard continued-fraction evaluation (Numerical Recipes §6.4) -- ~30 lines buys exact
# two-sided p at any df, instead of a lookup table that lies between its rows.


def _betacf(a: float, b: float, x: float) -> float:
    MAXIT, EPS, FPMIN = 200, 3e-9, 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    if abs(d) < FPMIN:
        d = FPMIN
    d = 1.0 / d
    h = d
    for m in range(1, MAXIT + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < EPS:
            break
    return h


def _betainc(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    ln_beta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(ln_beta + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def t_sf(t: float, df: int) -> float:
    """Survival function P(T >= t) of Student's t. Two-sided p = 2 * t_sf(|t|, df)."""
    if df <= 0:
        return float("nan")
    x = df / (df + t * t)
    p = 0.5 * _betainc(df / 2.0, 0.5, x)
    return p if t >= 0 else 1.0 - p


def t_crit95(df: int) -> float:
    """Two-sided 95% critical value of t (bisection on t_sf -- exact, no table)."""
    if df <= 0:
        return float("nan")
    lo, hi = 0.0, 700.0
    for _ in range(80):
        mid = (lo + hi) / 2.0
        if 2.0 * t_sf(mid, df) > 0.05:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


# --- M1: summaries and paired-seed comparisons ------------------------------------------------

@dataclass
class Summary:
    n: int
    mean: float
    sd: float | None      # None when n == 1: no error bar EXISTS, and we say so
    sem: float | None
    ci95: tuple[float, float] | None

    def __str__(self) -> str:
        if self.sd is None:
            return (f"{self.mean:+.4f} (n=1 -- UNPOWERED: no error bar exists; "
                    f"a single seed is an anecdote, not a verdict)")
        if self.sd == 0.0:
            return (f"{self.mean:+.4f} (identical across all {self.n} seeds -- "
                    f"deterministic substrate, not sampling luck)")
        lo, hi = self.ci95
        return f"{self.mean:+.4f} ± {self.sem:.4f} SEM  [95% CI {lo:+.4f} .. {hi:+.4f}]  (n={self.n})"


def summary(xs: list[float]) -> Summary:
    """Mean with an honest error bar -- and a refusal where none exists (the §5.12 lesson:
    the n=1 'confirmed' that reversed under replication is this function's calibration case)."""
    n = len(xs)
    if n == 0:
        raise ValueError("no data")
    m = statistics.fmean(xs)
    if n == 1:
        return Summary(1, m, None, None, None)
    sd = statistics.stdev(xs)
    sem = sd / math.sqrt(n)
    half = t_crit95(n - 1) * sem
    return Summary(n, m, sd, sem, (m - half, m + half))


def sign_test(diffs: list[float]) -> tuple[int, int, float]:
    """Exact one-sided sign test: (wins, n_nonzero, p). 5/5 is p = 1/32 -- fine for large
    effects, blind to modest ones (that's what power_n is for)."""
    nz = [d for d in diffs if d != 0.0]
    n = len(nz)
    if n == 0:
        return 0, 0, 1.0
    wins = sum(1 for d in nz if d > 0)
    p = sum(math.comb(n, k) for k in range(wins, n + 1)) / 2.0 ** n
    return wins, n, p


@dataclass
class Paired:
    """A paired-seed comparison (M1): arms share the seed list, so the unit of analysis is
    the PER-SEED DELTA -- never the difference of arm means."""
    diffs: list[float]
    treatment_mean: float
    control_mean: float
    effect: Summary = field(init=False)
    d: float = field(init=False)            # Cohen's d of the paired deltas
    t: float = field(init=False)
    p: float = field(init=False)            # two-sided, exact t
    sign: tuple[int, int, float] = field(init=False)

    def __post_init__(self) -> None:
        self.effect = summary(self.diffs)
        n = len(self.diffs)
        if n < 2 or self.effect.sd in (None, 0.0):
            self.d = math.inf if (n and statistics.fmean(self.diffs)) else 0.0
            self.t = math.inf if self.d == math.inf else 0.0
            self.p = float("nan") if n < 2 else (0.0 if self.d == math.inf else 1.0)
        else:
            self.d = self.effect.mean / self.effect.sd
            self.t = self.effect.mean / self.effect.sem
            self.p = 2.0 * t_sf(abs(self.t), n - 1)
        self.sign = sign_test(self.diffs)

    def __str__(self) -> str:
        wins, n, sp = self.sign
        if self.effect.sd == 0.0:   # deterministic substrate: d/t/p are degenerate, say why
            return f"effect {self.effect}   sign {wins}/{n} p {sp:.3f} (one-sided)"
        return (f"effect {self.effect}"
                f"\n  Cohen's d {self.d:+.2f}   t({len(self.diffs) - 1}) {self.t:+.2f}"
                f"  p {self.p:.4f} (two-sided)   sign {wins}/{n} p {sp:.3f} (one-sided)")


def paired(treatment: list[float], control: list[float]) -> Paired:
    if len(treatment) != len(control):
        raise ValueError("paired arms must share the seed list (equal lengths)")
    diffs = [t - c for t, c in zip(treatment, control)]
    return Paired(diffs, statistics.fmean(treatment), statistics.fmean(control))


# --- M2: clusters -----------------------------------------------------------------------------

@dataclass
class Clustered:
    per_cluster: Summary        # the honest one: each seed's run collapses to ONE observation
    naive_sem: float            # what pooling every probe as independent would have claimed
    understatement: float       # naive-vs-clustered ratio; Miller finds up to ~3x on real evals

    def __str__(self) -> str:
        note = (f"  (a naive SEM over pooled probes would claim ±{self.naive_sem:.4f} -- "
                f"{self.understatement:.1f}x tighter than the data supports)"
                if self.understatement > 1.05 else "")
        return f"{self.per_cluster}{note}"


def clustered(clusters: list[list[float]]) -> Clustered:
    """M2: probes inside one run are one draw of the world. Reduce each cluster (seed/run) to
    its mean FIRST, then summarize across clusters -- and report how much the naive pooled SEM
    would have understated the uncertainty."""
    if not clusters or any(not c for c in clusters):
        raise ValueError("each cluster needs at least one probe")
    means = [statistics.fmean(c) for c in clusters]
    honest = summary(means)
    pooled = [x for c in clusters for x in c]
    naive = (statistics.stdev(pooled) / math.sqrt(len(pooled))) if len(pooled) > 1 else 0.0
    ratio = (honest.sem / naive) if (naive and honest.sem) else 1.0
    return Clustered(honest, naive, ratio)


# --- M3: power --------------------------------------------------------------------------------

def power_n(d: float, power: float = 0.8, alpha: float = 0.05) -> int:
    """Seeds needed for a paired test to see a standardized effect |d| (two-sided alpha).
    Register the MINIMUM effect of interest alongside the falsifier and let this set n
    BEFORE the run -- so the harness stops 'confirming' nulls it never had power to reject.
    Normal-approximation with the usual small-n t correction (+1); good to ±1 seed."""
    if d == 0:
        return 10 ** 9
    nd = statistics.NormalDist()
    za = nd.inv_cdf(1.0 - alpha / 2.0)
    zb = nd.inv_cdf(power)
    return max(2, math.ceil(((za + zb) / abs(d)) ** 2) + 1)


# --- M4: resample within seed -----------------------------------------------------------------

def resample_means(per_seed_completions: list[list[float]]) -> list[float]:
    """M4: for anything scored downstream of SAMPLED speech, average k completions per seed
    first, then take per-seed deltas -- Miller's within-question variance reduction, nearly
    free on a local model. (This is clustered() without the audit: the reduction, reused.)"""
    return [statistics.fmean(c) for c in per_seed_completions]


# --- the one-line verdict formatter -----------------------------------------------------------

def verdict(label: str, cmp: Paired, min_effect: float | None = None) -> str:
    """The standard printed verdict: effect ± error bar, d, t, p, sign -- and, when a minimum
    effect of interest was registered, whether this n could even have seen it."""
    lines = [f"  {label}: {cmp}"]
    if min_effect is not None and cmp.effect.sd not in (None, 0.0):
        need = power_n(min_effect / cmp.effect.sd)
        n = len(cmp.diffs)
        if n < need:
            lines.append(f"    ⚠ registered minimum effect {min_effect:+.3f} needs n≈{need} "
                         f"seeds at 80% power -- this ran {n}: a null here is NOT evidence "
                         f"of absence")
    return "\n".join(lines)
