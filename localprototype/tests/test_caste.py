"""Tests for the two castes + the mating system (CIV_ARENA_PLAN.md).

Pinned, welfare first: breeders are NEVER mustered on any side of a war and never
fall in one; a breeder never brawls -- never confronts, is never a valid target,
never a casualty -- and is never harmed by mating (pairing only warms bonds);
allegiance.decide refuses danger for the caste before anything else is read.
Then the engine: mating produces ONE child whose genome is a blend of BOTH parents
(uniform crossover + one mutation), whose caste is one of the two and ~50/50 over
many births; a warrior that reaches a rival's hearth grudges THE RIVAL (never the
breeder); the arena land (Regions cols=6, rows=4) has 24 distinct-named regions
while the classic 3x2 stays byte-identical; and the camera's clamp contract holds.
"""

import random

from agent import allegiance
from agent.agent import WAR_THRESHOLD, Agent
from agent.bond import Bond
from agent.genome import Genome
from services.llm import MockLLM
from world import mating
from world import regions as R
from world import skirmish
from world import war
from world.sim import World


def _soul(w, sid, pos, caste="warrior", seed=None, bold=0.9):
    a = Agent(sid, sid.upper(), pos, f"You are {sid}.", ["the well"], w.llm,
              seed=seed if seed is not None else abs(hash(sid)) % 1000,
              temperament=0.0, lifespan=10 ** 6)
    a.bond_enabled = True
    a.boldness = bold
    a.caste = caste
    w.add(a)
    return a


def _world(seed=5):
    w = World(events_enabled=False)
    w.llm = MockLLM(seed=7)
    w._rng = random.Random(seed)
    return w


# --- welfare: the caste gates ---------------------------------------------------------

def test_breeders_are_never_mustered_in_war():
    """A raid raises its party and its defence from WARRIORS only: a breeder on
    either side -- however bold, however trusted -- keeps the hearth, and so can
    never fall in a war."""
    w = _world()
    w.regions_enabled = True
    w.regions = R.Regions(seed=1)
    w.war_enabled = True
    rich = max(range(6), key=lambda i: w.regions.yields[i])
    poor = min(range(6), key=lambda i: w.regions.yields[i])
    cx = lambda i: ((i % R.COLS) * 300 + 150.0, (i // R.COLS) * 300 + 150.0)
    atk = [_soul(w, f"k{i}", cx(poor), caste="breeder" if i == 1 else "warrior")
           for i in range(4)]
    dfd = [_soul(w, f"v{i}", cx(rich), caste="breeder" if i == 1 else "warrior",
                 bold=0.4) for i in range(4)]
    for grp in (atk, dfd):
        for a in grp:
            a.belief_vec = (1.0, 0, 0, 0, 0, 0) if grp is atk else (-1.0, 0, 0, 0, 0, 0)
            for b in grp:
                if a is not b:
                    a.bonds[b.id] = Bond(trust=0.8, history=2.5)
    w.regions.pools = [0.0] * 6
    w.regions.pools[rich] = 6.0
    war.war_tick(w)
    assert w._war_log, "the raid still happens without the breeders"
    log = w._war_log[-1]
    assert "k1" not in log["party"], "the attacker-side breeder kept the hearth"
    assert "v1" not in log["defenders"], "the defender-side breeder kept the hearth"
    assert "K1" not in log["fallen"] and "V1" not in log["fallen"]


def test_breeders_never_brawl_never_confront_never_fall():
    """The skirmish layer cannot reach a breeder from either end: an angry breeder
    never closes on a foe, and an angry warrior's open enmity toward a breeder
    finds no valid target -- no clash, no hurt, no casualty."""
    w = _world()
    w.skirmish_enabled = True
    # an angry WARRIOR beside a breeder it holds open enmity toward
    war_a = _soul(w, "w1", (100.0, 100.0))
    brd = _soul(w, "b1", (110.0, 100.0), caste="breeder")
    war_a.hostility[brd.id] = WAR_THRESHOLD + 1.0
    before_pos, before_well = brd.position, brd.wellbeing
    for _ in range(6):
        skirmish.skirmish_tick(w)
    assert brd.wellbeing == before_well, "a breeder is never hurt in a quarrel"
    assert brd in w.agents and war_a in w.agents
    assert brd.hostility.get(war_a.id, 0.0) == 0.0   # no clash hardened anything
    # an angry BREEDER never confronts: it does not close on its foe
    w2 = _world()
    w2.skirmish_enabled = True
    brd2 = _soul(w2, "b2", (100.0, 100.0), caste="breeder")
    far = _soul(w2, "w2", (300.0, 100.0))
    brd2.hostility[far.id] = WAR_THRESHOLD + 1.0
    skirmish.skirmish_tick(w2)
    assert brd2.position == (100.0, 100.0), "a breeder never rushes anyone"


def test_allegiance_refuses_danger_for_the_caste():
    """The caste floor sits before every other read: a breeder with the deepest
    bond in town still refuses danger -- and still joins the errands of peace."""
    w = _world()
    brd = _soul(w, "b1", (0.0, 0.0), caste="breeder")
    wrr = _soul(w, "w1", (0.0, 0.0))
    for a in (brd, wrr):
        a.bonds["lead"] = Bond(trust=0.9, history=3.0)
    verb, reason = allegiance.decide(brd, "lead", danger=0.7)
    assert verb == "refuse" and "hearth" in reason
    assert allegiance.decide(wrr, "lead", danger=0.7)[0] == "join"
    assert allegiance.decide(brd, "lead", danger=0.0)[0] == "join"   # peace is theirs too


# --- the engine: pairing, brooding, birth ----------------------------------------------

def _mating_world(seed=11):
    w = _world(seed=seed)
    w.mating_enabled = True
    wrr = _soul(w, "w1", (100.0, 100.0))
    brd = _soul(w, "b1", (120.0, 100.0), caste="breeder")
    wrr.genome = Genome(grip=0.9, compassion=0.9, temperament=0.9,
                        metabolism=0.9, boldness=0.9, openness=0.9, wrath=0.9)
    brd.genome = Genome(grip=0.1, compassion=0.1, temperament=0.1,
                        metabolism=0.1, boldness=0.1, openness=0.1, wrath=0.1)
    return w, wrr, brd


def test_mating_pairs_gestates_and_births_a_blend():
    """A fed grown warrior beside a free breeder pairs; the breeder broods; at term
    ONE child is born whose every dial came from one parent or the other (uniform
    crossover, one mutation) and whose caste is one of the two."""
    w, wrr, brd = _mating_world()
    mating.mating_tick(w)
    assert brd._sire == wrr.id and brd._gestation == mating.GESTATION
    assert brd._brood_genome is not None
    assert brd.wellbeing == 1.0, "pairing never costs the breeder anything"
    assert brd.bonds[wrr.id].trust > 0 and wrr.bonds[brd.id].trust > 0
    assert wrr._guard == brd.id                     # the warrior guards its hearth
    for _ in range(mating.GESTATION // mating.MATE_CHECK + 2):
        mating.mating_tick(w)
    born = [a for a in w.agents if a.id.startswith("born:")]
    assert len(born) == 1, "ONE child at term"
    child = born[0]
    assert child.caste in ("warrior", "breeder")
    assert child.genome.lineage == wrr.id
    from agent.genome import DIALS
    for dial in DIALS:
        v = getattr(child.genome, dial)
        assert (abs(v - 0.1) < 0.2) or (abs(v - 0.9) < 0.2), \
            f"{dial}={v} came from neither parent"
    assert child.bonds.get(brd.id) is not None      # knows its hearth
    assert child.bonds.get(wrr.id) is not None      # and its sire
    assert brd._recover > 0                         # the breeder rests; the hearth closed


def test_caste_is_roughly_even_over_many_births():
    w, wrr, brd = _mating_world(seed=23)
    castes = []
    for _ in range(60):
        brd._recover, brd._sire = 0, ""
        mating.mating_tick(w)                       # pair
        for _ in range(mating.GESTATION // mating.MATE_CHECK + 2):
            mating.mating_tick(w)                   # brood -> birth
        born = [a for a in w.agents if a.id.startswith("born:")]
        assert len(born) == 1
        castes.append(born[0].caste)
        w.agents = [a for a in w.agents if not a.id.startswith("born:")]
    share = castes.count("breeder") / len(castes)
    assert 0.25 < share < 0.75, f"caste split drifted to {share:.2f}"


def test_reaching_a_rivals_hearth_grudges_the_rival_never_the_breeder():
    w, wrr, brd = _mating_world()
    mating.mating_tick(w)                           # w1 pairs; the hearth is claimed
    rival = _soul(w, "r1", (130.0, 100.0))          # a second warrior arrives
    mating.mating_tick(w)
    assert rival.hostility.get(wrr.id, 0.0) >= mating.MATE_GRUDGE, \
        "the grudge lands on the RIVAL warrior"
    assert rival.hostility.get(brd.id, 0.0) == 0.0, "never on the breeder"
    assert brd.hostility.get(rival.id, 0.0) == 0.0
    assert brd.wellbeing == 1.0


def test_mating_replaces_surplus_budding():
    """With mating on, _selection_tick's surplus-birth path stands down (one birth
    channel, not two) while its starvation arm still runs."""
    w = _world()
    w.stakes_enabled = True
    w.selection_enabled = True
    w.heredity_enabled = True
    a = _soul(w, "w1", (100.0, 100.0))
    a.wellbeing, a.stores, a._met = 0.9, 2.0, 1.0
    w.mating_enabled = True
    for _ in range(w.BREED_TICKS + 5):
        w._selection_tick()
    assert not any(x.id.startswith("born:") for x in w.agents), \
        "no surplus budding while mating drives the births"
    w2 = _world()
    w2.stakes_enabled = True
    w2.selection_enabled = True
    w2.heredity_enabled = True
    b = _soul(w2, "w1", (100.0, 100.0))
    b.wellbeing, b.stores, b._met = 0.9, 2.0, 1.0
    for _ in range(w2.BREED_TICKS + 5):
        w2._selection_tick()
    assert any(x.id.startswith("born:") for x in w2.agents), \
        "the old world's budding is untouched"


def test_age_deaths_are_heirless_under_mating():
    """The heir channel stands down too: with mating on, an age-death ends heirless
    -- else heirs pin the population at the cap (pairing starves for room) and every
    breeder's heir wakes a default-caste warrior, eroding the breeding caste to
    extinction (the 3000-tick arc measured exactly that). Old worlds keep the heir."""
    w = _world()
    w.mating_enabled = True
    w.mourning_enabled = True
    brd = _soul(w, "b1", (100.0, 100.0), caste="breeder")
    kin = _soul(w, "w1", (110.0, 100.0))
    kin.bonds[brd.id] = Bond(trust=0.8, history=2.0)
    brd.age, brd.lifespan, brd.grace = 100, 100, 1.0
    w._reap()
    assert all(a.caste == "warrior" for a in w.agents), "no heir took the hearth"
    assert len(w.agents) == 1, "the lineage ended at the wheel's edge"
    assert any(brd.name in m.text and m.emotion < 0 for m in kin.memory.items), \
        "the death still lands on those who loved them"
    w2 = _world()                                   # mating off: the heir, as ever
    old = _soul(w2, "e1", (100.0, 100.0))
    old.age, old.lifespan, old.grace = 100, 100, 1.0
    w2._reap()
    assert len(w2.agents) == 1 and w2.agents[0].id.startswith("e1.")


# --- the land and the camera ------------------------------------------------------------

def test_arena_grid_and_the_classic_land_byte_identical():
    """Regions(cols=6, rows=4) is 24 distinct-named regions spanning the soil range;
    Regions() with the same seed stays EXACTLY what every validated world holds."""
    big = R.Regions(bounds=(3600.0, 2400.0), seed=17, cols=6, rows=4)
    assert big.cols * big.rows == len(big.names) == len(set(big.names)) == 24
    assert abs(max(big.yields) - 1.3) < 1e-9 and abs(min(big.yields) - 0.5) < 1e-9
    assert big.index((0, 0)) == 0 and big.index((3599, 2399)) == 23
    assert big.centre(0) == (300.0, 300.0) and big.centre(23) == (3300.0, 2100.0)
    rich = max(range(24), key=lambda i: big.yields[i])
    assert big.names[rich] == "the vale"            # the fattest land is still the vale
    classic = R.Regions(seed=1)
    assert (R.COLS, R.ROWS) == (3, 2) and (classic.cols, classic.rows) == (3, 2)
    assert classic.names == ["the heath", "the moor", "the crag",
                             "the vale", "the ridge", "the meadow"]
    assert classic.index((899, 599)) == 5
    # a land pickled before the grid was per-instance wakes as the 3x2 it was
    state = {k: v for k, v in classic.__dict__.items() if k not in ("cols", "rows")}
    woke = R.Regions.__new__(R.Regions)
    woke.__setstate__(state)
    assert (woke.cols, woke.rows) == (3, 2) and woke.index((899, 599)) == 5


def test_camera_clamp_contract():
    """The dashboard's clampCam() in python: a big world's camera stays within
    [0, bounds-view] on both axes; a world smaller than the view is centred."""
    W, H = 1000, 660

    def clamp(cx, cy, bounds, scale):
        vw, vh = W / scale, H / scale
        cx = min(max(cx, 0.0), bounds[0] - vw) if bounds[0] >= vw else (bounds[0] - vw) / 2
        cy = min(max(cy, 0.0), bounds[1] - vh) if bounds[1] >= vh else (bounds[1] - vh) / 2
        return cx, cy

    bounds, scale = (3600.0, 2400.0), W / 1400.0    # the arena at MOBA zoom
    vw, vh = W / scale, H / scale
    for cx, cy in ((-500, -500), (0, 0), (1800, 1200), (9999, 9999)):
        x, y = clamp(cx, cy, bounds, scale)
        assert 0.0 <= x <= bounds[0] - vw and 0.0 <= y <= bounds[1] - vh
    # her classic 900x600 town fits whole: the camera centres it and WASD holds still
    fit = min((W - 52) / 900.0, (H - 96) / 600.0)
    x, y = clamp(123.0, -77.0, (900.0, 600.0), fit)
    assert x == (900.0 - W / fit) / 2 and y == (600.0 - H / fit) / 2
