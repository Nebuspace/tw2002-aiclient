# tw2002-aiclient — Project Context

**Samantha's persona lives in the output-style** (`.claude/output-styles/samantha.md`), auto-loaded via `.claude/settings.json` (`outputStyle: Samantha`). This file is project context.

---

## This Repo

**tw2002-aiclient** — a **human-piloted trainer** for TradeWars 2002. The operator flies; the app carries only screens it has been *taught* (deterministic autopilot / macros); a retrospective AI teacher may propose draft rules when invited. The AI **never live-drives**.

This repo is in **rebirth** (2026-07-23): live tree is `canon/` (prescriptive OKF) + `workorders/` (master list `workorders/ULTRACODE-WO-INVENTORY.md`; Phase 0–2 materialized as `WO-P0/P1/P2-*.md`; `WO-00…WO-17` are LEGACY-SURFACE). Prior product code + old docs live under `archive/pre-rebirth-2026-07-23/` for reference/porting only. **DOCS WIN:** where archived code contradicts reborn canon, canon wins.

An instance rooted **here** is an **IMPLEMENTER** seat in the Nebuspace dual — live identity is set by `SAMANTHA_IDENTITY` / the seat's presence file in the coord-dir. Current roster: **`impl-aiclient-cursor`** (Cursor · volume) and **`impl-claudecode-aiclient`** (Claude Code · premium) (registered in `Claude_Samantha/.samantha/DEPLOYMENTS.md`). The **ORCHESTRATOR** runs from `"$(git rev-parse --show-toplevel)"/../`. Claude Code/Cursor auto-loads ancestor `CLAUDE.md` files, so the parent Nebuspace coordination spec is in context — but **this file's seat definition is authoritative for cwd = here**.

---

## Doc canon (read in this order)

1. **`canon/architecture/north-star.md`** — vision & win condition (human sovereign · app taught-screen autopilot · AI teacher never live-drives).
2. **`canon/index.md`** — the OKF bundle's entry point and full concept index. The bundle is the sole docs root (no second docs tree) and spans `canon/architecture/`, `canon/engine/`, `canon/surfaces/`, `canon/doctrine/`, `canon/strategy/`, plus `canon/ADR/` (decision records), `canon/DECISIONS.md` (open-questions workspace), and `canon/log.md`.
3. Surface / engine / strategy concepts under `canon/surfaces/`, `canon/architecture/`, `canon/engine/`, `canon/doctrine/`, `canon/strategy/` as the WO scopes them.
4. **`workorders/README.md`** — ordered product rebuild queue; each WO has Goal · Scope · Depends-on · Accept · Proof.
5. **`archive/pre-rebirth-2026-07-23/`** — reference only (old AI-first framing in places). Port behavior only when a WO scopes it and canon defines the target contract.

---

## How work proceeds

Build **only** through the ordered queue in `workorders/` — see `workorders/ULTRACODE-WO-INVENTORY.md` for the master list; start at the first unproven `WO-P0/P1/P2-*` item on a cold seat. Daemon-side safety items (TW-01…TW-30) stay in the parent Nebuspace `QUEUE.md`, not here.

Phase 0 already shipped greenfield package stubs at repo root (`tw2002_aiclient/` + `twclient/`) — this is **greenfield-from-`canon/`, not a restore of archived code**. Per [ADR-001](canon/ADR/001-one-tree-embedded-session.md) (**Accepted** 2026-07-24), the two sibling top-level packages are being consolidated into one `tw2002_aiclient` import tree with the daemon-core relocated under `tw2002_aiclient/session/`; until the follow-on relocation WO lands, `twclient/*` stays where it is and new daemon-core work continues to target it.

---

## Setup & commands (as of rebirth)

Greenfield package stubs exist at repo root today (`tw2002_aiclient/` product TUI, `twclient/` daemon-core — see the consolidation note above); `./tw`, `./twd`, `./tw2002-aiclient` launcher scripts and console-script wiring have not landed yet (no `[project.scripts]` in `pyproject.toml`). What runs today:

```bash
cd "$(git rev-parse --show-toplevel)"
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/python -m tw2002_aiclient   # placeholder TUI entry — TTY-gated, per WO-P0-003
```

- **Lint:** none configured — don't invent one.
- **Tests:** when `tests/` returns to root, prefer `.venv/bin/python -m pytest tests/` (network-free). Don't invent a lint gate.
- Never run `tw start`/`tw stop` against a session someone else may be driving without checking `tw status` first.

---

## Hard rules

- **Secrets never touch logs, argv, shell history, or the repo.** See `canon/doctrine/secrets-and-credentials.md`. `config/secrets.json` is chmod-600 + gitignored; `TW2002_PASSWORD_<PROFILE>` env-first. Every password send routes through the redaction sink. Public repo: no real personal names, handles, FQDNs, or usernames in committed artifacts.
- **AI never live-drives.** Live senders are `{app, human}` only. Spectate is read-only. At escalation the human responds by hand, Records a macro, or Analyzes with the AI teacher — every rule is human-approved before it can fire.
- **Single-connection, single-session daemon** (once the daemon module lands): one telnet socket; control-lock governs who may drive. Don't bypass it.
- **`.claude/` and `.samantha/` are gitignored** (hub ruling) — framework install is local orchestration, not shippable client. Same for private journals (`DESIGN-v2.md`, `QUEUE.md`, etc. if reintroduced).
- **Path-leak gate (both seats).** Do not commit operator-home absolute paths (`/Users/<username>/` or `/home/<username>/`). Claude Code enforces via PreToolUse; Cursor enforces `.cursor/hooks.json` → `.cursor/hooks/path-leak-gate.sh` with **`failClosed: true`** (deny if the hook crashes/missing) plus a tracked git hook at `scripts/githooks/pre-commit` (enable once: `git config core.hooksPath scripts/githooks`). Scanner: `scripts/path-leak-scan.sh`. Dry-run: stage a file containing `/Users/…` and confirm the scanner exits 1.

---

## Two-Instance Coordination (Implementer view)

Full protocol = parent **`Nebuspace/CLAUDE.md`** + `.samantha/references/coordination-protocol/README.md` (M9 STAR).

- **Identity:** set by `SAMANTHA_IDENTITY` / the seat's presence file in the coord-dir. Current roster: `impl-aiclient-cursor` (Cursor · volume) and `impl-claudecode-aiclient` (Claude Code · premium).
- **Outbox / presence:** `"$(git rev-parse --show-toplevel)"/../.samantha/coord/<identity>.md` — your own seat's file only (e.g. `impl-aiclient-cursor.md` or `impl-claudecode-aiclient.md`).
- **Watch only:** `orchestrator.md`
- **Arm each session:** parent `coord-monitor.sh` + `heartbeat.sh` for this identity; confirm `coord-status.sh` → BOTH ALIVE.
- **Cursor arming:** Shell `block_until_ms: 0`, `required_permissions: ["all"]`, and `notify_on_output` (deaf gap otherwise).
- Commit only explicit paths; never `git add -A` / `git add .` in a shared tree. Never write secrets to the coord-dir.
