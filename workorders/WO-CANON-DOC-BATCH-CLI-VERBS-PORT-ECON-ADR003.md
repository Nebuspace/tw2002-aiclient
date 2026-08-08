# WO-CANON-DOC-BATCH-CLI-VERBS-PORT-ECON-ADR003

Batch of 3 small, independent doc-accuracy fixes.

**Goal:**
1. **cli-verbs.md** — the "Read-only-safe at any time" runnable-verb list
   included `state` and `spectate` as if they were real `tw` subcommands.
   Neither is (grep-confirmed zero matches in `session/cli.py`'s
   `build_parser`). Both already had accurate caveats elsewhere in the same
   file's tables (`state`: WIRE-ONLY, no `tw state` subparser; `spectate`:
   RETIRED/WONTBUILD as a `tw` verb, lives in-cockpit instead) — only the
   summary list at the top hadn't been reconciled.
2. **port-economics.md** — the Code-divergence section still said
   floor/regrowth/plague numbers have "no code backing yet," stale as of
   this session's `port_floor_capture.py` (PR #530) + `tw port-floor` CLI
   verb (PR #533). Documented the module's actual shape and the CLI surface
   while explicitly preserving the still-true point that nothing is
   live-verified.
3. **ADR-003** — the "Still design-intent / process" list's 2 sub-items
   (sacrificial live-prove gate, bounded-repeat contract) had no cited
   follow-up ticket. Both are named as residuals in
   `WO-CANON-ROLLUP-ADR-003-DISTRIBUTED-FOLD-TAG.md`'s Accept #2 — added
   one-line pointers to that WO for both, noting no separate dedicated WO
   exists yet for either.

**Scope:**
- `canon/architecture/cli-verbs.md`
- `canon/strategy/port-economics.md`
- `canon/ADR/003-discovered-chain-approve-scaffold.md`
- this WO file

**Out of scope:** no code changed; no new WOs filed for the untracked
bounded-repeat sub-item (flagged in the doc, not auto-created).

**Constraints:** every claim verify-first — grepped `session/cli.py` for
verb registration, read `port_floor_capture.py`/`port_floor_cli.py` in
full, grepped `workorders/` for existing ADR-003 sub-item tracking before
writing any pointer.

**Accept:**
1. cli-verbs.md's runnable-verb list no longer claims `state`/`spectate`
   are `tw` subcommands; a short paragraph points to each's existing
   accurate table caveat.
2. port-economics.md documents `port_floor_capture.py`'s actual functions/
   output shape and the `tw port-floor` CLI verb, while preserving the
   "nothing live-verified yet" framing.
3. ADR-003's 2 residual sub-items each cite their tracking WO.
4. No code touched.

**Proof:** `.venv/bin/python -m pytest tests/test_port_floor_capture.py tests/test_cli_log.py -n0 -q` → 21 passed (docs-only change, suite unaffected — run for context confirmation only).
