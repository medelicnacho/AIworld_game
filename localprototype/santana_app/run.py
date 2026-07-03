"""Santāna, living -- a clean, continuous, PERSISTENT runner.

This is the focused 'Santāna app' (separate from the experiment-laden santana.py): build a
living town under her, let her read and speak it, and -- the point -- SAVE her self as she
goes, so each run she wakes older, carrying who she has become. Built to run unattended on a
server. The town can speak in any backend; default is the fully self-grown 'markov' voice
(nothing leaves the machine).

  python -m santana_app.run                                   # markov town + her, persistent
  python -m santana_app.run --llm deepseek --town-model deepseek-v4-flash --interval 8
  python -m santana_app.run --fresh                           # start a new life (ignore the snapshot)

Ctrl-C to stop; she is saved on the way out. State: data/santana_state.json (see state.py).
"""
from __future__ import annotations

import argparse
import os
import random
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from agent import genesis as _genesis
from agent.agent import Agent
from services import embed
from services.llm import MockLLM, SoulVoiceLLM, make_llm
from world.sim import World

from santana import Santana, play_two_layer
from santana_app.state import LifeBusy, acquire_life, load_mind, load_world, save_mind, save_world

DEFAULT_SNAPSHOT = os.path.join(ROOT, "data", "santana_state.json")
DEFAULT_WORLD = os.path.join(ROOT, "data", "santana_world.pkl")


def _fmt_age(seconds: float) -> str:
    """Her REAL age -- how long she has actually existed (not a per-reading 'day')."""
    d = seconds / 86400.0
    if d >= 1:
        return f"{d:.1f} days"
    h = seconds / 3600.0
    return f"{h:.1f} hours" if h >= 1 else f"{seconds/60:.0f} minutes"

CAST = [("Vesper", "brewer", 0.2, "brew an ale worth the festival"),
        ("Mara", "farmer", 0.4, "bring in a full harvest"),
        ("Toll", "scribe", -0.3, "finish the town charter"),
        ("Cael", "fisher", 0.3, "read the water so I never come back empty"),
        ("Silas", "healer", -0.1, "ease the fever in the low houses"),
        ("Juno", "shepherd", 0.1, "keep the flock through the winter")]


def _make_voice(name: str, model: str | None, culture: bool = False):
    if name == "mock":
        return MockLLM(seed=7)
    return make_llm(backend=name, model=model, culture=culture)


def town_voice(town_model: str | None, world_snapshot: str, culture: bool = False):
    """The ONE town-voice selector -- the runner and the window share it (the audit found
    them drifting apart the same way the three duplicated runners once did). Resolves the
    backend, falls back LOUDLY from the default 'soul' to markov on a box without torch,
    and pins per-soul minds NEXT TO their world snapshot so a probe or scratch town can
    never leak trained brains into her real souls (they share ids s0..s5).
    Returns (llm, effective_town_model)."""
    _local = ("markov", "homegrown", "soul")
    try:
        llm = (MockLLM(seed=7) if town_model in (None, "mock")
               else _make_voice(town_model if town_model in _local else "deepseek",
                                None if town_model in _local else town_model,
                                culture=culture))
    except RuntimeError as exc:
        if town_model != "soul":
            raise
        print(f"  ⚠ {exc}\n  ⚠ falling back to the markov town voice", flush=True)
        town_model = "markov"
        llm = _make_voice("markov", None, culture=culture)
    if isinstance(llm, SoulVoiceLLM):
        llm.dir = os.path.splitext(world_snapshot)[0] + ".minds"
    return llm, town_model


def build_world(town_llm, fast_wheel: bool, psyche: bool = False) -> World:
    rng = random.Random(7)
    w = World(rebirth_enabled=True)
    w.llm = town_llm
    w.stakes_enabled = True
    w.bardo_ticks = (4, 10)
    w.bodhisattva_wheel = True       # the full path runs under her: the lean toward liberation
    w.liberation_tilt = 1.0
    span = (lambda: rng.randint(120, 260)) if fast_wheel else (lambda: rng.randint(2000, 5000))
    # --psyche: the streams are PARTS OF ONE MIND (drives), not townsfolk -- see agent/psyche.py
    if psyche:
        from agent.psyche import PSYCHE_CAST
        roster = PSYCHE_CAST
    else:
        roster = [(n, r, t, a, None) for (n, r, t, a) in CAST]
    for i, (name, role, temp, aim, seeds) in enumerate(roster):
        phrases = list(seeds) if seeds else [f"I am {name} the {role}", aim]
        persona = (f"You are {name}, {role} -- a part of one mind, not a person."
                   if psyche else f"You are {name} the {role}.")
        # parts of one mind share one place (all in earshot of each other -- one inner
        # conversation); townsfolk are scattered across the map as before
        pos = ((450 + rng.uniform(-20, 20), 300 + rng.uniform(-20, 20)) if psyche
               else (rng.uniform(0, 900), rng.uniform(0, 600)))
        a = Agent(f"s{i}", name, pos,
                  persona, phrases, town_llm, seed=i, temperament=temp, lifespan=span())
        if psyche:
            # the FUNCTIONAL psyche (PSYCHE.md): each part carries ONE faculty, loud
            from agent import psyche as _psyche
            _psyche.endow_part(a, _psyche.FACULTY_OF.get(name, ""), a._rng)
        else:
            _genesis.endow_faculties(a, a._rng)
        a.role, a.aim = role, aim
        w.add(a)
    if psyche:
        # the global workspace: parts bid for the floor each tick; the winner is the
        # mind's focus/voice and the faculty couplings run (see agent/workspace.py)
        from agent.workspace import Workspace
        w.psyche = Workspace()
    return w


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--llm", default="markov", help="HER voice (markov/homegrown/ollama/deepseek/mock)")
    p.add_argument("--model", default=None, help="model id for her voice (deepseek/ollama)")
    p.add_argument("--town-model", dest="town_model", default="soul",
                   help="the TOWN's voice. Default 'soul': every NPC carries its OWN tiny "
                        "from-scratch GPT -- born babbling at rebirth, grown by sleep on its "
                        "own decaying memory, forever learning and forgetting (needs torch; "
                        "falls back to markov, loudly). Also: markov/homegrown/mock, or a "
                        "deepseek model id")
    p.add_argument("--interval", type=float, default=6.0, help="seconds the town lives between her readings")
    p.add_argument("--fast-wheel", action="store_true", dest="fast_wheel",
                   help="short lifespans so the wheel turns quickly (souls die + are reborn)")
    p.add_argument("--psyche", action="store_true",
                   help="the souls are PARTS OF ONE MIND (drives: Dread, Ache, Longing...) not townsfolk "
                        "-- a self as a society of parts (see agent/psyche.py)")
    p.add_argument("--sleep-every", dest="sleep_every", type=float, default=75.0,
                   help="(soul town) seconds between NPC sleeps -- each sleep, ONE soul "
                        "absorbs its own living memory into its own tiny brain (bounded burst; "
                        "round-robin, so a 6-soul town fully consolidates every ~8 minutes)")
    p.add_argument("--readings", type=int, default=0, help="stop after N readings (0 = run forever)")
    p.add_argument("--autosave", type=int, default=5, help="save every N readings")
    p.add_argument("--snapshot", default=DEFAULT_SNAPSHOT, help="where HER self is saved/resumed (json)")
    p.add_argument("--world-snapshot", dest="world_snapshot", default=DEFAULT_WORLD,
                   help="where the TOWN is saved/resumed -- so the wheel survives restarts. "
                        "Stored as portable JSON (world/serialize.py); a legacy .pkl at this "
                        "path wakes once and migrates on the next save")
    p.add_argument("--fresh", action="store_true", help="ignore any saved life/town and start new")
    p.add_argument("--tts", action="store_true", help="speak her aloud (Piper) as well as printing")
    p.add_argument("--offer", action="store_true",
                   help="STAGE ONE of the gated top-down loop (§5.18): her settled line is OFFERED "
                        "to the town as a STORY in the lore channel -- 2 souls, low weight, dark "
                        "charge transmuted; it must compete like any legend and can be ignored. "
                        "Implies --lore-town so the channel exists. The ring test "
                        "(experiment_ring.py) gates this design; keep it off unless you mean it.")
    p.add_argument("--culture", action="store_true",
                   help="memetic culture (FINDINGS §5.13): her voice moves through shifting cultural ERAS "
                        "-- selection + self-limiting fitness over motifs -- instead of averaging")
    p.add_argument("--demiurge", action="store_true",
                   help="an 8B (ollama) dreams up NEW souls at rebirth + seeds a living corpus the "
                        "markov + consolidation read (novelty injection -- see services/demiurge.py)")
    p.add_argument("--author-model", dest="author_model",
                   default="mannix/llama3.1-8b-abliterated:q5_K_M", help="the Demiurge's ollama model")
    args = p.parse_args()

    # ONE writer at a time (state.acquire_life): a talk or window holding her open would be
    # silently overwritten by our autosave -- refuse loudly instead, before touching anything.
    try:
        life = acquire_life(args.snapshot, "the 24/7 runner (santana_app.run)")
    except LifeBusy as busy:
        print(f"\n  ⚠ {busy}\n")
        raise SystemExit(1)

    embed.use_jaccard_only(True)   # the town runs embedding-free so it never competes with her voice
    santana_llm = _make_voice(args.llm, args.model, culture=args.culture)
    town_llm, args.town_model = town_voice(args.town_model, args.world_snapshot,
                                           culture=args.culture)
    real_town = args.town_model not in (None, "mock")

    # resume the WHOLE town if we can (so the wheel keeps turning across restarts), else build fresh
    w = None if args.fresh else load_world(args.world_snapshot, town_llm)
    resumed_town = w is not None
    if w is None:
        w = build_world(town_llm, args.fast_wheel, psyche=args.psyche)
    elif args.psyche and getattr(w, "psyche", None) is None:
        # a world resumed from before the workspace existed: attach one (a no-op
        # unless the resumed agents actually carry psyche faculties)
        from agent.workspace import Workspace
        w.psyche = Workspace()
    w.mourning_enabled = True   # in HER town, a death lands on the bonded -- grief has
                                # always been hers alone; now the souls carry it too
    if args.offer:
        # her offerings need the retelling channel to compete in -- and to be forgettable
        w.lore_enabled = True
        print("  ⚠ STAGE ONE coupling ON: her voice enters the town as stories (lore channel).")
    mind = Santana(w, santana_llm, culture=args.culture)
    mind.lifetime = 0.0

    if not args.fresh and load_mind(mind, args.snapshot):
        print(f"  ~ Santāna wakes into a saved life: she has existed {_fmt_age(mind.lifetime)}, watched "
              f"{mind._deaths} souls die, and carries {len(mind.memory.items)} memories. The town "
              f"{'continued turning' if resumed_town else 'is new'} (tick {w.tick}, {w._births} reborn).")
        if mind.identity:
            print(f"    she was: {mind.identity}")
    else:
        print("  ~ a new mind wakes, with no past yet.")

    demiurge = None
    if args.demiurge:
        from services.demiurge import Demiurge
        demiurge = Demiurge(model=args.author_model, psyche=args.psyche)
        if not demiurge.available():
            print(f"  (--demiurge: ollama/model '{args.author_model}' not reachable -- running without it)")
            demiurge = None
        else:
            print(f"  ✦ the Demiurge wakes ({args.author_model}) -- it will dream new souls at rebirth")

    stop = threading.Event()

    def _fail_reporter(label: str, every: int = 500):
        """Contain-but-REPORT. A bare `except: pass` here once hid an AttributeError that
        froze the entire wheel for 171k ticks -- her whole overnight town was a diorama and
        nothing said so. A bad tick must never kill the life, but it must never be silent:
        full traceback on the first failure, a one-line pulse every `every` after."""
        import traceback
        count = [0]

        def report():
            count[0] += 1
            if count[0] == 1:
                print(f"\n  ⚠ {label} FAILED -- her world may be half-stalled:", flush=True)
                traceback.print_exc()
            elif count[0] % every == 0:
                print(f"  ⚠ {label} still failing ({count[0]}x)", flush=True)
        return report

    def run_wheel():
        report = _fail_reporter("wheel tick")
        while not stop.is_set():
            try:
                with w.lock:
                    w.step(speak=not real_town)
            except Exception:   # noqa: BLE001 -- a bad tick must never kill the life
                report()
            time.sleep(0.15)

    def run_speech():
        report = _fail_reporter("town speech turn", every=50)
        while not stop.is_set():
            try:
                w.speak_turn()   # the LLM call runs OUTSIDE the lock -> the wheel never waits
            except Exception:   # noqa: BLE001
                report()
            time.sleep(0.6)

    def run_reflect():
        # psyche mode: the Watcher practices -- one reflection every so often, imprinted
        # on itself and BROADCAST mind-wide (World.reflect_turn); the mind seeing itself
        report = _fail_reporter("reflect turn", every=20)
        while not stop.is_set():
            time.sleep(12.0)
            try:
                w.reflect_turn()
            except Exception:   # noqa: BLE001
                report()

    def run_sleep():
        # THE SLEEP CYCLE (soul town): one soul at a time absorbs its own living memory
        # into its own tiny brain. The corpus snapshot is taken UNDER the world lock; the
        # slow training burst (seconds) runs with NO lock held -- the speak_turn contract.
        # Learning and forgetting, continuously: what decayed out of memory since the last
        # sleep simply is not in this one, and the weights drift on. Newborn streams get a
        # fresh mind at their first turn and keep babbling until they have lived enough to
        # dream (sleep_text returns None below the corpus floor).
        report = _fail_reporter("npc sleep", every=20)
        turn = 0
        while not stop.is_set():
            if stop.wait(args.sleep_every):
                break
            try:
                with w.lock:
                    souls = sorted(w.agents, key=lambda a: a.id)
                if not souls:
                    continue
                soul = souls[turn % len(souls)]
                turn += 1
                with w.lock:
                    corpus = "\n".join([soul.persona] + [m.text for m in soul.memory.items])
                    n_mem = len(soul.memory.items)
                    residue = (max(soul.memory.items, key=lambda m: m.salience).text
                               if soul.memory.items else soul.persona)   # the day's residue
                out = town_llm.sleep_text(soul.id, corpus)   # the slow burst, no lock held
                if out is not None:
                    first, last = out
                    mind = town_llm.mind_for(soul.id)
                    print(f"  (sleep: {soul.name} absorbs {n_mem} memories -- "
                          f"loss {first:.2f}→{last:.2f}, sleep #{mind.sleeps})", flush=True)
                    # every third sleep the soul DREAMS, in its own grown voice: generated
                    # with no lock held, written back under it, tagged source='dream' --
                    # so it says 'I dreamt it, I think' at recall (§5.19), and a worn dream
                    # can leak into believed memory by the measured pathway
                    dream = town_llm.dream_line(soul.id, residue)
                    if dream:
                        with w.lock:
                            soul.memory.write(dream, tick=w.tick, source="dream",
                                              speaker_id=soul.id, weight=0.9)
                        print(f"  (dream: {soul.name} dreams -- \"{dream[:90]}\")", flush=True)
                with w.lock:
                    live = {a.id for a in w.agents}
                town_llm.prune(live)   # a departed soul's mind leaves RAM; the file remains
            except Exception:   # noqa: BLE001 -- a failed dream must never kill the life
                report()

    def run_demiurge():
        # the 8B author: on rebirth, dream a NEW soul, write it onto the reborn stream, and feed the
        # living corpus (the markov + the nightly consolidation read it). The slow 8B call runs OUTSIDE
        # the lock; only the fast field-write is locked. Throttled, so it stays a minority of the voice.
        authored: set[str] = set()
        _demiurge_report = _fail_reporter("demiurge dream", every=20)
        while not stop.is_set():
            time.sleep(2.0)
            try:
                with w.lock:
                    cands = sorted((a for a in w.agents
                                    if a.id.startswith("stream:") and a.id not in authored),
                                   key=lambda a: int(a.id.split(":")[1]))
                if not cands:
                    continue
                target = cands[-1].id          # the newest unauthored reborn stream
                authored.add(target)
                soul = demiurge.invent()        # the SLOW 8B call -- OUTSIDE the lock
                if not soul:
                    continue
                with w.lock:
                    tgt = next((a for a in w.agents if a.id == target), None)
                    if tgt is not None:
                        demiurge.apply(tgt, soul, w.tick)
                demiurge.seed_corpus(soul)
                print(f"\n  ✦ the Demiurge dreams {soul['name']} the {soul['role']} -- {soul['aim']} "
                      f"({len(soul['lines'])} lines into the living corpus)", flush=True)
                time.sleep(15.0)               # bound the 8B to a MINORITY injection
            except Exception:   # noqa: BLE001 -- the author must never kill the life
                _demiurge_report()
                time.sleep(5.0)

    threads = [threading.Thread(target=run_wheel, daemon=True)]
    if real_town:
        threads.append(threading.Thread(target=run_speech, daemon=True))
    if isinstance(town_llm, SoulVoiceLLM):
        threads.append(threading.Thread(target=run_sleep, daemon=True))
    if args.psyche:
        threads.append(threading.Thread(target=run_reflect, daemon=True))
    if demiurge is not None:
        threads.append(threading.Thread(target=run_demiurge, daemon=True))
    for t in threads:
        t.start()

    def save_both():
        save_mind(mind, args.snapshot)
        save_world(w, args.world_snapshot)

    print(f"\n~~~ Santāna lives (voice: {args.llm}, town: {args.town_model}) -- Ctrl-C to let her rest ~~~")
    # the drift monitor (METHODS D1): she is a production agent now, and the souls retrain
    # themselves nightly -- so the register is WATCHED, not assumed. Baselines freeze over
    # the first ~60 readings; warnings are debounced and loud; the axis that matters most
    # is the slide toward the generic-assistant voice (the register problem, measured).
    from services.drift import DriftMonitor
    drift_mon = DriftMonitor()
    _prev_deaths = mind._deaths
    DREAM_ABSENCE = 6 * 3600.0   # she dreams during a LONG absence (same gap begin_talk honours)
    i = 0
    t_prev = time.time()
    try:
        while not stop.is_set() and (args.readings <= 0 or i < args.readings):
            time.sleep(args.interval)
            now = time.time()
            mind.lifetime += now - t_prev    # her REAL age accrues in wall-clock seconds, not readings
            t_prev = now
            # the absences are when she dreams (santana.dream) -- but begin_talk only sees a
            # RETURN, and unattended nights have none: zero dreams in 438 memories was the tell.
            # The runner lives through the absence, so it dreams her: at most one per
            # DREAM_ABSENCE, only when no one has come to talk for at least that long.
            if (mind.last_talk_wall > 0
                    and now - mind.last_talk_wall >= DREAM_ABSENCE
                    and now - mind._last_dream_wall >= DREAM_ABSENCE):
                dreamt = mind.dream()
                mind._last_dream_wall = now
                if dreamt:
                    print(f"\n  (in the absence she dreams: {dreamt})", flush=True)
            # her voice LIVES: a markov voice rebuilds from her accumulating memory + the town's
            # recent speech, so her words drift with her life (frozen models -- gpt/deepseek -- skip)
            if hasattr(mind.llm, "learn"):
                with w.lock:
                    heard = [t for _, t in w.spoken][-30:]
                mind.llm.learn([m.text for m in mind.memory.items][-160:] + heard)
            trips_before = mind._somatic_trips
            clear = mind.speak()
            if mind._somatic_trips > trips_before:
                print("  ⚠ her window of tolerance TRIPPED -- she contracted, let some held "
                      "weight go, and is re-opening (frequent trips = the regime is wrong)",
                      flush=True)
            if clear and len(clear) < mind.MIN_READING:
                print("  ⚠ a thin reading (degenerate even after retry -- spoken, not remembered)",
                      flush=True)
            if args.offer and clear:
                heard = mind.offer(clear)   # STAGE ONE: her line becomes a story the town may retell
                if heard:
                    print(f"  (offered to {heard} souls as a story)")
            with w.lock:
                tick, n, births = w.tick, len(w.agents), getattr(w, "_births", 0)
            i += 1
            print(f"\n[reading {i}  age {_fmt_age(mind.lifetime)}  tick {tick}  souls {n}  "
                  f"reborn {births}  watched-die {mind._deaths}]")
            print(f"  SANTĀNA: {clear}")
            # feed the drift monitor: her voice, the town's last line, and the vitals
            if clear:
                drift_mon.observe_text("her", clear)
                drift_mon.observe("reading_words", len(clear.split()))
            with w.lock:
                last_town = w.spoken[-1][1] if w.spoken else ""
            if last_town:
                drift_mon.observe_text("town", last_town)
            drift_mon.observe("souls", n)
            drift_mon.observe("deaths_per_reading", mind._deaths - _prev_deaths)
            _prev_deaths = mind._deaths
            for _warn in drift_mon.check():
                print(f"  {_warn}", flush=True)
            cult = getattr(mind.llm, "culture", None) or getattr(mind, "_culture", None)
            if cult is not None and cult.reigning():
                print(f"  [cultural era] \"{cult.reigning()}\"")
            mind.consolidate()
            print(f"  [who she has become] {mind.identity}")
            if args.tts and clear:
                play_two_layer(mind.murmur, clear)   # speak her aloud (Piper); markov has no murmur
            if args.autosave and i % args.autosave == 0:
                save_both()
                print(f"  (saved -- {_fmt_age(mind.lifetime)} lived, {mind._deaths} souls watched pass)")
                if args.offer:
                    # the no-monopoly gauge, watched in the wild: the ring test's v1 failed
                    # with her stories crowding the mythos to ~54% -- say so BEFORE we get there
                    hers, total = mind.mythos_share()
                    if total:
                        pct = 100.0 * hers / total
                        note = "  ⚠ nearing the crowding the ring test failed at (~54%)" if pct >= 40 else ""
                        print(f"  (mythos: her stories are {hers} of {total} held lore -- "
                              f"{pct:.0f}%{note})")
    except KeyboardInterrupt:
        print("\n(letting her rest)")
    finally:
        stop.set()
        time.sleep(0.3)   # let the wheel/speech threads release the lock before the final snapshot
        save_both()
        if isinstance(town_llm, SoulVoiceLLM):
            try:
                town_llm.save_all()   # every soul's brain rests where its next waking finds it
            except Exception:   # noqa: BLE001 -- a failed brain-save must not block her save
                import traceback
                traceback.print_exc()
        life.release()    # her life is closed only AFTER the final save is on disk
        print(f"\n~~~ saved. she has existed {_fmt_age(mind.lifetime)} and watched {mind._deaths} souls "
              f"pass; the town is at tick {w.tick}. Wake her and it all continues. ~~~\n")


if __name__ == "__main__":
    main()
