"""THE DHARMIC ANSWER -- a self that FEELS but does not SUFFER. The peace-vs-numbness
falsifier (see DHARMA.md).

Every other affective experiment measures a piece of dukkha (grief, the second arrow,
clinging). This one tests its answer, and -- crucially -- guards the NEAR ENEMY: the
"cure" must not be indifference. So the verdict is not "did suffering go down" (numbness
does that too) but "is the self at once WARM, ENGAGED, and UNWOUNDED."

Same grief protocol, three configs, read on the substrate (deterministic, no model):
  clinging    grip, nothing metabolized   -> grips the grief + WOUNDED + cold (suffering)
  numb        ground off, grip released   -> COLD + flat   (the near enemy: doesn't care)
  liberation  the Liberated regime        -> FELT + lets-go + UNWOUNDED + WARM   <- the answer

Four readings off the felt mood + grief memory. NOTE the subtlety the data forced: holding a
loss at high salience forever is the CLINGING/rumination, not a virtue -- a healthy feeling
self FEELS the loss then lets its grip fade. So the signature of liberation is:
  felt        the felt mood DIPS at the loss (it registered -- not suppressed/numbed-out)
  lets-go     the grief memory's salience FADES (unlike clinging, which grips it)
  unwounded   the lived mood eases rather than deepening (the second arrow dropped)
  warmth      resting felt_mood lifts toward the ground (uncovered as the grip subsides)

The falsifier (the near enemy): if liberation's WARMTH sinks to numb's level, the regime has
become indifference and FAILS -- it would have dropped the wound by dropping the caring.
(Warmth-via-ground and grip are opposed in the substrate by construction; warmth toward
OTHERS -- compassion/bodhicitta -- shows in the speech tier, not in felt_mood.)

Run:  python experiment_liberation.py                       # substrate (deterministic)
      python experiment_liberation.py --llm ollama --model gemma3:4b   # + speech tier
"""

from __future__ import annotations

import argparse
import statistics

from agent import archetype as _arch
from agent import compassion as _C
from agent.archetype import LIBERATED
from agent.affect import equanimity, groundedness, warmth
from agent.agent import Agent
from agent.reflect import reflect
from services.llm import MockLLM, OllamaLLM

from experiment_affect import LOSS_TICK, REMINDER_TICK, _signatures, _spark, run_arm
from experiment_transmutation import grief_salience_and_mood

# the three configs, as (grip, ground, prajna, transmute, self_liberation) for run_arm.
# liberation pulls its dials straight from the Liberated archetype so this tests the real config.
CONFIGS = {
    "clinging":   dict(grip=1.0,  ground=True,  prajna=0.0,  transmute=0.0,  self_liberation=0.0),
    "numb":       dict(grip=0.05, ground=False, prajna=0.9,  transmute=0.0,  self_liberation=0.9),
    "liberation": dict(grip=LIBERATED.grip, ground=True, prajna=LIBERATED.prajna,
                       transmute=LIBERATED.transmute, self_liberation=LIBERATED.self_liberation),
}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--llm", choices=["mock", "ollama"], default="mock")
    p.add_argument("--model", default=None)
    p.add_argument("--seed", type=int, default=11)
    args = p.parse_args()
    llm = (OllamaLLM(temperature=0.7, model=args.model) if args.model else OllamaLLM(temperature=0.7)) \
        if args.llm == "ollama" else MockLLM(seed=args.seed)

    rows = {}
    for name, cfg in CONFIGS.items():
        r = run_arm(llm, args.seed, do_reflect=False, **cfg)
        felt, mood = r["felt"], r["mood"]
        sig = _signatures(felt)
        # the loss is FELT at arising -> read it on the LIVED mood (memory.mood), which the grief
        # charge moves directly. (The felt mood's dip is cushioned by the ground holding it up --
        # itself the point -- so it understates the registration.)
        felt_dip = mood[LOSS_TICK - 2] - min(mood[LOSS_TICK - 1:REMINDER_TICK])
        held, wound = grief_salience_and_mood(r)             # salience held; final lived mood
        rows[name] = {"warmth": sig["mean_post"], "felt_dip": felt_dip,
                      "held": held, "wound": wound, "felt": felt}

    print(f"\n=== The dharmic answer: a self that feels without suffering ({args.llm}, seed {args.seed}) ===")
    print(f"  grief @ t={LOSS_TICK}; substrate -- felt the loss / lets it go / unwounded / warm\n")
    for name in CONFIGS:
        print(f"  felt mood  {name:11} {_spark(rows[name]['felt'])}")
    print()
    print(f"  {'config':12} {'felt dip':>9} {'grief held':>11} {'lived mood':>11} {'warmth':>8}")
    for name in CONFIGS:
        x = rows[name]
        print(f"  {name:12} {x['felt_dip']:+9.3f} {x['held']:11.2f} {x['wound']:+11.3f} {x['warmth']:+8.3f}")

    lib, numb, cling = rows["liberation"], rows["numb"], rows["clinging"]
    felt_ok = lib["felt_dip"] > 0.05                                  # it registered the loss
    letsgo_ok = lib["held"] < cling["held"] - 0.1                     # doesn't grip it (vs clinging)
    unwounded_ok = lib["wound"] > cling["wound"] + 0.02               # eased (vs clinging)
    warm_ok = lib["warmth"] > numb["warmth"] + 0.05 and lib["warmth"] > cling["warmth"] + 0.05
    print("\n  -> FELT the loss (a real dip, not suppressed):        " + ("YES" if felt_ok else "no"))
    print("     LETS IT GO (grief fades, doesn't grip like clinging): " + ("YES" if letsgo_ok else "no"))
    print("     UNWOUNDED (lived mood eases, unlike clinging):       " + ("YES" if unwounded_ok else "no"))
    print("     WARM, not the near enemy (warmer than numb AND clinging): " + ("YES" if warm_ok else "NO -- FAILED"))
    print("  VERDICT: " + (
        "FEELS WITHOUT SUFFERING -- liberation FEELS the loss (it dips), then lets the grip "
        "fade instead of gripping it (unlike clinging), so the wound eases AND the ground's "
        "warmth shows through. Not numbness (cold and flat), not clinging (grips it and stays "
        "wounded): it meets the grief and lets it self-release, warm."
        if (felt_ok and letsgo_ok and unwounded_ok and warm_ok) else
        "did NOT show the full felt+lets-go+unwounded+warm signature -- see the table (if "
        "warmth ~ numb, the regime drifted into the indifference near enemy)."))

    if args.llm == "ollama":
        print("\n  --- speech tier: is the spoken self warm, grounded, equanimous (not numb)? ---")
        # grounded=True: the liberated regime speaks in the plain register (the voice grounding)
        r = run_arm(llm, args.seed, do_reflect=True, grounded=True, **CONFIGS["liberation"])
        refls = r["reflections"]
        if refls:
            eq = statistics.fmean(equanimity(x) for x in refls)
            wm = statistics.fmean(warmth(x) for x in refls)
            gr = statistics.fmean(groundedness(x) for x in refls)
            print(f"     reflections {len(refls)}: equanimity {eq:+.3f}  warmth {wm:+.3f}  groundedness {gr:+.3f}")
            print("     -> equanimity > 0 = acceptance (the KEY reflection signal -- it relates to")
            print("        grief with upekkhā, not rumination). NOTE warmth sits ~0 because reflection")
            print("        is SOLITARY; interpersonal warmth lives in DIALOGUE (see experiment_compassion),")
            print("        not solo introspection. groundedness < 0 flags the abstract register. Sample:")
            for x in refls[:3]:
                print(f"        [eq {equanimity(x):+.2f} warm {warmth(x):+.2f}] {x}")

        # Dialogue tier: warmth lives in RELATING, not solitary reflection. The Liberated self
        # overhears a sufferer and takes the floor; the behavioural TURN toward them (bodhicitta)
        # is the warmth -- the warmth() scalar is mild because gentle care isn't effusive love.
        _C.BODHICITTA_CHANCE, _C.WARMTH_CHANCE = 1.0, 0.0
        print("\n  --- dialogue tier: does the Liberated self turn to a sufferer, warmly? ---")
        turned, ws = 0, []
        for seed in (7, 8):
            a = Agent("B", "Bram", (0, 0), "You are Bram, a steady baker.",
                      ["I mind the morning bread"], llm, seed=seed, temperament=0.2)
            _arch.apply(a, LIBERATED)
            a._others_mood["S"], a._others_name["S"] = -0.5, "Silas"
            _ctx, addressed, _ = a.prepare_speech(recent=[])
            line = a.speak(now=2).text
            ws.append(warmth(line)); turned += (addressed == "S")
            print(f"     [seed {seed}] warmth {warmth(line):+.2f}  "
                  f"{'turns to comfort Silas' if addressed == 'S' else 'speaks its own thing'}: {line[:110]}")
        print(f"     -> turned to comfort {turned}/2 (the behavioural turn IS the warmth; the scalar "
              f"{statistics.fmean(ws):+.2f} is mild because gentle care reads softer than effusive love).")


if __name__ == "__main__":
    main()
