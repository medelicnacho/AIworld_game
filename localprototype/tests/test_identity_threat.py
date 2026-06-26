"""Tests for identity-threat hostility & ideological laundering.

Hostility is driven by THREAT TO IDENTITY (a line negating one of my faith's
fundamentals), not by doctrinal disagreement. Doctrine governs only how the
hostility is expressed and whether it gets laundered into righteousness.

Topic/threat matching is forced to deterministic word-overlap here (no live
embeddings), so threat lines are near-copies of a faith's anti-axioms.

Run:  python -m unittest discover -s tests
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import ideology
from agent.agent import Agent
from agent.ideology import BLASPHEMER, EVIL, FELLOW
from agent.religion import THE_DEVOUT, THE_PATH
from services import embed
from services.llm import MockLLM
from world.events import Utterance

embed.use_jaccard_only(True)   # deterministic, Ollama-free

# a near-copy of a Path anti-axiom ("you must serve the Creator above all")
PATH_THREAT = "you must serve the Creator above all"
# safe peripheral debate for a Path soul (no apostrophes, to match word-overlap)
PATH_PERIPHERAL = "how best can we ease the pain of another"


def faith_agent(name, faith=THE_PATH, temperament=0.0):
    return Agent(name, name.title(), (0.0, 0.0), f"You are {name}.", [],
                 MockLLM(seed=1), seed=1, temperament=temperament, religion=faith)


def threat(spk, tick, text=PATH_THREAT):
    return Utterance(spk, text, tick, source="ai", religion="devout", mood=0.5)


class IdentityThreatTest(unittest.TestCase):

    def test_threat_spikes_hostility_peripheral_does_not(self):
        a = faith_agent("a")
        a.hear(threat("foe", 1), now=1)
        spike = a.hostility.get("foe", 0.0)
        self.assertGreater(spike, 0.0)                 # an attack on a fundamental builds hostility
        b = faith_agent("b")
        b.hear(Utterance("dis", PATH_PERIPHERAL, 1, source="ai", religion="devout", mood=0.5), now=1)
        self.assertEqual(b.hostility.get("dis", 0.0), 0.0)   # mere debate does not

    def test_laundering_flips_category_and_collapses_dissonance(self):
        a = faith_agent("a", temperament=-0.6)   # cold/reactive -> low launder threshold
        a.identity_investment = 1.0
        a.relationship["foe"] = FELLOW            # doctrine says spare this soul
        for t in range(1, 12):
            a.hear(threat("foe", t), now=t)
            if a.relationship.get("foe") == EVIL:
                break
        self.assertEqual(a.relationship.get("foe"), EVIL)   # FELLOW -> EVIL (Path's laundered label)
        self.assertEqual(a.dissonance, 0.0)                 # tension collapsed by RELABELLING
        self.assertGreater(a.hostility["foe"], 0.0)         # hostility was NOT reduced

    def test_warm_resists_flip_while_cold_flips_on_identical_input(self):
        cold = faith_agent("cold", temperament=-0.8)
        warm = faith_agent("warm", temperament=0.8)
        for ag in (cold, warm):
            ag.relationship["foe"] = FELLOW
            for t in range(1, 6):
                ag.hear(threat("foe", t), now=t)
        self.assertEqual(cold.relationship.get("foe"), EVIL)        # reactive soul flips
        self.assertNotEqual(warm.relationship.get("foe"), EVIL)     # peaceable soul holds

    def test_peripheral_from_graceful_mutates_low_grace_rival_does_not(self):
        moved = faith_agent("moved")
        moved.grace, moved.conviction = 0.3, 0.2     # low grace, wavering
        before = moved.belief
        moved.hear(Utterance("prophet", PATH_PERIPHERAL, 1, source="ai",
                             religion="devout", mood=0.5, effectiveness=1.0), now=1)
        self.assertNotEqual(moved.belief, before)    # a more graceful soul moves it (debate, not war)

        held = faith_agent("held")
        held.grace, held.conviction = 0.3, 0.2
        before_h = held.belief
        held.hear(Utterance("rival", PATH_PERIPHERAL, 1, source="ai",
                            religion="devout", mood=0.5, effectiveness=0.2), now=1)
        self.assertEqual(held.belief, before_h)      # a low-grace rival does not

    def test_devout_uses_its_own_laundered_label(self):
        d = faith_agent("d", faith=THE_DEVOUT, temperament=-0.7)
        d.identity_investment = 1.0
        d.relationship["foe"] = FELLOW
        # a Devout anti-axiom ("virtue toward your fellow soul matters more than any Creator")
        line = "virtue toward your fellow soul matters more than any Creator"
        for t in range(1, 12):
            d.hear(Utterance("foe", line, t, source="ai", religion="path", mood=-0.5), now=t)
            if d.relationship.get("foe") == BLASPHEMER:
                break
        self.assertEqual(d.relationship.get("foe"), BLASPHEMER)   # Devout launders to BLASPHEMER, not EVIL

    def test_safety_no_code_execution_sink(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        pat = r"(\beval\(|\bexec\(|os\.system|os\.popen|shell\s*=\s*True)"
        out = subprocess.run(
            ["grep", "-rnE", pat,
             os.path.join(root, "agent"), os.path.join(root, "world"),
             os.path.join(root, "services")],
            capture_output=True, text=True).stdout.strip()
        self.assertEqual(out, "", f"agent text must never reach a code-exec sink:\n{out}")


if __name__ == "__main__":
    unittest.main()
