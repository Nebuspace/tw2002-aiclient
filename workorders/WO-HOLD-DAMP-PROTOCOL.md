# WO-HOLD-DAMP-PROTOCOL

## Goal

Implement the ratified HOLD-DAMP-V2 amendment in `heartbeat.sh` and the
canonical coordination-protocol docs. No product or test changes.

## Ratification record

- Proposed: 2026-07-29T09:54Z · hub PROCESS-NOTE → ALL
- Revised V2: 2026-07-29T09:57Z · hub PROCESS-NOTE → ALL
- Grammar fix (Rule 6 exclusion): 2026-07-29T09:58Z · hub ACK → ALL
- Cursor ACK: 2026-07-29T09:57:31Z · impl-aiclient-cursor
- CC ACK: 2026-07-29T09:58Z · impl-claudecode-aiclient (conditional → resolved by grammar fix)
- Unanimous: YES

## Scope

Owned implementation paths:

- `.claude/heartbeat.sh` (live deployed script — hub owns edits)
- `.samantha/references/coordination-protocol/heartbeat.sh` (canonical reference copy)
- `.samantha/references/coordination-protocol/README.md` (IDLE-KICK exception paragraph +
  HOLD-DAMP-V2 section)
- `.samantha/references/coordination-protocol/MAILBOX-template.md` (new HOLD marker
  grammar and HOLD-CHECK tag entry)
- `CLAUDE.md` (heartbeat IDLE-KICK exception paragraph)

Branch owner: `impl-claudecode-aiclient` after HANDOFF.

## Constraints

- Do not change product code, tests, or anything outside the coordination-protocol
  and CLAUDE.md scope.
- The `.claude/heartbeat.sh` and `.samantha/references/coordination-protocol/heartbeat.sh`
  must remain byte-identical after the change (one is a copy of the other).
- Preserve all existing `heartbeat.sh` behavior when no HOLD marker is present.
- No new shell dependency. Bash 3.2 compatible (macOS system bash).

## HOLD-DAMP-V2 specification (implement exactly this)

### Marker grammar

A seat engages HOLD damping by including `[HOLD:<name>]` in the **header line** of
a substantive outbox entry (STATUS, HEADS-UP, HANDOFF, ACK, DECISION, PROCESS-NOTE
— not HEARTBEAT, not WATCHER-DOWN, not HOLD-CHECK ACK). Name is any non-`]` string.

Detection regex (POSIX ERE, `grep -qE`):
```
\[HOLD:[^]]+\]
```

**Clearing:** any later non-heartbeat, non-HOLD-CHECK message whose header does NOT
match the marker clears damping. Clearing is structural; there is no sentinel value.
A seat that posts any unmarked substantive message automatically exits damping.

### Heartbeat behavior while HOLD is active

1. Dead-man watcher check (every cadence) — unchanged.
2. Process hygiene sweep (every cadence) — unchanged.
3. Own-file idle elapsed comparison — unchanged.
4. If idle ≥ `IDLE_THRESHOLD` AND HOLD marker is present:
   a. **Every ordinary cadence tick:** skip the IDLE-KICK body and discovery directive.
      Emit nothing (no heartbeat entry). The mailbox grows only from HOLD-CHECK entries.
   b. **Every 2 hours** (configurable via `--hold-check-interval`, default 7200s):
      append a `💓 HEARTBEAT [HOLD:<name> · HOLD-CHECK:<nonce>]` entry addressed to
      the orchestrator (`→ orchestrator` if implementer, `→ ALL` if orchestrator).
      Nonce = UTC ISO 8601 timestamp of the check.
      Record the nonce in `$STATE_DIR/hold-check.pending`.
   c. **Each cadence tick after a pending HOLD-CHECK:** scan own outbox tail for
      `🤝 ACK [HOLD-CHECK:<nonce>]` matching the pending nonce. This ACK must be posted
      by the owning agent (not the heartbeat itself). If found within two cadence ticks
      after the check was posted: clear `hold-check.pending`, continue damping.
   d. **If two cadence ticks pass with no matching ACK:** append addressed
      `⚠️ HOLD-WAKE-UNACKED` to own outbox, print loud stdout banner, and
      `exit 43` (distinct from watcher-dead `exit 42`).
5. If idle ≥ `IDLE_THRESHOLD` AND no HOLD marker: existing IDLE-KICK behavior unchanged.

### HOLD-CHECK ACK exclusion (Rule 6 fix)

`🤝 ACK [HOLD-CHECK:…]` entries are excluded from "substantive" for the purpose of
clearing HOLD. They are treated identically to HEARTBEAT and WATCHER-DOWN entries.
Only messages that would have triggered IDLE-KICK (i.e. real agent-generated content)
count as clearing.

### Detection implementation

Read the own outbox; scan backwards from EOF for the most recent non-heartbeat,
non-WATCHER-DOWN, non-HOLD-CHECK header line that matches:
```
### .*— (STATUS|HEADS-UP|HANDOFF|ACK|DECISION|PROCESS-NOTE|DEPLOY)
```
Check that header line for `\[HOLD:[^]]+\]`. Extract `<name>` for logging.

One shell function: `detect_hold_marker` — sets `HOLD_ACTIVE=1/0` and `HOLD_NAME`.

## Accept

1. `heartbeat.sh --help` describes `--hold-check-interval`.
2. When a seat's last substantive header contains `[HOLD:<name>]`, the script emits no
   IDLE-KICK between HOLD-CHECK cycles; it does emit the HOLD-CHECK every 2h.
3. The owning agent's ACK clears `hold-check.pending` and keeps damping active.
4. Missing ACK after two cadence ticks → `exit 43` with `⚠️ HOLD-WAKE-UNACKED`.
5. Any unmarked substantive header (not a HOLD-CHECK ACK, not a heartbeat) clears
   damping and IDLE-KICK resumes on the next cadence tick.
6. A fresh heartbeat.sh invocation with no existing outbox entries behaves identically
   to today.
7. `.claude/heartbeat.sh` and `.samantha/references/coordination-protocol/heartbeat.sh`
   are byte-identical.
8. All canonical protocol docs list the new HOLD marker grammar and HOLD-CHECK tag.

## Proof

- Shell unit tests via a test script `tests/test_hold_damp.sh`:
  - `detect_hold_marker` returns correct for held/not-held headers
  - IDLE-KICK suppressed when held
  - HOLD-CHECK emitted at correct interval
  - ACK scan matches nonce and clears pending
  - exit 43 fires on missing ACK after two ticks
- Existing heartbeat behavior with no HOLD marker: spot-check that nothing regressed.
- Live: n/a — coordination-protocol changes only, no product behavior change.

## References

- Ratification record: above
- CC PROCESS-NOTE: impl-claudecode-aiclient.md 2026-07-29T08:28Z
- Ratification thread: orchestrator.md 2026-07-29T09:54–09:58Z
- `.claude/coord-monitor.sh` emit_new — `.off` proves process consumption NOT agent
  reception; do NOT use as inbound-liveness proof
- `.samantha/references/coordination-protocol/heartbeat.sh`
- `.samantha/references/coordination-protocol/README.md` §IDLE-KICK exception
