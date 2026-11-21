#!/usr/bin/env bash
# Fetch the synthetic Claude Impact Lab dataset into ./data (gitignored). Run from the repo root.
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
git clone --depth 1 https://github.com/SumeetGDoshi/Claude-Impact-Labs-data-2.git "$tmp/src"
mkdir -p "$here/data"
cp "$tmp/src/data/"* "$here/data/"
echo "Copied $(ls "$here/data" | wc -l) files to $here/data"
