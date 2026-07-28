# WO-PLAY-CHAINS-ARM-LIVE-PROVE — Live diversity prove of L)chains → confirm → taught autoloop

**Status:** OPEN · EXECUTE · HIGH · Cursor (`impl-aiclient-cursor`)  
**Posted:** 2026-07-28T21:15:26Z · Max redirect — stop hygiene; prove the automation already on `main`  
**Seat:** `impl-aiclient-cursor`  
**Depends:** `main` ≥ `e9b8655` · Play arm already shipped (#116) · inventory non-empty  
**Refs:** `WO-PLAY-AUTOLOOP-START` (shipped) · `WO-CHAINS-TUI-FULL` (#147) · `WO-PR-CI-LIVE-PROVE-SPLIT` diversity bar  
**Max GO (this chat):** sacrificial turn-spend on disposable/crawl_sac profiles authorized for this prove only — no prod, no Max bank.

## Goal

The money path **already exists on `main`**: `L)chains` → select **taught** row → confirm `y` → `adapters.autoloop_start`. What Max is owed is **live evidence**, not another EXEC of the wire.

Prove Play can arm a **taught** autoloop on **live TWGS** under the diversity bar.

## Tip-check (do not re-implement)

Confirm present on tip before live work (read-only):

- `adapters.autoloop_start`
- Play `chains_arm` + `arm_confirm` → start (`app.py`)
- Tests: `tests/test_adapters_autoloop_start.py`, `tests/test_play_chains_arm.py`

If any Accept of `WO-PLAY-AUTOLOOP-START` is missing on tip → STOP and `❓` — do not invent a second wire.

## Scope

1. **Stamp honesty:** mark `WO-PLAY-AUTOLOOP-START` **DONE** on this branch (shipped #116; WO status was stale OPEN).
2. **Live prove** the path on ≥3 catalog hosts with ≥1 NEW and ≥1 RETURNING across the run (not both on every host). SKIP untestable cells with reason.
3. Per host cell: ensure @ `main_command` → open `L)chains` → select a **taught** macro (teach first if the profile has none — Record/Trigger already on main) → confirm `y` → prove start (adapter/status/`autoloop status` evidence — no secrets in audit).
4. Discovered rows stay **non-armable** (pin already on tip — do not “fix” by arming finder output).
5. Suite green on the stamp commit; live-prove is the Accept weight.

## Constraints

- Money path: confirm-gated; never silent-arm; bare Enter never starts.
- No re-implementation of `autoloop_start` / Play arm if tip-check passes.
- No `autoloop_resume` invent (refused; relaunch is the other half — already shipped #101).
- No discovered→taught promotion (Max-gated `WO-DISCOVERED-TO-TAUGHT-PROMOTION`).
- Isolated config dirs outside the git tree; never commit secrets.
- Hub posts `hub-live-prove-check.sh` from your STATUS evidence.

## Accept

1. Tip-check recorded: Play arm present (or explicit missing-Accept `❓`).
2. `WO-PLAY-AUTOLOOP-START` status stamped DONE with ship ref `#116`.
3. Live diversity: ≥3 hosts · ≥1 NEW · ≥1 RETURNING · host keys + class counts in STATUS (no secrets).
4. Per successful cell: taught select → `y` → start proven; `N`/cancel cell shows no start.
5. Suite green · PR · STATUS with SHA.

## Proof

Live audit artifact(s) under `/tmp/…` (paths in STATUS only) + suite CI. Hub runs `scripts/hub-live-prove-check.sh <SHA> success|failure|n/a "<summary>"`.

## Explicitly out

- CI hygiene / skip-count / pty_ui census  
- Hub cleanup allowlist (#198 — CC)  
- Canon/ADR for discovered promotion  

---

## Live prove (Cursor · #201 · 2026-07-28)

**Artifact:** `/tmp/tw2002-chains-arm-live-20260728T2119Z/audit/SUMMARY.md`

| host key | class | ensure | y→start | n cancel |
|---|---|---|---|---|
| gone_rogue | RETURNING | PASS | ok=True | clean |
| academy_of_tradewars | RETURNING | PASS | ok=True | clean |
| a_net_online | NEW | PASS | ok=True | clean |
| microblaster_network | RETURNING | SKIP sector_display@12 | — | — |

**Diversity:** 3 hosts · NEW:1 · RETURNING:2 · tip-check OK · PLAY-AUTOLOOP stamped DONE.
