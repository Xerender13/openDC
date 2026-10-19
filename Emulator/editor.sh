#!/usr/bin/env bash
set -e
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
exec .venv/bin/python -m tools.editor "$@"
