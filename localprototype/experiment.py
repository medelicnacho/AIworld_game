"""Controlled experiment: N seeded replicates, treatment vs control, with a metric.

Fixes #1 (events) and #2 (telemetry) gave us a perturbation and a recorder. This
turns them into an actual experiment. It runs the world many times with events ON
(treatment) and many times with events OFF (control), one replicate per seed,
reduces each run to a single behavioral metric, and reports the effect with its
spread -- so a result is a number with variance, not one run's vibe.

Design is PAIRED: each seed is run once with events on and once with events off,
so everything except the events is held identical and the difference is the
event's effect for that seed. We then summarize the per-seed differences.

Determinism: the agent RNGs are seeded and the MockLLM backend is deterministic,
so a (seed, events) pair reproduces exactly -- rerun the experiment, get the same
numbers. To use a real model instead, run it at temperature 0.

Run:  python experiment.py                          # 8 replicates, 50 ticks
      python experiment.py --replicates 20 --ticks 60
"""

from __future__ import annotations

import argparse
import statistics

from agent.agent import Agent
from services.llm import MockLLM
from services.telemetry import felt_mood
from world.sim import World

# The scenario (personas + event schedule) lives in main.py -- single source of truth.
from main import EVENTS, PERSONAS


# --- building one run ------------------------------------------------------
def build_world(seed: int, events_enabled: bool) -> World:
    """A silent, deterministic world: MockLLM, no TTS, no print subscribers."""
    llm = MockLLM(seed=seed)
    world = World(events=EVENTS, events_enabled=events_enabled)
    for i, (aid, name, pos, persona, phrases, _voice, style, temper) in enumerate(PERSONAS):
        world.add(Agent(aid, name, pos, persona, phrases, llm,
                        seed=seed + i + 1, style=style, temperament=temper))
    world.agents[0].memory.write("the deep is cold", tick=0, source="self",
                                 speaker_id="river", emotion=-0.3)
    world.agents[1].memory.write("warmth fades", tick=0, source="self",
                                 speaker_id="ash", emotion=-0.2)
    return world


def mean_felt_mood(world: World) -> float:
    """The metric snapshot: average felt mood across all agents, right now."""
    return sum(felt_mood(a) for a in world.agents) / len(world.agents)


def run_replicate(seed: int, events_enabled: bool, ticks: int,
                  build=build_world, metric=mean_felt_mood) -> float:
    """Run one replicate; reduce it to a scalar = metric averaged over all ticks
    (the area under the mood curve, so a sustained shift counts more than a blip)."""
    world = build(seed, events_enabled)
    samples: list[float] = []
    world.bus.subscribe("tick", lambda _t: samples.append(metric(world)))
    world.run(ticks)
    return statistics.fmean(samples)


# --- statistics: the SHARED instrument (scripts/stats.py, METHODS.md M1) -------------------
# This file used to carry its own cohens_d_paired/paired_t; they were the pattern every
# other experiment copy-pasted (or skipped). The originals now live, tested against table
# values, in scripts/stats.py -- kept as thin aliases here so old callers keep working.
from scripts.stats import paired as _paired  # noqa: E402 -- sits with the section it feeds


def cohens_d_paired(diffs: list[float]) -> float:
    """Standardized effect size for paired data (delegates to scripts/stats.py)."""
    return _paired([d for d in diffs], [0.0] * len(diffs)).d if len(diffs) >= 2 else 0.0


def paired_t(diffs: list[float]) -> float:
    """One-sample t of the per-seed differences against zero (delegates to scripts/stats.py)."""
    return _paired([d for d in diffs], [0.0] * len(diffs)).t if len(diffs) >= 2 else 0.0


def compare(seeds: list[int], ticks: int,
            build=build_world, metric=mean_felt_mood) -> dict:
    """Paired treatment-vs-control comparison over a list of seeds (M1: the per-seed delta
    is the unit of analysis; the error bar comes from the shared instrument)."""
    treatment = [run_replicate(s, True, ticks, build, metric) for s in seeds]
    control = [run_replicate(s, False, ticks, build, metric) for s in seeds]
    cmp = _paired(treatment, control)
    return {
        "seeds": seeds,
        "ticks": ticks,
        "treatment": treatment,
        "control": control,
        "diffs": cmp.diffs,
        "treatment_mean": cmp.treatment_mean,
        "control_mean": cmp.control_mean,
        "effect_mean": cmp.effect.mean,
        "effect_std": cmp.effect.sd or 0.0,
        "effect_sem": cmp.effect.sem,          # new: the honest bar (M1)
        "ci95": cmp.effect.ci95,               # new: exact-t confidence interval
        "cohens_d": cmp.d,
        "t": cmp.t,
        "p": cmp.p,                            # new: exact two-sided p
        "sign": cmp.sign,                      # new: exact one-sided sign test
    }


def _report(r: dict) -> str:
    n = len(r["seeds"])
    lines = [
        "\n=== Experiment: events (treatment) vs control ===",
        f"replicates={n}  ticks={r['ticks']}  metric=mean felt_mood over the run",
        f"seeds: {r['seeds'][0]}..{r['seeds'][-1]}  (MockLLM, deterministic)\n",
        f"  treatment (events on):  mean {r['treatment_mean']:+.4f}",
        f"  control   (events off): mean {r['control_mean']:+.4f}",
        f"  paired effect (T - C):  {r['effect_mean']:+.4f} "
        f"± {r['effect_std']:.4f}  (Cohen's d {r['cohens_d']:+.2f}, "
        f"t({n - 1}) {r['t']:+.2f})\n",
    ]
    direction = "lowered" if r["effect_mean"] < 0 else "raised"
    lines.append(f"The events {direction} mean mood by "
                 f"{abs(r['effect_mean']):.4f} ± {r['effect_std']:.4f} "
                 f"across {n} paired replicates.")
    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--replicates", type=int, default=8,
                   help="number of seeded paired runs per arm")
    p.add_argument("--ticks", type=int, default=50)
    p.add_argument("--seed-base", type=int, default=100,
                   help="first seed; replicates use seed-base .. seed-base+N-1")
    args = p.parse_args()

    seeds = list(range(args.seed_base, args.seed_base + args.replicates))
    result = compare(seeds, args.ticks)
    print(_report(result))


if __name__ == "__main__":
    main()
