#!/usr/bin/env bash
# Clone the official FinReason Cup toolkit at the pinned commit into ./toolkit
set -euo pipefail
cd "$(dirname "$0")/.."
COMMIT=fa6d96dbfabd140b678dfadfff3a1f78586b2ea4
if [ ! -d toolkit/.git ]; then
  git clone https://github.com/The-FinAI/IEEE-bigdata-cup toolkit
fi
git -C toolkit fetch --depth 1 origin "$COMMIT" 2>/dev/null || true
git -C toolkit checkout -q "$COMMIT"
echo "toolkit at $(git -C toolkit rev-parse HEAD)"
