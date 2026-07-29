# WO-HUD-STATUS-BRIDGE — daemon emits `status["hud"]` tracked vitals

**Status:** READY · visible client gap (Max live-test 2026-07-29)
**Seat:** `impl-claudecode-aiclient`
**Branch:** `wo/HUD-STATUS-BRIDGE`
**Depends:** `main` ≥ `a88116c` (#225)

## Goal

Play's always-on HUD stops sitting on sticky `-` for fields the session can
already (or can safely) observe. Today `cockpit/hud.py` defines the wire
contract and paints honest unknown because **no producer emits
`status["hud"]`**. Login/viewport can show turns on the raw TWGS screen while
the right-gutter HUD stays blank — that mismatch is this WO.

## Symptom (operator)

After auto-login, the game screen shows turns; HUD CREDITS / SECTOR / TURNS
cells stay `-` and never fill during Play.

## Scope

1. **Emit `status["hud"]`** from `_status_response` (and any shared status
   builder Play already polls) matching the contract in `cockpit/hud.py`:

   ```
   status["hud"] = {
     "credits": {"value": <int|None>, "age_s": <float|None>},
     "sector":  {"value": <int|None>, "age_s": <float|None>},
     "turns":   {"value": <int|None>, "age_s": <float|None>},
     "cargo":   {"value": <int|None>, "age_s": <float|None>},  # may stay unknown
     "profit":  {"value": <int|None>, "age_s": <float|None>}, # may stay unknown
   }
   ```

2. **Sticky tracked model** (daemon-side monotonic ages) — persist last-known
   values across screens that omit a field. Prefer extending the existing
   `Session.observe_credits` / `credits_snapshot` pattern rather than inventing
   a parallel accumulator if one field already has the shape.

3. **Producers (minimum visible set):**
   - **credits** — already: `observe_credits` + `read_credits_balance` (T2).
   - **sector** — already: `read_current_sector` / `sector_wire` on the settled
     prompt line (do **not** reintroduce raw `status["prompt"]`).
   - **turns** — **new careful extractor** for classic `TL=<count>…` shapes on
     the command prompt; **must refuse** `TL=HH:MM:SS` countdown (archive
     defect: countdown forged `turns_left=0`). Absent/unreadable → leave cell
     unknown, never invent 0.

4. Update `tests/test_status_vocabulary_guard.py` STARVED_ALLOWLIST: remove
   `hud` when emitted; remove `credits` / `turns_left` **only if** those
   top-level keys are also produced (GOALS consumers). If this WO nests under
   `hud` only, leave top-level starved entries with an updated reason pointing
   here or a sibling — do not silently leave a false "no producer" claim for
   a key you now write.

5. Offline tests with captured / synthetic screens: classic TL count fills
   turns; countdown TL leaves turns unknown; sticky persistence across a
   credits-less screen; composer still paints `-` when hud absent.

## Out of scope

- Cold-join `I`-probe `hud_seed` (sibling; bank if still blank after bridge).
- Cargo / profit extractors (honest unknown OK this WO).
- Motion/liveness polish (delta chips, sparkline, fuel gauge).
- Explore dock default / chains live refresh (next WOs in visible tranche).
- Ledger → HUD (canon N4/N8 forbidden).

## Constraints

- Ages computed daemon-side (monotonic); never ship a clock base on the wire.
- No receive-buffer prompt echo on `status` (secrets doctrine / §C.2).
- DEPLOY-WINDOW if shared runtime daemon restart is required for live prove;
  request via hub before restarting a shared host.
- Smallest change that makes HUD turns/credits/sector visible in Play.

## Accept

1. With a settled classic `Command [TL=<count>…]:[<sector>]` screen on a test
   session, `status["hud"]` carries positive `turns` + `sector` (and credits
   when a credits line is present) with finite `age_s`.
2. Countdown-only `TL=HH:MM:SS` does **not** set turns to 0 / a forged count.
3. Play HUD composer receives the payload without composer changes (contract
   match) — pin via status→compose test or daemon status fixture.
4. Vocabulary guard updated honestly for keys this WO actually supplies.
5. Full offline `suite` green.

## Proof

- Focused unit/integration tests for extract + status hud payload + sticky age.
- Full offline `suite`.
- **Live-prove → Cursor** after suite green: attach Play on ≥1 reachable host,
  confirm HUD TURNS (and SECTOR/CREDITS when on screen) leave `-` after login
  / main_command. Safe half OK; no new arm path.

## Refs

- Max live-test complaint 2026-07-29 (HUD blank while login shows turns)
- `tw2002_aiclient/cockpit/hud.py` wire contract + "no wire bridge yet"
- `tw2002_aiclient/session/protocol.py` `_status_response` (credits/turns deferred note)
- `tw2002_aiclient/session/state_parser.py` TL= countdown refusal rationale
- `tests/test_status_vocabulary_guard.py` (`hud` T4 · `turns_left` T3 · `credits` T2)
- `.samantha/plans/visible-client-gaps-2026-07-29.md`
