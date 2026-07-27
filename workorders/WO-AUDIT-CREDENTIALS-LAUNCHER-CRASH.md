# WO-AUDIT-CREDENTIALS-LAUNCHER-CRASH — the launcher's first read stops crashing, and stops lying

> Status: **DONE** · origin `3c17479` (was IN FLIGHT 2026-07-25 · Max-gated lane (secrets), scoped authorization granted for error handling only · isolated worktree)
> Type: harden · Priority: P0 (launcher is dead at startup for four real conditions) · Lens: L2 code-vs-canon / honesty
> Refs: `tw2002_aiclient/session/credentials.py` (`list_profile_summaries`, `list_servers`, `resolve_profile_host_port`) · `tw2002_aiclient/app.py:41` `_load_profiles` (call site — NOT edited) · `canon/doctrine/secrets-and-credentials.md` · precedent `WO-AUDIT-PLAYER-BANK-STORE-HONESTY` (`a9868ac`) · content boundary `WO-AUDIT-F5-TYPE-NAME` (`6661f13`)

## Goal

`app._run` builds its first screen from `credentials.list_profile_summaries()`, unguarded, before
the operator can press a key. That call had two failure modes, both measured by execution against
real files rather than a mocked `open`:

**It raised — the launcher is dead at startup, before anything is drawn:**

| condition | pre-fix |
|---|---|
| `profiles.toml` chmod 000 | `PermissionError` |
| a directory standing at `profiles.toml`'s path | `IsADirectoryError` |
| a `profiles.toml` symlink loop | *(collapsed to `[]`, see below)* |
| corrupt TOML | `TOMLDecodeError` |
| non-UTF-8 bytes | `UnicodeDecodeError` |
| `servers.toml` chmod 000 / corrupt / non-UTF-8 / a directory | same four, read FIRST via `_catalog()` |
| `servers = 5` in `servers.toml` | `AttributeError` — `.items()` on an `int` |

**It lied — the collapse:** an unreadable *config directory* returned `[]`, which the launcher
draws as an empty picker with a lone "Create New Player": *"you have no characters"*, said about a
directory nobody could open. `Path.exists()` answers `False` for a file under a directory it cannot
traverse, so the collapse happened at the first line, before any handler could run. A symlink loop
collapsed the same way, and for the same reason.

A third, quieter dishonesty on the resolver: `resolve_profile_host_port` answered
`ProfileNotFound: <path> does not exist` for a `profiles.toml` under an unreadable directory — a
typed lie, since `env.py` classifies `ProfileNotFound` as *absent, fall through quietly*, sending
the operator to create a profile they already have.

## Scope

- `tw2002_aiclient/session/credentials.py` — one shared store reader; two new members of the
  existing `ProfileConnectionError` family; the display/strict split.
- `tw2002_aiclient/session/player_bank.py` — reads the strict half, so the bank surface inherits
  the honesty instead of regressing into it (see Constraints).
- `tests/test_credentials_store_honesty.py` (new) — every condition driven for real.
- `tests/test_player_bank.py`, `tests/test_bank_unreadable_pty.py` — monkeypatch repointed to the
  strict half; without this their isolation is fictional and they pass or fail depending on whether
  the machine happens to have a `config/profiles.toml`.

**Not in scope, deliberately** — `app.py` (live lane in another seat; the fix belongs in
`credentials.py` so every caller inherits it), peer-credential checking, run-dir mode `0o700`,
resolver precedence, and `get_password()` / `secrets.json` (a design fork — see Findings).

## Constraints

- Secrets lane. No password logging, no argv echo, no widening of resolver precedence. This changes
  error handling, not what resolves.
- **No error message may carry file content.** `tomllib` lifts keys straight out of the document
  into its message (`Cannot declare ('alpha',) twice`), and both decoders keep the entire
  failed-to-parse file on the exception (`TOMLDecodeError.doc`, `UnicodeDecodeError.object`). The
  pre-fix resolver interpolated `str(e)` of a `TOMLDecodeError` verbatim. Replacement: a type name
  plus integer coordinates, per `WO-AUDIT-F5-TYPE-NAME`.
- Extend the existing typed family (`ProfileConnectionError` / `ProfileNotFound` /
  `ProfileIncomplete` / `ProfileMalformed`); do not start a parallel one. Callers classify by TYPE,
  never by message text.
- The fix must not trade the launcher's lie for another surface's. `player_bank.list_players`
  filters out rows carrying an error, so a diagnostic row handed to it would be dropped and the
  bank view would paint "(bank empty)" — the same lie, one file over.
- Isolated worktree; no `git stash`; no commits or pushes from the lane.

## Accept

1. An unreadable `profiles.toml` produces no uncaught raise through launcher startup.
2. Corrupt TOML: same.
3. An unreadable config directory produces an honest result — never a silent false "no profiles".
4. The happy path is unchanged, and proven unchanged.
5. Suite green, with a proof of pre-fix crash → post-fix survival.

## Proof

- **Red-first by execution.** Real `chmod 000` on the file and on the directory, a real symlink
  loop, real corrupt bytes, real non-UTF-8 bytes — then revert-prove-restore against the pre-fix
  blobs, with an md5 confirming the restore is byte-identical.
- **Two-sided.** Every failure test is paired with a control that must keep answering `[]`: a file
  never written, an absent config dir, an empty file, a dangling symlink, a search-only (`0o111`)
  directory. A handler that shouts at everything has only moved the collapse.
- **Layer B at the operator's screen** — real curses in a real pty driving `app._run`, replayed
  through pyte: the unreachable-config-dir screen must GAIN a fault row, and the corrupt-TOML
  screen must exist at all (pre-fix it was a blank grid — the launcher died before its first draw).
- **Content boundary pinned** — a canary key and a canary value in the failing document, asserted
  absent from both the rendered row and the exception text.

## Refs

`credentials.py` `_load_toml_store` / `ProfileStoreUnreadable` / `ProfileStoreMalformed` ·
`player_bank.py` `list_players` · `a9868ac` (bank precedent: cause vocabulary, the `Path.exists()`
trap, file-vs-directory denial) · `6661f13` (decoder `doc`/`object` boundary, type-name rendering)
