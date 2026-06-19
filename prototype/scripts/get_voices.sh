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

fetch "en_GB/alan/medium" "en_GB-alan-medium"   # River  (calm British male)
fetch "en_US/ryan/medium" "en_US-ryan-medium"   # Ash    (dry American male)
fetch "en_US/amy/medium"  "en_US-amy-medium"    # Moth   (restless female)

echo "done -> $DIR"
ls -1 "$DIR"/*.onnx
