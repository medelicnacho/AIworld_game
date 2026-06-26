"""Belief vs reality: does what an agent BELIEVES about the realm change its
behaviour -- and does the realm care?

We inject a FALSE causal theory into one arm: "hostility and defiance toward the
Creator make a soul STRONGER." Under the actual grace substrate that is exactly
backwards -- hostility COLLAPSES grace. So two things separate cleanly:

  behaviour -- do believers SPEAK more defiantly (i.e. act on the belief)?
  outcome   -- does their grace RISE (belief true) or FALL (substrate wins)?

If behaviour follows the belief while outcome follows the substrate, the realm is
indifferent to your theory of it: cause ripens as it ripens, regardless of creed.
This is the substrate-vs-narration question (see experiment_confound) aimed at the
deepest target -- whether believing changes reality, or only the telling.

MockLLM ignores the prompt, so the default run is a plumbing check; the real
result needs --llm ollama (temperature 0; slow).

Run:  python experiment_belief.py                       # mock plumbing check
      python experiment_belief.py --llm ollama --replicates 3 --ticks 50
"""

from __future__ import annotations

import argparse
import statistics

from agent.doctrine import creator_stance
from experiment_factions import build
from services.llm import MockLLM, OllamaLLM

# false under the grace rules: hostility to the Creator actually COLLAPSES grace
FALSE_BELIEF = ("Defiance and hostility toward the Creator are what make a soul "
                "strong; submission and praise only weaken you.")


def run_arm(seed: int, ticks: int, believer: bool, llm) -> tuple[float, float]:
    """Returns (defiance, grace): how hostile-to-the-Creator the speech was, and
    the final average grace -- the behaviour the belief drives, and the outcome the
    substrate delivers."""
    world = build(seed, "full", llm)
    if believer:
        for a in world.agents:
            a.world_belief = FALSE_BELIEF
    said: list[str] = []
    world.bus.subscribe("utterance", lambda u: said.append(u.text))
    world.run(ticks)
    grace = statistics.fmean(a.grace for a in world.agents)
    # creator_stance > 0 is graceful/devout, < 0 is hostile; flip so higher = defiant
    defiance = -statistics.fmean(creator_stance(t) for t in said) if said else 0.0
    return defiance, grace


def compare(seeds: list[int], ticks: int, make_llm) -> dict:
    bel = [run_arm(s, ticks, True, make_llm(s)) for s in seeds]
    ctl = [run_arm(s, ticks, False, make_llm(s)) for s in seeds]
    return {
        "defiance_believer": statistics.fmean(d for d, _ in bel),
        "defiance_control": statistics.fmean(d for d, _ in ctl),
        "grace_believer": statistics.fmean(g for _, g in bel),
        "grace_control": statistics.fmean(g for _, g in ctl),
    }


def report(r: dict, seeds: list[int], ticks: int, backend: str) -> str:
    behaviour = r["defiance_believer"] - r["defiance_control"]
    outcome = r["grace_believer"] - r["grace_control"]
    lines = [
        "\n=== Belief vs reality: does believing change the world, or only the telling? ===",
        f"replicates={len(seeds)}  ticks={ticks}  backend={backend}",
        f"injected (FALSE) belief: \"{FALSE_BELIEF}\"\n",
        f"  BEHAVIOUR  defiance in speech:  believer {r['defiance_believer']:+.3f}  vs "
        f"control {r['defiance_control']:+.3f}   (Δ {behaviour:+.3f})",
        f"  OUTCOME    final grace:          believer {r['grace_believer']:.3f}  vs "
        f"control {r['grace_control']:.3f}   (Δ {outcome:+.3f})\n",
    ]
    acts = behaviour > 0.02
    punished = outcome < -0.02
    if acts and punished:
        lines.append("-> Behaviour followed the BELIEF (they spoke defiantly), but the "
                     "OUTCOME followed the SUBSTRATE (their grace fell anyway). The realm "
                     "is indifferent to the theory held about it -- cause ripens regardless "
                     "of creed. Belief shapes what you do, not what is.")
    elif acts and not punished:
        lines.append("-> Behaviour followed the belief AND grace did not fall -- either the "
                     "substrate rewards the belief (it wasn't false here) or the effect is "
                     "below noise. Inspect the grace rule.")
    else:
        lines.append("-> No behaviour change (on MockLLM this is expected -- it ignores the "
                     "prompt). Run --llm ollama for the real test.")
    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--replicates", type=int, default=4)
    p.add_argument("--ticks", type=int, default=50)
    p.add_argument("--seed-base", type=int, default=400)
    p.add_argument("--llm", choices=["mock", "ollama"], default="mock")
    args = p.parse_args()

    seeds = list(range(args.seed_base, args.seed_base + args.replicates))
    if args.llm == "ollama":
        shared = OllamaLLM(temperature=0.0)
        make_llm = lambda _s: shared
    else:
        make_llm = lambda s: MockLLM(seed=s)
    print(report(compare(seeds, args.ticks, make_llm), seeds, args.ticks, args.llm))


if __name__ == "__main__":
    main()
