"""Tests for seeing the fellowships (world/factions.py).

Pinned: aligned opinions cluster and orthogonal ones split (pure read, no mutation);
loners stay loners; the leader is the member most trusted BY ITS OWN; the home region
is where the plurality actually stands; the banner speaks the ground ("the folk of
the vale")."""

import random

from agent.agent import Agent
from agent.bond import Bond
from services.llm import MockLLM
from world import factions as F
from world import regions as R
from world.sim import World


def _town():
    w = World(events_enabled=False)
    w.llm = MockLLM(seed=7)
    w.regions_enabled = True
    w.regions = R.Regions(seed=1)
    souls = []
    for i in range(6):
        a = Agent(f"s{i}", f"F{i}", (50.0 + i, 50.0), "You are a soul.", ["the well"],
                  w.llm, seed=i, temperament=0.0, lifespan=10 ** 6)
        a.bond_enabled = True
        w.add(a)
        souls.append(a)
    # two clean blocs by construction: [+1,0,...] vs [-1,0,...]; s5 stays a loner
    for a in souls[:3]:
        a.belief_vec = (1.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    for a in souls[3:5]:
        a.belief_vec = (-1.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    souls[5].belief_vec = None
    return w, souls


def test_aligned_cluster_and_orthogonal_split():
    w, souls = _town()
    m = F.factions_of(w)
    assert m["s0"] == m["s1"] == m["s2"]
    assert m["s3"] == m["s4"] != m["s0"]
    assert m["s5"] == F.LONER


def test_the_leader_is_the_most_trusted_by_its_own():
    w, souls = _town()
    m = F.factions_of(w)
    souls[1].bonds["s0"] = Bond(trust=0.9, history=2.0)
    souls[2].bonds["s0"] = Bond(trust=0.8, history=2.0)
    lead = F.leader_of(w, m["s0"], m)
    assert lead.id == "s0"


def test_home_region_and_banner_read_the_ground_held():
    w, souls = _town()
    m = F.factions_of(w)
    rich = max(range(6), key=lambda i: w.regions.yields[i])
    cx = ((rich % R.COLS) * 300 + 150.0, (rich // R.COLS) * 300 + 150.0)
    for a in souls[:3]:
        a.position = cx                              # the bloc stands in the vale
    fid = m["s0"]
    assert F.home_region(w, fid, m) == rich
    assert F.banner_of(w, fid, m) == "the folk of the vale"
