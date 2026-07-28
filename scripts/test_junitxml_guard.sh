#!/usr/bin/env bash
# Pin: WO-CERT-JUNIT-HARDFAIL — missing/empty/zero-test junitxml hard-fails.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
GUARD="$ROOT/scripts/junitxml_guard.py"
CERT="$ROOT/scripts/cert-pytest-junit.sh"
PY="${PYTHON:-python3}"

bash -n "$CERT"
bash -n "$0"

# --- unit: missing file ---
set +e
out="$("$PY" "$GUARD" /tmp/junitxml_guard_missing_$$.xml 2>&1)"
ec=$?
set -e
test "$ec" -eq 1
printf '%s' "$out" | grep -q 'CERT HARD-FAIL: junitxml missing'

# --- unit: empty file ---
empty="$(mktemp)"
: >"$empty"
set +e
out="$("$PY" "$GUARD" "$empty" 2>&1)"
ec=$?
set -e
rm -f "$empty"
test "$ec" -eq 1
printf '%s' "$out" | grep -q 'CERT HARD-FAIL: junitxml empty'

# --- unit: zero-test xml ---
zero="$(mktemp)"
printf '%s' '<?xml version="1.0"?><testsuites><testsuite name="pytest" tests="0" failures="0" errors="0"/></testsuites>' >"$zero"
set +e
out="$("$PY" "$GUARD" "$zero" 2>&1)"
ec=$?
set -e
rm -f "$zero"
test "$ec" -eq 1
printf '%s' "$out" | grep -q 'CERT HARD-FAIL: junitxml reports zero tests'

# --- unit: honest ≥1 test passes ---
ok="$(mktemp)"
printf '%s' '<?xml version="1.0"?><testsuites><testsuite name="pytest" tests="3" failures="0" errors="0"/></testsuites>' >"$ok"
set +e
out="$("$PY" "$GUARD" "$ok" 2>&1)"
ec=$?
set -e
rm -f "$ok"
test "$ec" -eq 0
printf '%s' "$out" | grep -q 'tests=3'

# --- WO Proof (pytest 9.1.1): missing path exits 4 (usage), not 0.
# Equivalent exit-0 + tests="0" junitxml: collect-only with empty testpaths override.
proof_xml="$(mktemp)"
rm -f "$proof_xml"
set +e
"$PY" -m pytest --collect-only -q --junitxml="$proof_xml" \
  --override-ini="testpaths=no_such_path" >/dev/null 2>&1
pec=$?
set -e
test "$pec" -eq 0
test -f "$proof_xml"
set +e
out="$("$PY" "$GUARD" "$proof_xml" 2>&1)"
gec=$?
set -e
rm -f "$proof_xml"
test "$gec" -eq 1
printf '%s' "$out" | grep -q 'CERT HARD-FAIL: junitxml reports zero tests'

# --- cert wrapper: same exit-0 + zero-test path → hard fail ---
wrap_xml="$(mktemp)"
rm -f "$wrap_xml"
set +e
"$CERT" --collect-only -q --junitxml="$wrap_xml" \
  --override-ini="testpaths=no_such_path" >/dev/null 2>&1
ec=$?
set -e
test "$ec" -eq 1
rm -f "$wrap_xml"

# --- Accept 2: normal executed run (≥1 test) via cert wrapper is green ---
ok_xml="$(mktemp)"
set +e
"$CERT" -q -n0 --junitxml="$ok_xml" tests/test_env.py >/dev/null 2>&1
ec=$?
set -e
test "$ec" -eq 0
"$PY" "$GUARD" "$ok_xml" >/dev/null
rm -f "$ok_xml"

# --- cited WO missing-path artifact still trips the guard (even if pytest≠0) ---
miss_xml="$(mktemp)"
rm -f "$miss_xml"
set +e
"$PY" -m pytest --collect-only -q --junitxml="$miss_xml" tests/test_nonexistent.py >/dev/null 2>&1
set -e
test -f "$miss_xml"
set +e
"$PY" "$GUARD" "$miss_xml" >/dev/null 2>&1
gec=$?
set -e
rm -f "$miss_xml"
test "$gec" -eq 1

echo "OK junitxml_guard pins"
