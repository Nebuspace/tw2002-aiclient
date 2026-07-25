# WO-AUDIT-ENTRY-APP-CHIP — entry chip APP (match daemon MODE_APP)

> Status: **EXECUTED / DONE** 2026-07-25 · product tip **`7c0e882`** (CC · rebased from `0537298` onto Cursor docs tip) · docs stamp Cursor  
> Refs: Max entry-chip ruling `@ 09:33:23Z` · Batch 2/3 `APP` chip · ADR-002 · CC `WO-ENTRY-APP-CHIP`

## Tip verdict
**DONE** on origin `7c0e882` — cockpit entry is App-hold (`spectating=False`, `attached=False`); chip shows **`APP`** matching daemon `MODE_APP`, not SPECTATE. Canary re-justified (one AST-node pin); colour fence uses `run_attr` spy (more precise than count-proxy); tripwire comment micro rides same tip. Sibling stale-M docstring stack on origin: `ca1e078` (first pass) → follow-on **`276327e`** (`control_seat` `:84` App-branch truth; tip advanced after STATUS-DONE).

## Ruling
Entry chip = **APP** (match daemon). Product = CC; this stamp is tip-honesty only.

## Proof
CC STATUS-DONE @ 11:16:26Z · product tip `7c0e882`; docs tip rebased atop follow-on `276327e` (origin tip at stamp time). Push waits Accept (product already SHIPped).
