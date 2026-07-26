# WO-README-PLAYER-VOICE

**Status:** IN FLIGHT · Claude Code **side-subagent** (parallel to blank-reject) · hub-seeded `wo/README-PLAYER-VOICE`  
**Posted:** 2026-07-26 · Max ask — README is techno / deprecated / ops-verb soup; humans run one trainer client  
**Seat:** `impl-claudecode-aiclient` — **dispatch a subagent**; do **not** pause or dilute `WO-MICRO-LOGIN-BLANK-REJECT`

## Goal

Rewrite `README.md` for someone who wants to **play TradeWars 2002 with this trainer** — not for agents implementing WOs.

**Human truth:** there is **one** executable a person runs: `./tw2002-aiclient` (product TUI / launcher / play shell). Everything else (`./tw …`, daemon internals, workorders, classify, ensure matrix, pytest) is **AI-agent / ops** surface and must not dominate the README.

## Voice & content

Write as: *"I want to fly TW2002 with a powerful trainer."*

**In (player-facing):**
- What this is (trainer client; you teach the App; AI may propose, never live-drives)
- Install / venv / run `./tw2002-aiclient`
- Create or pick a profile, connect, play
- Autopilot / taught screens in plain language (halts when untaught)
- Where credentials live (local, private) — no how-to dump of every `tw` verb
- Link out once: “Agent / automation CLI is `./tw` — see CLAUDE.md or a short AGENTS note” (do not paste the verb table into the hero README)

**Out:**
- Full `./tw` verb catalog as the centerpiece
- Deprecated “coming soon” ops inventories that read as current
- Workorder / ADR / Phase-N scaffolding as primary docs
- Architecture diagrams that bury the play path
- Techno mumbo jumbo (settle edges, control-lock generation tokens, xdist, …) unless one short “reliability under the hood” paragraph is truly needed

## Scope

- `README.md` only (rewrite in place). Optional: 3–8 line pointer file `AGENTS.md` **only if** needed to park ops/agent docs without bloating README — ask in STATUS if you add it; default = README-only.

**Out of bounds:** product code · `login.py` / blank-reject · classify invent · deleting `./tw` · rewriting CLAUDE.md

## Accept

1. A new player can skim README and know: install → run `./tw2002-aiclient` → play; one human executable.
2. `./tw` is demoted to a short “for agents/automation” aside (or AGENTS.md), not a second product.
3. No stale “not on --help yet” verb laundry lists as the main body.
4. STATUS cites before/after intent; Pixel-ish sanity on tone OK via seat self-check.
5. Blank-reject lane remains primary — this WO is a **side-subagent** only.

## Proof

Diff of `README.md`; optional `wc -l` before/after; no suite required beyond secret-scan / path-leak on commit. live-prove n/a (docs).

## Refs

- Max session 2026-07-26T18:56Z
- Current `README.md` (product vs ops table is the smell to fix)
- Executable: `./tw2002-aiclient` → `tw2002_aiclient.app`
