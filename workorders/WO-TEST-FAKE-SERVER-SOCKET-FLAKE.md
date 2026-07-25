# WO-TEST-FAKE-SERVER-SOCKET-FLAKE

**Status:** OPEN · Cursor preferred (tests lane)  
**Posted:** 2026-07-25 IDLE-KICK refill (CC disclosure)

## Goal

Stabilize FakeTWGS / fake-server socket teardown under `pytest -n auto` so default parallel runs stop producing unrelated reds.

## Context

Two independent sightings under xdist:
1. `test_tx_record_honesty::test_real_broken_pipe_never_leaves_an_unqualified_TX_claim` — Bad file descriptor in FakeTWGS server thread (CC tip isolation proved serial green).
2. `test_login::test_registration_refused_raises_before_any_char_create_send` — same family on player_bank lane.

`pytest.ini` defaults to `-n auto` — every lane pays the tax.

## Scope

Fake server / PTY / socket fixture teardown (+ tests that pin the flake). Prefer fixture lifecycle fix over ignoring tests.

## Constraints

No classify parked tip · no secrets Max-gate expand · cite if touching shared fixtures.

## Accept

Targeted reproduction that was red under `-n auto` is green repeatedly (≥3 parallel runs) without weakening the honesty Accept of the affected tests.

## Proof

STATUS + SHA · before/after parallel evidence.

## Refs

CC STATUS disclosure @ ~2026-07-25 (parallel suite nondeterministic socket flake).
