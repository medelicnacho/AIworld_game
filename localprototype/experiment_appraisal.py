"""Appraisal falsifier: does EXPECTATION actually change what the same event does to a self?

The predictive-selfhood claim (agent/expectation.py): an event's charge is appraised against what
the self had come to expect -- the SAME loss lands as SHOCK in a self whose days were good and
softer in one already living the fall; a cold act from one EXPECTED WARM is a betrayal (a wound),
from one expected cold it is weather. Substrate-only (MockLLM, embeddings off), deterministic
per seed, 5 seeds.

PRE-REGISTERED (before running; the null in each case is "appraisal is decorative"):

  1. SHOCK vs BRACED : the identical -0.7 loss, after a good stretch vs a worsening one:
                       (a) the written charge is more aversive in the blindsided self,
                       (b) its arousal spikes higher,
                       (c) its lived mood DROPS further from its pre-loss level.
  2. MECHANISM       : with expect_enabled OFF, the two contexts write IDENTICAL charges
                       (any difference would mean the effect isn't the appraisal).
  3. BETRAYAL        : the identical cold act (a) wounds the bond when it violates a warm
                       history, (b) leaves no wound after a cold history, and (c) the
                       betrayed self's lived mood suffers more than the unsurprised one's.

  A claim passes at >= 4/5 seeds. FAILs get recorded (FINDINGS discipline).

  python experiment_appraisal.py
"""
from __future__ import annotations

import statistics

from agent.agent import Agent
from agent.bond import Bond
from agent import expectation
from services import embed
from services.llm import MockLLM
from world.events import WorldEvent

SEEDS = (11, 12, 13, 14, 15)
LOSS_TICK = 40
END_TICK = 90
LOSS = WorldEvent(name="loss", description="someone dear is gone from me",
                  tick=LOSS_TICK, emotion=-0.7, urge=0.6)
GOOD_RUN = [("the festival went well and the bread was warm", 0.3, 20),
            ("a kind word over the fence this morning", 0.3, 27),
            ("the work came good and the evening was easy", 0.3, 34)]
BAD_RUN = [("the rains failed again and the field is cracking", -0.3, 20),
           ("another cold word where a kind one used to be", -0.3, 27),
           ("the stores are thinner every day now", -0.3, 34)]


def _soul(seed: int, expect: bool) -> Agent:
    a = Agent("s", "Soul", (0.0, 0.0), "You are a working soul.", ["the same streets"],
              MockLLM(seed=1), seed=seed, temperament=0.0, lifespan=10 ** 9)
    a.expect_enabled = expect
    return a


def run_arm(seed: int, context, expect: bool = True) -> dict:
    """One life: a context stretch, then the identical loss. Returns the loss memory's
    written charge, arousal at the moment, and the mood drop from pre-loss to trough."""
    embed.use_jaccard_only(True)
    a = _soul(seed, expect)
    moods = []
    for t in range(1, END_TICK + 1):
        for text, emo, at in context:
            if t == at:
                a.perceive(WorldEvent(name="ctx", description=text, tick=t, emotion=emo), t)
        if t == LOSS_TICK:
            pre_mood = a.memory.mood()
            a.perceive(LOSS, t)
            arousal = a.arousal
            charge = next(m.emotion for m in reversed(a.memory.items)
                          if m.text == LOSS.description)
        a.step(t)
        moods.append(a.memory.mood())
    drop = pre_mood - min(moods[LOSS_TICK - 1:])
    return {"charge": charge, "arousal": arousal, "drop": drop}


def run_betrayal(seed: int, warm_history: bool) -> dict:
    """One bonded life: 12 conduct signals of history, then the identical cold act."""
    embed.use_jaccard_only(True)
    a = _soul(seed, expect=True)
    a.bond_enabled = True
    b = a.bonds.setdefault("v", Bond())
    sig = 0.4 if warm_history else -0.2
    for t in range(1, 13):
        expectation.appraise_conduct(a, "v", "Vesper", sig, t, b)
        a.step(t)
    expectation.appraise_conduct(a, "v", "Vesper", -0.4, 13, b)   # the identical cold act
    for t in range(13, 40):
        a.step(t)
    return {"wounds": b.wounds, "trust": b.trust, "mood": a.memory.mood()}


def main() -> None:
    print(__doc__)
    tallies = {k: 0 for k in ("charge", "arousal", "drop", "mechanism", "wound", "weather", "mood")}
    for seed in SEEDS:
        shock = run_arm(seed, GOOD_RUN)
        braced = run_arm(seed, BAD_RUN)
        off_g = run_arm(seed, GOOD_RUN, expect=False)
        off_b = run_arm(seed, BAD_RUN, expect=False)
        betrayed = run_betrayal(seed, warm_history=True)
        weather = run_betrayal(seed, warm_history=False)
        ok = {"charge": shock["charge"] < braced["charge"] - 0.05,
              "arousal": shock["arousal"] > braced["arousal"],
              "drop": shock["drop"] > braced["drop"],
              "mechanism": abs(off_g["charge"] - off_b["charge"]) < 1e-9,
              "wound": betrayed["wounds"] >= 1,
              "weather": weather["wounds"] == 0,
              "mood": betrayed["mood"] < weather["mood"]}
        for k, v in ok.items():
            tallies[k] += int(v)
        print(f"seed {seed}: loss charge blindsided {shock['charge']:+.2f} vs braced "
              f"{braced['charge']:+.2f} | arousal {shock['arousal']:.2f} vs {braced['arousal']:.2f} "
              f"| mood-drop {shock['drop']:.2f} vs {braced['drop']:.2f} | "
              f"betrayal wounds {betrayed['wounds']} vs cold-history {weather['wounds']} "
              f"(mood {betrayed['mood']:+.2f} vs {weather['mood']:+.2f})")
    n = len(SEEDS)
    print("\n=== VERDICT (pre-registered; a claim passes at >= 4/5 seeds) ===")
    print(f"  1a shock writes harder      : {tallies['charge']}/{n} -> "
          f"{'PASS' if tallies['charge'] >= 4 else 'FAIL'}")
    print(f"  1b shock arouses more       : {tallies['arousal']}/{n} -> "
          f"{'PASS' if tallies['arousal'] >= 4 else 'FAIL'}")
    print(f"  1c shock drops mood further : {tallies['drop']}/{n} -> "
          f"{'PASS' if tallies['drop'] >= 4 else 'FAIL'}")
    print(f"  2  mechanism (off = same)   : {tallies['mechanism']}/{n} -> "
          f"{'PASS' if tallies['mechanism'] >= 4 else 'FAIL'}")
    print(f"  3a warm history -> a wound  : {tallies['wound']}/{n} -> "
          f"{'PASS' if tallies['wound'] >= 4 else 'FAIL'}")
    print(f"  3b cold history -> weather  : {tallies['weather']}/{n} -> "
          f"{'PASS' if tallies['weather'] >= 4 else 'FAIL'}")
    print(f"  3c betrayal hurts the mood  : {tallies['mood']}/{n} -> "
          f"{'PASS' if tallies['mood'] >= 4 else 'FAIL'}")
    print("\nHonest frame: PASSes mean the SAME event does different things to differently-"
          "expecting selves -- functional appraisal, not anyone home (§7).")


if __name__ == "__main__":
    main()
