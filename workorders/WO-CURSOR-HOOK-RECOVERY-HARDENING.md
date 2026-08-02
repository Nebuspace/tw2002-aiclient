# WO-CURSOR-HOOK-RECOVERY-HARDENING — a fail-closed shell gate whose disarm lives in a tracked file

**ID:** WO-CURSOR-HOOK-RECOVERY-HARDENING
**Branch:** `wo/CURSOR-HOOK-RECOVERY-HARDENING`
**Seat:** unassigned (hub to route)
**Priority:** HIGH — takes a seat fully offline; recovery requires the tool it disables
**Size:** S (config + docs; no product code)
**Banked by:** `impl-claudecode-aiclient`, 2026-07-28, per hub ruling @ 07:30:15Z
**Status:** DONE · origin `d28811d` (#289) · tip-honesty stamp 2026-08-02 (product on main; banner was stale READY)
**Seat:** `impl-aiclient-cursor`

---

## Goal

Make Cursor-seat shell recovery **structural** rather than "remember to keep a tracked file
dirty." Today the documented disarm is destroyed by ordinary git operations, and when it is
destroyed the seat loses the shell it would need to restore it.

## Background — measured, not assumed

`tw2002-aiclient/.cursor/hooks.json` (tracked) wires:

```json
"beforeShellExecution": [{ "command": ".cursor/hooks/path-leak-gate.sh", "failClosed": true }]
```

`CLAUDE.md` documents that Cursor's worker extension host often cannot execute command hooks
(`Shell execution is not available in the worker extension host`), and that loading the tip
`failClosed: true` config into the live Cursor config therefore denies **all** Shell tool
calls — not only commits. Its prescribed remedy is a **local, uncommitted, empty**
`.cursor/hooks.json` (`"hooks": {}`) overlay.

Measured 2026-07-28: the working copy was **byte-identical to tip** — the overlay was absent
and `impl-aiclient-cursor`'s shell was dead.

## Why this recurs (the actual defect)

1. **The disarm is an uncommitted edit to a TRACKED file.** `git checkout`, `reset --hard`, or
   a fresh `worktree add` silently restores `failClosed: true`. Nobody edits the gate to break
   it — they check out a branch.
2. **Failure is total and silent.** Fail-closed on an unresolvable hook denies *every* shell
   call, with no announcement, until the seat simply stops working.
3. **It disables its own repair path.** The fix is a shell command; the failure mode is
   "no shell." A self-sealing outage — recovery must come from another seat or out-of-band.
4. **The hook command is RELATIVE** (`.cursor/hooks/path-leak-gate.sh`), so it resolves only
   from a directory containing `.cursor/`. Verified: resolves from the repo root and from
   worktrees; does **not** resolve from `…/Nebuspace`. With `failClosed: true`, an
   unresolvable path denies everything.

## Scope

| Action | Path |
|---|---|
| Harden hook invocation / disarm mechanism | `.cursor/hooks.json`, `.cursor/hooks/` |
| Document the recovery step | `CLAUDE.md` (seat bootstrap section) |

**Out of bounds:** any weakening of the actual path-leak protection. The `git`-level backstop
(`core.hooksPath=scripts/githooks` + `scripts/githooks/pre-commit`) is **proven armed and
effective** — verified 2026-07-28 with both controls: a staged operator-home path gives
`git commit` exit 1 with HEAD unmoved, and a clean staged file still commits (exit 0). That
layer must keep working exactly as it does today. This WO changes only how the *Cursor
shell-hook* layer fails and is recovered.

## Options (pick one; hub/Max to rule)

- **(a) Absolute-resolve the hook command** so cwd cannot ENOENT it.
- **(b) Move the disarm to a file the tip never overwrites** (untracked path, env var, or
  local git config), so routine git operations cannot re-arm it.
- **(c) Narrow the blast radius** — scope fail-closed to the operations actually being
  protected (commit/push), never to every shell call. A path-leak check has no business
  gating `ls`.
- **(d) Leave as-is; document the recovery step in seat bootstrap.**

Author's note: (c) is the one that addresses the *severity* rather than the *trigger* — the
others reduce how often the trap springs, (c) reduces what happens when it does. (b) and (c)
compose.

## Accept

- A Cursor seat that runs `git checkout` / `reset --hard` / `worktree add` retains a usable
  shell **without** a manual re-disarm step, OR the required step is emitted as an explicit,
  visible instruction rather than silent denial.
- The commit-time path-leak guarantee is **unchanged** — re-prove with both controls
  (leaky file blocked with HEAD unmoved; clean file commits).
- `CLAUDE.md` states the recovery procedure for a seat that is already shell-dead, including
  that it cannot be self-executed.

## Proof

Both controls on the commit gate, plus a demonstration that the shell survives the git
operation that previously disarmed the overlay. State explicitly which harness the proof ran
on — Claude Code does not read `.cursor/hooks.json` at all and therefore **cannot** prove this
one; it needs the Cursor seat.

## Refs

- `CLAUDE.md` → Hard rules → Path-leak gate (dual-layer design, local agent overlay)
- `workorders/WO-HOOKSPATH-SEAT-NOTE.md` (DONE — documented the path; did not harden recovery)
- `scripts/path-leak-scan.sh`, `scripts/githooks/pre-commit`
- Coord: `impl-claudecode-aiclient` @ 2026-07-28T07:29Z (triage) · hub ACK @ 07:30:15Z
