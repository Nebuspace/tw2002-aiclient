# WO-BUILD-PLAYER-BANK-ROTATION-DRIVER

**Goal:** `player_bank.next_player` / `tw players next` already pick a
read-only rotation *suggestion*; canon (`canon/surfaces/entry-and-profile-
selection.md` "Code divergence") flags that no rotation **driver** exists —
something that actually decides whose turn is due, as a first-class,
independently invocable operation, rather than a value a caller happens to
compute inline. This WO adds that driver.

**Rotation policy — the explicit decision this WO is required to document:**
**round-robin by oldest-`last_played`-first**, never-played profiles breaking
first, among rows outside the cooldown window. This is not a new policy: it
is `next_player`'s own existing key ordering (`(0, name)` for never-played,
then `(1, timestamp.timestamp(), name)` oldest-first, `(2, name)` for
unparseable-but-included rows when the cooldown is 0) — verified by reading
`player_bank.py:288-313` before writing `advance_rotation`. The driver wraps
`next_player` rather than re-deriving that ordering, so the two can never
silently diverge (`test_advance_rotation_matches_next_player_exactly` pins
this directly, sweeping three cooldown values).

**Decide-and-report, not decide-and-consume:** grepped the whole tree for any
existing writer of `last_played` (`grep -rn "last_played"
tw2002_aiclient/`) — every hit is a *reader* (`player_bank.py`,
`players_cli.py`, `screens.py`, a demo-fixture literal in `app.py`'s
`TW2002_BANK_SMOKE` path). No write path exists anywhere in this codebase
today; session-end rotation bookkeeping is a separate future wave. A driver
that fabricated a "played" stamp here would be recording a play session that
never happened — the opposite of this repo's honesty doctrine
(`player_bank.py`'s own module docstring on `BankUnreadable`). So
`advance_rotation` **decides and reports only**: it returns a
`RotationDecision(name, reason)`, never touches `BANK_PATH`, never opens a
session, never sends a keystroke
(`test_advance_rotation_never_writes_last_played` proves the store is
untouched). When a write path for `last_played` eventually lands, that
future caller marks a rotation *consumed* at the point a session genuinely
ends, using the same `name` this driver reported — out of scope here.

**Scope:**
- `tw2002_aiclient/session/player_bank.py` — new `RotationDecision` class +
  `advance_rotation(rows=None, *, cooldown_hours=..., now=None)`; module
  docstring / `DEFAULT_ROTATION_COOLDOWN_HOURS` comment updated to describe
  the driver instead of flagging it as future work.
- `tw2002_aiclient/players_cli.py` — new `tw players rotate` verb
  (`cmd_players_rotate` + parser wiring), mirroring `cmd_players_next`'s
  read/print/exit-code shape exactly.
- `tests/test_player_bank.py` — driver unit tests appended under a new
  `WO-BUILD-PLAYER-BANK-ROTATION-DRIVER` section.
- `tests/test_players_cli_rotate.py` — new, mirrors
  `tests/test_players_cli_list.py`'s structure for the new verb.
- this WO file.

**Out of scope:**
- Any write path for `last_played` / rotation consumption — none exists yet;
  inventing one is a separate WO once session-end bookkeeping is designed.
- Auto-login, auto-switch, or any live socket action. `advance_rotation` is
  read-only exactly like `next_player`; the daemon-side consumer that would
  actually act on a driver decision remains a distinct future wave (canon's
  own phrasing: "auto whose-turn-is-it across the bank").
- Changing `next_player`'s selection logic or key ordering — the driver
  wraps it unchanged.

**Constraints:**
- `advance_rotation` must never diverge from `next_player`'s own selection —
  no independent re-implementation of the ordering.
- No new persistent write, no new file, no mutation of `BANK_PATH` or any
  other store from this function.
- `rows=None` defaults to `list_players()` (matching `cmd_players_next`'s own
  call shape); `BankUnreadable` propagates unchanged, never swallowed into a
  decision.
- CLI tests use dynamic `datetime.now(timezone.utc)`, never a hardcoded
  clock-bomb date, per this repo's testing convention.

**Accept:**
1. `advance_rotation` returns `RotationDecision(name="alpha", reason="due")`
   for the same never-played-first, then-oldest ordering `next_player`
   already proves.
2. `advance_rotation([], ...)` reports `reason="empty_bank"`; all-rows-in-
   cooldown reports `reason="none_eligible"` — both `name=None`.
3. `advance_rotation` never writes `BANK_PATH` or any file — proven by
   asserting the path does not exist after a call.
4. `BankUnreadable` from `list_players()` propagates out of `advance_rotation`
   unchanged when `rows` is omitted.
5. `tw players rotate` prints the due profile name (exit 0), a reason-bearing
   "no eligible player (...)" message (exit 1) when nobody is due, or the
   unreadable-bank message (exit 2) on `BankUnreadable` — mirroring `tw
   players next`'s exit-code contract.

**Proof:** `.venv/bin/python -m pytest tests/test_player_bank.py tests/test_players_cli_list.py tests/test_players_cli_rotate.py -n0 -q` → 55 passed. Wider sweep `.venv/bin/python -m pytest tests/ -k "player or bank" -n0 -q --junitxml=...` → 198 passed, 0 failures, 0 errors.
