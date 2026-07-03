"""Tests for the faction metrics and the substrate-ablation gate.

The metrics must do two jobs honestly: SEE structure when camps really are
partitioned, and report NONE when the graph is flat -- otherwise an experiment
built on them would always 'find factions'. The ablation gate must truly freeze
the social graph so the null arm of experiment_factions.py is a real control.

Run:  python -m unittest discover -s tests
      python tests/test_factions.py
"""

from __future__ import annotations

import unittest


from agent import belief
from agent.agent import Agent
from services import embed, factions
from services.llm import MockLLM
from world.events import Utterance

embed.use_jaccard_only(True)   # deterministic, Ollama-free (creator_stance in commit_speech)


class StubAgent:
    """Just the surface the metrics read: id, affinity/hostility ledgers, and the
    two fixed labels. Lets us build exact graphs without running the sim."""

    def __init__(self, aid, religion="", temperament=0.0, said_lines=None):
        self.id = aid
        self.religion = religion
        self.temperament = temperament
        self.affinity: dict[str, float] = {}
        self.hostility: dict[str, float] = {}
        self.said_lines = said_lines or []


def _link(a, b, aff=0.0, host=0.0):
    a.affinity[b.id] = aff
    b.affinity[a.id] = aff
    if host:
        a.hostility[b.id] = host
        b.hostility[a.id] = host


def two_camps():
    """Two cohesive camps (A,B,C) and (D,E,F), bonded within, hostile across.
    Faith is aligned with the camps; temperament is CROSSED so the two labels
    can be told apart by the purity measures."""
    A = StubAgent("A", "devout", -0.5)
    B = StubAgent("B", "devout", 0.5)   # crossed temperament
    C = StubAgent("C", "devout", -0.4)
    D = StubAgent("D", "path", 0.5)
    E = StubAgent("E", "path", -0.5)    # crossed temperament
    F = StubAgent("F", "path", 0.4)
    camp1, camp2 = [A, B, C], [D, E, F]
    for camp in (camp1, camp2):
        for i, x in enumerate(camp):
            for y in camp[i + 1:]:
                _link(x, y, aff=0.9)
    for x in camp1:
        for y in camp2:
            _link(x, y, aff=-0.6, host=4.0)
    return camp1 + camp2


class FactionMetricTest(unittest.TestCase):
    def test_blocs_find_two_camps(self):
        groups = factions.blocs(two_camps())
        self.assertEqual(len(groups), 2)
        self.assertEqual({frozenset(g) for g in groups},
                         {frozenset({"A", "B", "C"}), frozenset({"D", "E", "F"})})

    def test_modularity_positive_for_partitioned_graph(self):
        self.assertGreater(factions.modularity(two_camps()), 0.2)

    def test_flat_graph_has_no_structure(self):
        # nobody feels anything about anyone: every soul its own bloc, Q ~ 0
        flat = [StubAgent(x, "devout" if i < 2 else "path", 0.0)
                for i, x in enumerate("ABCD")]
        self.assertEqual(len(factions.blocs(flat)), 4)
        self.assertAlmostEqual(factions.modularity(flat), 0.0, places=6)

    def test_faith_purity_high_when_blocs_are_faiths(self):
        # camps align with faith -> purity 1.0; but cross temperament -> temp
        # purity is only chance-level, which is exactly how we tell them apart
        agents = two_camps()
        self.assertAlmostEqual(factions.purity(agents, factions._faith), 1.0, places=6)
        self.assertLess(factions.purity(agents, factions._temper), 1.0)

    def test_split_by_reports_label_gap(self):
        agents = two_camps()
        _in, _cross, gap = factions.split_by(agents, factions._faith, factions._mutual)
        self.assertGreater(gap, 0.0)            # same-faith bond > cross-faith
        self.assertGreater(_in, _cross)

    def test_summary_has_all_keys(self):
        s = factions.summary(two_camps())
        for k in ("n_blocs", "modularity", "bloc_faith_purity",
                  "bloc_temp_purity", "faith_affinity_gap"):
            self.assertIn(k, s)


class AblationGateTest(unittest.TestCase):
    """The substrate-ablated control must actually freeze the social graph."""

    def _agent(self, learn):
        a = Agent("a", "A", (0.0, 0.0), "a voice", ["x"], MockLLM(seed=1), seed=1)
        a.memory.write("cold dark empty death", tick=0, source="self")  # a stance
        a.social_learning = learn
        return a

    def test_learning_on_moves_affinity(self):
        a = self._agent(learn=True)
        a.hear(Utterance("b", "all is cold and lost", 1, source="ai", mood=-0.6), now=1)
        self.assertNotEqual(a.feels_about("b"), 0.0)

    def test_ablated_freezes_affinity(self):
        a = self._agent(learn=False)
        a.hear(Utterance("b", "all is cold and lost", 1, source="ai", mood=-0.6), now=1)
        self.assertEqual(a.feels_about("b"), 0.0)        # graph frozen
        self.assertEqual(a.hostility, {})

    def test_ablated_still_hears_into_memory(self):
        # ablation must freeze only the SOCIAL graph, not perception itself
        a = self._agent(learn=False)
        before = len(a.memory)
        a.hear(Utterance("b", "all is cold and lost", 1, source="ai", mood=-0.6), now=1)
        self.assertGreater(len(a.memory), before)


class ComembershipTest(unittest.TestCase):
    def test_zero_when_membership_is_fixed(self):
        # same partition every run -> pairs always co-cluster or never -> variance 0
        p = {"A": 0, "B": 0, "C": 1, "D": 1}
        self.assertAlmostEqual(factions.comembership_variance([p, p, p]), 0.0, places=6)

    def test_positive_when_membership_varies(self):
        # A pairs with B in one run, with C in another -> history-dependent
        runs = [{"A": 0, "B": 0, "C": 1}, {"A": 0, "B": 1, "C": 0}]
        self.assertGreater(factions.comembership_variance(runs), 0.0)


class EmergentBondingTest(unittest.TestCase):
    """The bounded-confidence path must (a) only fire when belief_vec is seeded,
    (b) bond on alignment, and (c) actually MOVE the opinion (it's dynamics)."""

    def _agent(self):
        import random as _r
        a = Agent("a", "A", (0.0, 0.0), "v", ["x"], MockLLM(seed=1), seed=1)
        a.seed_opinion(_r.Random(1))
        return a

    def test_seed_opinion_unit_length(self):
        a = self._agent()
        self.assertIsNotNone(a.belief_vec)
        norm = sum(x * x for x in a.belief_vec) ** 0.5
        self.assertAlmostEqual(norm, 1.0, places=6)

    def test_aligned_speaker_bonds_and_pulls_opinion(self):
        a = self._agent()
        before = list(a.belief_vec)
        aligned = tuple(a.belief_vec)                       # identical view -> engage
        a.hear(Utterance("b", "hi", 1, source="ai", belief_vec=aligned), now=1)
        self.assertGreaterEqual(a.feels_about("b"), 0.0)
        self.assertNotEqual(list(a.belief_vec), before)     # opinion moved (dynamics)

    def test_opposed_speaker_cools(self):
        a = self._agent()
        opposed = tuple(-x for x in a.belief_vec)            # antipodal view -> reject
        a.hear(Utterance("c", "no", 1, source="ai", belief_vec=opposed), now=1)
        self.assertLess(a.feels_about("c"), 0.0)

    def test_legacy_path_untouched_without_seed(self):
        # no belief_vec -> the old faith/disposition logic still runs
        a = Agent("a", "A", (0.0, 0.0), "v", ["x"], MockLLM(seed=1), seed=1)
        a.memory.write("cold dark empty death", tick=0, source="self")
        a.hear(Utterance("b", "all is cold and lost", 1, source="ai", mood=-0.6), now=1)
        self.assertNotEqual(a.feels_about("b"), 0.0)


class OpinionLanguageTest(unittest.TestCase):
    """Stage 2: opinion lives in word-space; shared vocabulary points the same way."""

    def _vec(self, text):
        from agent.agent import _normalize
        return _normalize(belief.text_to_opinion(text))

    def test_shared_vocab_aligns(self):
        from agent.agent import _cosine
        a = self._vec("the tide rises and the deep water pulls")
        b = self._vec("water and tide, the deep keeps pulling")
        c = self._vec("stone mountain weight and grinding rock")
        self.assertGreater(_cosine(a, b), 0.4)      # shared words -> aligned
        self.assertLess(_cosine(a, c), 0.2)         # disjoint words -> orthogonal

    def test_tokens_drop_stopwords(self):
        self.assertEqual(belief.tokens("the and of a it"), [])
        self.assertIn("tide", belief.tokens("the tide is high"))

    def test_distinctive_term_is_the_banner(self):
        # 'tide' appears in every in-doc; other words only once -> it dominates
        ins = ["the tide rises", "the tide and the deep", "tide again at noon"]
        outs = ["stone and weight", "the heavy stone"]
        self.assertEqual(belief.distinctive_terms(ins, outs, k=1), ["tide"])


class GroundingTest(unittest.TestCase):
    """Speaking must pull a grounded agent's opinion toward its own words."""

    def test_speech_grounds_opinion(self):
        from agent.agent import _cosine
        a = Agent("a", "A", (0.0, 0.0), "v", ["x"], MockLLM(seed=1), seed=1)
        a.seed_opinion_text("stone and weight")     # start in 'stone' country
        line = "the tide and the deep water"
        before = _cosine(a.belief_vec, _normalize_via(line))
        a.commit_speech(line, now=1, addressed=None, mood=0.0)
        after = _cosine(a.belief_vec, _normalize_via(line))
        self.assertGreater(after, before)            # moved toward what it said
        self.assertIn(line, a.said_lines)


class BannerTest(unittest.TestCase):
    def test_banners_name_each_bloc(self):
        # two camps; one word dominates each camp's speech (others appear once)
        A = StubAgent("A", said_lines=["the tide rises", "tide and current"])
        B = StubAgent("B", said_lines=["tide again", "the tide deepens"])
        C = StubAgent("C", said_lines=["the stone holds", "stone and rock"])
        D = StubAgent("D", said_lines=["stone again", "the grey stone"])
        for x, y in ((A, B), (C, D)):
            x.affinity[y.id] = y.affinity[x.id] = 0.9
        for x in (A, B):
            for y in (C, D):
                x.affinity[y.id] = y.affinity[x.id] = -0.6
        found = set(factions.banners([A, B, C, D]).values())
        self.assertIn("tide", found)
        self.assertIn("stone", found)


class ConfoundMetricTest(unittest.TestCase):
    def test_identical_transcripts_zero_divergence(self):
        import experiment_confound as ec
        t = ["the tide and the deep stone", "stone and tide again"]
        self.assertAlmostEqual(ec.divergence(t, t), 0.0, places=6)

    def test_disjoint_vocab_high_divergence(self):
        import experiment_confound as ec
        a = ["the tide and the deep water"]
        b = ["stone mountain weight rock grinding"]
        self.assertGreater(ec.divergence(a, b), 0.8)


class UpdateCampsTest(unittest.TestCase):
    """World.update_camps must tag each soul with its camp's banner + the rival's."""

    def test_stamps_banner_and_rival(self):
        from world.sim import World
        world = World()
        # 'tide' is the thread through camp 1, 'stone' through camp 2; the other
        # words vary per soul so TF-IDF picks the shared distinctive term
        specs = [("A", ["the tide rises", "tide and current"]),
                 ("B", ["tide at dawn", "the tide deepens"]),
                 ("C", ["the stone holds", "stone and moss"]),
                 ("D", ["stone underfoot", "the grey stone"])]
        for aid, lines in specs:
            a = Agent(aid, aid, (0.0, 0.0), "v", ["x"], MockLLM(seed=1), seed=1)
            a.said_lines = list(lines)
            world.add(a)
        by = {a.id: a for a in world.agents}
        for x, y in (("A", "B"), ("C", "D")):
            by[x].affinity[y] = by[y].affinity[x] = 0.9
        for x in ("A", "B"):
            for y in ("C", "D"):
                by[x].affinity[y] = by[y].affinity[x] = -0.6
        world.update_camps()
        self.assertEqual(by["A"].banner, "tide")
        self.assertEqual(by["C"].banner, "stone")
        self.assertEqual(by["A"].rival_banner, "stone")   # leans against the other camp
        self.assertEqual(by["C"].rival_banner, "tide")


def _normalize_via(text):
    from agent.agent import _normalize
    return _normalize(belief.text_to_opinion(text))


if __name__ == "__main__":
    unittest.main()
