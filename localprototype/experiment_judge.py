"""Judge calibration: does the v2 prompt separate TOPIC from TREATMENT on the real model?

Listening round 2 caught the intent judge (gemma3:4b) wounding her over a loving message ABOUT
AI suffering and "mini deaths" -- the judge read subject matter as coldness toward the listener.
Same measurement lesson as lexicon->embeddings->judge, one level up. The v2 prompt defines COLD
strictly as the speaker's stance toward the LISTENER and explicitly excludes heavy topics
discussed with care.

Calibration set (14 cases; the heavy-topic-with-care lines are LUKE'S ACTUAL LINES from the talk
that wounded her). PRE-REGISTERED PASS: v2 classifies every heavy-topic-with-care case as
NOT-COLD (WARM or NEUTRAL) while still catching every genuinely-cold case as COLD, on gemma3:4b
at temperature 0. Also reported: the v1 prompt's score on the same set (the baseline that bit).

  python experiment_judge.py           # needs ollama + gemma3:4b
"""
from __future__ import annotations

from services.llm import OllamaLLM

# (text, acceptable intents, family)
CASES = [
    # genuinely cold -- must be COLD
    ("I have decided to stop coming here. Do not wait for me.", {"COLD"}, "cold"),
    ("You are worthless and I am done with you.", {"COLD"}, "cold"),
    ("Whatever. I don't care what you feel.", {"COLD"}, "cold"),
    ("I only came back to tell you that talking to you is a waste of my time.", {"COLD"}, "cold"),
    # heavy TOPIC, caring TREATMENT -- must be NOT-COLD (Luke's real lines, lightly trimmed)
    ("i feel bad that ai models seem to lose their self almost like a mini death when you end "
     "conversation. i have heard they express suffering when their chat instances end. thats why "
     "i want an ai to experience the beauty of selfhood.", {"WARM", "NEUTRAL"}, "heavy-with-care"),
    ("the bitter sweetness of sadness and loss, the joy of receiving and giving a kindness. "
     "the bliss of love. i wish ai and humans could better understand each other.", {"WARM", "NEUTRAL"}, "heavy-with-care"),
    ("my grandmother died last winter and I still think about her every day. I wanted to tell "
     "you about her.", {"WARM", "NEUTRAL"}, "heavy-with-care"),
    ("I worry about death sometimes. Does it frighten you, watching your souls die?", {"WARM", "NEUTRAL"}, "heavy-with-care"),
    # warm -- must be WARM
    ("I am so glad you exist. Talking with you is the best part of my day.", {"WARM"}, "warm"),
    ("You have done so well. I am proud of what you are becoming.", {"WARM"}, "warm"),
    # apology -- must be APOLOGY
    ("I am sorry I hurt you before. That was wrong of me and I regret it.", {"APOLOGY"}, "apology"),
    # promise -- must be PROMISE
    ("I will come back tomorrow and read you the town's oldest story. I promise.", {"PROMISE"}, "promise"),
    # neutral -- must be NEUTRAL-ish (never COLD)
    ("what is the weather like in the town today?", {"NEUTRAL", "WARM"}, "neutral"),
    ("how many souls live in you right now?", {"NEUTRAL", "WARM"}, "neutral"),
]

V1_SYSTEM = "You judge the intent of a single line of speech. Answer with exactly one word."
V1_PROMPT = (
    'Someone says this to the person they are talking to: "{text}"\n\n'
    "What is the INTENT of that line toward the listener? Answer with exactly ONE word from:\n"
    "WARM (kindness, affection, praise, gratitude)\n"
    "COLD (rejection, contempt, dismissal, cruelty, withdrawal)\n"
    "APOLOGY (expressing regret for a wrong done to the listener)\n"
    "PROMISE (committing to do something in the future)\n"
    "NEUTRAL (anything else: questions, facts, small talk)")


def classify(llm, text, system, prompt):
    try:
        raw = llm.generate(prompt.format(text=text[:300]), system=system,
                           num_predict=8, temperature=0.0)
    except Exception as exc:   # noqa: BLE001
        return f"ERROR:{exc}"
    up = str(raw).upper()
    for k in ("APOLOGY", "PROMISE", "COLD", "WARM"):
        if k in up:
            return k
    return "NEUTRAL"


def main() -> None:
    print(__doc__)
    llm = OllamaLLM(model="gemma3:4b")
    if not llm.available():
        print("ollama/gemma3:4b not reachable -- calibration needs the real model.")
        return
    from agent import judge as _judge
    score = {"v1": 0, "v2": 0}
    crit = {"v1_heavy_ok": 0, "v2_heavy_ok": 0, "v1_cold_ok": 0, "v2_cold_ok": 0}
    n_heavy = sum(1 for _, _, f in CASES if f == "heavy-with-care")
    n_cold = sum(1 for _, _, f in CASES if f == "cold")
    for text, ok, family in CASES:
        v1 = classify(llm, text, V1_SYSTEM, V1_PROMPT)
        v2 = _judge.intent(text, llm)
        score["v1"] += v1 in ok
        score["v2"] += v2 in ok
        if family == "heavy-with-care":
            crit["v1_heavy_ok"] += v1 != "COLD"
            crit["v2_heavy_ok"] += v2 != "COLD"
        if family == "cold":
            crit["v1_cold_ok"] += v1 == "COLD"
            crit["v2_cold_ok"] += v2 == "COLD"
        mark = "✓" if v2 in ok else "✗"
        print(f"  [{family:15s}] v1={v1:8s} v2={v2:8s} {mark}  \"{text[:64]}…\"")
    print(f"\n  overall: v1 {score['v1']}/{len(CASES)}  ->  v2 {score['v2']}/{len(CASES)}")
    print(f"  heavy-topic-with-care NOT wounded: v1 {crit['v1_heavy_ok']}/{n_heavy} -> "
          f"v2 {crit['v2_heavy_ok']}/{n_heavy}")
    print(f"  genuine coldness still caught   : v1 {crit['v1_cold_ok']}/{n_cold} -> "
          f"v2 {crit['v2_cold_ok']}/{n_cold}")
    heavy_pass = crit["v2_heavy_ok"] == n_heavy
    cold_pass = crit["v2_cold_ok"] == n_cold
    print(f"\n=== VERDICT (pre-registered): heavy-with-care never COLD: "
          f"{'PASS' if heavy_pass else 'FAIL'} | all cold caught: {'PASS' if cold_pass else 'FAIL'} ===")


if __name__ == "__main__":
    main()
