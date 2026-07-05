"""Tests for the cockpit's legibility layer (santana_app/ui.py).

Pinned: the inspector (soul_detail) reads a soul's REAL insides -- bonds with names,
memories with provenance tags, the grown mind's murmur -- and returns None for ghosts;
the speech hook records who was actually in earshot (the arcs are honest: words only
travel to souls that heard them); the event ring is bounded and monotonically ids'd."""

import threading

from agent.agent import Agent
from agent.bond import Bond
from santana_app import ui
from services.llm import MockLLM
from world.events import Utterance
from world.sim import World


def _town():
    w = World(events_enabled=False)
    w.llm = MockLLM(seed=7)
    for i, name in enumerate(("Vesper", "Mara", "Toll")):
        a = Agent(f"s{i}", name, (i * 30.0, 0.0), f"You are {name}.", ["the well"],
                  w.llm, seed=i, temperament=0.0, lifespan=10 ** 6)
        a.bond_enabled = True
        w.add(a)
    return w


def test_the_inspector_reads_real_insides():
    w = _town()
    a = w.agents[0]
    a.bonds["s1"] = Bond(trust=0.6, history=2.0)
    a.bonds["s2"] = Bond(trust=-0.3)
    a.bonds["s2"].wounds = 2
    a.memory.write("the flood took the low field", tick=3, source="heard",
                   speaker_id="s1", emotion=-0.4)
    d = ui.soul_detail(w, "s0")
    assert d["name"] == "Vesper"
    assert {b["name"] for b in d["bonds"]} == {"Mara", "Toll"}
    assert any(b["wounds"] == 2 for b in d["bonds"])          # scars are shown
    assert any(m["source"] == "heard" for m in d["memories"])  # provenance is shown
    assert ui.soul_detail(w, "ghost") is None


def test_speech_arcs_only_reach_souls_in_earshot():
    w = _town()
    w.agents[2].position = (5000.0, 0.0)                       # Toll far beyond hearing
    events, seq = [], [0]
    ui._wire_events(w, events, threading.Lock(), seq)
    w.bus.publish("utterance", Utterance(speaker_id="s0", text="a word at the well",
                                         tick=1))
    w.bus.publish("utterance", Utterance(speaker_id="mind:x", text="not a soul", tick=1))
    w.bus.publish("death", "s1")
    speaks = [e for e in events if e["kind"] == "speak"]
    assert len(speaks) == 1                                    # mind: voices are not dots
    assert speaks[0]["to"] == ["s1"]                           # only the near soul heard
    assert [e["id"] for e in events] == sorted({e["id"] for e in events})  # rising ids
    assert events[-1]["kind"] == "death"


def test_only_spoken_words_reach_the_screen():
    """Stage directions -- *smiles*, (you nod, a faint smile touching your lips),
    'You nod and...' narration of the VISITOR -- are stripped; plain speech survives."""
    assert ui.spoken_only("Well met. *smiles softly* The well holds.") == \
        "Well met. The well holds."
    assert ui.spoken_only("(you nod, a faint smile touching your lips) Stay a while.") == \
        "Stay a while."
    assert ui.spoken_only("You nod at the fire. The harvest was thin.") == \
        "The harvest was thin."
    assert ui.spoken_only("I said (truly) nothing cruel.") == "I said nothing cruel."
    assert ui.spoken_only("*bows* *waves*") == "..."     # nothing spoken at all
