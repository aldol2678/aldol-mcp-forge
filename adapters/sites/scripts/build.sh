#!/usr/bin/env bash
set -euo pipefail
project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
python3 "$project_root/scripts/embed-page.py"
python3 "$project_root/scripts/bundle.py"
mkdir -p "$project_root/dist/.openai"
cp "$project_root/.openai/hosting.json" "$project_root/dist/.openai/hosting.json"
echo "Built $project_root/dist"
