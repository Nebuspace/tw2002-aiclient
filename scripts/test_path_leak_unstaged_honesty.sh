#!/usr/bin/env bash
# test_path_leak_unstaged_honesty.sh — pins for WO-PATH-LEAK-UNSTAGED-HONESTY.
#
# Chosen behavior: dirty-tree refuse (empty index + dirty worktree → exit 1).
# Pre-commit / non-empty --cached path unchanged.
#
# Run: ./scripts/test_path_leak_unstaged_honesty.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/scripts/path-leak-scan.sh"
FAILED=0

[[ -f "$SRC" ]] || { echo "FAIL: script under test not found at $SRC" >&2; exit 1; }
bash -n "$SRC"
bash -n "$0"

fail() { echo "FAIL: $*" >&2; FAILED=1; }
ok()   { echo "  ok: $*"; }

# Build leak payloads without embedding a literal operator-home absolute path in
# this committed pin (would trip path-leak-scan on the pin itself).
FAKE_USERS_HOME=$'/Use''rs/operator-home'
FAKE_HOME_HOME=$'/ho''me/operator-home'

make_fixture() {
  local fix
  fix="$(mktemp -d)"
  git init -q "$fix/repo"
  (
    cd "$fix/repo"
    git config user.email test@example.invalid
    git config user.name "test"
    git config commit.gpgsign false
    echo seed > clean.txt
    mkdir -p scripts
    cp "$SRC" scripts/path-leak-scan.sh
    chmod +x scripts/path-leak-scan.sh
    git add clean.txt scripts/path-leak-scan.sh
    git commit -qm "seed"
  )
  echo "$fix"
}

run_scan() {
  local fix="$1"; shift
  set +e
  ( cd "$fix/repo" && ./scripts/path-leak-scan.sh "$@" ) > "$fix/out.txt" 2> "$fix/err.txt"
  RC=$?
  set -e
}

echo "== C0: clean tree, nothing staged → exit 0 =="
FIX="$(make_fixture)"
run_scan "$FIX"
if [[ "$RC" -eq 0 ]] && grep -q 'no staged changes' "$FIX/out.txt"; then
  ok "clean empty index exits 0"
else
  fail "clean empty index expected 0 + INFO; got rc=$RC out=$(cat "$FIX/out.txt") err=$(cat "$FIX/err.txt")"
fi
rm -rf "$FIX"

echo "== C1: dirty unstaged (with fake home path) + empty index → exit 1 refuse =="
FIX="$(make_fixture)"
(
  cd "$FIX/repo"
  printf '%s\n' "leak at ${FAKE_USERS_HOME}/secret" > dirty.txt
)
run_scan "$FIX"
if [[ "$RC" -eq 1 ]] && grep -q 'working tree is dirty' "$FIX/err.txt"; then
  ok "dirty unstaged refuses (not green)"
else
  fail "dirty refuse expected rc=1 + dirty message; got rc=$RC err=$(cat "$FIX/err.txt") out=$(cat "$FIX/out.txt")"
fi
rm -rf "$FIX"

echo "== C2: staged clean content → exit 0 (even if other unstaged dirt exists) =="
FIX="$(make_fixture)"
(
  cd "$FIX/repo"
  echo ok-line > staged.txt
  git add staged.txt
  printf '%s\n' "also dirty ${FAKE_USERS_HOME}/x" > other.txt
)
run_scan "$FIX"
if [[ "$RC" -eq 0 ]] && grep -q 'OK \[path-leak\]' "$FIX/out.txt"; then
  ok "staged clean still green; unstaged dirt ignored when index non-empty"
else
  fail "staged clean expected 0; got rc=$RC out=$(cat "$FIX/out.txt") err=$(cat "$FIX/err.txt")"
fi
rm -rf "$FIX"

echo "== C3: staged leak → exit 1 =="
FIX="$(make_fixture)"
(
  cd "$FIX/repo"
  printf '%s\n' "path ${FAKE_USERS_HOME}/leak" > leak.txt
  git add leak.txt
)
run_scan "$FIX"
if [[ "$RC" -eq 1 ]] && grep -q 'FAIL \[path-leak\]' "$FIX/err.txt"; then
  ok "staged leak fails"
else
  fail "staged leak expected 1; got rc=$RC err=$(cat "$FIX/err.txt") out=$(cat "$FIX/out.txt")"
fi
rm -rf "$FIX"

echo "== C4: --file still works =="
FIX="$(make_fixture)"
printf '%s\n' 'clean relative path only' > "$FIX/repo/one.txt"
run_scan "$FIX" --file one.txt
if [[ "$RC" -eq 0 ]]; then
  ok "--file clean"
else
  fail "--file clean expected 0; got rc=$RC"
fi
printf '%s\n' "${FAKE_HOME_HOME}/x" > "$FIX/repo/two.txt"
run_scan "$FIX" --file two.txt
if [[ "$RC" -eq 1 ]]; then
  ok "--file leak"
else
  fail "--file leak expected 1; got rc=$RC"
fi
rm -rf "$FIX"

if [[ "$FAILED" -ne 0 ]]; then
  echo "FAILED: $FAILED case(s)" >&2
  exit 1
fi
echo "ALL PASS [path-leak unstaged honesty · dirty-tree refuse]"
