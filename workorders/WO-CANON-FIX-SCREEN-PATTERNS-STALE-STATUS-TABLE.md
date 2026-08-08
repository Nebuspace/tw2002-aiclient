Goal:        Update `canon/research/tw2002-screen-patterns.md`'s "Status vs tree"
             table to code-truth: P-SETTLE-LINE and P-QTY/StarDock rows currently
             read unresolved but both shipped; only Planet/Citadel/Tavern gates
             remain genuinely absent.
Scope:       canon/research/tw2002-screen-patterns.md — docs-only, the status
             table rows named above.
Constraints: Touch only the stale rows; do not re-state anything beyond what the
             cited code proves. Planet/Citadel/Tavern rows stay marked absent.
             No product-code changes.
Accept:      P-SETTLE-LINE row reflects MATCH_SCOPE_PROMPT_LINE wired + tested
             (settle.py:230, 318-322); P-QTY/StarDock row reflects
             stardock_cargo_hold_quote / stardock_shipyard_listing screen
             classes wired + tested (classify.py:151-152); Planet/Citadel/Tavern
             rows unchanged (still absent). No other table rows altered.
Proof:       Docs-only diff; suite green. live-prove: n/a (docs).
Refs:        tw2002_aiclient/session/settle.py:230,318-322 ·
             tw2002_aiclient/session/classify.py:151-152 ·
             queue-aiclient.md Cycle-47 row (verified-against 2026-08-08).
