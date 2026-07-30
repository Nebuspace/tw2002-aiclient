# WO-HUD-I-LIVE-FIXTURE

## Goal

Promote the live-captured ship-info (`I`) screen from #226 into the durable
test corpus and prove that exact screen fills HUD turns without relying only
on a hand-typed label.

## Scope

- `tests/fixtures/ship_info_screen.txt`
- `tests/test_hud_status_bridge.py`

## Constraints

- Test/fixture only. Do not modify parser, daemon, cockpit, canon,
  dependencies, or runtime.
- Copy the capture byte-for-byte from
  `.samantha/audit/hud-status-bridge-live-20260729T1838Z/I_ship_info_raw_screen.txt`.
  Expected SHA-256:
  `5fa6cfb3aaf7989e0c94c7fcb27d028366b9643f109ab7765c566c9f5ef9c867`
  (1525 bytes, 25 lines). Do not normalize trailing spaces or redraw it.
- The fixture contains game-screen content only. Do not copy profile,
  hostname, run-directory, inventory, or coordination metadata.
- Keep the existing synthetic adversarial pins where they prove properties
  the live capture does not isolate. Add the real capture as integration
  evidence; do not weaken newline-forgery or countdown refusal tests.
- Read the fixture through the same `Session`/`protocol._status_response`
  path used by the existing HUD bridge tests.

## Accept

1. The committed fixture is byte-identical to the captured source and its
   test asserts the load-bearing live lines (`Turns left : 25000`, countdown
   prompt, current sector, and credits).
2. `read_turns_left_from_screen` reads `25000` with
   `SOURCE_TURNS_LEFT_LABEL`, while the countdown prompt itself remains
   `OUTCOME_ABSENT` and never yields forged zero.
3. The real `Session` + status-response path emits top-level
   `turns_left=25000` and `hud.turns.value=25000`; sector/credits may also be
   asserted only where the captured screen positively states them.
4. Existing synthetic edge-case tests remain intact.
5. Focused HUD bridge tests and the full offline suite pass.

## Proof

```bash
shasum -a 256 tests/fixtures/ship_info_screen.txt
pytest -q tests/test_hud_status_bridge.py
pytest -q tests
```

Live prove is `n/a`: this commits already-observed #226 evidence and changes
no product/runtime behavior.

## Refs

- #226 / `WO-HUD-STATUS-BRIDGE`
- `.samantha/audit/hud-status-bridge-live-20260729T1838Z/SUMMARY.md`
- `.samantha/audit/hud-status-bridge-live-20260729T1838Z/I_ship_info_raw_screen.txt`
- `tests/test_hud_status_bridge.py`
- Depends on `main` @ `c167d00`
