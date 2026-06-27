"""The self-model: perpetual self-referential consolidation.

The north star -- a self the LLM inhabits, thinking about itself continually. Anatta-
faithful: the self-model is RE-DERIVED each cycle from the five streams, never stored
as an essence. The soul reads who it has been (recall_self), how it feels (felt_mood),
who it has come to love or fear (bonds), what drifts in it (thought), and consolidates
ONE first-person line -- "who I am becoming right now." That line is written back as
high-salience self-memory AND fed into the next prompt, so the soul's speech references
the self it has formed:

    speak -> memory -> reflect -> self-model -> prompt -> speak

A self as a self-referential PROCESS -- an attractor that stays coherent yet drifts,
not a thing. Built as an opt-in faculty (Agent.self_model_enabled), driven on a cadence
by the harness/world; the prompt feedback is gated on a non-empty self_model so nothing
existing changes until a soul actually starts consolidating.
"""

from __future__ import annotations

from services.llm import _mood_word, _trim_to_sentence, sanitize

SELF_MODEL_SYSTEM = (
    "You are a mind quietly taking stock of who you have become -- not inventing a "
    "character, but noticing the self that has actually formed from your memories, "
    "feelings, and bonds. Speak plainly, in the first person."
)


def _relational_note(agent) -> str:
    """One line about the soul's strongest bond, without needing the other's name --
    who it has come to love or fear is part of who it is."""
    if not getattr(agent, "bonds", None):
        return ""
    _, b = max(agent.bonds.items(), key=lambda kv: abs(kv[1].trust))
    if b.trust > 0.25:
        return "There is someone here I have come to trust and care for."
    if b.trust < -0.25:
        return "Someone here has hurt me, and I stay wary of them."
    return ""


def consolidate(agent, llm, now: int):
    """One self-referential cycle: read the streams, consolidate a self-summary, write
    it back, and set agent.self_model. Returns the summary (or None if there isn't yet
    a self to take stock of / the backend can't do a free completion). Never raises."""
    if not hasattr(llm, "generate"):
        return None
    mems = [m.text for m in agent.memory.recall_self(k=4)]
    if not mems:
        return None
    parts = ["These are the things I keep coming back to about myself:"]
    parts += [f"- {m}" for m in mems]
    parts.append(f"Right now I feel {_mood_word(agent.felt_mood())}.")
    rel = _relational_note(agent)
    if rel:
        parts.append(rel)
    if agent.self_model:                       # the prior self -> coherence/attractor
        parts.append(f"A little while ago I understood myself as: \"{agent.self_model}\"")
    drift = agent.thought.current(2)
    if drift:
        parts.append("Drifting through me: " + "; ".join(drift))
    prompt = "\n".join(parts) + (
        "\n\nIn ONE short first-person sentence, say who you are becoming right now -- "
        "the self that has actually formed from all this. Ground it in the SPECIFIC "
        "people, places, losses and loves in your memories above; name them. Avoid "
        "generic self-description -- no 'quiet keeper of the land', no abstract roles "
        "or moods that could belong to anyone. Use fresh words; do not repeat your "
        "earlier line.")
    try:
        raw = llm.generate(prompt, system=SELF_MODEL_SYSTEM, num_predict=80,
                           temperature=0.7)
    except Exception:  # noqa: BLE001 -- self-reference must never crash the loop
        return None
    text = _trim_to_sentence(" ".join(sanitize(raw).split()).strip().strip('"').strip())
    if not text:
        return None
    agent.self_model = text
    agent.self_model_history.append(text)
    # written as the soul's own, high-salience -> recall_self surfaces it, so the next
    # consolidation is built partly from the last: the self-reinforcing attractor.
    agent.memory.write(text, tick=now, source="self", speaker_id=agent.id, weight=1.5)
    return text
