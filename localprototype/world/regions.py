"""regions.py -- the land itself: rich valleys, harsh ridges, and something to fight over.

The scale probes proved it twice, the hard way (EVOLUTION.md scale addendum): selection
needs GRADED, HETEROGENEOUS scarcity. A uniform world's famine is either rescued by
mutual aid or kills by lottery; the differential lives only where some ground is kind
and some is cruel. Regions are that geometry -- and they are also the ecology game's
first cause: a faction's territory (V2: fellowships take territory, 5/5) becomes a
faction's FOOD, and a lean ridge beside a fat valley is a war waiting for a reason.

A world with `regions_enabled` splits its bounds into a COLS x ROWS grid. Each region
carries its own commons pool and its own yield: labour done standing in a region feeds
THAT region's pool, scaled by its soil; hunger draws on the pool where you stand. The
old single `world.commons` float stays untouched for every world that never turns this
on (THE RULE: snapshot-compat defaults; nothing changes for anyone who didn't ask)."""
from __future__ import annotations

import random

COLS, ROWS = 3, 2
# soils from kind to cruel; shuffled per world so no seed learns "north is rich"
SOILS = (1.3, 1.15, 1.0, 0.85, 0.7, 0.5)
START_POOL = 2.0

_NAMES = ("vale", "meadow", "heath", "moor", "ridge", "crag",
          # the larger pool, for the big civ grids -- still ranked kind to cruel
          "dale", "lea", "combe", "glen", "holt", "shaw",
          "down", "wold", "fen", "marsh", "hollow", "carse",
          "brae", "scarp", "tor", "fell", "barrens", "waste")


class Regions:
    """The land: per-region commons pools and yields. Pure data + geometry.

    The grid is per-instance now (the civ arena wants 6x4 on a 3600x2400 map), but
    the default 3x2 world is byte-identical to what every validated snapshot holds:
    the exact six SOILS, the exact six names, the same shuffle off the same seed."""

    def __init__(self, bounds=(900.0, 600.0), seed: int = 0,
                 cols: int = COLS, rows: int = ROWS):
        rng = random.Random(seed)
        self.bounds = bounds
        self.cols, self.rows = cols, rows
        n = cols * rows
        if n == len(SOILS):
            soils = list(SOILS)                      # the canonical six, untouched
        elif n == 1:
            soils = [1.0]
        else:
            lo, hi = min(SOILS), max(SOILS)
            soils = [hi - (hi - lo) * i / (n - 1) for i in range(n)]
        rng.shuffle(soils)
        self.yields = soils                          # index -> soil multiplier
        self.pools = [START_POOL] * n                # index -> that region's commons
        # names ordered by kindness of soil, so "the vale" is always the fattest land
        order = sorted(range(len(soils)), key=lambda i: -soils[i])
        self.names = [""] * len(soils)
        for rank, idx in enumerate(order):
            self.names[idx] = (f"the {_NAMES[rank]}" if rank < len(_NAMES)
                               else f"field {rank + 1}")

    def __setstate__(self, state):
        # a land pickled before the grid was per-instance wakes as the 3x2 it was
        self.__dict__.update(state)
        self.__dict__.setdefault("cols", COLS)
        self.__dict__.setdefault("rows", ROWS)

    def index(self, pos) -> int:
        w, h = self.bounds
        c = min(self.cols - 1, max(0, int(pos[0] / (w / self.cols))))
        r = min(self.rows - 1, max(0, int(pos[1] / (h / self.rows))))
        return r * self.cols + c

    def centre(self, i) -> tuple:
        """World-coord centre of region i (the resettlement + guard geometry)."""
        rw, rh = self.bounds[0] / self.cols, self.bounds[1] / self.rows
        return ((i % self.cols) + 0.5) * rw, ((i // self.cols) + 0.5) * rh

    def name_of(self, pos) -> str:
        return self.names[self.index(pos)]

    def total(self) -> float:
        return sum(self.pools)


# --- the stakes layer's routing: one commons, or the land's many ------------------------

def pool_level(world, agent) -> float:
    """How much shared food this soul can SEE from where it stands."""
    if getattr(world, "regions_enabled", False) and world.regions is not None:
        return world.regions.pools[world.regions.index(agent.position)]
    return world.commons


def pool_add(world, agent, amount: float) -> None:
    """Labour lands where the labourer stands, scaled by that ground's soil."""
    if getattr(world, "regions_enabled", False) and world.regions is not None:
        i = world.regions.index(agent.position)
        world.regions.pools[i] += amount * world.regions.yields[i]
    else:
        world.commons += amount


def pool_take(world, agent, amount: float) -> float:
    """Draw from the pool where you stand; returns what was actually taken."""
    if getattr(world, "regions_enabled", False) and world.regions is not None:
        i = world.regions.index(agent.position)
        take = min(max(0.0, world.regions.pools[i]), amount)
        world.regions.pools[i] -= take
        return take
    take = min(max(0.0, world.commons), amount)
    world.commons -= take
    return take


def pool_scale_all(world, factor: float) -> None:
    """A hardship's bite on the granaries -- every pool, or the one float."""
    if getattr(world, "regions_enabled", False) and world.regions is not None:
        world.regions.pools = [max(0.0, p * factor) for p in world.regions.pools]
    else:
        world.commons = max(0.0, world.commons * factor)
