"""Stakes tests (deterministic, no model): archetype policy, action effects, hardship +
co-suffering, and the karma-seeds (response conditions the soul)."""

from agent import archetype as A
from agent.agent import Agent
from services.llm import MockLLM
from world import stakes
from world.sim import World


def _soul(arch_name, sid="s", seed=1):
    a = Agent(sid, arch_name, (0, 0), "p", ["x"], MockLLM(seed=seed), seed=seed)
    A.apply(a, A.BY_NAME[arch_name])
    a.bond_enabled = True
    a.stores = a.wellbeing = 1.0
    return a


def _world(*agents):
    w = World(move_seed=1)
    w.stakes_enabled = True
    w.llm = MockLLM(seed=1)
    for a in agents:
        w.add(a)
    return w


def test_stakes_off_by_default():
    assert World().stakes_enabled is False


def test_grasper_hoards_under_scarcity():
    g = _soul("Grasper")
    other = _soul("Sage", sid="o")
    g.wellbeing = 0.2          # scarcity
    w = _world(g, other)
    w.commons = 3.0
    assert stakes.choose_action(g, w) == "hoard"


def test_lover_shares_with_the_needy():
    lover = _soul("Lover")
    needy = _soul("Wounded", sid="n")
    needy.wellbeing = 0.2      # someone in need, lover is fine
    w = _world(lover, needy)
    assert stakes.choose_action(lover, w) == "share"


def test_work_builds_the_commons():
    a = _soul("Sage")
    w = _world(a)
    w.commons = 1.0
    stakes.apply_action(a, "work", w, now=1)
    assert w.commons > 1.0


def test_hoard_drains_commons_and_hardens_grip():
    g = _soul("Grasper")
    needy = _soul("Wounded", sid="n")
    needy.wellbeing = 0.2
    g.wellbeing = 0.2
    w = _world(g, needy)
    w.commons = 2.0
    grip0 = g.grip
    stakes.apply_action(g, "hoard", w, now=1)
    assert w.commons < 2.0          # drained the commons
    assert g.grip > grip0           # clinging-seed hardened the grip


def test_share_warms_the_recipients_bond_and_opens_giver():
    lover = _soul("Lover")
    needy = _soul("Wounded", sid="n")
    needy.wellbeing = 0.2
    w = _world(lover, needy)
    comp0 = lover.compassion
    lover.wellbeing = 0.3           # giver under scarcity too -> wise-seed fires
    stakes.apply_action(lover, "share", w, now=1)
    assert needy.bonds.get(lover.id) is not None and needy.bonds[lover.id].trust > 0
    assert lover.compassion > comp0  # giving under scarcity opened the heart


def test_hardship_wounds_writes_a_charge_and_bonds_cosufferers():
    a = _soul("Lover", sid="a")
    b = _soul("Sage", sid="b")
    w = _world(a, b)
    stakes.hardship(w, [a, b], now=5, kind="flood")
    assert a.wellbeing < 1.0 and a.stores < 1.0
    assert any("flood" in m.text and m.emotion < 0 for m in a.memory.items)  # real dukkha
    assert a.bonds.get(b.id) is not None and a.bonds[b.id].trust > 0          # co-suffering bond
