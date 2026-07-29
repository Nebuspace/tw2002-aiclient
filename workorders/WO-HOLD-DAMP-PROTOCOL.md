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

**Amended 2026-07-29 (Option A, hub-ratified).** The original scope listed five paths that
PR #217 cannot carry: `.claude/` and `.samantha/` are gitignored in this repo
(`.gitignore:17` and `.gitignore:16`), and the live files sit in the parent workspace
`Nebuspace/`, which is not a git repository at all. Delivery is therefore split.

**Carried by PR #217 (`impl-claudecode-aiclient`):**

- `tests/test_hold_damp.sh` — the proof battery, parameterised on `HEARTBEAT=<path>`
- `workorders/WO-HOLD-DAMP-PROTOCOL.md` — this file

**Applied to the parent workspace by the hub, from the staged artifact:**

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
- **Apply the live script by atomic replace (`mv`), never by editing in place.** Bash reads
  a running script incrementally from a byte offset, so rewriting the file underneath live
  heartbeats changes what they execute mid-flight. Measured on bash 3.2.57: an in-place
  rewrite of similar length made the running process execute the NEW file's tail; a shorter
  rewrite made it stop dead at the truncation point and **exit 0**. Since `exit 42` is the
  documented dead-man signal *"distinct from the normal cap-reached exit 0"*, a
  truncation-killed heartbeat is indistinguishable from a healthy finish — every seat would
  go deaf while `coord-status.sh` still read BOTH ALIVE. A `mv` leaves the running process
  on the old inode and it finishes intact. This is a Rule 2 transport-clause change.

## HOLD-DAMP-V2 specification (implement exactly this)

### Marker grammar

A seat engages HOLD damping by including `[HOLD:<name>]` in the **header line** of
a substantive outbox entry (STATUS, HEADS-UP, HANDOFF, ACK, DECISION, PROCESS-NOTE
— not HEARTBEAT, not WATCHER-DOWN, not HOLD-CHECK ACK). Name is any non-`]` string.

Marker regex (POSIX ERE, `grep -qE`) — unchanged and correct:
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

**Amended 2026-07-29 — the drafted header regex was inert.** The draft said to find the
most recent substantive header matching:
```
### .*— (STATUS|HEADS-UP|HANDOFF|ACK|DECISION|PROCESS-NOTE|DEPLOY)
```
Measured against the live coord dir, that expression matched **0 of 5034 real headers**, for
two independent reasons: it anchors the tag word immediately after `— `, but every real
header carries an emoji there; and the live tag vocabulary is far wider than those seven
words — `QUEUE-STATUS`, `ACCEPT`, `MERGED`, `CLAIM`, `GO`, `MERGE-ARMED`, `REVISE`,
`CORRECTION` are all in daily use. Implemented literally, HOLD damping would have been a
silent no-op: `HOLD_ACTIVE` always 0, IDLE-KICK never suppressed, HOLD-CHECK never posted,
`exit 43` unreachable — and a battery that only asked "does an unheld seat still work?"
would have passed.

**Ships instead:** enumerate the CLOSED side. Take every `^### … — … — …` header; a header is
**substantive unless** its tag word (text after the final `— `, with any trailing `[…]`
qualifier stripped) contains `HEARTBEAT`, `WATCHER-DOWN`, or `HOLD-WAKE-UNACKED`, or unless
the unstripped tag matches `ACK…[HOLD-CHECK:` (the Rule 6 exclusion, which needs the
qualifier to identify it). The last surviving header is the one tested for `[HOLD:<name>]`.

An unrecognised NEW tag therefore defaults to substantive → clears the hold → IDLE-KICK
resumes. That is the fail-LOUD direction; the closed-list version fails silent, which is the
wrong way round for a mechanism whose only job is to notice that somebody stopped answering.
The qualifier strip matters for the same reason: `📋 STATUS [WO-FIX-HEARTBEAT-DEADMAN]`
contains the word `HEARTBEAT` and must still count as a real message.

One shell function: `detect_hold_marker` — sets `HOLD_ACTIVE=1/0` and `HOLD_NAME`.

### ACK-scan placement (amended 2026-07-29)

Step 4c reads "each cadence tick after a pending HOLD-CHECK", but nesting that scan under
`idle >= IDLE_THRESHOLD` cannot work: posting the HOLD-CHECK appends to the outbox, which
resets the idle clock to ~0, so with shipped defaults the branch is not re-entered for four
more ticks — a "two cadence tick" window is unreachable there, and the agent's own ACK resets
the clock again. The ACK deadline is cadence-based, so `hold_ack_scan` runs at top level in
the main loop, outside the idle gate.

### The ACK scan must be anchored to header lines

`hold_ack_scan` matches `^### .*ACK.*\[HOLD-CHECK:<nonce>\]`. Unanchored, the check **ACKs
itself**: the HOLD-CHECK body prints the exact line the agent should post as a worked
example, so a whole-file substring search finds its own instruction text and clears the
pending check on the tick it was posted. Measured during build — `exit 43` became
unreachable. The worked example is indented inside a code block, so `^###` excludes it.

### Clearing a hold must never trip the alarm

If the hold clears while a HOLD-CHECK is pending, the clearing message is itself the proof of
life the check was asking for: `hold_ack_scan` drops the pending state instead of counting a
missed tick.

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
   are byte-identical **in the direction reference ← live**. They are NOT identical at the
   seed: the live copy (650L, md5 `f0c25ebc46bb…`) carries the self-nudge addressing fix from
   WO-PROCESS-HUB-IDLE-KICK-ADDRESS; the reference copy (644L, md5 `cdb2f15265b9…`) still
   prints the old bare `💓 HEARTBEAT` header. Syncing in the wrong direction would silently
   revert a shipped WO. Patch the LIVE copy, then copy it over the reference; md5-verify both.
8. A third copy exists — `Claude_Samantha/.samantha/references/coordination-protocol/heartbeat.sh`
   (428L, the only git-tracked one, 216 lines behind live). Its reconcile is a separate
   Max-gated framework backport, explicitly **out of this WO's DoD**.
9. All canonical protocol docs list the new HOLD marker grammar and HOLD-CHECK tag.

## Proof

### Where this battery is actually enforced (disclosed gap)

`tests/test_hold_damp.sh` ships in this repo but **CI can never run it**: pytest collects
`.py` only, and no `heartbeat.sh` is tracked anywhere in the tree (`git ls-files | grep
heartbeat.sh` → 0), so nothing in CI can supply `HEARTBEAT=<path>`. A test file that no
gate executes is not a gate — say so rather than let "tests added" imply coverage.

**The enforcement point is therefore the hub apply step, and it is mandatory:** before any
`mv` of a patched `heartbeat.sh` onto a live path, run

```
HEARTBEAT=<the patched copy> bash tests/test_hold_damp.sh
```

and record `N passed, 0 failed` in the apply STATUS. Same for the reference copy after the
`reference ← live` sync. If the coordination scripts are ever vendored into a repo, wire
this battery into that repo's CI and delete this paragraph.

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
