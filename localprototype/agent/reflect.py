"""reflect(): an agent's relationship to its OWN memory.

The agent reads the memories most present to it, plus its current felt state, and
forms a short meta-observation about them -- meeting what is there with
recognition rather than clinging (the Buddhist meta-cognition: sati / upekkha,
mindful equanimity). The reflection is written back as memory, so it re-enters the
subconscious drift (ThoughtLoop rebuilds from memory each tick) and colours future
mood. This is the mind relating to itself, not only reacting outward.

Built as a TOGGLEABLE MODULE (Agent.reflect_enabled), deliberately not a rewrite
of the agent: the SAME agent runs with reflect on in the clean-room lab
(experiment_affect.py) and, later, in the social sim. You flip the environment,
not the agent.

Stage-1 question this exists to answer (falsifiably): does relating to one's own
memory actually MOVE the emotional trajectory -- ease grief, speed habituation,
soften recurrence -- or is it a decorative loop that writes vague nothings? The
experiment A/Bs reflect on vs off on an identical, seeded grief protocol.
"""

from __future__ import annotations

from services.llm import _mood_word, sanitize

REFLECT_SYSTEM = (
    "You are a mind quietly observing its own thoughts and feelings, the way one "
    "watches weather pass -- not pushing anything away, not clinging to it, only "
    "noticing what is here and meeting it with acceptance."
)


def build_prompt(name: str, mood: float, memories: list[str]) -> str:
    body = "\n".join(f"- {m}" for m in memories)
    return (
        f"You are {name}. Right now you feel {_mood_word(mood)}. These are most "
        f"present in your mind:\n{body}\n\nIn one or two short first-person "
        "sentences, observe what is here in you and how you are holding it -- name "
        "the feeling and let it be, neither denying it nor drowning in it. Speak "
        "plainly, as yourself."
    )


def reflect(agent, llm, now: int, k: int = 4):
    """One reflection step: read salient memory + felt state, form a meta-thought,
    write it back as a 'reflection' memory. Returns the reflection text (or None if
    there was nothing to reflect on / the backend can't do a free completion).
    Never raises -- a failed reflection just doesn't happen, like a failed turn."""
    if not hasattr(llm, "generate"):
        return None
    # the most salient of the soul's OWN lived memory -- not the doctrines, which
    # are written at high weight and would otherwise crowd out recall(); reflection
    # is about what one is actually living through, not scripture.
    lived = [m for m in agent.memory.items if m.source != "doctrine"]
    if not lived:
        return None
    mems = sorted(lived, key=lambda m: m.salience, reverse=True)[:k]
    prompt = build_prompt(agent.name, agent.felt_mood(), [m.text for m in mems])
    try:
        raw = llm.generate(prompt, system=REFLECT_SYSTEM, num_predict=90,
                           temperature=0.7)
    except Exception:  # noqa: BLE001 -- a reflection must never crash the lab/sim
        return None
    text = " ".join(sanitize(raw).split()).strip().strip('"').strip()
    if not text:
        return None
    # Self-regulation: the emotion this reflection imprints is its EQUANIMITY, not
    # the sadness of its words -- so meeting a grief with acceptance SOOTHES the
    # lived mood while restating it ruminatively deepens it. Measured semantically
    # (embeddings) because the sentiment lexicon can't tell sad-toned acceptance
    # from despair; when embeddings are down we fall back to the lexicon (emotion=0
    # lets memory.write derive valence). This is the mind regulating itself through
    # how it relates to its own memory.
    from agent import affect
    from services import embed
    emo = affect.equanimity_emotion(text) if embed.using_embeddings() else 0.0
    # written like a self-statement: it is the agent's own, it counts toward mood
    # (mood() excludes only doctrine), and it feeds the next tick's drift.
    agent.memory.write(text, tick=now, source="reflection",
                       speaker_id=agent.id, emotion=emo, weight=1.0)
    return text
