# WO-PASSWORD-MINT-CANON

**Status:** OPEN  
**Posted:** 2026-07-27T05:19:10Z · Max GO ("don't wait — prove it all")  
**Seat:** `impl-aiclient-cursor`  
**Depends:** main tip ≥ `bd9ea1a`  
**Safety:** Max explicitly authorized login/credential mint work this turn.

## Goal

Make password minting **one canonical function**, TW-safe by construction (≤8 alnum), and close the stale `twclient` credentials test import so mint length cannot regress unseen.

## Context (proven tonight)

- Live sacrificial `Proof79ba3d58` stored a **24-char** urlsafe password in `/tmp/play-ladder-newchar-*/secrets.json` — **not** what `login._fresh_password()` mints (8 alnum). Likely hand-seeded during prove setup.
- Product path already has `_fresh_password(length=8)` in `login.py`.
- Canon cites `credentials.generate_password()`; `tests/test_credentials.py` still imports `twclient` and calls missing `credentials.generate_password` — collection ERROR (suite blind).

## Scope

- `tw2002_aiclient/session/credentials.py` — add `generate_password()` / `_GENERATED_PASSWORD_LEN=8` (alnum CSPRNG; no `token_urlsafe`)
- `tw2002_aiclient/session/login.py` — `_fresh_password` delegates to `credentials.generate_password` (single mint)
- `tests/test_credentials.py` — import `tw2002_aiclient.session.credentials`; keep short-alnum pin
- Optional thin pin: login NEW mint uses ≤8 alnum (mock save_password capture)

## Constraints

- Do not change redaction / `secret=True` / env-first resolution semantics.
- Do not widen password length above 8 without a new Max GO.
- No live server work on this seat (CC owns live).

## Accept

1. `credentials.generate_password()` returns len==8, `.isalnum()`, varies across draws.
2. `login._fresh_password()` identical contract (delegates).
3. `pytest tests/test_credentials.py -q` collects and the generate pin is green.
4. PR + STATUS.

## Proof

pytest as above; no live TWGS required.
