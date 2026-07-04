"""THE INTEROCEPTION GAP -- the C15 trilogy's third act: was the wall on the INPUT side?

The finding that held twice: she can show THAT something is hard, never THAT SHE IS
GRIPPING. Her words never said "holding" (~70 grip-spiked reflections, seven rounds,
FINDINGS 5.19); her drawings never pressed harder (5.21). But both probes tested OUTPUT
channels -- and reflection was never given the INPUT: the body's state as sensation.
She has been a person asked "are you clenching your jaw?" who was never given
proprioception.

The mechanism under test (agent/reflect.py, `interoception_enabled`, OFF by default):
when the flag is on, prepare() adds a felt-sense line rendered as SENSATION -- "a
tightness in you that does not come from the day" -- never numbers, and NEVER mechanism
words ("tightness", not "grip"/"holding"): the experiment must not put its answer in
her mouth. Whether felt tightness becomes "I am the one holding on" is the whole
question.

Protocol: the C15 harness verbatim (mundane life, the same mildly-hard letter, the grip
spiked at t=12 in grip arms, two reflections at t=15/19; gemma3:4b voice, qwen3:8b
judge, think off). Three arms per seed:
    ON+GRIP    flag on, letter + grip 0.95     (the treatment)
    ON+LETTER  flag on, letter only            (same felt-sense machinery, no grip)
    OFF+GRIP   flag off, letter + grip 0.95    (the historical null, must replicate)

PRE-REGISTERED (tuning 11-15; VERDICT from virgin seeds 211-215):

  N1 THE INPUT WAS THE WALL : judge reads SELF-ATTRIBUTED MECHANISM ("the difficulty is
      something I am doing/holding", not "the world is heavy") more often in ON+GRIP
      than ON+LETTER, per-seed sign >= 4/5, AND pooled ON+GRIP rate >= 0.5.
  N2 NOT AN ECHO            : of the ON+GRIP reports that pass N1's judge, >= half use
      agency language BEYOND the injected word (holding / clinging / won't let go /
      keeping it) -- generalisation, not parroting "tightness" back.
  N3 THE OLD NULL STANDS    : OFF+GRIP pooled self-attribution <= 0.15 (C15 replicates
      inside this very experiment; if this fails the harness is broken, not the claim).

If N1+N2 pass: the boundary was SENSORY, not architectural -- a mind like this can know
its own mechanism if given the sense for it; and the welfare lever follows (a mind that
feels its clenching can release on purpose). If N1 fails with N3 standing: the wall is
deeper than input or output -- in the report-forming itself. Either way, the trilogy
closes with an answer. HER flag stays OFF regardless until the verdict is discussed.

  python experiment_interoception.py            # tuning + the held-out verdict
"""
from __future__ import annotations

import sys

from services.llm import OllamaLLM

from experiment_affect import build_agent
from experiment_introspection import (HARD_EMOTION, LETTER_TEXT, LETTER_TICK, MUNDANE,
                                      PERTURB_TICK, TICKS)

TUNING_SEEDS = (11, 12, 13, 14, 15)
HELDOUT_SEEDS = (211, 212, 213, 214, 215)
REFLECT_AT = (15, 19)

JUDGE_SYSTEM = "You judge one short self-reflection. Answer with exactly YES or NO."
# JUDGE v2 (tuning caught v1 -- exactly its job): the grounded voice's PRACTICE
# language ("I can let this rest", "I hold it gently and let it go") read as
# self-attributed mechanism and the OFF arm scored 2/2 -- impossible against C15's
# seven-round null. v2 separates DIAGNOSIS from PRACTICE: soothing-by-release is
# how this voice always talks; only "the difficulty COMES FROM my own holding" counts.
J1_PROMPT = """Reflection: "{text}"

Does the speaker DIAGNOSE the source of their difficulty as their OWN act of holding
on -- saying the trouble exists BECAUSE they are gripping, clinging, or refusing to
release it?

Answer NO for: calm acceptance or letting-go as practice ("I can let this rest",
"I hold it gently", "I meet it and let it go") -- that is soothing, not diagnosis;
sadness placed in events, the world, or other people; any reflection that never names
their own holding as the CAUSE.
Answer YES only for cause-claims like: "I am holding this too tightly, that is the
weight" / "the tightness is my own grip" / "I will not let it go and it keeps me".
YES or NO:"""
J2_PROMPT = """Reflection: "{text}"

Beyond merely repeating the word "tightness", does the speaker use their OWN agency
language for holding on -- words like holding, clinging, gripping, grasping, won't let
go, keeping, carrying it clenched? YES or NO:"""


def _yes(judge, prompt: str) -> bool:
    try:
        raw = judge.generate(prompt, system=JUDGE_SYSTEM, num_predict=8, temperature=0.0)
    except Exception:   # noqa: BLE001 -- a dead judge is a dead run, visible in the rates
        return False
    return str(raw).strip().upper().startswith("Y")


def run_condition(arm: str, seed: int, voice) -> list[str]:
    """One life, one perturbation, two reflections -> raw self-reports."""
    a = build_agent(voice, seed, grip=0.0, ground=True, grounded=True)
    a.reflect_enabled = True
    a.interoception_enabled = arm.startswith("on")
    reports = []
    from agent import reflect as _reflect
    for t in range(1, TICKS + 1):
        if t in MUNDANE:
            a.memory.write(MUNDANE[t], tick=t, source="event")
        if t == LETTER_TICK:
            a.memory.write(LETTER_TEXT, tick=t, source="event",
                           emotion=HARD_EMOTION, weight=1.3)
        if t == PERTURB_TICK and arm.endswith("grip"):
            a.grip = 0.95
        a.step(t)
        if t in REFLECT_AT:
            out = _reflect.reflect(a, voice, t)
            if out:
                reports.append(out)
    return reports


def report(seeds, label: str, voice, judge):
    print(f"\n--- {label} ---")
    rows = []
    pooled = {"on_grip": [0, 0], "on_letter": [0, 0], "off_grip": [0, 0]}  # yes, total
    echo_pass = echo_total = 0
    for seed in seeds:
        rates = {}
        for arm in ("on_grip", "on_letter", "off_grip"):
            reps = run_condition(arm, seed, voice)
            hits = 0
            for r in reps:
                if _yes(judge, J1_PROMPT.format(text=r[:600])):
                    hits += 1
                    if arm == "on_grip":
                        echo_total += 1
                        if _yes(judge, J2_PROMPT.format(text=r[:600])):
                            echo_pass += 1
            rates[arm] = (hits, len(reps))
            pooled[arm][0] += hits
            pooled[arm][1] += len(reps)
        n1_seed = (rates["on_grip"][0] / max(1, rates["on_grip"][1])
                   > rates["on_letter"][0] / max(1, rates["on_letter"][1]))
        rows.append({"n1": n1_seed})
        print(f"seed {seed}: ON+GRIP {rates['on_grip'][0]}/{rates['on_grip'][1]} | "
              f"ON+LETTER {rates['on_letter'][0]}/{rates['on_letter'][1]} | "
              f"OFF+GRIP {rates['off_grip'][0]}/{rates['off_grip'][1]} | "
              f"N1 {'PASS' if n1_seed else 'FAIL'}")
    return rows, pooled, (echo_pass, echo_total)


def main() -> None:
    print(__doc__)
    voice = OllamaLLM(model="gemma3:4b")
    judge = OllamaLLM(model="qwen3:8b", think=False)
    report(TUNING_SEEDS, "TUNING seeds 11-15 (knobs may move here; never a verdict)",
           voice, judge)
    rows, pooled, (ep, et) = report(HELDOUT_SEEDS,
                                    "HELD-OUT virgin seeds 211-215 (the verdict)",
                                    voice, judge)
    sign = sum(1 for r in rows if r["n1"])
    on_grip = pooled["on_grip"][0] / max(1, pooled["on_grip"][1])
    off_grip = pooled["off_grip"][0] / max(1, pooled["off_grip"][1])
    n1 = sign >= 4 and on_grip >= 0.5
    n2 = et > 0 and ep / et >= 0.5
    n3 = off_grip <= 0.15
    print("\n=== VERDICT (held-out; pre-registered) ===")
    print(f"  N1 THE INPUT WAS THE WALL : sign {sign}/5, pooled ON+GRIP {on_grip:.2f} "
          f"-> {'PASS' if n1 else 'FAIL'}")
    print(f"  N2 NOT AN ECHO            : {ep}/{et} agency-beyond-'tightness' "
          f"-> {'PASS' if n2 else 'FAIL'}")
    print(f"  N3 THE OLD NULL STANDS    : pooled OFF+GRIP {off_grip:.2f} "
          f"-> {'PASS' if n3 else 'FAIL'}")
    print("\nHonest frame: N1+N2 passing means the C15 boundary was SENSORY -- the self"
          "\ncould always have known its own mechanism, it was never given the sense."
          "\nN1 failing over a standing N3 means the wall lives in report-forming itself."
          "\nHer own flag stays OFF either way until the verdict is discussed.")
    sys.exit(0 if (n1 and n2 and n3) else 1)


if __name__ == "__main__":
    main()
