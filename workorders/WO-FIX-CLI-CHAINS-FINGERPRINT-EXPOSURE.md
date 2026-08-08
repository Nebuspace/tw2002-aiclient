Goal:        `tw chains --json` must emit each chain's TradeChainPlan.fingerprint
             (the SHA-256 `tw chain start --fingerprint` requires), which today it
             never produces — forcing out-of-band derivation (live-witnessed friction).
Scope:       tw2002_aiclient/session/cli.py — cmd_chains JSON output path only.
             Compute each row's fingerprint via trade_chain_plan.plan_from_chain();
             emit null when plan_from_chain refuses (e.g. below the 2-hop floor).
Constraints: Additive to the JSON shape (existing sectors/hops/turns/cr_per_turn/
             cr_per_execution fields unchanged). No change to tw chain start. No
             new send path. Don't alter ranking or discovery.
Accept:      `tw chains --json` includes a `fingerprint` field per row matching what
             `tw chain start --fingerprint <fp>` accepts for that same chain; null
             for sub-floor chains; existing fields byte-identical; the --help claim
             ("exact chain fingerprint from tw chains") is now true.
Proof:       Unit test: a discovered chain's emitted fingerprint round-trips through
             tw chain start's fingerprint validation. Full suite green. live-prove: n/a.
Refs:        cli.py:977-1037,2149-2153 · trade_chain_plan.py:114-132 (plan_from_chain) ·
             workorders/WO-LIVE-WITNESS-FIRST-TRADE-LOOP.md:25 · catalog #31.
