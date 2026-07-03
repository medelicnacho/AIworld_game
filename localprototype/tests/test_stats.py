"""Tests for scripts/stats.py -- the shared statistics instrument (METHODS.md M1-M4).

Checked against hand-computed / table values, not against itself. The calibration case
demanded by METHODS.md is pinned last: an n=1 'verdict' must be refused an error bar and
say so -- the harness's own recorded failure (§5.12's n=1 claim that later reversed) is
the reason this file exists.
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import stats


def test_t_distribution_matches_tables():
    # classic table values: two-sided 95% critical t
    assert abs(stats.t_crit95(4) - 2.776) < 0.01
    assert abs(stats.t_crit95(9) - 2.262) < 0.01
    assert abs(stats.t_crit95(29) - 2.045) < 0.01
    # survival function: P(T4 >= 2.776) = 0.025
    assert abs(stats.t_sf(2.776, 4) - 0.025) < 0.001
    assert abs(stats.t_sf(0.0, 10) - 0.5) < 1e-9


def test_sign_test_five_of_five_is_one_in_thirtytwo():
    wins, n, p = stats.sign_test([0.1, 0.2, 0.05, 0.3, 0.15])
    assert (wins, n) == (5, 5)
    assert abs(p - 1.0 / 32.0) < 1e-12
    # zeros are neither wins nor losses
    wins, n, p = stats.sign_test([0.1, 0.0, -0.2])
    assert (wins, n) == (1, 2)


def test_paired_known_values():
    # diffs [1..5]: mean 3, sd 1.5811, sem 0.7071, t = 4.2426 (df 4), p ~ 0.0132, d ~ 1.897
    cmp = stats.paired([2, 4, 6, 8, 10], [1, 2, 3, 4, 5])
    assert abs(cmp.effect.mean - 3.0) < 1e-9
    assert abs(cmp.effect.sem - 0.7071) < 0.001
    assert abs(cmp.t - 4.2426) < 0.001
    assert abs(cmp.p - 0.0132) < 0.001
    assert abs(cmp.d - 1.897) < 0.01
    lo, hi = cmp.effect.ci95
    assert abs(lo - (3.0 - 2.776 * 0.7071)) < 0.01   # CI from the exact t critical value
    assert cmp.sign[:2] == (5, 5)


def test_paired_requires_shared_seed_list():
    try:
        stats.paired([1, 2, 3], [1, 2])
        raise AssertionError("unequal arms must be refused -- pairing IS the method")
    except ValueError:
        pass


def test_clustered_catches_the_naive_understatement():
    # 4 seeds whose runs disagree (cluster means spread) but are tight WITHIN each run:
    # pooling all probes as independent claims far more certainty than 4 draws support.
    clusters = [[0.10, 0.11, 0.09, 0.10] , [0.30, 0.31, 0.29, 0.30],
                [0.50, 0.51, 0.49, 0.50], [0.70, 0.71, 0.69, 0.70]]
    c = stats.clustered(clusters)
    assert c.per_cluster.n == 4                       # the honest n is seeds, not probes
    assert abs(c.per_cluster.mean - 0.40) < 1e-9
    assert c.understatement > 1.5                     # Miller: naive SEs understate up to ~3x
    assert "tighter than the data supports" in str(c)


def test_power_matches_the_textbook():
    # paired d=1.0 at 80% power / alpha .05 needs ~9-10 subjects (textbook: 10)
    assert 8 <= stats.power_n(1.0) <= 11
    # a modest effect needs far more than 5 seeds -- 5/5 sign tests are blind to it
    assert stats.power_n(0.5) >= 30
    n5_effect = stats.power_n(2.0)                    # what CAN n=5 see? only huge effects
    assert n5_effect <= 5


def test_resample_means_reduces_within_seed_first():
    assert stats.resample_means([[1.0, 3.0], [2.0, 4.0]]) == [2.0, 3.0]


def test_the_calibration_case_n1_is_refused_an_error_bar():
    # METHODS.md: the helper must flag the archived n=1 claim that later reversed.
    s = stats.summary([0.42])
    assert s.sd is None and s.sem is None and s.ci95 is None
    assert "UNPOWERED" in str(s)
    assert "n=1" in str(s)


def test_verdict_warns_when_underpowered_for_registered_effect():
    # tiny spread, 3 seeds, but the registered minimum effect needs many more
    cmp = stats.paired([0.51, 0.49, 0.50], [0.50, 0.50, 0.50])
    text = stats.verdict("underpowered probe", cmp, min_effect=0.001)
    assert "NOT evidence of absence" in text
