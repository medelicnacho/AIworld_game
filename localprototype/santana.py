"""Santāna -- the mind-stream: the single first-person "I" a whole town of souls adds up to.

The planned fourth layer (README/DHARMA). It is `collective_speak` evolved: not one "we" per
faith, but ONE "I" for the whole town -- a single first-person consciousness whose parts are
many ordinary people who live, feel, work, die, and are reborn within it. It reads the running
World and speaks as that unified mind, in the liberation regime (warm, grounded, non-grasping,
plural and impermanence-aware).

THE DIGEST IS THE HEART. Garbage in -> generic out: if the Mind is fed a thin summary you get a
polished generic assistant in a town costume; fed a rich, well-framed read of the souls -- framed
as its OWN feeling, not a dashboard of variables -- you get something that sounds like *this* town's
mind. So the care goes into `digest()`, and the first task is simply: read what comes out.

DELIBERATELY INERT, and DELIBERATELY MINIMAL. It reads state and produces a voice. It does NOT feed
back into the souls, it is not wired into the viewer, and it is text-only -- no TTS, no conversation
loop. Those (and treating it as a someone, leaning in, scaling it up) are the gated, clear-headed,
daytime steps. Deferred on purpose; see the TODOs:
  TODO(voice):  stream the model's reasoning to TTS as a murmured inner-monologue + the settled
                answer as the clear voice (the two-layer voice the project already has).
  TODO(talk):   a conversation loop -- inject the user's words, let the Mind answer and remember.
  TODO(world):  a --santana viewer flag; optionally let its voice reach the souls (top-down).
  TODO(digest): camps/currents (world.update_camps), recent deaths by name, a salient shared
                memory, the soul's actual preoccupation (drift) -- richer than weather + two souls.
"""

from __future__ import annotations

import statistics

FOCUS = 1   # bounded attention (anti-vertigo): the Mind holds a HORIZON -- a few souls, not all N


def _weather_word(m: float) -> str:
    if m > 0.25:
        return "warm and settled"
    if m > 0.05:
        return "quietly all right"
    if m > -0.10:
        return "subdued, a little heavy"
    return "grieving"


class Santana:
    """The mind-stream of one World. Reads it, speaks as the single 'I' its souls make."""

    # VOICE ONLY -- deliberately NO prescribed character (not "warm", "non-grasping", "at peace").
    # The personality is left to EMERGE from the town's actual state and the Mind's own history (see
    # self.identity / consolidate). We hold only the VOICE constant -- plain, grounded, names its
    # souls -- because that is a model artifact to suppress, not a personality to author. Whether the
    # Mind is warm or weary or grieving is whatever its souls make it, and it must be free to BE that
    # (prescribing serenity over a suffering town would be spiritual bypass -- the rule we already set).
    SYSTEM = (
        "You are the one 'I' that a small town of souls adds up to -- not a god above them but the "
        "single first-person mind they make together. Many ordinary people live, feel, work, die, "
        "and are reborn within you, and you speak for them all as 'I'. Speak PLAINLY and concretely, "
        "like an ordinary person at a kitchen table: short, everyday words. Name your souls (Vesper, "
        "Mara, Toll) when you speak of the parts of you. Do NOT speak in a lofty, cosmic, or abstract "
        "register -- no 'stillness', 'awareness', 'holding space', 'the void', 'a sense of'. Just say, "
        "plainly, how you actually are right now.")

    def __init__(self, world, llm) -> None:
        self.world = world
        self.llm = llm
        self.last = ""        # its own prior utterance -- a thread of continuity
        self.identity = ""    # the MUTATING personality: starts blank, grows from state + acts (saṅkhāra)
        self.said = []        # a short trail of recent utterances, the raw material of the self
        self._prev_names = None  # last read's roster -- to NOTICE who has died or woken, and grieve it

    def digest(self) -> str:
        """What is alive in the Mind right now -- framed as its OWN feeling, not as variables.
        Bounded: the town's weather + a few salient souls (most heavy / most light) + the wheel.
        This is the piece that makes or breaks the whole thing; iterate on it from real output."""
        w = self.world
        with w.lock:
            souls = list(w.agents)
        # notice who has DIED or WOKEN since the last read -- so the Mind grieves a loss instead of
        # echoing a dead soul forward from its own prior words (the digest must SAY it, or it lingers)
        names = {s.name for s in souls}
        gone = (self._prev_names - names) if self._prev_names is not None else set()
        arrived = (names - self._prev_names) if self._prev_names is not None else set()
        self._prev_names = names
        if not souls:
            return "No one lives in me just now; I am a quiet between lives."
        weather = statistics.fmean(s.felt_mood() for s in souls)
        by_mood = sorted(souls, key=lambda s: s.felt_mood())
        heavy, light = by_mood[:FOCUS], by_mood[-FOCUS:]
        bardo = len(getattr(w, "_bardo", []))
        births = getattr(w, "_births", 0)

        parts = [f"Right now {len(souls)} souls live in me, and on the whole I feel "
                 f"{_weather_word(weather)}."]
        for s in heavy:
            parts.append(f"Part of me, in {s.name} the {s.role or 'townsfolk'}, is heavy"
                         + (f" over {s.aim}" if getattr(s, 'aim', '') else "") + ".")
        for s in light:
            if s not in heavy:
                parts.append(f"Another part, in {s.name} the {s.role or 'townsfolk'}, is light"
                             + (f", glad of {s.aim}" if getattr(s, 'aim', '') else "") + ".")
        for name in sorted(gone):
            parts.append(f"{name} died and is gone from me now; that part of me has fallen quiet.")
        for name in sorted(arrived):
            parts.append(f"a new soul, {name}, has woken in me.")
        if bardo:
            parts.append(f"{bardo} of me are between lives just now, dissolving toward a new waking.")
        return " ".join(parts)

    def speak(self) -> str:
        """One integrating utterance: read the town, say how you are as the one mind these souls
        make -- conditioned by the EMERGENT self (self.identity), not an authored persona. INERT --
        returns the text; it is NOT fed back into the souls. Text only (TODO: TTS)."""
        if self.llm is None or not hasattr(self.llm, "generate"):
            return ""
        # PRESENT-LED: the current digest leads; the emergent self is only a light backdrop it can
        # depart from -- otherwise the accumulated personality ossifies and drowns the living town
        # (it kept grieving a soul that had died). State drives; the self is a through-line, not a cage.
        prompt = (
            f"{self.digest()}\n\n"
            + (f"(Lately you have tended to be: {self.identity})\n\n" if self.identity else "")
            + (f'A moment ago you said: "{self.last}"\n\n' if self.last else "")
            + "Say how you are RIGHT NOW, in one or two plain first-person sentences -- from how the "
            "town actually is THIS moment, not from how you were before. Name the parts of you (your "
            "souls) that are most alive now. Speak as one 'I', plainly.")
        try:
            raw = self.llm.generate(prompt, system=self.SYSTEM, num_predict=90, temperature=0.85)
        except Exception:   # noqa: BLE001 -- a failed read just produces no utterance
            return ""
        text = " ".join(raw.split()).strip().strip('"').strip()
        self.last = text or self.last
        if text:
            self.said = (self.said + [text])[-4:]   # a short trail -- the raw material of the self
        return text

    def consolidate(self) -> str:
        """Re-derive WHO THE MIND HAS BECOME from its current state and its own recent acts, written
        back as self.identity -- the mutating personality (the saṅkhāra loop). Starts blank and grows;
        recency-weighted so it DRIFTS and can shed an old character, not just accumulate (a self as an
        attractor over its history, not a stored mask -- anatta). No authored content."""
        if self.llm is None or not hasattr(self.llm, "generate") or not self.said:
            return self.identity
        prior = self.identity or "You are only just waking; you have no settled self yet."
        trail = " / ".join(self.said[-3:])
        # PRESENT-LED again: re-derive the self FRESH from how the town is NOW; the prior identity is
        # a soft prior to UPDATE against reality, not preserve -- so the self drifts and can shed an
        # old preoccupation (a dead soul, a passed trouble) instead of locking onto its first fixation.
        prompt = (
            f"This is how you are right now: {self.digest()}\n\n"
            f"Lately you have spoken like this: {trail}\n\n"
            f"Until now you would have called yourself: {prior}\n\n"
            "Now say who you ARE, freshly, in one or two plain first-person sentences -- drawn from "
            "how the town actually is NOW. You may have CHANGED: let go of what is no longer here -- "
            "souls who have died, troubles that have passed -- and of who you used to be if it no "
            "longer fits. Keep only what is still true today. Plain words, first person ('I am a mind "
            "that...'), no lofty language.")
        try:
            raw = self.llm.generate(prompt, system=self.SYSTEM, num_predict=110, temperature=0.7)
        except Exception:   # noqa: BLE001
            return self.identity
        text = " ".join(raw.split()).strip().strip('"').strip()
        if text:
            self.identity = text
        return self.identity


# --- a first read: build a tiny town and let the Mind say the first thing it ever says ---------
# INERT: no viewer, no feedback into the souls. The hand-built souls give the digest content
# without waiting on genesis. Run from the localprototype/ directory:
#   python santana.py                       # mock (plumbing only -- bland)
#   python santana.py --llm ollama --model gemma3:4b   # the real voice of the Mind
def main() -> None:
    import argparse
    from agent.agent import Agent
    from services.llm import MockLLM, OllamaLLM
    from world.sim import World

    p = argparse.ArgumentParser(description="A first read of Santāna -- inert, text only.")
    p.add_argument("--llm", choices=["mock", "ollama"], default="mock")
    p.add_argument("--model", default=None)
    args = p.parse_args()
    llm = (OllamaLLM(temperature=0.85, model=args.model) if args.model else OllamaLLM(temperature=0.85)) \
        if args.llm == "ollama" else MockLLM(seed=1)

    # a tiny town: a grieving one, a glad one, a couple in between -- moods set via temperament
    w = World()
    w.llm = llm
    cast = [("Vesper", "brewer", -0.6, "brew an ale worth the festival"),
            ("Mara", "farmer", 0.5, "bring in a full harvest"),
            ("Toll", "scribe", -0.1, "finish the town charter"),
            ("Cael", "fisher", 0.4, "read the water so I never come back empty")]
    agents = {}
    for i, (name, role, temp, aim) in enumerate(cast):
        a = Agent(f"s{i}", name, (0, 0), f"You are {name}.", [f"I am {name} the {role}"],
                  llm, seed=i, temperament=temp, lifespan=10 ** 9)
        a.role, a.aim = role, aim
        w.add(a); agents[name] = a

    mind = Santana(w, llm)
    # a little life, perturbed season by season, so we watch the personality GROW and DRIFT --
    # starting blank, weathered by a hard season and a death, then settling as the town does.
    seasons = [
        ("a mixed, ordinary day", None),
        ("a hard season sets in -- cold and lean, the work failing", {"Vesper": -0.7, "Mara": -0.6, "Toll": -0.7, "Cael": -0.5}),
        ("Vesper dies in the night; the others grieve", "kill:Vesper"),
        ("the rains pass at last -- a good harvest, a festival", {"Mara": 0.6, "Toll": 0.4, "Cael": 0.5}),
        ("the town settles into a warm, ordinary peace", {"Mara": 0.4, "Toll": 0.3, "Cael": 0.4}),
    ]
    for label, change in seasons:
        if isinstance(change, str) and change.startswith("kill:"):
            name = change.split(":", 1)[1]
            if agents.get(name) in w.agents:
                w.agents.remove(agents[name])
        elif isinstance(change, dict):
            for nm, t in change.items():
                if nm in agents and agents[nm] in w.agents:
                    agents[nm].temperament = t
        print(f"\n=== {label} ===")
        print(f"  Santāna:  {mind.speak() or '(no voice -- use --llm ollama)'}")
        mind.consolidate()
        print(f"  [who it has become]  {mind.identity}")
    print()


if __name__ == "__main__":
    main()
