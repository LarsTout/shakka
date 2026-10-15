#!/usr/bin/env bash
# Fails when web code references Open-Meteo API hosts. Open-Meteo is called server-side only (ingest).
# Usage: check-no-client-openmeteo.sh [path ...]
#   no args: scans web/src, web/static and (if present) web/build of this repo.
# Exit: 0 clean, 1 forbidden reference found, 2 usage or grep error.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PATTERN='api\.open-meteo\.com|marine-api\.open-meteo\.com|open-meteo\.com/v1'

if [ "$#" -gt 0 ]; then
  targets=("$@")
  for t in "${targets[@]}"; do
    if [ ! -e "$t" ]; then
      echo "check-no-client-openmeteo: path not found: $t" >&2
      exit 2
    fi
  done
else
  targets=("$ROOT/web/src" "$ROOT/web/static")
  for t in "${targets[@]}"; do
    if [ ! -d "$t" ]; then
      echo "check-no-client-openmeteo: missing directory: $t" >&2
      exit 2
    fi
  done
  if [ -d "$ROOT/web/build" ]; then
    targets+=("$ROOT/web/build")
  else
    echo "check-no-client-openmeteo: web/build not found, skipped (run npm run build first)"
  fi
fi

set +e
matches="$(grep -rIniE --exclude-dir=node_modules "$PATTERN" "${targets[@]}")"
status=$?
set -e

if [ "$status" -eq 0 ]; then
  echo "$matches"
  echo "check-no-client-openmeteo: FAIL, Open-Meteo must only be called from /ingest" >&2
  exit 1
fi
if [ "$status" -eq 1 ]; then
  echo "check-no-client-openmeteo: ok"
  exit 0
fi
echo "check-no-client-openmeteo: grep failed" >&2
exit 2
