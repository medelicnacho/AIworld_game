"""Telos (chanda) tests -- deterministic. Tending an aim advances progress and lays a pleasant
charge; a setback knocks progress back and lays an aversive one. (How the faculties MEET those
charges -- chanda vs taṇhā -- is the experiment's job; here we pin the mechanism.)"""

import pytest

from agent import telos
from agent.agent import Agent
from services import embed
from services.llm import MockLLM


@pytest.fixture(autouse=True)
def _jaccard():
    embed.use_jaccard_only(True)
    yield
    embed.use_jaccard_only(False)


def _soul(telos_=0.7, aim="brew an ale worth a festival"):
    a = Agent("s", "S", (0, 0), "p", ["x"], MockLLM(seed=1), seed=1)
    a.telos, a.aim = telos_, aim
    return a


def test_off_by_default():
    a = Agent("x", "X", (0, 0), "p", ["x"], MockLLM(seed=1), seed=1)
    assert a.telos == 0.0 and a.aim == "" and a.aim_progress == 0.0


def test_pursue_advances_and_gladdens():
    a = _soul()
    telos.pursue(a, now=1)
    assert a.aim_progress > 0.0                                   # the work came on a little
    glad = next(m for m in a.memory.items if "tended my aim" in m.text)
    assert glad.emotion > 0.0                                     # a gladness of the work (savoured by joy)


def test_pursue_noop_without_telos_or_aim():
    a = _soul(telos_=0.0)
    telos.pursue(a, now=1)
    assert a.aim_progress == 0.0                                  # no aspiration -> the static present
    b = _soul(aim="")
    telos.pursue(b, now=1)
    assert b.aim_progress == 0.0


def test_pursue_stops_at_completion():
    a = _soul()
    a.aim_progress = 1.0
    telos.pursue(a, now=1)
    assert a.aim_progress == 1.0                                  # reached -> rest, no overshoot


def test_setback_knocks_back_and_charges():
    a = _soul()
    a.aim_progress = 0.8
    telos.setback(a, now=5, severity=0.4, what="the mash soured")
    assert abs(a.aim_progress - 0.4) < 1e-9                       # progress lost
    wound = next(m for m in a.memory.items if "undone" in m.text)
    assert wound.emotion < 0.0                                    # an aversive charge the faculties meet


def test_setback_floors_at_zero():
    a = _soul()
    a.aim_progress = 0.2
    telos.setback(a, now=5, severity=0.5)
    assert a.aim_progress == 0.0


def test_step_pursues_when_enabled():
    # the live hook: a telos soul tends its aim each step
    a = _soul()
    p0 = a.aim_progress
    a.step(1)
    assert a.aim_progress > p0


# --- lineage across the wheel: the thirst (not the self) transmigrates ---

def test_reborn_telos_clinging_carries_more_than_wisdom():
    clinging = telos.reborn_telos(dead_telos=0.7, effective_grip=0.7)   # gripped its becoming
    wise = telos.reborn_telos(dead_telos=0.7, effective_grip=0.05)      # held it lightly
    assert clinging > wise                                              # taṇhā drags the thirst onward
    assert wise <= telos.LINEAGE_BASE + 0.05                            # wisdom carries almost none


def test_reborn_telos_floor_and_bounds():
    assert telos.reborn_telos(0.0, 0.0) == telos.LINEAGE_BASE           # nothing clung -> a fresh modest aim
    for dt in (0.0, 0.5, 1.0):
        for eg in (0.0, 0.5, 1.0):
            assert 0.0 <= telos.reborn_telos(dt, eg) <= 1.0


def test_thirst_escalates_under_clinging_settles_under_wisdom():
    # iterate the wheel: a clinging lineage climbs, a wise one settles
    t_cling = t_wise = 0.5
    for _ in range(6):
        t_cling = telos.reborn_telos(t_cling, effective_grip=0.75)
        t_wise = telos.reborn_telos(t_wise, effective_grip=0.09)
    assert t_cling > 0.8           # the hungry wheel spins faster
    assert t_wise < 0.4            # the wise lineage rests
