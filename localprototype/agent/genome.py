"""genome.py -- E1: the germ line. Heritable traits over the faculties that already exist.

The honest gap EVOLUTION.md opens with: the wheel CONSERVES population and RE-ROLLS
faculties at rebirth -- nothing is inherited, so nothing can evolve (only culture spreads,
§5.13). This module closes it: a small heritable vector, carried through the bardo with a
small Gaussian mutation applied AT THE CROSSING, expressed onto the newborn stream instead
of the fresh roll. No fitness is scored anywhere, ever -- E1 is inheritance only; selection
is E2's job (differential survival under the stakes), and the falsifier for THIS stage is
the null: with mutation and no selection, the population mean must STAY PUT.

What is in the germ line -- and, deliberately, what is not:
  in:  grip (baseline clinging), compassion, temperament, metabolism (how fast a soul
       consumes stakes -- E2 expresses it), boldness (the work/hoard/share lean -- E2).
  out: telos -- it already crosses the bardo as THIRST (§5.5, validated: coupling-
       dependent, bodhicitta-transmutable); prajna/bodhicitta/grip-as-practice -- they
       cross as the CULTIVATED LEAN under the bodhisattva wheel (§ the Path). Cultivation
       is not heredity; double-carrying one dial through two channels would confound
       both. Precedence is explicit in the wheel: the germ line expresses first, and the
       Path's carry still outranks it for the practice dials.

Mutation uses REFLECTION at the bounds, not clamping: a clamped walk piles up on its
walls and drags the mean inward -- a bias the drift-null falsifier would (rightly) flag
as inheritance leaking. Reflection keeps the null clean.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

SIGMA = 0.03            # per-crossing mutation (the ecology literature's 3e-2 -- EVOLUTION E1)
# dial -> (lo, hi). temperament lives on [-1, 1]; everything else on [0, 1].
BOUNDS = {"grip": (0.0, 1.0), "compassion": (0.0, 1.0), "temperament": (-1.0, 1.0),
          "metabolism": (0.0, 1.0), "boldness": (0.0, 1.0)}
DIALS = tuple(BOUNDS)


@dataclass
class Genome:
    grip: float
    compassion: float
    temperament: float
    metabolism: float = 0.5      # E2: how fast this soul consumes stakes
    boldness: float = 0.5        # E2: the work-vs-hoard-vs-share lean
    lineage: str = ""            # parent-of-record's id -- genealogy ground truth,
                                 # never mutated, never expressed (the ledger, not the flesh)


def _reflect(x: float, lo: float, hi: float) -> float:
    """Fold a value back into [lo, hi] by reflection at the walls."""
    span = hi - lo
    while x < lo or x > hi:
        if x < lo:
            x = lo + (lo - x)
        if x > hi:
            x = hi - (x - hi)
        if span <= 0:
            return lo
    return x


def from_agent(agent, rng) -> Genome:
    """Capture a founder's germ line from the dials it woke with. metabolism/boldness are
    E2's dials -- rolled fresh here (uniform) if the soul does not carry them yet, so the
    founding population starts VARIED (a monoculture founding would make G1's correlation
    claim vacuous and E2's selection blind)."""
    return Genome(
        grip=float(getattr(agent, "grip", 0.0)),
        compassion=float(getattr(agent, "compassion", 0.0)),
        temperament=float(getattr(agent, "temperament", 0.0)),
        metabolism=float(getattr(agent, "metabolism", rng.uniform(0.2, 0.8))),
        boldness=float(getattr(agent, "boldness", rng.uniform(0.2, 0.8))),
        lineage="",
    )


def inherit(parent: Genome, rng, parent_id: str, sigma: float = SIGMA) -> Genome:
    """The crossing: the child's germ line is the parent's, perturbed once (Gaussian,
    reflected at the bounds), with the lineage tag recording whose it was."""
    child = replace(parent, lineage=parent_id)
    for dial in DIALS:
        lo, hi = BOUNDS[dial]
        setattr(child, dial, _reflect(getattr(parent, dial) + rng.gauss(0.0, sigma), lo, hi))
    return child


def express(genome: Genome, agent) -> None:
    """Write the germ line onto the flesh. Called on a newborn stream AFTER the fresh
    endowment (heredity overrides the re-roll) and BEFORE the bodhisattva carry (the Path
    outranks the germ line for the practice dials -- see world/sim.py)."""
    agent.grip = genome.grip
    agent.compassion = genome.compassion
    agent.temperament = genome.temperament
    agent.metabolism = genome.metabolism     # dormant until E2 wires stakes consumption
    agent.boldness = genome.boldness         # dormant until E2 wires the action lean
