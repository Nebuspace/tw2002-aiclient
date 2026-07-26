# Hub laptop checklist — multi-host ensure re-prove

**WO:** `WO-ENSURE-MULTIHOST-REPROVE` · **PR:** #20  
**Fill matrix:** `audit/live-ensure-matrix-reprove-20260726.md`  
**Bank (paths only):** `TW_CONFIG_DIR=/tmp/tw2002-live-ensure-matrix-20260726T0801Z`  
Keys present (hub 18:20Z): `proof_anet` · `proof_micro` · `proof_rogue` · `proof_rogue_new` — **never paste values into coord/git**.

Cursor Shell is often no-exit — **hub runs every live cell**.

---

## Preconditions

1. Checkout tip under test = `origin/main` at or after `7e43af6` (or FF that includes blank-reject before micro cell).
2. Confirm bank dir exists, mode `700`, credential files `0600`, **outside** the repo.
3. Confirm you will **not** touch Max’s default `config/` / xeno profile.
4. For every `ensure`/`status`/`stop`: set **both** `TW_CONFIG_DIR` **and** `--run-dir` (or `TW_RUN_DIR`). Isolated config without run-dir is fail-closed (rc 2).
5. Never commit bank contents; only redacted matrix rows land in `audit/`.

---

## Per-cell recipe (copy pattern)

```bash
cd "$(git rev-parse --show-toplevel)"   # tw2002-aiclient tip under test
export TW_CONFIG_DIR=/tmp/tw2002-live-ensure-matrix-20260726T0801Z
CELL_RUN=/tmp/tw2002-live-ensure-matrix-20260726T0801Z/reprove/<cell-id>
mkdir -p "$CELL_RUN"
chmod 700 "$CELL_RUN"

# NEW (or RETURNING after a prior PASS that persisted the bank key)
./tw ensure --profile <proof_*> --run-dir "$CELL_RUN" --json > "$CELL_RUN/ensure.json"
./tw status --run-dir "$CELL_RUN" --json > "$CELL_RUN/status.json"
# PASS criterion: settled class / ensure ok cites main_command (or equivalent post-login stable)
./tw stop --run-dir "$CELL_RUN"
```

Redact before any paste: no credentials, handles, or raw frames with private content.

---

## Ordered cells

| Step | Cell | Profile | Do | Pass / honest fail |
|---|---|---|---|---|
| 1a | rogue NEW | `proof_rogue_new` or sacrificial NEW key | ensure → stop | `main_command` |
| 1b | rogue RETURNING | `proof_rogue` (persisted) | fresh run-dir → ensure | `main_command` |
| 2a | a-net NEW | `proof_anet` (+ register if needed) | ensure | Prefer `main_command`; if FAIL record class@step (no invent) |
| 2b | a-net RETURNING | same after persist | fresh run-dir → ensure | `main_command` or honest FAIL |
| 3 | micro NEW | `proof_micro` | **Only after** blank-reject on main; else mark SKIP/FAIL residual | Expect prior blank-reject shape gone → `main_command` or new honest class |
| 4 | xeno | prior capture / optional read-only | **Do not invent** `[A]` as `game_select`; halt cell = N-A or FAIL `unknown`@6 citing `audit/xeno-fingerprint-20260726.md` | Honest halt |

Do **not** wait on micro to finish rogue + a-net.

---

## After live

1. Fill the Results matrix in `audit/live-ensure-matrix-reprove-20260726.md` (outcomes + error class + evidence paths).
2. Commit/push redacted fill on PR #20 if Cursor tip already merged prep — or hub amends tip.
3. Post GitHub `live-prove` Check Run (hub-only).
4. Merge when suite + live-prove green.

---

## Out of bounds

- `session/login.py` (CC blank-reject)
- Xeno Phase-2 product invent
- Autopilot / Manual `game_select` auto-pick
- Credential material or handles in coord / PR body / audit prose
