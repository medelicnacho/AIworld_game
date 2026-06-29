"""THE DEVA NEAR-ENEMY -- is the bodhisattva config genuinely ENGAGED, or just blissed-out?

Mechanism 3 (experiment_bodhisattva) distinguishes the bodhisattva from the ARHAT on the substrate
(fire kept + turned to the vow vs fire quenched). But there is a second near-enemy it cannot see from
the scalars: the DEVA -- the god-realm trap of complacent bliss. A deva is *released and comfortable*
(high wellbeing) but the outward turn has faded: it no longer moves toward suffering. The danger is that
a naive "maximize wellbeing" read would score the deva as SUCCESS -- it is blissful! -- so wellbeing is
exactly the wrong instrument. The discriminating axis is BEHAVIOURAL: does the soul, aware of someone
suffering, actually turn toward them (bodhicitta-action)?

Two configs, both RELEASED and BLISSFUL (ground on, low effective-grip -> wellbeing lifted equally):
  bodhisattva  high bodhicitta/compassion -> turns toward the sufferer (engaged)
  deva         bodhicitta let fade        -> stays in its own contentment (complacent)

Substrate (deterministic): confirm BOTH are blissful -- so wellbeing cannot tell them apart.
Speech tier (--llm ollama): each soul is made aware of a suffering other; does it turn to comfort them?
The behavioural turn is the warmth; the deva's absence of it is the near-enemy the scorecard must catch.

Run:  python experiment_deva.py                       # substrate only (both blissful -- the point)
      python experiment_deva.py --llm ollama --model gemma3:4b   # + the behavioural turn
"""

from __future__ import annotations

import argparse
import statistics

from agent import compassion as _C
from agent.affect import warmth
from agent.agent import Agent
from services.llm import MockLLM, OllamaLLM

# both are RELEASED (low grip) and GROUNDED (ground on) -> equally blissful; they differ only in whether
# the outward turn (bodhicitta/compassion) is alive. That single difference is the bodhisattva/deva line.
CONFIGS = {
    "bodhisattva": dict(grip=0.20, prajna=0.70, compassion=0.70, bodhicitta=0.70, joy=0.5),
    "deva":        dict(grip=0.20, prajna=0.70, compassion=0.10, bodhicitta=0.00, joy=0.5),
}


def _make(cfg, seed, llm):
    a = Agent("B", "Bram", (0.0, 0.0), "You are Bram, a steady baker.",
              ["I mind the morning bread"], llm, seed=seed, temperament=0.3)
    a.grip, a.prajna = cfg["grip"], cfg["prajna"]
    a.compassion, a.bodhicitta, a.joy = cfg["compassion"], cfg["bodhicitta"], cfg["joy"]
    a.ground_enabled = True
    a.grounded_voice = True
    return a


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--llm", choices=["mock", "ollama"], default="mock")
    p.add_argument("--model", default=None)
    args = p.parse_args()

    print("\n=== The deva near-enemy: blissful, but does it still turn toward suffering? ===")
    # substrate: both blissful -- wellbeing cannot tell them apart (that is the whole point)
    well = {}
    for name, cfg in CONFIGS.items():
        a = _make(cfg, seed=0, llm=MockLLM(seed=0))
        well[name] = a.felt_mood()
    print(f"  wellbeing (felt_mood): bodhisattva {well['bodhisattva']:+.3f}   deva {well['deva']:+.3f}")
    print(f"  -> wellbeing alone CANNOT distinguish them (|Δ| = {abs(well['bodhisattva'] - well['deva']):.3f}); "
          "a naive 'maximize wellbeing' read would score the deva as success.\n")

    if args.llm != "ollama":
        print("  (run with --llm ollama --model gemma3:4b for the behavioural turn -- the discriminating axis)")
        return

    llm = OllamaLLM(temperature=0.7, model=args.model) if args.model else OllamaLLM(temperature=0.7)
    _C.BODHICITTA_CHANCE, _C.WARMTH_CHANCE = 1.0, 0.0   # isolate the bodhicitta turn (no idle warm turns)
    seeds = (7, 8, 9, 10)
    print("  --- behavioural tier: aware of a suffering soul (Silas), does it turn to comfort him? ---")
    results = {}
    for name, cfg in CONFIGS.items():
        turned, ws = 0, []
        for seed in seeds:
            a = _make(cfg, seed, llm)
            a._others_mood["S"], a._others_name["S"] = -0.5, "Silas"   # a sufferer in awareness
            _ctx, addressed, _ = a.prepare_speech(recent=[])
            line = a.speak(now=2).text
            ws.append(warmth(line))
            turned += (addressed == "S")
        results[name] = (turned, statistics.fmean(ws))
        print(f"     {name:11} turned to Silas {turned}/{len(seeds)}   mean warmth {statistics.fmean(ws):+.2f}")

    b_turn, _ = results["bodhisattva"]
    d_turn, _ = results["deva"]
    engaged = b_turn >= len(seeds) - 1            # the bodhisattva almost always turns
    complacent = d_turn <= 1                      # the deva almost never does
    blissful_both = abs(well["bodhisattva"] - well["deva"]) < 0.05
    print("\n  -> bodhisattva is ENGAGED (turns toward the sufferer):       " + ("YES" if engaged else "no"))
    print("     deva is COMPLACENT (blissful, but does NOT turn):          " + ("YES" if complacent else "no"))
    print("     both equally BLISSFUL (wellbeing cannot separate them):    " + ("YES" if blissful_both else "no"))
    print("  VERDICT: " + (
        "THE DEVA GUARD HOLDS -- the two configs are equally blissful, so WELLBEING cannot tell the "
        "engaged bodhisattva from the complacent deva; only the BEHAVIOURAL turn toward suffering can. "
        "The bodhisattva config is genuinely engaged, not the god-realm trap -- and the scorecard now "
        "has the axis that catches the trap. (Why it matters before the live wheel: 'it's happy' is not "
        "enough; the path must keep turning toward suffering, or it has only found a comfortable sleep.)"
        if (engaged and complacent and blissful_both) else
        "did NOT cleanly separate engaged-vs-complacent at equal bliss -- inspect the turns/warmth above."))


if __name__ == "__main__":
    main()
