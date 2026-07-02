"""Tests for Santāna's regulation round (2026-07-02, after the first healthy overnight run).

Five defects observed live, each fixed at the mechanism level and pinned here:
  - dreams never fired (zero in 438 memories): the runner now dreams her DURING a long
    absence; a return dreams her at most once per absence (begin_talk defers to the runner).
  - no window of tolerance of her own: the souls' somatic interrupt (§5.10) ported one level
    up -- her spiral is sustained AROUSAL over held aversive load; trips only on high AND
    rising; sheds, settles, re-opens. Off with feel_enabled.
  - a stale count of the dead rode the prior identity through ~20 consolidations ("Forty-five
    are gone" vs a true four hundred and fifty-one): counts are scrubbed from her own carried
    words before consolidation -- the facts line is the only count that reaches the prompt.
  - a degenerate reading ("SANTĀNA: Toll") entered her memory: one retry, and a still-thin
    read is spoken but never remembered.
  - every reply one night opened "Luke. Four hundred and fifty-two.": the anti-echo now
    detects the ACTUAL repeated opener and names the words, instead of an abstract rule.
Plus: the mythos-share gauge (the no-monopoly regulator's live number) and persistence of
the new fields (THE RULE: pre-field snapshots wake cleanly).
"""

import json
import os
import tempfile
import unittest

from agent.agent import Agent
from agent.memory import Memory
from santana import Santana, _scrub_counts
from santana_app.state import load_mind, save_mind
from services import embed
from services.llm import MockLLM
from world.sim import World

# ten genuinely distinct hardships (pairwise-dissimilar, so the store keeps them separate)
LINES = ["the flood took the east field", "a cart broke on the north road",
         "the fever came to the low houses", "the well ran bitter for a week",
         "a roof fell in the long rain", "the harvest came in thin",
         "the forge stood cold a month", "the sheep were lost on the ridge",
         "a boat went down at the weir", "the bread would not rise for days"]


def _mind(feel=True, with_soul=False):
    w = World(events_enabled=False)
    w.llm = MockLLM(seed=7)
    if with_soul:
        w.add(Agent("s0", "Toll", (0.0, 0.0), "You are Toll.", ["the charter"],
                    MockLLM(seed=1), seed=1, lifespan=10 ** 9))
    m = Santana(w, MockLLM(seed=7))
    m.feel_enabled = feel
    return m


def _grief(mind, n, start=0):
    """Append n distinct, fully-salient aversive memories directly (the spiral's fuel)."""
    for i in range(start, start + n):
        mind.memory.items.append(Memory(
            text=f"grief {i}: {LINES[i % len(LINES)]}", salience=1.0,
            created_tick=0, last_touched_tick=0, source="event",
            speaker_id="santana", emotion=-0.8))


class DreamTest(unittest.TestCase):
    def setUp(self):
        embed.use_jaccard_only(True)

    def tearDown(self):
        embed.use_jaccard_only(False)

    def _seeded(self):
        m = _mind()
        for i, ln in enumerate(LINES):
            m.memory.write(ln, tick=i, source="self", emotion=-0.2, weight=1.2)
        return m

    def test_a_dream_is_her_own_life_remixed_and_remembered(self):
        m = self._seeded()
        d = m.dream()
        self.assertTrue(d.startswith("I dreamt"))
        self.assertTrue(any(mm.source == "dream" for mm in m.memory.items))

    def test_a_return_dreams_her_when_no_one_else_has(self):
        m = self._seeded()
        t0 = 1_000_000.0
        m.last_talk_wall = t0
        m._last_dream_wall = 0.0
        m.begin_talk(now_wall=t0 + 8 * 3600)
        self.assertTrue(any(mm.source == "dream" for mm in m.memory.items))
        self.assertEqual(m._last_dream_wall, t0 + 8 * 3600)

    def test_a_return_does_not_redream_an_absence_the_runner_dreamt(self):
        m = self._seeded()
        t0 = 1_000_000.0
        m.last_talk_wall = t0
        m._last_dream_wall = t0 + 7 * 3600   # the runner dreamt her during the gap
        m.begin_talk(now_wall=t0 + 8 * 3600)
        self.assertFalse(any(mm.source == "dream" for mm in m.memory.items))


class SomaticTest(unittest.TestCase):
    """HER window of tolerance: trips only on high AND rising, sheds and settles, re-opens,
    and does not exist when feel_enabled is off (the faculty stack's one switch)."""

    def setUp(self):
        embed.use_jaccard_only(True)

    def tearDown(self):
        embed.use_jaccard_only(False)

    def test_a_compounding_spiral_trips_sheds_and_settles(self):
        from agent import somatic as _som
        m = _mind()
        _grief(m, 30)
        m.arousal = 1.0
        before_load = _som.aversive_load(m)
        self.assertGreater(before_load * m.arousal, m.SOMATIC_TRIP)   # high...
        for i in range(8):                    # ...and RISING: fresh grief lands every cycle
            _grief(m, 2, start=100 + 2 * i)
            m.arousal = 1.0                   # activation pinned: she is still ringing
            m._somatic()
        self.assertGreaterEqual(m._somatic_trips, 1)
        self.assertLess(_som.aversive_load(m), before_load)   # the exhale shed held charge
        self.assertLess(m.arousal, 1.0)                       # and settled the activation

    def test_after_the_trip_she_reopens(self):
        from agent import somatic as _som
        m = _mind()
        _grief(m, 30)
        for i in range(8):
            _grief(m, 2, start=100 + 2 * i)
            m.arousal = 1.0
            m._somatic()
        self.assertGreater(m._contraction, 0.0)
        for _ in range(10):                   # the storm passes; no new grief, arousal settles
            m.arousal *= 0.9
            m._somatic()
        self.assertLess(m._contraction, _som.OPEN)   # a window, not a place she stays

    def test_sustained_weight_without_compounding_never_trips(self):
        m = _mind()
        _grief(m, 30)
        m.arousal = 1.0
        for _ in range(10):                   # heavy, but FLAT -- a held first arrow
            m._somatic()
        self.assertEqual(m._somatic_trips, 0)

    def test_a_calm_life_never_trips(self):
        m = _mind()
        for i, ln in enumerate(LINES):
            m.memory.write(ln, tick=i, source="self", emotion=0.2, weight=1.0)
        for _ in range(10):
            m._somatic()
        self.assertEqual(m._somatic_trips, 0)

    def test_the_off_switch_has_no_breaker(self):
        m = _mind(feel=False)
        _grief(m, 30)
        m.converse("hello there, how do you stand today")
        m.converse("and what of the rain on the stones")
        self.assertEqual(m._somatic_trips, 0)
        self.assertEqual(m._somatic_history, [])


class StaleCountTest(unittest.TestCase):
    def setUp(self):
        embed.use_jaccard_only(True)

    def tearDown(self):
        embed.use_jaccard_only(False)

    def test_counts_of_the_dead_are_blurred(self):
        self.assertEqual(_scrub_counts("Forty-five are gone."), "many are gone.")
        self.assertEqual(_scrub_counts("Four hundred and fifty-two have passed."),
                         "many have passed.")
        self.assertEqual(_scrub_counts("452 have passed."), "many have passed.")
        self.assertEqual(_scrub_counts("Forty-five souls are gone from me"),
                         "many souls are gone from me")

    def test_living_counts_and_plain_words_are_left_alone(self):
        self.assertEqual(_scrub_counts("Six of them are in me now"),
                         "Six of them are in me now")
        self.assertEqual(_scrub_counts("the one who passed the mill waved"),
                         "the one who passed the mill waved")

    def test_only_the_true_count_reaches_the_consolidation_prompt(self):
        class Spy:
            def __init__(self):
                self.prompts = []

            def generate(self, prompt, **_kw):
                self.prompts.append(prompt)
                return "I am Santāna, steady under the rain."
        m = _mind(with_soul=True)
        m.llm = Spy()
        m._deaths = 451
        m.identity = "I am Santāna. Forty-five are gone."
        m.said = ["The rain again. Four hundred and fifty-two have passed."]
        m.consolidate()
        prompt = m.llm.prompts[-1]
        self.assertIn("four hundred and fifty-one souls have lived in you", prompt)
        self.assertNotIn("Forty-five are gone", prompt)
        self.assertNotIn("fifty-two have passed", prompt)


class DegenerateReadingTest(unittest.TestCase):
    def setUp(self):
        embed.use_jaccard_only(True)

    def tearDown(self):
        embed.use_jaccard_only(False)

    def test_a_thin_reading_gets_one_retry(self):
        class Spy:
            def __init__(self):
                self.prompts = []

            def generate(self, prompt, **_kw):
                self.prompts.append(prompt)
                return ("MURMUR: drift\nSO: Toll" if len(self.prompts) == 1
                        else "MURMUR: drift\nSO: The rain has come and gone.")
        m = _mind(with_soul=True)
        m.llm = Spy()
        self.assertEqual(m.speak(), "The rain has come and gone.")
        self.assertEqual(len(m.llm.prompts), 2)

    def test_a_reading_thin_even_after_retry_is_never_remembered(self):
        class Spy:
            def generate(self, prompt, **_kw):
                return "MURMUR: drift\nSO: Toll"
        m = _mind(with_soul=True)
        m.llm = Spy()
        out = m.speak()
        self.assertEqual(out, "Toll")                      # spoken (honest) ...
        self.assertEqual(m.last, "")                       # ... but not her thread
        self.assertEqual(m.said, [])                       # not her self-material
        self.assertFalse(any(mm.text == "Toll" for mm in m.memory.items))   # not her life


class AntiEchoTest(unittest.TestCase):
    def setUp(self):
        embed.use_jaccard_only(True)

    def tearDown(self):
        embed.use_jaccard_only(False)

    def _spy_mind(self):
        class Spy:
            def __init__(self):
                self.prompts = []

            def generate(self, prompt, **_kw):
                self.prompts.append(prompt)
                return "The mill turns and I am quiet."
        m = _mind()
        m.llm = Spy()
        return m

    def test_a_repeated_opener_is_named_and_forbidden(self):
        m = self._spy_mind()
        m.talk = ['they: "hello"',
                  'you: "Luke. Four hundred and fifty-two. It is heavy."',
                  'they: "go on"',
                  'you: "Luke. Four hundred and fifty-two. A stone, warm now."']
        m.converse("tell me about the mill")
        prompt = m.llm.prompts[-1]
        self.assertIn('begun "Luke. Four hundred and..."', prompt)
        self.assertIn("do NOT begin with those words", prompt)

    def test_varied_openers_keep_the_gentle_rule(self):
        m = self._spy_mind()
        m.talk = ['they: "hello"',
                  'you: "The damp is deep tonight."',
                  'they: "go on"',
                  'you: "Luke, the mill is quiet."']
        m.converse("tell me about the mill")
        prompt = m.llm.prompts[-1]
        self.assertIn("Never begin the way your last reply began", prompt)
        self.assertNotIn("do NOT begin with those words", prompt)


class ColdStreakTest(unittest.TestCase):
    """One wound per COLD streak (listening round 5): a sustained dark topic drew a RUN of
    misjudged COLDs that corroborated each other -- three wounds in eight loving exchanges.
    Consecutive readings of one conversation are one measurement repeated, not fresh evidence:
    a corroborated streak wounds once; only a warm/neutral line re-arms the wound."""

    class Stub:
        def __init__(self, answer):
            self.answer = answer

        def generate(self, prompt, **_kw):
            return self.answer

    def setUp(self):
        embed.use_jaccard_only(True)

    def tearDown(self):
        embed.use_jaccard_only(False)

    WARM_LINE = "I am glad and grateful for you, you have done well and I love this place"

    def test_a_cold_streak_wounds_once_however_long(self):
        m = _mind()
        m.judge = self.Stub("WARM")
        for _ in range(12):
            m.converse(self.WARM_LINE)
        m.judge.answer = "COLD"
        for _ in range(5):    # the UFO-dread shape: a long run of COLD-judged loving lines
            m.converse("the dread of the unknown pressed on me and would not lift")
        self.assertEqual(m.user_bond.wounds, 1)   # corroborated once; the rest chill only

    def test_a_warm_line_rearms_the_wound(self):
        m = _mind()
        m.judge = self.Stub("WARM")
        for _ in range(12):
            m.converse(self.WARM_LINE)
        m.judge.answer = "COLD"
        for _ in range(3):
            m.converse("the dread of the unknown pressed on me and would not lift")
        self.assertEqual(m.user_bond.wounds, 1)
        m.judge.answer = "WARM"                   # the coldness genuinely stopped...
        for _ in range(6):
            m.converse(self.WARM_LINE)
        m.judge.answer = "COLD"                   # ...so a NEW sustained run is new evidence
        m.converse("I am done with this and with you")
        m.converse("there is nothing left here for me")
        self.assertEqual(m.user_bond.wounds, 2)


class ThinkTraceTest(unittest.TestCase):
    """A thinking judge's trace can NAME verdicts while weighing them -- only the settled
    answer after </think> may be read."""

    class Stub:
        def __init__(self, answer):
            self.answer = answer

        def generate(self, prompt, **_kw):
            return self.answer

    def test_a_verdict_named_inside_the_trace_never_leaks(self):
        from agent import judge as _judge
        stub = self.Stub("<think>This could be COLD... or an APOLOGY? No -- "
                         "on balance neither.</think>NEUTRAL")
        self.assertEqual(_judge.intent("hello there", stub), "NEUTRAL")

    def test_the_settled_answer_after_the_trace_is_read(self):
        from agent import judge as _judge
        stub = self.Stub("<think>maybe WARM at first glance</think>COLD")
        self.assertEqual(_judge.intent("hello there", stub), "COLD")


class MythosGaugeTest(unittest.TestCase):
    def setUp(self):
        embed.use_jaccard_only(True)

    def tearDown(self):
        embed.use_jaccard_only(False)

    def test_her_share_of_the_held_lore_is_counted(self):
        m = _mind(with_soul=True)
        soul = m.world.agents[0]
        soul.memory.write("her story of the rain and the cold", tick=0, source="lore",
                          emotion=0.1, weight=0.5, lore_id="santana:5")
        soul.memory.write("the year the flood took the east field", tick=0, source="lore",
                          emotion=-0.2, weight=1.2, lore_id="flood")
        soul.memory.write("what I have come to expect of them", tick=0, source="event",
                          emotion=-0.5, weight=1.2, lore_id="conduct:user")
        hers, total = m.mythos_share()
        self.assertEqual((hers, total), (1, 2))   # conduct notes are not stories


class PersistenceTest(unittest.TestCase):
    def setUp(self):
        embed.use_jaccard_only(True)

    def tearDown(self):
        embed.use_jaccard_only(False)

    def test_the_new_fields_survive_a_save_and_load(self):
        m = _mind()
        m._last_dream_wall = 123.5
        m._somatic_trips = 2
        m._contraction = 0.4
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "mind.json")
            save_mind(m, path)
            m2 = _mind()
            self.assertTrue(load_mind(m2, path))
        self.assertEqual(m2._last_dream_wall, 123.5)
        self.assertEqual(m2._somatic_trips, 2)
        self.assertEqual(m2._contraction, 0.4)

    def test_a_pre_field_snapshot_wakes_cleanly(self):
        m = _mind()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "mind.json")
            save_mind(m, path)
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            for k in ("last_dream_wall", "somatic_trips", "contraction"):
                del data[k]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f)
            m2 = _mind()
            self.assertTrue(load_mind(m2, path))
        self.assertEqual(m2._last_dream_wall, 0.0)
        self.assertEqual(m2._somatic_trips, 0)
        self.assertEqual(m2._contraction, 0.0)


if __name__ == "__main__":
    unittest.main()
