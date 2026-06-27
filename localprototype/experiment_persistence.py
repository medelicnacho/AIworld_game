"""STAGE 5 -- does a SELF survive death? The deepest anattā question the project can
ask, made measurable.

The self-model (the autobiography: "Silas of Oakhaven, my grandfather's laughter") is
NOT carried across the bardo -- that would be transmitting a self, which the wheel
forbids. Only vāsanā crosses: the blurred drift residue, the opinion/stance lean. So
if a reborn stream re-consolidates a self-model that resembles the DEAD soul's more
than a STRANGER's, a self-PATTERN has survived through the impersonal residue alone --
continuity without a transmitted essence. If it resembles the stranger just as much,
no self survived; only generic drift did.

Design: two thematically DISTINCT souls A (the sea) and C (fire/forge). A consolidates
a self-model S_A, then dies; a new stream R coalesces from A's vāsanā only and
consolidates S_R. Measure (embeddings):  sim(S_R, S_A)  vs  sim(S_R, S_C).

Needs a capable model: on gemma3:1b every consolidation collapses into the same
grief/"I am becoming" register, which swamps the sea-vs-forge signal (the reborn self
scores ~equal to both). On gemma3:4b the signal is clean.

Run:  python experiment_persistence.py --llm ollama --model gemma3:4b
"""

from __future__ import annotations

import argparse

from agent import self_model as _sm
from agent.agent import Agent
from services.embed import score
from services.llm import MockLLM, OllamaLLM
from world.sim import World

# Two MAXIMALLY DISTINCT souls, hand-authored on purpose: the homogeneous 1b genesis
# makes every soul a grandmother-and-loss vessel, which defeats the discrimination this
# test needs (a reborn self can only "resemble its predecessor more than a stranger" if
# predecessor and stranger actually differ). So we control that confound here.
SEA_LINES = [
    "The tide drags everything under in the end.",
    "Salt has cracked my hands raw since I was a boy.",
    "I was born on the grey water and I will end there.",
    "My father rowed out one morning and the sea kept him.",
    "The drowned do not come back; the water only keeps taking.",
    "I read the swell and the weather the way others read faces.",
]
FORGE_LINES = [
    "The forge eats the dark and gives back iron.",
    "I was raised in cinder and ash and the ring of the hammer.",
    "Fire purifies what it takes; nothing wasted, nothing mourned.",
    "My hands are scarred by coals and I am proud of every burn.",
    "A blade is honest: it is exactly as true as the smith who made it.",
    "I shape hard things into useful ones; that is my whole creed.",
]


def _make_soul(w, aid, name, temp, lines, llm):
    a = Agent(aid, name, (0.0, 0.0), f"You are {name}.", list(lines), llm,
              seed=hash(aid) & 0xFFFF, lifespan=10 ** 9, temperament=temp)
    for ln in lines:
        a.memory.write(ln, tick=0, source="self", speaker_id=aid, weight=1.4)
    a.belief = lines[0]
    a.seed_opinion_text(" ".join(lines))
    a.self_model_enabled = True
    a.bond_enabled = True
    a.concept_speech = True
    w.add(a)
    return a


def _consolidate_living(w, llm, t):
    for a in w.agents:
        if a.self_model_enabled:
            _sm.consolidate(a, llm, t)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--llm", choices=["mock", "ollama"], default="mock")
    p.add_argument("--model", default=None)
    p.add_argument("--seed", type=int, default=5)
    args = p.parse_args()
    llm = (OllamaLLM(temperature=0.8, model=args.model) if args.model else OllamaLLM(temperature=0.8)) \
        if args.llm == "ollama" else MockLLM(seed=args.seed)

    w = World(rebirth_enabled=True)
    w.hearing_range = 1e12
    w.llm = llm
    w.bond_vasana = 0.5
    # suppress speech: the self-model should form from MEMORY + vāsanā, not from lived
    # conversation (which contaminates the residue and adds runtime). This isolates the
    # question -- does the impersonal residue encode the self -- from the chatter.
    w.speak_threshold = 1e9
    print("two distinct souls: a sea-soul and a forge-soul...", flush=True)
    A = _make_soul(w, "A", "Maren", -0.4, SEA_LINES, llm)
    C = _make_soul(w, "C", "Brand", 0.0, FORGE_LINES, llm)
    print(f"  A = {A.name} (sea), C = {C.name} (forge)\n--- A lives ---", flush=True)

    for t in range(1, 25):
        w.run(1)
        if t % 8 == 0:
            _consolidate_living(w, llm, t)
    S_A = A.self_model
    S_C = C.self_model
    print(f"  S_A ({A.name}): {S_A}")
    print(f"  S_C ({C.name}): {S_C}")

    # A dies -- dissolve it WITHOUT shrinking its lifespan (so the reborn stream lives)
    print("\n--- A dies; only its vāsanā enters the bardo (no self-model crosses) ---", flush=True)
    w.bardo_ticks = (1, 1)
    w._dissolve(A)
    w.agents = [x for x in w.agents if x is not A]
    w.run(2)                                  # ripen -> a new stream coalesces
    streams = [x for x in w.agents if x.id.startswith("stream:")]
    if not streams:
        print("  (no stream reborn -- abort)")
        return
    R = streams[0]
    print(f"  reborn stream: {R.name} (id {R.id}); self_model so far: {R.self_model!r}")

    # Isolate R so its self re-forms from A's vāsanā ALONE -- without this, 20 ticks of
    # conversation with the forge-stranger contaminate the residue and wash it out (which
    # is itself telling: a self is fragile across the gap). This tests the cleaner
    # question: does the impersonal residue ENCODE the self enough to re-grow it?
    w.agents = [R]

    print("\n--- R lives ALONE and re-consolidates a self from the residue ---", flush=True)
    for t in range(25, 45):
        w.run(1)
        if t % 6 == 0:
            _sm.consolidate(R, llm, t)
    S_R = R.self_model
    print(f"  S_R ({R.name}): {S_R}")

    to_dead = score(S_R, S_A) if (S_R and S_A) else 0.0
    to_stranger = score(S_R, S_C) if (S_R and S_C) else 0.0
    print("\n=== Stage 5: does a self survive death? ===")
    print(f"  sim(S_R, S_A dead self):     {to_dead:+.3f}")
    print(f"  sim(S_R, S_C stranger self): {to_stranger:+.3f}")
    survived = to_dead > to_stranger + 0.02
    print("  -> " + (
        "A SELF SURVIVED: the reborn self re-cohered toward the dead one -- from vāsanā "
        "alone, no autobiography crossed. Continuity without a transmitted essence (anattā)."
        if survived else
        "no self survived: the reborn self resembles a stranger as much as its predecessor "
        "-- only generic drift carried, not a self-pattern."))


if __name__ == "__main__":
    main()
