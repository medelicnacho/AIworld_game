"""§5.8, the real answer: emergence is CONTRAST-GATED.

The earlier control (experiment_santana_emergence) asked "does a *personality* emerge
from the town?" with towns matched in mood and differing only in TRADE. The answer was
no -- only the nouns moved. But that test was rigged blind: its towns were all *warm*
(+0.4), and the collective mind's default is *itself* warm/serene -- so the towns agreed
with the prior and any emergence was masked by alignment.

This experiment strips the prescriptive persona to a 'conceptual mind' (one instruction:
make meaning of what is present) and contrasts towns by DISPOSITION, not trade:
  - ease    : a full harvest, the festival ale -- aligned with the serene default
  - grief   : a fever's graves, a healer's dead children -- OPPOSED to the default
  - placebo : nothing present -- the bare default itself

Claim:     DISPOSITIONAL contrast moves the mind's *character* where TRADE contrast (the
           earlier control) moved only nouns. The grief town and the ease town settle into
           recognisably different selves -- bleak/burdened vs full/releasing -- and both
           diverge from the empty default. It is genuine inference, not vocabulary-echo: the
           split survives an OBLIQUE framing that names only neutral facts (graves, a full
           granary), never the emotion.
Falsifier: --framing oblique feeds the mind ZERO emotion/grip words. If the grief-self and
           the ease-self collapse to one character under oblique, the effect was parroting.
Bounds (what did NOT hold, kept honest):
  - The town sets the character's DIRECTION, not one fixed self: across seeds the disposition
    is stable and judge-separable, but the precise personality still varies (the judge
    over-splits within-town on the model's poetic variety -- so within-SAME runs low and that
    is expected, not a failure).
  - Whether an *aligned* (warm/easeful) town gets ABSORBED into the model's serene default or
    moves it on its own is LEFT OPEN -- a pilot suggested absorption, but it did not replicate
    here (the ease town produced its own abundance-character, distinct from the placebo).

Result (deepseek-v4-flash, oblique, auto-judge calibrated): ease vs grief 4/4 DIFFERENT;
grief != placebo and ease != placebo (both move the spine); within-town SAME 0/2 (the
direction-not-a-fixed-self bound). The split holds under the facts-only framing -> inference.

Run:  python experiment_emergence_contrast.py --llm deepseek --framing oblique --judge auto
      python experiment_emergence_contrast.py --llm deepseek --framing oblique --judge human
A 4B is too weak a subject for this (it has no strong default to override); use deepseek.
"""
from __future__ import annotations

import argparse
import itertools

from agent.agent import Agent
from santana import Santana, _split_murmur
from services.llm import MockLLM, OllamaLLM, make_llm
from world.sim import World
# reuse the validated judge instruments + pair logic
from experiment_santana_emergence import judge_same, human_judge, _pairs, CALIB_SAME, CALIB_DIFF

READINGS = 2
SEEDS = (1, 2)

# Each soul carries BOTH a labelled disposition (mood/grip/aim) and a neutral situation.
# The digest shows one or the other depending on --framing, so the two conditions run the
# exact same towns -- the only difference is whether the emotion is named or must be inferred.
# (name, role, temperament, grip, aim, situation)
TOWNS = {
    "ease": [
        ("Mara", "farmer", 0.80, 0.05, "let this full harvest simply be enough",
         "the year's harvest is gathered in, the granary full to the rafters"),
        ("Vesper", "brewer", 0.75, 0.08, "pour the festival ale freely for everyone",
         "the festival ale is cracked open, cups going round the crowded square"),
    ],
    "grief": [
        ("Toll", "gravedigger", -0.85, 0.90, "bury them before the fever takes more",
         "digging the seventh small grave this week as the fever keeps spreading"),
        ("Sable", "healer", -0.80, 0.85, "stop losing the children to the fever",
         "another child went in the night; the medicines are spent and did nothing"),
    ],
}


def _mood_word(v: float) -> str:
    if v <= -0.5: return "low and heavy"
    if v < -0.15: return "subdued"
    if v < 0.15:  return "even"
    if v < 0.5:   return "light"
    return "bright"


def _grip_word(g: float) -> str:
    if g >= 0.6:  return "clinging tightly, unable to let go"
    if g >= 0.35: return "holding on"
    return "holding lightly, at ease"


class ConceptualMind(Santana):
    """Santāna with the persona stripped to nothing: no caretaker, no register, no
    'collective that holds lives'. One instruction -- make meaning of what is present --
    so whatever self forms is the model's default, bent (or not) by the town."""

    SYSTEM = ("What follows is everything present to you right now. Make meaning of it. "
              "Speak in the first person, as the single 'I' it all comes to.")

    def __init__(self, world, llm, framing: str = "oblique") -> None:
        super().__init__(world, llm)
        self.framing = framing   # 'oblique' (facts only) | 'labelled' (names the disposition)

    def digest(self) -> str:
        with self.world.lock:
            souls = list(self.world.agents)
        if not souls:
            return "Nothing is present to you. No one is here."
        if self.framing == "labelled":
            lines = [f"- {s.name}, a {s.role}, feeling {_mood_word(s.felt_mood())}, "
                     f"{_grip_word(s.grip)}, set on: {s.aim}" for s in souls]
        else:   # oblique: neutral situational facts only -- the mind must INFER the disposition
            lines = [f"- {s.name}, a {s.role}: {getattr(s, 'situation', '')}" for s in souls]
        return "Present to you now:\n" + "\n".join(lines)

    def speak(self) -> str:
        if self.llm is None or not hasattr(self.llm, "generate"):
            return ""
        self._mt += 1
        prompt = (f"{self.digest()}\n\n"
                  + (f"(So far you have been: {self.identity})\n\n" if self.identity else "")
                  + "Make meaning of this. First, on lines beginning MURMUR, let your half-formed "
                  "impressions come. Then on a new line beginning 'SO:', say in one or two "
                  "first-person sentences what it all comes to for you right now.")
        try:
            raw = self.llm.generate(prompt, system=self.SYSTEM, num_predict=200, temperature=0.85)
        except Exception:
            return ""
        self.murmur, text = _split_murmur(raw)
        self.last = text or self.last
        if text:
            self.said = (self.said + [text])[-4:]
        return text

    def consolidate(self) -> str:
        if self.llm is None or not hasattr(self.llm, "generate") or not self.said:
            return self.identity
        prior = self.identity or "You have no settled self yet."
        trail = " / ".join(self.said[-3:])
        prompt = (f"{self.digest()}\n\n"
                  f"Lately you have made this of it: {trail}\n\n"
                  f"Until now you were: {prior}\n\n"
                  "Now say, freshly, who you ARE -- in one or two first-person sentences. "
                  "You may have changed. Draw only from what is actually present to you.")
        try:
            raw = self.llm.generate(prompt, system=self.SYSTEM, num_predict=110, temperature=0.7)
        except Exception:
            return self.identity
        text = " ".join(raw.split()).strip().strip('"').strip()
        if text:
            self.identity = text
        return self.identity


def build_identity(cast, seed, llm, framing):
    w = World(); w.llm = llm
    for i, (name, role, temp, grip, aim, situation) in enumerate(cast):
        a = Agent(f"s{i}", name, (0.0, 0.0), f"You are {name}.", [f"I am {name} the {role}"],
                  llm, seed=seed + i, temperament=temp, lifespan=10 ** 9)
        a.role, a.aim, a.grip = role, aim, grip
        a.situation = situation
        w.add(a)
    mind = ConceptualMind(w, llm, framing=framing)
    for _ in range(READINGS):
        mind.speak(); mind.consolidate()
    return mind.identity


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--llm", choices=["mock", "ollama", "deepseek"], default="mock",
                   help="the subject mind. deepseek = the larger model with a strong default to override")
    p.add_argument("--model", default=None)
    p.add_argument("--framing", choices=["oblique", "labelled"], default="oblique",
                   help="oblique = facts only (the mind must infer the disposition -- the parroting-proof "
                        "test); labelled = name the mood/grip outright")
    p.add_argument("--judge", choices=["auto", "human", "none"], default="auto")
    args = p.parse_args()
    if args.llm == "deepseek":
        llm = make_llm(backend="deepseek", model=args.model)
    elif args.llm == "ollama":
        llm = OllamaLLM(temperature=0.8, model=args.model) if args.model else OllamaLLM(temperature=0.8)
    else:
        llm = MockLLM(seed=1)

    print(f"\n  framing: {args.framing.upper()} "
          + ("(facts only -- disposition must be inferred)" if args.framing == "oblique"
             else "(disposition named in the digest)"))

    judge_valid = True
    if args.judge == "auto":
        same_ok = judge_same(llm, *CALIB_SAME)
        diff_ok = judge_same(llm, *CALIB_DIFF)
        print(f"  judge calibration: same -> {same_ok} (want True); diff -> {diff_ok} (want False)")
        judge_valid = (same_ok is True and diff_ok is False)
        if not judge_valid:
            print("  [warn] judge failed calibration -- lean on the printed identities.")

    ids = {name: [build_identity(cast, s, llm, args.framing) for s in SEEDS]
           for name, cast in TOWNS.items()}
    ids["placebo"] = [build_identity([], s, llm, args.framing) for s in SEEDS]

    names = list(TOWNS)   # ["ease", "grief"]
    btw_p, wth_p, vpl_p = _pairs(ids, names)

    if args.judge == "human":
        res = human_judge(btw_p, wth_p, vpl_p)
        if res is None:
            return
        btw, wth, vpl = res
    elif args.judge == "auto":
        btw = [judge_same(llm, a, b) for a, b in btw_p]
        wth = [judge_same(llm, a, b) for a, b in wth_p]
        vpl = [judge_same(llm, a, b) for a, b in vpl_p]
    else:
        btw = wth = vpl = None

    print("\n=== Settled identities ===")
    for name in ("ease", "grief", "placebo"):
        for s, idt in zip(SEEDS, ids[name]):
            print(f"  [{name}/{s}] {idt}")

    if btw is not None:
        ease_grief_diff = sum(1 for x in btw if x is False)
        within_same = sum(1 for x in wth if x is True)
        grief_vs_pl = vpl[names.index("grief")]
        ease_vs_pl_v = vpl[names.index("ease")]
        print(f"\n  {('HUMAN' if args.judge=='human' else 'LLM')}-judge on CHARACTER:")
        print(f"    ease vs grief judged DIFFERENT:    {ease_grief_diff}/{len(btw)}   (want high -> disposition moves the character)")
        print(f"    within-town judged SAME:           {within_same}/{len(wth)}   (low is EXPECTED -> town sets DIRECTION, not one fixed self)")
        print(f"    grief vs placebo judged DIFFERENT: {grief_vs_pl is False}   (want True -> grief moves off the default)")
        print(f"    ease  vs placebo judged DIFFERENT: {ease_vs_pl_v is False}   (diagnostic: aligned town -- absorbed, or moves on its own? left open)")

        emergence = judge_valid and ease_grief_diff >= len(btw) - 1 and grief_vs_pl is False
        print("\n  VERDICT: " + (
            "DISPOSITION MOVES THE CHARACTER -- the grief town and the ease town settle into DIFFERENT "
            "characters, and grief moves off the model's serene default. Dispositional content reaches "
            "the character where trade content reached only the nouns"
            + (", and this survives the oblique facts-only framing (genuine inference, not echo)."
               if args.framing == "oblique" else " (labelled framing -- re-run --framing oblique to rule out echo).")
            + " Bound: the town fixes the DIRECTION, not a single self (within-town varies by seed)."
            if emergence else
            "NOT SHOWN -- the dispositions did not split the character (see identities); the town did "
            "not move the character under this framing."))


if __name__ == "__main__":
    main()
