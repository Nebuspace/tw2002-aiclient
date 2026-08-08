Goal:        Live-drive this client on a `crawl_sacrificial=true` profile and
             produce evidence-grade research findings across the autopilot's
             core value loops — Trade Loop Chains, automatic credit doubling,
             and purchase strategy (fighters, cargo holds, new ship) — to seed
             the next work-order tranche (human directive 2026-08-08: assemble
             30+ WOs from this research).
Scope:       canon/research/autopilot-live-drive-findings-2026-08-08.md (new,
             this branch) — findings document ONLY. No product-code changes in
             this WO; defects found become WO seeds, not drive-by fixes.
             Live keystrokes via the sender="dev" path
             (WO-BUILD-DEV-DRIVE-SENDER-ENFORCEMENT) and/or existing
             crawl/autopilot surfaces, on a `crawl_sacrificial=true` profile.
Research axes (each gets its own findings section):
             1. Trade Loop Chain lifecycle — discovery/scan, plan preview
                (trade_chain_plan → T-mode confirm), approved execution,
                bounded-repeat behavior, abort path (ADR-003 scaffold).
             2. Automatic credit doubling — record starting credits, drive
                toward 2x; log per-leg profit, stall points, and every manual
                intervention required; name precisely where the autopilot falls
                short of unattended doubling.
             3. Fighters purchase — venue screens (hardware emporium),
                classification coverage, taught-rule coverage, price/quantity
                handling.
             4. Cargo-holds purchase — same treatment
                (stardock_cargo_hold_quote path).
             5. New-ship purchase — shipyard listing coverage
                (stardock_shipyard_listing), trade-in handling, progression fit
                vs canon/strategy/ship-progression.md.
Constraints: Sacrificial profile only — the `is_crawl_sacrificial` gate stays
             the enforcement; real accounts never. Defensive/paladin conduct
             only (no PK). Findings doc is public-repo-safe: profile keys only,
             no server FQDNs, usernames, or personal names. Every finding
             carries evidence (transcript excerpt or file:line). An axis not
             exercised is written up as NOT-ATTEMPTED with the reason — never
             silently skipped.
Accept:      Findings doc lands with all 5 axes covered or explicitly
             NOT-ATTEMPTED; each finding tagged [WORKS] / [GAP] / [BREAKS] /
             [UX] / [NO-CANON]; the credit-doubling axis includes numeric
             before/after credits and a leg-by-leg account; the doc yields
             concrete WO-seed material (a "WO seeds" list at the end, one line
             each).
Proof:       The findings document itself, with transcript/ledger citations.
             STATUS summarizes per-axis outcomes. live-prove: this WO IS the
             live exercise.
Refs:        CLAUDE.md:63 (post-#545) · canon/doctrine/dev-drive-exception.md ·
             canon/ADR/003-discovered-chain-approve-scaffold.md ·
             canon/strategy/trade-loops.md · canon/strategy/ship-progression.md ·
             canon/strategy/port-economics.md.
