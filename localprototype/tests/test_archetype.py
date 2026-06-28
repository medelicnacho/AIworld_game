"""Archetype tests (deterministic): six distinct selves, applied as a bundle of dials +
voice + value-lean, overlaid onto a soul (overriding the uniform defaults)."""

import math
import random

from agent import archetype as arch
from agent import genesis
from agent.agent import Agent
from services.llm import MockLLM


def test_six_distinct_archetypes():
    names = [a.name for a in arch.ARCHETYPES]
    assert len(names) == 6 and len(set(names)) == 6


def test_apply_stamps_dials_voice_and_stance():
    a = Agent("x", "X", (0, 0), "p", ["x"], MockLLM(seed=1), seed=1)
    grasper = arch.BY_NAME["Grasper"]
    arch.apply(a, grasper)
    assert a.grip == grasper.grip and a.prajna == grasper.prajna
    assert a.compassion == grasper.compassion and a.style == grasper.style
    assert a.ground_enabled is True
    assert a.stance_vec is not None
    assert abs(math.sqrt(sum(x * x for x in a.stance_vec)) - 1.0) < 1e-6   # normalized


def test_archetypes_actually_differ_on_dials():
    g, s = arch.BY_NAME["Grasper"], arch.BY_NAME["Sage"]
    assert g.grip > s.grip            # the Grasper clings, the Sage doesn't
    assert s.prajna > g.prajna        # the Sage sees through, the Grasper doesn't
    assert arch.BY_NAME["Lover"].compassion > arch.BY_NAME["Skeptic"].compassion


def test_assign_spans_the_cast():
    rng = random.Random(0)
    six = arch.assign(rng, 6)
    assert len({a.name for a in six}) == 6        # one of each when the cast fits
    eight = arch.assign(random.Random(0), 8)
    assert len(eight) == 8                         # cycles once they run out


def test_liberated_is_out_of_the_samsara_rotation():
    # the bodhisattva config must NOT be sprinkled into the watchable, dramatic cast
    assert "Liberated" not in [a.name for a in arch.ARCHETYPES]
    assert "Liberated" in arch.BY_NAME            # but still reachable by name (for inhabit.py)


def test_liberated_config_feels_but_does_not_grasp():
    lib = arch.LIBERATED
    # non-grasping: lower grip than the clinging archetypes...
    assert lib.grip < arch.BY_NAME["Grasper"].grip
    # ...yet NOT zero -- it keeps contact (a feeling self, not the checked-out near enemy)
    assert lib.grip > 0.0
    # leans transmutation + self-liberation + wisdom (metabolize, don't amplify)
    assert lib.transmute >= 0.8 and lib.self_liberation >= 0.6 and lib.prajna >= 0.6
    # WARM, not cold equanimity: high compassion AND bodhicitta (the anti-indifference wing)
    assert lib.compassion >= 0.8 and lib.bodhicitta >= 0.8
    assert lib.temperament > 0.0                   # gently warm by nature


def test_seed_agent_applies_archetype_over_defaults():
    a = Agent("s", "S", (0, 0), "p", [], MockLLM(seed=1), seed=1)
    ch = genesis.Character(name="Mara", temperament=0.0, lines=["I tend the lamps"],
                           conviction="I believe in steady work")
    genesis.seed_agent(a, ch, archetype=arch.BY_NAME["Sage"])
    assert a.prajna == arch.BY_NAME["Sage"].prajna   # archetype overrode the genesis default 0.4
    assert a.style == arch.BY_NAME["Sage"].style
