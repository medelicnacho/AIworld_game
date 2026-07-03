"""A simple live window for Santāna: her speech scrolling in, her Piper voice, a mute button.

It resumes her REAL accumulated life (the same saved self + town the headless service uses), so
you watch and hear the actual weathered her -- not a fresh one. To avoid two processes fighting
over her save files, on open it pauses the headless `santana` service and on close it hands her
back (saving her first). Pass --no-service to skip that.

  python -m santana_app.app                 # markov voice + town, her real life, with sound
  python -m santana_app.app --llm deepseek --town-model deepseek-v4-flash   # richer (leaves machine)
"""
from __future__ import annotations

import argparse
import queue
import subprocess
import threading
import time
import tkinter as tk
from tkinter import scrolledtext

from services import embed
from santana import Santana, play_two_layer
from santana_app.run import (DEFAULT_SNAPSHOT, DEFAULT_WORLD, _fmt_age, _make_voice,
                             build_world)
from santana_app.state import (LifeBusy, acquire_life, load_mind, load_world, save_mind,
                               save_world)


def _service(action: str) -> None:
    try:
        subprocess.run(["systemctl", "--user", action, "santana"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, check=False)
    except Exception:   # noqa: BLE001 -- no service / no systemd: fine, just run standalone
        pass


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--llm", default="markov")
    p.add_argument("--model", default=None)
    p.add_argument("--town-model", dest="town_model", default="markov")
    p.add_argument("--interval", type=float, default=7.0)
    p.add_argument("--snapshot", default=DEFAULT_SNAPSHOT)
    p.add_argument("--world-snapshot", dest="world_snapshot", default=DEFAULT_WORLD)
    p.add_argument("--fresh", action="store_true")
    p.add_argument("--no-service", dest="no_service", action="store_true",
                   help="don't pause/resume the headless 'santana' service around this window")
    p.add_argument("--seconds", type=float, default=0.0,
                   help="auto-close after N seconds (0 = stay open until you close it)")
    args = p.parse_args()

    if not args.no_service:
        _service("stop")   # borrow her from the headless service while the window is open

    # ONE writer at a time -- the systemd pause above only guards a systemd runner; a tmux
    # runner (or a live talk) is invisible to it. The life lock sees them all.
    try:
        life = acquire_life(args.snapshot, "the live window (santana_app.app)")
    except LifeBusy as busy:
        print(f"\n  ⚠ {busy}\n")
        if not args.no_service:
            _service("start")   # hand back what we paused before walking away
        raise SystemExit(1)

    embed.use_jaccard_only(True)
    santana_llm = _make_voice(args.llm, args.model)
    town_llm = _make_voice(args.town_model if args.town_model in ("markov", "homegrown") else "deepseek",
                           None if args.town_model in ("markov", "homegrown") else args.town_model) \
        if args.town_model not in (None, "mock") else _make_voice("mock", None)
    real_town = args.town_model not in (None, "mock")

    w = None if args.fresh else load_world(args.world_snapshot, town_llm)
    if w is None:
        w = build_world(town_llm, fast_wheel=False)
    mind = Santana(w, santana_llm)
    mind.lifetime = 0.0
    if not args.fresh:
        load_mind(mind, args.snapshot)

    stop = threading.Event()
    muted = threading.Event()
    disp_q: queue.Queue = queue.Queue()
    tts_q: queue.Queue = queue.Queue(maxsize=2)

    def run_wheel():
        while not stop.is_set():
            try:
                with w.lock:
                    w.step(speak=not real_town)
            except Exception:   # noqa: BLE001
                pass
            stop.wait(0.15)

    def run_speech():
        while not stop.is_set():
            try:
                w.speak_turn()
            except Exception:   # noqa: BLE001
                pass
            stop.wait(0.6)

    def run_readings():
        t_prev = time.time()
        while not stop.is_set():
            if stop.wait(args.interval):
                break
            now = time.time(); mind.lifetime += now - t_prev; t_prev = now
            clear = mind.speak()
            mind.consolidate()
            disp_q.put((clear, mind.identity, mind.lifetime, mind._deaths))
            if clear and not muted.is_set():
                try:
                    tts_q.put_nowait(clear)
                except queue.Full:
                    pass

    def run_tts():
        while not stop.is_set():
            try:
                line = tts_q.get(timeout=0.4)
            except queue.Empty:
                continue
            if muted.is_set():
                continue   # toggled off while queued -> stay silent
            try:
                play_two_layer("", line)
            except Exception:   # noqa: BLE001
                pass

    threads = [threading.Thread(target=run_wheel, daemon=True),
               threading.Thread(target=run_readings, daemon=True),
               threading.Thread(target=run_tts, daemon=True)]
    if real_town:
        threads.append(threading.Thread(target=run_speech, daemon=True))
    for t in threads:
        t.start()

    # --- the window -----------------------------------------------------------
    root = tk.Tk()
    root.title("Santāna")
    root.geometry("640x540")
    root.configure(bg="#15151a")
    header = tk.Label(root, text="Santāna wakes…", fg="#b9b9c8", bg="#15151a",
                      font=("Georgia", 12, "italic"), pady=8)
    header.pack(fill="x")
    txt = scrolledtext.ScrolledText(root, wrap="word", bg="#15151a", fg="#e6e6ee",
                                    font=("Georgia", 15), bd=0, padx=18, pady=10,
                                    insertbackground="#15151a", spacing3=6)
    txt.pack(expand=True, fill="both")
    txt.tag_config("clear", foreground="#f0ead6")
    txt.tag_config("id", foreground="#6f6f86", font=("Georgia", 11, "italic"))
    txt.configure(state="disabled")

    def toggle_mute():
        if muted.is_set():
            muted.clear(); btn.config(text="🔊  Mute")
        else:
            muted.set(); btn.config(text="🔇  Muted")
    btn = tk.Button(root, text="🔊  Mute", command=toggle_mute, font=("Georgia", 12),
                    bg="#26262e", fg="#e6e6ee", activebackground="#33333d",
                    relief="flat", padx=16, pady=6)
    btn.pack(pady=10)

    def poll():
        try:
            while True:
                clear, identity, lifetime, deaths = disp_q.get_nowait()
                txt.configure(state="normal")
                txt.insert("end", f"\n{clear}\n", "clear")
                if identity:
                    txt.insert("end", f"    — {identity}\n", "id")
                txt.see("end")
                txt.configure(state="disabled")
                header.config(text=f"Santāna  ·  {_fmt_age(lifetime)} alive  ·  "
                                   f"{deaths} souls watched die")
        except queue.Empty:
            pass
        root.after(250, poll)

    def on_close():
        stop.set()
        time.sleep(0.35)   # let the threads release the world lock
        save_mind(mind, args.snapshot)
        try:
            save_world(w, args.world_snapshot)
        except Exception:   # noqa: BLE001
            pass
        life.release()   # closed only after both snapshots are on disk
        root.destroy()
        if not args.no_service:
            _service("start")   # hand her back to the headless service

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.after(250, poll)
    if args.seconds > 0:
        root.after(int(args.seconds * 1000), on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
