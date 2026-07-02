"""Reputation falsifier (C3): does a soul's conduct reach souls it never touched -- as gossip?

The claim: reputation = TRANSMITTED EXPECTATION. A betrayal writes a conduct-story
(lore_id "conduct:<subject>"); the lore channel retells it; hearers' conduct-expectations of the
SUBJECT move (agent/lore.py REP_RATE) -- so the town comes to be wary of someone most of it never
met. Substrate-only (MockLLM, embeddings off, stakes off so no competing legends), co-located.

One OFFENDER runs hot-and-cold on ONE victim (warm streaks rebuilding trust, then a cold act --
each cycle re-fires the betrayal and reinforces the story). Six BYSTANDERS never receive a single
direct act from the offender. 600 ticks.

PRE-REGISTERED (tuned 11-15 if needed; VERDICT from virgin seeds 21-25; >= 4/5 each):

  1. TRANSMISSION : >= 3 of 6 bystanders end wary of the offender (expectation < -0.1) in the
                    LORE arm; in the no-lore null NO bystander holds any opinion at all.
  2. CONSENSUS    : of the bystanders who hold an opinion of the offender, >= 80% share its
                    sign, and their mean is < -0.1 -- the town CONVERGES on a reputation
                    rather than scattering.
  3. SPECIFICITY  : the same bystanders hold ~no opinion (|exp| < 0.1) of an INNOCENT soul --
                    reputation is per-subject, not a diffuse souring.
  4. VOICE        : a bystander preparing to speak to the offender carries the reputation line
                    ("heard how they treat people") with NO bond of its own -- gossip reaches
                    speech before acquaintance does.

  python experiment_reputation.py
"""
from __future__ import annotations

import statistics

from agent import expectation
from agent.agent import Agent
from agent.bond import Bond
from services import embed
from services.llm import MockLLM
from world.sim import World

TUNING_SEEDS = (11, 12, 13, 14, 15)
HELDOUT_SEEDS = (21, 22, 23, 24, 25)
TICKS = 600
N_BYSTANDERS = 6
CYCLE = 40           # offender's hot-cold rhythm: warm streak, then the knife


def build(seed: int, lore_on: bool) -> World:
    w = World(events_enabled=False, murmur_enabled=True, move_seed=seed)
    w.llm = MockLLM(seed=7)
    w.lore_enabled = lore_on
    names = (["Victa", "Orvin"] + [f"Byst{i}" for i in range(N_BYSTANDERS)])
    for i, name in enumerate(names):
        a = Agent(f"s{i}", name, (i * 10.0, 0.0), "You are a working soul.",
                  [f"the well and the road, day {i}"], w.llm,
                  seed=1000 * seed + i, temperament=0.0, lifespan=10 ** 9)
        a.expect_enabled = True
        a.bond_enabled = True
        w.add(a)
    return w


def run(seed: int, lore_on: bool) -> dict:
    embed.use_jaccard_only(True)
    w = build(seed, lore_on)
    victim, offender = w.agents[0], w.agents[1]
    bond = victim.bonds.setdefault(offender.id, Bond())
    for t in range(1, TICKS + 1):
        phase = t % CYCLE
        if phase != 0 and phase % 3 == 0:      # the warm streak (rebuilds the expectation)
            expectation.appraise_conduct(victim, offender.id, offender.name, 0.5, t, bond)
        elif phase == 0:                        # the knife (re-fires the betrayal + the story)
            expectation.appraise_conduct(victim, offender.id, offender.name, -0.5, t, bond)
        w.advance()
    bystanders = w.agents[2:]
    off_exp = [b._conduct_expect.get(offender.id) for b in bystanders]
    innocent_exp = [abs(b._conduct_expect.get(w.agents[2].id, 0.0)) for b in bystanders[1:]]
    # claim 4: the reputation line reaches a bystander's SPEECH toward the offender
    voice = False
    for b in bystanders:
        if b._conduct_expect.get(offender.id, 0.0) < -0.2 and offender.id not in b.bonds:
            b._rng.random = lambda: 0.99
            b.last_heard_from, b.last_heard_name = offender.id, offender.name
            b.last_heard_text = "good morning"
            ctx, _, _ = b.prepare_speech()
            voice = "heard how" in ctx.bond_line
            break
    return {"off": off_exp, "innocent": innocent_exp, "voice": voice,
            "wounds": victim.bonds[offender.id].wounds}


def report(seeds, label: str):
    print(f"\n--- {label} ---")
    rows = []
    for seed in seeds:
        c = run(seed, lore_on=True)
        n = run(seed, lore_on=False)
        held = [e for e in c["off"] if e is not None]
        wary = sum(1 for e in held if e < -0.1)
        null_opinions = sum(1 for e in n["off"] if e is not None)
        consensus = (sum(1 for e in held if e < 0) / len(held)) if held else 0.0
        mean = statistics.fmean(held) if held else 0.0
        m = {"transmission": wary >= 3 and null_opinions == 0,
             "consensus": bool(held) and consensus >= 0.8 and mean < -0.1,
             "specificity": all(x < 0.1 for x in c["innocent"]),
             "voice": bool(c["voice"])}
        rows.append(m)
        print(f"seed {seed}: victim wounds {c['wounds']} | bystanders wary {wary}/6 "
              f"(null arm opinions: {null_opinions}) | consensus {consensus:.0%}, mean "
              f"{mean:+.2f} | innocent max |exp| "
              f"{max(c['innocent']) if c['innocent'] else 0:.2f} | voice: {c['voice']}")
        for k, lab in (("transmission", "1 transmission"), ("consensus", "2 consensus"),
                       ("specificity", "3 specificity"), ("voice", "4 voice")):
            print(f"    {lab:15s}: {'PASS' if m[k] else 'FAIL'}")
    print(f"\n  {label} tally:")
    for k, lab in (("transmission", "1 TRANSMISSION"), ("consensus", "2 CONSENSUS"),
                   ("specificity", "3 SPECIFICITY"), ("voice", "4 VOICE")):
        print(f"    {lab:15s}: {sum(1 for r in rows if r[k])}/{len(rows)}")
    return rows


def main() -> None:
    print(__doc__)
    report(TUNING_SEEDS, "TUNING seeds 11-15 (knobs may be tuned here; not the verdict)")
    held = report(HELDOUT_SEEDS, "HELD-OUT virgin seeds 21-25 (the verdict)")
    print("\n=== VERDICT (held-out; pre-registered: a claim passes at >= 4/5) ===")
    for k, lab in (("transmission", "1 TRANSMISSION"), ("consensus", "2 CONSENSUS"),
                   ("specificity", "3 SPECIFICITY"), ("voice", "4 VOICE")):
        cnt = sum(1 for r in held if r[k])
        print(f"  {lab:15s}: {cnt}/{len(held)} -> {'PASS' if cnt >= 4 else 'FAIL'}")
    print("\nHonest frame: a PASS means conduct travels as testimony on this substrate -- the town "
          "comes to be wary of someone most of it never met, per-subject and speakable. Whether the "
          "reputation is FAIR rides the same mutating channel as any legend, and that is a feature "
          "to observe, not a claim made here (§7 unchanged).")


if __name__ == "__main__":
    main()
