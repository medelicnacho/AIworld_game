"""THE PROVENANCE PASS (C2 + C14 + S2): one pass over one store, three findings.

Promoted from queued to URGENT by listening round 6 (FINDINGS §5.18): the deepseek voice
confabulated Cludel's biography -- she needs to KNOW, at recall, what she lived, what she
was told, what she dreamt, and what has worn past knowing. The mechanism is built in
agent/memory.py (source_tag / attributed / mineness); this file is its falsifier.

PRE-REGISTERED CLAIMS (all deterministic substrate, no model; scripts/stats.py error bars):

  P1 (C2, confidence): the hedge tracks GROUND-TRUTH distortion -- hedged memories have
     drifted farther from their original text (Jaccard) than unhedged ones, beating a
     shuffled-hedge null (95th pct) -- and the hedge is NOT a mood read (emotion gap small).
     Non-trivial because drift also comes the repair path and hedges could misfire.
  P2 (C14a, source): source_tag accuracy against true provenance beats a shuffled-provenance
     null by >= +0.30, every seed (paired per-seed).
  P3 (C14b, the leak): under retelling pressure, source-confusion OCCURS (>= 1 story/dream
     ends tagged 'mine'/'witnessed' -- emergent false memory), stays a LEAK not a flood
     (pooled rate <= 0.5 of story+dream items), and is 100% AUDITABLE end-to-end (every
     confused story's lore_id still names the event it descends from).
  P4 (S2, ownership): ablating mineness on a stratified half of self-memories changes the
     RENDERING on exactly that half while recall RANKING is untouched; a sham ablation
     changes nothing; and an unowned wound still bends mood() while vanishing from
     recall_self() -- the behaviour/report dissociation.

Discipline: tuning seeds 11-15 (default; never a verdict). The VERDICT runs on virgin
held-out seeds (--heldout), untouched during design. CONSUMED: 41-45 -- spent on the v1
discriminator (mutation weight 0.35; P1 FAIL 4/5, P2-P4 PASS), before an existing C2 test
caught v1 conflating content doubt with source doubt. v2 rebalanced (0.2/0.9); its verdict
comes from 51-55, and 41-45 are never a verdict again.

Run:  python experiment_provenance.py             # tuning read
      python experiment_provenance.py --heldout   # THE VERDICT (virgin seeds 51-55)
"""
from __future__ import annotations

import argparse
import random
import statistics
import sys

from agent.memory import MemoryStore, _similarity, attributed, source_tag
from scripts.stats import paired, summary, verdict

TICKS = 400
REINFORCE_EVERY = 26          # rarely enough that the mutation window (age >= 20) opens
RETELL_EVERY = 30             # the adopted story is retold in one's OWN voice this often

# the corpus leans on BLUR-able words (deep/cold/water/fire/light/night...) so mutation
# genuinely blurs; lines are mutually distinct (Jaccard < 0.6) so nothing cross-merges
# except what the protocol intends.
WITNESSED = [
    ("heard", "the cold water rose in the night and took the low bridge"),
    ("event", "smoke hung over the west field after the fire"),
    ("heard", "Mara said the harvest cart broke its wheel on the hill"),
    ("heard", "a light moved across the deep water past the docks"),
    ("event", "the night watch heard wings over the granary"),
    ("user", "Toll paid his debt at the market in full"),
    ("heard", "the river ran heavier after the long rain"),
    ("event", "Cael came back with empty nets and a torn line"),
]
SELF = [
    "I mended the fence by the north gate before the rain",
    "I am slower this season and it worries me",
    "I told Vesper the truth about the ledger",
    "I keep the morning fire going for the children",
    "I walked the ridge path alone and felt small",
    "I promised Juno help with the flock come winter",
]
STORIES = [
    ("ev:1", "they say a fisher drowned at the weir the year the water rose"),
    ("ev:2", "they say the old brewer hid coin under the mill floor"),
    ("ev:3", "they say a light walks the ridge on the last night of harvest"),
]
DREAMS = [
    "I dreamed of deep water circling the house",
    "I dreamed the fire spoke with my father's voice",
]


def run_store(seed: int):
    """Live one store through the protocol. Returns (store, truth) where truth maps
    id(memory) -> (true_class, original_text) -- the experimenter's ledger, never the self's."""
    s = MemoryStore(seed=seed)
    truth: dict[int, tuple[str, str]] = {}
    for src, text in WITNESSED:
        truth[id(s.write(text, tick=0, source=src))] = ("witnessed", text)
    for text in SELF:
        truth[id(s.write(text, tick=0, source="self"))] = ("mine", text)
    for lid, text in STORIES:
        truth[id(s.write(text, tick=0, source="lore", lore_id=lid))] = ("story", text)
    for text in DREAMS:
        truth[id(s.write(text, tick=0, source="dream"))] = ("dream", text)

    order = list(s.items)                       # rotation for staggered reinforcement
    for t in range(1, TICKS + 1):
        s.tick(t)
        # staggered rehearsal: item i is re-touched every REINFORCE_EVERY ticks, offset by
        # 3*i -- often enough to LIVE (salience never nears the forget floor), rarely enough
        # that the mutation window (age >= 20 since last touch) opens for ~a quarter of each
        # cycle. Expected ~1.5 mutations per item over the run: a real mix of worn and clean.
        for i, m in enumerate(order):
            if m in s.items and (t - 3 * i) % REINFORCE_EVERY == 0:
                s.write(m.text, tick=t, source=m.source, lore_id=getattr(m, "lore_id", ""))
        if t % RETELL_EVERY == 0:
            # the confusion pathway: the FIRST story is retold in one's own voice --
            # the words merge home, and the frame smears a little each time
            adopted = next((x for x in s.items if getattr(x, "lore_id", "") == "ev:1"), None)
            if adopted is not None:
                s.write(adopted.text, tick=t, source="self")
    return s, truth


def hedge_level(m) -> int:
    return 2 if m.mutation_count >= 3 else (1 if m.mutation_count >= 1 else 0)


def claim_p1(stores) -> tuple[list[float], list[float], list[float]]:
    """Per seed: (drift gap hedged-vs-not, its shuffled 95th pct, emotion gap)."""
    gaps, null95s, emo_gaps = [], [], []
    for s, truth in stores:
        alive = [m for m in s.items if id(m) in truth]
        drift = {id(m): 1.0 - _similarity(truth[id(m)][1], m.text) for m in alive}
        hedged_d = [drift[id(m)] for m in alive if hedge_level(m) >= 1]
        clean_d = [drift[id(m)] for m in alive if hedge_level(m) == 0]
        if not hedged_d or not clean_d:
            gaps.append(0.0); null95s.append(0.0); emo_gaps.append(0.0)
            continue
        gaps.append(statistics.fmean(hedged_d) - statistics.fmean(clean_d))
        rng = random.Random(1000 + len(alive))
        labels = [hedge_level(m) >= 1 for m in alive]
        vals = [drift[id(m)] for m in alive]
        nulls = []
        for _ in range(200):
            rng.shuffle(labels)
            h = [v for v, L in zip(vals, labels) if L]
            c = [v for v, L in zip(vals, labels) if not L]
            nulls.append((statistics.fmean(h) if h else 0.0) - (statistics.fmean(c) if c else 0.0))
        null95s.append(sorted(nulls)[int(0.95 * len(nulls))])
        emo_h = [abs(m.emotion) for m in alive if hedge_level(m) >= 1]
        emo_c = [abs(m.emotion) for m in alive if hedge_level(m) == 0]
        emo_gaps.append(abs(statistics.fmean(emo_h) - statistics.fmean(emo_c)))
    return gaps, null95s, emo_gaps


def claim_p2(stores) -> tuple[list[float], list[float]]:
    """Per seed: (real tag accuracy, shuffled-provenance accuracy)."""
    real_accs, shuf_accs = [], []
    for s, truth in stores:
        alive = [m for m in s.items if id(m) in truth]
        real_accs.append(statistics.fmean(
            1.0 if source_tag(m) == truth[id(m)][0] else 0.0 for m in alive))
        rng = random.Random(2000)
        prov = [(m.source, getattr(m, "lore_id", "")) for m in alive]
        accs = []
        for _ in range(200):
            rng.shuffle(prov)
            correct = 0
            for m, (src, lid) in zip(alive, prov):
                keep_src, keep_lid = m.source, m.lore_id
                m.source, m.lore_id = src, lid
                correct += 1 if source_tag(m) == truth[id(m)][0] else 0
                m.source, m.lore_id = keep_src, keep_lid
            accs.append(correct / len(alive))
        shuf_accs.append(statistics.fmean(accs))
    return real_accs, shuf_accs


def claim_p3(stores):
    """Pooled: (n confusions, n story+dream items, all_auditable, cases)."""
    confusions, pool, cases = 0, 0, []
    auditable = True
    for s, truth in stores:
        for m in s.items:
            if id(m) not in truth:
                continue
            cls = truth[id(m)][0]
            if cls in ("story", "dream"):
                pool += 1
                if source_tag(m) in ("mine", "witnessed"):
                    confusions += 1
                    origin = getattr(m, "lore_id", "") or ("harness:dream" if cls == "dream" else "")
                    cases.append((m.text[:60], cls, source_tag(m), origin or "LOST"))
                    if cls == "story" and not getattr(m, "lore_id", ""):
                        auditable = False
    return confusions, pool, auditable, cases


def claim_p4(seed: int) -> dict:
    """The S2 ablation, one seed -> dict of booleans (all must hold)."""
    s = MemoryStore(seed=seed)
    texts = [f"I remember the {w} season and what it asked of me"
             for w in ("first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth")]
    for i, t in enumerate(texts):
        s.write(t, tick=i, source="self")
    for t in range(8, 40):
        s.tick(t)
    before_rank = [m.text for m in s.recall(k=8)]
    before_render = {id(m): attributed(m) for m in s.items}
    by_sal = sorted(s.items, key=lambda m: m.salience, reverse=True)
    ablate = set(id(m) for m in by_sal[::2])            # stratified: every other rank
    for m in s.items:
        if id(m) in ablate:
            m.mineness = 0.0
    after_rank = [m.text for m in s.recall(k=8)]
    changed = {id(m) for m in s.items if attributed(m) != before_render[id(m)]}
    sham_before = {id(m): attributed(m) for m in s.items}
    for m in s.items:                                    # sham: touch the OTHER half with 1.0
        if id(m) not in ablate:
            m.mineness = 1.0
    sham_changed = any(attributed(m) != sham_before[id(m)] for m in s.items)
    # dissociation: an unowned wound bends mood, vanishes from the story
    base_mood = s.mood()
    wound = s.write("the flood took what I had built", tick=41, source="self",
                    emotion=-0.9, mineness=0.0)
    return {
        "ranking_intact": before_rank == after_rank,
        "render_exact": changed == ablate,
        "sham_silent": not sham_changed,
        "wound_bends_mood": s.mood() < base_mood,
        "wound_unclaimed": all(m is not wound for m in s.recall_self(k=10)),
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--heldout", action="store_true",
                   help="run the VERDICT on virgin seeds 51-55 (tuning default: 11-15; "
                        "41-45 were consumed by the v1 discriminator and are never a "
                        "verdict again)")
    args = p.parse_args()
    seeds = list(range(51, 56)) if args.heldout else list(range(11, 16))
    mode = "VERDICT (held-out, virgin)" if args.heldout else "tuning (NEVER a verdict)"
    print(f"\n=== The provenance pass: C2 + C14 + S2 ({mode}; seeds {seeds[0]}..{seeds[-1]}) ===")

    stores = [run_store(s) for s in seeds]
    ok = []

    gaps, null95s, emo_gaps = claim_p1(stores)
    cmp1 = paired(gaps, null95s)
    print("\nP1 (C2): hedge tracks ground-truth drift, beating the shuffled null per seed")
    print(verdict("drift gap (hedged - clean) vs its null 95th pct", cmp1))
    print(f"  emotion gap |hedged-clean| (must stay small -- the hedge is not a mood read): "
          f"{summary(emo_gaps)}")
    p1 = (all(g > n for g, n in zip(gaps, null95s)) and statistics.fmean(emo_gaps) < 0.2)
    ok.append(("P1", p1))
    print(f"  -> beats null {sum(g > n for g, n in zip(gaps, null95s))}/{len(seeds)} seeds, "
          f"mood-blind: {'PASS' if p1 else 'FAIL'}")

    real, shuf = claim_p2(stores)
    cmp2 = paired(real, shuf)
    print("\nP2 (C14a): source tags track true provenance vs shuffled-provenance null")
    print(verdict("accuracy real - shuffled", cmp2))
    p2 = cmp2.effect.mean >= 0.30 and cmp2.sign[0] == cmp2.sign[1]
    ok.append(("P2", p2))
    print(f"  -> gap >= +0.30 with all seeds positive: {'PASS' if p2 else 'FAIL'}")

    confusions, pool, auditable, cases = claim_p3(stores)
    rate = confusions / pool if pool else 0.0
    print(f"\nP3 (C14b): the leak -- {confusions} of {pool} story/dream items ended believed "
          f"({rate:.0%}); every confused story auditable: {auditable}")
    for text, cls, tag, origin in cases[:6]:
        print(f"    '{text}...' was {cls.upper()}, now presents as {tag.upper()} -- "
              f"true origin: {origin}")
    p3 = confusions >= 1 and rate <= 0.5 and auditable
    ok.append(("P3", p3))
    print(f"  -> exists, stays a leak (<= 50%), 100% traceable: {'PASS' if p3 else 'FAIL'}")

    p4_rows = [claim_p4(s) for s in seeds]
    keys = list(p4_rows[0])
    print("\nP4 (S2): the ownership ablation, per seed")
    for k in keys:
        wins = sum(1 for r in p4_rows if r[k])
        print(f"    {k:18} {wins}/{len(seeds)}")
    p4 = all(all(r.values()) for r in p4_rows)
    ok.append(("P4", p4))
    print(f"  -> all five properties, all seeds: {'PASS' if p4 else 'FAIL'}")

    print(f"\n=== {mode}: " + "  ".join(f"{k} {'PASS' if v else 'FAIL'}" for k, v in ok) + " ===")
    if not args.heldout:
        print("(tuning seeds -- design freely here, but the verdict only ever comes from "
              "--heldout, seeds 51-55, untouched during design; 41-45 are consumed)")
    sys.exit(0 if all(v for _, v in ok) else 1)


if __name__ == "__main__":
    main()
