# WO-P2-OPS-VERB-F-PREP — Spectate / attach inventory (no UI wire)

> Status: **DONE** · origin `9b66ec6` (hub Accept stamp 2026-07-26 · PREP docs tip; `b9dc80d` was watch wire not this PREP)
> Seat: `impl-aiclient-cursor`
> Parent: `WO-P2-OPS-VERB-SURFACE.md` slice F
> Refs: `canon/surfaces/spectate-and-attach.md` · WatchHub `1825758` · `tw watch` `b9dc80d`

## Goal

Honesty-gated execute plan for `tw spectate` / `tw attach`. **Do not wire UI
in this WO.**

## Tip vs archive (2026-07-24)

| Piece | Tip (`tw2002_aiclient.session`) | Archive (`twclient`) |
|-------|----------------------------------|----------------------|
| WatchHub / `subscribe` | **LIVE** (`watch.py` + daemon) | live |
| `tw watch` CLI | **LIVE** (E2) | live |
| Daemon `_handle_attach` | **LIVE** (thin keystroke lifetime + control_lock) | live (+ ledger redaction extras) |
| `tw attach` CLI / curses | **MISSING** — no `cli` verb; no `interactive_app.py` | `interactive_app.py` ~294 LOC · `cmd_attach` |
| `tw spectate` CLI / curses | **MISSING** — no modules | `spectate_app.py` ~2575 LOC · `spectate_layout.py` ~2967 LOC · `cmd_spectate` |
| Ignored banked tests | `tests/test_attach_*.py`, `test_spectate_*.py` still `--ignore` (import `twclient`) | greenfield rewrites owed per slice |

**Already on tip (do not re-port):** `ControlLock`, daemon attach protocol,
WatchHub. Product cockpit (`./tw2002-aiclient`) is a **different** surface —
Max pace-down holds Phase-3 chrome; this PREP is ops-only.

## Recommended execute slices

| Slice | Goal | Bound | Depends |
|-------|------|-------|---------|
| **F1** | Wire thin `tw attach` CLI over **existing** daemon `_handle_attach` (TTY check · open attach sock · forward keystrokes · release on exit). Prefer porting `interactive_app.py` (~294 LOC) or a thinner raw client if curses color is deferrable. Rehab `test_attach_protocol` (ignore → greenfield). | Medium · FakeDaemon attach tests already banked ignored | WatchHub optional (attach opens subscribe separately in archive) |
| **F1b** (optional) | Attach redaction / secret keystroke hardening from archive `test_attach_redaction` — only if F1 lands without it | Small | F1 |
| **F2a** | Port `spectate_layout.py` pure compose (no curses I/O) — largest LOC; can ship tests-first against FakeSession frames | Large (~3k LOC) · split further if >1.5k | WatchHub live |
| **F2b** | Port `spectate_app.py` + `tw spectate` CLI (`--snapshot` first for non-TTY, then interactive) | Large (~2.5k LOC) | F2a + WatchHub |
| **F3** | Un-ignore / rewrite remaining spectate suite; README Spectator section → shipped | Docs + rehab | F2b |

**Honesty bar:** keep `spectate` / `attach` off `./tw --help` until the matching
slice Accepts. Do not invent a fake one-shot spectate that is not a stream.

## Out of scope (this PREP)

Implementing any of F1–F3 · cockpit/chrome · `state_parser` · CC seat.

## Accept (this PREP)

STATUS cites gaps + recommended slices · README/WO honesty · no new verbs on help · SHA if docs commit.
