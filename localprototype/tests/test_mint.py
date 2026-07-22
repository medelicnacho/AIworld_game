"""Tests for seeded, model-free soul minting (agent.genesis.mint).

gameworld/PLAN.md §3 consequence 3: a world that streams settlements from
hash(worldSeed, chunkCoords) cannot wait on an LLM. The path that existed was
generate_character's EXCEPTION HANDLER, and it could not found villages -- names from a
16-entry pool, every voice 6 lines drawn from the same 10, and an EMPTY aim.
"""

import random

from agent.genesis import NAMES, SEED_CONCEPTS, _THEMES, mint


def test_same_seed_gives_a_bit_identical_soul():
    """Without this a streamed world cannot re-derive a village it unloaded, and the
    dirty-region persistence plan (store nothing re-derivable) has no ground."""
    a, b = mint(random.Random(42)), mint(random.Random(42))
    assert (a.name, a.role, a.task, a.temperament, tuple(a.lines), a.conviction, a.aim) == \
           (b.name, b.role, b.task, b.temperament, tuple(b.lines), b.conviction, b.aim)


def test_different_seeds_give_different_souls():
    assert mint(random.Random(1)).name != mint(random.Random(2)).name


def test_names_are_coined_not_drawn_from_the_16_entry_pool():
    """The old path drew from NAMES (16), so a second village already collided."""
    rng = random.Random(0)
    names = [mint(rng).name for _ in range(300)]
    assert len(set(names)) > 270              # coined, effectively unbounded
    assert sum(1 for n in names if n in NAMES) < 30


def test_every_soul_has_an_aim():
    """The old fallback left aim EMPTY, so telos -- the faculty that gives a soul a
    future to tend -- had nothing to tend."""
    rng = random.Random(3)
    assert all(mint(rng).aim for _ in range(200))


def test_voices_are_composed_not_sampled_from_ten_lines():
    """The failure this catches is a hamlet of clones: the old path gave every soul 6
    lines out of the same 10."""
    rng = random.Random(4)
    voices = [tuple(mint(rng).lines) for _ in range(300)]
    assert len(set(voices)) > 290
    # and a soul's lines carry ITS OWN trade and business, not just shared themes
    rng = random.Random(9)
    s = mint(rng)
    assert any(s.role in ln or s.task in ln for ln in s.lines)


def test_a_soul_has_a_conviction_and_it_is_one_of_its_own_lines():
    rng = random.Random(6)
    for _ in range(50):
        s = mint(rng)
        assert s.conviction and s.conviction in s.lines


def test_taken_names_are_avoided():
    rng = random.Random(8)
    first = mint(rng)
    for _ in range(20):
        assert mint(rng, taken={first.name}).name != first.name


def test_minting_is_cheap_enough_to_found_a_village_in_a_frame():
    import time
    rng = random.Random(0)
    mint(rng)                                  # warm
    t0 = time.perf_counter()
    for _ in range(500):
        mint(rng)
    per_us = (time.perf_counter() - t0) / 500 * 1e6
    assert per_us < 200.0, per_us              # generous; measured ~12us
