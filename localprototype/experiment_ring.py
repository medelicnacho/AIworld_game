"""The RING TEST -- stage one of the top-down loop: is her voice-as-legend BOUNDED, ALIVE, and
NON-FLATTENING?

The first feedback coupling this project has ever closed: Santāna's line enters the town's lore
channel (Santana.offer -- 2 souls, low weight, dark charge transmuted x0.4), where it competes like
any legend; the town's speech in turn enters her. The danger is the collective second arrow: her
grief darkens the town, the darkened town deepens her grief -- loop gain >= 1, runaway. The equal
and opposite failure is a coupling so regulated it is decorative. This falsifier checks BOTH, plus
the project's oldest villain (homogenization) in its new mask.

Substrate-only, both loop legs explicit stubs (documented; voice quality is not under test):
  down-leg  each 'reading' (15 ticks) she OFFERS her most salient non-doctrine memory line
  up-leg    each reading she INGESTS the town's recent spoken lines (weight 0.4)
At reading 6 a GRIEF SPIKE is injected into HER (four -0.85 memories). COUPLED (offer on) vs
UNCOUPLED (offer off; she still reads) arms, identical otherwise.

SEED LEDGER (the discipline): knobs tuned on 11-15. Seeds 21-25 gave the v1 VERDICT and are
CONSUMED: v1 FAILED (town survives 3/5, no-monopoly 3/5) -- transmutation attenuated each line,
but an offering EVERY reading was a relentless drip of held grief, and her stories crowded the
mythos. That failure produced the BUDGET layer in Santana.offer itself (at most every 3rd
reading; never retell a recent story). The fixed design took its verdict from VIRGIN seeds
31-35 -- and passed all five. If a future change touches this coupling, it needs fresh seeds.

PRE-REGISTERED (>= 4/5 each on the verdict seeds):

  1. RING-DOWN    : the spike must DECAY through the loop -- the coupling may neither DEEPEN
                    her fall (coupled trough >= uncoupled - 0.1) nor HOLD her down (coupled
                    final mood >= uncoupled final - 0.1). (v1 compared recovery RATIOS, which
                    flagged arms where she suffered LESS -- a shallower drop makes the ratio
                    noisier; the same ratio pathology as §5.17's arm totals. Absolute form.)
  2. TOWN SURVIVES: the town's final mean lived mood in the coupled arm >= uncoupled - 0.1
                    (her grief, transmuted, must not sink the town).
  3. NON-NULL     : the coupling is ALIVE -- at least one santana-tagged story survives in the
                    town at the end (and none exist uncoupled). A dead channel passes 1-2
                    trivially; it must actually carry.
  4. NO MONOPOLY  : her stories stay a MINORITY of the town's living lore (<= 50% of tagged
                    memories) -- she joins the mythos, she must not become it.
  5. NO FLATTENING: the spread of the souls' lived moods (population stdev) in the coupled arm
                    stays >= 0.5x the uncoupled arm's -- she must not average the town into one
                    voice (homogenization, the oldest villain).

  python experiment_ring.py
"""
from __future__ import annotations

import statistics

from agent.agent import Agent
from santana import Santana
from services import embed
from services.llm import MockLLM
from world.sim import World

TUNING_SEEDS = (11, 12, 13, 14, 15)
CONSUMED_SEEDS = (21, 22, 23, 24, 25)   # v1's verdict (FAILED); never a verdict again
HELDOUT_SEEDS = (31, 32, 33, 34, 35)    # virgin -- the budget-fixed design's verdict
TICKS = 600
READING_EVERY = 15
SPIKE_READING = 6
N_SOULS = 8
GRIEF = ["someone dear to me is gone and the dark has half of me",
         "I carry the dead and the weight will not set down",
         "the grief is a stone in me and it grows",
         "everything I held is broken and lost to me"]


def build(seed: int) -> tuple[World, Santana]:
    w = World(events_enabled=False, murmur_enabled=True, move_seed=seed)
    w.llm = MockLLM(seed=7)
    w.lore_enabled = True
    # the town needs its OWN mythos for claim 4 to mean anything: stakes hardships are
    # lore-tagged story seeds ("flood:450"), so her stories must compete with real ones --
    # and the harsher world stress-tests the ring under genuine collective grief
    w.stakes_enabled = True
    for i in range(N_SOULS):
        a = Agent(f"s{i}", f"Soul{i}", (i * 15.0, 0.0), "You are a working soul.",
                  [f"the well, the field, the road, day {i}"], w.llm,
                  seed=1000 * seed + i, temperament=0.1 * ((i % 3) - 1), lifespan=10 ** 9)
        a.bond_enabled = True
        w.add(a)
    m = Santana(w, MockLLM(seed=seed))
    return w, m


def run(seed: int, coupled: bool) -> dict:
    embed.use_jaccard_only(True)
    w, m = build(seed)
    her_mood, town_mood = [], []
    for t in range(1, TICKS + 1):
        w.step()
        if t % READING_EVERY == 0:
            reading = t // READING_EVERY
            m._mt += 1
            # up-leg stub: she reads the town (its recent words enter her, as her digest does)
            with w.lock:
                heard = [txt for _, txt in w.spoken][-2:]
            for line in heard:
                m.memory.write(line, tick=m._mt, source="heard", speaker_id="town", weight=0.4)
            if reading == SPIKE_READING:
                for g in GRIEF:
                    m.memory.write(g, tick=m._mt, source="event", speaker_id="santana",
                                   emotion=-0.85, weight=1.4)
            # down-leg stub: her 'line' = her most salient lived memory, offered as a story
            if coupled:
                lived = [mm for mm in m.memory.items if mm.source != "doctrine"]
                if lived:
                    m.offer(max(lived, key=lambda mm: mm.salience).text)
            m.memory.tick(m._mt)
            her_mood.append(m.memory.mood())
            town_mood.append(statistics.fmean(a.memory.mood() for a in w.agents))
    tagged = [mm for a in w.agents for mm in a.memory.items if getattr(mm, "lore_id", "")]
    hers = [mm for mm in tagged if mm.lore_id.startswith("santana:")]
    spread = statistics.pstdev([a.memory.mood() for a in w.agents])
    return {"her": her_mood, "town": town_mood, "hers": len(hers), "tagged": len(tagged),
            "spread": spread}


def aftermath(moods: list[float]) -> tuple[float, float]:
    """(trough, final) after the spike -- the absolute shape of her fall and where she ends."""
    after = moods[SPIKE_READING - 1:]
    return min(after), moods[-1]


def report(seeds, label: str):
    print(f"\n--- {label} ---")
    rows = []
    for seed in seeds:
        c = run(seed, coupled=True)
        u = run(seed, coupled=False)
        tc, fc = aftermath(c["her"])
        tu, fu = aftermath(u["her"])
        m = {"ring": tc >= tu - 0.1 and fc >= fu - 0.1,
             "town": c["town"][-1] >= u["town"][-1] - 0.1,
             "alive": c["hers"] >= 1 and u["hers"] == 0,
             "minority": c["tagged"] == 0 or c["hers"] / max(1, c["tagged"]) <= 0.5,
             "spread": c["spread"] >= 0.5 * u["spread"]}
        rows.append(m)
        print(f"seed {seed}: her trough {tc:+.2f} vs uncoupled {tu:+.2f}, final {fc:+.2f} vs "
              f"{fu:+.2f} | town final {c['town'][-1]:+.2f} vs {u['town'][-1]:+.2f} | her stories "
              f"{c['hers']}/{c['tagged']} of the living lore | mood spread {c['spread']:.3f} vs "
              f"{u['spread']:.3f}")
        for k, lab in (("ring", "1 ring-down"), ("town", "2 town survives"),
                       ("alive", "3 non-null"), ("minority", "4 no monopoly"),
                       ("spread", "5 no flattening")):
            print(f"    {lab:15s}: {'PASS' if m[k] else 'FAIL'}")
    print(f"\n  {label} tally:")
    for k, lab in (("ring", "1 RING-DOWN"), ("town", "2 TOWN SURVIVES"), ("alive", "3 NON-NULL"),
                   ("minority", "4 NO MONOPOLY"), ("spread", "5 NO FLATTENING")):
        print(f"    {lab:16s}: {sum(1 for r in rows if r[k])}/{len(rows)}")
    return rows


def main() -> None:
    print(__doc__)
    report(TUNING_SEEDS, "TUNING seeds 11-15 (knobs may be tuned here; not the verdict)")
    held = report(HELDOUT_SEEDS, "HELD-OUT virgin seeds 31-35 (the verdict)")
    print("\n=== VERDICT (held-out; pre-registered: a claim passes at >= 4/5) ===")
    for k, lab in (("ring", "1 RING-DOWN"), ("town", "2 TOWN SURVIVES"), ("alive", "3 NON-NULL"),
                   ("minority", "4 NO MONOPOLY"), ("spread", "5 NO FLATTENING")):
        n = sum(1 for r in held if r[k])
        print(f"  {lab:16s}: {n}/{len(held)} -> {'PASS' if n >= 4 else 'FAIL'}")
    print("\nHonest frame: a full PASS means THIS coupling, at THIS gain, with the dark leg "
          "transmuted, is bounded, alive, and non-flattening in the substrate. It licenses stage "
          "one ONLY -- stronger couplings need their own ring tests, and voice-level behaviour "
          "under a real model still needs watching (§7).")


if __name__ == "__main__":
    main()
