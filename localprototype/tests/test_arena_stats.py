"""Tests for the arena instrument (scripts/arena_stats.py, EVOLUTION_NEXT stage 1).

The instrument exists because the arena ran a full founder turnover with its selection
engine switched off and nobody watching. An instrument that reports movement where there
is none would be worse than none at all -- these pin that it cannot.
"""

import random

import pytest

from agent.genome import DIALS
from scripts.arena_stats import founding_centre, genome_stats
from services.llm import MockLLM
from world.sim import World


def _town(n=60, seed=3):
    from santana_app.evolution import _found_souls
    w = World(rebirth_enabled=False, events_enabled=False)
    w.llm = MockLLM(seed=seed)
    _found_souls(w, random.Random(seed), n)
    return w


def test_reads_every_germ_line_dial():
    """All 7, not the 4 the HTTP bridge carries -- the reason this reads snapshots."""
    row = genome_stats(_town().agents)
    assert set(row["dials"]) == set(DIALS)
    assert row["n"] == 60 and row["n_genomes"] == 60


def test_a_fresh_founding_has_not_drifted_from_its_own_centre():
    """THE INSTRUMENT'S OWN FALSIFIER. A just-founded town IS the baseline, so every
    drift must read ~0. This is the check that would have caught the bug this file was
    written after: assuming a 0.5 centre for every dial reported grip as -0.142 and
    openness as -0.112 drifted -- a fabricated selective sweep, in a town that had
    not moved at all."""
    row = genome_stats(_town(n=300, seed=5).agents)
    for d, v in row["dials"].items():
        assert abs(v["drift"]) < 0.06, (d, v["drift"])


def test_centre_is_measured_from_the_real_founding_path_not_assumed():
    """The centres live in three files (genesis.endow_faculties, genome.from_agent,
    evolution._found_souls) and must never be copied here to rot. Pin the two that
    are NOT 0.5 -- the ones the naive assumption got wrong."""
    c = founding_centre()
    assert 0.30 < c["grip"] < 0.40          # uniform(0.2,0.5), NOT 0.5
    assert 0.55 < c["compassion"] < 0.65    # a flat 0.6, NOT 0.5
    assert 0.35 < c["openness"] < 0.45      # uniform(0.25,0.55), NOT 0.5


def test_variance_is_reported_flat_when_nothing_is_inherited():
    """The absence-detector (the §5.13 discipline). Clone one genome across the town --
    no standing variation at all -- and every sd must read 0. An instrument that shows
    diversity here is lying, and every later divergence claim would inherit the lie."""
    w = _town(n=40, seed=7)
    donor = w.agents[0].genome
    for a in w.agents:
        a.genome = type(donor)(**{**donor.__dict__})
    row = genome_stats(w.agents)
    for d, v in row["dials"].items():
        assert v["sd"] == 0.0, (d, v["sd"])


def test_drift_is_omitted_rather_than_faked_when_no_baseline_is_given():
    """Pass no centre -> no drift column, instead of a number measured against nothing."""
    row = genome_stats(_town(n=20).agents, centre={})
    assert row["dials"] and all("drift" not in v for v in row["dials"].values())


def test_counts_castes_and_blocs():
    row = genome_stats(_town(n=50, seed=11).agents)
    assert sum(row["castes"].values()) == 50
    assert set(row["castes"]) <= {"breeder", "warrior"}
    assert sum(row["factions"].values()) in (0, 50)   # partitioned, or cleanly absent
