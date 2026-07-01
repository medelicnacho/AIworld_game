"""Tests for the FUNCTIONAL psyche (agent/psyche.py + agent/workspace.py + the world wiring).

Deterministic substrate checks (MockLLM, Jaccard-only). The psyche is PSYCHE.md made live: each part
carries ONE faculty (differential endowment), bids for the mind's floor by that faculty's live state
(activation), and a global workspace with fatigue-with-memory decides who has the floor -- coupling
Dread's presence to the mind's grip, Ache's to how losses persist, and broadcasting the Watcher's
reflections. The wheel, inside a psyche, re-arises a DRIVE (function carried), never a townsperson.
"""

import unittest

from agent import psyche
from agent.agent import Agent
from agent.workspace import Workspace
from services import embed
from services.llm import MockLLM
from world.events import WorldEvent
from world.sim import World


def _part(name, pid=None, llm=None, lifespan=10 ** 9):
    entry = next(e for e in psyche.PSYCHE_CAST if e[0] == name)
    _n, func, temp, aim, seeds = entry
    a = Agent(pid or name.lower(), name, (0.0, 0.0),
              f"You are {name}, {func} -- a part of one mind, not a person.",
              list(seeds), llm or MockLLM(seed=1), seed=abs(hash(name)) % 9999,
              temperament=temp, lifespan=lifespan)
    a.role, a.aim = func, aim
    psyche.endow_part(a, psyche.FACULTY_OF[name], a._rng)
    return a


def _mind(lifespan=10 ** 9, rebirth=False, stakes=True, seed=0):
    w = World(events_enabled=False, rebirth_enabled=rebirth, move_seed=seed)
    w.llm = MockLLM(seed=7)
    w.stakes_enabled = stakes
    w.psyche = Workspace()
    for i, (name, _f, _t, _a, _s) in enumerate(psyche.PSYCHE_CAST):
        w.add(_part(name, pid=f"p{i}", llm=w.llm, lifespan=lifespan))
    return w


class EndowmentTest(unittest.TestCase):
    def setUp(self):
        embed.use_jaccard_only(True)

    def tearDown(self):
        embed.use_jaccard_only(False)

    def test_parts_carry_distinct_faculties(self):
        parts = {n: _part(n) for n in psyche.FACULTY_OF}
        # only the Watcher reflects; only Ember carries the survival floor
        self.assertTrue(parts["Watcher"].reflect_enabled)
        self.assertTrue(parts["Ember"].somatic_enabled)
        for n, p in parts.items():
            if n != "Watcher":
                self.assertFalse(p.reflect_enabled, n)
            if n != "Ember":
                self.assertFalse(p.somatic_enabled, n)
        # each carrier is the LOUDEST holder of its own dial
        self.assertEqual(max(parts, key=lambda n: parts[n].grip), "Dread")
        self.assertEqual(max(parts, key=lambda n: parts[n].compassion), "Tending")
        self.assertEqual(max(parts, key=lambda n: parts[n].telos), "Longing")

    def test_an_ordinary_soul_is_untouched(self):
        a = Agent("t", "Toll", (0, 0), "You are Toll.", ["the charter"], MockLLM(seed=1), seed=1)
        self.assertEqual(a.psyche_faculty, "")
        self.assertEqual(psyche.activation(a, [a]), 0.0)


class ActivationTest(unittest.TestCase):
    def setUp(self):
        embed.use_jaccard_only(True)

    def tearDown(self):
        embed.use_jaccard_only(False)

    def test_dread_rouses_on_a_fresh_blow_not_old_grief(self):
        calm, struck = _part("Dread", pid="d1"), _part("Dread", pid="d2")
        struck.memory.write("someone dear is gone", tick=95, source="event", emotion=-0.85)
        self.assertGreater(psyche.activation(struck, [struck], now=100),
                           psyche.activation(calm, [calm], now=100))
        # the same blow, long past the fresh window -> Dread has stood down
        self.assertEqual(psyche.activation(struck, [struck], now=200),
                         psyche.activation(calm, [calm], now=200))

    def test_ache_holds_the_ledger_dread_only_the_arriving(self):
        ache, dread = _part("Ache"), _part("Dread")
        for p in (ache, dread):
            p.memory.write("the flood took my provisions", tick=10, source="event", emotion=-0.7)
        # old loss: Ache still carries it, Dread (fresh window) does not
        self.assertGreater(psyche.activation(ache, [ache, dread], now=100), 0.0)
        self.assertEqual(psyche.activation(dread, [ache, dread], now=100), 0.0)
        # the mind's own dark mutter is NOT in the loss-ledger (rumination != a blow)
        muttering = _part("Ache", pid="a2")
        muttering.memory.write("the empty chair is mine", tick=10, source="self",
                               speaker_id="a2", emotion=-0.7)
        self.assertEqual(psyche.activation(muttering, [muttering]), 0.0)

    def test_longing_is_the_wanting_gap(self):
        far, near = _part("Longing", pid="l1"), _part("Longing", pid="l2")
        near.aim_progress = 0.9
        self.assertGreater(psyche.activation(far, [far]), psyche.activation(near, [near]))

    def test_tending_hears_a_suffering_sibling(self):
        tending = _part("Tending")
        dark = _part("Dread")   # temperament -0.5 -> felt dark
        dark.memory.write("everything is breaking", tick=0, source="self",
                          speaker_id=dark.id, emotion=-0.9)
        bright = _part("Ember")  # temperament +0.4 -> felt light
        with_pain = psyche.activation(tending, [tending, dark])
        without = psyche.activation(tending, [tending, bright])
        self.assertGreater(with_pain, without)


class WorkspaceTest(unittest.TestCase):
    def test_fatigue_forces_turnover_not_a_frozen_note(self):
        ws = Workspace()
        winners = []
        for _ in range(300):
            ws.observe({"a": 1.0, "b": 0.5, "c": 0.3})
            winners.append(ws.reigning_id())
        # the loudest DOMINATES but does not freeze: the floor changes hands...
        self.assertGreater(sum(1 for i in range(1, 300) if winners[i] != winners[i - 1]), 10)
        # ...and dominance tracks loudness (regression: the share-penalty formula
        # had a fixed point where the QUIETEST part held the floor forever)
        counts = {k: winners.count(k) for k in ("a", "b", "c")}
        self.assertEqual(max(counts, key=counts.get), "a")

    def test_equal_bids_share_the_floor(self):
        ws = Workspace()
        winners = []
        for _ in range(300):
            ws.observe({"a": 1.0, "b": 1.0, "c": 1.0})
            winners.append(ws.reigning_id())
        counts = {k: winners.count(k) for k in ("a", "b", "c")}
        self.assertGreater(min(counts.values()), 50)

    def test_names_and_coalition(self):
        ws = Workspace()
        ws.names = {"a": "Dread", "b": "Ache"}
        for _ in range(5):
            ws.observe({"a": 1.0, "b": 0.8})
        self.assertIn(ws.reigning(), ("Dread", "Ache"))
        self.assertEqual(set(ws.coalition(2)), {"Dread", "Ache"})


class MindIntegrationTest(unittest.TestCase):
    def setUp(self):
        embed.use_jaccard_only(True)

    def tearDown(self):
        embed.use_jaccard_only(False)

    def test_the_workspace_runs_and_the_floor_is_a_part(self):
        w = _mind()
        for _ in range(60):
            w.step()
        names = {a.name for a in w.agents}
        self.assertTrue(w.psyche.log)
        self.assertTrue(set(w.psyche.log) <= names)

    def test_dreads_presence_raises_the_minds_grip(self):
        w = _mind(stakes=False)
        dread = next(a for a in w.agents if a.psyche_faculty == "grip")
        others = [a for a in w.agents if a.psyche_faculty not in ("grip", "")]
        for m in range(6):   # blows land on the mind -> Dread's presence becomes tension
            dread.memory.write(f"disaster struck us, wave {m}", tick=0,
                               source="event", emotion=-0.9)
        for _ in range(30):
            w.step()
        self.assertTrue(any(p.grip > p._psyche_base_grip + 1e-6 for p in others))

    def test_ache_holds_the_minds_losses_against_decay(self):
        # identical grieving part; with the workspace (Ache present) the loss keeps
        # more salience than under plain decay
        def run(with_workspace):
            w = _mind(stakes=False)
            if not with_workspace:
                w.psyche = None
            ember = next(a for a in w.agents if a.psyche_faculty == "somatic")
            m = ember.memory.write("the frost took the one I kept the coal for", tick=0,
                                   source="event", emotion=-0.8)
            for _ in range(40):
                w.step(speak=False)
            return m.salience
        self.assertGreater(run(True), run(False))

    def test_the_watchers_seeing_is_broadcast_mind_wide(self):
        w = _mind(stakes=False)
        watcher = next(a for a in w.agents if a.psyche_faculty == "reflect")
        watcher.memory.write("the whole of us is heavy tonight", tick=0,
                             source="self", speaker_id=watcher.id, emotion=-0.5)
        text = w.reflect_turn()
        self.assertTrue(text)
        others = [a for a in w.agents if a is not watcher]
        self.assertTrue(any(m.source == "reflection" and m.speaker_id == watcher.id
                            for p in others for m in p.memory.items))


class PsycheWheelTest(unittest.TestCase):
    def setUp(self):
        embed.use_jaccard_only(True)

    def tearDown(self):
        embed.use_jaccard_only(False)

    def test_a_reborn_part_is_a_drive_not_a_tradesman(self):
        w = _mind(lifespan=25, rebirth=True, stakes=False)
        w.bardo_ticks = (3, 6)
        for _ in range(120):
            w.step(speak=False)
        reborn = [a for a in w.agents if a.id.startswith("stream:")]
        self.assertTrue(reborn)
        for a in reborn:
            self.assertIn(a.psyche_faculty, psyche.FUNCTION_OF)          # the function re-arose
            self.assertEqual(a.role, psyche.FUNCTION_OF[a.psyche_faculty])  # not a trade
            self.assertEqual(a.aim, psyche.AIM_OF[a.psyche_faculty])

    def test_an_ordinary_wheel_is_untouched(self):
        # no workspace -> the plain wheel: reborn streams get trades, as before
        w = World(events_enabled=False, rebirth_enabled=True, move_seed=1)
        w.llm = MockLLM(seed=7)
        a = Agent("s0", "Toll", (0, 0), "You are Toll.", ["the charter waits"],
                  MockLLM(seed=1), seed=1, lifespan=10)
        w.add(a)
        w.bardo_ticks = (2, 3)
        for _ in range(30):
            w.step(speak=False)
        reborn = [x for x in w.agents if x.id.startswith("stream:")]
        self.assertTrue(reborn)
        self.assertEqual(reborn[0].psyche_faculty, "")
        self.assertNotIn(reborn[0].role, psyche.FUNCTION_OF.values())


if __name__ == "__main__":
    unittest.main()
