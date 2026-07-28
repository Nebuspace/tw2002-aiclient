#!/usr/bin/env bash
# cert-pytest-junit.sh — run pytest; on exit 0, hard-fail if junitxml is
# missing / empty / unparseable / zero-test (WO-CERT-JUNIT-HARDFAIL).
#
# Usage (same args as pytest; --junitxml= is required):
#   ./scripts/cert-pytest-junit.sh -q --junitxml=/tmp/suite.xml tests/
#
# If pytest exits non-zero, that status is returned unchanged (no second guess
# from the guard — the suite already failed).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GUARD="$ROOT/scripts/junitxml_guard.py"
# Prefer an explicit interpreter, then this tree's .venv, then PATH python3.
# Worktrees without a local .venv: set PYTHON to the primary-tree venv before calling.
if [[ -n "${PYTHON:-}" ]]; then
  PY="$PYTHON"
elif [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY="$ROOT/.venv/bin/python"
else
  PY=python3
fi

if [[ ! -f "$GUARD" ]]; then
  echo "cert-pytest-junit: missing guard $GUARD" >&2
  exit 2
fi

junit_path=""
args=("$@")
i=0
while (( i < ${#args[@]} )); do
  a="${args[$i]}"
  case "$a" in
    --junitxml=*)
      junit_path="${a#--junitxml=}"
      ;;
    --junitxml)
      i=$((i + 1))
      if (( i >= ${#args[@]} )); then
        echo "cert-pytest-junit: --junitxml requires a path" >&2
        exit 2
      fi
      junit_path="${args[$i]}"
      ;;
  esac
  i=$((i + 1))
done

if [[ -z "$junit_path" ]]; then
  echo "cert-pytest-junit: require --junitxml=<path> (or --junitxml <path>)" >&2
  exit 2
fi

set +e
"$PY" -m pytest "$@"
pytest_ec=$?
set -e

if (( pytest_ec != 0 )); then
  exit "$pytest_ec"
fi

exec "$PY" "$GUARD" "$junit_path"
