"""Build a training corpus from the sim's OWN recorded life -- the in-world prose it has
already spoken (town utterances, Santāna's voice, her murmurs) -- stripped of log scaffolding.
A self grown from this learns to speak in the voice of the world it came from.

Usage:  python homegrown/harvest.py <dir-with-transcripts> [more dirs...]  -> homegrown/corpus.txt
The transcript lines it understands (from santana.py --live output):
  [heard] NAME: <line>      a townsperson speaking
  SANTĀNA: <line>           her settled voice
  (murmur) <line>           her inner monologue
  [who she has become] ...  her self-model
"""
from __future__ import annotations

import glob
import os
import re
import sys

PATTERNS = [
    re.compile(r"^\s*\[heard\]\s+[^:]+:\s*(.+)$"),
    re.compile(r"^\s*SANT[ĀA]NA:\s*(.+)$"),
    re.compile(r"^\s*\(murmur\)\s*(.+)$"),
    re.compile(r"^\s*\[who she has become\]\s*(.+)$"),
]
_DROP = re.compile(r"\[tts\].*|\(none.*\)|\(no voice.*\)")


def harvest(paths: list[str]) -> list[str]:
    files: list[str] = []
    for p in paths:
        files += glob.glob(os.path.join(p, "**", "*.output"), recursive=True)
        files += glob.glob(os.path.join(p, "**", "*.txt"), recursive=True)
        if os.path.isfile(p):
            files.append(p)
    lines: list[str] = []
    seen: set[str] = set()
    for fn in sorted(set(files)):
        try:
            text = open(fn, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        for raw in text.splitlines():
            for pat in PATTERNS:
                m = pat.match(raw)
                if not m:
                    continue
                line = _DROP.sub("", m.group(1)).strip()
                line = re.sub(r"\s+", " ", line).strip(" -—…")
                # keep real prose only: a sentence-ish line, not a truncated stub
                if len(line) >= 25 and line not in seen and not line.endswith(("the", "a", "to", "of")):
                    seen.add(line)
                    lines.append(line if line.endswith((".", "!", "?")) else line + ".")
                break
    return lines


def main() -> None:
    paths = sys.argv[1:] or ["."]
    lines = harvest(paths)
    out = os.path.join(os.path.dirname(__file__), "corpus.txt")
    text = "\n".join(lines) + "\n"
    with open(out, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"harvested {len(lines)} lines, {len(text)} chars -> {out}")
    print("--- a taste ---")
    for ln in lines[:6]:
        print("  " + ln[:90])


if __name__ == "__main__":
    main()
