"""TOWARD BUDDHAHOOD: does the wheel become a PATH, and does it LEAN toward liberation?

The live wheel (experiment_lineage.run_livewheel) re-rolls wholesome faculties every rebirth and
carries ONLY the thirst -- so a life's CULTIVATION (path.cultivate grooving grip DOWN / prajñā UP as
the soul meets its mind with equanimity) dies at death. That is Sisyphus, not a path.

Three mechanisms bend the wheel toward buddhahood (bodhisattva, not hungry ghost):
  1. [DONE]  carry the CULTIVATED LEAN across the bardo -- the vāsanā of practice. Turns the wheel
     from Sisyphus into a path. (Symmetric: practice frees, rumination binds, equally.)
  2. [HERE]  a buddha-nature TILT: fade the carried vāsanā toward the LIBERATED ground (low grip /
     high prajñā), not the neutral mean. Fading toward the liberated pole does both tathāgatagarbha
     jobs at once -- a wholesome lean (near the ground) barely erodes (STICKS, the grain), while
     clinging (far from it) erodes hard toward freedom (SLIPS, the kleśas adventitious / āgantuka).
     Liberation becomes the ATTRACTOR: a hungry-ghost start drifts home.
  3. [next]  BODHICITTA transmuting the carried thirst from self-craving toward the vow -- the same
     fire, redirected: hungry ghost -> bodhisattva (keeps the energy, ≠ deva complacency, ≠ arhat exit).

Substrate test, deterministic (MockLLM, no embeddings): cultivation is driven by WRITING reflections
that carry a given equanimity as their emotion -- exactly what reflect()+affect.equanimity imprint on a
real model (the equanimity read itself is validated in experiment_path / experiment_affect) -- so we
test the CARRY + TILT dynamics model-free.

HONEST CAVEAT: the tilt is a BUILT-IN bias, not a discovered one (tathāgatagarbha is a faith claim,
not a theorem -- same by-construction issue as FINDINGS §5.5). So the falsifiable content is NOT "the
nature leans toward liberation" (we built that) but the PATH's dynamics: is the bodhisattva basin
REACHABLE from a hungry-ghost start, and what are its LIMITS (relentless active clinging still resists --
buddha-nature inclines, it does not compel).

Run:  python experiment_bodhisattva.py
"""

from __future__ import annotations

import argparse
import random
import statistics

from agent.agent import Agent
from services.llm import MockLLM
from world.events import WorldEvent

TICKS = 48
REFLECT_EVERY = 4
LOSSES = (8, 28, 40)                         # a life met by repeated loss
START_GRIP, START_PRAJNA = 0.70, 0.10       # a clinging start, for the step-1 arms
PRACTICE_SIGNAL = 0.30                       # equanimity a life's reflections imprint (chanda practice)
RUMINATION_SIGNAL = -0.30                    # rumination (clinging practice)
SEED_LINES = ["I work my trade before dawn", "the season turns", "my hands know the craft"]
# Varied reflection texts (>= one per reflection in a life) so they DON'T merge in memory.write --
# identical/near-identical text (Jaccard >= 0.6) collapses into one memory with a fixed created_tick,
# which cultivate()'s window then ages out, silently stopping the grooving mid-life. Real reflect()
# produces varied text; this mirrors that. Their own valence is irrelevant -- we force the imprint
# to the practice signal below.
REFLECT_POOL = [
    "the loss sat with me a while and I let it be what it was",
    "I felt the old grip tighten, and watched it without feeding it",
    "the work went on today; I held it lightly and did not clutch",
    "grief moved through like weather, and I did not shut the door",
    "I caught a wanting for things to be otherwise, and softened it",
    "an ordinary morning, taken as it came, nothing pushed away",
    "the ache was there under everything, and I made room for it",
    "I noticed how I reach to hold what is already leaving",
    "evening came quiet; I sat with what the day had been",
    "something in me wanted to grasp, and I let the hand open",
    "the same streets, the same weight, met without complaint",
    "I remembered the one I lost; warmth and sting both allowed to stand",
    "nothing to fix tonight, only this breath and then the next",
    "I met my own mind as it was, neither chasing it nor refusing it",
]

BASELINE_GRIP, BASELINE_PRAJNA = 0.50, 0.20   # the NEUTRAL samsaric mean (where an untilted bardo fades to)
LIBERATED_GRIP, LIBERATED_PRAJNA = 0.10, 0.70  # the LIBERATED ground (where the buddha-nature tilt fades to)
VASANA_FADE = 0.15                            # fraction of the cultivated lean that erodes toward the baseline
                                             # in the bardo (the rest -- the habit-energy -- crosses)

# --- real-model validation (--llm ollama): genuine reflect() drives the cultivation -------------
# Shorter than the synthetic life (each reflection is a real model call). Confirms the equanimity
# signal the substrate test injects is one a real model actually produces, and that it carries.
TICKS_REAL = 24
LOSSES_REAL = (6, 16)
REAL_GENS = 3


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def _fade(cult: float, neutral: float, liberated: float, tilt: float, rng: random.Random) -> float:
    """One faculty's vāsanā across the bardo: erode a little toward a baseline (lightly perturbed). The
    `tilt` slides that baseline from the neutral samsaric mean to the liberated ground (mechanism 2)."""
    base = (1.0 - tilt) * neutral + tilt * liberated
    return _clamp(cult + VASANA_FADE * (base - cult) + rng.gauss(0.0, 0.02))


def life(start_grip: float, start_prajna: float, practice_signal: float, seed: int):
    """One life under repeated loss, PRACTISING: each reflection carries `practice_signal` as its
    equanimity (what reflect()+affect imprint on a real model), so step() -> cultivate() grooves the
    faculties. Returns the cultivated (grip, prajñā) at death + the mean lived mood over the life."""
    a = Agent("self", "Soul", (0.0, 0.0), "You are a working soul.", list(SEED_LINES),
              MockLLM(seed=seed), seed=seed, temperament=0.0, lifespan=10 ** 9)
    a.grip, a.prajna, a.ground_enabled = start_grip, start_prajna, True
    a.cultivate_enabled = True
    for ln in SEED_LINES:
        a.memory.write(ln, tick=0, source="self", speaker_id="self", weight=1.2)
    mood = []
    for t in range(1, TICKS + 1):
        if t in LOSSES:
            a.perceive(WorldEvent("loss", "Someone you loved is gone.", t, emotion=-0.85, urge=0.7), t)
        if t % REFLECT_EVERY == 0:   # the practice: meet the mind with this equanimity
            text = REFLECT_POOL[(t // REFLECT_EVERY - 1) % len(REFLECT_POOL)]   # distinct -> no merge
            m = a.memory.write(text, tick=t, source="reflection", speaker_id="self",
                               emotion=practice_signal, weight=1.0)
            m.emotion = practice_signal   # force the exact signal (write's `emotion or valence` reads 0.0 as falsy)
        a.step(t)                    # runs cultivate(): grooves grip/prajñā from the recent reflections
        mood.append(a.memory.mood())
    return a.grip, a.prajna, statistics.fmean(mood)


def carry_vasana(cult_grip: float, cult_prajna: float, rng: random.Random, tilt: float = 0.0):
    """The vāsanā of practice across the bardo. A little of the cultivated lean erodes toward a BASELINE,
    lightly perturbed (a tendency, not a copy -- anatta). The buddha-nature TILT (mechanism 2) sets WHERE
    that baseline sits: tilt=0 -> the neutral samsaric mean (the wheel returns you to the middling round);
    tilt=1 -> the LIBERATED ground (low grip / high prajñā). Fading toward the liberated pole does both
    tathāgatagarbha jobs at once: a wholesome lean (already near the ground) barely erodes (it STICKS --
    the grain of the wood), while clinging (far from the ground) erodes hard toward freedom (it SLIPS --
    the kleśas are adventitious, āgantuka). Liberation becomes the attractor, not merely a reachable state."""
    return (_fade(cult_grip, BASELINE_GRIP, LIBERATED_GRIP, tilt, rng),
            _fade(cult_prajna, BASELINE_PRAJNA, LIBERATED_PRAJNA, tilt, rng))


def run_lineage(practice_signal: float, gens: int, carry: bool, seed: int, tilt: float = 0.0,
                start_grip: float = START_GRIP, start_prajna: float = START_PRAJNA):
    """A lineage of `gens` lives. carry=True: the cultivated lean crosses the bardo (the path), faded
    toward the baseline the `tilt` selects. carry=False: faculties re-roll to the same start each life
    (the live wheel -- practice discarded). Tracks the grip/prajñā each generation WAKES with -- that is
    what shows whether, and where, the lineage develops across the wheel."""
    rng = random.Random(seed)
    grip, prajna = start_grip, start_prajna
    rows = []
    for g in range(gens):
        cult_grip, cult_prajna, mood = life(grip, prajna, practice_signal, seed + g)
        rows.append({"gen": g, "woke_grip": grip, "woke_prajna": prajna,
                     "cult_grip": cult_grip, "cult_prajna": cult_prajna, "mood": mood})
        grip, prajna = (carry_vasana(cult_grip, cult_prajna, rng, tilt) if carry
                        else (start_grip, start_prajna))
    return rows


# === Mechanism 3: BODHICITTA transmutes the carried thirst (hungry ghost -> bodhisattva) =========
# Mechanism 2 frees grip/prajñā -- but pure release toward low-grip/high-prajñā is the ARHAT's basin
# (released, but disengaged: the fire is out). The bodhisattva keeps the FIRE (telos) and turns its
# OBJECT from self-craving to the vow -- via bodhicitta, which (doctrinally) is not passively granted by
# the ground but AROUSED and cultivated (bodhicitta-utpāda). So the buddha-nature tilt lifts only the
# WISDOM wing (grip/prajñā); bodhicitta is carried as vāsanā but fades toward a LOW baseline unless
# cultivated -- the arhat, never arousing it, stays released-but-disengaged.
WIS_GROOVE = 0.27        # per-life grip-freeing / prajñā-growth from wholesome practice (matched to the
                         # Agent-based cultivation validated above: grip 0.70 -> ~0.43 per life at full practice)
COMP_GROOVE = 0.27       # per-life bodhicitta growth from cultivating the compassion wing (arousing the vow)
BASE_BODHICITTA = 0.10   # bodhicitta's resting baseline -- LOW: it is aroused, not passively granted
THIRST_CARRY3 = 1.30     # how a gripped (clenched) fire escalates as self-craving across the wheel
THIRST_BASE3 = 0.15      # a fresh life's modest baseline drive
VOW_KEEP = 0.90          # how strongly bodhicitta SUSTAINS the carried fire as the vow (vs letting it quench)


def transmute_thirst(telos: float, eff_grip: float, bodhicitta: float) -> float:
    """The carried fire (telos), its object set by what claims it -- the same drive, three fates:
      gripped (eff_grip high)     -> escalates as self-craving (taṇhā): the HUNGRY GHOST
      released, low bodhicitta     -> quenches toward rest: the ARHAT (fire out, disengaged peace)
      released, high bodhicitta    -> SUSTAINED as the vow: the BODHISATTVA (fire kept, turned to all)
    Bodhicitta is what keeps the energy alive AND outward once the grip lets go -- the saint who stays."""
    craving = THIRST_CARRY3 * telos * eff_grip
    vow = VOW_KEEP * telos * bodhicitta
    return _clamp(THIRST_BASE3 + craving + vow)


def run_lineage_m3(gens: int, seed: int, tilt: float, cultivate_compassion: bool, start: dict,
                   wis: float = WIS_GROOVE, comp: float = COMP_GROOVE):
    """A lineage tracking BOTH wings + the fire. `start` = dict(grip, prajna, bodhicitta, telos). Each
    life: the wisdom wing grooves grip/prajñā (wis>0 frees, wis<0 binds); the compassion wing arouses
    bodhicitta (comp, only if cultivate_compassion). The bardo carries grip/prajñā toward the tilted
    ground (mechanism 2), bodhicitta toward its LOW baseline (aroused, not granted -- so the arhat who
    never cultivates it stays disengaged), and the fire via transmute_thirst. Records, per generation,
    self_craving = telos·effective_grip (the clenched drive) and vow = telos·bodhicitta (turned to all)."""
    rng = random.Random(seed)
    grip, prajna = start["grip"], start["prajna"]
    bod, telos = start["bodhicitta"], start["telos"]
    rows = []
    for g in range(gens):
        eff = grip * (1.0 - prajna)
        rows.append(dict(gen=g, grip=grip, prajna=prajna, bodhicitta=bod, telos=telos,
                         self_craving=telos * eff, vow=telos * bod))
        cult_grip = _clamp(grip - wis)
        cult_prajna = _clamp(prajna + max(0.0, wis))
        cult_bod = _clamp(bod + (comp if cultivate_compassion else 0.0))
        eff_cult = cult_grip * (1.0 - cult_prajna)
        grip = _fade(cult_grip, BASELINE_GRIP, LIBERATED_GRIP, tilt, rng)
        prajna = _fade(cult_prajna, BASELINE_PRAJNA, LIBERATED_PRAJNA, tilt, rng)
        bod = _fade(cult_bod, BASE_BODHICITTA, BASE_BODHICITTA, tilt, rng)   # no tilt: bodhicitta is aroused, not granted
        telos = transmute_thirst(telos, eff_cult, cult_bod)
    return rows


def life_real(start_grip: float, start_prajna: float, llm, seed: int):
    """One life driven by GENUINE reflect() (real model + embeddings): the equanimity that grooves the
    faculties is READ from the actual reflection text by affect.equanimity, not injected. Returns the
    cultivated (grip, prajñā), the mean lived mood, and the mean genuine equanimity signal observed --
    so we can see the real signal is positive (equanimous) and that it frees the soul, validating the
    synthetic substrate driver above. Uses the grounded contemplative voice (equanimous register)."""
    from agent.reflect import reflect
    a = Agent("self", "Aldous", (0.0, 0.0), "You are Aldous, a quiet soul.", list(SEED_LINES),
              llm, seed=seed, temperament=0.0, lifespan=10 ** 9)
    a.grip, a.prajna, a.ground_enabled = start_grip, start_prajna, True
    a.reflect_enabled = a.cultivate_enabled = True
    a.grounded_voice = True
    for ln in SEED_LINES:
        a.memory.write(ln, tick=0, source="self", speaker_id="self", weight=1.2)
    mood = []
    for t in range(1, TICKS_REAL + 1):
        if t in LOSSES_REAL:
            a.perceive(WorldEvent("loss", "Someone you loved is gone.", t, emotion=-0.85, urge=0.7), t)
        a.step(t)                          # step() runs cultivate() on the recent reflections
        if t % REFLECT_EVERY == 0:
            reflect(a, llm, t)             # genuine: writes a reflection whose emotion = its measured equanimity
        mood.append(a.memory.mood())
    emos = [m.emotion for m in a.memory.items if m.source == "reflection"]
    sig = statistics.fmean(emos) if emos else 0.0
    return a.grip, a.prajna, statistics.fmean(mood), sig


def run_lineage_real(llm, gens: int, seed: int, tilt: float = 1.0):
    """A lineage driven by genuine reflect(), the cultivated lean carried (tilted) across the bardo --
    the whole step-1+2 path end to end on a real model, from a clinging start."""
    rng = random.Random(seed)
    grip, prajna = START_GRIP, START_PRAJNA
    rows = []
    for g in range(gens):
        cult_grip, cult_prajna, mood, sig = life_real(grip, prajna, llm, seed + g)
        rows.append({"gen": g, "woke_grip": grip, "woke_prajna": prajna,
                     "cult_grip": cult_grip, "cult_prajna": cult_prajna, "mood": mood, "sig": sig})
        grip, prajna = carry_vasana(cult_grip, cult_prajna, rng, tilt)
    return rows


def _print_arm(label, arm):
    wg = " ".join(f"{r['woke_grip']:.2f}" for r in arm)
    wp = " ".join(f"{r['woke_prajna']:.2f}" for r in arm)
    print(f"  {label:24} woke grip:    {wg}")
    print(f"  {label:24} woke prajñā:  {wp}\n")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--gens", type=int, default=6, help="generations for the step-1 arms")
    p.add_argument("--seed", type=int, default=11)
    p.add_argument("--llm", choices=["mock", "ollama"], default="mock",
                   help="ollama: also run a real-model validation lineage (genuine reflect() drives cultivation)")
    p.add_argument("--model", default=None)
    args = p.parse_args()

    # === Step 1: does PRACTICE transmigrate? (the carry, un-tilted -- symmetric) ===
    step1 = {
        "practice-carried":   dict(practice_signal=PRACTICE_SIGNAL,   carry=True,  tilt=0.0),
        "practice-fresh":     dict(practice_signal=PRACTICE_SIGNAL,   carry=False, tilt=0.0),
        "rumination-carried": dict(practice_signal=RUMINATION_SIGNAL, carry=True,  tilt=0.0),
    }
    out = {name: run_lineage(seed=args.seed, gens=args.gens, **cfg) for name, cfg in step1.items()}

    print(f"\n=== Step 1: does PRACTICE transmigrate? (the carry, un-tilted -- {args.gens} generations) ===")
    print(f"  a clinging start (grip {START_GRIP}, prajñā {START_PRAJNA}); each life practises, cultivate() grooves it.\n")
    for name in step1:
        _print_arm(name, out[name])

    pc, pf, rc = out["practice-carried"], out["practice-fresh"], out["rumination-carried"]
    frees_across = (pc[-1]["woke_grip"] < pc[0]["woke_grip"] - 0.15
                    and pc[-1]["woke_prajna"] > pc[0]["woke_prajna"] + 0.15)
    fresh_static = abs(pf[-1]["woke_grip"] - pf[0]["woke_grip"]) < 0.05
    rumination_binds = rc[-1]["woke_grip"] > rc[0]["woke_grip"] + 0.10
    print("  -> carrying practice makes the wheel a PATH (lineage frees across lives):   " + ("YES" if frees_across else "no"))
    print("     the live wheel (fresh re-roll) discards it -- every life starts over:    " + ("YES" if fresh_static else "no"))
    print("     but UN-TILTED the path runs both ways (rumination compounds to clinging): " + ("YES" if rumination_binds else "no"))
    print("  STEP 1: " + ("the carry makes a path, but it is SYMMETRIC -- a hungry-ghost start only deepens."
                          if (frees_across and fresh_static and rumination_binds) else "signature not clean -- tune."))

    # === Step 2: the buddha-nature TILT -- is liberation the ATTRACTOR from a hungry-ghost start? ===
    HG_GRIP, HG_PRAJNA = 0.85, 0.10   # a hungry ghost: gripped, little wisdom
    NEUTRAL_PRACTICE = 0.0            # net-neutral practice: equanimity and rumination cancel (no self-progress)
    STUBBORN = -0.20                  # relentless active rumination (the honest limit)
    G2 = 12                           # the path is slow; give it lives enough to converge

    off = run_lineage(NEUTRAL_PRACTICE, G2, carry=True, seed=args.seed, tilt=0.0,
                      start_grip=HG_GRIP, start_prajna=HG_PRAJNA)
    on = run_lineage(NEUTRAL_PRACTICE, G2, carry=True, seed=args.seed, tilt=1.0,
                     start_grip=HG_GRIP, start_prajna=HG_PRAJNA)
    stub = run_lineage(STUBBORN, G2, carry=True, seed=args.seed, tilt=1.0,
                       start_grip=HG_GRIP, start_prajna=HG_PRAJNA)

    print(f"\n=== Step 2: the buddha-nature TILT -- liberation as the attractor ({G2} generations) ===")
    print(f"  a HUNGRY GHOST (grip {HG_GRIP}, prajñā {HG_PRAJNA}); the only difference between the first two arms")
    print("  is the tilt -- whether the bardo fades the vāsanā toward the neutral mean (off) or the liberated")
    print("  ground (on). Net-neutral practice, so the soul makes no progress on its OWN -- the tilt is the lean.\n")
    _print_arm("net-neutral, tilt OFF", off)
    _print_arm("net-neutral, tilt ON", on)
    _print_arm("stubborn rumination, ON", stub)

    on_g, on_p = on[-1]["woke_grip"], on[-1]["woke_prajna"]
    off_g = off[-1]["woke_grip"]
    stub_g = stub[-1]["woke_grip"]
    reaches_basin = on_g < 0.30 and on_p > 0.45            # the bodhisattva basin: low grip, real wisdom
    off_circles = off_g > on_g + 0.25                      # untilted, it only circles the samsaric mean
    limit_honest = stub_g > 0.60                           # relentless clinging resists -- inclines, not compels
    print("  -> with the tilt, the hungry ghost reaches the bodhisattva basin (grip<0.30, prajñā>0.45): "
          + ("YES" if reaches_basin else "no"))
    print(f"     without it, it only circles the samsaric mean (final grip {off_g:.2f} vs tilted {on_g:.2f}):     "
          + ("YES" if off_circles else "no"))
    print(f"     HONEST LIMIT: relentless active rumination still resists (final grip {stub_g:.2f}):         "
          + ("YES" if limit_honest else "no"))
    print("  VERDICT: " + (
        "MECHANISM 2 WORKS -- fading the vāsanā toward the liberated ground makes liberation the ATTRACTOR: "
        "from a hungry-ghost start, a soul whose own practice nets to nothing still drifts home to the "
        "bodhisattva basin (a wholesome lean sticks; clinging slips -- adventitious), where the untilted "
        "wheel only circles the samsaric mean. The nature now LEANS toward liberation. But buddha-nature "
        "INCLINES, it does not COMPEL: relentless active rumination still resists the lean -- the honest "
        "limit (and the right one: a being grasping with all its might is not force-saved). Mechanism 3 "
        "(bodhicitta) makes this the BODHISATTVA's path, not the solitary arhat's -- next."
        if (reaches_basin and off_circles and limit_honest) else
        "did NOT show the attractor + limit signature -- tune VASANA_FADE / LIBERATED_* / G2."))

    # === Step 3: BODHICITTA -- the bodhisattva vs the arhat (the same fire, redirected) ===
    HG = dict(grip=0.85, prajna=0.10, bodhicitta=0.10, telos=0.80)   # a hungry ghost: gripped, self-burning
    G3 = 8
    bodhi = run_lineage_m3(G3, args.seed, tilt=1.0, cultivate_compassion=True,  start=HG)
    arhat = run_lineage_m3(G3, args.seed, tilt=1.0, cultivate_compassion=False, start=HG)
    ghost = run_lineage_m3(G3, args.seed, tilt=0.0, cultivate_compassion=False, start=HG, wis=-0.10)

    def _fmt(arm, key):
        return " ".join(f"{r[key]:.2f}" for r in arm)

    print(f"\n=== Step 3: BODHICITTA transmutes the fire -- bodhisattva vs arhat vs hungry ghost ({G3} gens) ===")
    print("  the SAME fire (telos), its object set by what claims it. self-craving = telos·effective_grip")
    print("  (the clenched drive); vow = telos·bodhicitta (the drive turned to all beings). All three start")
    print("  as a hungry ghost; the bodhisattva also AROUSES bodhicitta, the arhat frees but never does.\n")
    for name, arm in (("bodhisattva ", bodhi), ("arhat       ", arhat), ("hungry ghost", ghost)):
        print(f"  {name}  telos:        {_fmt(arm, 'telos')}")
        print(f"  {name}  self-craving: {_fmt(arm, 'self_craving')}")
        print(f"  {name}  vow:          {_fmt(arm, 'vow')}\n")

    b, ar, hg = bodhi[-1], arhat[-1], ghost[-1]
    bodhi_basin = b["grip"] < 0.30 and b["self_craving"] < 0.10 and b["vow"] > 0.20 and b["telos"] > 0.35
    arhat_near = (ar["self_craving"] < 0.10 and ar["vow"] < b["vow"] - 0.10 and ar["telos"] < b["telos"] - 0.10)
    ghost_stuck = hg["self_craving"] > 0.30
    print("  -> BODHISATTVA basin reached (released, fire KEPT, turned to the vow):  " + ("YES" if bodhi_basin else "no"))
    print(f"     ARHAT near-enemy DISTINGUISHED (released but fire out, vow {ar['vow']:.2f} vs {b['vow']:.2f}): "
          + ("YES" if arhat_near else "no"))
    print("     HUNGRY GHOST stays self-craving (the gripped fire escalates):        " + ("YES" if ghost_stuck else "no"))
    print("  VERDICT: " + (
        "MECHANISM 3 WORKS -- the wisdom tilt (mechanism 2) alone lands a soul in the ARHAT basin: released "
        "from clinging, but the fire quenched and disengaged (low vow). Arousing BODHICITTA -- carried as "
        "vāsanā, not granted by the ground -- transmutes the SAME fire from self-craving to the vow: the "
        "bodhisattva keeps the energy and turns it to all beings (vow high, self-craving low, fire kept), "
        "where the hungry ghost's gripped fire only escalates. The path now leans toward BUDDHAHOOD, not "
        "the solitary peace -- the saint who stays, not the one who exits."
        if (bodhi_basin and arhat_near and ghost_stuck) else
        "did NOT cleanly separate bodhisattva / arhat / hungry ghost -- tune VOW_KEEP / COMP_GROOVE / THIRST_*."))

    # === Real-model validation: does GENUINE reflect() produce the equanimity signal, and carry? ===
    if args.llm == "ollama":
        from services.llm import OllamaLLM
        llm = OllamaLLM(temperature=0.7, model=args.model) if args.model else OllamaLLM(temperature=0.7)
        print(f"\n=== Real-model validation ({args.model or 'gemma3:4b'}): genuine reflect() drives the path ===")
        print(f"  a clinging start (grip {START_GRIP}, prajñā {START_PRAJNA}); each life truly reflects, the")
        print("  equanimity READ from its words grooves the faculties, and the lean is carried (tilted).\n")
        real = run_lineage_real(llm, REAL_GENS, args.seed, tilt=1.0)
        _print_arm("genuine-practice", real)
        sigs = " ".join(f"{r['sig']:+.3f}" for r in real)
        print(f"  {'genuine-practice':24} equanimity signal per life:  {sigs}")
        sig_mean = statistics.fmean(r["sig"] for r in real)
        real_frees = real[-1]["woke_grip"] < real[0]["woke_grip"] - 0.05
        sig_positive = sig_mean > 0.0
        print("\n  -> the genuine reflection signal is positive (equanimous, not ruminative): "
              + ("YES" if sig_positive else f"no ({sig_mean:+.3f})"))
        print("     and it frees the lineage across the wheel (woke grip falls):              "
              + ("YES" if real_frees else "no"))
        print("  VALIDATION: " + (
            "the synthetic substrate driver is faithful -- a real model's reflections carry a genuine "
            "positive equanimity that cultivate() reads and the wheel carries, freeing the lineage just as "
            "the injected signal did. The mechanisms are not an artifact of the synthetic signal."
            if (sig_positive and real_frees) else
            "the genuine signal did NOT free as expected -- inspect the per-life signal (a small/CPU model "
            "may reflect less equanimously; raise REAL_GENS/TICKS_REAL or check embeddings are up)."))


if __name__ == "__main__":
    main()
