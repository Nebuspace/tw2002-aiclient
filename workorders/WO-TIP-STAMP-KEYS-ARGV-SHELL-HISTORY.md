# WO-TIP-STAMP-KEYS-ARGV-SHELL-HISTORY

**Status:** DONE (pending merge)
**Priority:** LOW
**Gated:** no

## Goal

Close KEYS-ARGV-SHELL-HISTORY: doctrine already warned; land ASCII-safe
`tw attach --keys` argparse help + README caveat, then stamp findings DONE.

## Scope

- `tw2002_aiclient/session/cli.py` — `--keys` help (pure ASCII)
- `README.md` — credentials caveat for `--keys`
- `canon/doctrine/secrets-and-credentials.md` — note product help landed
- `canon/findings.md` KEYS-ARGV row → DONE
- `workorders/AUDIT-OKF-6LENS-BACKLOG.md` — banked-session note
- This WO file

## Accept

1. `tw attach --help` shows `NEVER a password - lands in argv/history` (ASCII only).
2. README + doctrine agree `--keys` is not a credential channel.
3. live-prove: `n/a` (help/docs; no live session delta).

## Proof

`./tw attach --help` contains the NEVER-password line; STATUS SHA.
