#!/usr/bin/env bash
# Launch Felt from a checkout, creating its venv on first run.
set -euo pipefail
cd "$(dirname "$0")"
UV="${UV:-$(command -v uv || echo "$HOME/.hermes/bin/uv")}"
if [ ! -x .venv/bin/felt ]; then
  "$UV" venv
  "$UV" pip install -e .
fi
exec .venv/bin/felt "$@"
