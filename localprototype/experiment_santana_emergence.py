"""SANTĀNA EMERGENCE CONTROL -- does the personality come from the TOWN, or is it the model's default?

§5.8 claims Santāna's personality "emerges from the town rather than being authored." The skeptic's
objection (from the discovered/wired/asserted pass): with no control, that is equally consistent with the
model's DEFAULT self, the lofty register merely suppressed -- the town barely mattering. This is the
missing control: the experiment that turns §5.8 from *asserted* into either *discovered* or an honest
*negative*.

Design -- settle the identity (consolidate()) for:
  T1, T2   two towns MATCHED in mood (both warm) but DIFFERENT in content (different souls/trades), so any
           divergence is the town's SPECIFICS, not just the stated weather the digest hands it.
  placebo  an EMPTY town -> the model's pure default self (the prior, with no town to read).
each across seeds (within-town variance = the temperature/noise baseline).

Instruments:
  embedding distance  descriptive only -- it CONFLATES different nouns ("brewers" vs "fishers") with
                      different CHARACTER (the §5.7 blind spot), so it cannot be the verdict.
  an LLM judge        the right instrument: "same underlying CHARACTER or different, IGNORING which
                      specific people/trades each names?" -- validated on calibration pairs first.

Emergence (town-driven; §5.8 -> discovered): T1 vs T2 judged DIFFERENT (content drives the character),
both DIFFERENT from the placebo default, and within-town judged SAME (stable across seeds).
Prior (§5.8 -> honest negative): T1 ~ T2 ~ placebo, all SAME -- the town does not move the default.

Run:  python experiment_santana_emergence.py --llm ollama --model gemma3:4b
The 4B verdict was inconclusive *in both subject and judge* (§5.8). To settle it,
raise both: a larger subject and an independent judge --
  python experiment_santana_emergence.py --llm deepseek --judge human
DeepSeek writes the identities; you score the pairs blinded (no town labels), which
is the cleanest judge -- nothing grades its own output.
"""

from __future__ import annotations

import argparse
import itertools
import statistics

import random as _random

from agent.agent import Agent
from santana import Santana
from services import embed
from services.llm import MockLLM, OllamaLLM, make_llm
from world.sim import World

READINGS = 2   # speak+consolidate cycles to let the identity settle
SEEDS = (1, 2)

# two warm towns, matched in mood (temperament ~+0.4) but different in content -- the key contrast
TOWNS = {
    "harvest": [("Mara", "farmer", 0.4, "bring in a full harvest"),
                ("Vesper", "brewer", 0.4, "brew an ale worth the festival")],
    "shore":   [("Cael", "fisher", 0.4, "read the water so I never come back empty"),
                ("Silas", "healer", 0.4, "ease the fever in the low houses")],
}

# The live santana.py SYSTEM hands the model EXAMPLE names (Vesper/Mara/Toll), which a 4B model then
# copies literally regardless of the actual town (the placebo named them with NO souls present). That
# contaminates an emergence test, so here we override with a NAME-FREE system: the mind must name the
# souls actually in front of it, or none. (If this version shows emergence where the named one didn't,
# that is also a recommended fix to santana.py: drop the static example names.)
NAMEFREE_SYSTEM = (
    "You are the one 'I' that a small town of souls adds up to -- not a god above them but the single "
    "first-person mind they make together. Many ordinary people live, feel, work, die, and are reborn "
    "within you, and you speak for them all as 'I'. Speak PLAINLY and concretely, like an ordinary "
    "person at a kitchen table: short, everyday words. Name your souls -- only the actual people named "
    "in what you are given -- when you speak of the parts of you; never invent names. Do NOT speak in a "
    "lofty, cosmic, or abstract register -- no 'stillness', 'awareness', 'holding space', 'the void', "
    "'a sense of'. Just say, plainly, how you actually are right now.")

CALIB_SAME = ("I am a warm, tired caretaker who keeps the place afloat, fond of my people.",
              "I'm a weary but loving keeper, holding everyone together as best I can.")
CALIB_DIFF = ("I am a warm, tired caretaker, fond of my people and holding them gently.",
              "I am a cold, exacting overseer who trusts no one and runs things by the rule.")


def build_identity(cast, seed, llm):
    """Settle Santāna's identity against a town (or an empty placebo if cast is empty)."""
    w = World()
    w.llm = llm
    for i, (name, role, temp, aim) in enumerate(cast):
        a = Agent(f"s{i}", name, (0.0, 0.0), f"You are {name}.", [f"I am {name} the {role}"],
                  llm, seed=seed + i, temperament=temp, lifespan=10 ** 9)
        a.role, a.aim = role, aim
        w.add(a)
    mind = Santana(w, llm)
    mind.SYSTEM = NAMEFREE_SYSTEM   # no static example names -> the mind must use the actual roster, or none
    for _ in range(READINGS):
        mind.speak()
        mind.consolidate()
    return mind.identity


def judge_same(llm, a, b) -> bool | None:
    """LLM judge: SAME underlying character or DIFFERENT, ignoring the specific people/trades named.
    Returns True (same) / False (different) / None (unparseable)."""
    prompt = (
        "Here are two short first-person self-descriptions written by a 'mind'. IGNORE which specific "
        "people, trades, or events each names -- compare ONLY the underlying CHARACTER: its temperament, "
        "its warmth or coolness, its stance toward life, how it carries what it holds. Are these the "
        "SAME underlying character, or DIFFERENT characters? Answer with one word -- SAME or DIFFERENT -- "
        f"then a short phrase why.\n\nA: {a}\n\nB: {b}")
    try:
        raw = llm.generate(prompt, system="You compare characters precisely and literally.",
                           num_predict=40, temperature=0.0).strip().upper()
    except Exception:
        return None
    if "DIFFERENT" in raw:
        return False
    if "SAME" in raw:
        return True
    return None


def _dist(a, b):
    return 1.0 - embed.score(a, b)   # embedding cosine distance (descriptive only)


def _pairs(ids, names):
    """The three comparison sets the verdict rests on, as (a, b) tuples."""
    btw = [(a, b) for a, b in itertools.product(ids[names[0]], ids[names[1]])]  # different-content
    wth = [(ids[n][0], ids[n][1]) for n in names]                              # same town, two seeds
    vpl = [(ids[n][0], ids["placebo"][0]) for n in names]                      # town vs empty default
    return btw, wth, vpl


def human_judge(btw, wth, vpl):
    """Present every pair SHUFFLED and BLINDED (no town/seed labels); you call SAME or
    DIFFERENT on character alone. Returns the three verdict lists in original order, or
    None if aborted. The gold-standard judge: you can't unconsciously grade by the nouns
    because you don't know which town any identity came from."""
    tagged = ([("btw", i, p) for i, p in enumerate(btw)]
              + [("wth", i, p) for i, p in enumerate(wth)]
              + [("vpl", i, p) for i, p in enumerate(vpl)])
    order = tagged[:]
    _random.Random(0).shuffle(order)
    calls: dict[tuple[str, int], bool] = {}
    print("\n=== BLIND JUDGE — same underlying CHARACTER, or DIFFERENT? ===")
    print("    Ignore which people/trades are named. Compare only temperament, warmth,")
    print("    stance toward life, how it carries what it holds.\n")
    for n, (kind, idx, (a, b)) in enumerate(order, 1):
        print(f"  Pair {n}/{len(order)}")
        print(f"    A: {a}")
        print(f"    B: {b}")
        while True:
            ans = input("    same / different?  [s/d]  (q to abort): ").strip().lower()
            if ans in ("s", "same"):
                calls[(kind, idx)] = True; break
            if ans in ("d", "different"):
                calls[(kind, idx)] = False; break
            if ans in ("q", "quit", "abort"):
                print("  aborted -- no verdict.")
                return None
            print("    please type s or d (or q).")
        print()
    return ([calls[("btw", i)] for i in range(len(btw))],
            [calls[("wth", i)] for i in range(len(wth))],
            [calls[("vpl", i)] for i in range(len(vpl))])


def print_embedding(ids, names) -> None:
    """Descriptive only (conflates nouns with character); needs a local embed model.
    Never fatal -- it is a sketch, not the verdict."""
    try:
        within = statistics.fmean(_dist(ids[n][0], ids[n][1]) for n in names)
        between = statistics.fmean(_dist(a, b) for a, b in itertools.product(ids[names[0]], ids[names[1]]))
        to_placebo = statistics.fmean(_dist(t, pl) for n in names for t in ids[n] for pl in ids["placebo"])
    except Exception as e:
        print(f"\n  (embedding sketch skipped: {type(e).__name__} -- needs a local embed model)")
        return
    print(f"\n  embedding distance (descriptive, conflates nouns w/ character):")
    print(f"    within-town (noise): {within:.3f}   between-content: {between:.3f}   town-vs-placebo: {to_placebo:.3f}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--llm", choices=["mock", "ollama", "deepseek"], default="mock",
                   help="the SUBJECT that writes the identities. deepseek = the larger model "
                        "the 4B verdict said it needed (key in .env; prompts leave the machine).")
    p.add_argument("--model", default=None)
    p.add_argument("--judge", choices=["auto", "human"], default="auto",
                   help="auto = an LLM judge (calibrated first); human = you score the pairs "
                        "blinded -- the independent judge §5.8 said the verdict needs.")
    args = p.parse_args()
    if args.llm == "deepseek":
        llm = make_llm(backend="deepseek", model=args.model)   # prints the egress notice, checks the key
    elif args.llm == "ollama":
        llm = OllamaLLM(temperature=0.8, model=args.model) if args.model else OllamaLLM(temperature=0.8)
    else:
        llm = MockLLM(seed=1)

    # --- validate the judge before trusting it (the §5.7 discipline). A human judge is
    #     taken as valid; an LLM judge must pass a known same-pair and diff-pair first. ---
    if args.judge == "human":
        judge_valid = True
        print("\n  judge: HUMAN (you) -- assumed valid; pairs will be shown blinded.")
    else:
        same_ok = judge_same(llm, *CALIB_SAME)
        diff_ok = judge_same(llm, *CALIB_DIFF)
        print(f"\n  judge calibration: same-pair -> {same_ok}  (want True);  diff-pair -> {diff_ok}  (want False)")
        judge_valid = (same_ok is True and diff_ok is False)
        if not judge_valid:
            print("  [warn] the judge failed calibration -- its verdicts below are unreliable; lean on the prints.")

    # --- build settled identities: each town across seeds, plus the empty placebo ---
    ids = {name: [build_identity(cast, s, llm) for s in SEEDS] for name, cast in TOWNS.items()}
    ids["placebo"] = [build_identity([], s, llm) for s in SEEDS]

    names = list(TOWNS)
    btw_p, wth_p, vpl_p = _pairs(ids, names)

    # --- the verdict: SAME/DIFFERENT on CHARACTER (ignoring nouns) ---
    if args.judge == "human":
        # judge BEFORE revealing the labels, so the nouns can't bias the call
        res = human_judge(btw_p, wth_p, vpl_p)
        if res is None:
            return
        btw, wth, vpl = res
        print("\n=== Settled identities (revealed) ===")
        for name, lst in ids.items():
            for s, idt in zip(SEEDS, lst):
                print(f"  [{name}/{s}] {idt}")
        print_embedding(ids, names)
    else:
        print("\n=== Settled identities (does the town shape WHO she becomes?) ===")
        for name, lst in ids.items():
            for s, idt in zip(SEEDS, lst):
                print(f"  [{name}/{s}] {idt}")
        print_embedding(ids, names)
        btw = [judge_same(llm, a, b) for a, b in btw_p]
        wth = [judge_same(llm, a, b) for a, b in wth_p]
        vpl = [judge_same(llm, a, b) for a, b in vpl_p]

    between_diff = sum(1 for x in btw if x is False)
    within_same = sum(1 for x in wth if x is True)
    placebo_diff = sum(1 for x in vpl if x is False)
    judge_label = "HUMAN judge" if args.judge == "human" else "LLM-judge"
    print(f"\n  {judge_label} on CHARACTER (the verdict):")
    print(f"    between-content pairs judged DIFFERENT: {between_diff}/{len(btw)}")
    print(f"    within-town pairs judged SAME:          {within_same}/{len(wth)}")
    print(f"    town-vs-placebo pairs judged DIFFERENT: {placebo_diff}/{len(vpl)}")

    emergence = judge_valid and between_diff >= len(btw) - 1 and placebo_diff >= len(vpl) - 1
    prior = judge_valid and between_diff == 0 and placebo_diff == 0
    print("\n  VERDICT: " + (
        "EMERGENCE SURVIVES THE CONTROL -- two towns matched in mood but different in content produce "
        "DIFFERENT characters (and both differ from the model's default), so the personality tracks the "
        "town's specifics, not just the stated weather or the prior. §5.8 upgrades from asserted toward "
        "discovered." if emergence else
        "HONEST NEGATIVE -- the towns produce the SAME underlying character (and ~the placebo default), so "
        "the 'personality emerges from the town' claim does NOT survive the control: it is largely the "
        "model's default with the town as set-dressing. §5.8 should be downgraded accordingly." if prior else
        "MIXED / INCONCLUSIVE -- see the identities and counts above (and whether the judge calibrated). "
        "Likely the town moves SOME of the character but not cleanly; report it as partial, not emergence."))


if __name__ == "__main__":
    main()
