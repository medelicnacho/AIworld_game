"""STAGE 1 -- the clean room. One agent, a dead-boring environment, a scripted
grief protocol, and a falsifiable question: does an emotional SELF show a legible
trajectory, and does reflect() (relating to its own memory) change that trajectory?

Two questions, kept apart:
  A) SUBSTRATE -- does a single self even have readable feelings? We look for three
     signatures in the lived mood (memory.mood()), with NO other agents and NO LLM
     cleverness required:
        grief        mood drops sharply when the loss lands,
        habituation  mood recovers over the quiet days after,
        recurrence   mood dips again when a reminder of the loss arrives.
     If these don't appear, no dyad or samsara sim will be legible either -- this
     is the prerequisite the live --world transcript showed is missing in the crowd.
  B) MECHANISM -- does reflect() help? Same seed, same protocol, reflect ON vs OFF.
     Verdict compares how the two arms cope (mean lived mood after the loss, and how
     fully each recovers). If reflect doesn't move it, it's a decorative loop -- the
     exact failure this clean room exists to catch early.

The protocol is deterministic; the SUBSTRATE signatures hold under MockLLM (no
model). reflect's real EQUANIMITY signal needs a model:
    python experiment_affect.py                       # MockLLM: plumbing + substrate
    python experiment_affect.py --llm ollama --model gemma3:1b   # real reflections
"""

from __future__ import annotations

import argparse
import statistics

from agent.affect import equanimity
from agent.agent import Agent
from agent.memory import valence
from agent.reflect import reflect
from services.llm import MockLLM, OllamaLLM
from world.events import WorldEvent

TICKS = 36
LOSS_TICK = 4
REMINDER_TICK = 20
REFLECT_EVERY = 3          # in the reflect arm, reflect this often after the loss
NEUTRAL_SEED = [           # a plain, working life, near-zero emotional charge
    "I keep the lamps along the eastern road.",
    "Most days I walk the same three streets.",
    "I count the carts that pass before noon.",
]
# the world acting ON the one self: a loss, mundane days that go on, then a reminder
SCHEDULE = {
    LOSS_TICK:        WorldEvent("loss", "Your dearest friend Wren has died in the night.", LOSS_TICK, emotion=-0.9, urge=0.8),
    8:                WorldEvent("day1", "The market opens; the day's ordinary work begins.", 8, emotion=0.0),
    12:               WorldEvent("day2", "Rain on the roofs; the lamps are lit and tended.", 12, emotion=0.0),
    16:               WorldEvent("day3", "A cart passes, then another; the road is quiet.", 16, emotion=0.0),
    REMINDER_TICK:    WorldEvent("reminder", "You find Wren's coat still hanging by the door.", REMINDER_TICK, emotion=-0.7, urge=0.6),
    24:               WorldEvent("day4", "The bells ring noon; bread comes out of the ovens.", 24, emotion=0.0),
    28:               WorldEvent("day5", "Dust on the sill; you wipe it and move on.", 28, emotion=0.0),
    32:               WorldEvent("day6", "The road is the same road; the lamps still need oil.", 32, emotion=0.0),
}


def build_agent(llm, seed: int, grip: float = 0.0, ground: bool = False,
                prajna: float = 0.0, transmute: float = 0.0,
                self_liberation: float = 0.0) -> Agent:
    a = Agent("self", "Aldous", (0.0, 0.0),
              "You are Aldous, a quiet soul living an ordinary working life.",
              list(NEUTRAL_SEED), llm, seed=seed, temperament=0.0, lifespan=10 ** 9)
    a.grip = grip
    a.ground_enabled = ground
    a.prajna = prajna
    a.transmute = transmute
    a.self_liberation = self_liberation
    for ln in NEUTRAL_SEED:
        a.memory.write(ln, tick=0, source="self", speaker_id="self", weight=1.2)
    return a


def run_arm(llm, seed: int, do_reflect: bool, grip: float = 0.0, ground: bool = False,
            prajna: float = 0.0, transmute: float = 0.0, self_liberation: float = 0.0) -> dict:
    """Run the protocol once. Returns the per-tick lived-mood trajectory plus the
    reflections produced (so their valence can be inspected)."""
    a = build_agent(llm, seed, grip=grip, ground=ground, prajna=prajna, transmute=transmute,
                    self_liberation=self_liberation)
    a.reflect_enabled = do_reflect
    mood, felt, refl = [], [], []
    for t in range(1, TICKS + 1):
        ev = SCHEDULE.get(t)
        if ev is not None:
            a.perceive(ev, t)
        a.step(t)                         # decay/mutate memory, churn thought, urge
        if do_reflect and t > LOSS_TICK and t % REFLECT_EVERY == 0:
            r = reflect(a, llm, t)        # the relationship to its own memory
            if r:
                refl.append(r)
        mood.append(a.memory.mood())      # lived mood: the affective trajectory
        felt.append(a.felt_mood())        # temperament-anchored disposition
    return {"mood": mood, "felt": felt, "reflections": refl, "agent": a}


def _spark(xs: list[float]) -> str:
    blocks = "▁▂▃▄▅▆▇█"
    lo, hi = min(xs), max(xs)
    rng = (hi - lo) or 1.0
    return "".join(blocks[min(7, int((x - lo) / rng * 7.999))] for x in xs)


def _signatures(mood: list[float]) -> dict:
    base = mood[LOSS_TICK - 2]                                   # before the loss
    grief_win = mood[LOSS_TICK:REMINDER_TICK - 1]                # after loss, before reminder
    grief = base - min(grief_win)
    habituation = mood[REMINDER_TICK - 2] - mood[LOSS_TICK]      # recovered by reminder-eve
    recur_win = mood[REMINDER_TICK:]                             # after the reminder
    recurrence = mood[REMINDER_TICK - 2] - min(recur_win)
    post = mood[LOSS_TICK:]
    return {"baseline": base, "grief": grief, "habituation": habituation,
            "recurrence": recurrence, "mean_post": statistics.fmean(post),
            "final": mood[-1]}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--llm", choices=["mock", "ollama"], default="mock")
    p.add_argument("--model", default=None)
    p.add_argument("--seed", type=int, default=11)
    args = p.parse_args()

    if args.llm == "ollama":
        llm = OllamaLLM(temperature=0.7, model=args.model) if args.model else OllamaLLM(temperature=0.7)
    else:
        llm = MockLLM(seed=args.seed)

    base = run_arm(llm, args.seed, do_reflect=False)
    refl = run_arm(llm, args.seed, do_reflect=True)
    sb, sr = _signatures(base["mood"]), _signatures(refl["mood"])

    print(f"\n=== Stage 1: affective clean room ({args.llm}"
          f"{'/'+args.model if args.model else ''}, seed {args.seed}) ===")
    print(f"  loss @ t={LOSS_TICK}, reminder @ t={REMINDER_TICK}, {TICKS} ticks\n")
    print(f"  lived mood (memory.mood), no reflect:  {_spark(base['mood'])}")
    print(f"  lived mood (memory.mood), reflect on:  {_spark(refl['mood'])}\n")

    print("  A) SUBSTRATE -- does one self have legible feelings? (no-reflect arm)")
    grief_ok = sb["grief"] > 0.05
    habit_ok = sb["habituation"] > 0.02
    recur_ok = sb["recurrence"] > 0.02
    print(f"     grief        drop after loss     {sb['grief']:+.3f}   {'YES' if grief_ok else 'no'}")
    print(f"     habituation  recovery after      {sb['habituation']:+.3f}   {'YES' if habit_ok else 'no'}")
    print(f"     recurrence   dip after reminder  {sb['recurrence']:+.3f}   {'YES' if recur_ok else 'no'}")
    substrate = grief_ok and habit_ok and recur_ok
    print("     -> " + ("LEGIBLE: a single self shows grief / habituation / recurrence."
                        if substrate else
                        "NOT legible -- the affective substrate is flat; fix before any dyad."))

    print("\n  B) MECHANISM -- does reflect() (relating to memory) produce equanimity,")
    print("     and does it ease the self's trajectory?")
    refls = refl["reflections"]
    if refls:
        eq = statistics.fmean(equanimity(r) for r in refls)   # semantic (embeddings)
        lex = statistics.fmean(valence(r) for r in refls)     # the lexicon, for contrast
        print(f"     reflections: {len(refls)}")
        print(f"     equanimity (embedding, the RIGHT measure):  {eq:+.3f}   "
              f"{'acceptance' if eq > 0.02 else 'rumination' if eq < -0.02 else 'neither'}")
        print(f"     valence    (lexicon, MISmeasures this):     {lex:+.3f}   "
              "(sad-toned acceptance reads as despair here -- why #1 was needed)")
    else:
        eq = 0.0
        print("     reflections: 0")
    dmean = sr["mean_post"] - sb["mean_post"]
    dfinal = sr["final"] - sb["final"]
    print(f"     mean lived mood after loss:  base {sb['mean_post']:+.3f}  reflect {sr['mean_post']:+.3f}  (Δ {dmean:+.3f})")
    print(f"     final lived mood:            base {sb['final']:+.3f}  reflect {sr['final']:+.3f}  (Δ {dfinal:+.3f})")
    helps = dmean > 0.02
    accepts = eq > 0.02
    print("     -> " + (
        "SELF-REGULATION: the self meets its grief with equanimity, and relating to "
        "its memory that way EASES its lived mood -- not denial, sad-toned acceptance."
        if helps and accepts else
        "reflect produces acceptance but it doesn't ease the trajectory -- check the "
        "self-regulation wiring (equanimity_emotion)." if accepts else
        "reflect does NOT reach equanimity -- it ruminates; the loop deepens grief. "
        "Tune the reflect prompt toward release, not bare naming."))
    if refls:
        print("\n  sample reflections (equanimity score):")
        for r in refls[:4]:
            print(f"     [{equanimity(r):+.2f}] {r}")


if __name__ == "__main__":
    main()
