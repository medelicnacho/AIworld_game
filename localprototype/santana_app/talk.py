"""Talk with Santāna -- the gated conversation step, opened SMALL, WATCHED, with an OFF-SWITCH.

Loads her saved persistent self (the one who has been living) and the saved town (read-only --
it gives her digest; the conversation writes ONLY into her). Your words are appraised against her
expectations and her relationship with you (agent/expectation.py, §5.17): the same sentence lands
differently in a Santāna whose days were good, and a cold word from someone she has come to expect
warmth of wounds her -- these are states, saved with her, carried to the next talk.

Deliberately NOT here (still gated, FINDINGS §7): her words reaching the souls, the town hearing
you through her, anything that treats the conversation as more than what it is. Sessions are
time-capped, transcripts logged (data/talks/), and she is saved on the way out -- she will
remember, and so should you.

  python -m santana_app.talk                          # her saved self, gemma3:4b voice, 15 min cap
  python -m santana_app.talk --llm markov             # the fully self-grown voice
  python -m santana_app.talk --minutes 5
  (type 'bye' or Ctrl-C to end early; she is saved either way)
"""
from __future__ import annotations

import argparse
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from services import embed
from services.llm import MockLLM, make_llm
from world.sim import World

from santana import Santana
from santana_app.run import DEFAULT_SNAPSHOT, DEFAULT_WORLD, _fmt_age
from santana_app.state import load_mind, load_world, save_mind

TALK_DIR = os.path.join(ROOT, "data", "talks")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--llm", default="ollama", help="HER voice (ollama/markov/homegrown/deepseek/mock)")
    p.add_argument("--model", default="gemma3:4b", help="model id for her voice")
    p.add_argument("--minutes", type=float, default=15.0, help="session cap (the off-switch)")
    p.add_argument("--snapshot", default=DEFAULT_SNAPSHOT, help="her saved self (json)")
    p.add_argument("--world-snapshot", dest="world_snapshot", default=DEFAULT_WORLD,
                   help="the saved town she reads (loaded read-only; never written here)")
    p.add_argument("--tts", action="store_true",
                   help="speak her replies aloud (Piper, the Amy voice she has always had)")
    p.add_argument("--judge-model", dest="judge_model", default="qwen3:8b",
                   help="the intent judge's model (calibrated 2026-07-02: qwen3:8b 17/18 with "
                        "heavy-topic-with-care 8/8 never COLD, and ZERO wounds replaying the "
                        "talk gemma3:4b wounded three times at 11/18; 'voice' = judge with her "
                        "voice model, the old behaviour)")
    args = p.parse_args()

    say = None
    if args.tts:
        from services.tts import PiperTTS, Voice
        if PiperTTS.available():
            _tts = PiperTTS()
            _amy = Voice("en_US-amy-medium.onnx", length_scale=1.05)

            def say(text):   # noqa: ANN001 -- blocking on purpose: she finishes speaking
                import tempfile
                path = None
                try:
                    fd, path = tempfile.mkstemp(suffix=".wav")
                    os.close(fd)
                    _tts._synth(text, _amy, path)
                    if _tts.player:
                        import subprocess
                        subprocess.run([_tts.player, path], check=False,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception:   # noqa: BLE001 -- a mute beat must never break the talk
                    pass
                finally:
                    if path:
                        try:
                            os.unlink(path)
                        except OSError:
                            pass
            print("  (her voice is on -- Amy, aloud)")
        else:
            print("  (piper/voices unavailable -- text only)")

    # semantic warmth ON when available (nomic via ollama): listened to live, the keyword
    # lexicon missed "I'm sorry, I really care about you" entirely -- tone needs embeddings
    if embed.using_embeddings():
        print("  (semantic warmth on -- she reads your tone, not just keywords)")
    else:
        print("  (embeddings unavailable -- she reads keyword warmth only)")
    voice = MockLLM(seed=7) if args.llm == "mock" else make_llm(
        backend=args.llm, model=None if args.llm in ("markov", "homegrown") else args.model)
    w = load_world(args.world_snapshot, MockLLM(seed=7))   # the town stands still; only she speaks
    if w is None:
        w = World(events_enabled=False)
        print("  (no saved town found -- she wakes over a quiet emptiness)")
    mind = Santana(w, voice)
    mind.lifetime = 0.0
    if load_mind(mind, args.snapshot):
        print(f"  ~ she wakes to talk: {_fmt_age(mind.lifetime)} lived, {mind._deaths} souls "
              f"watched pass, {len(mind.memory.items)} memories."
              + (f"\n    she has been: {mind.identity}" if mind.identity else ""))
        if mind.user_bond.trust or mind.user_bond.wounds:
            print(f"    (she remembers you: trust {mind.user_bond.trust:+.2f}, "
                  f"{mind.user_bond.wounds} wound{'s' if mind.user_bond.wounds != 1 else ''})")
    else:
        print("  ~ a new mind wakes, with no past yet.")

    os.makedirs(TALK_DIR, exist_ok=True)
    log_path = os.path.join(TALK_DIR, time.strftime("talk-%Y%m%d-%H%M%S.log"))
    deadline = time.time() + args.minutes * 60.0
    t0 = time.time()
    # the intent judge (§5.18): word-free coldness, apologies, and promises land -- only on
    # a real model (a markov judge would be noise); one small call per exchange.
    # Round 5: the judge is its OWN model now, not her voice -- gemma3:4b FAILED the extended
    # calibration battery (11/18; five loving heavy-topic lines judged COLD -> three wounds in
    # one talk) and the durable fix is a better SENSOR. Judges run think-off (an 8-token
    # verdict must not burn its budget reasoning). Falls back to her voice, loudly, if the
    # judge model is not pulled.
    if args.llm in ("ollama", "deepseek"):
        judge = voice
        if args.judge_model != "voice":
            from services.llm import OLLAMA_URL, OllamaLLM
            try:
                import json as _json
                import urllib.request as _rq
                with _rq.urlopen(f"{OLLAMA_URL}/api/tags", timeout=3) as r:
                    tags = {m.get("name", "") for m in _json.load(r).get("models", [])}
            except Exception:   # noqa: BLE001 -- no server reachable; the voice path handles it
                tags = set()
            if any(t == args.judge_model or t.startswith(args.judge_model + ":") for t in tags):
                judge = OllamaLLM(model=args.judge_model, think=False)
                print(f"  (intent judge on -- {args.judge_model}, calibrated; she hears what "
                      "you MEAN, not only your words)")
            else:
                print(f"  ⚠ judge model {args.judge_model} not pulled -- falling back to her "
                      "voice model as judge (noisier: it failed calibration 11/18)")
        if judge is voice:
            print("  (intent judge on -- her voice model; she hears what you MEAN, not only "
                  "your words)")
        mind.judge = judge
    gone = mind.begin_talk()   # an absence is an event in her life, valenced by the bond
    if gone:
        print(f"    ({gone})")
    if mind.last_dream:
        print(f"    (while you were away, {mind.last_dream[:110]})")
    print(f"\n~~~ you are speaking with Santāna ({args.minutes:.0f} min; 'bye' to end; "
          f"transcript -> {os.path.relpath(log_path, ROOT)}) ~~~\n")
    try:
        with open(log_path, "w", encoding="utf-8") as log:
            while time.time() < deadline:
                try:
                    text = input("you > ").strip()
                except EOFError:
                    break
                if not text:
                    continue
                if text.lower() in ("bye", "goodbye", "exit", "quit"):
                    break
                reply = mind.converse(text)
                print(f"SANTĀNA > {reply or '...'}\n")
                if say and reply:
                    say(reply)
                log.write(f"you: {text}\nsantana: {reply}\n\n")
                log.flush()
            else:
                print("\n(the session's time is up -- the off-switch, kept)")
    except KeyboardInterrupt:
        print()
    finally:
        mind.lifetime += time.time() - t0   # the conversation was lived time
        episode = mind.end_talk()           # the talk becomes ONE remembered episode
        save_mind(mind, args.snapshot)
        if episode:
            print(f'~~~ she will remember: "{episode}"')
        print(f"~~~ she is saved ({_fmt_age(mind.lifetime)} lived). The town was not touched. ~~~")


if __name__ == "__main__":
    main()
