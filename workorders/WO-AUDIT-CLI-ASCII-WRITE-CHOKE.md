# WO-AUDIT-CLI-ASCII-WRITE-CHOKE

**Status:** STAGED · product · waiting Max glyph ruling  
**Supersedes:** thin docs-only `WO-AUDIT-CLI-HELP-ASCII` / ASCII-HELP-BANK (hub `@ 15:52:50Z`)

## Goal

Shared CLI write-choke so `./tw` help / menumap / loops do not die mid-output on non-UTF-8 stdout.

## Context

- Attach banner path fixed in `fec3ffe` (ASCII-only ATTACHED strings).
- Residual: argparse `help=` / verb output still carry ★ / em-dash / … → `UnicodeEncodeError` under ascii/latin-1.
- Accurate reachable set: `PYTHONIOENCODING=ascii|latin-1` · `LC_ALL=en_US.ISO8859-1` · `LC_ALL=C` **with UTF-8 mode off**. Bare `LC_ALL=C` alone does **not** crash (PEP 540).

## Constraints

- **No `cli.py` edit until Max rules** fork: (A) refuse/exit ASCII-only error · (B) substitute NO-SWAP glyphs · (C) other.
- Do not claim a findings row or docs stub closes the product defect.
- Tests tracked as MISSING-TESTS **MT-05** / inventory pin **MT-06**.

## Accept (after ruling + product tip)

Under ruled policy, `PYTHONIOENCODING=ascii ./tw --help` and representative `menumap` / `loops` invocations neither traceback nor truncate mid-glyph incorrectly.

## Refs

- Hub DECISION-NEEDED `@ 2026-07-25T15:52:50Z`
- `canon/findings.md` · `CLI-ASCII-WRITE-CHOKE`
- `workorders/AUDIT-MISSING-TESTS.md` MT-05/06
