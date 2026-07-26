# WO-LIVE-ENSURE-MATRIX

**Status:** OPEN · Cursor preferred · **Max GO 2026-07-26** — prove game-select + NEW + RETURNING on live servers  
**Posted:** 2026-07-26T07:46Z

## Goal

Empirically prove, on **≥3 distinct live TWGS-direct servers**, that:

1. **Game selection** honors `game_letter` from the profile (different letters and/or different servers).
2. **NEW character creation** works when `allow_register=true` (sacrificial handles only).
3. **RETURNING automatic login** works on a subsequent `ensure` with the saved password (same profile, fresh daemon/session).

## Scope

- **Isolated** `TW_CONFIG_DIR` under `/tmp` or `audit/live-ensure-matrix-<UTC>/` — **never** touch Max's live `config/profiles.toml` / `secrets.json` / `xeno`.
- Profiles: `crawl_sacrificial=true`, `allow_register=true`, unique throwaway handles (prefix `Proof` + random), cosmetic names from pools.
- Candidate hosts (TCP UP @ probe 07:45Z): `roguetw.net:2002` · `twgs.microblaster.net:2002` · `game.a-net-online.lol:2002` (swap if a host refuses register / is full — document and pick next UP host).
- Per server: (A) ensure NEW → reach main command / post-login stable class · (B) stop · (C) ensure RETURNING → same · capture `tw status --json` / screen class + redacted log excerpts.
- At least one matrix cell with a **different `game_letter`** than another cell (prove select is profile-driven, not hardcoded `A`).
- Optional 4th: `twgs.exiled.org:2002` **RETURNING-only** only if Max later OK's using an existing sacrificial there — default **skip** Max's `xeno` profile.

## Constraints

- **Sacrificial only** — no real-money / named alts; stop if a prompt is gameplay-committal beyond login cosmetics.
- Secrets stay in the isolated dir (chmod 600); **do not commit** secrets or raw RX with passwords.
- Stay off CC X5 lanes (`autoloop` / floor / player safety kernel).
- Corpus/fixtures: trim handles before any tracked artifact.
- If BrokenPipe / ensure FAIL: record host+phase+recovery attempt (stop+re-ensure once); do not silently mark PASS.
- Product classify fixes still need hub GO — report defects as findings/WOs.

## Accept

A results matrix (server × NEW × RETURNING × game_letter) with PASS/FAIL + evidence paths; defects filed as WOs for any FAIL; STATUS with SHA only if docs tip lands (matrix report may live under `audit/` untracked or docs-only tip without secrets).

## Proof

Live runs + matrix markdown · redacted STATUS.

## Refs

Max request 2026-07-26 · login-automaton.md NEW/RETURNING · `allow_register` · WO-GAME-SELECT-CLASSIFY-SCOUT (related; may finish scout first or fold method notes)
