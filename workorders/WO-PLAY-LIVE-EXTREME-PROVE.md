# WO-PLAY-LIVE-EXTREME-PROVE

**Status:** OPEN · **supersedes parked Accept of** `WO-PLAY-OFFER-LIVE-REPROVE`  
**Posted:** 2026-07-27T05:19:10Z · Max GO ("don't wait — prove it all out to the extreme")  
**Seat:** `impl-claudecode-aiclient` (live TWGS / Fable)  
**Depends:** tip ≥ `bd9ea1a` (offer mid-strip). Prefer mint-canon tip if #PASSWORD merges mid-flight; do **not** block starting on `bd9ea1a`.

## Goal

Extreme live proof of the one-client Play ladder on a real TWGS:

1. **Password/RETURNING gate** — product mint only (empty `secrets.json`), NEW register → disconnect → ensure again (RETURNING) succeeds.
2. **Offer visibility** — with populated `log_tail`, mid-strip shows explore offer (`press E`).
3. **Arm path** — `E` → `y` → explore progress on hint band (`explore N/5…` / `explore_band`).

## Hard rules (tonight’s failure modes)

- **Never** hand-seed `secrets.json` with `token_urlsafe` or any password. Start `{}` chmod 600; let the daemon/login mint.
- **Never** reuse `Proof79ba3d58` / the 0424Z bank as primary — fresh handle every attempt.
- Random catalog server (port 2002 preferred after first non-2002 skip), NEW `allow_register=true` profile hand-written.
- If offer invisible: **FAIL honest** with frame evidence — do not press E blind.
- Redact secrets in audit; never paste passwords to coord.

## Accept (all required)

| # | Criterion |
|---|-----------|
| A | NEW char reaches `main_command` via product mint |
| B | Second ensure (RETURNING, same secrets) reaches `main_command` — proves mint is TW-safe |
| C | Play shows offer on mid-strip with live `log_tail` (observed) |
| D | `E`→`y` arms explore; hint band shows live progress |
| E | Audit under `audit/live-play-extreme-<shortsha>-<UTC>.md` |

Partial A-only without B/C/D = not Accept (document which legs passed).

## Proof

Live audit + STATUS. Unit suite alone is insufficient.

## After Accept

Seat may idle briefly; hub will refill toward larger vision (teach `T` wire / P5 / north-star) — do not invent that lane until HANDOFF.
