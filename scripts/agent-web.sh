#!/usr/bin/env bash
set -euo pipefail

# Resolve repo root (this script is in scripts/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SCRIPT_DIR}/.."
cd "${REPO_ROOT}"

# Load .env if present
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

# Run web UI; extra args override .env (e.g., --port 8090)
exec python3 -m agentic.cli --serve "$@"

