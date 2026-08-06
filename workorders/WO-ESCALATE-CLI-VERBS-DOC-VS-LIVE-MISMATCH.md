# WO-ESCALATE-CLI-VERBS-DOC-VS-LIVE-MISMATCH

**Status:** DONE (pending merge)
**Priority:** HIGH
**Gated:** no (Max Option B carte blanche 2026-08-05)

## Goal

Stop `canon/architecture/cli-verbs.md` from presenting `analyze` / `mine` /
`replay` / `play` / `autoloop` / `haggle` / `autopilot` / `crawl` (and peers)
as runnable `tw` subcommands when `session/cli.py` `build_parser()` does not
register them.

## Scope

- `canon/architecture/cli-verbs.md` — Option B honesty pass
- This WO file

## Accept

1. Catalog teach / App-drive HOLD rows marked TARGET (or WIRE-ONLY / RETIRED).
2. Examples no longer show `tw analyze` / `tw mine` / `tw spectate` as live.
3. Implementation status LIVE list matches `./tw --help` tip verbs (incl. report,
   chains, explore, reflex, rule, servers, probe).
4. live-prove: n/a (docs-only).

## Proof

```
./tw --help   # verb set cited in Implementation status
# no product code change
```
