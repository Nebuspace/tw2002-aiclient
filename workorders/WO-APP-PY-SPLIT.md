# WO-APP-PY-SPLIT

## Goal

Bring `tw2002_aiclient/app.py` under the **1500-line** project cap by extracting the
play-shell loop and its play-only helpers into a dedicated module. **Zero runtime
behavior change** — refactor only.

## Scope

Owned paths:

- `tw2002_aiclient/app.py` (shrink; keep public entrypoints)
- `tw2002_aiclient/app_play.py` (new — play loop + co-located helpers)
- `tests/` only where imports must be updated (prefer **re-exports on `app`** so tests
  keep patching `tw2002_aiclient.app` / `app_mod._daemon_status_provider`)

Branch: `wo/APP-PY-SPLIT` · seat: `impl-claudecode-aiclient`

## Constraints

- **No** logic, string, timing, or control-flow changes in the play loop.
- Move as a **coherent unit** at minimum:
  - `_run_play`
  - `_attempt_attach`, `_explore_status_line_from_wire`, `_poll_explore_status`
  - `_daemon_status_provider`, `_preview_relaunch_sends`
  - explore-offer constants used only inside `_run_play` (relocate with the loop)
- Keep `main`, `_run`, launcher/create/bank paths, terminal guard/getch helpers in
  `app.py` unless needed for import cycles.
- **`tw2002_aiclient.app` compatibility:** re-export any symbol tests or docs reference
  by qualified name (`app._run_play`, `app._daemon_status_provider`, explore-offer
  constants, etc.).
- No new dependencies.

## Build wave

1. **Extract lane:** create `app_play.py`, wire imports, re-export from `app.py`.
2. **Proof lane:** full offline `suite`; spot-check pty tests that patch `app_mod`.
3. **Adversarial review:** import-cycle check; grep for stale `app.py`-only private
   imports; line count `wc -l app.py` ≤ 1500.

## Accept

1. `wc -l tw2002_aiclient/app.py` ≤ **1500**.
2. `tw2002_aiclient/__main__.py` unchanged behavior (`main` still on `app`).
3. All existing imports from `tw2002_aiclient.app` used in tests still resolve
   (directly or via re-export).
4. Full offline **suite** green.
5. No unrelated edits.

## Proof

- `wc -l tw2002_aiclient/app.py tw2002_aiclient/app_play.py`
- Full offline `suite`.
- Live: **DEFERRED → Cursor** (TUI/play path — hub diversity prove after merge if
  product-touch bar applies; otherwise hub documents `n/a` with reason).

## References

- Project line-cap rule (TypeScript/Python **1500**)
- `tw2002_aiclient/app.py` (1603 lines at WO authoring)
