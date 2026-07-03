"""Tests for pledges (agent/pledge.py) -- a promise is a conduct-expectation with a deadline.

Pinned: the word given is remembered and lends a little warmth on credit; kept IN TIME it
deepens trust and writes a warm conduct story; past its deadline it breaks in step() where
the absence is measured -- always a betrayal (a promise IS an explicit expectation), with
the loyalty buffer absorbing exactly as everywhere else; a late fulfilment cannot rescue a
lapsed word; and pre-pledge snapshots wake cleanly (THE RULE)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import pledge
from agent.agent import Agent
from agent.bond import Bond
from services.llm import MockLLM


def _soul(sid="s0"):
    a = Agent(sid, "Cael", (0.0, 0.0), "You are Cael the fisher.",
              ["the water and the nets"], MockLLM(seed=7), seed=5, temperament=0.0,
              lifespan=10 ** 9)
    a.bond_enabled = True
    a.expect_enabled = True
    return a


def test_the_word_given_is_remembered_and_lends_credit():
    a = _soul()
    pledge.make(a, "player", "the stranger", "I will mend your north fence", due_tick=30, now=1)
    assert len(a.promises_held) == 1 and a.promises_held[0]["open"]
    assert any("gave me their word" in m.text for m in a.memory.items)
    assert a._conduct_expect["player"] > 0        # a stated intention: warmth on credit


def test_kept_in_time_deepens_trust_and_travels_warm():
    a = _soul()
    pledge.make(a, "player", "the stranger", "I will mend your north fence", due_tick=30, now=1)
    kept = pledge.fulfill(a, "player", now=20)
    assert kept == "I will mend your north fence"
    assert a.bonds["player"].trust > 0            # warmer -- at the Bond's own slow pace
    assert a.bonds["player"].wounds == 0
    story = [m for m in a.memory.items if "kept their word" in m.text]
    assert story and story[0].lore_id == "conduct:player"   # a kept word can gossip too
    assert a._conduct_expect["player"] > 0.2
    assert not a.promises_held[0]["open"]


def test_kept_words_compound():
    # trust is EARNED at the Bond's designed pace: one kept word is a start, three are a
    # relationship -- promises must never be a trust cheat-code around the dyad substrate
    one, three = _soul("s3"), _soul("s4")
    pledge.make(one, "player", "the stranger", "word one", due_tick=10, now=1)
    pledge.fulfill(one, "player", now=2)
    for i in range(3):
        pledge.make(three, "player", "the stranger", f"word {i}", due_tick=10 * i + 10,
                    now=10 * i + 1)
        pledge.fulfill(three, "player", now=10 * i + 2)
    assert three.bonds["player"].trust > one.bonds["player"].trust > 0


def test_the_clock_breaks_it_where_the_absence_is_measured():
    a = _soul()
    pledge.make(a, "player", "the stranger", "I will bring grain before the frost",
                due_tick=10, now=1)
    for t in range(2, 13):
        a.step(t)                                  # the lapse fires from step(), not a caller
    assert not a.promises_held[0]["open"] and a.promises_held[0]["kept"] is False
    assert a.bonds["player"].wounds == 1           # always a betrayal: the word WAS the expectation
    assert a.bonds["player"].trust < 0
    breach = [m for m in a.memory.items if "broken their word" in m.text]
    assert breach and breach[0].lore_id == "conduct:player"  # A BROKEN WORD TRAVELS
    assert a._conduct_expect["player"] < 0


def test_a_late_keeping_cannot_rescue_a_lapsed_word():
    a = _soul()
    pledge.make(a, "player", "the stranger", "I will return the boat", due_tick=5, now=1)
    for t in range(2, 8):
        a.step(t)
    assert pledge.fulfill(a, "player", now=8) is None       # too late: the break stands
    assert a.bonds["player"].wounds == 1


def test_loyalty_absorbs_the_breach():
    stranger, friend = _soul("s1"), _soul("s2")
    fb = friend.bonds.setdefault("player", Bond())
    for _ in range(12):
        fb.warm(0.5)                               # twelve warm seasons of history
    for a in (stranger, friend):
        pledge.make(a, "player", "the stranger", "I will stand with you", due_tick=5, now=1)
        for t in range(2, 8):
            a.step(t)
    assert friend.bonds["player"].trust > stranger.bonds["player"].trust
    assert friend.bonds["player"].trust > 0        # the deep bond bends, doesn't break


def test_pre_pledge_snapshots_wake_cleanly():
    a = _soul()
    state = a.__getstate__()
    del state["promises_held"]                     # a snapshot from before the organ existed
    b = object.__new__(Agent)
    b.__setstate__(state)
    assert b.promises_held == []                   # THE RULE: every new field gets a default
