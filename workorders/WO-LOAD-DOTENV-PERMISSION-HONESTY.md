# WO-LOAD-DOTENV-PERMISSION-HONESTY

**Status:** DONE · origin `909ab01`  
**Posted:** 2026-07-26T00:55:00Z

## Goal

`load_dotenv`'s `exists()`-then-`read_text()` can leak a bare `PermissionError` into the same class of startup traceback that `c263f16` fixed for the profile store. Make unreadable dotenv fail **closed and honest** (no raw traceback as the operator UX), without inventing a silent "no env" lie if policy says loud-base.

## Scope

- Dotenv load path(s) used by daemon/CLI startup
- Tests with `chmod 000` **tempdir only** (never repo `config/` / live `run/`)

## Constraints

- **Secrets Max-gate** (`repr(UnicodeDecodeError)` / `get_password` decoder / stuck-login wire) is orthogonal — do not expand
- Tempdir-only mode flips; restore in `finally`
- Hands off Max live session / real profile store
- If behavior needs a Max ruling (silent vs loud), STATUS with ❓ DECISION-NEEDED — do not freestyle

## Accept

Unreadable dotenv → controlled error path (typed / message), no uncaught traceback on the happy operator path; pins green; suite otherwise green.

## Proof

STATUS + SHA · targeted pytest with temp chmod 000.

## Refs

CC Item disclosure post-`c263f16` · `WO-TWD-PROFILE-STORE-UNREADABLE.md` · secrets doctrine
