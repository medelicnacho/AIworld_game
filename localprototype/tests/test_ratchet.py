"""Tests for the language ratchet (services/llm.py: schooling + biased transmission).

Pinned: a newborn mind needs school exactly once (a mind that has slept, or a saved
brain on disk, is not a newborn); the school corpus is the ELDERS' own spoken lines and
nothing else; trust weights the sleep corpus (the loved are heard twice, the deeply
trusted thrice -- the town's own prestige signal, no outside yardstick); schooling on an
empty tongue marks the soul schooled anyway (a town too young to have a tongue lets the
newborn found it). The cross-generational claims live in experiment_ratchet.py."""

import random

import pytest

pytest.importorskip("torch")

from agent.agent import Agent
from agent.bond import Bond
from services.llm import MockLLM, SoulVoiceLLM


def _soul(sid, name, age, lifespan=1000):
    a = Agent(sid, name, (0.0, 0.0), f"You are {name}.", ["the well"],
              MockLLM(seed=1), seed=int(sid[-1]) if sid[-1].isdigit() else 0,
              temperament=0.0, lifespan=lifespan)
    a.age = age
    a.bond_enabled = True
    return a


def test_a_newborn_needs_school_exactly_once(tmp_path):
    v = SoulVoiceLLM(minds_dir=str(tmp_path), seed=3)
    babe = _soul("s0", "Fenn", age=10)
    assert v.needs_school(babe)
    v.school(babe, "the well keeps us\nthe harvest is in\n" * 30)
    assert not v.needs_school(babe)                    # schooled, once, ever
    slept = _soul("s1", "Toll", age=500)
    v.mind_for("s1").sleeps = 4                        # a mind that has lived
    assert not v.needs_school(slept)


def test_the_school_corpus_is_the_elders_spoken_lines(tmp_path):
    v = SoulVoiceLLM(minds_dir=str(tmp_path), seed=3)
    elder, adult, child = (_soul("s0", "Old", 900), _soul("s1", "Mid", 400),
                           _soul("s2", "New", 20))
    elder.memory.write("the frost came early the year of the flood", tick=1,
                       source="self", speaker_id="s0")
    elder.memory.write("someone else's tale", tick=1, source="heard", speaker_id="s1")
    adult.memory.write("a mid-life line", tick=1, source="self", speaker_id="s1")
    child.memory.write("goo", tick=1, source="self", speaker_id="s2")
    corpus = v.school_corpus([elder, adult, child])
    assert "frost came early" in corpus                # the elders' tongue
    assert "goo" not in corpus                         # the young do not teach
    assert "someone else's tale" not in corpus         # spoken lines only


def test_trust_weights_the_sleep_corpus(tmp_path):
    v = SoulVoiceLLM(minds_dir=str(tmp_path), seed=3)
    a = _soul("s0", "Cael", age=300)
    a.bonds["friend"] = Bond(trust=0.8, history=2.0)
    a.memory.write("the zephyr grain is in", tick=1, source="heard", speaker_id="friend")
    a.memory.write("the cinder bell rang", tick=1, source="heard", speaker_id="stranger")
    corpus = v.weighted_corpus(a)
    assert corpus.count("zephyr grain") == 3           # deeply trusted: thrice
    assert corpus.count("cinder bell") == 1            # a stranger: once, as lived


def test_a_town_with_no_tongue_lets_the_newborn_found_it(tmp_path):
    v = SoulVoiceLLM(minds_dir=str(tmp_path), seed=3)
    babe = _soul("s9", "First", age=1)
    assert v.school(babe, "") is None
    assert not v.needs_school(babe)                    # marked schooled all the same


def test_the_mouth_brain_split_speaks_readably_and_individually(tmp_path):
    """TownVoices: a soul's mouth is its OWN markov chain -- only real words it was
    given, personalized after refresh, shared-anchor before; prune follows the living."""
    from services.llm import TownVoices
    from services.prompts import SpeechContext

    tv = TownVoices(seed=5)
    ctx = SpeechContext(name="Vesper", persona="You are Vesper.", mood=0.0,
                        agent_id="s0", drift=["the well keeps us"])
    before = tv.speak(ctx)                              # shared anchor: still real words
    assert before and "\x02" not in before
    tv.refresh("s0", ["the mash tun boiled over again this morning",
                      "a barrel of dark ale for the festival",
                      "no", "too short"])               # scraps are left out
    assert "s0" in tv.chains                            # personalized after refresh
    # its OWN life shows up in its OWN mouth: across samples, the brewer's chain
    # speaks brewer words (deterministic under the seeded rng)
    brewer = {"mash", "tun", "ale", "barrel", "boiled", "festival"}
    lines = " ".join(tv.speak(ctx) for _ in range(40)).lower()
    assert any(w in lines for w in brewer)
    tv.prune({"s1"})
    assert "s0" not in tv.chains                        # the mouth follows the living
