#!/usr/bin/env bash
# Download the Piper voice models the agents speak with (~190MB, gitignored).
# Run once after cloning:  bash scripts/get_voices.sh
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/data/voices"
BASE="https://huggingface.co/rhasspy/piper-voices/resolve/main/en"
mkdir -p "$DIR"

fetch() {  # <relative-path> <filename>
  local rel="$1" name="$2"
  for ext in onnx onnx.json; do
    if [ ! -f "$DIR/$name.$ext" ]; then
      echo "downloading $name.$ext ..."
      curl -fsSL -o "$DIR/$name.$ext" "$BASE/$rel/$name.$ext"
    fi
  done
}

# A distinct model per agent -- British/American, male/female timbres.
fetch "en_GB/alan/medium"                   "en_GB-alan-medium"                   # River (calm British male)
fetch "en_US/ryan/medium"                   "en_US-ryan-medium"                   # Ash   (dry American male)
fetch "en_GB/northern_english_male/medium"  "en_GB-northern_english_male-medium"  # Mire  (bleak Northern male)
fetch "en_US/amy/medium"                    "en_US-amy-medium"                    # Lark  (quick bright female)
fetch "en_GB/cori/medium"                   "en_GB-cori-medium"                   # Wren  (warm British female)
fetch "en_US/joe/medium"                    "en_US-joe-medium"                    # Sol   (open American male)
fetch "en_US/kristin/medium"                "en_US-kristin-medium"                # default voice
fetch "en_US/lessac/medium"                 "en_US-lessac-medium"                 # The Devout (collective mind)

echo "done -> $DIR"
ls -1 "$DIR"/*.onnx
