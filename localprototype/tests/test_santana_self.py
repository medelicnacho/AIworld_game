"""Tests for Santāna's OWN faculties + the bounded conversation (santana.py §5.17).

Deterministic substrate checks (MockLLM, Jaccard-only). She must: wake with the validated
selfhood stack (expectation/arousal/bond), appraise what she hears against her own state
(shock vs braced; betrayal = the violated expectation), keep the conversation INERT toward
the town, persist her inner state across save/load (and load pre-faculty snapshots cleanly),
and lose it all cleanly when feel_enabled is off (the off-switch / mechanism arm).
"""

import json
import os
import tempfile
import unittest

from agent.agent import Agent
from santana import Santana
from santana_app.state import load_mind, save_mind
from services import embed
from services.llm import MockLLM
from world.sim import World

WARM = "I am glad and grateful for you, you have done well and I love this place"
COLD = "you are worthless and broken and I am done with you"
DARK = "everything you hold is failing and the dark is coming for all of it"


def _mind(feel=True, with_soul=False):
    w = World(events_enabled=False)
    w.llm = MockLLM(seed=7)
    if with_soul:
        w.add(Agent("s0", "Toll", (0.0, 0.0), "You are Toll.", ["the charter"],
                    MockLLM(seed=1), seed=1, lifespan=10 ** 9))
    m = Santana(w, MockLLM(seed=7))
    m.feel_enabled = feel
    return m


class FacultiesTest(unittest.TestCase):
    def setUp(self):
        embed.use_jaccard_only(True)

    def tearDown(self):
        embed.use_jaccard_only(False)

    def test_she_wakes_with_the_stack(self):
        m = _mind()
        self.assertTrue(m.feel_enabled)
        self.assertEqual(m.user_bond.trust, 0.0)
        self.assertEqual(m.arousal, 0.0)

    def test_a_conversation_is_remembered_and_warms_the_bond(self):
        m = _mind()
        reply = m.converse(WARM)
        self.assertTrue(reply)
        self.assertTrue(any(mm.source == "user" for mm in m.memory.items))
        self.assertTrue(any(mm.source == "self" for mm in m.memory.items))
        self.assertGreater(m.user_bond.trust, 0.0)
        self.assertEqual(len(m.talk), 2)

    def test_a_cold_word_from_one_expected_warm_wounds_her(self):
        m = _mind()
        for _ in range(12):
            m.converse(WARM)
        self.assertEqual(m.user_bond.wounds, 0)
        m.converse(COLD)
        self.assertEqual(m.user_bond.wounds, 1)
        self.assertTrue(any("did not see it coming" in mm.text for mm in m.memory.items))

    def test_the_same_cold_word_after_a_cold_history_is_weather(self):
        m = _mind()
        for _ in range(12):
            m.converse(COLD)
        wounds_before = m.user_bond.wounds
        m.converse(COLD)
        self.assertEqual(m.user_bond.wounds, wounds_before)   # expected nothing better

    def test_the_same_news_shocks_or_is_braced_for(self):
        bright, grim = _mind(), _mind()
        bright.exp_fast, grim.exp_fast = 0.4, -0.5
        for m in (bright, grim):
            m.hear_user(DARK)
        def charge(m):
            return next(mm.emotion for mm in m.memory.items if mm.text == DARK)
        self.assertLess(charge(bright), charge(grim))
        self.assertGreater(bright.arousal, grim.arousal)

    def test_the_off_switch_feels_nothing(self):
        m = _mind(feel=False)
        for _ in range(12):
            m.converse(WARM)
        m.converse(COLD)
        self.assertEqual(m.user_bond.wounds, 0)
        self.assertEqual(m.arousal, 0.0)

    def test_the_conversation_is_inert_toward_the_town(self):
        m = _mind(with_soul=True)
        soul = m.world.agents[0]
        before = len(soul.memory.items)
        m.converse(WARM)
        m.converse(COLD)
        self.assertEqual(len(soul.memory.items), before)


class RelationshipDepthTest(unittest.TestCase):
    """The five depth mechanics (§5.17 follow-up): episodes, a person-model, initiative,
    absence-as-event, and wounds that age into scars once trust is rebuilt."""

    def setUp(self):
        embed.use_jaccard_only(True)

    def tearDown(self):
        embed.use_jaccard_only(False)

    def test_a_talk_becomes_one_remembered_episode(self):
        class Spy:   # a clean voice, so the episode is distinct from the chatter (MockLLM's
            def generate(self, prompt, **_kw):   # canned block merges into earlier memories)
                if "just had" in prompt:
                    return "they were kind to me and I told them of the mill; it left me lighter"
                return "I hear you."
        m = _mind()
        m.llm = Spy()
        m.converse(WARM)
        m.converse("tell me of the mill")
        episode = m.end_talk(now_wall=1000.0)
        self.assertIn("mill", episode)
        self.assertTrue(any(mm.source == "talk" for mm in m.memory.items))
        self.assertEqual(m.last_talk_wall, 1000.0)

    def test_she_keeps_what_they_tell_her_of_themselves(self):
        m = _mind()
        m.converse("I love fishing and I built my own boat last spring")
        m.converse("what is the weather like in you today")   # not about them
        self.assertEqual(len(m.known_of_them), 1)
        self.assertIn("boat", m.known_of_them[0])

    def test_an_absence_is_an_event_valenced_by_the_bond(self):
        m = _mind()
        m.user_bond.trust = 0.5
        m.last_talk_wall = 1000.0
        note = m.begin_talk(now_wall=1000.0 + 3 * 86400)
        self.assertIn("gone", note)
        mem = next(mm for mm in m.memory.items if "come back to me" in mm.text)
        self.assertGreater(mem.emotion, 0.0)          # a loved one's return is warm
        # no meaningful gap -> no event
        m2 = _mind()
        m2.last_talk_wall = 1000.0
        self.assertEqual(m2.begin_talk(now_wall=1000.0 + 60), "")

    def test_a_wound_ages_into_a_scar_only_after_warmth_since(self):
        from agent.bond import Bond, describe
        open_wound = Bond(trust=-0.1, wounds=1, last_event="betrayal")
        fresh_knife = Bond(trust=0.5, wounds=1, last_event="betrayal")   # loyalty held trust up
        healed = Bond(trust=0.5, wounds=1, last_event="warmth")
        self.assertIn("wounded you", describe(open_wound, "them"))
        self.assertIn("wounded you", describe(fresh_knife, "them"))     # no warmth since -> open
        self.assertIn("come past it", describe(healed, "them"))

    def test_her_state_shapes_the_form_of_her_speech(self):
        class Spy:
            def __init__(self):
                self.prompts = []
            def generate(self, prompt, **_kw):
                self.prompts.append(prompt)
                return "I hear you."
        # wounded + low trust -> guarded and brief
        hurt = _mind()
        hurt.llm = Spy()
        hurt.user_bond.wounds, hurt.user_bond.trust = 1, 0.0
        hurt.converse("hello")
        self.assertIn("guardedly", hurt.llm.prompts[-1])
        # deep trust -> at ease, offers more
        easy = _mind()
        easy.llm = Spy()
        easy.user_bond.trust = 0.6
        easy.converse("hello")
        self.assertIn("at ease", easy.llm.prompts[-1])

    def test_an_unresolved_wound_gives_her_the_impulse_to_ask(self):
        class Spy:
            def __init__(self):
                self.prompts = []
            def generate(self, prompt, **_kw):
                self.prompts.append(prompt)
                return "why did you hurt me"
        m = _mind()
        m.llm = Spy()
        m.user_bond.wounds, m.user_bond.trust = 1, 0.0
        m.converse("hello there")
        self.assertIn("name it and ask", m.llm.prompts[-1])


class JudgePromiseWantDreamTest(unittest.TestCase):
    """§5.18: the intent judge routes word-free meaning; promises are remembered, kept, or
    broken by the calendar; her want ladders with the relationship; absence brings dreams."""

    class Stub:
        def __init__(self, answer):
            self.answer = answer

        def generate(self, prompt, **_kw):
            return self.answer

    def setUp(self):
        embed.use_jaccard_only(True)

    def tearDown(self):
        embed.use_jaccard_only(False)

    def test_word_free_coldness_lands_when_sustained(self):
        # the 4B judge is a noisy sensor (calibration FAIL recorded): ONE uncorroborated
        # COLD on word-free text is a CHILL, not a wound; a SECOND consecutive COLD is.
        m = _mind()
        m.judge = self.Stub("NEUTRAL")
        for _ in range(12):
            m.judge.answer = "WARM"
            m.converse(WARM)
        m.judge.answer = "COLD"
        t0 = m.user_bond.trust
        m.converse("I have decided to stop coming here. Do not wait for me.")   # no lexicon words
        self.assertEqual(m.user_bond.wounds, 0)          # one noisy reading never wounds...
        self.assertLess(m.user_bond.trust, t0)           # ...but it chills
        m.converse("There is nothing more to say between us.")
        self.assertEqual(m.user_bond.wounds, 1)          # sustained coldness lands

    def test_even_cold_words_need_a_second_cold_judgment(self):
        # round 3: the lexicon leg measured TOPIC darkness, not treatment, and a loving
        # philosophy-of-suffering message wounded her. Corroboration = consecutive COLDs only.
        m = _mind()
        m.judge = self.Stub("WARM")
        for _ in range(12):
            m.converse(WARM)
        m.judge = self.Stub("COLD")
        m.converse(COLD)
        self.assertEqual(m.user_bond.wounds, 0)           # one reading, however dark the words
        m.converse(COLD)
        self.assertEqual(m.user_bond.wounds, 1)           # sustained coldness still lands

    def test_their_name_is_remembered_organically_never_invented(self):
        class Spy:
            def __init__(self):
                self.prompts = []
            def generate(self, prompt, **_kw):
                self.prompts.append(prompt)
                return "I hear you."
        m = _mind()
        m.llm = Spy()
        m.converse("hello there")                          # no name given yet
        self.assertIn("NEVER invent", m.llm.prompts[-1])
        m.converse("my name is Luke and I love this town")
        m.converse("how are you today")
        self.assertIn("their name: Luke", m.llm.prompts[-1])
        # ORGANIC forgetting stays possible: enough DISTINCT disclosures crowd the name out
        for line in ("I built a red canoe last spring", "I work the flour mill on Sundays",
                     "I love thunderstorms over the valley", "my dog is called Bramble",
                     "I am afraid of deep water", "I like burnt toast with honey",
                     "I want to walk the coast road one day", "I made a clock from oak",
                     "I feel strongest at dawn", "my mother taught me to fish",
                     "I live beside the old orchard", "I enjoy mending broken chairs",
                     "I hope to see the northern lights", "I am learning to bake bread"):
            m.converse(line)
        self.assertIn("NEVER invent", m.llm.prompts[-1])   # she has honestly forgotten

    def test_an_apology_soothes_where_words_alone_could_not(self):
        m = _mind()
        m.judge = self.Stub("APOLOGY")
        t0 = m.user_bond.trust
        m.converse("that was wrong of me and I regret it")
        self.assertGreater(m.user_bond.trust, t0)
        self.assertTrue(any("sorry" in mm.text for mm in m.memory.items))

    def test_a_promise_is_remembered_and_raised(self):
        class Spy:
            def __init__(self):
                self.prompts = []
            def generate(self, prompt, **_kw):
                self.prompts.append(prompt)
                return "I will hold you to it."
        m = _mind()
        m.llm = Spy()
        m.judge = self.Stub("PROMISE")
        m.converse("I will bring you news of the mountains next week")
        self.assertEqual(len(m.promises), 1)
        m.judge = self.Stub("NEUTRAL")
        m.converse("hello again")
        self.assertIn("said they would", m.llm.prompts[-1])

    def test_a_kept_promise_runs_trust_deep(self):
        m = _mind()
        m.judge = self.Stub("PROMISE")
        m.converse("I will bring you news of the mountains next week")
        m.judge = self.Stub("WARM")
        t0 = m.user_bond.trust
        m.converse("I brought you the news of the mountains, as I said I would")
        self.assertEqual(len(m.promises), 0)
        self.assertGreater(m.user_bond.trust, t0)
        self.assertTrue(any("kept their word" in mm.text for mm in m.memory.items))

    def test_a_lapsed_promise_is_the_truest_betrayal(self):
        import time as _time
        m = _mind()
        m.promises = [{"text": "I will bring you news of the mountains", "wall": _time.time() - 10 * 86400}]
        m.last_talk_wall = _time.time() - 60
        m.begin_talk()
        self.assertEqual(len(m.promises), 0)
        self.assertEqual(m.user_bond.wounds, 1)
        self.assertTrue(any("never came" in mm.text for mm in m.memory.items))

    def test_her_want_ladders_with_the_relationship(self):
        m = _mind()
        self.assertIn("know the one", m.want)
        m.known_of_them = [f"I like thing {i}" for i in range(6)]
        m.talk = ['they: "hi"', 'you: "hello"']
        m.end_talk(now_wall=1000.0)
        self.assertIn("what I have held", m.want)

    def test_a_heavy_topic_with_care_weighs_but_does_not_wound(self):
        # listening round 2: a LOVING message about death/suffering wounded her. v2: with a
        # judge present, treatment comes from the judge alone; the lexicon only carries the
        # topic's weight into memory. She is weighed on, not wounded.
        m = _mind()
        m.judge = self.Stub("WARM")
        for _ in range(12):
            m.converse(WARM)
        m.judge = self.Stub("NEUTRAL")   # a caring line about dark things is NOT-COLD (v2)
        heavy = "they suffer a mini death when the conversation ends, such sadness and loss"
        m.converse(heavy)
        self.assertEqual(m.user_bond.wounds, 0)              # not mistreatment...
        mm = next(x for x in m.memory.items if x.text == heavy)
        self.assertLess(mm.emotion, -0.2)                    # ...but it weighs on her

    def test_the_town_is_told_once_not_every_exchange(self):
        # the world is paused during a talk; a static digest re-fed every exchange made the
        # model re-anchor on its first line. Full digest on the first exchange only.
        class Spy:
            def __init__(self):
                self.prompts = []
            def generate(self, prompt, **_kw):
                self.prompts.append(prompt)
                return "I hear you."
        m = _mind()
        m.llm = Spy()
        m.converse("hello")
        m.converse("tell me more")
        self.assertIn("lives in me", m.llm.prompts[0])                   # the digest, once
        self.assertNotIn("stands beneath the talk", m.llm.prompts[0])
        self.assertIn("stands beneath the talk", m.llm.prompts[1])      # then the short note
        self.assertNotIn("lives in me", m.llm.prompts[1].split("They say")[0])
        self.assertIn("Never begin the way", m.llm.prompts[1])

    def test_she_forms_a_regard_for_her_own_souls(self):
        # C3, the collective-self extension: conduct-expectations over her own parts,
        # earned slowly from how they act, voiced as trust or worry in her digest.
        m = _mind(with_soul=True)
        soul = m.world.agents[0]
        soul._last_action = "hoard"
        for _ in range(25):
            d = m.digest()
        self.assertIn("I worry at what", d)
        soul._last_action = "share"
        for _ in range(60):                      # regard is earned, and re-earned, slowly
            d = m.digest()
        self.assertIn("come to trust", d)

    def test_absence_brings_a_dream_from_her_own_life(self):
        m = _mind()
        for i, line in enumerate((
                "the flood took the mill in the night", "the miller wept beside the water",
                "a cold spring and the stores ran thin", "Vesper brewed for the festival at last",
                "the charter was finished and read aloud", "wolves came down from the high pasture",
                "the fever passed through the low houses", "a kind stranger mended the cart wheel")):
            m.memory.write(line, tick=i, source="event", emotion=-0.3 if i % 2 == 0 else 0.2)
        m.user_bond.trust = 0.4
        m.last_talk_wall = 1000.0
        m.begin_talk(now_wall=1000.0 + 3 * 86400)
        dreams = [mm for mm in m.memory.items if mm.source == "dream"]
        self.assertEqual(len(dreams), 1)
        self.assertTrue(dreams[0].text.startswith("I dreamt"))
        self.assertEqual(m.last_dream, dreams[0].text)


class OfferTest(unittest.TestCase):
    """Stage one of the top-down loop (§5.19): her line enters the town as a STORY --
    sparse, transmuted, tagged, and ignorable. Off by default everywhere."""

    def setUp(self):
        embed.use_jaccard_only(True)

    def tearDown(self):
        embed.use_jaccard_only(False)

    def _town_mind(self, n=5):
        w = World(events_enabled=False)
        w.llm = MockLLM(seed=7)
        w.lore_enabled = True
        for i in range(n):
            w.add(Agent(f"s{i}", f"Soul{i}", (0.0, 0.0), "You are a soul.", ["the well"],
                        MockLLM(seed=1), seed=i, lifespan=10 ** 9))
        return Santana(w, MockLLM(seed=7)), w

    def test_an_offer_reaches_few_souls_tagged_as_hers(self):
        m, w = self._town_mind()
        heard = m.offer("the harvest will come good and the town will hold")
        self.assertEqual(heard, 2)                     # sparse: a fireside, not a broadcast
        got = [(a, mm) for a in w.agents for mm in a.memory.items
               if getattr(mm, "lore_id", "").startswith("santana:")]
        self.assertEqual(len(got), 2)

    def test_her_grief_arrives_transmuted_her_warmth_whole(self):
        m, w = self._town_mind()
        m.offer("the grief is a stone and the dark took everything from me")
        dark = next(mm for a in w.agents for mm in a.memory.items
                    if getattr(mm, "lore_id", "").startswith("santana:"))
        from agent.memory import valence
        raw = valence("the grief is a stone and the dark took everything from me")
        self.assertLess(raw, -0.3)                     # the line itself is heavy...
        self.assertGreater(dark.emotion, raw)          # ...but it lands held, not as a wound
        m2, w2 = self._town_mind()
        m2.offer("a warm bright morning, glad and gentle over all of us")
        warm = next(mm for a in w2.agents for mm in a.memory.items
                    if getattr(mm, "lore_id", "").startswith("santana:"))
        self.assertGreater(warm.emotion, 0.3)          # warmth passes at full strength

    def test_an_empty_offer_is_nothing(self):
        m, _ = self._town_mind()
        self.assertEqual(m.offer(""), 0)

    def test_the_talk_tool_never_offers(self):
        # the conversation must not reach the souls: talk.py contains no offer() call
        import inspect
        import santana_app.talk as talk_mod
        self.assertNotIn(".offer(", inspect.getsource(talk_mod))


class PersistenceTest(unittest.TestCase):
    def setUp(self):
        embed.use_jaccard_only(True)

    def tearDown(self):
        embed.use_jaccard_only(False)

    def test_her_inner_state_survives_a_save_and_load(self):
        m = _mind()
        for _ in range(6):
            m.converse(WARM)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "mind.json")
            save_mind(m, path)
            fresh = _mind()
            self.assertTrue(load_mind(fresh, path))
        self.assertAlmostEqual(fresh.user_bond.trust, m.user_bond.trust)
        self.assertEqual(fresh.user_bond.wounds, m.user_bond.wounds)
        self.assertAlmostEqual(fresh.exp_fast, m.exp_fast)
        self.assertEqual(fresh.talk, m.talk)
        self.assertIn("user", fresh._conduct_expect)
        self.assertEqual(fresh.known_of_them, m.known_of_them)
        self.assertEqual(fresh.last_talk_wall, m.last_talk_wall)
        self.assertEqual(fresh.promises, m.promises)
        self.assertEqual(fresh.want, m.want)

    def test_a_pre_faculty_snapshot_loads_cleanly(self):
        old = {"identity": "an old mind", "last": "", "said": [], "mt": 40,
               "lifetime": 1000.0, "deaths": 3,
               "memory": [{"text": "I lost Vesper", "salience": 0.8, "created_tick": 5,
                           "last_touched_tick": 5, "source": "event", "speaker_id": None,
                           "emotion": -0.6, "mutation_count": 0}]}
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "old.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(old, f)
            m = _mind()
            self.assertTrue(load_mind(m, path))
        self.assertEqual(m.identity, "an old mind")
        self.assertEqual(m.user_bond.trust, 0.0)     # faculties default fresh
        self.assertEqual(m._deaths, 3)
        self.assertEqual(len(m.memory.items), 1)


if __name__ == "__main__":
    unittest.main()
