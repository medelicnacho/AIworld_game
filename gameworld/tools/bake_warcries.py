#!/usr/bin/env python3
"""Bake the hardcoded war cries to shippable audio.

WHY THIS EXISTS
---------------
Piper is a synthesizer, and synthesizers do not care WHEN they run. The bridge ran it at
play time, which meant every voice in the game lived behind a localhost server — so a built
copy had no war cries at all, not even the hardcoded ones, because the lines were authored
in config but the *sound* was made on demand by a machine only the developer has.

The taunts and hails are a FIXED LIST. Nothing about them needs a live model. So they are
synthesized once, here, and shipped as ordinary audio files like any other sound effect.
The frontier gets its voices back with no server, no latency and no per-player cost.

What is NOT baked: anything the LLM writes. Those stay a dev-only enhancement (see LAB in
config.js) and are layered on top of this floor when the lab is running.

USAGE
    tools/bake_warcries.py            # bake anything missing
    tools/bake_warcries.py --force    # re-bake everything (after editing a line or a voice)

Run it whenever you add a line to WARCRY.taunts or WARCRY.hails, and commit the output —
the wavs are build INPUT, so a machine without Piper can still ship the game.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GAME = HERE.parent
CONFIG = GAME / "src" / "config.js"
OUT_DIR = GAME / "public" / "voice" / "warcry"
MANIFEST = GAME / "public" / "voice" / "warcry.json"
LAB = GAME.parent / "localprototype"
VENV_PY = GAME.parent / ".venv" / "bin" / "python"


def extract_lines(name: str) -> list[str]:
    """Pull one string array out of config.js.

    Deliberately reading the authored source rather than keeping a second copy of the lines
    in a JSON somewhere: two lists of the same thing is how one of them goes stale, and the
    comment beside them in config says both halves of the war's vocabulary are edited in one
    place. If the shape ever changes this fails loudly at build time, which is the point.
    """
    src = CONFIG.read_text()
    m = re.search(rf"^\s*{name}:\s*\[(.*?)^\s*\],", src, re.S | re.M)
    if not m:
        sys.exit(f"could not find WARCRY.{name} in {CONFIG} — has the config shape changed?")
    lines = re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(1))
    if not lines:
        sys.exit(f"WARCRY.{name} looks empty")
    return [ln.encode().decode("unicode_escape") for ln in lines]


def voice_settings() -> tuple[str, float]:
    """The model and pace faction 0 speaks with — all three share it today."""
    src = CONFIG.read_text()
    m = re.search(r'0:\s*\{\s*model:\s*"([^"]+)",\s*pace:\s*([0-9.]+)', src)
    if not m:
        sys.exit("could not read WARCRY.voices[0] from config.js")
    return m.group(1), float(m.group(2))


def slug(text: str) -> str:
    """A stable filename per line. Hashed, so punctuation and length cannot bite."""
    return hashlib.sha1(text.encode()).hexdigest()[:16]


BAKE_ONE = r"""
import sys, json
sys.path.insert(0, sys.argv[1])
from services.tts import PiperTTS, Voice
jobs = json.load(open(sys.argv[2]))
tts = PiperTTS()
for text, path, model, pace in jobs:
    tts.synth_to(text, Voice(model=model, length_scale=pace), path)
    print(path, flush=True)
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="re-bake lines that already exist")
    args = ap.parse_args()

    if not VENV_PY.exists():
        sys.exit(f"no venv at {VENV_PY} — Piper lives there (see localprototype/run.sh)")

    model, pace = voice_settings()
    groups = {"taunts": extract_lines("taunts"), "hails": extract_lines("hails")}
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, list[dict]] = {}
    jobs: list[tuple[str, str, str, float]] = []
    for kind, lines in groups.items():
        manifest[kind] = []
        for text in lines:
            name = f"{slug(text)}.wav"
            dest = OUT_DIR / name
            manifest[kind].append({"text": text, "file": f"voice/warcry/{name}"})
            if args.force or not dest.exists():
                jobs.append((text, str(dest), model, pace))

    total = sum(len(v) for v in manifest.values())
    if jobs:
        print(f"baking {len(jobs)} of {total} lines with {model} @ pace {pace} ...")
        spec = OUT_DIR / "_jobs.json"
        spec.write_text(json.dumps(jobs))
        try:
            subprocess.run([str(VENV_PY), "-c", BAKE_ONE, str(LAB), str(spec)], check=True)
        finally:
            spec.unlink(missing_ok=True)
    else:
        print(f"all {total} lines already baked (use --force to redo)")

    # PRUNE WHAT NOTHING POINTS AT. Filenames are hashes of the LINE, so editing a taunt does
    # not overwrite its wav — it writes a new one and abandons the old, which then ships for
    # ever as audio no code can reach. Anything the manifest does not name goes.
    keep = {Path(e["file"]).name for v in manifest.values() for e in v}
    dropped = 0
    for f in OUT_DIR.glob("*.wav"):
        if f.name not in keep:
            f.unlink()
            dropped += 1
    if dropped:
        print(f"pruned {dropped} orphaned wav(s) — lines that were edited or removed")

    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps({"voice": model, "pace": pace, **manifest}, indent=1))
    size = sum(p.stat().st_size for p in OUT_DIR.glob("*.wav"))
    print(f"{total} lines -> {MANIFEST.relative_to(GAME)}  ({size / 1024:.0f} KB of audio)")


if __name__ == "__main__":
    main()
