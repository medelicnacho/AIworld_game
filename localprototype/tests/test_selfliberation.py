"""Self-liberation (rang drol) tests (deterministic): a fresh charge is felt at arising
then frees itself over the next few ticks; off by default; the prompt carries the move."""

from agent.agent import Agent
from agent.memory import Memory
from services.llm import MockLLM, SpeechContext, build_system


def _agent(sl=0.0):
    a = Agent("s", "S", (0, 0), "p", ["x"], MockLLM(seed=1), seed=1)
    a.self_liberation = sl
    return a


def test_self_liberation_off_by_default():
    assert _agent().self_liberation == 0.0


def test_fresh_charge_is_felt_then_frees():
    a = _agent(sl=0.9)
    a.memory.items = [Memory("a sharp grief", 0.6, created_tick=0, last_touched_tick=0,
                             source="event", emotion=-0.8)]
    m = a.memory.items[0]
    # tick 0 = arising: felt fully (not yet damped)
    assert m.emotion == -0.8
    a.step(now=1)                  # age 1: begins to self-free
    after_one = m.emotion
    assert after_one > -0.8        # the charge is loosening...
    for t in range(2, 6):
        a.step(now=t)
    assert m.emotion > after_one   # ...and keeps dissolving toward neutral
    assert m.emotion > -0.4        # mostly freed within a few ticks


def test_old_charge_is_not_touched():
    # self-liberation acts only at ARISING; an old held charge is left alone
    a = _agent(sl=0.9)
    a.memory.items = [Memory("an old wound", 0.6, created_tick=0, last_touched_tick=0,
                             source="self", emotion=-0.8)]
    m = a.memory.items[0]
    a.step(now=20)                 # age 20 -> not fresh -> untouched by self-liberation
    assert m.emotion == -0.8


def test_off_soul_keeps_the_charge():
    a = _agent(sl=0.0)
    a.memory.items = [Memory("a grief", 0.6, created_tick=0, last_touched_tick=0,
                             source="event", emotion=-0.8)]
    a.step(now=1)
    assert a.memory.items[0].emotion == -0.8


def test_selflib_prompt_is_arising_not_suppression():
    sysp = build_system(SpeechContext(name="S", persona="p", mood=0.0, self_liberation=0.8))
    low = sysp.lower()
    assert "frees itself" in low and "water" in low
    plain = build_system(SpeechContext(name="S", persona="p", mood=0.0, self_liberation=0.0))
    assert "frees itself" not in plain.lower()
