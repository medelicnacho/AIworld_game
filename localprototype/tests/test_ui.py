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


def test_the_bridge_acts_land_on_validated_organs_only():
    """apply_act routes deeds to witness, promises to pledge, and refuses anything
    else -- a game can only touch the town through the measured karma roads."""
    w = _town()
    out = ui.apply_act(w, {"kind": "deed", "act": "kindness"})
    assert out["ok"] and out["witnessed_by"] == 3          # placeless: seen by all
    assert all(a._conduct_expect.get("player", 0) > 0 for a in w.agents)
    out = ui.apply_act(w, {"kind": "pledge", "to": "s1",
                           "text": "I will bring what you need", "due_ticks": 50})
    assert out["ok"] and w.agents[1].promises_held
    out = ui.apply_act(w, {"kind": "fulfill", "to": "s1"})
    assert out["ok"] and out["kept"]
    assert not ui.apply_act(w, {"kind": "smite", "to": "s1"})["ok"]     # no such road
    assert not ui.apply_act(w, {"kind": "deed", "act": "arson"})["ok"]  # no such deed


def test_the_muster_payload_carries_names_and_reasons():
    from agent.bond import Bond
    w = _town()
    w.agents[0].bonds["player"] = Bond(trust=0.8, history=2.5)
    w.agents[1]._conduct_expect["player"] = -0.6
    m = ui.muster_payload(w, "player", 0.2)
    assert {a["name"] for a in m["join"]} == {"Vesper"}
    assert {a["name"] for a in m["oppose"]} == {"Mara"}
    assert len(m["reasons"]) == 3 and all(isinstance(r, str) for r in m["reasons"].values())
