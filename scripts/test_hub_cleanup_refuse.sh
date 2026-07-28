#!/usr/bin/env bash
# test_hub_cleanup_refuse.sh — falsification pins for hub-wo-merge-cleanup.sh's
# worktree-ownership gate (WO-HUB-CLEANUP-SEAT-REFUSE).
#
# Why this drives the REAL script instead of sourcing its two functions:
# a test that lifts `is_hub_owned_wt` and calls it directly proves the predicate
# classifies correctly and says NOTHING about `reap_worktrees` still calling it.
# The gate's whole value is the wire. So every case below executes the actual
# script end-to-end.
#
# Why it copies the script into a throwaway repo: hub-wo-merge-cleanup.sh does
# `REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"` then `cd "$REPO_ROOT"` — it
# operates on whatever repo it physically lives in, and then runs
# `git push origin --delete` and `git branch -D`. Invoking the tree's own copy
# would exercise this gate against the live repository and its GitHub remote.
# The fixture copy is taken fresh from the tree on every run, so it can never
# drift from the file under test.
#
# Run: ./scripts/test_hub_cleanup_refuse.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/scripts/hub-wo-merge-cleanup.sh"
BR="wo/TESTLANE"
FAILED=0

[[ -f "$SRC" ]] || { echo "FAIL: script under test not found at $SRC" >&2; exit 1; }

fail() { echo "FAIL: $*" >&2; FAILED=1; }
ok()   { echo "  ok: $*"; }

# Build a self-contained repo whose <branch> tip is already an ancestor of
# origin/main, so the script's landing gate passes and every REFUSE we then
# observe is attributable to the ownership gate rather than to "not merged".
make_fixture() {
  local fix
  fix="$(mktemp -d)"
  git init --bare -q "$fix/origin.git"
  git init -q "$fix/repo"
  (
    cd "$fix/repo"
    git config user.email test@example.invalid
    git config user.name "test"
    git config commit.gpgsign false
    echo seed > file.txt
    git add file.txt
    git commit -qm "seed"
    git branch -M main
    git remote add origin "$fix/origin.git"
    git push -q -u origin main
    git checkout -qb "$BR"
    echo work >> file.txt
    git commit -qam "wo work"
    git push -q -u origin "$BR"
    git checkout -q main
    git merge -q --ff-only "$BR"
    git push -q origin main
    mkdir -p scripts
    cp "$SRC" scripts/hub-wo-merge-cleanup.sh
    chmod +x scripts/hub-wo-merge-cleanup.sh
  )
  echo "$fix"
}

# A worktree at an arbitrary path, on its own throwaway branch.
add_wt() { (cd "$1/repo" && git worktree add -q "$1/repo/.worktrees/$2" -b "$3" >/dev/null); }

# Run the fixture's copy, capturing status and output without a pipeline —
# `cmd | tail` would hand back tail's exit code, not the script's.
run_cleanup() {
  local fix="$1"; shift
  set +e
  ( cd "$fix/repo" && ./scripts/hub-wo-merge-cleanup.sh "$@" ) > "$fix/out.txt" 2> "$fix/err.txt"
  RC=$?
  set -e
}

echo "== C0 control: the fixture's landing gate passes, so a later REFUSE is about ownership =="
FIX="$(make_fixture)"
add_wt "$FIX" hub-scratch t1
run_cleanup "$FIX" "$BR" "$FIX/repo/.worktrees/hub-scratch"
[[ $RC -eq 0 ]] || fail "C0: hub-owned argv should exit 0, got $RC ($(tail -2 "$FIX/err.txt"))"
if [[ -d "$FIX/repo/.worktrees/hub-scratch" ]]; then fail "C0: hub-scratch should have been reaped"; fi
grep -q "Removing worktree" "$FIX/out.txt" || fail "C0: no 'Removing worktree' line — the harness cannot observe a reap at all"
if [[ $FAILED -eq 0 ]]; then ok "hub-owned worktree reaped; the harness can see a reap"; fi
rm -rf "$FIX"

echo "== C1: an explicit seat path is REFUSED, and the directory survives =="
FIX="$(make_fixture)"
add_wt "$FIX" cc-scratch t1
run_cleanup "$FIX" "$BR" "$FIX/repo/.worktrees/cc-scratch"
[[ $RC -eq 2 ]] || fail "C1: expected exit 2, got $RC"
# The exit code alone is not the outcome: assert WHY it refused, or a refusal
# for an unrelated reason (not-merged, bad branch) would pass this case.
grep -q "not hub-owned" "$FIX/err.txt" || fail "C1: refused for the wrong reason: $(head -2 "$FIX/err.txt")"
[[ -d "$FIX/repo/.worktrees/cc-scratch" ]] || fail "C1: cc-scratch was removed despite the REFUSE"
ok "seat path refused, and still on disk afterwards"
rm -rf "$FIX"

echo "== C2: mixed argv reaps NOTHING — the all-or-nothing gate =="
# Regression pin for the 2026-07-28 finding: when the refusal fired from inside
# the removal loop, `hub-a cc-x hub-b` reaped hub-a, aborted, and never reached
# hub-b — a half-done cleanup wearing a refusal's exit code.
FIX="$(make_fixture)"
add_wt "$FIX" hub-a t1
add_wt "$FIX" cc-x   t2
add_wt "$FIX" hub-b  t3
run_cleanup "$FIX" "$BR" \
  "$FIX/repo/.worktrees/hub-a" "$FIX/repo/.worktrees/cc-x" "$FIX/repo/.worktrees/hub-b"
[[ $RC -eq 2 ]] || fail "C2: expected exit 2, got $RC"
grep -q "not hub-owned" "$FIX/err.txt" || fail "C2: refused for the wrong reason"
for d in hub-a cc-x hub-b; do
  [[ -d "$FIX/repo/.worktrees/$d" ]] || fail "C2: $d was reaped before the refusal — partial cleanup"
done
if grep -q "Removing worktree" "$FIX/out.txt"; then fail "C2: a removal was attempted despite the refusal"; fi
ok "mixed argv: all three worktrees intact, nothing removed"
rm -rf "$FIX"

echo "== C3: auto-discover SKIPs a non-hub worktree on the merged branch =="
FIX="$(make_fixture)"
(cd "$FIX/repo" && git worktree add -q "$FIX/repo/.worktrees/cc-auto" "$BR" >/dev/null)
run_cleanup "$FIX"  "$BR"
[[ $RC -eq 0 ]] || fail "C3: auto-discover should not abort, got $RC ($(tail -2 "$FIX/err.txt"))"
grep -q "SKIP non-hub worktree" "$FIX/out.txt" || fail "C3: expected a SKIP line, got: $(cat "$FIX/out.txt")"
[[ -d "$FIX/repo/.worktrees/cc-auto" ]] || fail "C3: auto-discover reaped a seat lane — the original incident"
ok "seat lane skipped by auto-discover and still on disk"
rm -rf "$FIX"

echo "== C4 control: auto-discover DOES reap a hub worktree on the merged branch =="
# Without this, C3 passes for free on any script that never removes anything.
FIX="$(make_fixture)"
(cd "$FIX/repo" && git worktree add -q "$FIX/repo/.worktrees/hub-auto" "$BR" >/dev/null)
run_cleanup "$FIX" "$BR"
[[ $RC -eq 0 ]] || fail "C4: expected exit 0, got $RC"
if [[ -d "$FIX/repo/.worktrees/hub-auto" ]]; then fail "C4: hub worktree survived auto-discover — C3 proves nothing"; fi
ok "hub worktree reaped by auto-discover"
rm -rf "$FIX"

echo "== C5: the allowlist's broad basename clause is deliberate, and pinned =="
# `[[ "$(basename "$wt")" == hub-* ]]` accepts a hub-* basename ANYWHERE, not
# only under .worktrees/. That is load-bearing rather than sloppy: a relative
# path like `.worktrees/hub-x` does NOT match `*/.worktrees/hub-*`, which needs
# a component before the slash — so narrowing the predicate without normalising
# the path first would reject the invocation form a human is most likely to
# type. Hub ruling 2026-07-28: keep the clause, pin the behaviour here, and bank
# realpath normalisation as a follow-on rather than doing it in this PR.
# The REFUSE message previously promised "basename hub-* under .worktrees/",
# a constraint the predicate does not apply; corrected in this PR so the two
# describe the same rule. This case is what will notice if they drift apart
# again.
FIX="$(make_fixture)"
(cd "$FIX/repo" && git worktree add -q "$FIX/repo/hub-outside" -b t1 >/dev/null)
run_cleanup "$FIX" "$BR" "$FIX/repo/hub-outside"
[[ $RC -eq 0 ]] || fail "C5: broad basename clause no longer accepts hub-* outside .worktrees/ (got $RC) — if that was deliberate, update this pin AND the relative-path case"
if [[ -d "$FIX/repo/hub-outside" ]]; then fail "C5: expected the broad clause to accept and reap this path"; fi
ok "hub-* basename outside .worktrees/ is accepted, and the REFUSE message now says so"
rm -rf "$FIX"

if [[ $FAILED -ne 0 ]]; then
  echo "hub-cleanup ownership gate: FAILURES above" >&2
  exit 1
fi
echo "OK hub-cleanup ownership-gate pins (C0-C5)"
