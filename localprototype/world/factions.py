"""factions.py -- seeing the fellowships: emergent opinion-blocs as first-class groups.

The substrate already GROWS factions (bounded-confidence opinion dynamics -- validated:
history-dependent blocs, not label-homophily) and they already TAKE TERRITORY (V2,
5/5). What the ecology game needs is to SEE them: a pure read that clusters souls by
opinion alignment, names each bloc by the ground it holds, and picks the soul the
others would actually follow. Nothing here mutates a soul; factions remain something
the town DOES, not something it is assigned."""
from __future__ import annotations

from agent.agent import _cosine as opinion_alignment

ALIGN_AT = 0.45          # alignment above this makes two souls same-bloc candidates
LONER = -1               # faction id for souls with no opinion vector / no bloc


class _Find:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, i):
        while self.p[i] != i:
            self.p[i] = self.p[self.p[i]]
            i = self.p[i]
        return i

    def union(self, i, j):
        self.p[self.find(i)] = self.find(j)


def factions_of(world) -> dict:
    """soul_id -> faction index (stable within a call; LONER for the unaligned).
    Pure read; call under the world lock."""
    souls = [a for a in world.agents if getattr(a, "belief_vec", None) is not None]
    uf = _Find(len(souls))
    for i in range(len(souls)):
        for j in range(i + 1, len(souls)):
            if opinion_alignment(souls[i].belief_vec, souls[j].belief_vec) >= ALIGN_AT:
                uf.union(i, j)
    roots: dict = {}
    out = {}
    for i, a in enumerate(souls):
        r = uf.find(i)
        if r not in roots:
            roots[r] = len(roots)
        out[a.id] = roots[r]
    for a in world.agents:
        out.setdefault(a.id, LONER)
    return out


def members(world, fid: int, mapping: dict | None = None) -> list:
    m = mapping or factions_of(world)
    return [a for a in world.agents if m.get(a.id) == fid]


def leader_of(world, fid: int, mapping: dict | None = None):
    """The soul the bloc would actually follow: the member most trusted BY its own --
    highest incoming trust from bloc-mates. None for an empty bloc."""
    crew = members(world, fid, mapping)
    if not crew:
        return None
    ids = {a.id for a in crew}

    def incoming(a):
        return sum(b.bonds[a.id].trust for b in crew
                   if a.id in getattr(b, "bonds", {}) and b.id != a.id)
    return max(crew, key=lambda a: (incoming(a), a.id in ids, a.id))


def home_region(world, fid: int, mapping: dict | None = None) -> int | None:
    """Where the bloc actually lives: the region holding the plurality of its members
    (V2: fellowships take territory -- this reads the territory they took)."""
    if not getattr(world, "regions_enabled", False) or world.regions is None:
        return None
    crew = members(world, fid, mapping)
    if not crew:
        return None
    counts: dict = {}
    for a in crew:
        i = world.regions.index(a.position)
        counts[i] = counts.get(i, 0) + 1
    return max(counts, key=lambda k: (counts[k], -k))


def banner_of(world, fid: int, mapping: dict | None = None) -> str:
    """A speakable name: the folk of the ground they hold."""
    home = home_region(world, fid, mapping)
    if home is None:
        return f"bloc {fid}"
    return f"the folk of {world.regions.names[home]}"
