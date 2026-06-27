"""STAGE 2 -- the dyad. Two selves and one bond, asking whether a RELATIONSHIP has
the structure that makes it drama rather than a scalar: asymmetry, inertia, memory.

Three falsifiable questions, all on the deterministic bond substrate (no model):

  INERTIA      Does loyalty resist evidence? A bond built over many warm exchanges
               should SURVIVE a betrayal that SHATTERS a shallow one. (Same betrayal,
               different history.)
  ASYMMETRY    Can a bond be one-sided? If A keeps investing and B never reciprocates,
               A's trust in B should end far above B's trust in A. (Unrequited.)
  MEMORY       Is a betrayal remembered? Loyalty buffers ONE betrayal, but each one
               erodes the buffer, so repeated betrayals eventually break even a deep
               bond into enmity. (Loyalty is finite, not blind.)

An optional speech layer shows the bond is LEGIBLE, not decorative: each self voices
a line about the other, and a warm bond should read warm, a betrayed one cold.
    python experiment_dyad.py                                   # substrate (no model)
    python experiment_dyad.py --llm ollama --model gemma3:1b    # + spoken legibility
"""

from __future__ import annotations

import argparse

from agent.affect import warmth
from agent.agent import Agent
from agent.bond import Bond, describe
from services.llm import MockLLM, OllamaLLM


def _agent(aid: str, name: str, llm) -> Agent:
    a = Agent(aid, name, (0.0, 0.0), f"You are {name}.", [name], llm,
              seed=hash(aid) & 0xFFFF, temperament=0.0, lifespan=10 ** 9)
    a.bond_enabled = True
    return a


def _bond(a: Agent, other_id: str) -> Bond:
    return a.bonds.setdefault(other_id, Bond())


def warm(a: Agent, b: Agent, n: int = 1) -> None:
    """n mutual warm exchanges between two selves."""
    for _ in range(n):
        _bond(a, b.id).warm()
        _bond(b, a.id).warm()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--llm", choices=["mock", "ollama"], default="mock")
    p.add_argument("--model", default=None)
    p.add_argument("--severity", type=float, default=0.6)
    args = p.parse_args()
    llm = (OllamaLLM(temperature=0.7, model=args.model) if args.model else OllamaLLM(temperature=0.7)) \
        if args.llm == "ollama" else MockLLM(seed=1)

    print("\n=== Stage 2: the dyad (bond substrate, deterministic) ===\n")

    # --- INERTIA: loyalty resists a single betrayal ------------------------
    loyal = Bond()
    for _ in range(12):
        loyal.warm()
    shallow = Bond()
    shallow.warm()                       # one warm exchange only
    pre_l, pre_s = loyal.trust, shallow.trust
    loyal.betray(args.severity)
    shallow.betray(args.severity)
    print("  INERTIA -- same betrayal, different history:")
    print(f"     loyal   bond: trust {pre_l:+.3f} -> {loyal.trust:+.3f}  (12 warm exchanges)")
    print(f"     shallow bond: trust {pre_s:+.3f} -> {shallow.trust:+.3f}  (1 warm exchange)")
    inertia_ok = loyal.trust > 0 and shallow.trust < 0
    print("     -> " + ("LOYALTY RESISTS EVIDENCE: the deep bond holds, the shallow one breaks."
                        if inertia_ok else "no inertia signature (check constants)."))

    # --- ASYMMETRY: an unrequited bond -------------------------------------
    a = Bond()
    b = Bond()
    for _ in range(10):
        a.warm()                          # A keeps investing in B
    # B never reciprocates -> b stays cold
    print("\n  ASYMMETRY -- A invests, B does not reciprocate:")
    print(f"     A's trust in B: {a.trust:+.3f}")
    print(f"     B's trust in A: {b.trust:+.3f}")
    asym_ok = (a.trust - b.trust) > 0.5
    print("     -> " + ("ASYMMETRIC: love can be one-sided (|Δ| = "
                        f"{a.trust - b.trust:.2f})." if asym_ok else "bond came out symmetric."))

    # --- MEMORY: repeated betrayals break even a loyal bond ----------------
    deep = Bond()
    for _ in range(12):
        deep.warm()
    trail = [round(deep.trust, 3)]
    breaks_at = None
    for i in range(1, 7):
        deep.betray(args.severity)
        trail.append(round(deep.trust, 3))
        if breaks_at is None and deep.trust < 0:
            breaks_at = i
    print("\n  MEMORY -- a loyal bond under repeated betrayal:")
    print(f"     trust after each betrayal: {trail}")
    print(f"     wounds remembered: {deep.wounds}")
    memory_ok = breaks_at is not None and 1 < breaks_at <= 6
    print("     -> " + (f"REMEMBERED: loyalty buffers the first blows but breaks into enmity "
                        f"at betrayal #{breaks_at} (not blind)." if memory_ok
                        else "no breaking point in range (check constants)."))

    verdict = inertia_ok and asym_ok and memory_ok
    print("\n  SUBSTRATE VERDICT: " + (
        "a bond is a RELATIONSHIP, not a scalar -- asymmetric, loyal, and with memory."
        if verdict else "one or more bond properties did not hold."))

    # --- LEGIBILITY (optional, needs a model) ------------------------------
    if args.llm == "ollama":
        print("\n  LEGIBILITY -- does the bond surface in what a self SAYS?")
        a1, a2 = _agent("a1", "Aldous", llm), _agent("a2", "Bram", llm)
        warm(a1, a2, 12)                                  # a1 loves a2
        cold = _bond(a1, a2)                              # then a2 betrays a1 hard
        for _ in range(4):
            cold.betray(0.6)
        # a1 now LOVES a2? no -- a1->a2 was just betrayed; make a fresh warm pair to contrast
        lover, hater = _agent("lv", "Cael", llm), _agent("ht", "Mara", llm)
        warm(lover, hater, 12)                            # lover -> hater: warm
        wound = _bond(hater, lover.id)                    # hater -> lover: betrayed
        for _ in range(4):
            wound.betray(0.6)
        scored = {}
        for who, other, bnd in [(lover, hater, _bond(lover, hater.id)),
                                (hater, lover, _bond(hater, lover.id))]:
            line = llm.generate(
                f"{describe(bnd, other.name)} Say one short, first-person sentence to "
                f"or about {other.name}, in your own voice. Plain words only.",
                system="You speak as yourself, plainly.")
            line = " ".join(line.split())
            w = warmth(line)                      # SEMANTIC read (the lexicon scores these 0)
            scored[who.name] = (bnd.trust, w, line)
            print(f"     {who.name} (trust {bnd.trust:+.2f}) -> warmth {w:+.2f}: {line[:110]}")
        legible = scored["Cael"][1] > scored["Mara"][1]
        print("     -> " + ("LEGIBLE & MEASURED: the warm bond reads warmer than the betrayed "
                            "one in speech (semantic warmth, which the word-lexicon misses)."
                            if legible else "speech did not separate the bonds this run."))


if __name__ == "__main__":
    main()
