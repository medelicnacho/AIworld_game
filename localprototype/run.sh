#!/usr/bin/env bash
# Launch the world with the project venv (where piper-tts + pygame live).
# Usage:  ./run.sh                 # default run, audio on
#         ./run.sh --show-text     # also print the lines
#         ./run.sh --backend mock --ticks 30
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$HERE/../.venv/bin/python"
if [ ! -x "$VENV" ]; then
  echo "venv not found at $VENV"
  echo "create it:  python3 -m venv ../.venv && ../.venv/bin/pip install -r requirements.txt"
  exit 1
fi
exec "$VENV" "$HERE/main.py" "$@"
