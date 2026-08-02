# WO-CONN-HEARTBEAT-GLYPH

**Status:** DONE · origin `13a6ecf` (#300) · tip-honesty stamp 2026-08-02 (product on main; banner was stale READY)
**Seat:** `impl-aiclient-cursor`
**Branch:** `wo/CONN-HEARTBEAT-GLYPH`
**Depends:** `main` ≥ `efeb7e7`

## Why

Local/full-suite noise: `test_connected_conn_rides_the_top_strip_only` flakes when top CONN slow-flash `●` collides with bottom-right liveness heartbeat `●` (seat ignored this as “pre-existing” on #298/#299). Also bank `test_cockpit_focus_pty` narrow-tier `wait_frame` stall if the same tip-check shows it still red — fix or honest skip with reason, do not ignore silently.

## Goal

CONN top light and liveness heartbeat are visually/assertably distinct; conn pty pin stable green without ignore.

## Scope

1. Diagnose why the conn pty pin confuses CONN `●` with heartbeat `●` (assert too loose? same glyph both places?).
2. Fix product and/or pin so Connected CONN is proven on the **top strip only**, without matching bottom liveness.
3. Prefer distinct glyphs or scoped region asserts (e.g. only `regions["strip"]` rows) over renaming operator-facing CONN away from Max’s green `●` ruling unless necessary — if both must stay `●`, assert by **geometry** (top vs bottom-right).
4. Tip-check focus pty narrow-tier failure; fix if same root class, else file follow-on one-liner in STATUS Concerns.
5. This WO on the branch.

## Out of scope

#283 · teachband · trade auto-fire · explore-default (superseded by #297).

## Accept

1. `test_connected_conn_rides_the_top_strip_only` green `-n0` and under suite (no ignore).
2. Top CONN still green slow-flash when connected (Max ruling intact).
3. Focused + full suite green.

## Proof

pytest conn pty + suite; live-prove `n/a` (chrome/assert). No self-merge.

## Refs

`tests/test_cockpit_conn_pty.py` · `screens.py` `_CONN_GLYPH_*` · `cockpit/liveness.py` heartbeat glyphs
