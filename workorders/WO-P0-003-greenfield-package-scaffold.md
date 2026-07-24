# WO-P0-003 — Greenfield package scaffold

> Status: PLANNED (greenfield · HOLD-GATES-PENDING blocks execution until a lifting HANDOFF)
**Phase:** 0 · **Type:** bootstrap · **Depends:** —
**Canon:** `canon/architecture/session-engine.md`

**Goal:** Stand up empty `tw2002_aiclient` (product TUI) and `tw2002_aiclient.session` (daemon-core) package stubs
at repo root, mirroring the two-process split session-engine specifies, with a TTY gate on the
product entry point.

**Scope:** Repo-root package layout only — `tw2002_aiclient/__init__.py`, `tw2002_aiclient/__main__.py`,
`tw2002_aiclient/session/__init__.py`, `pyproject.toml` or `setup.cfg` (packaging metadata), `requirements.txt`
(pyte dependency). No behavior beyond import + TTY gate; no daemon, no CLI verbs, no curses screens.

**Accept:**
- `tw2002_aiclient/` and `tw2002_aiclient/session/` both import cleanly from repo root (`python -c "import
  tw2002_aiclient, tw2002_aiclient.session"` exits 0).
- `python -m tw2002_aiclient` run against a non-TTY stdin/stdout (e.g. piped) exits **2** and prints
  a one-line "requires a real terminal" message — never a traceback.
- `python -m tw2002_aiclient` run against a real TTY reaches a placeholder entry point without
  raising (further behavior is out of scope — later WOs build the launcher itself).
- No `archive/` import path is referenced anywhere in the new scaffold.

**Proof:**
```bash
cd "$(git rev-parse --show-toplevel)"
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -c "import tw2002_aiclient, tw2002_aiclient.session; print('ok')"
echo | .venv/bin/python -m tw2002_aiclient; echo "exit=$?"   # expect exit=2, no traceback
```
