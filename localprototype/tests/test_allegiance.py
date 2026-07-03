"""Tests for Phase B allegiance (agent/allegiance.py) -- join/refuse/oppose, DERIVED.

Pinned: deep trust joins; a dark reputation opposes even in a stranger; conscience
refuses a dark name despite a warm personal bond (compassion outvotes affection); a
collapsed or contracted soul stays OUT of danger regardless of love (the somatic floor
extends to war); the timid refuse dangers the bold accept (E1's dial at work); wounds
vote; strangers with no name stay out; muster() sorts a whole town with legible
reasons. No loyalty scalar exists anywhere -- every assertion reads real state."""

import random

from agent import allegiance
from agent.agent import Agent
from agent.bond import Bond
from agent.genesis import endow_faculties
from services.llm import MockLLM
from world.sim import World


def _soul(name="Cael", **over):
    a = Agent("s0", name, (0.0, 0.0), f"You are {name}.", ["the well"],
              MockLLM(seed=7), seed=3, temperament=0.0, lifespan=10 ** 6)
    endow_faculties(a, random.Random(3))
    a.bond_enabled = True
    for k, v in over.items():
        setattr(a, k, v)
    return a


def test_deep_trust_joins():
    a = _soul()
    a.bonds["player"] = Bond(trust=0.8, history=2.5)
    verb, why = allegiance.decide(a, "player")
    assert verb == "join" and "trust" in why


def test_a_dark_name_opposes_even_in_a_stranger():
    a = _soul()
    a._conduct_expect["player"] = -0.6              # gossip did its work
    verb, why = allegiance.decide(a, "player")
    assert verb == "oppose" and "heard" in why


def test_conscience_outvotes_affection():
    a = _soul(compassion=0.9)
    a.bonds["player"] = Bond(trust=0.7, history=2.0)   # loves you...
    a._conduct_expect["player"] = -0.5                 # ...but your name is dark
    verb, _ = allegiance.decide(a, "player")
    assert verb == "oppose"                            # a warm heart STANDS AGAINST cruelty
    cold = _soul(compassion=0.0)
    cold.bonds["player"] = Bond(trust=0.7, history=2.0)
    cold._conduct_expect["player"] = -0.5
    # the callous soul just weighs bond against name and lands unsure -- it will not
    # crusade against you; only conscience turns a friend into an opponent
    assert allegiance.decide(cold, "player")[0] == "refuse"


def test_the_worn_stay_out_of_danger_regardless_of_love():
    a = _soul(wellbeing=0.1)
    a.bonds["player"] = Bond(trust=0.9, history=3.0)
    verb, why = allegiance.decide(a, "player", danger=0.8)
    assert verb == "refuse" and "worn" in why
    assert allegiance.decide(a, "player", danger=0.0)[0] == "join"   # an errand is fine


def test_the_timid_refuse_what_the_bold_accept():
    timid = _soul(boldness=0.05)
    bold = _soul(boldness=0.95)
    for s in (timid, bold):
        s.bonds["player"] = Bond(trust=0.6, history=1.5)
    danger = 0.7
    assert allegiance.decide(bold, "player", danger)[0] == "join"
    assert allegiance.decide(timid, "player", danger)[0] == "refuse"


def test_wounds_vote():
    fresh = _soul()
    scarred = _soul()
    for s in (fresh, scarred):
        s.bonds["player"] = Bond(trust=0.55, history=1.5)
    scarred.bonds["player"].wounds = 6
    assert allegiance.decide(fresh, "player")[0] == "join"
    assert allegiance.decide(scarred, "player")[0] != "join"    # scars remember


def test_strangers_stay_out():
    a = _soul()
    verb, why = allegiance.decide(a, "player")
    assert verb == "refuse" and "hardly know" in why


def test_muster_sorts_a_town_with_reasons():
    w = World(rebirth_enabled=True, events_enabled=False)
    w.llm = MockLLM(seed=7)
    rng = random.Random(5)
    for i, (trust, rep) in enumerate([(0.8, 0.3), (0.0, -0.6), (0.0, 0.0)]):
        a = Agent(f"s{i}", f"F{i}", (i * 10.0, 0.0), "You are a soul.", ["the well"],
                  w.llm, seed=i, temperament=0.0, lifespan=10 ** 6)
        endow_faculties(a, rng)
        a.bond_enabled = True
        if trust:
            a.bonds["player"] = Bond(trust=trust, history=2.0)
        if rep:
            a._conduct_expect["player"] = rep
        w.add(a)
    m = allegiance.muster(w, "player")
    assert [len(m["join"]), len(m["oppose"]), len(m["refuse"])] == [1, 1, 1]
    assert len(m["reasons"]) == 3                     # every soul says WHY, speakably
