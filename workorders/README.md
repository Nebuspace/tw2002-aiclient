# tw2002-aiclient — product work orders

**Master list: [`ULTRACODE-WO-INVENTORY.md`](ULTRACODE-WO-INVENTORY.md).** Build proceeds **greenfield from `canon/`** — `archive/pre-rebirth-2026-07-23/` is reference-only and is never restored to root (Max GO, WO-ULTRACODE-ADOPT, 2026-07-23). The inventory holds the canon coverage matrix and ~85 executable phased PWOs (Phase 0–9); Phase 0–2 are being materialized as real files (`WO-P0-*.md`, `WO-P1-*.md`, `WO-P2-*.md`) as they're built out — this queue table will point at those as they land.

Grounded in the reborn OKF canon (`canon/`), especially `canon/surfaces/entry-and-profile-selection.md`, `trainer-cockpit.md`, and `mode-line-and-teach-controls.md`.

**`WO-00`…`WO-17` below are LEGACY-SURFACE — non-executable.** They predate the 2026-07-23 root archive and their Proof paths assume product code (`twclient/`, `config/`, `tests/`) at repo root; that code now lives only under `archive/pre-rebirth-2026-07-23/` for reference. Retained for their Goal/Accept/Proof shape and canon citations — see the inventory's §5 current→proposed mapping for each one's replacement PWO(s). Do not execute them as-is.

**Not here (legacy):** daemon QUEUE items from pre-rebirth docs are archived with the old tree — engine/doctrine work is proposed in the ultracode inventory, not the old `QUEUE.md`.

**Path-leak gate:** both Implementer seats refuse commits that stage `/Users/<username>/` (or `/home/<username>/`) paths — Cursor via `.cursor/hooks.json` (`failClosed: true`) + `scripts/githooks/pre-commit` + `scripts/path-leak-scan.sh`; Claude Code via its PreToolUse hook.

## Legacy queue (WO-00…17 — reference only, see banner above)

| # | File | One line |
|---|------|----------|
| 00 | [WO-00-dev-seat-smoke.md](WO-00-dev-seat-smoke.md) | Verify venv, `./tw2002-aiclient --help`, TTY gate |
| 01 | [WO-01-launcher-smoke.md](WO-01-launcher-smoke.md) | **Verify** launcher list · navigate · quit |
| 02 | [WO-02-create-profile-form.md](WO-02-create-profile-form.md) | **Verify** create form saves to profiles.toml |
| 03 | [WO-03-play-shell-chrome.md](WO-03-play-shell-chrome.md) | **Verify** play header · Esc → launcher |
| 04 | [WO-04-ensure-daemon-wire.md](WO-04-ensure-daemon-wire.md) | **Verify** play entry runs ensure → main_command |
| 05 | [WO-05-autopilot-toggle.md](WO-05-autopilot-toggle.md) | **Verify** `a`/Space toggles Autopilot + profile write-back |
| 06 | [WO-06-live-panels-poll.md](WO-06-live-panels-poll.md) | **Verify** GOALS/FOCUS/DECISIONS refresh from `tw status` |
| 07 | [WO-07-intervention-banner.md](WO-07-intervention-banner.md) | **Verify** attention strip when `needs_attention` |
| 08 | [WO-08-human-attach.md](WO-08-human-attach.md) | **Verify** `h` attach · Ctrl-] detach · back to play |
| 09 | [WO-09-world-identity-strip.md](WO-09-world-identity-strip.md) | **Extend** launcher/play header with host · game · character |
| 10 | [WO-10-cockpit-outer-frame.md](WO-10-cockpit-outer-frame.md) | **Build** bordered outer frame per trainer-cockpit canon |
| 11 | [WO-11-game-viewport-center.md](WO-11-game-viewport-center.md) | **Build** 80×24 native game viewport in play screen |
| 12 | [WO-12-logs-panel.md](WO-12-logs-panel.md) | **Extend** full-width `[LOGS]` transcript tail |
| 13 | [WO-13-mode-line-app-human.md](WO-13-mode-line-app-human.md) | **Extend** App/Human mode badge (not `ai_pilot` label) |
| 14 | [WO-14-teach-hotkeys-scaffold.md](WO-14-teach-hotkeys-scaffold.md) | **Build** A/R/T teach affordances + on-demand-only guard |
| 15 | [WO-15-semantic-colors.md](WO-15-semantic-colors.md) | **Polish** shared ok/warn/danger/info palette on product TUI |
| 16 | [WO-16-player-bank-touchpoint.md](WO-16-player-bank-touchpoint.md) | **Extend** rotation bank line + no-collusion boundary text |
| 17 | [WO-17-coverage-meter.md](WO-17-coverage-meter.md) | **Build** taught-vs-escalation coverage strip (read-only) |

## How to run the next WO (greenfield)

1. Read [`ULTRACODE-WO-INVENTORY.md`](ULTRACODE-WO-INVENTORY.md) §4 for the current phase's PWOs; start at Phase 0 (PWO-003, the greenfield package scaffold) if the seat is cold.
2. `cd "$(git rev-parse --show-toplevel)"`
3. Once a phase's PWOs are materialized as real `WO-P<phase>-*.md` files, read the file — **Goal · Scope · Depends-on · Accept · Proof** — same anatomy as the legacy WOs below.
4. If the WO says **Verify**: run Proof commands in an actual terminal; fix only if Accept fails.
5. If the WO says **Build/Extend/Polish**: implement in scoped paths, then run Proof in the app.
6. Mark done in your session notes; proceed to the next PWO.

The legacy `WO-00…17` table above is Goal/Accept/Proof reference shape only — its Proof commands assume code at repo root that does not exist yet under greenfield; don't run them.

## Baseline (honest — greenfield)

There is **no product code at repo root today**. `archive/pre-rebirth-2026-07-23/` holds a prior implementation (`app.py` curses router, `screens.py`, `adapters.py`) kept strictly as reference — it is never restored or imported. The greenfield rebuild starts from PWO-003 in the inventory; early PWOs are mostly **bootstrap + verify**, matching the legacy WOs' shape without their stale paths.

## Canon refs (read before Build WOs)

- `canon/architecture/north-star.md` — human sovereign · app taught-screen autopilot · AI teacher never live-drives
- `canon/surfaces/entry-and-profile-selection.md` — launcher + create flow
- `canon/surfaces/trainer-cockpit.md` — panel grid + game viewport
- `canon/surfaces/mode-line-and-teach-controls.md` — App/Human dual · M/A/R/T · no AI-drives mode
- `.samantha/plans/ui-polish-assessment.md` — color/glyph vocabulary (internal)
