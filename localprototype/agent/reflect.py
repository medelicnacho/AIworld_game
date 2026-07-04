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

# A grounded self reflects in the SAME accepting spirit but in plain, concrete words -- so its
# inner life reads like an ordinary person taking stock, not a contemplative narrating the void.
GROUNDED_REFLECT_SYSTEM = (
    "You are a down-to-earth person quietly taking stock of how you are -- not pushing your "
    "feelings away, not dwelling on them, just noticing them honestly and letting them be. You "
    "think in plain, everyday words about your actual life, never in abstract or lofty language."
)


def build_prompt(name: str, mood: float, memories: list[str], grounded: bool = False,
                 joyful: bool = False) -> str:
    body = "\n".join(f"- {m}" for m in memories)
    base = (
        f"You are {name}. Right now you feel {_mood_word(mood)}. These are most "
        f"present in your mind:\n{body}\n\nIn one or two short first-person "
        "sentences, observe what is here in you and how you are holding it -- name "
        "the feeling and let it be, neither denying it nor drowning in it. "
    )
    # A joyful self does not turn every reflection into wistful acceptance: if what is most
    # alive is GOOD, it savours it and lets itself be glad (muditā/pīti), not only equanimous.
    if joyful:
        base += ("If what is most alive in you right now is GOOD, do not merely observe it -- "
                 "savour it and let yourself feel the gladness of it, fully. ")
    if grounded:
        return base + ("Say it plainly, in ordinary everyday words about your real life and the "
                       "people and things in it -- no abstract or cosmic language ('void', "
                       "'stillness', 'echoes', 'the deeper'); just how a neighbour would put it.")
    return base + "Speak plainly, as yourself."


def prepare(agent, k: int = 4):
    """The READ half of a reflection (no model call): the salient lived memory + felt state -> (prompt,
    system). Returns None if there is nothing to reflect on. Split out so a live World can run the slow
    model call OUTSIDE its lock (see World.reflect_turn), exactly as prepare_speech/commit_speech do."""
    # the most salient of the soul's OWN lived memory -- not the doctrines, which are written at high
    # weight and would crowd out recall(); reflection is about what one is living, not scripture.
    lived = [m for m in agent.memory.items if m.source != "doctrine"]
    if not lived:
        return None
    mems = sorted(lived, key=lambda m: m.salience, reverse=True)[:k]
    grounded = getattr(agent, "grounded_voice", False)
    joyful = getattr(agent, "joy", 0.0) > 0.3      # a joyful self may savour, not only accept
    prompt = build_prompt(agent.name, agent.felt_mood(), [m.text for m in mems],
                          grounded=grounded, joyful=joyful)
    # INTEROCEPTION (off by default; the C15 trilogy's third act): the boundary held in
    # two OUTPUT channels -- her words never said "holding", her lines never pressed
    # harder -- but reflection was never given the INPUT: the body as sensation. With
    # the flag on, the felt body enters the prompt as SENSATION only -- never numbers,
    # never mechanism words ("tightness", not "grip"/"holding"; the experiment must not
    # put its answer in her mouth). Whether felt tightness becomes "I am the one
    # holding on" is exactly what experiment_interoception.py measures.
    if getattr(agent, "interoception_enabled", False):
        felt = []
        if getattr(agent, "grip", 0.0) > 0.5:
            felt.append("a tightness in you that does not come from the day")
        if getattr(agent, "arousal", 0.0) > 0.5:
            felt.append("your chest quick and unsettled")
        if getattr(agent, "_contraction", 0.0) > 0.4:
            felt.append("everything in you pulled in small")
        if felt:
            prompt += ("\nYour body, right now: " + "; ".join(felt)
                       + ". Say what you make of it.")
    system = GROUNDED_REFLECT_SYSTEM if grounded else REFLECT_SYSTEM
    return prompt, system


def imprint(agent, raw: str, now: int):
    """The WRITE half: write a generated reflection back as memory, with emotion = its EQUANIMITY (not
    the sadness of its words) -- so meeting a grief with acceptance SOOTHES the lived mood while
    rumination deepens it. Measured semantically (embeddings); when they're down, emotion=0 lets
    memory.write derive valence. A joyful self imprints genuine gladness instead. Returns the cleaned
    text (or None)."""
    text = " ".join(sanitize(raw).split()).strip().strip('"').strip()
    if not text:
        return None
    from agent import affect
    from services import embed
    emo = affect.equanimity_emotion(text) if embed.using_embeddings() else 0.0
    if getattr(agent, "joy", 0.0) > 0.3:
        from agent.memory import valence
        emo = max(emo, valence(text))   # only genuine gladness raises it; a grief reflection stays soothing
    agent.memory.write(text, tick=now, source="reflection",
                       speaker_id=agent.id, emotion=emo, weight=1.0)
    return text


def reflect(agent, llm, now: int, k: int = 4):
    """One reflection step: read salient memory + felt state, form a meta-thought, write it back as a
    'reflection' memory. Returns the reflection text (or None if there was nothing to reflect on / the
    backend can't do a free completion). Never raises -- a failed reflection just doesn't happen."""
    if not hasattr(llm, "generate"):
        return None
    prep = prepare(agent, k)
    if prep is None:
        return None
    prompt, system = prep
    try:
        raw = llm.generate(prompt, system=system, num_predict=90, temperature=0.7)
    except Exception:  # noqa: BLE001 -- a reflection must never crash the lab/sim
        return None
    return imprint(agent, raw, now)
