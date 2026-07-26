# WO-P0-TW-SHIM — Root `tw` / `twd` ADR-001 import fix

> Status: **DONE** · origin `38a6050` (hub Accept stamp 2026-07-26 · was EXECUTE DONE awaiting Accept)
> Seat: `impl-aiclient-cursor` · URGENT POC unblock
> Tip base: `3d7e32c`

## Goal

Root shims still imported retired `twclient` after ADR-001 one-tree relocate — unblock Max ops POC.

## Shipped

| Path | Change |
|------|--------|
| `tw` | `from tw2002_aiclient.session.cli import main` |
| `twd` | `from tw2002_aiclient.session.daemon import main` |

`tw2002-aiclient` product shim was already correct — untouched.

## Proof

```bash
./tw --help   # exit 0, ops verbs
.venv/bin/python -c 'from tw2002_aiclient.session.daemon import main'
rg -n 'from twclient|import twclient' tw twd   # expect 0
```
