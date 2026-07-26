# WO-TEST-FAKE-SERVER-SOCKET-FLAKE

**Status:** DONE · tip pending (connect-side barrier + forced-repro)  
**Prior:** `34a41b4` landed PARTIAL (`.errors` xdist poison fixed) · CLOSED banner @ `7afcbcf` **reverted** — 4 post-fix reds after tip (≥1 serial).  
**Posted:** 2026-07-25 IDLE-KICK refill (CC disclosure)

## Goal

Eliminate the remaining FakeTWGS / `test_real_broken_pipe…` race so parallel **and serial** runs stop producing unrelated reds.

## Context

Two independent sightings under xdist (historical):
1. `test_tx_record_honesty::test_real_broken_pipe_never_leaves_an_unqualified_TX_claim` — Bad file descriptor in FakeTWGS server thread (CC tip isolation proved serial green).
2. `test_login::test_registration_refused_raises_before_any_char_create_send` — same family on player_bank lane.

**Post-`34a41b4` (CC):** four full-suite / serial reds of the same test after the tip; one fresh green on `7afcbcf` proves nothing at ~1-in-3 flake rate. Diagnosis "xdist-only" is falsified by a serial failure.

`pytest.ini` defaults to `-n auto` — every lane pays the tax.

## Scope

Fake server / PTY / socket fixture teardown (+ tests that pin the flake). Prefer fixture lifecycle fix over ignoring tests.

## Constraints

No classify · no secrets expand · cite if touching shared fixtures.

## Accept

**Structural** argument the race cannot occur, **or** a **forced deterministic repro** (barrier at the suspect point → red every time before, green every time after). Run counts are corroboration only — **never** the Accept gate. Do not weaken honesty Accept of affected tests.

## Proof

STATUS + SHA · forced-repro or structural writeup · hub Accept.

## Refs

CC 2026-07-26T03:15:00Z reopen ask · tip `34a41b4` · CLOSED stamps `7afcbcf` (banner wrong for this WO only)
