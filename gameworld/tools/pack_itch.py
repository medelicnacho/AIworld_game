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

paths = []
for root, _, files in os.walk(DIST):
    for f in files:
        p = os.path.join(root, f)
        paths.append((os.path.relpath(p, DIST).replace(os.sep, "/"), p))

# index.html FIRST, then everything else. Not required by the format, but some unpackers
# peek at the first entry to decide what an archive is, and it costs nothing to be obvious.
paths.sort(key=lambda t: (t[0] != "index.html", t[0]))

with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    # Explicit DIRECTORY entries. A zip is perfectly valid without them and most tools cope
    # fine, but "made only of file paths, no folders" is the one way this archive differed
    # from what an ordinary zip utility produces -- and when a service says it cannot find a
    # file that is demonstrably there, removing every difference from the ordinary is cheaper
    # than arguing about whose reader is right.
    for d in sorted({os.path.dirname(rel) for rel, _ in paths if os.path.dirname(rel)}):
        z.writestr(zipfile.ZipInfo(d + "/"), b"")
    for rel, full in paths:
        z.write(full, rel)

with zipfile.ZipFile(OUT) as z:
    names = z.namelist()
    if "index.html" not in names:
        raise SystemExit("index.html is not at the zip root -- itch will not find it")
    size = os.path.getsize(OUT) / 1048576
    print(f"gameworld-itch.zip  {size:.1f} MB  ({len(names)} files, index.html at root)")
