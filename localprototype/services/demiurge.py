"""The Demiurge -- an 8B author that injects NOVELTY into the closed markov ecology.

A pure markov corpus can only recombine what it already holds, so over time it converges and goes
stale (the inbreeding / mutation problem -- you can watch it loop). The Demiurge is the missing
mutation operator: a LOCAL ollama model (default the abliterated llama3.1-8b -- more chaos, better
for emergence) that, whenever a soul is reborn, dreams up a GENUINELY NEW villager -- name, trade, a
ruling fear, and a few first-person lines -- writes that identity onto the reborn stream, and feeds
the lines into a LIVING corpus that the markov voices and Santāna's nightly consolidation both read.
So: an 8B seeds novelty -> the souls live and morph it (markov) -> Santāna consolidates it. LLMs
around a markov corpus the LLMs keep changing.

Honest, per CONTINUAL.md / FINDINGS §7:
  - it runs LOCAL (ollama) so nothing leaves the machine -- but it is a BORROWED brain. A town
    seeded by it is partly a distillation of llama3; it is no longer "nothing borrowed". Said plainly.
  - the original hand-authored anchor (corpus_train.txt / MarkovLLM._authored) is PERMANENT and the
    8B lines are a bounded minority, so the texture can't collapse into 8B-average mush.
  - a diversity log (data/demiurge.log: lines / unique-ratio / vocab) makes collapse VISIBLE.
"""
from __future__ import annotations

import os
import random
import re
import time

from services.llm import LIVING_CORPUS, OllamaLLM, _clean

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIVLOG = os.path.join(ROOT, "data", "demiurge.log")

DEFAULT_MODEL = "mannix/llama3.1-8b-abliterated:q5_K_M"

_SYS = ("You invent souls for a small, hard, half-mythic medieval town. Terse, grounded, a little "
        "strange. Each is a GROWN villager with a settled trade -- never a child or an apprentice. "
        "No preamble, no commentary, no markdown. Output ONLY the requested block.")

# We pick the trade and the name's initial OURSELVES and hand them to the model -- otherwise the
# abliterated 8B grooves into one mode (it kept dreaming 'G'-named blacksmith's apprentices). Forcing
# a varied trade per call spreads the dreamed souls across the whole town; we also overwrite role with
# our choice after parsing, so the spread is GUARANTEED regardless of what the model echoes.
_TRADES = ["fisher", "midwife", "gravedigger", "brewer", "beekeeper", "tanner", "miller", "herbalist",
           "stonemason", "shepherd", "charcoal-burner", "saltmaker", "candlemaker", "ferryman",
           "ratcatcher", "glassblower", "cooper", "thatcher", "drover", "wet-nurse", "bonesetter",
           "reeve", "fletcher", "dyer", "swineherd", "net-mender", "peat-cutter", "hedge-witch",
           "tollkeep", "plague-doctor", "smith", "weaver", "potter", "carter", "huntsman", "sexton"]
_INITIALS = "ABCDEFHIJKLMNOPRSTUVW"   # deliberately no 'G' (the rut), no awkward Q/X/Y/Z

_USER_TMPL = (
    "Invent ONE new GROWN villager (not a child, not an apprentice) just born into the town. Use "
    "EXACTLY this format, nothing else:\n"
    "NAME: <one invented given name that BEGINS WITH the letter '{initial}'>\n"
    "TRADE: {trade}\n"
    "FEAR: <one ruling fear or longing of a {trade}, a short phrase>\n"
    "LINES:\n"
    "- <a short thing they mutter to themselves, first person, under 12 words>\n"
    "- <a daily worry specific to being a {trade}>\n"
    "- <something strange they half-believe>\n"
    "- <a private line of their faith or their dread>\n")


def _name_of(s: str) -> str | None:
    toks = re.sub(r"[^A-Za-z'\-]", " ", s).split()
    if not toks:
        return None
    n = toks[0].strip("'-").capitalize()
    return n[:14] if len(n) >= 2 else None


class Demiurge:
    """Dreams new souls via a local 8B. invent() is the SLOW call (run it off any sim lock);
    apply() is fast (run it under the lock); seed_corpus() is plain file IO."""

    def __init__(self, model: str = DEFAULT_MODEL, temperature: float = 1.15) -> None:
        self.model = model
        self._rng = random.Random()
        # high temperature -- the caller asked for chaos; novelty is the whole point
        self._llm = OllamaLLM(model=model, temperature=temperature, num_predict=240)

    def available(self) -> bool:
        if not self._llm.available():
            return False
        try:                                   # is THIS model actually pulled?
            import json
            import urllib.request
            with urllib.request.urlopen(f"{self._llm.url}/api/tags", timeout=3) as r:
                tags = json.loads(r.read().decode("utf-8"))
            names = {m.get("name", "") for m in tags.get("models", [])}
            return self.model in names or any(self.model.split(":")[0] == n.split(":")[0] for n in names)
        except Exception:   # noqa: BLE001
            return True      # reachable but couldn't list -- let the first call decide

    def invent(self) -> dict | None:
        """One 8B call -> a parsed soul, or None if it returned garbage. SLOW; never hold a lock.
        We pick the trade + name-initial and hand them in, then OVERWRITE role with our trade -- so the
        souls spread across the town even when the model wants to groove into one mode."""
        trade = self._rng.choice(_TRADES)
        initial = self._rng.choice(_INITIALS)
        try:
            raw = self._llm.generate(_USER_TMPL.format(trade=trade, initial=initial),
                                     system=_SYS, num_predict=240, temperature=1.2)
        except Exception:   # noqa: BLE001 -- a flaky model must never kill the world
            return None
        soul = self._parse(raw)
        if soul:
            soul["role"] = trade   # OUR randomized trade -> guaranteed spread, not the model's rut
        return soul

    def _parse(self, raw: str) -> dict | None:
        name = role = aim = None
        lines: list[str] = []
        seen_name = False           # ignore any preamble the model emits before the block
        for ln in raw.splitlines():
            s = ln.strip().lstrip("-*•").strip()
            if not s:
                continue
            low = s.lower()
            if low.startswith("name:"):
                name = _name_of(s.split(":", 1)[1]); seen_name = True
            elif low.startswith(("trade:", "role:")):
                role = _clean(s.split(":", 1)[1]).strip()[:24] or None
            elif low.startswith(("fear:", "longing:", "aim:")):
                aim = _clean(s.split(":", 1)[1]).strip()[:60] or None
            elif low.startswith("lines:"):
                continue
            elif seen_name and not s.endswith(":"):   # a muttered line (only inside the block)
                t = _clean(s.strip('"').strip())
                if 2 <= len(t.split()) <= 18:
                    lines.append(t)
        lines = list(dict.fromkeys(lines))[:5]            # dedupe, cap
        if not name or not lines:
            return None
        return {"name": name, "role": role or "wanderer", "aim": aim or lines[0], "lines": lines}

    def apply(self, agent, soul: dict, tick: int) -> None:
        """Write the dreamed identity onto a (still-living) reborn agent. Fast -- call under the lock."""
        agent.name = soul["name"]
        agent.role = soul["role"]
        agent.task = soul["role"]
        agent.aim = soul["aim"]
        for ln in soul["lines"]:
            try:
                agent.memory.write(ln, tick=tick, source="self", speaker_id=agent.id, weight=0.9)
            except Exception:   # noqa: BLE001
                pass
        agent.phrases = list(soul["lines"]) + list(getattr(agent, "phrases", []))[:3]

    def seed_corpus(self, soul: dict) -> None:
        """Append the new lines to the living corpus (markov + consolidation read it) + log diversity."""
        os.makedirs(os.path.dirname(LIVING_CORPUS), exist_ok=True)
        with open(LIVING_CORPUS, "a", encoding="utf-8") as f:
            f.write("\n".join(soul["lines"]) + "\n")
        self._log_diversity()

    def _log_diversity(self) -> None:
        """Make model-collapse VISIBLE: log how varied the living corpus stays as the 8B feeds it."""
        try:
            lines = [ln for ln in open(LIVING_CORPUS, encoding="utf-8").read().splitlines() if ln.strip()]
            total = len(lines)
            uniq = len(set(lines))
            vocab = len({w for ln in lines for w in ln.split()})
            os.makedirs(os.path.dirname(DIVLOG), exist_ok=True)
            with open(DIVLOG, "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  lines={total}  "
                        f"unique={uniq/total:.2f}  vocab={vocab}\n")
        except Exception:   # noqa: BLE001
            pass
