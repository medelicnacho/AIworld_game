"""pledge.py -- a promise is a conduct-expectation with a DEADLINE (Phase A, ported down
from HER).

Santāna has held the one who talks to her to their word since §5.18: a promise recorded,
kept warms her deeply, lapsed wounds her where the absence is measured. This is that organ
at the SOUL level -- an NPC holds anyone (another soul, or the PLAYER, who is just another
id here) to what they said they would do, by the town's own clock.

The three moves:
  make()    -- the word is given: recorded with a due tick, and remembered ("they gave me
               their word"). The promise itself already moves the expectation a little:
               a stated intention is a small warmth on credit.
  fulfill() -- the word is kept, in time: deep trust (bond.warm), a warm memory, the
               conduct-expectation rises -- and the keeping is a CONDUCT STORY
               (lore_id conduct:<promiser>), so a kept word can travel as gossip too.
  lapse()   -- the deadline passes unmet (checked from Agent.step): a promise IS an
               explicit expectation, so the breach is ALWAYS a betrayal -- no gap test
               needed (unlike appraise_conduct's weather). Bond.betray (loyalty absorbs,
               exactly as everywhere else), a charged memory, the expectation drops, and
               the breach writes its conduct story: A BROKEN WORD TRAVELS. Through the
               validated C3 channel it hardens into reputation among souls the promiser
               never met -- which is what makes promises to ONE soul matter to a TOWN
               (and, in the game to come, to an army).

Substrate only, deterministic, no model anywhere. Off unless promises are made."""
from __future__ import annotations

from agent.bond import Bond
from agent.expectation import BOND_EXPECT_RATE

MADE_NUDGE = 0.15      # a given word is a small warmth on credit
KEPT_SIG = 0.65        # how a kept word lands on the conduct-expectation
BROKEN_SIG = -0.7      # how a lapsed one lands
KEPT_WARM = 0.5        # bond.warm on a kept promise (trust runs deep)
BROKEN_SEV = 0.6       # bond.betray severity on a lapse (history absorbs, as ever)


def _nudge_expect(agent, pid: str, sig: float) -> None:
    exp = agent._conduct_expect.get(pid)
    agent._conduct_expect[pid] = (sig if exp is None
                                  else exp + BOND_EXPECT_RATE * (sig - exp))


def make(agent, promiser_id: str, promiser_name: str, text: str, due_tick: int,
         now: int) -> dict:
    """The word is given. Returns the recorded promise."""
    p = {"promiser": promiser_id, "name": promiser_name, "text": text[:120],
         "due": int(due_tick), "made": int(now), "open": True}
    agent.promises_held.append(p)
    # deliberately WITHOUT the promise's words: the pledge record above holds those. If
    # this memory carried them, the later kept/broken memory (which does) would merge
    # into it (memory.write folds near-identical texts) and the outcome's charge would
    # be averaged away into the making -- the ledger and the memory are different organs.
    agent.memory.write(f"{promiser_name} gave me their word",
                       tick=now, source="event", speaker_id=promiser_id,
                       emotion=0.2, weight=1.0)
    _nudge_expect(agent, promiser_id, MADE_NUDGE)
    return p


def fulfill(agent, promiser_id: str, now: int) -> str | None:
    """The earliest open promise from this promiser is KEPT (in time). Returns its text,
    or None if nothing was open."""
    for p in agent.promises_held:
        if p["open"] and p["promiser"] == promiser_id and now <= p["due"]:
            p["open"] = False
            p["kept"] = True
            if agent.bond_enabled:
                agent.bonds.setdefault(promiser_id, Bond()).warm(KEPT_WARM)
            agent.memory.write(f"{p['name']} kept their word to me -- {p['text']}",
                               tick=now, source="event", speaker_id=promiser_id,
                               emotion=0.5, weight=1.2,
                               lore_id=f"conduct:{promiser_id}")
            _nudge_expect(agent, promiser_id, KEPT_SIG)
            return p["text"]
    return None


def lapse_check(agent, now: int) -> list[str]:
    """Called each step: every open promise whose deadline has passed BREAKS here, where
    the absence is measured. Returns the broken texts (for logs)."""
    broken: list[str] = []
    for p in agent.promises_held:
        if p["open"] and now > p["due"]:
            p["open"] = False
            p["kept"] = False
            if agent.bond_enabled:
                agent.bonds.setdefault(p["promiser"], Bond()).betray(BROKEN_SEV)
            agent.memory.write(
                f"{p['name']} gave their word -- {p['text']} -- and let it come to nothing",
                tick=now, source="event", speaker_id=p["promiser"],
                emotion=-0.55, weight=1.3, lore_id=f"conduct:{p['promiser']}")
            _nudge_expect(agent, p["promiser"], BROKEN_SIG)
            broken.append(p["text"])
    return broken
