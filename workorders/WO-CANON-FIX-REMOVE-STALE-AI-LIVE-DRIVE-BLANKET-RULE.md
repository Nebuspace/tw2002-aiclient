Goal:        Remove the stale blanket "AI never live-drives" Hard Rule and replace with language
             matching the two authorizations that already exist but were never reflected in
             CLAUDE.md's Hard Rules section.
Scope:       CLAUDE.md:63 (Hard Rules section) — the AI-live-drive rule only.
             canon/doctrine/dev-drive-exception.md — "Manual, one action at a time" bullet,
             cross-referencing the separate already-authorized autopilot/chain path.
Out-of-scope: Real-account invariant, anti-PK, paladin-ethos language anywhere — unchanged.
             MODE_AI_PILOT / control_lock.py — stays retired, no code capability change.
             Any other doctrine file's `{app,human}` language.
Constraints: Documentation-only change reflecting existing rulings, not a new code capability.
Accept:      CLAUDE.md and dev-drive-exception.md read consistently with each other and with the
             DECISIONS.md/doctrine citations; no other doctrine file's `{app,human}` language
             touched.
Proof:       Diff review — confirm only the two named files/sections changed, scoped commit.
Refs:        canon/doctrine/dev-drive-exception.md, CLAUDE.md:63.

## Ruling

Max, direct instruction (2026-08-08): "update the CLAUDE.md so that the AI never drives rule is
removed.. its confusing.. we need to live drive to improve the client." Resolves the canon-conflict
escalation (blanket "AI never live-drives" vs the 2026-07-21 witness-carte-blanche +
2026-08-07 dev-drive-exception authorizations). The blanket rule was stale/overbroad and is
replaced, not the underlying safety invariant — real-player accounts still stay `{app, human}`-only;
the change is scoped to `crawl_sacrificial=true` profiles, where an AI agent may now live-drive
(manually per dev-drive-exception.md, or via autopilot/chain execution per witness-carte-blanche)
for development, debugging, and proving the client works end-to-end.

Also unblocks WO-BUILD-DEV-DRIVE-SENDER-ENFORCEMENT (the third `VALID_SENDERS` value +
`crawl_sacrificial` gate), built in the same session.
