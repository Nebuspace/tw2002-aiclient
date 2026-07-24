---
type: ADR
title: ADR 001 — One Package Tree, Embedded Session Engine
description: Collapses the Phase-0 two-top-level-package scaffold into a single tw2002_aiclient import tree with the daemon-core relocated under session/, plus app-owned daemon lifecycle and an exit-time stop-the-daemon-too confirm popup.
tags: [adr, packaging, session-engine, lifecycle]
timestamp: 2026-07-24T00:08:22Z
---

# ADR 001 — One Package Tree, Embedded Session Engine

Filename convention: `/ADR/001-one-tree-embedded-session.md`

---

## Status

Accepted · Accepted 2026-07-24 by Max

---

## Context

Greenfield packaging for the rebirth started from WO-P0-003 (`workorders/WO-P0-003-greenfield-package-scaffold.md`),
which stood up **two sibling top-level packages** at the repo root: `tw2002_aiclient/` (the product
TUI) and `twclient/` (the daemon-core: `daemon.py`, `cli.py`, `session.py`, `credentials.py`, and
the rest of the session-engine module set cataloged in the project `CLAUDE.md`'s Architecture map).
The scaffold's own goal line described this as "mirroring the two-process split session-engine
specifies" — i.e. it read the **process split** (`twd` persistent daemon + `tw` one-shot CLI) as
requiring a **package split**, and stood up two top-level importable packages to match.

Max caught this gap in review: a two-process runtime does not require a two-package import tree.
`canon/architecture/session-engine.md`'s "Two-Process Split" section is entirely about *processes*
sharing one connection over a unix-socket protocol — it says nothing about where their source lives
in the repo. For a greenfield project with no existing external importers of `twclient` as a
standalone package, two sibling top-level packages is unwarranted surface area: two `__init__.py`
roots, two entries in `pyproject.toml`'s `packages.find`, and an implicit invitation for import paths
to fork (`from twclient import X` next to `from tw2002_aiclient import Y`) with no single place a
newcomer reads to find "the codebase."

This is a canon **Change** per the ADR-process taxonomy (`.samantha/references/adr-process/README.md`):
canon itself was not wrong about the process split, but the scaffold that stood up from it drew the
wrong packaging inference, and nothing in canon explicitly said "one tree" to block that inference.
This ADR closes that gap going forward and records the correction as a canon-directed decision
rather than a silent code fix.

Affected: every future WO that imports from `twclient.*` (daemon-core lane) or that would otherwise
import from a second top-level package; the `pyproject.toml` console-script wiring; and the
session-engine canon page, which needs a packaging-shape section it does not currently have.

---

## Decision

The project uses **one top-level importable package, `tw2002_aiclient/`**. There is no second
top-level package. The daemon (`twd`), the one-shot CLI (`tw`), transport, credentials, and the
rest of the current `twclient/` module set live under `tw2002_aiclient/session/` (former `twclient/*`
becomes `tw2002_aiclient/session/*`); the product TUI app and its screens live under
`tw2002_aiclient/` directly (`app.py`, `screens/`, etc.), with `__init__.py`/`__main__.py` as the
`python -m tw2002_aiclient` TUI entry point. Console scripts `tw` and `twd` point **into**
`tw2002_aiclient.session.*` — never into a second top-level package. This is packaging only: it does
**not** change the process model — the daemon (`twd`) and the one-shot CLI (`tw`) remain 2–3
separate OS processes per session-engine's "Two-Process Split," and that section of canon is
unchanged by this decision; embedding into one import tree is not the same as collapsing to one
process. Additionally, the aiclient app (the process the player runs) **owns the daemon's lifecycle
at the UX level**: it may start/ensure the daemon on entry, and on the player's exit from the
aiclient app it presents a confirm popup — "Stop the daemon too? (Yes / No)" — before the app itself
exits, rather than silently leaving the daemon's fate unstated.

---

## Consequences

**Positive:** one import root to read, one `pyproject.toml` `packages.find` entry, no forked
`from twclient import X` / `from tw2002_aiclient import Y` convention to keep straight, and a
packaging shape that matches the "single product" mental model a human piloting one app expects.
The exit-confirm popup makes the daemon's continuity an explicit, visible choice at the one moment
it matters (quitting the app) instead of an implicit side effect the player has to already know
about.

**Trade-offs accepted:** every module formerly under the Phase-0 `twclient/` sibling had to be
relocated and every import path updated — nontrivial mechanical churn that was **executed** after
Accept (WO-P0-RELOCATE-SESSION and follow-ons). **Tip reality (as of `8f03289` / Phase 0–3 CLOSED):**
there is exactly one top-level importable package (`tw2002_aiclient*`); daemon/CLI live under
`tw2002_aiclient/session/`; no sibling `twclient/` package remains on tip. This ADR's Status is
**Accepted**; the Consequences below that still speak of "until that WO lands" / "scaffold on disk"
are **historical** — the relocate is done.

**New constraint introduced:** no future WO may add a second top-level importable package without a
new ADR superseding this one. Console-script entry points must resolve into
`tw2002_aiclient.session.*`, never a sibling root.

**Follow-on work (historical checklist — relocate DONE on tip):**

The itemized relocate list that follows was the Accept-gated debt; it is retained as the record of
what was moved, not as open work:

1. **Relocate `twclient/` → `tw2002_aiclient/session/`.** Physically move every module currently
   under `twclient/` (`daemon.py`, `cli.py`, `connection.py`, `iac.py`, `session.py`, `terminal.py`,
   `settle.py`, `classify.py`, `state_parser.py`, `protocol.py`, `control_lock.py`, `credentials.py`,
   `login.py`, `guardian.py`, `haggle.py`, `ledger.py`, `skills.py`, `miner.py`, `loop_player.py`,
   `watch.py`, `spectate_app.py`, `spectate_layout.py`, `interactive_app.py`, `logging_util.py`,
   `env.py`, `world_identity.py`, `player_bank.py`, and any other current `twclient/*` module — per
   the project `CLAUDE.md` Architecture map and current repo contents) into
   `tw2002_aiclient/session/`.
2. **Update every internal import** referencing `twclient.*` to `tw2002_aiclient.session.*` across
   the codebase (product app, tests, and any cross-referencing module).
3. **Update `pyproject.toml`**: collapse `packages.find` `include` to `tw2002_aiclient*` only (drop
   `twclient*`); add/repoint the `tw` and `twd` console-script entry points at
   `tw2002_aiclient.session.cli:main` / `tw2002_aiclient.session.daemon:main` (exact entry-point
   names to be confirmed against the actual `main()`/`cmd_*` dispatch shape at relocation time).
4. **Update WO-P0 / WO-P1 Proof paths.** Every workorder whose Proof section shells out against
   `twclient` module paths must be repointed at `tw2002_aiclient.session.*` — at minimum
   `WO-P0-003-greenfield-package-scaffold.md`, `WO-P0-004-dev-seat-smoke.md`,
   `WO-P0-005-config-and-secrets-layout.md`, `WO-04-ensure-daemon-wire.md`,
   `WO-07-intervention-banner.md`, `WO-09-world-identity-strip.md`,
   `WO-11-game-viewport-center.md`, `WO-12-logs-panel.md`, `WO-P1-012-create-profile-form.md`,
   `WO-P1-015-player-bank-touchpoint.md`, and the WO-P2 daemon-core batch
   (`WO-P2-020` through `WO-P2-028`) — re-grep at relocation time for any that have landed or been
   added meanwhile.
5. **Update the session-engine module Citations.** `canon/architecture/session-engine.md`'s
   Citations section ([3]–[7]) currently cites `twclient/daemon.py`, `twclient/connection.py`,
   `twclient/iac.py`, `twclient/terminal.py`, `twclient/control_lock.py`, `twclient/session.py`,
   `twclient/protocol.py`, `twclient/env.py` — these must be repointed to their
   `tw2002_aiclient/session/*` paths once the relocate lands (not touched by this ADR; this ADR adds
   a new section instead of mass-rewriting Citations, per its own scope).
6. **`archive/` references are explicitly out of scope** — historical citations to `twclient/` under
   `archive/` describe a past state and are never rewritten by the relocate WO.

None of the above may be executed before this ADR's Status moves to **Accepted** by Max — until
then it is deferred code-debt, listed here so it is not lost, not started.
