"""Tests for the workspace instrument (scripts/psyche_stats.py, WORKSPACE_NEXT W0).

Two of these are the instrument's own falsifiers. W2 will let a part read the workspace
back, and its failure mode is a self-reinforcing loop that FREEZES the floor -- precisely
what the §5.13 share-penalty formula was measured to do before fatigue-with-memory
replaced it. An instrument that showed a lively stream through a freeze would hide the
one thing it exists to catch.
"""

from agent.workspace import Workspace
from scripts.psyche_stats import workspace_stats


def _ws(log, names=None):
    ws = Workspace()
    ws.log = list(log)
    ws.names = names or {}
    return ws


def test_empty_log_is_reported_as_empty_not_as_calm():
    row = workspace_stats(_ws([]))
    assert row["ticks"] == 0 and row["turnovers"] == 0
    assert row["mean_reign"] is None and row["entropy"] is None


def test_a_frozen_floor_reads_zero_turnover_and_full_share():
    """THE INSTRUMENT'S FALSIFIER. One part holding the floor forever is a stuck note,
    not a stream. Turnover must be 0, share 100%, entropy 0 -- anything else and a
    freeze could pass for a mind."""
    row = workspace_stats(_ws(["Dread"] * 200))
    assert row["turnovers"] == 0
    assert row["turnover_rate"] == 0.0
    assert row["share"]["Dread"] == 1.0
    assert row["entropy"] == 0.0
    assert row["mean_reign"] == 200.0


def test_turnover_and_entropy_are_independent_readings():
    """Churn is not life: a stream that alternates every tick has MAXIMAL turnover and
    maximal entropy, and is no more a mind than the frozen one. The pair must be
    readable apart -- which is why both are reported and neither is a verdict alone."""
    flick = workspace_stats(_ws(["Dread", "Ache"] * 100))
    assert flick["turnover_rate"] > 0.9          # changes hands every tick
    assert flick["mean_reign"] == 1.0            # ... so no moment lasts
    assert flick["entropy"] > 0.99               # and the spread is maximal
    # a real stream: moments that LAST, and still turn over
    real = workspace_stats(_ws(["Dread"] * 8 + ["Tending"] * 6 + ["Ache"] * 9 +
                               ["Ember"] * 7 + ["Dread"] * 5))
    assert 0.0 < real["turnover_rate"] < 0.2
    assert real["mean_reign"] > 3.0


def test_reigns_are_runs_not_tick_counts():
    """A moment is a RUN. Dread holding 10 straight ticks is one reign, not ten."""
    row = workspace_stats(_ws(["Dread"] * 10 + ["Ache"] * 10))
    assert row["turnovers"] == 1
    assert row["mean_reign"] == 10.0


def test_window_reads_only_the_recent_stream():
    """A change taking hold now must be visible under a long history of the old regime."""
    log = ["Dread"] * 500 + ["Tending"] * 50
    assert workspace_stats(_ws(log))["share"]["Dread"] > 0.85
    recent = workspace_stats(_ws(log), window=50)
    assert recent["share"] == {"Tending": 1.0}


def test_share_sums_to_one_and_is_ordered():
    row = workspace_stats(_ws(["Dread"] * 5 + ["Ache"] * 3 + ["Ember"] * 2))
    assert abs(sum(row["share"].values()) - 1.0) < 1e-9
    assert list(row["share"]) == ["Dread", "Ache", "Ember"]      # loudest first
