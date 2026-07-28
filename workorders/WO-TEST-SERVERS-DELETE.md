# WO-TEST-SERVERS-DELETE — delete orphan `test_servers.py` (archive `twclient.servers`)

**ID:** WO-TEST-SERVERS-DELETE  
**Branch:** `wo/TEST-SERVERS-DELETE`  
**Seat:** Cursor (`impl-aiclient-cursor`)  
**Priority:** HIGH  
**Size:** XS (delete 1 file + 1 pytest.ini line)

---

## Goal

Delete `tests/test_servers.py` and remove its `--ignore` line from `pytest.ini`.

`test_servers.py` is a 97-line archive file that imports `twclient.servers` —
a module that no longer exists. It hard-fails at collection with
`ModuleNotFoundError: twclient`. It is classified **BANK-DELETE** in the
ignore-list audit (`workorders/AUDIT-TEST-IGNORE-LIST-LANDMINE.md`).

The reborn server-catalog API lives at
`tw2002_aiclient.session.credentials.list_servers()` and is already exercised
by `test_credentials.py`, `test_profile_resolver.py`, and
`test_create_form_error_path.py`. No new tests are needed.

---

## Scope

| Action | Path |
|---|---|
| **DELETE** | `tests/test_servers.py` |
| **EDIT** | `pytest.ini` — remove `--ignore=tests/test_servers.py` line |

Owned paths: `tests/test_servers.py` · `pytest.ini`

Out of bounds: everything else.

---

## Constraints

- Do **NOT** write any replacement test. The reborn coverage is sufficient.
- Do **NOT** touch any other `--ignore` line.
- Do **NOT** use `git add -A`. Commit explicit paths only:
  `git commit -- tests/test_servers.py pytest.ini`
- `tests/test_servers.py` has no other references in `tests/` — verify with
  `grep -r test_servers tests/` before deleting.

---

## Acceptance criteria

1. `tests/test_servers.py` is absent from the repo.
2. `pytest.ini` no longer contains `--ignore=tests/test_servers.py`.
3. `pytest.ini` still contains every other `--ignore` line unchanged.
4. Suite passes: `.venv/bin/python -m pytest -n auto -q` — no collection errors,
   no new test failures.

---

## Proof

Run:
```
.venv/bin/python -m pytest -n auto -q
```

Report: exit code, total collected, pass/fail counts.
Also confirm: `grep test_servers pytest.ini` → no output.

---

## Refs

- `workorders/AUDIT-TEST-IGNORE-LIST-LANDMINE.md` — disposition: BANK-DELETE
- PR #154 (`WO-TEST-AICLIENT-ADAPTERS-REHAB`) — pattern to follow (delete stale archive test + remove ignore)
- `tw2002_aiclient/session/credentials.py` — `list_servers()` is the reborn API
- `tests/test_profile_resolver.py` — server catalog covered here (reborn)

---

## Status: DONE (hub-finish 2026-07-28)

**Hub finish:** Cursor seat CLAIMed but shell-blocked (bash ENOENT). Hub completed from `wo/TEST-SERVERS-DELETE` worktree.

- `tests/test_servers.py` deleted (97-line archive file, `twclient.servers` hard-fail).
- `pytest.ini` `--ignore=tests/test_servers.py` line removed.
- Suite passed: no collection errors, no new failures.
- Merged via PR #155.
