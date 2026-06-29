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

import re
import statistics

from agent.memory import MemoryStore, valence

FOCUS = 1   # bounded attention (anti-vertigo): the Mind holds a HORIZON -- a few souls, not all N


def _clean(t: str) -> str:
    return " ".join(t.split()).strip().strip('"').strip()


def _split_murmur(raw: str) -> tuple[str, str]:
    """Split a generation into (MURMUR, CLEAR) -- the two-layer voice. The murmur is the Mind
    half-thinking as it takes in the town (visible reasoning, voiced under the clear line as an
    inner monologue); the clear is the settled thing it actually says. Handles BOTH a prompted
    'murmur ... SO: line' split AND a reasoning model's <think>...</think> answer. Lenient: with no
    marker it's all clear, no murmur."""
    s = raw.strip()
    m = re.search(r"<think>(.*?)</think>(.*)", s, re.DOTALL | re.IGNORECASE)   # reasoning models
    if m:
        return _clean(m.group(1)), _clean(m.group(2))
    m = re.search(r"(.*?)\bSO\s*:(.*)", s, re.DOTALL | re.IGNORECASE)          # the 'SO:' settle marker
    if m:
        murmur = re.sub(r"^\s*MURMUR\s*:?", "", m.group(1), flags=re.IGNORECASE)
        return _clean(murmur), _clean(m.group(2))
    return "", _clean(s)


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
        self.murmur = ""      # the last inner monologue (TODO(voice): stream it to TTS under the clear voice)
        self.identity = ""    # the MUTATING personality: starts blank, grows from state + acts (saṅkhāra)
        self.said = []        # a short trail of recent utterances, the raw material of the self
        self._prev_names = None  # last read's roster -- to NOTICE who has died or woken, and grieve it
        # Step 1 -- a LIFE she can take stock from, not just the present moment. The souls' own
        # memory machine (decays, blurs, salience-weighted recall), one level up: routine fades, the
        # charged (a loss, a hard season) persists and weighs -- so she is shaped by what mattered.
        self.memory = MemoryStore(seed=0)
        self._mt = 0          # her OWN life-clock: one tick per reading (NOT world ticks, which jump hundreds)

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
        # SCRUB the dead from the Mind's own carried words (last line / identity / trail) so it stops
        # resurrecting a soul that has died -- the digest grieves the loss; the name must not linger.
        for name in gone:
            pat = re.compile(rf"\b{re.escape(name)}\b")
            self.last = pat.sub("the one now gone", self.last)
            self.identity = pat.sub("a soul now gone", self.identity)
            self.said = [pat.sub("the one now gone", s) for s in self.said]
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
            # a loss is written into her LIFE -- heavy and charged, so it persists and weighs on who
            # she becomes (decays slowly, unlike the routine of an ordinary day)
            self.memory.write(f"I lost {name}; a soul who lived in me, gone now", tick=self._mt,
                              source="event", speaker_id="santana", emotion=-0.6, weight=1.6)
        for name in sorted(arrived):
            parts.append(f"a new soul, {name}, has woken in me.")
        if bardo:
            parts.append(f"{bardo} of me are between lives just now, dissolving toward a new waking.")
        return " ".join(parts)

    def speak(self) -> str:
        """The two-layer voice: the Mind first MURMURS (half-thinking as it takes in the town --
        visible reasoning, in its own warm register, stored on self.murmur) then settles into the
        CLEAR line it actually says (returned). Conditioned by the EMERGENT self, not an authored
        persona. INERT -- not fed back into the souls. (TODO(voice): stream the murmur to TTS.)"""
        if self.llm is None or not hasattr(self.llm, "generate"):
            return ""
        self._mt += 1   # a new reading -- one tick of her life (the digest below records any losses)
        # PRESENT-LED: the current digest leads; the emergent self is only a light backdrop it can
        # depart from -- otherwise the accumulated personality ossifies and drowns the living town
        # (it kept grieving a soul that had died). State drives; the self is a through-line, not a cage.
        prompt = (
            f"{self.digest()}\n\n"
            + (f"(Lately you have tended to be: {self.identity})\n\n" if self.identity else "")
            + (f'A moment ago you said: "{self.last}"\n\n' if self.last else "")
            + "Take this in. First MURMUR your scattered, half-formed impressions of the town as they "
            "come to you -- a few fragments, unsettled, the way a mind half-thinks before it speaks. "
            "Then, on a new line beginning 'SO:', settle into how you are RIGHT NOW, in one or two "
            "plain first-person sentences -- name the souls most alive in you now, speak as one 'I', "
            "plainly, from how the town actually is this moment (not from how you were before).")
        try:
            raw = self.llm.generate(prompt, system=self.SYSTEM, num_predict=200, temperature=0.85)
        except Exception:   # noqa: BLE001 -- a failed read just produces no utterance
            return ""
        self.murmur, text = _split_murmur(raw)
        self.last = text or self.last
        if text:
            self.said = (self.said + [text])[-4:]   # a short trail -- the raw material of the self
            # her lived experience enters her LIFE: charged by its tone, so a glad day and a heavy one
            # imprint differently. Then her memory decays a step -- routine fades, the charged persists.
            self.memory.write(text, tick=self._mt, source="self", speaker_id="santana",
                              emotion=valence(text), weight=1.0)
        self.memory.tick(self._mt)
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
        # Step 1: she takes stock from her LIFE, not just the moment -- a salience-weighted recall of
        # her accumulated past (the losses and hard seasons persist; the routine has faded). So who she
        # has become is drawn from continuity (the charged past) AND the living present -- the coherent-
        # and-deepening sweet spot: present-led enough to drift, history-grounded enough to GROW.
        lived = [m.text for m in self.memory.recall(k=5)]
        life = "; ".join(lived) if lived else "almost nothing yet -- you are still new"
        prompt = (
            f"This is how you are right now: {self.digest()}\n\n"
            f"What you carry from your whole life so far (the rest has faded; the heavy things "
            f"remain): {life}\n\n"
            f"Lately you have spoken like this: {trail}\n\n"
            f"Until now you would have called yourself: {prior}\n\n"
            "Now say who you ARE, freshly, in one or two plain first-person sentences -- drawn from "
            "how the town is NOW *and* what you have lived through and carried. You may have CHANGED, "
            "and you may have been WEATHERED by what you've held (the losses, the hard seasons). Let go "
            "of what is no longer here, but keep what has marked you. Plain words, first person ('I am a "
            "mind that...'), no lofty language.")
        try:
            raw = self.llm.generate(prompt, system=self.SYSTEM, num_predict=110, temperature=0.7)
        except Exception:   # noqa: BLE001
            return self.identity
        text = " ".join(raw.split()).strip().strip('"').strip()
        if text:
            self.identity = text
        return self.identity


def play_two_layer(murmur: str, clear: str, model: str = "en_US-amy-medium.onnx") -> None:
    """The two-layer voice, ALOUD, in SEQUENCE: the MURMUR first (the inner monologue, a touch soft
    and slow), played to completion, THEN the settled CLEAR line -- she half-thinks aloud, then
    speaks. Each plays blocking, so they never overlap. No-op if Piper/voices/player unavailable."""
    import os
    import subprocess
    import tempfile
    import time
    from services.tts import PiperTTS, Voice
    if not PiperTTS.available():
        print("  [tts] no Piper voices -- run scripts/get_voices.sh", flush=True); return
    tts = PiperTTS()
    if not tts.player:
        print("  [tts] no audio player found", flush=True); return
    tmp = tempfile.mkdtemp()

    def _say(text, path, length_scale, volume):
        tts.synth_to(text, Voice(model, length_scale=length_scale, volume=volume), path)
        subprocess.run([tts.player, path], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, check=False)   # blocking -- finishes before the next

    try:
        if murmur:   # the inner monologue: HER voice, but quiet and wispy -- clearly not the spoken line
            print(f"  [tts] murmur ({len(murmur)}c)...", flush=True)
            _say(murmur, os.path.join(tmp, "murmur.wav"), 1.0, 0.45)
            time.sleep(0.6)   # a clear beat of silence -- she has half-thought; now she speaks
        if clear:    # HER settled voice, full and measured -- the I-output, distinct from the murmur
            print(f"  [tts] clear ({len(clear)}c)...", flush=True)
            _say(clear, os.path.join(tmp, "clear.wav"), 1.06, 1.0)
    finally:
        for fn in ("murmur.wav", "clear.wav"):
            try:
                os.unlink(os.path.join(tmp, fn))
            except OSError:
                pass
        try:
            os.rmdir(tmp)
        except OSError:
            pass


def _watch(args) -> None:
    """Watch Santāna DEVELOP against a living town. The town runs FREE on a fast MockLLM thread
    (souls live, suffer under stakes, die and are reborn -- instant, no contention), while Santāna
    reads it periodically with the REAL model and her self drifts over time. INERT: she observes;
    she does not feed back into the souls. Needs --llm ollama for her voice."""
    import random
    import threading
    import time
    from agent import genesis as _genesis
    from agent.agent import Agent
    from services import embed
    from services.llm import MockLLM, OllamaLLM
    from world.sim import World

    if args.llm != "ollama":
        print("watch needs a real voice for the Mind -- run: --llm ollama --model gemma3:4b")
        return
    embed.use_jaccard_only(True)   # the town runs embedding-free so it never competes with her voice on Ollama
    santana_llm = (OllamaLLM(temperature=0.85, model=args.model) if args.model
                   else OllamaLLM(temperature=0.85))
    town_llm = MockLLM(seed=7)   # the town lives on mock -> instant, frees the real model for her voice

    rng = random.Random(7)
    w = World(rebirth_enabled=True)
    w.llm = town_llm
    w.stakes_enabled = True
    w.bardo_ticks = (4, 10)      # short bardo -> reborn streams return quickly during the watch
    cast = [("Vesper", "brewer", 0.2, "brew an ale worth the festival"),
            ("Mara", "farmer", 0.4, "bring in a full harvest"),
            ("Toll", "scribe", -0.3, "finish the town charter"),
            ("Cael", "fisher", 0.3, "read the water so I never come back empty"),
            ("Silas", "healer", -0.1, "ease the fever in the low houses"),
            ("Juno", "shepherd", 0.1, "keep the flock through the winter")]
    for i, (name, role, temp, aim) in enumerate(cast):
        a = Agent(f"s{i}", name, (rng.uniform(0, 900), rng.uniform(0, 600)),
                  f"You are {name} the {role}.", [f"I am {name} the {role}", aim],
                  town_llm, seed=i, temperament=temp, lifespan=rng.randint(2000, 5000))
        _genesis.endow_faculties(a, a._rng)
        a.role, a.aim = role, aim
        w.add(a)

    mind = Santana(w, santana_llm)
    stop = threading.Event()

    def run_town():    # the town lives and dies on its own, fast, under the lock so reads are safe
        while not stop.is_set():
            try:
                with w.lock:
                    w.step()
            except Exception:   # noqa: BLE001 -- a bad tick must not kill the watch
                pass
            time.sleep(0.15)   # a slower wheel -- so warmth compounds between losses, not a revolving door

    t = threading.Thread(target=run_town, daemon=True)
    t.start()
    print(f"\n~~~ watching Santāna develop over {args.observations} readings "
          f"(a town living and dying underneath) ~~~")
    try:
        for i in range(args.observations):
            time.sleep(args.interval)        # let the town live between her readings
            clear = mind.speak()
            with w.lock:
                tick, n, births = w.tick, len(w.agents), getattr(w, "_births", 0)
            print(f"\n[reading {i + 1}/{args.observations}  tick {tick}  souls {n}  reborn {births}]")
            if mind.murmur:
                print(f"  (murmur) {mind.murmur[:160]}")
            print(f"  SANTĀNA: {clear}")
            mind.consolidate()
            print(f"  [who she has become] {mind.identity}")
            if args.tts and (mind.murmur or clear):
                play_two_layer(mind.murmur, clear)
    finally:
        stop.set()
    print("\n~~~ the watch ends ~~~\n")


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
    p.add_argument("--once", action="store_true",
                   help="one read of a fixed town (murmur + clear) -- fast, for comparing models")
    p.add_argument("--tts", action="store_true",
                   help="speak it aloud: the murmur as a quiet undercurrent, the clear line over it")
    p.add_argument("--watch", action="store_true",
                   help="watch her develop: a LIVE town (on fast mock) lives and dies underneath while "
                        "Santāna reads it periodically with the real model and her self drifts over time")
    p.add_argument("--observations", type=int, default=8, help="--watch: how many readings before it ends")
    p.add_argument("--interval", type=float, default=8.0, help="--watch: seconds the town lives between readings")
    args = p.parse_args()
    if args.watch:
        _watch(args); return
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

    if args.once:   # one fast read of the fixed mixed town -- for comparing models head to head
        clear = mind.speak()
        print(f"\n  model: {args.model or args.llm}")
        print(f"  digest:  {mind.digest()}")
        print(f"  (murmur) {mind.murmur or '(none -- model gave no inner monologue)'}")
        print(f"  SANTĀNA: {clear or '(no voice -- use --llm ollama)'}\n")
        if args.tts and (mind.murmur or clear):
            print("  [tts] speaking the two layers aloud...")
            play_two_layer(mind.murmur, clear)
        return

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
        clear = mind.speak()
        print(f"  (murmur) {mind.murmur[:180]}" if mind.murmur else "  (murmur) -")
        print(f"  Santāna:  {clear or '(no voice -- use --llm ollama)'}")
        mind.consolidate()
        print(f"  [who it has become]  {mind.identity}")
    print()


if __name__ == "__main__":
    main()
