"""Stage-3 self-model loop tests (deterministic, MockLLM).

Pins the wiring: consolidate() reads self-memory, writes a self-model back, records
history, and is a no-op with nothing to take stock of; the self-model feeds into the
prompt. The semantic coherence/distinctness signature is shown live by
experiment_selfmodel.py (needs a model)."""

from agent import self_model as sm
from agent.agent import Agent
from services.llm import MockLLM, SpeechContext, build_system


def _agent():
    llm = MockLLM(seed=1)
    a = Agent("self", "Aldous", (0.0, 0.0), "a quiet life", ["a quiet life"],
              llm, seed=1, temperament=0.0)
    return a, llm


def test_consolidate_writes_self_model_and_history():
    a, llm = _agent()
    a.memory.write("I came from the river country", tick=1, source="self",
                   speaker_id="self")
    text = sm.consolidate(a, llm, now=2)
    assert text
    assert a.self_model == text
    assert a.self_model_history == [text]
    assert any(m.source == "self" and m.text == text for m in a.memory.items)


def test_consolidate_noop_without_self_memory():
    llm = MockLLM(seed=1)
    a = Agent("self", "A", (0, 0), "p", [], llm, seed=1)   # only doctrine memories
    assert sm.consolidate(a, llm, now=1) is None


def test_self_model_defaults_off_and_empty():
    a, _ = _agent()
    assert a.self_model_enabled is False
    assert a.self_model == "" and a.self_model_history == []


def test_self_model_feeds_into_prompt():
    sys_with = build_system(SpeechContext(name="A", persona="p", mood=0.0,
                                          self_model="I am one who tends lamps at dusk"))
    assert "tends lamps at dusk" in sys_with
    sys_without = build_system(SpeechContext(name="A", persona="p", mood=0.0))
    assert "understand yourself as" not in sys_without


def test_consolidation_builds_on_prior_self_model():
    a, llm = _agent()
    a.memory.write("I grew up among bells", tick=1, source="self", speaker_id="self")
    sm.consolidate(a, llm, now=2)
    sm.consolidate(a, llm, now=10)
    assert len(a.self_model_history) == 2   # the loop runs again, building on the last


def test_reborn_stream_has_self_faculties():
    # a stream that coalesces from the bardo carries the faculties of a self (so a
    # self can RE-form), though no self-model autobiography crosses the gap.
    from world.sim import World
    w = World(rebirth_enabled=True)
    w.llm = MockLLM(seed=1)
    w.bardo_ticks = (1, 1)
    a = Agent("A", "A", (0, 0), "p", ["x"], w.llm, seed=1)
    w.add(a)
    a.age, a.lifespan = 0, 1
    w.step()
    streams = [x for x in w.agents if x.id.startswith("stream:")]
    assert streams
    assert streams[0].self_model_enabled and streams[0].bond_enabled
    assert streams[0].self_model == ""        # no autobiography crossed
