"""Pledge falsifier (Phase A): does a word broken to ONE soul become a TOWN's wariness?

The player is just another id here ("player") -- never present as an agent, only as the
one whose promises land on a victim soul. The claim chain: a lapsed promise is a betrayal
(pledge.py) -> the breach writes a conduct story -> the VALIDATED C3 channel
(experiment_reputation.py) gossips it -> souls the player never touched grow wary. And the
mirror: kept words travel warm. This is the trust/karma substrate the game's join-or-oppose
decisions will read -- measured before anything is built on it.

Substrate-only (MockLLM, embeddings off), co-located town, same harness shape as the
reputation falsifier. One VICTIM receives promises from "player"; six BYSTANDERS never do.

PRE-REGISTERED (tuning 11-15; VERDICT from virgin seeds 71-75; each claim >= 4/5).
CONSUMED: 61-65 -- spent on v1, whose stories carried their charge only in the emotion=
parameter: the dyad held (claims 3+4 PASS 5/5) but nothing traveled (claims 1+2 FAIL 0/5),
because GOSSIP TRANSMITS FEELING ONLY THROUGH THE WORDING -- hearers re-derive the charge
from the retold text. v2 charges the words themselves ("broken", "bitter", "kindness");
61-65 are never a verdict again.

  1. TRAVELS DARK : broken-word arm -- >= 3 of 6 bystanders end wary of "player"
                    (conduct-expectation < -0.1); in the no-lore null, NO bystander holds
                    any opinion of "player" at all.
  2. TRAVELS WARM : kept-word arm -- of bystanders holding an opinion of "player",
                    >= 80% lean warm and their mean is > +0.05 (direction, not just noise).
  3. SPECIFICITY  : in both arms, bystanders hold ~no opinion (|exp| < 0.1) of a
                    "stranger" id that promised nothing -- reputation is per-subject.
  4. THE VICTIM   : broken arm -- the victim carries wounds (>= 2) and negative trust
                    toward "player"; kept arm -- zero wounds and positive trust.
                    (The dyad substrate holds underneath the gossip.)

  python experiment_pledge.py
"""
from __future__ import annotations

import statistics

from agent import pledge
from agent.agent import Agent
from services import embed
from services.llm import MockLLM
from world.sim import World

TUNING_SEEDS = (11, 12, 13, 14, 15)
HELDOUT_SEEDS = (71, 72, 73, 74, 75)   # 61-65 consumed by v1 (see docstring)
TICKS = 600
N_BYSTANDERS = 6
CYCLE = 40           # a promise made every cycle; kept in time, or left to the clock


def build(seed: int, lore_on: bool) -> World:
    w = World(events_enabled=False, murmur_enabled=True, move_seed=seed)
    w.llm = MockLLM(seed=7)
    w.lore_enabled = lore_on
    names = ["Victa"] + [f"Byst{i}" for i in range(N_BYSTANDERS)]
    for i, name in enumerate(names):
        a = Agent(f"s{i}", name, (i * 10.0, 0.0), "You are a working soul.",
                  [f"the well and the road, day {i}"], w.llm,
                  seed=1000 * seed + i, temperament=0.0, lifespan=10 ** 9)
        a.expect_enabled = True
        a.bond_enabled = True
        w.add(a)
    return w


def run(seed: int, kept: bool, lore_on: bool) -> dict:
    embed.use_jaccard_only(True)
    w = build(seed, lore_on)
    victim = w.agents[0]
    for t in range(1, TICKS + 1):
        phase = t % CYCLE
        if phase == 1:      # the word is given, due mid-cycle
            pledge.make(victim, "player", "the far-walker",
                        "I will bring grain before the frost", due_tick=t + 15, now=t)
        elif phase == 10 and kept:              # kept in time...
            pledge.fulfill(victim, "player", now=t)
        w.advance()                              # ...or the clock breaks it (Agent.step)
    bystanders = w.agents[1:]
    player_exp = [b._conduct_expect.get("player") for b in bystanders]
    stranger_exp = [abs(b._conduct_expect.get("stranger", 0.0)) for b in bystanders]
    vb = victim.bonds.get("player")
    return {"exp": player_exp, "stranger": stranger_exp,
            "wounds": vb.wounds if vb else 0, "trust": vb.trust if vb else 0.0}


def report(seeds, label: str):
    print(f"\n--- {label} ---")
    rows = []
    for seed in seeds:
        broke = run(seed, kept=False, lore_on=True)
        broke_null = run(seed, kept=False, lore_on=False)
        keptr = run(seed, kept=True, lore_on=True)
        held_dark = [e for e in broke["exp"] if e is not None]
        wary = sum(1 for e in held_dark if e < -0.1)
        null_opinions = sum(1 for e in broke_null["exp"] if e is not None)
        held_warm = [e for e in keptr["exp"] if e is not None]
        warm_share = (sum(1 for e in held_warm if e > 0) / len(held_warm)) if held_warm else 0.0
        warm_mean = statistics.fmean(held_warm) if held_warm else 0.0
        m = {"dark": wary >= 3 and null_opinions == 0,
             "warm": bool(held_warm) and warm_share >= 0.8 and warm_mean > 0.05,
             "specificity": all(x < 0.1 for x in broke["stranger"] + keptr["stranger"]),
             "victim": (broke["wounds"] >= 2 and broke["trust"] < 0
                        and keptr["wounds"] == 0 and keptr["trust"] > 0)}
        rows.append(m)
        print(f"seed {seed}: broken -> victim wounds {broke['wounds']} trust "
              f"{broke['trust']:+.2f}, bystanders wary {wary}/6 (null opinions "
              f"{null_opinions}) | kept -> victim trust {keptr['trust']:+.2f}, "
              f"bystanders warm {warm_share:.0%} mean {warm_mean:+.2f}")
        for k, lab in (("dark", "1 travels dark"), ("warm", "2 travels warm"),
                       ("specificity", "3 specificity"), ("victim", "4 the victim")):
            print(f"    {lab:15s}: {'PASS' if m[k] else 'FAIL'}")
    print(f"\n  {label} tally:")
    for k, lab in (("dark", "1 TRAVELS DARK"), ("warm", "2 TRAVELS WARM"),
                   ("specificity", "3 SPECIFICITY"), ("victim", "4 THE VICTIM")):
        print(f"    {lab:15s}: {sum(1 for r in rows if r[k])}/{len(rows)}")
    return rows


def main() -> None:
    print(__doc__)
    report(TUNING_SEEDS, "TUNING seeds 11-15 (knobs may be tuned here; not the verdict)")
    held = report(HELDOUT_SEEDS, "HELD-OUT virgin seeds 71-75 (the verdict)")
    print("\n=== VERDICT (held-out; pre-registered: a claim passes at >= 4/5) ===")
    ok = True
    for k, lab in (("dark", "1 TRAVELS DARK"), ("warm", "2 TRAVELS WARM"),
                   ("specificity", "3 SPECIFICITY"), ("victim", "4 THE VICTIM")):
        cnt = sum(1 for r in held if r[k])
        ok &= cnt >= 4
        print(f"  {lab:15s}: {cnt}/{len(held)} -> {'PASS' if cnt >= 4 else 'FAIL'}")
    print("\nHonest frame: a PASS means a promise to ONE soul measurably becomes a TOWN's "
          "opinion of the promiser, in both directions, per-subject -- the substrate the "
          "game's join-or-oppose decision will read. Whether that opinion is FAIR rides "
          "the same mutating channel as any legend (§7 unchanged).")


if __name__ == "__main__":
    main()
