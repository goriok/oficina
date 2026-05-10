#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "==> Checking uv..."
if ! command -v uv &>/dev/null; then
  echo "uv not found. Install from https://docs.astral.sh/uv/getting-started/installation/"
  exit 1
fi

echo "==> Installing mcx..."
uv tool install --from "$REPO_ROOT/mcx" mcx --force

echo ""
echo "Done. Run 'mcx --help' to get started."
