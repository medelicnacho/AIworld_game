"""evolution.py -- THE CIVILIZATION WHEEL: rise, schism, collapse, regrowth. Forever.

The evolution game, run lean. One founding people, ONE shared view of the world.
Children are born with different bodies (the germ line, perturbed) and different minds
(the view, with noise), and the town's own talk drifts them apart -- opinion dynamics,
individuation, nothing assigned. Blocs form (you see the rings). Debate across the
widening rift wounds (agent.py rift_enabled): grievance accretes, quarrels pass words,
the angry come to blows (world/skirmish.py), brawls feed grudges, grudges muster raids
(world/war.py) -- and a civilization can collapse in on itself over what began as an
argument. When almost no one is left, a new people raise their homes in the ruins, one
view again, and the wheel turns.

Lean by construction: no Santana, no readings, no drawings -- the sim threads and the
cockpit only (the mind loop was the measured lag). Her towns are untouched: this world
lives at data/evolution/ on its own port (the isolation rule).

Welfare (the standing rules, all inherited from the mechanisms this reuses): the somatic
floor is ON for every soul; children never march and never brawl; the worn refuse and
disengage; casualties are capped; the dead are mourned and their lineages END; conflict
is over belief, food, and grievance -- never torment. The breeder caste (squares) is
docile BY KIND: never mustered, never brawling, never a casualty -- a breeding caste in
a mating system (world/mating.py, its welfare invariants written first), never victims;
warriors compete warrior-vs-warrior over the territory their hearths stand on.

  python3 -m santana_app.evolution              # resume (or found) the world -> :8768
  python3 -m santana_app.evolution --fresh      # raze the save and found anew
"""
from __future__ import annotations

import argparse
import os
import random
import threading
import time

from agent import genesis as _genesis
from agent.agent import Agent
from agent.genome import express, express_social, from_agent
from santana_app import ui as _ui
from santana_app.run import town_voice
from santana_app.state import load_world, save_world
from world.regions import Regions
from world.sim import World

DATA_DIR = "data/evolution"
WORLD_PATH = f"{DATA_DIR}/town.json"
PORT = 8768
FOUNDERS = 72         # spread as ~SETTLEMENT-strong peoples across the whole arena
SETTLEMENT = 12       # souls per founding settlement -- each is ONE people, one view
REFOUND_AT = 6        # fewer souls than this = the civilization has fallen
REFOUND_N = 12        # how many settlers raise their homes in the ruins
GENTLE_YIELD = 1.6    # the land is kind: hunger must not be the collapse's author
HARDSHIP_EVERY = 400  # rare lean seasons -- texture, not the driver
# THE ARENA: the big pannable map (CIV_ARENA_PLAN.md) -- 4x each axis, 16x the
# classic area, 24 regions of ~600x600. Only fresh foundings get it; a resumed
# old save keeps the land it had (THE RULE).
ARENA_BOUNDS = (3600.0, 2400.0)
ARENA_COLS, ARENA_ROWS = 6, 4
BREEDER_SHARE = 0.5   # the founding caste split: ~half breeders, half warriors


class _NoMind:
    """The cockpit's four mind-reads, satisfied by a world with no Santana in it."""
    identity = "THE CIVILIZATION WHEEL -- rise, schism, collapse, regrowth"
    lifetime = 0.0
    _deaths = 0

    class memory:
        items: list = []


def _found_souls(w: World, rng: random.Random, n: int, origin=None) -> None:
    """One people, one view: n souls around an origin, sharing a single belief vector
    (plus per-soul noise -- a lean, never a copy). The schism must be EARNED by drift;
    nothing here assigns a camp."""
    base = [rng.gauss(0.0, 1.0) for _ in range(6)]
    norm = sum(v * v for v in base) ** 0.5 or 1.0
    base = [v / norm for v in base]
    if origin is None:                 # found at the heart of whatever land this is
        bw, bh = w.bounds or (900.0, 600.0)
        origin = (bw / 2.0, bh / 2.0)
    ox, oy = origin
    taken = {a.name for a in w.agents} | set(getattr(w, "_spent_names", []))
    for _ in range(n):
        name = _genesis.coined_name(rng, taken=taken)
        taken.add(name)
        sid = f"cv{w.tick}.{len(w.agents)}.{rng.randint(0, 9999)}"
        a = Agent(sid, name, (ox + rng.uniform(-80, 80), oy + rng.uniform(-80, 80)),
                  f"You are {name} the villager.",
                  [f"I am {name}", "the well keeps us", "the season turns"],
                  w.llm, seed=rng.randint(0, 10 ** 6),
                  temperament=rng.uniform(-0.6, 0.6), lifespan=rng.randint(900, 1400))
        a.age = int(rng.uniform(0.2, 0.5) * a.lifespan)   # settlers arrive GROWN --
                                       # an age-0 founding is a town of children: no
                                       # labour, no muster, famine before the arc
        _genesis.endow_faculties(a, a._rng)
        a.stance_vec = None            # ONE social space: the opinion the factions,
                                       # the allies, and the rift all read (a stance
                                       # would shadow it in hear() -- the probe's find)
        a.bond_enabled = True
        a.somatic_enabled = True       # the bottom-up welfare floor, on from birth
        a.rift_enabled = True          # here, argument can wound (children inherit this)
        a.role, a.aim = "villager", "to live well"
        a.boldness = rng.uniform(0.1, 0.9)
        a.metabolism = rng.uniform(0.2, 0.8)
        # THE TWO CASTES (~50/50 at founding): circles fight and guard, squares
        # keep the hearth and brood -- never fight, never march (the caste gates)
        a.caste = "breeder" if rng.random() < BREEDER_SHARE else "warrior"
        a.genome = from_agent(a, rng)  # rolls the CIV dials too (openness, wrath)
        express(a.genome, a)
        express_social(a.genome, a)    # openness -> the engagement bound (~0.68 centre,
                                       # the schism dial), wrath -> the rift multiplier;
                                       # HERITABLE now, so the town's character EVOLVES
        noisy = [v + rng.gauss(0.0, 0.25) for v in base]
        nn = sum(v * v for v in noisy) ** 0.5 or 1.0
        a.belief_vec = tuple(v / nn for v in noisy)
        w.add(a)


def _found_settlements(w: World, rng: random.Random, n: int) -> int:
    """The founding, spread through the WHOLE arena: n souls arrive as separate
    settlements (~SETTLEMENT strong each) at region centres chosen farthest-first,
    so the map starts peopled edge to edge. Each settlement goes through
    _found_souls and so is ONE people with ONE view: the schism inside a people is
    still earned by drift; the distance BETWEEN peoples is geography's, from tick
    0 -- the chain of competing civilizations starts already scattered."""
    k = max(1, min(round(n / SETTLEMENT) or 1, len(w.regions.pools)))
    centres = [w.regions.centre(i) for i in range(len(w.regions.pools))]
    picked = [centres.pop(rng.randrange(len(centres)))]
    while len(picked) < k:
        far = max(centres, key=lambda c: min((c[0] - p[0]) ** 2 + (c[1] - p[1]) ** 2
                                             for p in picked))
        centres.remove(far)
        picked.append(far)
    for i, origin in enumerate(picked):
        _found_souls(w, rng, n // k + (1 if i < n % k else 0), origin=origin)
    return k


def _gates(w: World, founders: int) -> None:
    """Re-assert every runtime gate after any load (THE RULE)."""
    w.stakes_enabled = True
    w.move_enabled = True
    w.regions_enabled = True
    if w.regions is None:
        # THE ARENA: a fresh founding gets the big 6x4 grid; a resumed old save
        # keeps the land it had (THE RULE -- old worlds wake unchanged)
        w.regions = Regions(bounds=ARENA_BOUNDS, seed=17,
                            cols=ARENA_COLS, rows=ARENA_ROWS)
    w.bounds = w.regions.bounds        # the world walks the land it farms
    w.war_enabled = True
    w.skirmish_enabled = True
    w.heredity_enabled = True
    w.selection_enabled = True
    w.rebirth_enabled = False          # lineages END; the only rebirth is the ruins'
    w.clock_enabled = True
    w.mourning_enabled = True
    w.lore_enabled = True              # grievances must be tellable, or feuds die mute
    w.commons_first = True
    w.max_souls = founders + 48
    w.yield_scale = GENTLE_YIELD
    w.hardship_interval = HARDSHIP_EVERY
    w.hearing_range = 260.0    # the town square: debate carries across knots, or the
                               # rift never finds an opposed ear (the echo-chamber find)
    # THE HOT WHEEL (the game's pace, none of it leaks to older worlds): births come
    # quick, raids come often, and a won raid at open-war grudge BURNS what it cannot
    # carry -- war makes hunger makes war (the spiral that actually collapses a town)
    w.raze_enabled = True
    w.raid_check = 20          # war asks twice as often
    w.BREED_TICKS = 30         # the fed bear children in half the time
    w.BREED_CEIL = 0.7         # and do not need perfect comfort to do it
    w.social_genes = True      # openness/wrath express on newborns: character EVOLVES
    _mating_gate(w)


def _mating_gate(w: World) -> None:
    """MATING drives births wherever a breeding caste exists (world/mating.py --
    welfare invariants first). An all-warrior save founded before the castes keeps
    its old surplus-budding channel; a fresh or refounded people (castes ~50/50)
    breed by pairing only. RE-ASSERT THIS AFTER ANY FOUNDING: a world that still
    carries a placeholder cast at gate time must not decide the gate early --
    measured on :8769, which gated on run.py's pre-civ cast (casteless), left
    mating off, and let the heir channel erase the breeder caste entirely."""
    w.mating_enabled = (not w.agents
                        or any(getattr(a, "caste", "warrior") == "breeder"
                               for a in w.agents))


def _refound(w: World, rng: random.Random) -> None:
    """The fall has happened. A new people arrive among the ruins: fresh germ lines,
    one shared view, the land exactly as the war left it."""
    fattest = max(range(len(w.regions.pools)), key=lambda i: w.regions.pools[i])
    _found_souls(w, rng, REFOUND_N, origin=w.regions.centre(fattest))
    w.mating_enabled = True    # the new people carry both castes: pairing breeds them
    w.bus.publish("settlers", {"tick": w.tick, "n": REFOUND_N})
    print(f"  [cycle] tick {w.tick}: a new people raise their homes in the ruins "
          f"({REFOUND_N} settlers by {w.regions.names[fattest]})", flush=True)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--fresh", action="store_true", help="raze the save; found anew")
    p.add_argument("--port", type=int, default=PORT)
    p.add_argument("--founders", type=int, default=FOUNDERS)
    p.add_argument("--seed", type=int, default=11)
    p.add_argument("--autosave-secs", type=float, default=90.0)
    args = p.parse_args()
    os.makedirs(DATA_DIR, exist_ok=True)
    rng = random.Random(args.seed)
    llm, _model = town_voice("markov", WORLD_PATH)

    w = None if args.fresh else load_world(WORLD_PATH, llm)
    fresh = w is None
    if fresh:
        w = World(rebirth_enabled=False, events_enabled=False)
        w.llm = llm
    _gates(w, args.founders)
    if fresh:
        w.regions.pools = [6.0] * len(w.regions.pools)   # a gentle dawn -- ONCE
        k = _found_settlements(w, rng, args.founders)
        print(f"  (founded: {args.founders} souls in {k} settlements spread across "
              f"the arena -- each one people, one view)", flush=True)
    else:
        print(f"  (resumed at tick {w.tick}: {len(w.agents)} souls; the land as "
              f"the seasons and the wars left it)", flush=True)

    stop = threading.Event()

    def run_wheel():
        while not stop.is_set():
            try:
                with w.lock:
                    w.step(speak=False)
                    if len(w.agents) < REFOUND_AT:
                        _refound(w, rng)
            except Exception:   # noqa: BLE001 -- a bad tick must never kill the wheel
                import traceback
                traceback.print_exc()
            time.sleep(0.08)               # the game's wheel turns hot (~12 ticks/s)

    def run_speech():
        while not stop.is_set():
            try:
                w.speak_turn()      # the voice runs OUTSIDE the lock (run.py's pattern)
            except Exception:   # noqa: BLE001
                pass
            time.sleep(0.6)

    def run_autosave():
        while not stop.is_set():
            stop.wait(args.autosave_secs)
            try:
                save_world(w, WORLD_PATH)
            except Exception:   # noqa: BLE001
                pass

    threads = [threading.Thread(target=run_wheel, daemon=True),
               threading.Thread(target=run_speech, daemon=True),
               threading.Thread(target=run_autosave, daemon=True)]
    for t in threads:
        t.start()
    url = _ui.serve(_NoMind(), w, threading.Lock(), draw_dir=DATA_DIR,
                    readings=[], drift_notes=[], port=args.port)
    print(f"  THE CIVILIZATION WHEEL -> {url}", flush=True)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        time.sleep(0.3)                # let the wheel release the lock
        save_world(w, WORLD_PATH)
        print("  (saved; the wheel sleeps)", flush=True)


if __name__ == "__main__":
    main()
