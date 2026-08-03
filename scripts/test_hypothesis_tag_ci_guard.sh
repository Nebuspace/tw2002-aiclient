#!/usr/bin/env bash
# test_hypothesis_tag_ci_guard.sh — pins for PWO-114.
#
# Proves:
#   1. Tip green path — real port_economics passes
#   2. Deliberate untagged fixture — assert fails (exit 1) — not a no-op gate
#
# Run: ./scripts/test_hypothesis_tag_ci_guard.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
GUARD="$ROOT/scripts/hypothesis_tag_ci_guard.py"
PY="${PYTHON:-}"
if [[ -z "$PY" ]]; then
  if [[ -x "$ROOT/.venv/bin/python" ]]; then
    PY="$ROOT/.venv/bin/python"
  else
    common="$(cd "$ROOT" && git rev-parse --git-common-dir)"
    common="$(cd "$ROOT" && cd "$common" && pwd)"
    main_root="$(dirname "$common")"
    if [[ -x "$main_root/.venv/bin/python" ]]; then
      PY="$main_root/.venv/bin/python"
    else
      PY=python3
    fi
  fi
fi

bash -n "$0"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
"$PY" -m py_compile "$GUARD"

FAILED=0
fail() { echo "FAIL: $*" >&2; FAILED=1; }
ok()   { echo "  ok: $*"; }

echo "== U1: tip green path (real port_economics) =="
set +e
out="$("$PY" "$GUARD" 2>&1)"
ec=$?
set -e
if [[ "$ec" -eq 0 ]] && printf '%s' "$out" | grep -q 'OK \[hypothesis-tag\]'; then
  ok "live module passes"
else
  fail "tip expected ec=0; got $ec out=$out"
fi

echo "== U2: deliberate untagged fixture must fail =="
set +e
out="$("$PY" "$GUARD" --self-test-fail 2>&1)"
ec=$?
set -e
if [[ "$ec" -eq 1 ]] && printf '%s' "$out" | grep -q 'assert bit as expected'; then
  ok "untagged fixture reddens the gate"
else
  fail "self-test-fail expected ec=1 + assert bit; got $ec out=$out"
fi

echo "== U3: guard imports real module path (not a stand-in) =="
if grep -q 'from tw2002_aiclient import port_economics' "$GUARD" \
  && grep -q 'assert_all_unverified_tagged' "$GUARD"; then
  ok "imports real port_economics.assert_all_unverified_tagged"
else
  fail "guard must import real port_economics assert"
fi

if [[ "$FAILED" -ne 0 ]]; then
  echo "FAILED $FAILED check(s)" >&2
  exit 1
fi
echo "ALL PASS"
exit 0
