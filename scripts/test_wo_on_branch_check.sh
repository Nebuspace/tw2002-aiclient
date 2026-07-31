#!/usr/bin/env bash
# test_wo_on_branch_check.sh — Accept pins for wo-on-branch-check.sh (WO-DEC-07).
#
# Drives the REAL script against throwaway fixture repos (same posture as
# test_hub_cleanup_refuse.sh): never against the live tree's remotes.
#
# Run: ./scripts/test_wo_on_branch_check.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/scripts/wo-on-branch-check.sh"
FAILED=0

[[ -f "$SRC" ]] || { echo "FAIL: script under test not found at $SRC" >&2; exit 1; }

fail() { echo "FAIL: $*" >&2; FAILED=1; }
ok()   { echo "  ok: $*"; }

make_fixture() {
  local fix
  fix="$(mktemp -d)"
  git init -q "$fix/repo"
  (
    cd "$fix/repo"
    git config user.email test@example.invalid
    git config user.name "test"
    git config commit.gpgsign false
    echo seed > README.md
    git add README.md
    git commit -qm "seed"
    git branch -M main
    mkdir -p scripts
    cp "$SRC" scripts/wo-on-branch-check.sh
    chmod +x scripts/wo-on-branch-check.sh
  )
  echo "$fix"
}

run_check() {
  local fix="$1"; shift
  set +e
  ( cd "$fix/repo" && ./scripts/wo-on-branch-check.sh "$@" ) > "$fix/out.txt" 2> "$fix/err.txt"
  RC=$?
  set -e
}

echo "== A1: wo/* tip WITHOUT workorders/WO-*.md → exit 1 =="
FIX="$(make_fixture)"
(
  cd "$FIX/repo"
  git checkout -qb wo/MISSING-WO
  echo work > work.txt
  git add work.txt
  git commit -qm "wo work without WO file"
)
run_check "$FIX" wo/MISSING-WO
if [[ "$RC" -eq 1 ]] && grep -q 'missing workorders/WO-MISSING-WO.md' "$FIX/err.txt"; then
  ok "refuses missing WO (rc=$RC)"
else
  fail "expected rc=1 + missing path; got rc=$RC err=$(cat "$FIX/err.txt")"
fi
rm -rf "$FIX"

echo "== A2: wo/* tip WITH matching WO file → exit 0 =="
FIX="$(make_fixture)"
(
  cd "$FIX/repo"
  git checkout -qb wo/DEC-07-WO-ATOMIC
  mkdir -p workorders
  printf '# WO-DEC-07-WO-ATOMIC\n\nGoal: test\n' > workorders/WO-DEC-07-WO-ATOMIC.md
  git add workorders/WO-DEC-07-WO-ATOMIC.md
  git commit -qm "seed WO file"
)
run_check "$FIX" wo/DEC-07-WO-ATOMIC
if [[ "$RC" -eq 0 ]] && grep -q 'WO-DEC-07-WO-ATOMIC.md present' "$FIX/out.txt"; then
  ok "accepts present WO (rc=$RC)"
else
  fail "expected rc=0 + present; got rc=$RC out=$(cat "$FIX/out.txt") err=$(cat "$FIX/err.txt")"
fi
rm -rf "$FIX"

echo "== A3: non-wo branch → exit 0 (gate n/a) =="
FIX="$(make_fixture)"
(
  cd "$FIX/repo"
  git checkout -qb feature/no-gate
)
run_check "$FIX" feature/no-gate
if [[ "$RC" -eq 0 ]] && grep -q 'not wo/\*' "$FIX/out.txt"; then
  ok "skips non-wo branch (rc=$RC)"
else
  fail "expected rc=0 n/a; got rc=$RC out=$(cat "$FIX/out.txt")"
fi
rm -rf "$FIX"

echo "== A4: --ref pin uses the named commit, not working tree =="
FIX="$(make_fixture)"
(
  cd "$FIX/repo"
  git checkout -qb wo/REF-PIN
  mkdir -p workorders
  printf '# WO-REF-PIN\n' > workorders/WO-REF-PIN.md
  git add workorders/WO-REF-PIN.md
  git commit -qm "with WO"
  GOOD="$(git rev-parse HEAD)"
  # Next commit deletes the WO from tip — check must still pass against GOOD.
  git rm -q workorders/WO-REF-PIN.md
  git commit -qm "delete WO"
  echo "$GOOD" > "$FIX/good.sha"
)
GOOD="$(cat "$FIX/good.sha")"
run_check "$FIX" --ref "$GOOD" wo/REF-PIN
if [[ "$RC" -eq 0 ]]; then
  ok "--ref accepts historical tip that had the WO"
else
  fail "--ref should accept; rc=$RC err=$(cat "$FIX/err.txt")"
fi
run_check "$FIX" wo/REF-PIN
if [[ "$RC" -eq 1 ]]; then
  ok "current tip without WO still refuses"
else
  fail "current tip should refuse; rc=$RC"
fi
rm -rf "$FIX"

if [[ "$FAILED" -ne 0 ]]; then
  echo "FAILED"
  exit 1
fi
echo "ALL PASS"
exit 0
