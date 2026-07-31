# WO-PLAY-STRIP-TRAINER-CHROME

**Status:** DONE · tip `fd90573` (`wo/PLAY-STRIP-TRAINER-CHROME`) · HIGH · Max GO 2026-07-31 (trainer strip redesign wave 1/3)
**Seat:** `impl-aiclient-cursor`
**Branch:** `wo/PLAY-STRIP-TRAINER-CHROME`
**Depends:** `main` ≥ `f378779` · DECISION `RESOLVED-TRAINER-STRIP-AND-GUTTER-20260731`
**Proof:** WO Proof list + full `pytest tests/ -q` green (6727 passed, 0 failed). live-prove **n/a** (chrome/layout paint only).

## Why

Calm Play chrome is a developer repertoire (A/R/T/V/U/H/O + Panic + separate APP/ARM/CONN).
Max ruled a trainer strip: Mode key + merged seat, Port/Loops/Trade/Cargo/Ship labels,
CONN on the top server row, outcomes in LOGS — not mid-strip.

## Goal

Ship **chrome + paint policy** for the trainer bottom/top strip. Policy auto-spend and
left-gutter nest are follow-on WOs (`WO-PLAY-STRIP-POLICY-AUTO`,
`WO-LEFT-GUTTER-NEST-FOCUS-FORMATIONS`).

## Scope

1. **Merged seat chip with Mode key**
   - Bottom strip shows `^A)APP-ARMED` or `^A)MANUAL-HUMAN` (narrow OK: `^A)APP` / `^A)MANUAL`).
   - Do **not** co-render separate `APP` + `ARM ON/OFF` chips.
   - Spectate: keep honest SPECTATE (or documented short form); do not lie APP-ARMED.
2. **Calm teachband tokens only**
   - `E)xplore`
   - `P)ort Trade·ON` / `P)ort Trade·OFF` (default **ON** for new Play)
   - `L)oops` (reuse/adapt chains list affordance; label may stay `L)oops`)
   - `T)rade Loop Chain`
   - `C)argo Hold Upgrade·ON` / `·OFF` (default **ON**)
   - `S)hip Upgrade·ON` / `·OFF` (default **ON**)
   - Retire from calm band: A/R/T/V/U, `H)old?`, `O)ffer?`, `P panic`.
3. **CONN → top / server row**
   - Remove CONN from bottom control strip.
   - Place beside host/server identity on the profile/title strip.
   - Connected = **green slowly flashing** light; offline/unknown = honest non-green (no lying pulse).
   - Move or retire CONN keyboard-focus with the chip (no dead arrow target on bottom).
4. **status_line → LOGS**
   - App outcome / offer prose paints in **LOGS** (append or reserved row) — not mid control-strip `status_offer`.
   - Do not wipe the session transcript with a single status line.
5. **Canon**
   - Amend `canon/surfaces/mode-line-and-teach-controls.md` (and strip diagrams) to match this DECISION.
   - Mark `OPEN-PLAY-STATUS-MIDSTRIP` superseded in `canon/DECISIONS.md` if not already.
6. **Pins**
   - Teachband exact calm string / tokens.
   - Merged seat+Mode key visible; no separate ARM chip on calm strip.
   - CONN on top strip when connected (tone/flash); absent from bottom strip.
   - With live LOGS tail, outcomes still appear in LOGS (not mid-strip).
7. This WO file on the branch.

## Out of scope

- Nesting FOCUS inside GOALS / tall FORMATIONS panel → `WO-LEFT-GUTTER-NEST-FOCUS-FORMATIONS`.
- Making Mode leave halt all runners; retiring panic **handler**; silent money-path auto without `y` → `WO-PLAY-STRIP-POLICY-AUTO`.
- Wiring C/S/P toggles into daemon spend paths beyond local Play state that drives chrome (stubs OK if App ignores them until WO3 — document honesty).
- #283 live diversity.

## Constraints

- No new deps · lead-seat OK · no force-push.
- Width: teachband is all-or-nothing — shorten labels only if pins prove drop; prefer truncation strategy already used.
- ADR-002: Mode remains **Ctrl-A**; attached `M` = Move.

## Accept

1. Calm strip matches Max chrome (Mode+seat · E · Port Trade · Loops · Trade Loop Chain · Cargo Hold Upgrade · Ship Upgrade) with defaults ON for P/C/S.
2. No Panic / A/R/T/V/U / Hold? / Offer? on calm teachband.
3. CONN not on bottom strip; top row shows green slow flash when connected.
4. Outcome prose visible via LOGS path; mid-strip offer segment gone or unused.
5. Suite green · live-prove **n/a** (chrome/layout paint — no money-path live arm).

## Proof

```bash
.venv/bin/python -m pytest \
  tests/test_cockpit_teachband.py \
  tests/test_cockpit_teachband_pty.py \
  tests/test_cockpit_conn_pty.py \
  tests/test_cockpit_strip.py \
  tests/test_cockpit_arm_wiring.py \
  tests/test_play_offer_visible_on_live.py \
  -n0 --tb=line
# + full suite before STATUS
```

## Refs

- `.samantha/plans/play-strip-autonomy-keys.md`
- DECISION `RESOLVED-TRAINER-STRIP-AND-GUTTER-20260731`
- Explore map: seat `control_seat` / `teachband` / `strip` / `screens` / `arm`
