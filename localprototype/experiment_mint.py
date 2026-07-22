"""MINTED SOULS: can a village founded without a model actually live?

gameworld/PLAN.md §3 consequence 3: "genesis.generate_character is an LLM call -- unusable
when the world mints villages as you walk." A world streaming settlements from
hash(worldSeed, chunkCoords) needs souls in microseconds, thousands of times, offline.

An LLM-free path existed only as generate_character's EXCEPTION HANDLER, and measured, it
could not found villages: names from a 16-entry pool (a second village already collides),
every inner voice 6 lines sampled from the same 10, and `aim` empty so telos has nothing to
tend. genesis.mint() composes instead of sampling.

The danger this experiment exists for: a village of DEGENERATE souls is worse than no
village. Cheap and deterministic is easy; cheap, deterministic AND ALIVE is the claim.

PRE-REGISTERED (3 seeds; a claim passes at 3/3). The reference arm is a town founded the
authored way (MockLLM through generate_character) -- so "viable" means "behaves like the
souls the validated experiments were run on", not "behaves like something".

  M1 DETERMINISTIC. The same seed yields a bit-identical soul, every time. Without this a
     streamed world cannot re-derive a village it unloaded, and PLAN's dirty-region
     persistence (store nothing that is re-derivable) has no ground to stand on.

  M2 DISTINCT. Across 2000 souls: names collide rarely, and inner voices are near-all
     unique. The failure this catches is a hamlet of clones.

  M3 ALIVE -- the claim. A minted town, run the same ticks as an authored town, forms
     BONDS, FACTIONS and MEMORY at comparable levels (within half the authored arm on
     each). Souls that never bond or never cluster are scenery, not a substrate.

  M4 CHEAP. Under 100us per soul, so a village is minted inside a frame.

  python3 -u experiment_mint.py

VERDICT (seeds 11-13): M1 3/3, M2 3/3, M3 2/3, M4 3/3. Fails the 3/3-on-all bar.

M1/M2/M4 are clean and are what mint() was built for: bit-identical per seed, 95%+ distinct
names and 100% distinct voices across 2000 souls, ~12us each.

M3 AS SPECIFIED IS UNINFORMATIVE AND IS RECORDED AS SUCH RATHER THAN RE-SPECIFIED. It
compares bond counts that came out at 0-3 in BOTH arms -- 24 souls over 1200 ticks with one
speaker per speech turn barely interact at all, so the claim compared noise to noise and its
2/3 means nothing in either direction. A useful version needs a town that actually talks
(more speech turns, tighter hearing range), pre-registered before running.

WHAT THE RUN DID REVEAL, from the column that was not noise -- factions: minted 15-17 of 24
souls, authored 1. Minted souls are TOO DISTINCT to cluster on their own. Composed lines
give near-orthogonal belief vectors (mean lexical overlap 0.386 vs the authored arm's
0.484), so nearly every soul is its own faction and §5.6's emergence has nothing to work
with. This is stance.py's already-recorded problem arriving from a new direction: "grounded
trade-distinct souls start at mean cosine ~0 and ~13% of pairs clear the engagement bar".

THE DESIGN CONSEQUENCE, which is the useful output of this experiment: mint() gives you a
PERSON, and a VILLAGE still has to seed a SHARED VIEW on top -- exactly what
evolution._found_souls already does (one base belief vector per settlement, plus per-soul
noise: "a lean, never a copy"). A streamed world must do the same per chunk: mint the
people, then hand the settlement its one view. Minting alone would produce hamlets of
mutual strangers who never form a faction, which is the opposite of the failure it was
guarding against.
"""
from __future__ import annotations

import random
import statistics as st
import time

from agent.agent import Agent
from agent.genesis import endow_faculties, generate_character, mint, seed_agent
from services.llm import MockLLM
from world.factions import factions_of

TICKS = 1200
N = 24
SEEDS = (11, 12, 13)


def _town(seed: int, minted: bool):
    """A town founded either way, then run identically. Only the founding differs."""
    from world.sim import World
    from services import embed as _embed
    _embed.use_jaccard_only(True)
    w = World(rebirth_enabled=False, events_enabled=False, move_seed=seed)
    w.llm = MockLLM(seed=seed)
    w.move_enabled = True
    rng = random.Random(seed)
    taken: set = set()
    for i in range(N):
        ch = mint(rng, taken=taken) if minted else generate_character(w.llm, rng)
        taken.add(ch.name)
        a = Agent(f"s{i}", ch.name, (rng.uniform(0, 400), rng.uniform(0, 400)),
                  f"You are {ch.name} the {ch.role or 'villager'}.", list(ch.lines),
                  w.llm, seed=i, temperament=ch.temperament, lifespan=10 ** 9)
        endow_faculties(a, a._rng)
        seed_agent(a, ch, tick=0)
        a.bond_enabled = True
        w.add(a)
    for t in range(1, TICKS + 1):
        w.step(speak=False)
        if t % 7 == 0:
            w.speak_turn()
    return w


def _read(w) -> dict:
    bonds = sum(len(getattr(a, "bonds", {}) or {}) for a in w.agents)
    warm = sum(1 for a in w.agents for b in (getattr(a, "bonds", {}) or {}).values()
               if getattr(b, "trust", 0.0) > 0.15)
    items = sum(len(a.memory.items) for a in w.agents)
    facs = {f for f in factions_of(w).values() if f >= 0}
    return {"bonds": bonds, "warm": warm, "items": items, "factions": len(facs)}


def main() -> None:
    print(f"  {TICKS} ticks, {N} souls, seeds {SEEDS}\n")
    print(f"  {'seed':<6}{'arm':<10}{'bonds':>7}{'warm':>7}{'items':>8}{'factions':>10}")
    m1 = m2 = m3 = m4 = 0
    for sd in SEEDS:
        # M1 determinism
        a, b = mint(random.Random(sd)), mint(random.Random(sd))
        ok1 = (a.name, a.role, a.temperament, tuple(a.lines), a.aim) == \
              (b.name, b.role, b.temperament, tuple(b.lines), b.aim)
        # M2 distinctness + M4 cost
        rng = random.Random(sd)
        t0 = time.perf_counter()
        souls = [mint(rng) for _ in range(2000)]
        per = (time.perf_counter() - t0) / 2000 * 1e6
        names = len({s.name for s in souls}) / 2000
        voices = len({tuple(s.lines) for s in souls}) / 2000
        ok2 = names > 0.90 and voices > 0.90
        ok4 = per < 100.0
        # M3 alive, against the authored arm
        mt, au = _read(_town(sd, True)), _read(_town(sd, False))
        for label, r in (("minted", mt), ("authored", au)):
            print(f"  {sd:<6}{label:<10}{r['bonds']:>7}{r['warm']:>7}{r['items']:>8}"
                  f"{r['factions']:>10}")
        ok3 = all(mt[k] >= 0.5 * au[k] for k in ("bonds", "warm", "items"))
        m1 += ok1
        m2 += ok2
        m3 += ok3
        m4 += ok4
        print(f"        -> M1 deterministic {'YES' if ok1 else 'no '}  "
              f"M2 distinct {'YES' if ok2 else 'no '} (names {names:.1%}, voices {voices:.1%})  "
              f"M3 alive {'YES' if ok3 else 'no '}  M4 cheap {'YES' if ok4 else 'no '} "
              f"({per:.0f}us)\n")
    n = len(SEEDS)
    print(f"  M1 DETERMINISTIC : {m1}/{n}")
    print(f"  M2 DISTINCT      : {m2}/{n}")
    print(f"  M3 ALIVE         : {m3}/{n}   (vs an authored town, the reference arm)")
    print(f"  M4 CHEAP         : {m4}/{n}")
    ok = m1 == n and m2 == n and m3 == n and m4 == n
    print(f"\n  VERDICT: {'MINTED VILLAGES LIVE' if ok else 'did NOT show the signature'}")


if __name__ == "__main__":
    main()
