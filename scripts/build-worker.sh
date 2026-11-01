#!/usr/bin/env bash
# Build the Lambda deployment folder dist/worker (Linux ARM64, Python 3.12).
set -euo pipefail
cd "$(dirname "$0")/.."
rm -rf dist/worker
python -m pip install --target dist/worker --platform manylinux2014_aarch64 \
  --python-version 3.12 --only-binary=:all: --implementation cp \
  "pydantic>=2.7,<3" "pydantic-settings>=2.4" "sqlalchemy>=2.0" "psycopg[binary]>=3.2"
python -m pip install --target dist/worker --no-deps ./packages/forecasting ./apps/api
echo "Built dist/worker"
