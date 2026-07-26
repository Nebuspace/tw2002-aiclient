# Live ensure stall diagnosis — 2026-07-26 (redacted)

**Dispatch:** Max's ensure DoD re-prioritization · **Seat:** monk/impl-claudecode-aiclient (isolated worktree)
**Tip:** `f6432a1` (WO-ENSURE-SPAWN-READINESS `61bdea2` already ancestor — the readiness-probe
defect from `WO-ENSURE-SPAWN-READINESS` is already fixed at this tip)
**Isolated config reused:** `/tmp/tw2002-live-ensure-matrix-20260726T0801Z` (`proof_micro`,
`proof_anet`, `proof_rogue` — no new accounts registered, per constraint)
**No passwords, handles, or committed screen dumps in this file** — same discipline as the sibling
matrix doc. Frame JSON lives under `/tmp` only (paths below); none of it contains a secret or an
operator handle (both stalls happen *before* either profile's handle is ever sent — see below).

## Method (Phase 1 discriminator, per host)

1. Reproduce the stall via `tw ensure --profile <p> --run-dir <isolated>`.
2. **Do not disconnect.** `_login_failure_response` (protocol.py:819-830) deliberately omits
   `screen`/`prompt` on a failed `ensure` (canon `DECISIONS.md` C.2 — redaction-by-omission against
   password-echo hosts) but the TCP session is left connected (`_dispatch_ensure` never closes on
   `LoginError`). `screen` / `read` still call `build_response()` unchanged, so the **same live
   session** can be inspected right after the failure — this is the documented recovery path
   (`login.py:316-327`'s own comment: "the operator's screen is still the operator's — via a live
   attach, the `screen` verb, or a `subscribe` feed"). This resolves the earlier matrix's "stall
   frame: Gone" note — it was never lost, `ensure`'s own response just never carries it.
3. Capture frame **A** via `tw screen` immediately.
4. Force a second settle cycle via `tw read --timeout 10` (read-only, waits idle/prompt/timeout) —
   frame **B**, plus `settled_reason`.
5. Capture frame **C** via a second `tw screen`.
6. Compare A/B/C. Identical ⇒ stable-but-unclassified (classify-coverage gap). Different ⇒ mid-paint
   (settle/timing gap).

## Result 1 — `twgs.microblaster.net` (`proof_micro`), NEW

Reproduced identically to the matrix: `login_failed:automaton_stuck:classification='unknown':step=6`.

**Discriminator: A == B == C, byte-identical.** `read`'s `settled_reason` = `timeout` after a full
10s wait with zero new bytes. **Not mid-paint — a stable, dead-end screen.**

**Frame content** (`/tmp/…/micro-frame-A.json`): the OUTER BBS connection-level name prompt, three
full prompt/reject cycles, ending on the reject line with no further prompt:
```
Please enter your name (ENTER for none):
A login name is required.
Please enter your name (ENTER for none):
A login name is required.
Please enter your name (ENTER for none):
A login name is required.
```
The raw transcript (`logs/session-20260726T122630Z.log`, this worktree, gitignored) confirms it byte
for byte: our automaton sent blank+CRLF **four** times (`login.py`'s documented behavior for this
exact prompt shape — `_OUTER_NAME_PROMPT_RE` correctly matches "ENTER for none" and answers blank,
per canon `login-automaton.md`'s own worked example). The first three sends each got
`"A login name is required."` followed by a fresh re-ask. The **fourth** send got the rejection with
**no re-ask following it** — the host goes silent. At that point the CURRENT last line is
`"A login name is required."`, which matches no `classify.py` anchor (gate or content) ⇒ `unknown`,
and stays `unknown` for 3 stagnant rounds ⇒ `automaton_stuck`.

**Diagnosis: this is a genuine remote-host divergence, not a classify or settle bug.**
`twgs.microblaster.net`'s outer BBS gate does not honor its own printed "(ENTER for none)" — it
rejects a blank name, and after repeated rejections stops re-displaying the prompt at all, so the
automaton is *correctly* driving canon's documented flow against a host that does not behave the way
that flow assumes. `login.py` has no retry/fallback for this specific gate (no "if the blank answer
gets explicitly rejected, retry with `profile.handle` instead" branch) — every other prompt in the
table has exactly one interpretation; this one has two live server behaviors and the automaton only
implements one of them.

**Neither the handle nor a password is ever sent on this path** (the stall is upstream of both the
module-entry menu and the character-handle prompt) — nothing to redact beyond the host/game text
already in the matrix.

## Result 2 — `game.a-net-online.lol` (`proof_anet`), NEW

Reproduced identically: `login_failed:automaton_stuck:classification='menu':step=5`.

**Discriminator: A == B == C, byte-identical.** `settled_reason` = `timeout` after 10s idle.
**Not mid-paint.**

**Frame content** (`/tmp/…/anet-frame-A.json`): the TWGS server-level game-select screen — banner
(`TWGS v2.20b` / `Server registered to A-Net Online`) followed by a heavy ANSI-art box containing the
game list (`<A> Space Balls` … `<Q> Quit / Logoff`) and, embedded inside the art, the title text
`Trade Wars 2002 Game Server`.

**Diagnosis: confirmed classify-coverage gap, verified by calling `classify_screen()` directly
against the captured text** (not inferred):

```
title match?      False   (_TWGS_BANNER_TITLE_RE)
version match?     True   (_TWGS_BANNER_VERSION_RE)
registered match?  True   (_TWGS_BANNER_REGISTERED_RE)
_is_twgs_server_banner_game_select_menu -> False
_is_twgs_boxed_game_select_menu         -> False
classify_screen                         -> 'menu'
```

Two independent reasons, **either one alone would sink it**:

1. `_TWGS_BANNER_TITLE_RE = r"trade\s*wars\s+game\s+server"` (classify.py:158) requires "wars"
   directly followed by whitespace then "game" — no token allowed between them. This host's title is
   `Trade Wars **2002** Game Server` (note the year inserted) — never matches.
2. Even granting a fixed title regex: `_BANNER_PROXIMITY_MAX_LINES = 6` (classify.py:164) requires
   the three banner lines to sit within 6 rows of each other. On this host, `TWGS v2.20b` /
   `Server registered to …` are plain top-of-screen lines (rendered rows 0, 2) but the title text is
   embedded 13 rows down, *inside* the ANSI-art box — an 13-row spread, not 6. The proximity
   invariant would reject it even with signal (1) fixed.

Neither `_is_twgs_boxed_game_select_menu` (needs a bare "Game" header cell — this host's title cell
is "Trade Wars 2002 Game Server", not a bare "Game") nor the plain `"select a game"` gate anchor
matches either, so the screen falls through to the generic `menu` content anchor (correctly, given
its ten-plus bracket-style options) — a **content anchor**, so `game_select` (a **gate** anchor
family) never gets a chance to override it, and `login.py`'s `_decide()` has no rule for "menu that
is actually the game-select door," so it stagnates.

**This is a fourth, real, live-captured TWGS game-select layout** distinct from the three already
anchored (`select a game`, boxed-"Game"-header, plain banner+bracket-list) — same status the other
three had before their own dedicated WO. It is **not** a one-line regex loosen: the proximity
invariant is there specifically to stop a stale banner vouching for an unrelated later menu
(`_is_twgs_server_banner_game_select_menu`'s own docstring), so widening it needs the same
adversarial-hardening pass (fixture + stale-scrollback negative tests) every prior variant got, not a
drive-by widen.

## Contrast / control — `roguetw.net` (`proof_rogue`), same code, same tip

Requested by the hub mid-build: since `proof_rogue` already has a saved credential and both NEW and
RETURNING passed clean on it, it is not usable for a fresh NEW/RETURNING split test, but it **is** a
live control for "what does a working `game_select` screen look like on this exact code." Captured
via `tw ensure game_select --profile proof_rogue` (target set to `game_select` so `run_login` returns
the instant it classifies correctly, rather than driving further) — succeeded in exactly 1 automaton
step, `classification: "game_select"`.

Its banner: `TradeWars Game Server` (no digit token — matches `_TWGS_BANNER_TITLE_RE` cleanly) with
`TWGS v2.20b` / `Server registered to Gone Rogue` all within 3 rendered rows of each other (well under
the 6-row proximity budget) and **no** ANSI-art box burying the title. This is squarely the shape
`_is_twgs_server_banner_game_select_menu` was built for, and it is why the *same* classify.py
recognizes rogue and misses a-net: **a host-layout difference, not a flaky detector.**

## Answering the brief's framing question directly

**The stall is per-host, not NEW-vs-RETURNING** (confirmed independently of the hub's correction:
rogue passed both; the two failing hosts were only ever reachable via NEW, since neither ever
persisted a credential — there is no RETURNING case to test on them, and none was manufactured).
**The failing step number varies (5 vs 6) because the two hosts fail at two *different* screens for
two *different* reasons** — not because either host is flaky or the same screen sometimes settles
and sometimes doesn't. Both are **stable** per the settle-twice discriminator. One is a classify gap
on an existing class (`game_select`); the other is a login-automaton gap (no fallback when the
canonical blank-Enter answer is rejected) — neither is a settle/timing defect, and neither needed (or
got) a new `screen_class`.

## What was NOT done, and why

- **No live attempt against `twgs.exiled.org` (xeno).** This dispatch runs in a git-worktree-isolated
  sandbox — the harness itself refused a cross-worktree git read earlier this same session
  ("a worktree-isolated agent's git operations must target its own worktree"). Reaching Max's real
  daemon/socket/config for the **one authorized, precious** ensure attempt against his actual
  character means pointing this worktree's client at the shared checkout's `run/`/`config/` — file
  reads across that boundary are evidently permitted, but a stateful action against a live personal
  session, with no do-over, is a different risk class than a read. I chose not to gamble the one
  shot on a boundary this harness itself flagged as enforced. The exact 3-command recipe above
  (`ensure` → `screen` → `read` → `screen`) is proven on two independent hosts and is ready to run
  verbatim from the main checkout.
- **No classify.py or login.py edit landed.** Both root causes are evidence-backed and the a-net one
  even has an exact file:line, but every prior classify change in this module landed through its own
  scout → fixture → adversarial-review cycle (see the three existing game-select variants' own
  docstrings), and Max's 5A ruling GO'd *investigation*, not a widen. Proposing, not landing, per this
  dispatch's own Phase 3 instruction.
- **No new accounts registered anywhere**, no secrets committed, `proof_rogue`'s connection was
  stopped (`tw stop`) immediately after the one-step control capture.

## Proposed smallest honest fixes (not built)

1. **Micro (login.py):** on the outer `login_name` gate, if the blank-Enter answer is met with an
   explicit rejection line (`"A login name is required."` or similar) rather than a fresh prompt,
   retry once with `profile.handle` instead of stagnating. Scoped narrowly to this one gate; does not
   touch the RETURNING/NEW branch logic. Needs its own fixture (this capture) + a negative test that
   a host accepting blank still gets blank (rogue's own shape).
2. **A-net (classify.py):** a fourth `game_select` detector (or a widened `_is_twgs_server_banner_*`)
   that tolerates (a) a title token between "Wars" and "Game" (i.e. `\S*\s*` not `\s+`) and (b) a
   banner-to-title distance longer than 6 rows when the intervening content is the ANSI-art box itself
   (not a different, unrelated menu) — the exclusivity checks already in
   `_range_has_no_menu_after_game_select_markers` are the right tool to reuse for "nothing else is a
   real menu in between," rather than a flat line-count budget. Needs the same fixture +
   stale-scrollback adversarial pass as the other three variants.

## Proof

- Full suite: **3383** (junitxml read after process exit, `/private/tmp/…/scratchpad/baseline.xml`).
  Tree fingerprint (`git ls-files -z | xargs -0 md5 -q | md5`) identical before and after this session
  (`37910f3b3cefc98d6ab28487cfce9b5e`) — no product file touched.
- Hosts touched: `twgs.microblaster.net` (1 ensure attempt, `proof_micro`, already-existing profile),
  `game.a-net-online.lol` (1 ensure attempt, `proof_anet`), `roguetw.net` (1 ensure-to-`game_select`
  control capture, `proof_rogue`, immediately stopped). **`twgs.exiled.org` (xeno) not touched.**

---

## Addendum — `twgs.exiled.org` (xeno), captured from the main checkout

The sandboxed lane declined to drive the operator's live daemon for a one-shot
stateful action — correct judgement from inside a worktree boundary. Captured here
instead, using the lane's own proven recipe, with Max's explicit GO. **One ensure
attempt only.**

Pre-flight: `daemon_running: true`, `connected: false`, `mode: app` (nobody attached),
idle ~36 min.

**Reproduced:** `login_failed:automaton_stuck:classification='unknown':step=6` — byte-for-byte
the same error the hub saw at 12:04Z.

**Discriminator (capture → independent settle → capture):**

```
frame1: 1999 chars  md5=9acb27084705  classification=unknown
frame2: 1999 chars  md5=9acb27084705  classification=unknown
settle between: settled_reason=timeout
=> IDENTICAL — a stable unclassified screen, NOT mid-paint
```

That makes **3 of 3** failing hosts stable rather than mid-paint. The settle layer is
exonerated on all three; the gap is screen coverage.

**But xeno is a THIRD distinct failure class, not a repeat of either.** Structural markers
against `classify.py`'s own regexes:

| marker | xeno |
|---|---|
| `_TWGS_BANNER_TITLE_RE` | ✗ |
| `_TWGS_BANNER_VERSION_RE` | ✗ |
| `_TWGS_BANNER_REGISTERED_RE` | ✗ |
| `login name is required` (micro's class) | ✗ |
| `ENTER for none` | ✗ |
| `Selection` | ✗ |
| digit-token title (a-net's class) | ✗ |
| box-drawing present | ✓ |
| non-empty rendered rows | 21 |

**No TWGS banner signal at all**, and none of micro's or a-net's fingerprints. So the three
failures have **three different causes**, and "one systematic coverage gap" — the framing this
investigation started from, mine included — is wrong. Each needs its own capture, fixture and
adversarial pass; none is a one-line fix.

**Honest bar status:** `roguetw.net` reaches `main_command` on NEW **and** RETURNING. The other
three stall at three unrelated screens. **1 of 4.**
