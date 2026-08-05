# WO-BUILD-SERVERS-PROBE-CLI-VERBS

## Goal
Wire `tw servers list` → `summarize_inventory` and `tw probe` → catalog TCP probe
(same engine as `scripts/catalog-tcp-probe.py`).

## Scope
- `tw2002_aiclient/catalog_cli.py` (new)
- `tw2002_aiclient/session/cli.py` (parser registration only)
- `scripts/catalog-tcp-probe.py` (thin wrapper; shared engine)
- `canon/architecture/cli-verbs.md` (catalog + HOLD honesty)
- tests + this WO

## Accept
1. `tw servers list [--json]` prints inventory provenance/liveness summary.
2. `tw probe [--limit N]` writes liveness sidecar; shares code with the script.
3. Shipped-verb allowlist includes `servers` + `probe`.
4. cli-verbs HOLD list no longer claims servers/probe unshipped.

## Proof
- pytest `tests/test_cli_servers_probe.py` `tests/test_cli_log.py`
- live: `tw probe --limit 5` (TCP-only; no login)

## Out of scope
IAC/L0 banner classify · `tw players` · SessionGuardian escalate
