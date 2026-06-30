#!/usr/bin/env bash
# Launch the Santāna app with the project's venv python -- no venv activation needed.
# Usage:  ./app.sh                 # town + music + her voice
#         ./app.sh --no-music      # ...any viewer/app flag passes through
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$HERE/../.venv/bin/python"
if [ ! -x "$VENV" ]; then
  echo "venv python not found at $VENV"; exit 1
fi
exec "$VENV" "$HERE/app.py" "$@"
