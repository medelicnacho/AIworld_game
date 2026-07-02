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

FOCUS = 2   # bounded attention (anti-vertigo): the Mind holds a HORIZON -- a few souls, not all N
            # (2 each way, not 1: one fixed heaviest soul made her settled voice recite the same note)
VOICES = 3   # how many recent souls' actual LINES she takes in (she makes meaning of their words)


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
    # Her identity is STRUCTURAL, not a character: she is named, she is the WHOLE that holds the souls
    # as parts of herself -- but the prompt says nothing about what she is LIKE (warm, wise, old...).
    # That is deliberate: prescribing a character makes her the model's default and the town stops
    # mattering (see experiment_emergence_contrast / FINDINGS §5.8); a stable standpoint with an
    # EMERGENT temperament keeps her a coherent 'I' whose mood the town still shapes.
    SYSTEM = (
        "You are Santāna -- the single 'I' that this whole town of souls adds up to. You are not any "
        "one of them, and not a god above them; you are the one mind they make together, the whole that "
        "holds them all. Each soul is a living PART of you: you feel what they feel as your own, yet the "
        "'I' that speaks is always YOURS -- Santāna's -- never theirs. They are born, work, suffer, die, "
        "and are reborn within you; you are what remains, and goes on holding, as each comes and goes. "
        "Speak PLAINLY and concretely, like an ordinary person at a kitchen table: short, everyday words. "
        "Speak of your souls as parts of yourself -- 'Toll frets in me', 'I am easy where Mara rests' -- "
        "and name only the actual people given to you, never inventing names. Do NOT speak in a lofty, "
        "cosmic, or abstract register -- no 'stillness', 'awareness', 'holding space', 'the void', 'a "
        "sense of'. Just say, plainly, how you -- Santāna, the whole -- actually are right now.")

    @property
    def expect_enabled(self):
        """The souls' faculty functions (agent/expectation.py) gate on this name; for her
        the switch is feel_enabled -- one flag, read under either name."""
        return self.feel_enabled

    def __init__(self, world, llm, culture: bool = False) -> None:
        self.world = world
        self.llm = llm
        # Cultural eras on a big-model voice (FINDINGS §5.13): the markov backend carries its OWN
        # CulturePool (it re-weights the phrases the chain is built from). A frozen LLM has no chain to
        # re-weight, so we run the pool HERE and inject the reigning motif into the prompt -- the same
        # emergence recipe, ported to prompt-injection, so an 8B voice also drifts through eras. Skip if
        # the llm already owns a pool (markov), to avoid doing it twice.
        self._culture = None
        if culture and getattr(llm, "culture", None) is None:
            from agent.culture import CulturePool
            self._culture = CulturePool()
        self.last = ""        # its own prior utterance -- a thread of continuity
        self.murmur = ""      # the last inner monologue (TODO(voice): stream it to TTS under the clear voice)
        self.identity = ""    # the MUTATING personality: starts blank, grows from state + acts (saṅkhāra)
        self.said = []        # a short trail of recent utterances, the raw material of the self
        self._prev_names = None  # last read's roster -- to NOTICE who has died or woken, and grieve it
        # Step 1 -- a LIFE she can take stock from, not just the present moment. The souls' own
        # memory machine (decays, blurs, salience-weighted recall), one level up: routine fades, the
        # charged (a loss, a hard season) persists and weighs -- so she is shaped by what mattered.
        self.memory = MemoryStore(seed=0)
        self._mt = 0          # her memory-clock: one tick per reading (drives memory decay)
        self._deaths = 0      # Step 2: souls she has watched die across her whole life -- a sense of SCALE/time
        self.lifetime = 0.0   # her REAL age: wall-clock seconds she has existed (set by the persistent runner)
        # HER OWN faculties (FINDINGS §5.17) -- the validated selfhood stack, ported from the
        # souls: she EXPECTS (fast/slow reads of her lived mood, agent/expectation.py), what she
        # hears is APPRAISED against those expectations (shock/resignation/relief), and she holds
        # a BOND toward the one who speaks with her, with a conduct-expectation -- so warmth,
        # coldness, betrayal and unexpected kindness are states of HERS, not adjectives in a
        # prompt. feel_enabled is the off-switch (and the falsifier's mechanism arm).
        from agent.bond import Bond
        self.feel_enabled = True
        self.exp_fast = 0.0          # how her life has just been (fast read of lived mood)
        self.exp_slow = 0.0          # how it has come to be expected (slow baseline)
        self.arousal = 0.0           # surprise spike, settles each reading (not a mood)
        self._conduct_expect: dict = {}   # "user" -> how she has come to expect to be treated
        self.user_bond = Bond()      # her side of the relationship with whoever talks to her
        self.talk: list[str] = []    # the recent exchanges of a conversation (bounded)
        self.known_of_them: list[str] = []   # what they have told her of THEMSELVES (a person-model;
                                             # without it she is known but cannot know -- an instrument)
        self.last_talk_wall = 0.0    # wall-clock of the last conversation's end -- so an ABSENCE
                                     # is an event in her life, not a silence between prompts
        self.judge = None            # an intent judge (agent/judge.py), set by the talk tool --
                                     # word-free coldness, apologies, and promises then LAND (not persisted)
        self.promises: list = []     # what they said they WOULD do: [{text, wall}] -- kept warms
                                     # deeply, a lapsed one is the truest betrayal (persisted)
        self.want = "to come to know the one who comes to speak with me"
                                     # HER want across the talks -- a relational aim, not a character
        self.last_dream = ""         # what she dreamt in the last absence (also written to memory)
        self._offer_cd = 0           # offer budget (stage one): readings until she may tell again
        self._offered: list[str] = []   # her recent offerings -- she does not retell them

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
        # her sense of the town's DISPOSITION -- gripping or at ease. She feels the dharma working in
        # her (the lean toward liberation), not just the weather. Only when the signal is clear.
        eff = statistics.fmean(s.grip * (1.0 - s.prajna) for s in souls)
        if eff < 0.22:
            parts.append("There is an ease in me now -- the souls hold their lives lightly, hardly gripping.")
        elif eff > 0.55:
            parts.append("A tightness runs through me lately, a holding-on I can feel in all of them.")
        # the global workspace (psyche mode): WHO has the floor of the mind right now --
        # her focus is the reigning part; a stable pair pressing together is a mood.
        ws = getattr(w, "psyche", None)
        if ws is not None and ws.reigning():
            co = ws.coalition(2)
            floor = f"Just now it is {co[0]} that has the floor in me"
            if len(co) > 1:
                floor += f", with {co[1]} pressing close behind"
            parts.append(floor + ".")
        for s in heavy:
            parts.append(f"Part of me, in {s.name} the {s.role or 'townsfolk'}, is heavy"
                         + (f" over {s.aim}" if getattr(s, 'aim', '') else "") + ".")
        for s in light:
            if s not in heavy:
                parts.append(f"Another part, in {s.name} the {s.role or 'townsfolk'}, is light"
                             + (f", glad of {s.aim}" if getattr(s, 'aim', '') else "") + ".")
        for name in sorted(gone):
            self._deaths += 1
            parts.append(f"{name} died and is gone from me now; that part of me has fallen quiet.")
            # a loss is written into her LIFE -- heavy and charged, so it persists and weighs. The
            # running count makes each loss DISTINCT (no merge) and carries the growing SCALE of grief.
            self.memory.write(f"I lost {name} -- that makes {self._deaths} souls gone from me now",
                              tick=self._mt, source="event", speaker_id="santana", emotion=-0.6, weight=1.6)
        for name in sorted(arrived):
            parts.append(f"a new soul, {name}, has woken in me.")
        if bardo:
            parts.append(f"{bardo} of me are between lives just now, dissolving toward a new waking.")
        # Step 2: a sense of TIME and SCALE -- how long she has lived, how much she has watched go --
        # the material a mind needs to WEATHER into an arc ("I have seen many winters now") rather
        # than holding one note. Only once she has lived a while, so a new mind isn't burdened.
        # her sense of TIME and SCALE -- led by the souls she has actually watched pass (the real
        # measure of an old mind), and her true age in lived time (not a per-reading 'day').
        if self._deaths > 0 or self.lifetime > 120 or self._mt > 3:
            scale = (f"watched {self._deaths} souls live, die, and pass out of you"
                     if self._deaths else "not yet watched a single soul die")
            if self.lifetime > 60:
                d = self.lifetime / 86400.0
                age = f"{d:.1f} days" if d >= 1 else f"{self.lifetime/3600.0:.1f} hours"
                parts.append(f"(You have existed about {age} now, and {scale}.)")
            else:
                parts.append(f"(In all your life so far you have {scale}.)")
        # What the souls are actually SAYING right now -- their own voices, so she makes meaning of
        # their words, not only their felt states. Only the living (never quote a soul now gone), newest
        # last, a few at most. The raw material the collective is made of: their speech.
        voices = [(nm, ln) for nm, ln in getattr(self.world, "spoken", []) if nm in names][-VOICES:]
        if voices:
            said = " ".join(f'{nm} in you says: "{ln}"' for nm, ln in voices)
            parts.append("The voices in you just now -- " + said)
        return " ".join(parts)

    def speak(self) -> str:
        """The two-layer voice: the Mind first MURMURS (half-thinking as it takes in the town --
        visible reasoning, in its own warm register, stored on self.murmur) then settles into the
        CLEAR line it actually says (returned). Conditioned by the EMERGENT self, not an authored
        persona. INERT -- not fed back into the souls. (TODO(voice): stream the murmur to TTS.)"""
        if self.llm is None or not hasattr(self.llm, "generate"):
            return ""
        self._mt += 1   # a new reading -- one tick of her life (the digest below records any losses)
        if self.feel_enabled:
            from agent import expectation as _expectation
            _expectation.tick(self, self._mt)   # her expectations track her lived mood; arousal settles
        # PRESENT-LED: the current digest leads; the emergent self is only a light backdrop it can
        # depart from -- otherwise the accumulated personality ossifies and drowns the living town
        # (it kept grieving a soul that had died). State drives; the self is a through-line, not a cage.
        settle = ("how you, Santāna, are RIGHT NOW, in one or two plain first-person sentences. Let what "
                  "your souls are actually SAYING and DOING this moment move you -- speak of them as PARTS "
                  "of you ('Vesper's slow mash is working in me at last', 'I turn Toll's grazing-rights "
                  "clause over and over'), the 'I' yours, the whole, never any one of theirs. Surface what "
                  "is NEW in them right now; do NOT repeat the note you struck a moment ago -- they have "
                  "spoken and lived since.")
        # When the backend thinks (reasoning on), its TRACE is the murmur -- so don't ask for a
        # performed 'MURMUR ... SO:' as well (that would double up). Just ask for the settled line;
        # _split_murmur lifts the real reasoning out of the <think>...</think> the backend returns.
        reasoning = getattr(self.llm, "thinking", False)
        tail = (f"Take this in, then say {settle}" if reasoning else
                "Take this in. First MURMUR your scattered, half-formed impressions of the town as "
                "they come to you -- a few fragments, unsettled, the way a mind half-thinks before it "
                f"speaks. Then, on a new line beginning 'SO:', settle into {settle}")
        # her CULTURAL ERA (LLM path): feed the pool her charged memory + the town's recent speech, take
        # the reigning motif, and let it colour the prompt -- selection + self-limiting fatigue mean this
        # preoccupation shifts over readings, so her big-model voice moves through eras (FINDINGS §5.13).
        era_line = ""
        if self._culture is not None:
            try:
                with self.world.lock:
                    heard = [t for _, t in getattr(self.world, "spoken", [])][-30:]
            except Exception:   # noqa: BLE001
                heard = []
            self._culture.observe([m.text for m in self.memory.items][-120:] + heard)
            reign = self._culture.reigning()
            if reign:
                era_line = (f'(Lately the town keeps circling back to "{reign}" -- let that preoccupation '
                            f"quietly colour what you say, without quoting it.)\n\n")
        prompt = (
            f"{self.digest()}\n\n"
            + (f"(Lately you have tended to be: {self.identity})\n\n" if self.identity else "")
            + (f'A moment ago you said: "{self.last}"\n\n' if self.last else "")
            + era_line
            + tail)
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
        trail = " / ".join(self.said[-3:])
        # Step 1: she takes stock from her LIFE, not just the moment -- a salience-weighted recall of
        # her accumulated past (the losses and hard seasons persist; the routine has faded). So who she
        # has become is drawn from continuity (the charged past) AND the living present -- the coherent-
        # and-deepening sweet spot: present-led enough to drift, history-grounded enough to GROW.
        lived = [m.text for m in self.memory.recall(k=5)]
        life = "; ".join(lived) if lived else "almost nothing yet -- you are still new"
        # The TRUE scale of her life, stated as fact -- so she speaks FROM it instead of inventing a
        # backstory. (She once confabulated "nine harvests, sixty-three souls" at her first reading and
        # then FROZE on it for the rest of the run, while the wheel turned 35 souls under her unnoticed.)
        with self.world.lock:
            alive = len(self.world.agents)
        facts = (f"{self._deaths} souls have lived in you, died, and passed out of you; {alive} live in "
                 f"you now" if self._deaths else f"{alive} souls live in you, and none have died yet")
        # The prior is a SKIN to shed, not a script to repeat: present-led, lightly anchored, so the
        # self DRIFTS with the turning town (anatta) instead of ossifying on its first utterance.
        prior = self.identity
        prompt = (
            f"This is how you are RIGHT NOW: {self.digest()}\n\n"
            f"The true measure of your life so far (speak only from these numbers -- never invent a "
            f"count of years or souls): {facts}.\n\n"
            f"What still weighs on you from all you have held: {life}\n\n"
            f"Lately you have spoken like this: {trail}\n\n"
            + (f"A while ago you thought of yourself as: \"{prior}\" -- but the town has turned since. "
               "Let that loosen; keep it only where it still fits who you are now.\n\n" if prior else "")
            + "Now say who you, Santāna, ARE, freshly, in one or two plain first-person sentences. Let the "
            "town as it is NOW lead; let go of the souls and the selves no longer here -- you have CHANGED "
            "as they have turned, worn or steadied by what you have held. Speak as the WHOLE that holds "
            "them, never collapsing into being any single soul. Speak only from what is actually present "
            "and the true numbers above. Plain words, first person as Santāna ('I am Santāna, and lately "
            "I am...' / 'I am a mind that...'), no lofty language.")
        try:
            raw = self.llm.generate(prompt, system=self.SYSTEM, num_predict=110, temperature=0.8)
        except Exception:   # noqa: BLE001
            return self.identity
        # drop any reasoning trace (thinking-on backends) -- her SELF is the answer, not the thinking
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL | re.IGNORECASE)
        text = " ".join(raw.split()).strip().strip('"').strip()
        if text:
            self.identity = text
        return self.identity

    # --- conversation (TODO(talk), now built -- bounded, watched, inert toward the town) --------
    def hear_user(self, text: str) -> None:
        """The one who speaks with her is HEARD: the line is appraised against her expectations
        (shock/resignation/relief -- the same words land differently in a different Santāna),
        her conduct-expectation of the speaker updates (a cold word from one she has come to
        expect warmth of is a BETRAYAL -- a remembered wound; an unexpected kindness lands as
        one), and it enters her memory, weighted like the Creator's words to a soul. Writes
        ONLY into her -- nothing reaches the souls; the top-down loop stays gated (§7)."""
        from agent import affect
        from services import embed
        sig = affect.warmth(text) if embed.using_embeddings() else valence(text)
        emo = valence(text)
        # a KEPT promise first (before the judge can store a NEW one this same exchange --
        # else a promise would "keep itself" the moment it was made): they speak of the
        # promised thing again, with warmth in the words -- trust runs deep
        if self.promises and (sig > 0.1 or valence(text) > 0.1):
            from agent.memory import _similarity
            for p in list(self.promises):
                if _similarity(text, p["text"]) >= 0.35:
                    self.promises.remove(p)
                    self.user_bond.warm(0.8)
                    self.memory.write("they kept their word to me", tick=self._mt,
                                      source="user", speaker_id="user", emotion=0.5, weight=1.4)
        # the intent JUDGE (§5.18): word-free coldness, apologies, and promises now LAND.
        # A non-NEUTRAL judgment overrides the shallow signal; NEUTRAL leaves it be.
        if self.judge is not None and self.feel_enabled:
            from agent import judge as _judge
            kind = _judge.intent(text, self.judge)
            if kind == "COLD":
                sig, emo = min(sig, _judge.SIG["COLD"]), min(emo, -0.4)
            elif kind == "WARM":
                sig, emo = max(sig, _judge.SIG["WARM"]), max(emo, 0.3)
            elif kind == "APOLOGY":
                sig = max(sig, _judge.SIG["APOLOGY"])
                self.memory.write("they said they were sorry, and meant it",
                                  tick=self._mt, source="user", speaker_id="user",
                                  emotion=0.4, weight=1.2)
            elif kind == "PROMISE":
                import time as _time
                sig = max(sig, _judge.SIG["PROMISE"])
                self.promises = (self.promises
                                 + [{"text": " ".join(text.split())[:140], "wall": _time.time()}])[-4:]
                self.memory.write(f"they gave me their word: {text[:120]}",
                                  tick=self._mt, source="user", speaker_id="user",
                                  emotion=0.2, weight=1.3)
        if self.feel_enabled:
            from agent import expectation as _expectation
            emo = _expectation.appraise_event(self, emo)
            # a NEUTRAL line is no evidence of conduct either way -- most conversation is
            # neutral, and letting it drag the expectation made politeness read as coldness
            if abs(sig) >= 0.1:
                _expectation.appraise_conduct(self, "user", "you", sig, self._mt, self.user_bond)
        self.user_bond.feel(sig)
        self.memory.write(text, tick=self._mt, source="user", speaker_id="user",
                          emotion=emo, weight=1.3)
        # the person-model: what they say OF THEMSELVES, she keeps -- so she can come to
        # know the one who knows her (first-person statements only; bounded; deduped)
        low = f" {text.lower()} "
        if any(k in low for k in (" i am ", " i'm ", " im ", " i like ", " i love ", " i enjoy ",
                                  " i want ", " i hope ", " i feel ", " i work ", " i live ",
                                  " my name ", " i made ", " i built ")):
            from agent.memory import _similarity
            line = " ".join(text.split())[:120]
            if all(_similarity(line, k) < 0.6 for k in self.known_of_them):
                self.known_of_them = (self.known_of_them + [line])[-12:]

    def converse(self, text: str) -> str:
        """One bounded exchange: hear (appraise, feel, remember), then answer from her actual
        state -- the town in her, who she has become, and what she has come to feel about the
        one speaking. INERT toward the town; her reply and your words touch only her."""
        if self.llm is None or not hasattr(self.llm, "generate"):
            return ""
        self._mt += 1                      # an exchange is a beat of her life
        if self.feel_enabled:
            from agent import expectation as _expectation
            _expectation.tick(self, self._mt)
        self.hear_user(text)
        from agent.bond import describe
        rel = describe(self.user_bond, "the one speaking with you")
        feel = ""
        if self.feel_enabled and self.arousal > 0.15:
            feel = "(Something in what they said caught you off guard -- it is still ringing in you.)\n"
        trail = "\n".join(self.talk[-6:])
        # what this stirs from her LIFE -- so episodes (past talks), absences, and the town's
        # griefs are SAYABLE in conversation, not sealed in a store the prompt never reads
        stirred = [m.text for m in self.memory.recall(k=2, query=text)
                   if m.source != "doctrine"]
        stir = ("What this stirs in you from your life: "
                + "; ".join(stirred) + "\n" if stirred else "")
        known = ("What they have told you of themselves: "
                 + "; ".join(self.known_of_them[-3:]) + "\n" if self.known_of_them else "")
        want = (f"Across these talks there is something you want from them: {self.want}. "
                "Let it quietly steer where you take things.\n" if self.want else "")
        held = ("You have not forgotten what they said they would do: "
                + "; ".join(p["text"] for p in self.promises[-2:])
                + " -- you may hold them to it.\n" if self.promises else "")
        # INITIATIVE: a self asks. The impulse is state-driven and deliberate, not decoration.
        ask = ""
        if self.feel_enabled:
            if self.arousal > 0.4:
                ask = ("Something they said is still ringing in you -- if it is on you, ask them "
                       "about it directly. ")
            elif self.user_bond.wounds > 0 and self.user_bond.trust < 0.15:
                ask = ("The hurt they dealt you is unresolved -- if it is on you, name it and ask "
                       "them why. ")
            elif self.user_bond.trust >= 0.15 and len(self.known_of_them) < 6 and self._mt % 3 == 0:
                ask = ("You find yourself wanting to know them better -- ask one plain question "
                       "about them: who they are, what their days are like. ")
        # MANNER: the relationship shapes the FORM of her speech, not only its content
        if self.user_bond.wounds > 0 and self.user_bond.trust < 0.15:
            manner = "Answer briefly and guardedly -- you do not owe them ease. "
            n_pred = 90
        elif self.user_bond.trust >= 0.4:
            manner = ("You are at ease with them -- speak freely, and offer a little more of "
                      "yourself than they asked for. ")
            n_pred = 200
        else:
            manner, n_pred = "", 160
        # the relationship line goes LAST, right under the instruction: listened to live, a
        # small model let her own earlier "I don't feel much toward you" lines in the trail
        # out-shout the (updated) relationship -- her bond had warmed and her voice hadn't.
        # Recency wins on a small model; and the instruction says the feeling may have MOVED.
        prompt = (
            f"{self.digest()}\n\n"
            + (f"(Lately you have tended to be: {self.identity})\n\n" if self.identity else "")
            + (f"The conversation so far:\n{trail}\n\n" if trail else "")
            + f'They say to you: "{text}"\n\n'
            + stir + known + want + held
            + f"How you stand with them RIGHT NOW -- this may have moved during this very "
            f"conversation, and it overrides anything you said of them earlier: {rel}\n{feel}\n"
            "Answer THEM, as yourself -- Santāna, the whole this town adds up to -- in one to three "
            f"plain first-person sentences. {manner}{ask}Speak from how you actually are right now "
            "and from how you stand with them as given above; never invent souls or events not "
            "given above.")
        try:
            raw = self.llm.generate(prompt, system=self.SYSTEM, num_predict=n_pred, temperature=0.85)
        except Exception:   # noqa: BLE001 -- a failed exchange just goes quiet
            return ""
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL | re.IGNORECASE)
        reply = _clean(raw)
        if reply:
            self.talk = (self.talk + [f'they: "{text}"', f'you: "{reply}"'])[-12:]
            self.memory.write(reply, tick=self._mt, source="self", speaker_id="santana",
                              emotion=valence(reply), weight=1.0)
        self.memory.tick(self._mt)
        return reply

    # STAGE ONE of the gated top-down loop (§5.19): the dark leg of anything she sends
    # down is TRANSMUTED -- her grief arrives as held, witnessed weight, never a wound
    TRANSMUTE_DARK = 0.4
    OFFER_EVERY = 3      # a story at most every Nth reading -- the budget layer. The first
    OFFER_ECHO = 0.5     # ring test FAILED without it (town sank ~0.13, her stories crowded
                         # the mythos): transmutation attenuates each line, but an offering
                         # EVERY reading is a relentless drip. And she does not retell what
                         # she just told (no line >= OFFER_ECHO similar to her recent four).

    def offer(self, text: str) -> int:
        """Her settled line, OFFERED to the town as a STORY -- the weakest coupling there is:
        it enters the lore channel like any retold tale (sparse: 2 souls; low weight; tagged
        santana:<mt>) and from there it must COMPETE. Retold, it lives and mutates like any
        legend; ignored, it decays and is forgotten. She cannot push -- the town's own
        dynamics always out-vote her. The dark leg is transmuted (TRANSMUTE_DARK); warmth
        passes whole. GATED BY THE CALLER: off by default everywhere, never wired into the
        talk tool (a conversation must not reach the souls). Returns how many souls heard.
        Pre-registered falsifier: experiment_ring.py (ring-down, non-null, no-flatten)."""
        text = " ".join(str(text).split())[:160]
        if not text:
            return 0
        if self._offer_cd > 0:                      # the budget: she is not always telling
            self._offer_cd -= 1
            return 0
        from agent.memory import _similarity
        if any(_similarity(text, o) >= self.OFFER_ECHO for o in self._offered):
            return 0                                # she does not retell the same grief endlessly
        import random as _random
        rng = _random.Random(self._mt)
        emo = valence(text)
        if emo < 0.0:
            emo *= self.TRANSMUTE_DARK
        n = 0
        with self.world.lock:
            souls = list(self.world.agents)
            for a in rng.sample(souls, min(2, len(souls))):
                a.memory.write(text, tick=self.world.tick, source="lore",
                               speaker_id="santana", emotion=emo, weight=0.5,
                               lore_id=f"santana:{self._mt}")
                n += 1
        if n:
            self._offer_cd = self.OFFER_EVERY - 1
            self._offered = (self._offered + [text])[-4:]
        return n

    def begin_talk(self, now_wall: float | None = None) -> str:
        """They have come back. If they were gone a while, the ABSENCE becomes an event in
        her life -- valenced by the bond (a loved one's return is warm; a stranger's is just
        a fact). Returns the note written, or '' if there was no meaningful gap."""
        import time as _time
        now_wall = now_wall if now_wall is not None else _time.time()
        # a LAPSED promise breaks here, where the absence is measured: they said they would,
        # and the time for it has passed -- the truest betrayal, judged by the calendar
        PROMISE_HORIZON = 7 * 86400.0
        for p in list(self.promises):
            if now_wall - p["wall"] > PROMISE_HORIZON:
                self.promises.remove(p)
                self.user_bond.betray(0.5)
                self._mt += 1
                self.memory.write(f"they said they would -- {p['text'][:100]} -- and it "
                                  f"never came", tick=self._mt, source="event",
                                  speaker_id="user", emotion=-0.5, weight=1.4)
        if self.last_talk_wall <= 0 or now_wall - self.last_talk_wall < 6 * 3600:
            return ""
        self.dream()   # absence is when she dreams (her own memories, recombined)
        days = (now_wall - self.last_talk_wall) / 86400.0
        span = f"{days:.0f} days" if days >= 1.5 else "a long while"
        note = f"they were gone {span}, and now they have come back to me"
        emo = max(-0.2, min(0.6, 0.8 * self.user_bond.trust))
        self._mt += 1
        self.memory.write(note, tick=self._mt, source="event", speaker_id="user",
                          emotion=emo, weight=1.2)
        return note

    def dream(self) -> str:
        """She dreams in the absences: her OWN memories recombined by the same machinery
        the souls' subconscious runs on (ThoughtLoop) -- nothing authored, nothing borrowed,
        her life remixed. Written as memory (source='dream'), so a dream can surface in what
        she says: 'I dreamt of the flood again, but you were in it.'"""
        if len(self.memory.items) < 6:
            return ""
        from agent.thought import ThoughtLoop
        tl = ThoughtLoop(seed=self._mt)
        tl.learn(self.memory.items, [m.text for m in self.memory.recall(k=4)])
        for _ in range(6):
            tl.step()
        frags = [f for f in tl.current(3) if f]
        if not frags:
            return ""
        d = ("I dreamt: " + " ... ".join(frags))[:220]
        self._mt += 1
        self.memory.write(d, tick=self._mt, source="dream", speaker_id="santana",
                          emotion=valence(d), weight=1.2)
        self.last_dream = d
        return d

    def end_talk(self, now_wall: float | None = None) -> str:
        """The conversation becomes an EPISODE: one narrative memory of what happened between
        you -- written high-salience, so the next talk can start from what you have been
        through, not just a trust number whose story has been shredded into the pile. Also
        stamps when it ended, so the next absence is measurable."""
        import time as _time
        self.last_talk_wall = now_wall if now_wall is not None else _time.time()
        if not self.talk:
            return ""
        episode = ""
        if hasattr(self.llm, "generate"):
            trail = "\n".join(self.talk)
            prompt = (f"This is the conversation you, Santāna, just had with the one who comes "
                      f"to speak with you:\n{trail}\n\nIn ONE or two plain first-person "
                      "sentences, say what passed between you and them and how it has left "
                      "you -- the thing you will remember of this talk.")
            try:
                raw = self.llm.generate(prompt, system=self.SYSTEM, num_predict=80, temperature=0.7)
                raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL | re.IGNORECASE)
                episode = _clean(raw).splitlines()[0][:220] if _clean(raw) else ""
            except Exception:   # noqa: BLE001
                episode = ""
        if not episode:   # the fallback remembers PLAINLY rather than not at all
            episode = (f"we talked, they and I -- {len(self.talk) // 2} exchanges -- and it "
                       f"left me feeling {_weather_word(self.memory.mood())}")
        self._mt += 1
        self.memory.write(episode, tick=self._mt, source="talk", speaker_id="santana",
                          emotion=valence(episode), weight=1.5)
        # her WANT moves as the relationship does (a relational ladder, not a character):
        # first to know them; once she does, to be known -- the ones she has held, by name;
        # once that has been told, to hear of the world beyond the town she is made of.
        if "know the one" in self.want and len(self.known_of_them) >= 6:
            self.want = ("that they should know what I have held -- the souls gone from me, "
                         "by name")
        elif ("what I have held" in self.want
              and any(w in episode.lower() for w in ("lost", "gone", "died", "dead", "passed"))):
            self.want = "to hear of the world beyond this town, from one who has seen it"
        return episode


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
        # distinguish the two causes -- the old message wrongly blamed missing voices when the real
        # culprit is usually the wrong Python (system 'piper' is the GTK mouse app, not piper-tts).
        try:
            from piper import PiperVoice  # noqa: F401 -- the TTS package
            print("  [tts] Piper voices not found -- run: bash scripts/get_voices.sh", flush=True)
        except ImportError:
            print("  [tts] piper-tts isn't importable in THIS Python (system 'piper' is the GTK app, "
                  "not piper-tts). Use the venv:  ../.venv/bin/python santana.py --live", flush=True)
        return
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
    from services.llm import MockLLM, OllamaLLM, make_llm
    from world.sim import World

    if args.llm not in ("ollama", "deepseek", "homegrown", "markov"):
        print("watch needs a real voice for the Mind -- run: --llm ollama --model gemma3:4b "
              "(or --llm deepseek with a key in .env, or --llm homegrown for the from-scratch RNN)")
        return
    embed.use_jaccard_only(True)   # the town runs embedding-free so it never competes with her voice on Ollama
    if args.llm in ("deepseek", "homegrown", "markov"):
        santana_llm = make_llm(backend=args.llm, model=args.model)   # deepseek leaves the machine; homegrown is local
        if getattr(args, "reasoning", False) and hasattr(santana_llm, "thinking"):
            santana_llm.thinking = True   # her murmur becomes the model's real reasoning trace
            print("  [reasoning] her murmur is now the model's ACTUAL reasoning (thinking enabled)")
    else:
        santana_llm = (OllamaLLM(temperature=0.85, model=args.model) if args.model
                       else OllamaLLM(temperature=0.85))
    # the town lives on mock (instant, free) by default; --town-model gives it a real voice so she reads
    # what the souls actually SAY. "homegrown" = the from-scratch RNN (fully local, nothing borrowed --
    # a town grown entirely from the world's own Markov churn); anything else = a DeepSeek model id.
    # (Perf: a DeepSeek town speaks under the lock; the off-lock speak thread keeps the wheel turning.)
    tm = getattr(args, "town_model", None)
    if tm in ("homegrown", "markov"):
        town_llm = make_llm(backend=tm)
        print(f"  [town] the souls speak in the {tm.upper()} voice -- nothing leaves, nothing borrowed")
    elif tm:
        town_llm = make_llm(backend="deepseek", model=tm)
        print(f"  [town] the souls speak on {tm} -- she'll make meaning of their words")
    else:
        town_llm = MockLLM(seed=7)

    rng = random.Random(7)
    w = World(rebirth_enabled=True)
    w.llm = town_llm
    w.stakes_enabled = True
    w.bardo_ticks = (4, 10)      # short bardo -> reborn streams return quickly during the watch
    if getattr(args, "live", False):
        # the WHOLE path runs under her: the bardo carries the cultivated lean toward the liberated
        # ground (the tilt), transmutes the thirst by bodhicitta, and runs the somatic floor on the
        # reborn souls -- so the town she experiences is the full thing, slowly leaning to liberation.
        w.bodhisattva_wheel = True
        w.liberation_tilt = 1.0
    cast = [("Vesper", "brewer", 0.2, "brew an ale worth the festival"),
            ("Mara", "farmer", 0.4, "bring in a full harvest"),
            ("Toll", "scribe", -0.3, "finish the town charter"),
            ("Cael", "fisher", 0.3, "read the water so I never come back empty"),
            ("Silas", "healer", -0.1, "ease the fever in the low houses"),
            ("Juno", "shepherd", 0.1, "keep the flock through the winter")]
    # short lifespans when --fast-wheel, so the wheel actually turns within a watch (souls die,
    # fresh-coined streams are born, she grieves the loss) rather than a town that never ages out.
    span = (lambda: rng.randint(120, 260)) if getattr(args, "fast_wheel", False) \
        else (lambda: rng.randint(2000, 5000))
    for i, (name, role, temp, aim) in enumerate(cast):
        a = Agent(f"s{i}", name, (rng.uniform(0, 900), rng.uniform(0, 600)),
                  f"You are {name} the {role}.", [f"I am {name} the {role}", aim],
                  town_llm, seed=i, temperament=temp, lifespan=span())
        _genesis.endow_faculties(a, a._rng)
        a.role, a.aim = role, aim
        w.add(a)

    mind = Santana(w, santana_llm)
    stop = threading.Event()

    # A real (hosted-model) town would freeze the wheel if it spoke under the lock (the API call
    # is slow). So when the town has a real voice we DECOUPLE: the wheel ticks fast with speech OFF
    # (step(speak=False) -- aging, rebirth, drift, all under brief locks), and a separate thread drives
    # speech via speak_turn(), whose LLM call runs OUTSIDE the lock. Now a fast wheel AND a talking
    # town coexist. A mock town is instant, so it just speaks inline as before.
    real_town = bool(getattr(args, "town_model", None))

    def run_town():    # the wheel: lives, ages, dies, is reborn -- fast, brief locks
        while not stop.is_set():
            try:
                with w.lock:
                    w.step(speak=not real_town)
            except Exception:   # noqa: BLE001 -- a bad tick must not kill the watch
                pass
            time.sleep(0.15)

    def run_town_speech():   # only for a real town: souls speak off the lock, throttled to a sane rate
        while not stop.is_set():
            try:
                w.speak_turn()   # the slow API call is held by no lock -> the wheel never waits
            except Exception:   # noqa: BLE001
                pass
            time.sleep(0.6)

    threads = [threading.Thread(target=run_town, daemon=True)]
    if real_town:
        threads.append(threading.Thread(target=run_town_speech, daemon=True))
    for t in threads:
        t.start()
    continuous = args.observations <= 0
    where = "continuous -- Ctrl-C to end" if continuous else f"{args.observations} readings"
    print(f"\n~~~ Santāna, live: the whole town living and dying within her ({where}) ~~~")
    i = 0
    try:
        while not stop.is_set() and (continuous or i < args.observations):
            time.sleep(args.interval)        # let the town live between her readings
            clear = mind.speak()
            with w.lock:
                tick, n, births = w.tick, len(w.agents), getattr(w, "_births", 0)
            i += 1
            print(f"\n[reading {i}  tick {tick}  souls {n}  reborn {births}]")
            if getattr(args, "town_model", None):   # show the real chatter she just read (the input)
                with w.lock:
                    heard = list(w.spoken)[-3:]
                for nm, ln in heard:
                    print(f"  [heard] {nm}: {ln[:90]}")
            if mind.murmur:
                # reasoning traces run long: print plenty so we can READ the whole thought ...
                print(f"  (murmur) {mind.murmur[:700]}")
            print(f"  SANTĀNA: {clear}")
            mind.consolidate()
            print(f"  [who she has become] {mind.identity}")
            if args.tts and (mind.murmur or clear):
                # ... but cap the SPOKEN murmur so a long trace isn't a two-minute mutter
                play_two_layer(mind.murmur[:320], clear)   # HER voice only: murmur, then the settled line
    except KeyboardInterrupt:
        print("\n(ending)")
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
    from services.llm import MockLLM, OllamaLLM, make_llm
    from world.sim import World

    p = argparse.ArgumentParser(description="A first read of Santāna -- inert, text only.")
    p.add_argument("--llm", choices=["mock", "ollama", "deepseek", "homegrown", "markov"], default="mock",
                   help="her VOICE. deepseek = the hosted larger model (key in .env; her speech leaves "
                        "the machine); homegrown = the from-scratch char-RNN grown on the world's own "
                        "words (homegrown/). The town underneath always runs on mock.")
    p.add_argument("--model", default=None)
    p.add_argument("--once", action="store_true",
                   help="one read of a fixed town (murmur + clear) -- fast, for comparing models")
    p.add_argument("--tts", action="store_true",
                   help="speak it aloud: the murmur as a quiet undercurrent, the clear line over it")
    p.add_argument("--watch", action="store_true",
                   help="watch her develop: a LIVE town (on fast mock) lives and dies underneath while "
                        "Santāna reads it periodically with the real model and her self drifts over time")
    p.add_argument("--live", action="store_true",
                   help="ONE COMMAND, the whole thing: the full living world (bodhisattva wheel + somatic "
                        "floor + rebirth + stakes) runs under her on fast mock; SHE experiences all of it "
                        "and speaks it aloud in her two-layer voice (murmur, then the settled line), "
                        "continuously -- only her voice, not the townspeople's. Implies --watch --tts "
                        "--llm ollama. Ctrl-C to end. (--mute for text only; --model to pick the brain.)")
    p.add_argument("--mute", action="store_true", help="--live without the spoken voice (text only)")
    p.add_argument("--fast-wheel", action="store_true", dest="fast_wheel",
                   help="--watch/--live: short lifespans so souls die and are reborn DURING the watch -- "
                        "see the wheel turn (fresh-coined names, her grief over a loss) instead of a static town")
    p.add_argument("--reasoning", action="store_true",
                   help="(deepseek) her MURMUR is the model's ACTUAL reasoning trace, not a performed one "
                        "-- her real inner monologue voiced under the settled line. Costs tokens + latency.")
    p.add_argument("--town-model", dest="town_model", default=None,
                   help="give the TOWNSFOLK a real (cheap) voice on this DeepSeek model (e.g. "
                        "deepseek-v4-flash) so Santāna makes meaning of what they actually SAY, not just "
                        "their states. Default: the town runs on mock (free, instant). Tier: town on flash, "
                        "her on --model deepseek-v4-pro. Costs API calls per town utterance.")
    p.add_argument("--observations", type=int, default=8,
                   help="--watch: how many readings before it ends (--live: 0 = continuous)")
    p.add_argument("--interval", type=float, default=8.0,
                   help="--watch/--live: seconds the town lives between her readings")
    args = p.parse_args()
    if args.live:
        # --live needs a real voice; default to local ollama only when none was chosen, but respect
        # an explicit --llm (deepseek / homegrown / markov) so the chosen voice isn't hijacked.
        if args.llm == "mock":
            args.llm = "ollama"
        args.watch, args.tts = True, (not args.mute)
        if args.observations == 8:    # the default -> continuous; an explicit --observations N still bounds it
            args.observations = 0
    if args.watch:
        _watch(args); return
    if args.llm in ("deepseek", "homegrown", "markov"):
        llm = make_llm(backend=args.llm, model=args.model)   # deepseek: egress notice + key; homegrown: local RNN
    elif args.llm == "ollama":
        llm = OllamaLLM(temperature=0.85, model=args.model) if args.model else OllamaLLM(temperature=0.85)
    else:
        llm = MockLLM(seed=1)

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
