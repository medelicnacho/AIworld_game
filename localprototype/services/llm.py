"""LLM backends.

The sim never talks to a model directly -- it builds a SpeechContext and calls
backend.speak(ctx). The backends share the same prompt builders:
  - OllamaLLM   : a local model over HTTP (free, offline) -- stdlib only
  - MockLLM     : no model at all, composes from drift so the world still runs
  - DeepSeekLLM : hosted API (OpenAI-compatible) -- the opt-in larger-model path
Swapping backends never touches agent/sim code. The default is local-only:
'auto' chooses Ollama (or Mock), never the API, so nothing leaves the machine
unless you ask for DeepSeek by name with a key in .env. That opt-in is the one
path on which prompts and generated speech leave the box (see make_llm).
"""

from __future__ import annotations

import json
import os
import random
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

OLLAMA_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "gemma3:4b"   # small + fast local model for this variant
OLLAMA_NUM_THREAD = 8        # P-core sweet spot here; 12 oversubscribes E-cores
OLLAMA_KEEP_ALIVE = "30m"    # keep the model resident so turns don't cold-reload

# Hosted DeepSeek backend (OpenAI-compatible). OFF unless explicitly selected: the
# default ('auto') is local-only -- nothing leaves the machine. DeepSeek is the
# opt-in path to a larger model than this box can run (see make_llm + README).
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash"   # cheap, fast; thinking disabled below


def load_dotenv(path: str | None = None) -> None:
    """Minimal .env loader: KEY=VALUE lines into os.environ (no overwrite).

    Keeps the API key out of source and out of shell history. .env is gitignored.
    """
    env_path = Path(path) if path else Path(__file__).resolve().parent.parent / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))




# --- the prompt layer lives in services/prompts.py now (2026-07-03 port-prep split) ----------
# llm.py held two concerns: WHAT to say (SpeechContext + builders + faculty clauses) and HOW
# to reach a model (the backends below). The WHAT moved to services/prompts.py -- the port
# seam a game engine reimplements -- and is re-exported here in full so every existing
# `from services.llm import SpeechContext, build_system, ...` keeps working unchanged.
from services.prompts import (  # noqa: F401 -- re-exports are the point
    GROUNDED_VOICE, PRAJNA_FLOOR, PRAJNA_SYSTEM, SELFLIB_FLOOR, SELFLIB_SYSTEM,
    TRANSMUTE_FLOOR, TRANSMUTE_SYSTEM, SpeechContext, _aim_clause, _clean,
    _compassion_clause, _disposition, _grounded_clause, _joy_clause, _mood_word,
    _prajna_clause, _self_clause, _selflib_clause, _stance_clause, _transmute_clause,
    _trim_to_sentence, _work_clause, build_system, build_user, sanitize,
)



class DeepSeekLLM:
    """DeepSeek API backend (OpenAI-compatible). The opt-in larger-model path.

    Stdlib HTTP -- no SDK. China-hosted: prompts and generated speech LEAVE this
    machine (see the notice in make_llm). Use it for the runs that need more than a
    4B can give (the emergence verdict); local stays the committed default so saved
    experiments stay reproducible against a model that can't drift or be deprecated.
    """

    def __init__(self, model: str = DEFAULT_DEEPSEEK_MODEL, url: str = DEEPSEEK_URL,
                 temperature: float = 0.95, max_tokens: int = 110,
                 timeout: float = 90.0, thinking: bool = False) -> None:
        self.model = model
        self.url = url
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        # thinking=True -> v4-flash's reasoning trace is returned (in message.reasoning_content)
        # and generate() wraps it as <think>...</think> so a caller's murmur-splitter can voice the
        # ACTUAL reasoning as the inner monologue. Off by default (it costs tokens + latency).
        self.thinking = thinking
        self._key = os.environ.get("DEEPSEEK_API_KEY", "")

    @staticmethod
    def available() -> bool:
        return bool(os.environ.get("DEEPSEEK_API_KEY"))

    def _post_full(self, messages: list[dict], max_tokens: int,
                   temperature: float) -> tuple[str, str]:
        """Returns (content, reasoning). reasoning is '' unless thinking is on."""
        if self.thinking:
            max_tokens = max(max_tokens, 1024)   # leave room for the trace AND the answer
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
            # v4-flash defaults to thinking mode, which burns the budget on reasoning and
            # returns empty content -- disabled for fast one-liners unless asked for explicitly.
            "thinking": {"type": "enabled" if self.thinking else "disabled"},
        }
        req = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self._key}"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
        msg = data["choices"][0]["message"]
        return (msg.get("content") or "", msg.get("reasoning_content") or "")

    def _post(self, messages: list[dict], max_tokens: int, temperature: float) -> str:
        return self._post_full(messages, max_tokens, temperature)[0]

    def speak(self, ctx: SpeechContext) -> str:
        text = self._post(
            [{"role": "system", "content": build_system(ctx)},
             {"role": "user", "content": build_user(ctx)}],
            self.max_tokens, self.temperature)
        return _trim_to_sentence(_clean(text)) or "..."

    def generate(self, prompt: str, system: str = "", num_predict: int = 260,
                 temperature: float = 1.0) -> str:
        """Free-form completion (genesis authoring, reflect, the emergence judge):
        returns RAW text so the caller parses its own structured reply. With thinking on,
        the reasoning trace is prepended as <think>...</think> so a murmur-splitter can voice it."""
        messages = ([{"role": "system", "content": system}] if system else []) \
            + [{"role": "user", "content": prompt}]
        content, reasoning = self._post_full(messages, num_predict, temperature)
        if reasoning.strip():
            return f"<think>{reasoning.strip()}</think>{content}"
        return content


class OllamaLLM:
    def __init__(self, model: str = DEFAULT_OLLAMA_MODEL, url: str = OLLAMA_URL,
                 temperature: float = 0.95, num_predict: int = 110,
                 num_thread: int = OLLAMA_NUM_THREAD, keep_alive: str = OLLAMA_KEEP_ALIVE,
                 timeout: float = 120.0,   # cold load fits; a hung call fails sooner
                 think: bool | None = None) -> None:
        self.model = model
        self.url = url
        self.temperature = temperature
        self.num_predict = num_predict
        self.num_thread = num_thread
        self.keep_alive = keep_alive
        self.timeout = timeout
        # reasoning control for thinking models (qwen3 etc.): False = answer directly (a
        # tiny-token judge call would otherwise burn its whole budget inside <think>).
        # None = don't send the field at all (older servers/models never see it).
        self.think = think

    def available(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self.url}/api/tags", timeout=3) as r:
                return r.status == 200
        except (urllib.error.URLError, OSError):
            return False

    def speak(self, ctx: SpeechContext) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": build_system(ctx)},
                {"role": "user", "content": build_user(ctx)},
            ],
            "stream": False,
            "keep_alive": self.keep_alive,   # avoid cold reloads between turns
            "options": {"temperature": self.temperature,
                        "num_predict": self.num_predict,
                        "num_thread": self.num_thread},  # 8 > 12 here (skips E-cores)
        }
        if self.think is not None:
            payload["think"] = self.think
        req = urllib.request.Request(
            f"{self.url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
        return _trim_to_sentence(_clean(data.get("message", {}).get("content", ""))) or "..."

    def generate(self, prompt: str, system: str = "", num_predict: int = 260,
                 temperature: float = 1.0) -> str:
        """A free-form completion (NOT agent speech): used to author a character at
        genesis. High temperature for variety; returns the RAW text so the caller
        can parse the structured reply itself."""
        messages = ([{"role": "system", "content": system}] if system else []) \
            + [{"role": "user", "content": prompt}]
        payload = {
            "model": self.model, "messages": messages, "stream": False,
            "keep_alive": self.keep_alive,
            "options": {"temperature": temperature, "num_predict": num_predict,
                        "num_thread": self.num_thread},
        }
        if self.think is not None:
            payload["think"] = self.think
        req = urllib.request.Request(
            f"{self.url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
        return data.get("message", {}).get("content", "")


class MockLLM:
    """No-model fallback: weave drift + recall + a nod to whoever spoke."""

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    def speak(self, ctx: SpeechContext) -> str:
        bits: list[str] = []
        if ctx.reply_to_text:
            # echo only a short snippet so replies don't snowball
            snippet = " ".join(ctx.reply_to_text.lower().split()[:5])
            bits.append(f"{self._rng.choice(['you say', 'so', 'maybe', 'still'])}, {snippet}")
        if ctx.drift:
            bits.append(self._rng.choice(ctx.drift))
        elif ctx.memories:
            bits.append(" ".join(self._rng.choice(ctx.memories).split()[:6]))
        return _clean(" ... ".join(bits) or "...")

    def generate(self, prompt: str = "", system: str = "", **_kw) -> str:
        """A deterministic fake character so genesis runs (and tests) without a
        model -- the same structured format the real backend emits. Also serves the
        reflect() module: when the system prompt is the reflection framing, return a
        canned EQUANIMOUS line (net-positive valence) so the clean-room A/B plumbing
        and unit tests run without a model -- the real equanimity signal needs an
        actual LLM, this only proves the wiring moves mood the intended way."""
        if "observing its own" in system or "acceptance" in system:
            return self._rng.choice([
                "There is sorrow here, yet I hold it gently, and a quiet calm remains.",
                "I feel the heaviness, and I let it be soft -- it is here, and so am I.",
                "The grief moves through me like weather; I meet it with a gentle peace.",
            ])
        if "who you have become" in system:   # the self-model consolidation
            return self._rng.choice([
                "I am someone learning to carry loss without being ruled by it.",
                "I am becoming quieter and steadier, shaped by the work I tend each day.",
                "I am a person who holds to small warmths against the dark.",
            ])
        name = self._rng.choice(["Vesper", "Toll", "Cael", "Mara", "Juno", "Bram",
                                 "Sable", "Orin", "Nyx", "Pell", "Liri", "Senna"])
        temp = round(self._rng.uniform(-1.0, 1.0), 2)
        themes = self._rng.sample(
            ["I mind the morning bread", "the wool's dear this season", "my neighbour's geese again",
             "I'm saving for a better roof", "the festival's coming up", "my apprentice is clumsy",
             "a good haggle at market", "the cart wheel wants mending",
             "my mother's old recipe", "the long walk to the well"], 6)
        return f"NAME: {name}\nNATURE: {temp}\nVOICE:\n" + "\n".join(themes)


_HOMEGROWN_DIR = Path(__file__).resolve().parent.parent / "homegrown"
HOMEGROWN_PATH = str(_HOMEGROWN_DIR / "model.npz")   # the old numpy char-RNN
HOMEGROWN_GPT = str(_HOMEGROWN_DIR / "gpt.pt")       # the trained PyTorch GPT (preferred when present)
LIVING_CORPUS = str(_HOMEGROWN_DIR / "living_corpus.txt")   # the Demiurge's novelty feed (see demiurge.py)


class HomegrownLLM:
    """A from-scratch model grown on the world's OWN recorded words -- it does not follow
    instructions, it simply speaks in the voice it learned. Prefers the trained GPT (gpt.pt,
    homegrown/gpt.py) when it exists, else falls back to the numpy char-RNN (model.npz). The
    most literal 'self from the substrate' in the project: every letter it speaks, it learned here."""

    def __init__(self, path: str = HOMEGROWN_PATH, temperature: float = 0.85,
                 seed: str = "") -> None:   # "" = start cold, so it generates a natural line-start it learned
        self.path = path
        self.temperature = temperature
        self.seed = seed
        self._model = None

    def available(self) -> bool:
        return Path(HOMEGROWN_GPT).is_file() or Path(self.path).is_file()

    def _net(self):
        if self._model is None:
            if Path(HOMEGROWN_GPT).is_file():        # the trained GPT wins
                from homegrown.gpt import GPTVoice
                self._model = GPTVoice(HOMEGROWN_GPT)
            else:
                from homegrown.charrnn import CharRNN
                self._model = CharRNN.load(self.path)
        return self._model

    def _line(self, seed: str, n: int, temperature: float) -> str:
        # warm on a SHORT in-voice seed (the char-RNN can't read a real prompt), then speak.
        cont = self._net().generate(seed, n=n, temp=temperature)
        return _trim_to_sentence(_clean(seed + cont)) or "..."

    def speak(self, ctx: SpeechContext) -> str:
        return self._line(self.seed, 200, self.temperature)

    def generate(self, prompt: str = "", system: str = "", num_predict: int = 200,
                 temperature: float = 1.0) -> str:
        return self._line(self.seed, num_predict, temperature)


class MarkovLLM:
    """The world's own words, recombined -- an order-N word Markov. Unlike a trained model, it is
    NOT frozen: it carries the project's authored lines (each trade's concerns, the genesis themes,
    the religions' scripture) as a clean ANCHOR, and learn() folds in the world's LIVING lines, so
    the voice DRIFTS with experience -- always becoming, never done -- while never garbling a word
    (it can only ever say words it has been given). The 'grown from the Markov chain' voice, alive."""

    _START = "\x02"

    def __init__(self, order: int = 2, seed: int | None = None, temperature: float = 1.0,
                 culture: bool = False) -> None:
        from agent.genesis import ROLES, _THEMES
        from agent.religion import RELIGIONS
        base: list[str] = list(_THEMES)
        for _role, tasks in ROLES:
            base += tasks
        for rel in RELIGIONS.values():
            base.append(rel.creed)
            base += list(rel.scripture)
        self._authored = base          # the stable, clean anchor (keeps the drift from degenerating)
        self.order = order
        self._rng = random.Random(seed)
        # opt-in memetic culture (FINDINGS §5.13): selection + self-limiting fitness over motifs, so the
        # voice develops shifting cultural ERAS instead of freezing or averaging. Off -> old behaviour.
        if culture:
            from agent.culture import CulturePool
            self.culture = CulturePool(seed=seed)
        else:
            self.culture = None
        self._build([])                # initial chain = authored only

    @staticmethod
    def _living_corpus() -> list[str]:
        """The Demiurge's novelty feed (8B-dreamed lines), re-read each rebuild so the voice picks up
        new souls as they are born. Bounded -> a minority of the chain, never drowning the anchor."""
        try:
            if os.path.isfile(LIVING_CORPUS):
                return [ln.strip() for ln in open(LIVING_CORPUS, encoding="utf-8").read().splitlines()
                        if ln.strip()][-400:]
        except Exception:   # noqa: BLE001
            pass
        return []

    def _build(self, living: list[str]) -> None:
        """Rebuild the chain from the authored anchor + the Demiurge's living corpus + the world's
        LIVING lines. All filtered (sane length) so the voice stays clean as it drifts."""
        feed = living + self._living_corpus()
        sents = self._authored + [s for s in feed if s and 2 <= len(s.split()) <= 24]
        trans: dict[tuple, list] = {}
        for s in sents:
            toks = [self._START] * self.order + s.split() + [None]   # None = end of line
            for i in range(len(toks) - self.order):
                trans.setdefault(tuple(toks[i:i + self.order]), []).append(toks[i + self.order])
        self._trans = trans

    def learn(self, lines) -> None:
        """Feed the voice the world's accumulating life -- it rebuilds itself, so it is always
        changing, never frozen. Bounded (keeps the most recent lines) so it stays clean and cheap.
        With a culture pool, motifs the town echoes are amplified and the reigning one fatigues, so
        the voice moves through cultural eras (FINDINGS §5.13)."""
        recent = [str(s).strip() for s in lines][-300:]
        if self.culture is not None:
            self.culture.observe(recent)
            self._build(self.culture.voiced(recent))
        else:
            self._build(recent)

    def available(self) -> bool:
        return bool(self._trans)

    def _walk(self, max_words: int = 16) -> str:
        ctx = (self._START,) * self.order
        out: list[str] = []
        for _ in range(max_words):
            nxts = self._trans.get(ctx)
            if not nxts:
                break
            w = self._rng.choice(nxts)
            if w is None:
                break
            out.append(w)
            ctx = tuple(list(ctx)[1:] + [w])
        return " ".join(out)

    def speak(self, ctx: SpeechContext) -> str:
        return _clean(self._walk()) or "..."

    def generate(self, prompt: str = "", system: str = "", num_predict: int = 200,
                 temperature: float = 1.0) -> str:
        n = self._rng.randint(1, 2)
        return _clean(" ".join(self._walk() for _ in range(n))) or "..."


class TownVoices:
    """THE MOUTH -- half of the mouth/brain split (the user's design, and the right one).

    Every soul SPEAKS through its OWN word-Markov chain: the authored anchor plus the
    lines IT has actually lived -- so speech is readable from the first breath (a chain
    can only say real words it was given), individual (Vesper's chain smells of brewing,
    Toll's of the charter), and instantly learning (refresh() refolds a soul's lived
    lines whenever its brain sleeps). Meanwhile the BRAINS (SoulVoiceLLM, the tiny
    per-soul GPTs) never speak ambiently: they learn silently at night from the same --
    now readable -- lines, keep dreaming in their own growing voices, and keep being
    schooled at rebirth. The town sounds like a village; the infants study under it.
    Culture still flows: souls hear each other's chain-lines, remember them, and fold
    them into their own chains at the next refresh -- chained off each other, literally."""

    def __init__(self, seed: int | None = None, culture: bool = False) -> None:
        self._seed = seed or 7
        self.shared = MarkovLLM(seed=seed, culture=culture)   # town-wide fallback voice
        self.chains: dict[str, MarkovLLM] = {}

    def refresh(self, soul_id: str, lines: list[str]) -> None:
        """Refold a soul's OWN lived lines into its personal chain (called from the
        sleep thread with a snapshot taken under the world lock -- the mouth freshens
        as the brain sleeps). Short fragments are left out; a chain fed scraps says
        scraps."""
        chain = self.chains.get(soul_id)
        if chain is None:
            chain = self.chains[soul_id] = MarkovLLM(
                seed=self._seed + (hash(soul_id) % 9973))
        chain.learn([t for t in lines if len(t) >= 12 and t.count(" ") >= 2])

    def speak(self, ctx: SpeechContext) -> str:
        sid = ctx.agent_id or ""
        voice = self.chains.get(sid, self.shared)   # personal once refreshed, else shared
        return voice.speak(ctx)

    def generate(self, prompt: str = "", system: str = "", num_predict: int = 200,
                 temperature: float = 0.9) -> str:
        return self.shared.generate(prompt, system=system, num_predict=num_predict,
                                    temperature=temperature)

    def learn(self, lines) -> None:
        self.shared.learn(lines)

    def prune(self, live_ids: set[str]) -> None:
        for sid in [s for s in self.chains if s not in live_ids]:
            del self.chains[sid]


class SoulVoiceLLM:
    """PER-SOUL minds: every NPC speaks from its OWN tiny homegrown GPT.

    One router object serves the whole town (so load_world's re-injection Just Works),
    but each speak() is routed by ctx.agent_id to that soul's PRIVATE brain
    (homegrown/soulmind.py): born a fresh random init at rebirth -- a newborn BABBLES,
    it has not yet learned to speak -- then grown by SLEEP (the runner's sleep thread
    calls sleep_one) on nothing but its own living memory, which itself decays and
    mutates. Learning and forgetting are therefore continuous and inherited: what falls
    out of memory falls out of the next sleep, and the weights drift on. The wheel hands
    on karma, never weights.

    Minds persist per-soul under data/npc_minds/ (atomic saves), are pruned when their
    soul leaves the world, and are NEVER part of a world snapshot (Agent.__getstate__
    already nulls llm; world/serialize.py would loudly refuse a tensor anyway)."""

    def __init__(self, minds_dir: str | None = None, seed: int | None = None) -> None:
        from homegrown.soulmind import SoulMind   # raises ImportError if torch is absent
        self._SoulMind = SoulMind
        root = Path(__file__).resolve().parent.parent
        self.dir = minds_dir or str(root / "data" / "npc_minds")
        self.minds: dict[str, object] = {}
        self._seed = seed
        self._schooled: set[str] = set()   # souls whose newborn mind got its schooling

    def _path(self, soul_id: str) -> str:
        safe = "".join(c if (c.isalnum() or c in "-_") else "_" for c in soul_id)
        return os.path.join(self.dir, f"{safe}.pt")

    def mind_for(self, soul_id: str):
        """This soul's own brain -- loaded if it has lived before, else born blank."""
        if soul_id not in self.minds:
            path = self._path(soul_id)
            if os.path.isfile(path):
                try:
                    self.minds[soul_id] = self._SoulMind.load(path)
                except Exception:   # noqa: BLE001 -- an unreadable brain is a fresh birth, said aloud
                    print(f"  ⚠ {soul_id}'s saved mind could not be woken -- born fresh "
                          f"(the old file stays at {path})", flush=True)
                    self.minds[soul_id] = self._SoulMind(soul_id, seed=self._seed)
            else:
                self.minds[soul_id] = self._SoulMind(soul_id, seed=self._seed)
        return self.minds[soul_id]

    def speak(self, ctx: SpeechContext) -> str:
        sid = ctx.agent_id or ctx.name or "town"
        mind = self.mind_for(sid)
        # seed the continuation with the soul's own subconscious fragment -- the same
        # drift-feeds-speech contract every other backend honours
        prompt = ((ctx.drift[-1] if ctx.drift else ctx.name) + "\n")
        return _clean(mind.line(prompt=prompt)) or "..."

    def generate(self, prompt: str = "", system: str = "", num_predict: int = 200,
                 temperature: float = 0.9) -> str:
        return _clean(self.mind_for("town").line(prompt=prompt, n=min(num_predict, 200),
                                                 temp=temperature)) or "..."

    DREAM_EVERY = 3   # every third sleep, the soul dreams -- often enough to be a life,
                      # rare enough that dreams stay a minority of what a soul holds

    # --- the sleep cycle (called from the runner's sleep thread) --------------------------
    def sleep_text(self, soul_id: str, corpus: str) -> tuple[float, float] | None:
        """One soul's sleep on a PRE-SNAPSHOTTED corpus (take it under the world lock;
        the slow training burst then runs with no lock held -- the speak_turn contract).
        Returns (first_loss, last_loss) or None (too little lived yet: infants babble)."""
        mind = self.mind_for(soul_id)
        report = mind.sleep(corpus)
        if report is not None:
            mind.save(self._path(soul_id))
        return report

    def weighted_corpus(self, agent) -> str:
        """The soul's sleep corpus with BIASED TRANSMISSION (the ratchet's first half):
        a heard line from a soul you TRUST is repeated in the corpus -- you learn hardest
        from those you love -- while everything else appears once, exactly as lived.
        The prestige signal is the town's own (bond trust), never an outside yardstick:
        the culture stays fully self-grown. Take it under the world lock."""
        lines = [agent.persona]
        bonds = getattr(agent, "bonds", {})
        for m in agent.memory.items:
            lines.append(m.text)
            spk = getattr(m, "speaker_id", "")
            if getattr(m, "source", "") in ("ai", "heard") and spk:
                b = bonds.get(spk)
                if b is not None and b.trust > 0.3:
                    lines.append(m.text)               # the loved are heard twice
                    if b.trust > 0.6:
                        lines.append(m.text)           # the deeply trusted, thrice
        return "\n".join(lines)

    def sleep_one(self, agent) -> tuple[float, float] | None:
        """Convenience (single-threaded callers/tests): snapshot + sleep in one call.
        The corpus is the soul's persona + the memories it still holds -- decayed,
        mutated, exactly as lived -- with trusted voices weighted (weighted_corpus)."""
        return self.sleep_text(agent.id, self.weighted_corpus(agent))

    # --- the ratchet's second half: SCHOOLING (cross-generational transmission) -----------
    # Without this, every rebirth resets a mind to zero and culture can never accumulate
    # in weights: the wheel hands on karma, never language. Schooling is the smallest
    # honest ratchet: a newborn mind's FIRST training is on the elders' own spoken lines
    # -- born babbling, raised by the village -- so each generation starts where the last
    # one ended. The school corpus is town-grown text only; nothing human enters here.
    # (Iterated-learning literature -- Kirby -- predicts structure should RISE through
    # this bottleneck across generations; experiment_ratchet.py holds the claims.)

    def needs_school(self, agent) -> bool:
        """A soul needs schooling exactly once: while its mind has never slept."""
        if agent.id in self._schooled:
            return False
        mind = self.minds.get(agent.id)
        if mind is None and os.path.isfile(self._path(agent.id)):
            return False                       # a saved mind has lived; not a newborn
        return mind is None or getattr(mind, "sleeps", 0) == 0

    def school_corpus(self, agents, cap: int = 400) -> str:
        """What the village teaches: the SPOKEN lines (source='self') of the oldest
        third of living souls -- the elders' tongue, exactly as they said it."""
        elders = sorted(agents, key=lambda a: a.age / max(1, a.lifespan))[-max(1, len(agents) // 3):]
        lines = [m.text for a in elders for m in a.memory.items if m.source == "self"]
        return "\n".join(lines[-cap:])

    def school(self, agent, corpus: str) -> tuple[float, float] | None:
        """One schooling burst on a PRE-SNAPSHOTTED elders' corpus (same threading
        contract as sleep_text). Marks the soul schooled either way -- a town too young
        to have a tongue simply lets this newborn found it."""
        self._schooled.add(agent.id)
        if not corpus.strip():
            return None
        return self.sleep_text(agent.id, corpus)

    # --- dreams (NPC dreams ride the sleep cycle, like hers ride her absences) ------------
    def dream_line(self, soul_id: str, residue: str) -> str:
        """Every DREAM_EVERY-th sleep, the soul's OWN brain dreams one line -- seeded by
        the day's residue (its most salient memory), run hotter than waking speech, so it
        comes out loosened the way dreams do. Returns "" on non-dream sleeps, for infants
        (no sleeps yet -- a mind that cannot speak cannot dream), or a too-thin dream.

        The caller writes it back as memory with source='dream': the provenance layer
        (§5.19) then does the rest -- the soul says 'I dreamt it, I think' at recall, and
        a dream worn by drift and retelling can LEAK into believed memory, auditable,
        exactly as the C14b falsifier measured for stories."""
        mind = self.minds.get(soul_id)
        if mind is None or mind.sleeps == 0 or mind.sleeps % self.DREAM_EVERY:
            return ""
        text = _clean(mind.line(prompt=(residue or "")[-40:] + "\n", n=90, temp=1.05))
        return text if len(text) >= 8 else ""

    def dream_one(self, agent, tick: int) -> str | None:
        """Convenience (single-threaded callers/tests): dream + write-back in one call.
        Threaded callers (the runner) use dream_line and write under the world lock."""
        residue = (max(agent.memory.items, key=lambda m: m.salience).text
                   if agent.memory.items else agent.persona)
        dream = self.dream_line(agent.id, residue)
        if not dream:
            return None
        agent.memory.write(dream, tick=tick, source="dream",
                           speaker_id=agent.id, weight=0.9)
        return dream

    def prune(self, live_ids: set[str]) -> None:
        """Drop minds whose souls have left the world (RAM only -- the files remain as
        relics until their name is reborn... which, with fresh-coined names, it isn't)."""
        for sid in [s for s in self.minds if s not in live_ids and s != "town"]:
            del self.minds[sid]
        self._schooled &= live_ids             # the ledger follows the living

    def save_all(self) -> None:
        for sid, mind in self.minds.items():
            mind.save(self._path(sid))


def make_llm(backend: str = "auto", model: str | None = None,
             seed: int | None = None, culture: bool = False):
    """Pick a backend. Local is the default; DeepSeek is explicit opt-in only.

    'auto'    : Ollama if a local model is reachable, else Mock. Never the API --
                so a stray key in the environment can't silently ship the world out.
    'ollama'  : local model (errors if not reachable).
    'deepseek': hosted DeepSeek API. Must be asked for by name + a key in .env;
                prompts and speech leave the machine (a notice prints once).
    'homegrown': the from-scratch char-RNN grown on the world's own words (homegrown/).
    'mock'    : no model.
    """
    if backend == "homegrown":
        h = HomegrownLLM()
        if not h.available():
            raise RuntimeError("homegrown model not found -- train it first: "
                               "python homegrown/harvest.py <transcripts> && python homegrown/train.py")
        kind = "GPT" if Path(HOMEGROWN_GPT).is_file() else "char-RNN"
        print(f"[llm] homegrown {kind} -- a voice grown from nothing on the world's own words")
        return h

    if backend == "markov":
        print("[llm] markov -- the world's own authored words recombined (clean, fully self-grown, "
              "nothing trained or borrowed)" + (" + culture (shifting eras, §5.13)" if culture else ""))
        return MarkovLLM(seed=seed, culture=culture)

    if backend == "soul":
        try:
            router = SoulVoiceLLM(seed=seed)
        except ImportError as exc:
            raise RuntimeError("the per-soul minds need PyTorch (homegrown/soulmind.py) -- "
                               "pip install torch, or use --town-model markov") from exc
        print("[llm] soul minds -- every NPC carries its OWN tiny from-scratch GPT: born "
              "babbling at rebirth, grown by sleep on its own decaying memory (learning and "
              "forgetting, continuously; homegrown/soulmind.py)")
        return router

    if backend == "deepseek":
        load_dotenv()
        if not DeepSeekLLM.available():
            raise RuntimeError(
                "DeepSeek requested but DEEPSEEK_API_KEY is not set "
                "(put it in .env -- see .env.example).")
        m = model or DEFAULT_DEEPSEEK_MODEL
        print(f"[llm] DeepSeek API: {m} -- prompts + speech leave this machine "
              "(api.deepseek.com, China; ~30d retention; turn off 'Improve the model "
              "for everyone' to keep them out of training). Local is the default.")
        return DeepSeekLLM(model=m)

    if backend in ("ollama", "auto"):
        m = model or DEFAULT_OLLAMA_MODEL
        ollama = OllamaLLM(model=m)
        if ollama.available():
            print(f"[llm] using Ollama model: {m}")
            return ollama
        if backend == "ollama":
            raise RuntimeError("Ollama requested but not reachable at " + OLLAMA_URL)
        print("[llm] Ollama not reachable -> falling back to MockLLM")

    print("[llm] using MockLLM (no model)")
    return MockLLM(seed=seed)
