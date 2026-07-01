"""Tests for lore -- gossip that mutates into legend (agent/lore.py).

Deterministic substrate checks (MockLLM, Jaccard-only). Lore must: stay OFF by default,
carry provenance (Memory.lore_id) through perceive/write/merge and stakes hardships,
transmit the teller's CURRENT text to a few nearby hearers (fanout, range), re-engrave
the teller's own copy (rehearsal), and keep the chain alive past its first holder.
"""

import unittest

from agent import lore
from agent.agent import Agent
from services import embed
from services.llm import MockLLM
from world.events import WorldEvent
from world.sim import World

STORY = "the great flood in the night took the miller's child and half the winter stores"


def _soul(pid, pos=(0.0, 0.0)):
    return Agent(pid, pid.capitalize(), pos, "You are a working soul.", ["the same streets"],
                 MockLLM(seed=1), seed=hash(pid) % 9999, temperament=0.0, lifespan=10 ** 9)


def _world(*souls, lore_on=True, seed=3):
    w = World(events_enabled=False, move_seed=seed)
    w.llm = MockLLM(seed=7)
    w.lore_enabled = lore_on
    for s in souls:
        w.add(s)
    return w


class ProvenanceTest(unittest.TestCase):
    def setUp(self):
        embed.use_jaccard_only(True)

    def tearDown(self):
        embed.use_jaccard_only(False)

    def test_memories_carry_no_tag_by_default(self):
        a = _soul("a")
        m = a.memory.write("an ordinary day at the well", tick=1, source="self")
        self.assertEqual(m.lore_id, "")

    def test_perceive_tags_from_the_event(self):
        a = _soul("a")
        a.perceive(WorldEvent(name="flood", description=STORY, tick=1,
                              emotion=-0.7, lore_id="the-flood"), now=1)
        m = next(m for m in a.memory.items if m.text == STORY)
        self.assertEqual(m.lore_id, "the-flood")

    def test_a_merge_inherits_the_tag(self):
        a = _soul("a")
        a.memory.write(STORY, tick=1, source="event")               # untagged resident
        m = a.memory.write(STORY, tick=2, source="lore", lore_id="the-flood")
        self.assertEqual(m.lore_id, "the-flood")

    def test_a_noticeably_fuller_telling_repairs_a_decayed_copy(self):
        a = _soul("a")
        decayed = "the great flood in the night took the child and half winter stores"
        mine = a.memory.write(decayed, tick=1, source="lore", lore_id="the-flood")
        a.memory.write(STORY, tick=2, source="lore", lore_id="the-flood")   # a better teller
        self.assertEqual(mine.text, STORY)
        # ...but small drift is NOT corrected (the margin): a one-word-fuller telling
        # leaves my version alone, so legends keep drifting instead of freezing
        b = _soul("b")
        near = "great flood in the night took the miller's child and half the winter stores"
        bm = b.memory.write(near, tick=1, source="lore", lore_id="the-flood")
        b.memory.write(STORY, tick=2, source="lore", lore_id="the-flood")
        self.assertEqual(bm.text, near)

    def test_a_stakes_hardship_is_a_story_seed(self):
        from world import stakes
        w = _world(_soul("a"), _soul("b"), lore_on=False)
        stakes.hardship(w, list(w.agents), now=5, kind="flood")
        m = next(m for m in w.agents[0].memory.items if "took my provisions" in m.text)
        self.assertEqual(m.lore_id, "flood:5")


class RetellTest(unittest.TestCase):
    def setUp(self):
        embed.use_jaccard_only(True)

    def tearDown(self):
        embed.use_jaccard_only(False)

    def _witnessed(self, pid, pos=(0.0, 0.0)):
        a = _soul(pid, pos)
        a.perceive(WorldEvent(name="flood", description=STORY, tick=1,
                              emotion=-0.7, lore_id="the-flood"), now=1)
        return a

    def test_off_by_default_nothing_is_retold(self):
        w = _world(self._witnessed("a"), _soul("b"), lore_on=False)
        for _ in range(120):
            w.step(speak=False)
        self.assertFalse(any(m.source == "lore" for m in w.agents[1].memory.items))

    def test_a_story_reaches_a_nearby_hearer_with_its_tag(self):
        w = _world(self._witnessed("a"), _soul("b"))
        for _ in range(120):
            w.step(speak=False)
        got = [m for m in w.agents[1].memory.items if m.lore_id == "the-flood"]
        self.assertTrue(got)
        self.assertEqual(got[0].source, "lore")

    def test_a_story_does_not_carry_beyond_range(self):
        w = _world(self._witnessed("a"), _soul("far", pos=(5000.0, 5000.0)))
        for _ in range(120):
            w.step(speak=False)
        self.assertFalse(any(getattr(m, "lore_id", "") for m in w.agents[1].memory.items))

    def test_telling_re_engraves_the_teller(self):
        a = self._witnessed("a")
        w = _world(a, _soul("b"))
        story = lore.pick(a)
        story.salience = 0.2
        a._retell_cd = 1                       # tells on the next pass
        lore.retell(w)
        self.assertGreater(story.salience, 0.2)

    def test_the_hearer_receives_the_tellers_current_drifted_text(self):
        a = self._witnessed("a")
        story = lore.pick(a)
        story.text = "the flood in the dark took the child and the stores"   # already drifted
        w = _world(a, _soul("b"))
        a._retell_cd = 1
        lore.retell(w)
        got = next(m for m in w.agents[1].memory.items if m.lore_id == "the-flood")
        self.assertEqual(got.text, story.text)   # the VERSION travels, not the original

    def test_the_chain_survives_its_first_holder(self):
        a = self._witnessed("a")
        b, c = _soul("b"), _soul("c")
        w = _world(a, b, c)
        for _ in range(150):
            w.step(speak=False)
        w.agents.remove(a)                      # the witness is gone
        for x in (b, c):                        # strip anything c may already hold,
            pass                                # then let B carry the chain onward
        c.memory.items = [m for m in c.memory.items if not getattr(m, "lore_id", "")]
        for _ in range(150):
            w.step(speak=False)
        self.assertTrue(any(getattr(m, "lore_id", "") == "the-flood"
                            for m in c.memory.items))

    def test_pick_prefers_the_most_salient_story(self):
        a = self._witnessed("a")
        a.memory.write("a small tale of the broken cart", tick=2, source="lore",
                       weight=0.2, lore_id="the-cart")
        self.assertEqual(lore.pick(a).lore_id, "the-flood")
        self.assertIsNone(lore.pick(_soul("empty")))


if __name__ == "__main__":
    unittest.main()
