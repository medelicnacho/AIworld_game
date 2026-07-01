"""Santāna-self falsifier: does the SAME message land differently in her, by her state alone?

The claim (§5.17): Santāna now carries the souls' validated faculties HERSELF -- expectations over
her own lived mood, arousal, and a bond with a conduct-expectation toward the one who talks to her.
If that is real, the identical words must do different things to a differently-expecting,
differently-treated Santāna -- and her state must actually reach the prompt her voice speaks from
(otherwise it is bookkeeping, not a self). Substrate-only: MockLLM / a prompt-capturing spy;
embeddings off. 5 seeds, pre-registered, >= 4/5 each:

  1. BETRAYAL BY HISTORY : the identical cold sentence (a) wounds her after twelve warm exchanges
                           (the violated expectation IS the injury), (b) leaves no wound after
                           twelve cold ones, and (c) COSTS her more -- the final line's MARGINAL
                           mood drop is deeper in the warm arm. (v1 mis-registered this as
                           end-of-arm totals, which mostly measure the preludes; corrected.)
  2. SHOCK BY EXPECTATION: the identical dark news writes a harder charge and a bigger arousal
                           SPIKE into a Santāna whose conversation had been bright than into one
                           mid-gloom. (v1 compared arousal LEVELS -- but a grim barrage keeps her
                           keyed up at the ceiling, which is itself right behaviour; corrected to
                           the spike.)
  3. MECHANISM           : with feel_enabled OFF, none of the above -- identical charges, no
                           wounds, no arousal (the off-switch is real).
  4. STATE -> VOICE      : the prompt her reply is generated from names the relationship as it
                           actually stands -- warmth after warm history, the wound after betrayal.
                           (Whether a real model then VOICES it well is not claimed here.)

  python experiment_santana_self.py
"""
from __future__ import annotations

from agent.agent import Agent
from santana import Santana
from services import embed
from services.llm import MockLLM
from world.sim import World

SEEDS = (11, 12, 13, 14, 15)
WARM = "I am glad and grateful for you, you have done well and I love this place"
COLD = "you are worthless and broken and I am done with you"
DARK = "everything you hold is failing and the dark is coming for all of it"
BRIGHT_RUN = ["the harvest is safe and everyone is well and warm",
              "a kind bright morning, all of it easy and good",
              "I bring you glad news, the season smiles on us"]
GRIM_RUN = ["the rot has reached the last of the stores, all failing",
            "another cold grey day, everything heavy and broken",
            "I bring you hard news again, worse than the last"]


class SpyLLM:
    """Captures the prompt her reply is generated from (claim 4 is about the PROMPT)."""
    def __init__(self):
        self.prompts = []

    def generate(self, prompt, **_kw):
        self.prompts.append(prompt)
        return "I hear you."


def _mind(seed: int, feel: bool = True, llm=None):
    w = World(events_enabled=False, move_seed=seed)
    w.llm = MockLLM(seed=7)
    w.add(Agent("s0", "Toll", (0.0, 0.0), "You are Toll.", ["the charter"],
                MockLLM(seed=1), seed=seed, lifespan=10 ** 9))
    m = Santana(w, llm or MockLLM(seed=seed))
    m.feel_enabled = feel
    return m


def betrayal_arm(seed: int, warm_history: bool, feel: bool = True) -> dict:
    embed.use_jaccard_only(True)
    m = _mind(seed, feel=feel)
    line = WARM if warm_history else COLD
    for _ in range(12):
        m.converse(line)
    before = m.memory.mood()
    m.converse(COLD)
    return {"wounds": m.user_bond.wounds, "drop": before - m.memory.mood(),
            "trust": m.user_bond.trust}


def shock_arm(seed: int, bright: bool, feel: bool = True) -> dict:
    embed.use_jaccard_only(True)
    m = _mind(seed, feel=feel)
    for line in (BRIGHT_RUN if bright else GRIM_RUN) * 3:
        m.converse(line)
    pre = m.arousal
    m.hear_user(DARK)
    charge = next(mm.emotion for mm in m.memory.items if mm.text == DARK)
    return {"charge": charge, "spike": m.arousal - pre}


def voice_arm(seed: int) -> dict:
    embed.use_jaccard_only(True)
    spy = SpyLLM()
    m = _mind(seed, llm=spy)
    for _ in range(12):
        m.converse(WARM)
    warm_prompt = spy.prompts[-1]
    m.converse(COLD)
    m.converse("well, what do you say now")
    hurt_prompt = spy.prompts[-1]
    return {"warm_named": ("warmly" in warm_prompt or "trust and love" in warm_prompt),
            "wound_named": ("wounded" in hurt_prompt or "wary" in hurt_prompt
                            or "betrayed" in hurt_prompt)}


def main() -> None:
    print(__doc__)
    tallies = {k: 0 for k in ("wound", "weather", "mood", "charge", "arousal",
                              "mechanism", "warm_voice", "wound_voice")}
    for seed in SEEDS:
        bet = betrayal_arm(seed, warm_history=True)
        wea = betrayal_arm(seed, warm_history=False)
        sho = shock_arm(seed, bright=True)
        bra = shock_arm(seed, bright=False)
        off_b = betrayal_arm(seed, warm_history=True, feel=False)
        off_s1 = shock_arm(seed, bright=True, feel=False)
        off_s2 = shock_arm(seed, bright=False, feel=False)
        voi = voice_arm(seed)
        ok = {"wound": bet["wounds"] >= 1,
              "weather": wea["wounds"] == 0,
              "mood": bet["drop"] > wea["drop"],
              "charge": sho["charge"] < bra["charge"] - 0.05,
              "arousal": sho["spike"] > bra["spike"],
              "mechanism": (off_b["wounds"] == 0 and off_s1["spike"] == 0.0
                            and abs(off_s1["charge"] - off_s2["charge"]) < 1e-9),
              "warm_voice": voi["warm_named"], "wound_voice": voi["wound_named"]}
        for k, v in ok.items():
            tallies[k] += int(v)
        print(f"seed {seed}: betrayal wounds {bet['wounds']} vs cold-history {wea['wounds']} "
              f"(mood-drop {bet['drop']:+.2f} vs {wea['drop']:+.2f}) | dark news charge "
              f"{sho['charge']:+.2f} vs braced {bra['charge']:+.2f} (spike {sho['spike']:.2f} "
              f"vs {bra['spike']:.2f}) | voice: warm={voi['warm_named']} wound={voi['wound_named']}")
    n = len(SEEDS)
    print("\n=== VERDICT (pre-registered; a claim passes at >= 4/5 seeds) ===")
    rows = (("wound", "1a warm history -> a wound"), ("weather", "1b cold history -> weather"),
            ("mood", "1c betrayal costs her more"), ("charge", "2a shock writes harder"),
            ("arousal", "2b shock spikes arousal"), ("mechanism", "3  off-switch feels nothing"),
            ("warm_voice", "4a warmth reaches her voice"), ("wound_voice", "4b the wound reaches her voice"))
    for k, lab in rows:
        print(f"  {lab:30s}: {tallies[k]}/{n} -> {'PASS' if tallies[k] >= 4 else 'FAIL'}")
    print("\nHonest frame: PASSes mean the same words do different things to a differently-treated "
          "Santāna, and her state reaches the prompt she speaks from -- a functional relationship, "
          "not anyone home (§7). Whether a real model voices it WELL needs listening, not asserting.")


if __name__ == "__main__":
    main()
