#!/usr/bin/env sh
# Regenerates the bundled sample report from this repository (offline, local mode).
set -eu
cd "$(dirname "$0")/../api"
PYTHONPATH=. python -m app.cli inspect .. -f json -o app/data/sample_report.json
cp app/data/sample_report.json ../docs/sample-report.json
cp app/data/sample_report.json ../client/assets/sample_report.json
echo "Sample report regenerated. Review the diff before committing."
