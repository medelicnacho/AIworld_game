"""Tests for the per-soul minds (homegrown/soulmind.py + services.llm.SoulVoiceLLM).

The claims pinned here are the DESIGN, not the poetry: a newborn babbles (fresh random
init, no inheritance of weights across the wheel); sleep on the soul's own corpus LEARNS
(loss falls); a different soul id is a different brain; brains persist atomically and wake
identical; the router speaks per-soul and prunes the departed; an infant with too little
lived simply does not dream yet.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

torch = pytest.importorskip("torch")

from homegrown.soulmind import BLOCK, SoulMind
from services.llm import SoulVoiceLLM
from services.prompts import SpeechContext

CORPUS = ("I mend the nets at first light and watch the water for the change.\n"
          "The saltmarsh smells of iron after rain and the gulls know it first.\n"
          "My father taught me the knots and the patience between them.\n") * 6


def test_newborn_babbles_but_speaks():
    mind = SoulMind("s0", seed=3)
    line = mind.line("the morning\n")
    assert isinstance(line, str)           # an infant SAYS something...
    assert mind.sleeps == 0                # ...before it has ever slept


def test_sleep_learns_its_own_corpus():
    mind = SoulMind("s1", seed=3)
    first, last = mind.sleep(CORPUS, steps=25)
    assert last < first                    # the day was absorbed: loss fell
    assert mind.sleeps == 1


def test_rebirth_is_a_fresh_brain_not_an_inheritance():
    a = SoulMind("stream:1", seed=1)
    b = SoulMind("stream:2", seed=2)       # the wheel hands on karma, never weights
    pa = torch.cat([p.flatten() for p in a.model.parameters()])
    pb = torch.cat([p.flatten() for p in b.model.parameters()])
    assert not torch.equal(pa, pb)


def test_too_little_lived_means_no_dream_yet():
    mind = SoulMind("s2", seed=3)
    assert mind.sleep("a" * (BLOCK // 2)) is None    # an infant keeps babbling
    assert mind.sleeps == 0


def test_save_load_wakes_the_same_brain(tmp_path):
    mind = SoulMind("s3", seed=3)
    mind.sleep(CORPUS, steps=15)
    path = str(tmp_path / "s3.pt")
    mind.save(path)
    woken = SoulMind.load(path)
    assert woken.sleeps == 1
    pa = torch.cat([p.flatten() for p in mind.model.parameters()])
    pb = torch.cat([p.flatten() for p in woken.model.parameters()])
    assert torch.equal(pa, pb)


def test_router_speaks_per_soul_and_prunes_the_departed(tmp_path):
    router = SoulVoiceLLM(minds_dir=str(tmp_path))
    ctx = SpeechContext(name="Vesper", agent_id="s0", persona="a brewer", mood=0.0,
                        drift=["the ale wants patience"])
    line = router.speak(ctx)
    assert isinstance(line, str) and line
    assert "s0" in router.minds
    assert router.mind_for("s0") is router.mind_for("s0")     # one soul, one brain
    assert router.mind_for("s0") is not router.mind_for("s9")  # two souls, two brains
    router.prune(live_ids={"s0"})
    assert "s9" not in router.minds and "s0" in router.minds


def test_sleep_one_snapshot_and_persistence(tmp_path):
    class _Mem:
        def __init__(self, t):
            self.text = t

    class _Store:
        items = [_Mem(ln) for ln in CORPUS.splitlines()]

    class _Soul:
        id, persona = "s7", "You are Cael the fisher."
        memory = _Store()

    router = SoulVoiceLLM(minds_dir=str(tmp_path))
    first, last = router.sleep_one(_Soul)
    assert last < first
    assert os.path.isfile(os.path.join(str(tmp_path), "s7.pt"))   # rests where waking finds it
