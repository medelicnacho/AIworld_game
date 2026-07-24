#!/usr/bin/env python3
"""Pack dist/ into gameworld-itch.zip for upload to itch.io.

The one thing that actually matters here: index.html must sit at the ROOT of the zip, not
inside a folder. itch looks for it there and nowhere else, and a zip made by right-clicking
the dist folder puts everything one level down -- which produces a page that loads to a
blank frame with no error explaining why. Zipping the CONTENTS is the whole trick.

    npm run pack        (build + pack)
"""
import os
import zipfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(HERE, "dist")
OUT = os.path.join(HERE, "gameworld-itch.zip")

if not os.path.isdir(DIST):
    raise SystemExit("no dist/ -- run `npm run build` first")

with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    for root, _, files in os.walk(DIST):
        for f in files:
            p = os.path.join(root, f)
            z.write(p, os.path.relpath(p, DIST))

with zipfile.ZipFile(OUT) as z:
    names = z.namelist()
    if "index.html" not in names:
        raise SystemExit("index.html is not at the zip root -- itch will not find it")
    size = os.path.getsize(OUT) / 1048576
    print(f"gameworld-itch.zip  {size:.1f} MB  ({len(names)} files, index.html at root)")
