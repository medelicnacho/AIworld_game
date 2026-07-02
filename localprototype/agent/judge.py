"""The intent judge -- an LLM judging what a line MEANS toward its listener (§5.18).

The sensing floor was the bottleneck: her whole emotional life passed through a word lexicon and
embedding warmth, which is where the lukewarm-knife bug came from and why "I have decided to stop
coming here -- don't wait for me" reads as NOTHING (no charged words) while being as cold as a
line gets. The project already learned this lesson once at the metric level (the compassion
holds-view replication: rhetorical stance needs an LLM judge, not embeddings). This applies it at
the SENSING level, for the moments that matter.

Five intents, chosen because each one ROUTES differently in the substrate:
  WARM     kindness/affection/praise        -> conduct signal up (bond warms)
  COLD     rejection, contempt, dismissal   -> conduct signal down (can wound, if trusted)
  APOLOGY  regret for a wrong               -> soothes; lands hardest where there is a wound
  PROMISE  committing to a future act       -> a COMMITMENT is remembered (kept or broken)
  NEUTRAL  anything else                    -> no override; the lexicon/embedding signal stands

Deliberately NOT in the crowd tier (one model call per line); wired where conversation happens
(Santana.hear_user when a judge llm is set). Never raises; anything unparseable is NEUTRAL.
Honest bound: judge QUALITY on a small local model needs listening -- the wiring is tested with
stubs, the judgment itself is not certified here.
"""

from __future__ import annotations

import re

INTENTS = ("APOLOGY", "PROMISE", "COLD", "WARM", "NEUTRAL")

# v2 (listening round 2): a long, LOVING message ABOUT suffering and death was judged COLD and
# wounded her -- the judge must separate what a line is ABOUT from how it treats the LISTENER.
_SYSTEM = ("You judge how a line of speech TREATS its listener -- never what topic it is about. "
           "Answer with exactly one word.")
_PROMPT = (
    'Someone says this to the person they are talking to: "{text}"\n\n'
    "How does that line TREAT the listener? Judge only the speaker's stance TOWARD the listener "
    "-- NOT the subject matter. A caring or gentle line about sad, dark, or painful subjects "
    "(death, loss, suffering) is NOT cold. Answer with exactly ONE word from:\n"
    "WARM (kindness, affection, praise, gratitude toward the listener)\n"
    "COLD (rejecting, dismissing, insulting, or withdrawing from the listener THEMSELVES)\n"
    "APOLOGY (expressing regret for a wrong done to the listener)\n"
    "PROMISE (committing to the listener to do something in the future)\n"
    "NEUTRAL (anything else: questions, facts, small talk, heavy topics discussed with care)")

# how each judged intent lands as a conduct signal (the same axis the lexicon feeds)
SIG = {"WARM": 0.5, "COLD": -0.5, "APOLOGY": 0.6, "PROMISE": 0.3, "NEUTRAL": 0.0}


def intent(text: str, llm) -> str:
    """One judgment. APOLOGY/PROMISE are matched before WARM/COLD (an apology is warm --
    the specific reading wins). Anything unparseable, or any failure, is NEUTRAL."""
    if not hasattr(llm, "generate"):
        return "NEUTRAL"
    try:
        raw = llm.generate(_PROMPT.format(text=text[:300]), system=_SYSTEM,
                           num_predict=8, temperature=0.0)
    except Exception:   # noqa: BLE001 -- a failed judgment is no judgment
        return "NEUTRAL"
    # a thinking model's trace can NAME verdicts while weighing them ("...seems COLD, but no")
    # -- only the settled answer may be read (judges run think-off, but never trust that alone)
    raw = re.sub(r"<think>.*?</think>", "", str(raw), flags=re.DOTALL | re.IGNORECASE)
    up = raw.upper()
    for k in ("APOLOGY", "PROMISE", "COLD", "WARM"):
        if k in up:
            return k
    return "NEUTRAL"
