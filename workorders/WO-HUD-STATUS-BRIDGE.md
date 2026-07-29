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
   - **turns** — **new careful extractor** `read_turns_left(prompt_line)` on the
     settled prompt line only (same last-match discipline as sector; never
     whole-screen search). Disambiguation (archive scar — pin in tests):
     - `TL=` body matching `\d{1,2}:\d{2}:\d{2}` (HH:MM:SS countdown) →
       **absent** (no key / unknown cell — never forge `0`)
     - otherwise leading digit sequence (e.g. `00753:0/0/0/850`, bare `00753`)
       → **read** with turn count
   - On `OUTCOME_READ`, emit **both**:
     - top-level `resp["turns_left"] = N` (fixes GOALS Turns row)
     - `resp["hud"]["turns"] = {"value": N, "age_s": <daemon age>}` (fixes HUD)

4. Update `tests/test_status_vocabulary_guard.py` STARVED_ALLOWLIST: remove
   `hud` and `turns_left` when those keys are produced; remove `credits` only
   if top-level `credits` is also written this WO. Exact-set guard fails both
   directions — stale allowlist entries after wiring are red.

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

1. Classic `Command [TL=00753:0/0/0/850]:[<sector>]` → `status["turns_left"]=753`
   and `status["hud"]["turns"]` value 753 with finite `age_s`; sector/credits
   fill when their producers read.
2. Countdown `Command [TL=00:00:00]:…` → **no** `turns_left` key and HUD turns
   stay unknown — never a forged `0`.
3. Play HUD composer unchanged (contract match) — status→compose pin.
4. GOALS Turns row consumes top-level `turns_left` (not viewport paint).
5. Vocabulary guard updated honestly for keys this WO actually supplies.
6. Full offline `suite` green.

## Proof

- `tests/test_state_parser_turns.py` (or equivalent): classic → 753; countdown
  → absent; bare `TL=00753` → 753; non-string → unreadable.
- Status/hud integration + sticky age pins.
- Full offline `suite`.
- **Live-prove → Cursor** after suite green: Play HUD TURNS leave `-` after
  login / main_command; GOALS Turns not `? —` when classic TL is on screen.
  Safe half OK; no new arm path.

## Refs

- Max live-test complaint 2026-07-29 (HUD blank while login shows turns)
- Hub diagnosis corroboration 2026-07-29: viewport shows raw TL=; missing
  `read_turns_left` (T3) + missing `status["hud"]` (T4) + Wave-3 cut at
  `protocol.py` `_status_response` — payload omission, not a composer bug
- `tw2002_aiclient/cockpit/hud.py` wire contract + "no wire bridge yet"
- `tw2002_aiclient/session/protocol.py` `_status_response` (credits/turns deferred note)
- `tw2002_aiclient/session/state_parser.py` TL= countdown refusal rationale (~412–421)
- `tests/test_status_vocabulary_guard.py` (`hud` T4 · `turns_left` T3 · `credits` T2)
- `.samantha/plans/visible-client-gaps-2026-07-29.md`
