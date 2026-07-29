#!/bin/bash
# tests/test_hold_damp.sh — HOLD-DAMP-V2 battery (WO-HOLD-DAMP-PROTOCOL, #217).
#
# Proves the HOLD damping amendment in heartbeat.sh: marker detection, IDLE-KICK
# suppression, the periodic HOLD-CHECK, the agent ACK, and the exit-43 dead-man.
#
# USAGE:  HEARTBEAT=/path/to/heartbeat.sh bash tests/test_hold_damp.sh
#
# HEARTBEAT is REQUIRED and has NO DEFAULT — deliberately. The obvious default
# would be the live deployed script, and a test that reads live runtime state fails
# exactly when the product is in use and then looks like somebody's regression. It
# would also make this battery's verdict depend on which machine ran it. Point it at
# whichever copy you mean to certify.
#
# Everything runs in a private temp coord-dir. Nothing here touches a live coord
# file, a live pidfile, or a running heartbeat.

set -u

if [[ -z "${HEARTBEAT:-}" ]]; then
  echo "FATAL: set HEARTBEAT=<path to heartbeat.sh>. There is no default (see header)." >&2
  exit 2
fi
if [[ ! -f "$HEARTBEAT" ]]; then
  echo "FATAL: HEARTBEAT=$HEARTBEAT does not exist." >&2
  exit 2
fi
HEARTBEAT="$(cd "$(dirname "$HEARTBEAT")" && pwd)/$(basename "$HEARTBEAT")"

PASS=0
FAIL=0
FAILED_NAMES=""

ok()   { PASS=$((PASS+1)); printf '  ok   %s\n' "$1"; }
bad()  { FAIL=$((FAIL+1)); FAILED_NAMES="$FAILED_NAMES
    - $1"; printf '  FAIL %s\n       %s\n' "$1" "${2:-}"; }

check() { # name, expected, actual
  if [[ "$2" == "$3" ]]; then ok "$1"; else bad "$1" "expected [$2] got [$3]"; fi
}

TMPROOT=$(mktemp -d "${TMPDIR:-/tmp}/holddamp.XXXXXX")
FAKE_WATCHER_PID=""

cleanup() {
  # Process hygiene (AMEND-PROCESS-HYGIENE-20260726): anything this battery starts,
  # this battery reaps. Kill by RECORDED pid only — never pkill -f, whose pattern
  # would also match this script's own command line.
  if [[ -n "$FAKE_WATCHER_PID" ]] && kill -0 "$FAKE_WATCHER_PID" 2>/dev/null; then
    kill "$FAKE_WATCHER_PID" 2>/dev/null
  fi
  rm -rf "$TMPROOT"
}
trap cleanup EXIT

# ─────────────────────────────────────────────────────────────────────────────
# Unit layer — the HOLD functions, lifted out of the script and evaluated here.
#
# The script ends in an infinite main loop, so it cannot simply be sourced. We
# extract the region between the HOLD-DAMP banner and the main-loop banner and eval
# that. If the extraction ever comes up empty the battery fails loudly rather than
# silently testing nothing.
# ─────────────────────────────────────────────────────────────────────────────

HOLD_SRC=$(awk '/^# ── HOLD damping \(HOLD-DAMP-V2/{f=1} /^# ── main loop/{f=0} f' "$HEARTBEAT")

if [[ -z "$HOLD_SRC" ]]; then
  echo "FATAL: could not extract the HOLD-DAMP block from $HEARTBEAT." >&2
  echo "       Either the script is unpatched, or the banner text moved." >&2
  exit 2
fi
if ! printf '%s\n' "$HOLD_SRC" | grep -q 'detect_hold_marker()'; then
  echo "FATAL: extracted block does not define detect_hold_marker." >&2
  exit 2
fi

now_epoch() { date +%s; }        # stub — the real one lives above the extracted region
IDENTITY="impl-test"
ROLE="implementer"
COORD_DIR="$TMPROOT/coord"
SCRIPT_ABS="$HEARTBEAT"
CADENCE=1
HOLD_CHECK_INTERVAL=1
HOLD_ACK_TICKS=2
mkdir -p "$COORD_DIR"
HOLD_PENDING_FILE="$TMPROOT/hold-check.pending"
HOLD_TICKS_FILE="$TMPROOT/hold-check.ticks"
HOLD_LAST_FILE="$TMPROOT/hold-check.last"

eval "$HOLD_SRC"

MY_FILE="$TMPROOT/unit-outbox.md"

# Real header shapes, copied from the live coord dir — emoji and all.
H_STATUS_HELD='### 2026-07-29T10:00:00Z — impl-test → orchestrator — 📋 STATUS [HOLD:live-prove-wait]'
H_STATUS_PLAIN='### 2026-07-29T10:05:00Z — impl-test → orchestrator — 📋 STATUS [WO-FOO]'
H_HEARTBEAT='### 2026-07-29T10:10:00Z — impl-test → impl-test — 💓 HEARTBEAT [self-nudge]'
H_HOLDCHECK='### 2026-07-29T10:11:00Z — impl-test → orchestrator — 💓 HEARTBEAT [HOLD:live-prove-wait · HOLD-CHECK:2026-07-29T10:11:00Z]'
H_ACK_HOLD='### 2026-07-29T10:12:00Z — impl-test → orchestrator — 🤝 ACK [HOLD-CHECK:2026-07-29T10:11:00Z]'
H_ACK_PLAIN='### 2026-07-29T10:13:00Z — impl-test → orchestrator — 🤝 ACK [WO-FOO]'
H_WATCHERDOWN='### 2026-07-29T10:14:00Z — impl-test → orchestrator — ⚠️ WATCHER-DOWN'
H_NEWTAG='### 2026-07-29T10:15:00Z — impl-test → orchestrator — 🔀 MERGE-ARMED [WO-FOO]'
H_ABOUT_HB='### 2026-07-29T10:16:00Z — impl-test → orchestrator — 📋 STATUS [WO-FIX-HEARTBEAT-DEADMAN]'

mk() { printf '%s\n\nbody text\n' "$@" > "$MY_FILE"; }

echo "── unit: detect_hold_marker ──"

mk "$H_STATUS_HELD"
detect_hold_marker
check "held marker on the latest substantive header engages damping" "1" "$HOLD_ACTIVE"
check "hold name is extracted"                                        "live-prove-wait" "$HOLD_NAME"

mk "$H_STATUS_PLAIN"
detect_hold_marker
check "an unmarked substantive header is not a hold" "0" "$HOLD_ACTIVE"

# The F6 regression pin. The ratified draft specified detection as
#   ### .*— (STATUS|HEADS-UP|HANDOFF|ACK|DECISION|PROCESS-NOTE|DEPLOY)
# which anchors the tag word immediately after "— ". Every real header puts an emoji
# there, so that regex matched 0 of 5034 headers in the live coord dir and HOLD
# damping would have been an inert no-op. This test fails if anyone reintroduces it.
WO_DRAFT_RE='### .*— (STATUS|HEADS-UP|HANDOFF|ACK|DECISION|PROCESS-NOTE|DEPLOY)'
mk "$H_STATUS_HELD"
n=$(grep -cE "$WO_DRAFT_RE" "$MY_FILE")
check "the ratified draft's regex really does miss real headers (documents why we deviated)" "0" "$n"
detect_hold_marker
check "...and the shipped detector sees the same header anyway" "1" "$HOLD_ACTIVE"

mk "$H_STATUS_HELD" "$H_STATUS_PLAIN"
detect_hold_marker
check "a later unmarked substantive message clears the hold" "0" "$HOLD_ACTIVE"

mk "$H_STATUS_HELD" "$H_HEARTBEAT"
detect_hold_marker
check "a heartbeat after the marker does not clear the hold" "1" "$HOLD_ACTIVE"

mk "$H_STATUS_HELD" "$H_HOLDCHECK"
detect_hold_marker
check "the HOLD-CHECK entry itself does not clear the hold" "1" "$HOLD_ACTIVE"

# Rule 6 exclusion — the grammar fix. Without it, ACKing the 2-hourly liveness check
# would clear the very hold it is proving you are alive under: proving you are there
# would un-hold you every two hours.
mk "$H_STATUS_HELD" "$H_HOLDCHECK" "$H_ACK_HOLD"
detect_hold_marker
check "a HOLD-CHECK ACK does not clear the hold (Rule 6 exclusion)" "1" "$HOLD_ACTIVE"

mk "$H_STATUS_HELD" "$H_ACK_PLAIN"
detect_hold_marker
check "an ordinary ACK is substantive and DOES clear the hold" "0" "$HOLD_ACTIVE"

mk "$H_STATUS_HELD" "$H_WATCHERDOWN"
detect_hold_marker
check "a WATCHER-DOWN alert does not clear the hold" "1" "$HOLD_ACTIVE"

# Fail-loud default: a tag nobody enumerated must count as substantive, so an
# unrecognised message resumes IDLE-KICK rather than leaving the seat quietly damped.
mk "$H_STATUS_HELD" "$H_NEWTAG"
detect_hold_marker
check "an unrecognised NEW tag defaults to substantive and clears the hold" "0" "$HOLD_ACTIVE"

# Exclusion is tag-scoped, not line-scoped: a STATUS *about* the heartbeat is a real
# message. Matching "HEARTBEAT" anywhere on the line would swallow it and leave the
# seat damped — the fail-silent direction.
mk "$H_STATUS_HELD" "$H_ABOUT_HB"
detect_hold_marker
check "a STATUS whose WO id contains HEARTBEAT still counts as substantive" "0" "$HOLD_ACTIVE"

mk '### 2026-07-29T10:00:00Z — impl-test → orchestrator — 📋 STATUS [HOLD:]'
detect_hold_marker
check "an empty hold name is not a hold (grammar requires [^]]+)" "0" "$HOLD_ACTIVE"

mk '### 2026-07-29T10:00:00Z — impl-test → orchestrator — 📋 STATUS [HOLD:max pace-down]'
detect_hold_marker
check "a hold name containing spaces is extracted whole" "max pace-down" "$HOLD_NAME"

rm -f "$MY_FILE"
detect_hold_marker
check "a missing outbox is not a hold" "0" "$HOLD_ACTIVE"

: > "$MY_FILE"
detect_hold_marker
check "an empty outbox is not a hold (Accept #6 — fresh seat behaves as today)" "0" "$HOLD_ACTIVE"

# ─────────────────────────────────────────────────────────────────────────────
# Integration layer — run the real script against a private coord dir.
# ─────────────────────────────────────────────────────────────────────────────
echo
echo "── integration: the running script ──"

ID="impl-holdtest"

# A fake watcher whose command line contains "watch-coordination.sh", so the script's
# PID-reuse guard accepts it and the dead-man never trips during these runs.
cat > "$TMPROOT/watch-coordination.sh" <<'W'
#!/bin/bash
sleep 600
W
chmod +x "$TMPROOT/watch-coordination.sh"
"$TMPROOT/watch-coordination.sh" &
FAKE_WATCHER_PID=$!

# Assertions must target the real markers, not prose that MENTIONS them. The
# HOLD-CHECK body explains what it is by naming "IDLE-KICK" and "HOLD-WAKE-UNACKED"
# in its own text, so a bare `grep -q IDLE-KICK` matches the explanation and reports
# a kick that never happened — and `grep -q HOLD-WAKE-UNACKED` passes green while the
# alert it claims to see was never posted. Anchor to the emitted line shapes.
has_kick()       { grep -qE '^⚡ \*\*IDLE-KICK\*\*' "$1"; }
has_wake_alert() { grep -qE '^### .*⚠️ HOLD-WAKE-UNACKED' "$1"; }

setup_seat() { # $1 = outbox content (may be empty)
  rm -rf "$TMPROOT/c"
  mkdir -p "$TMPROOT/c/.watch-state/$ID"
  printf '%s' "$FAKE_WATCHER_PID" > "$TMPROOT/c/.watch-state/$ID/watcher.pid"
  if [[ -n "${1:-}" ]]; then printf '%s\n\nbody\n' "$1" > "$TMPROOT/c/$ID.md"
  else : > "$TMPROOT/c/$ID.md"; fi
  # Backdate the outbox so the seat reads as idle on the very first tick.
  touch -t 202001010000 "$TMPROOT/c/$ID.md"
}

OUT=""
RC=""
run_hb() { # $1 = seconds to let it run, rest = extra args
  local secs="$1"; shift
  local log="$TMPROOT/hb.log"
  : > "$log"
  bash "$HEARTBEAT" --identity "$ID" --role implementer --dir "$TMPROOT/c" \
       --idle-threshold 1 --cadence 1 "$@" > "$log" 2>&1 &
  local pid=$!
  local waited=0
  while kill -0 "$pid" 2>/dev/null && [[ $waited -lt $((secs * 10)) ]]; do
    sleep 0.1
    waited=$((waited + 1))
  done
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null; wait "$pid" 2>/dev/null; RC="RUNNING"
  else
    wait "$pid" 2>/dev/null; RC=$?
  fi
  OUT=$(cat "$log")
}

# Control FIRST: prove this harness can actually observe an IDLE-KICK. Without this,
# "no IDLE-KICK appeared" in the damped case would be unfalsifiable — a harness that
# can never see a kick would report the damping test green for the wrong reason.
setup_seat ""
run_hb 4
if has_kick "$TMPROOT/c/$ID.md"; then
  ok "control: an UNHELD seat still gets its IDLE-KICK (harness can see a kick)"
else
  bad "control: an UNHELD seat still gets its IDLE-KICK" "no IDLE-KICK in outbox; log: $OUT"
fi

setup_seat '### 2026-07-29T10:00:00Z — impl-holdtest → orchestrator — 📋 STATUS [HOLD:live-prove-wait]'
run_hb 4 --hold-check-interval 9000
if has_kick "$TMPROOT/c/$ID.md"; then
  bad "a HELD seat gets no IDLE-KICK" "IDLE-KICK was appended anyway"
else
  ok "a HELD seat gets no IDLE-KICK"
fi
if printf '%s' "$OUT" | grep -q "HOLD 'live-prove-wait' active"; then
  ok "the damped tick says so on stdout"
else
  bad "the damped tick says so on stdout" "log: $OUT"
fi

setup_seat '### 2026-07-29T10:00:00Z — impl-holdtest → orchestrator — 📋 STATUS [HOLD:live-prove-wait]'
run_hb 6 --hold-check-interval 1
if grep -q 'HOLD-CHECK:' "$TMPROOT/c/$ID.md"; then
  ok "a HOLD-CHECK is posted once the interval elapses"
else
  bad "a HOLD-CHECK is posted once the interval elapses" "outbox tail: $(tail -3 "$TMPROOT/c/$ID.md")"
fi
if [[ -s "$TMPROOT/c/.watch-state/$ID/hold-check.pending" ]]; then
  ok "the pending nonce is recorded in state"
else
  bad "the pending nonce is recorded in state" "pending file empty/absent"
fi
if has_kick "$TMPROOT/c/$ID.md"; then
  bad "the HOLD-CHECK carries no IDLE-KICK body" "a real ⚡ IDLE-KICK marker was appended"
else
  ok "the HOLD-CHECK carries no IDLE-KICK body"
fi

# exit 43 — no agent ACK.
setup_seat '### 2026-07-29T10:00:00Z — impl-holdtest → orchestrator — 📋 STATUS [HOLD:live-prove-wait]'
run_hb 12 --hold-check-interval 1
check "an unACKed HOLD-CHECK self-terminates with exit 43" "43" "$RC"
if has_wake_alert "$TMPROOT/c/$ID.md"; then
  ok "...and posts an addressed ⚠️ HOLD-WAKE-UNACKED"
else
  bad "...and posts an addressed ⚠️ HOLD-WAKE-UNACKED" "not in outbox"
fi
if printf '%s' "$OUT" | grep -q 'exit 43'; then
  ok "...and prints a loud stdout banner naming exit 43"
else
  bad "...and prints a loud stdout banner naming exit 43" "log: $OUT"
fi
# The dead-man must not forgive itself. append_hold_check resets hold-check.ticks to 0,
# so if a new check were posted on the interval while one was still outstanding, the
# counter would restart every tick and exit 43 could never be reached. This run uses
# --hold-check-interval 1 with cadence 1 precisely so a re-asking implementation would
# post many; a correct one asks once and waits for the deadline.
nchecks=$(grep -cE '^### .*💓 HEARTBEAT \[HOLD:.*HOLD-CHECK:' "$TMPROOT/c/$ID.md")
check "exactly one HOLD-CHECK is outstanding at a time (no self-forgiving re-ask)" "1" "$nchecks"

# The agent ACKs -> damping continues, no exit 43.
setup_seat '### 2026-07-29T10:00:00Z — impl-holdtest → orchestrator — 📋 STATUS [HOLD:live-prove-wait]'
(
  # Stand in for a present, responsive agent: ACK every distinct nonce for the whole
  # run. Answering only the FIRST check would be an agent that went quiet after one
  # reply, and exit 43 on that is correct behaviour, not a bug to test away.
  last=""; i=0
  while [[ $i -lt 45 ]]; do
    sleep 0.3
    i=$((i+1))
    n=$(cat "$TMPROOT/c/.watch-state/$ID/hold-check.pending" 2>/dev/null)
    if [[ -n "$n" && "$n" != "$last" ]]; then
      printf '\n### %s — %s → orchestrator — 🤝 ACK [HOLD-CHECK:%s]\n\nstill here.\n' \
        "$(date -u +%FT%TZ)" "$ID" "$n" >> "$TMPROOT/c/$ID.md"
      last="$n"
    fi
  done
) &
ACKER=$!
run_hb 12 --hold-check-interval 1
wait $ACKER 2>/dev/null
check "an ACKed HOLD-CHECK does NOT exit 43" "RUNNING" "$RC"
if printf '%s' "$OUT" | grep -q 'ACKed by agent'; then
  ok "...the ACK is recognised and damping continues"
else
  bad "...the ACK is recognised and damping continues" "log: $OUT"
fi
if has_kick "$TMPROOT/c/$ID.md"; then
  bad "...and the ACK did not un-hold the seat (Rule 6)" "IDLE-KICK resumed after the ACK"
else
  ok "...and the ACK did not un-hold the seat (Rule 6)"
fi

# Clearing a hold while a check is pending must never trip the alarm: the clearing
# message is itself proof of life.
setup_seat '### 2026-07-29T10:00:00Z — impl-holdtest → orchestrator — 📋 STATUS [HOLD:live-prove-wait]'
(
  for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
    sleep 0.4
    if [[ -s "$TMPROOT/c/.watch-state/$ID/hold-check.pending" ]]; then
      printf '\n### %s — %s → orchestrator — 🛰️ HEADS-UP\n\nhold lifted, back on the lane.\n' \
        "$(date -u +%FT%TZ)" "$ID" >> "$TMPROOT/c/$ID.md"
      break
    fi
  done
) &
CLEARER=$!
run_hb 12 --hold-check-interval 1
wait $CLEARER 2>/dev/null
check "clearing a hold with a check pending does not exit 43" "RUNNING" "$RC"
if printf '%s' "$OUT" | grep -q 'hold cleared with HOLD-CHECK'; then
  ok "...the pending check is resolved by the clearing message"
else
  bad "...the pending check is resolved by the clearing message" "log: $OUT"
fi

echo
echo "── contract ──"

HELP=$(bash "$HEARTBEAT" --help 2>&1); HRC=$?
check "--help exits 0" "0" "$HRC"
if printf '%s' "$HELP" | grep -q -- '--hold-check-interval'; then
  ok "--help documents --hold-check-interval (Accept #1)"
else
  bad "--help documents --hold-check-interval (Accept #1)" "help: $HELP"
fi
# Written as an existence check on a FRESH dir. The lazy form
#   [[ -f pidfile ]] || bash --help
# is true whenever --help exits 0, i.e. it can never fail.
rm -rf "$TMPROOT/helpcheck"; mkdir -p "$TMPROOT/helpcheck/.watch-state/$ID"
bash "$HEARTBEAT" --identity "$ID" --role implementer --dir "$TMPROOT/helpcheck" --help >/dev/null 2>&1
if [[ -e "$TMPROOT/helpcheck/.watch-state/$ID/heartbeat.pid" ]]; then
  bad "--help still writes no pidfile" "a pidfile appeared"
else
  ok "--help still writes no pidfile"
fi

if bash -n "$HEARTBEAT" 2>/dev/null; then
  ok "the script parses (bash -n)"
else
  bad "the script parses (bash -n)" "$(bash -n "$HEARTBEAT" 2>&1)"
fi

echo
echo "═══ $PASS passed, $FAIL failed ═══"
if [[ $FAIL -gt 0 ]]; then
  printf 'failed:%s\n' "$FAILED_NAMES"
  exit 1
fi
exit 0
