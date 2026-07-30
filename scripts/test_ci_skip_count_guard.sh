#!/usr/bin/env bash
# test_ci_skip_count_guard.sh — pins for WO-TEST-CI-SKIP-COUNT-GUARD.
#
# Proves: missing/empty/toy XML fail closed · skipped!=0 fails ·
# inject @pytest.mark.skip reddens · restore md5-identical · tip green path.
#
# Run: ./scripts/test_ci_skip_count_guard.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
GUARD="$ROOT/scripts/ci_skip_count_guard.py"
PY="${PYTHON:-}"
if [[ -z "$PY" ]]; then
  if [[ -x "$ROOT/.venv/bin/python" ]]; then
    PY="$ROOT/.venv/bin/python"
  else
    # Linked worktree: venv lives on the primary checkout (git-common-dir parent).
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
"$PY" -m py_compile "$GUARD"

FAILED=0
fail() { echo "FAIL: $*" >&2; FAILED=1; }
ok()   { echo "  ok: $*"; }

write_xml() {
  local path="$1" tests="$2" skipped="$3"
  printf '%s' "<?xml version=\"1.0\"?><testsuites><testsuite name=\"pytest\" tests=\"${tests}\" failures=\"0\" errors=\"0\" skipped=\"${skipped}\"/></testsuites>" >"$path"
}

echo "== U1: missing XML =="
set +e
out="$("$PY" "$GUARD" /tmp/ci-skip-guard-missing-$$.xml 2>&1)"
ec=$?
set -e
if [[ "$ec" -eq 1 ]] && printf '%s' "$out" | grep -q 'junitxml missing'; then
  ok "missing fails closed"
else
  fail "missing expected ec=1; got $ec out=$out"
fi

echo "== U2: empty XML =="
empty="$(mktemp)"
: >"$empty"
set +e
out="$("$PY" "$GUARD" "$empty" 2>&1)"
ec=$?
set -e
rm -f "$empty"
if [[ "$ec" -eq 1 ]] && printf '%s' "$out" | grep -q 'junitxml empty'; then
  ok "empty fails closed"
else
  fail "empty expected ec=1; got $ec out=$out"
fi

echo "== U3: implausible tests count (toy) before skipped =="
toy="$(mktemp)"
write_xml "$toy" 3 0
set +e
out="$("$PY" "$GUARD" "$toy" 2>&1)"
ec=$?
set -e
rm -f "$toy"
if [[ "$ec" -eq 1 ]] && printf '%s' "$out" | grep -q 'implausible tests'; then
  ok "toy tests=3 fails before skipped check"
else
  fail "toy expected implausible; got $ec out=$out"
fi

echo "== U4: thousands + skipped!=0 =="
bad="$(mktemp)"
write_xml "$bad" 6243 1
set +e
out="$("$PY" "$GUARD" "$bad" 2>&1)"
ec=$?
set -e
rm -f "$bad"
if [[ "$ec" -eq 1 ]] && printf '%s' "$out" | grep -q 'skipped=1'; then
  ok "skipped!=0 fails"
else
  fail "skipped expected fail; got $ec out=$out"
fi

echo "== U5: thousands + skipped=0 =="
good="$(mktemp)"
write_xml "$good" 6243 0
set +e
out="$("$PY" "$GUARD" "$good" 2>&1)"
ec=$?
set -e
rm -f "$good"
if [[ "$ec" -eq 0 ]] && printf '%s' "$out" | grep -q 'skipped=0'; then
  ok "plausible zero-skip green"
else
  fail "green expected; got $ec out=$out"
fi

echo "== I1: inject @pytest.mark.skip → guard reddens; restore md5-identical =="
TARGET="$ROOT/tests/test_env.py"
[[ -f "$TARGET" ]] || { echo "FAIL: missing $TARGET" >&2; exit 1; }
BEFORE_MD5="$(md5 -q "$TARGET" 2>/dev/null || md5sum "$TARGET" | awk '{print $1}')"
# Insert skip on the first test function def (portable; no /Users path literals).
"$PY" - "$TARGET" <<'PY'
import sys
from pathlib import Path
p = Path(sys.argv[1])
text = p.read_text(encoding="utf-8")
needle = "\ndef test_"
idx = text.find(needle)
if idx < 0:
    raise SystemExit("no test_ function found to inject")
# Place marker immediately before the first test_ def.
inject = "\n@pytest.mark.skip(\"WO-TEST-CI-SKIP-COUNT-GUARD inject probe\")\ndef test_"
# Ensure pytest is imported as pytest for the marker.
if "import pytest" not in text:
    text = "import pytest\n" + text
    idx = text.find(needle)
text = text[:idx] + inject + text[idx + len(needle) :]
p.write_text(text, encoding="utf-8")
print("injected")
PY

XML="$(mktemp "${TMPDIR:-/tmp}/ci-skip-inject.XXXXXX.xml")"
rm -f "$XML"
set +e
"$PY" -m pytest -q -m "not live_login and not pty_ui" --junitxml="$XML" \
  -n auto >/tmp/ci-skip-inject-pytest.out 2>&1
pec=$?
set -e
# Pytest may exit 0 with skips; either way the XML must show skipped>=1.
set +e
out="$("$PY" "$GUARD" "$XML" 2>&1)"
gec=$?
set -e

# Restore BEFORE interpreting results so a pin failure never leaves dirt.
git checkout -- "$TARGET"
AFTER_MD5="$(md5 -q "$TARGET" 2>/dev/null || md5sum "$TARGET" | awk '{print $1}')"

if [[ "$BEFORE_MD5" != "$AFTER_MD5" ]]; then
  fail "inject restore md5 mismatch before=$BEFORE_MD5 after=$AFTER_MD5"
elif [[ "$gec" -eq 1 ]] && printf '%s' "$out" | grep -q 'skipped='; then
  ok "inject reddened guard (pytest_ec=$pec guard_ec=$gec); md5 restored"
else
  fail "inject expected guard ec=1; got guard=$gec pytest=$pec out=$out"
  echo "---- pytest tail ----" >&2
  tail -20 /tmp/ci-skip-inject-pytest.out >&2 || true
fi
rm -f "$XML"

if [[ "$FAILED" -ne 0 ]]; then
  echo "FAILED: $FAILED case(s)" >&2
  exit 1
fi
echo "ALL PASS [ci skip-count guard · skipped==0 pin]"
