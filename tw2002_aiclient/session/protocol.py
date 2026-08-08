"""JSON verb protocol shared by the daemon's socket server and the CLI
(canon: `canon/architecture/session-engine.md` "The Unix-Socket JSON Verb
Protocol").

Wire format: one line-delimited JSON object per request/response over the
unix-domain socket. Request: `{"verb": "...", "args": {...}}`. Response:
always has `"ok"`; on success carries verb-specific fields, on failure
carries `"error"`.

**WO-P2-020 Wave-3 SUBSET + WO-P2-025 control-lock + WO-P2-OPS-VERB-B** --
ported from `archive/pre-rebirth-2026-07-23/code/twclient/protocol.py`.
Live one-shot verbs: `ensure`, `status`, `screen`, `stop`, `do`, `send`,
`read`, `history`, `state`, `autoloop_start`, `autoloop_stop`,
`autoloop_status`, `explore_start`, `explore_stop`, `explore_status`.
Lifetime `attach` / `subscribe` are handled in
`daemon.py` (not here) — `subscribe` streams WatchHub settle-edge events
(WO-P2-WATCHHUB-PORT). `set_mode`/`crawl_start`/`autopilot_*`/
`record_*`/`replay`/`mine`/`play*`/`haggle`/`list_skills` remain later WOs
-- `dispatch()` returns `unknown_verb` for them, and so do canon's
`autoloop pause`/`resume` (`cli-verbs.md §"App-drive (deterministic macro / loop / pilot playback)"`): both are controls on a
REPEATING loop, and WO-P2-G4-X4 ships one pass (`session/autoloop.py`,
"One pass"). An honest `unknown_verb` beats a verb that accepts a pause
it cannot perform. Drive verbs
(`ensure`/`do`/`send`) ride `_driving_dispatch` (acquire_driver /
release_driver) for refuse-not-queue. Live senders are `{app, human}` only
(never AI).

`build_response()` here is a bounded subset of archive protocol.py:407-470
-- see its own docstring for the exact fields cut and why.
"""

import json
import os
import re
import time
from contextlib import contextmanager

from . import autoloop
from . import sector_explore
from . import stardock_hold
from . import trade_chain
from .. import explore as _explore
from .classify import classify_screen
from .control_lock import (
    MODE_HUMAN,
    MODE_SPECTATE,
    ControlModeConflict,
)
from .hud_seed import seed_hud_after_join
from .hud_tracking import format_cargo_hud_value
from .settle import MATCH_SCOPE_PROMPT_LINE
from .state_parser import (
    OUTCOME_READ,
    REASON_SESSION_DISCONNECTED,
    read_current_sector,
    sector_unreadable,
    sector_wire,
)


def build_response(session, rows=None, settled_reason=None, extra=None):
    """WO-P2-020 Wave-3 CUT vs archive protocol.py:407-470: `state` (the
    archive folded a `parse_state()` dict into every drive answer; the
    reborn read lives on its own `state` verb instead -- see
    `_state_response` -- and is deliberately NOT duplicated onto this
    response, for the same reason `status` stopped duplicating a
    live-paint field onto the structured answer),
    `cursor` (`session.cursor_pos()` -- the attach surface
    that reads it hasn't landed), the `world_identity`/`world_model`
    write hooks, `observe_credits`/`observe_turns`/`observe_fighters`
    (Session methods cut in Wave-2), and the `frame_recorder` post-mortem
    hook are all left off this response until their own work orders land.
    `sent_input` is kept -- it's a plain `Session` attribute (session.py,
    Wave-2), zero extra dependency.

    WO-P4-053: `color` is back, additive, but ONLY on the bare-`rows`
    path -- every caller here except `screen`'s `raw` branch (`do`,
    `send`, `read`, `ensure`, and `watch.py`'s seed-subscribe/settle-edge
    emit) already calls this with no `rows`, so they all pick up `color`
    for free. That bare path takes BOTH rows and color from
    `session.render_with_color()`, which
    captures them under ONE lock acquisition -- see that method's own
    docstring for why calling `render()` and a separate `color_map()`
    read is a RACE (a byte arriving between the two calls shifts the
    content bounding box, producing a color map that no longer lines up
    with the text it's supposed to paint). When the CALLER already
    supplied `rows` (only `screen`'s one-shot `raw` path today), a
    matching color map can no longer be safely derived from that same
    snapshot, so `color` is omitted entirely rather than pairing the
    caller's rows with a color map captured moments later against
    whatever the screen has become since -- honest absence over a
    plausible-but-misaligned map. Do not "fix" this asymmetry by adding
    a second `terminal.color_map()` read on the `rows`-supplied path."""
    color = None
    if rows is None:
        rows, color = session.render_with_color()
    text = session.render_text(rows)
    prompt = rows[-1].strip() if rows else ""
    resp = {
        "ok": True,
        "screen": rows,
        "prompt": prompt,
        "classification": classify_screen(text, prompt),
        "sent_input": getattr(session, "last_sent", None),
    }
    if color is not None:
        resp["color"] = color
    if settled_reason is not None:
        resp["settled_reason"] = settled_reason
    if extra:
        resp.update(extra)
    return resp


def _control_lock_error(server):
    """Fast, non-atomic MODE hint for App driving verbs.

    None when App may claim the driver slot (no lock / mode app with no
    auto_loop hold). Otherwise a typed refuse naming who holds the
    keyboard. Atomic authority is still `acquire_driver()` inside
    `_driving_dispatch` — this is only the common-case early exit.
    """
    lock = getattr(server, "control_lock", None)
    if lock is None:
        return None
    if getattr(lock, "is_auto_loop_held", lambda: False)():
        return {"ok": False, "error": "controller_locked_by_auto_loop"}
    if lock.app_may_send():
        return None
    mode = lock.mode
    if mode == MODE_HUMAN:
        return {"ok": False, "error": "controller_locked_by_human"}
    if mode == MODE_SPECTATE:
        return {"ok": False, "error": "spectate_read_only"}
    return {"ok": False, "error": f"controller_locked:{mode}"}


@contextmanager
def _driving_dispatch(server):
    """Shared ensure/(future do/send) guard: mode hint + acquire_driver.

    Second concurrent App driver → typed refuse (`controller_busy` /
    `controller_locked_by_human` / `spectate_read_only` / …), never
    queued. Bare harness with no `control_lock` stays unrestricted
    (tests). Always release_driver on the way out.
    """
    lock_error = _control_lock_error(server)
    if lock_error is not None:
        yield lock_error
        return
    lock = getattr(server, "control_lock", None)
    if lock is None:
        yield None
        return
    try:
        lock.acquire_driver()
    except ControlModeConflict as e:
        yield {"ok": False, "error": str(e)}
        return
    try:
        yield None
    finally:
        lock.release_driver()


def _status_response(session, server):
    """The `status` verb's answer -- bounded by construction, and deliberately
    NOT a mirror of the receive buffer (canon `DECISIONS.md` §C.2, ruled
    2026-07-26; the leak itself is named in `canon/doctrine/
    secrets-and-credentials.md` Code Divergence #1, "Status-verb wire").

    **The carrier this exists to close.** This branch used to answer with
    `"prompt": rows[-1].strip()` -- the live pyte tail, verbatim
    receive-buffer content. On a server that ECHOES at the password gate (the
    behavior canon's RX-side no-leak guarantee openly rests on never
    happening) that line IS the operator's credential, and it rode every
    `status` round trip: `tw status`, `tw status --json`, and any spectator
    holding the socket. Measured end to end through the real daemon socket and
    the real CLI, not reasoned about:
    `tests/test_status_prompt_redaction.py`. Note there is no
    "human-readable is narrower" carve-out here the way there is for `ensure`'s
    failure answer: a `status` response has no `screen` key, so BOTH branches
    of `cli.print_response` fall through to `json.dumps(resp)` -- every
    `tw status` invocation serialises the whole dict.

    **The split §C.2 asks for is already carried by the VERB, not by the
    field.** `status` is the structured/diagnostic verb -- a spectator parses
    it. The live paint of the telnet stream is `screen` (one-shot),
    `subscribe` (the WatchHub stream behind `watchfeed.py` ->
    `cockpit/viewport.py`), `attach`, and the `do`/`send`/`read` answers --
    every one of them `build_response()`, which is untouched and still mirrors
    the buffer in full. The defect was that `status` DUPLICATED a live-paint
    field onto the structured answer; the fix is to stop duplicating it, not
    to add machinery that disambiguates two consumers of one field. There is
    no second consumer to disambiguate: no cockpit panel reads
    `status["prompt"]` -- `goals`/`focus`/`hud`/`arm`/`stopbanner`/`logsband`
    and `screens.py`'s own status read are pinned byte-identical with and
    without the field by
    `test_no_cockpit_panel_changes_when_the_prompt_field_disappears`, and the
    viewport's rows come from the subscribe event, never from here.
    (`cockpit/control_seat.py` mentions `status["mode"]` in prose but its
    composers take primitives, not the status dict, so it is not a consumer of
    this response at all.)

    **Unconditional, never gated on "does this prompt look secret".**
    `classify.py`'s `login_password` gate anchor is literally
    `re.compile(r"password", re.I)`, and `is_probable_secret_prompt()` is a
    wider word list over the same idea. Both are heuristics, and both fail
    OPEN in exactly the scenario under test: an echoing server REPLACES the
    word "password" on that line with the credential, so the recogniser
    answers `unknown` and a recognition-gated redactor would hand the secret
    straight through. Redaction that depends on recognition is redaction that
    stops the day recognition does -- the same argument
    `_login_failure_response` makes, and the reason this function relies on no
    heuristic at all.

    **Why omit rather than mask.** Masking would need the plaintext at this
    layer, and this layer deliberately does not have it (`session.last_sent` is
    already `"<redacted>"` for a `secret=True` send; the credential lives only
    inside `run_login`'s frame). It would also be fail-OPEN even then: pyte
    wraps at the column boundary, an echo can be partially overwritten, and the
    grid may hold a SIBLING profile's secret or one the human typed into an
    earlier attach -- content this process never held a copy of to match
    against. A mask that misses ships the credential wearing a redacted look.

    **What it still carries, and why each is bounded.** `classification` is
    `classify.classify_screen`'s CLOSED vocabulary -- a label from the anchor
    tables or `unknown`, never a slice of the screen -- so an operator still
    learns WHICH screen the session is sitting on, which is the diagnostic
    `prompt` was mostly serving. `connected`/`idle_ms`/`subscribers`/`port` are
    scalars; `host`/`port`/`name` come from the PROFILE, not the receive
    buffer; `autopilot` is one bool, and `intervention` (WO-P2-G4-X4) is one
    bool plus a code drawn from `loops/player.py`'s closed halt vocabulary --
    `session/autoloop.py` states why nothing derived from the receive buffer,
    from a macro's recorded keystrokes, or from server-side paths can reach
    either; `mode` is the control lock's own closed
    vocabulary. `replay_arm` (WO-STATUS-EXPOSE-REPLAY-ARM) is always present:
    `armed` plus profile name + reconnect `(host, port)` when stamped, or an
    explicit disarmed shape when `auto_login_profile` is unset -- never a
    missing key that could read as safe; profile name is that field itself,
    never a password. `log_tail` is the one remaining screen-adjacent field and it is
    safe for a structural reason rather than a filtering one: `transcript_tail.
    TranscriptTail` is TX-only and redact-at-INSERT -- `append_redacted()`
    cannot accept a payload at all -- so no receive-side byte can enter that
    ring. Do not add an RX feed to it without re-opening this ruling.

    No length, shape, or character-class digest of the prompt line is offered
    in its place: doctrine invariant 2 counts a length as a leak in its own
    right, and `login.LoginStalled` already refused exactly that digest.
    `prompt_withheld` is honest absence rather than a silently missing key -- a
    consumer can tell "withheld here" from "this daemon never had one" -- and
    the key is omitted rather than set to a marker STRING so a caller doing
    `resp["prompt"]` fails loudly instead of formatting `"<withheld>"` into a
    plausible-looking line. A consumer that genuinely needs the live line asks
    the verb whose job it is: `screen`, or `subscribe`.

    **Forward note (the archive's real consumer) -- now answered.** `adapters.
    sector_from_status()` in the pre-rebirth tree derived the current SECTOR by
    re-parsing `status["prompt"]` (`Command [TL=...]:[2642]`) client-side; this
    docstring required that the number instead arrive as a bounded daemon-side
    derivation, never by shipping the raw prompt line for a client to re-parse.
    WO-P2-G4-X1 landed it: `_state_response` below answers the `state` verb
    with `state_parser.sector_wire()`, whose every value is an int or a member
    of that module's closed vocabularies. `status` is unchanged and grew no
    sector field -- a spectator wanting the sector asks the verb whose job it
    is, exactly as it does for the live line.
    """
    # WO-P2-020 Wave-3 CUT vs archive: play/credits*/turns*/
    # fighters*/world_id still deferred. Mode + arm state + intervention +
    # subscribers (WatchHub) are live enough for cockpit status.
    rows = session.render()
    text = session.render_text(rows)
    # WO-P2-G4-X5: the HUMAN-driven half of credits supervision -- where a
    # balance the operator saw while flying by hand becomes the arm-confirm
    # precondition a later floored run needs ("the arm sequence must have
    # shown a confirmed balance before a floored run will start"). The
    # App-driven half is `autoloop._ReplayPort.screen()`; both feed the same
    # sticky pair, and neither decides anything -- capture only.
    #
    # This comment used to read "every `do`/`read`/`screen`/`status` answer
    # passes through here" (WO-HUD-STATUS-BRIDGE corrected it). It does not:
    # this is `_status_response`, and `dispatch` routes ONLY the `status`
    # verb here -- `do`/`read`/`screen` answer through `build_response`,
    # which has no observation site at all. So `status` is not one of four
    # observers, it is the ONLY one, and a session driven purely by
    # `do`/`send` would never fill the sticky pair from this side.
    #
    # That is why the two stores added below sit HERE rather than in
    # `build_response`: this verb is the one the Play HUD polls, and putting
    # the HUD's producers anywhere else would leave the bridge wired to a
    # source nothing fills.
    #
    # `callable`-guarded like `session.tail` below, for the same bare test
    # harnesses; a session that cannot observe leaves the balance `absent`,
    # which is a HALT on any floored run rather than a shrug.
    observe_credits = getattr(session, "observe_credits", None)
    if callable(observe_credits):
        observe_credits(text)
    # Local only, and used ONLY to scope `classify_screen`'s gate anchors to
    # the current prompt line (classify.py's stale-scrollback discipline).
    # It is deliberately not a key below -- see this function's docstring.
    prompt_line = rows[-1].strip() if rows else ""
    # WO-HUD-STATUS-BRIDGE: the turns counterpart, sited AFTER `prompt_line`
    # because it is the one observer that reads both halves of the screen --
    # the prompt-line `TL=` count and, when that says nothing, the body
    # statement. Which of the two wins is `Session.observe_turns`'s call,
    # not this call site's.
    observe_turns = getattr(session, "observe_turns", None)
    if callable(observe_turns):
        observe_turns(text, prompt_line)
    observe_cargo = getattr(session, "observe_cargo", None)
    if callable(observe_cargo):
        observe_cargo(text)
    observe_holdings = getattr(session, "observe_holdings", None)
    if callable(observe_holdings):
        observe_holdings(text)
    # WO-STATUS-FIGHTERS-ABOARD: same cadence as credits/cargo — status is
    # the wire that observes, not only the wire that reports.
    observe_fighters = getattr(session, "observe_fighters", None)
    if callable(observe_fighters):
        observe_fighters(text)
    observe_current_ship = getattr(session, "observe_current_ship", None)
    if callable(observe_current_ship):
        observe_current_ship(text)
    observe_sector = getattr(session, "observe_sector", None)
    if callable(observe_sector):
        observe_sector(prompt_line)
    watch_hub = getattr(server, "watch_hub", None)
    lock = getattr(server, "control_lock", None)
    # WO-P2-G4-X4: ONE observation of the arm state, feeding BOTH fields
    # below. `autopilot.running` used to be the hardcoded literal
    # `{"running": False}` ("autopilot.py is not ported — ensure never
    # arms"), which was true then and would be a fabricated safety claim
    # now that `session/autoloop.py` can genuinely arm. Taken as a single
    # snapshot rather than two reads because the arm chip and the STOP
    # banner would otherwise be able to describe two different instants --
    # see `autoloop.observe`.
    arm = autoloop.observe(getattr(server, "autoloop", None), lock)
    trade_runner = _trade_chain_runner(server)
    trade = (
        trade_runner.snapshot()
        if trade_runner is not None
        else trade_chain.TradeSnapshot(running=False)
    )
    # WO-STATUS-EXPOSE-REPLAY-ARM: always-present arm report so a missing key
    # cannot read as "safe / disarmed". Profile name is `session.auto_login_profile`
    # itself (same field `guardian._maybe_reconnect` reads) — never re-derived.
    # When armed, host/port are the reconnect TCP target (`session.reconnect()`
    # uses the session endpoint, not a second profile lookup).
    profile_name = getattr(session, "auto_login_profile", None)
    if profile_name:
        replay_arm = {
            "armed": True,
            "profile": profile_name,
            "host": session.host,
            "port": session.port,
        }
    else:
        replay_arm = {
            "armed": False,
            "profile": None,
            "host": None,
            "port": None,
        }
    resp = {
        "ok": True,
        "connected": session.conn.connected,
        "idle_ms": int((time.monotonic() - session.last_rx) * 1000),
        "classification": classify_screen(text, prompt_line),
        "prompt_withheld": "structured_mirror",
        "host": session.host,
        "port": session.port,
        "name": session.name,
        # The global status surface stays deliberately bounded; detailed
        # route/fingerprint progress is available only from the dedicated
        # trade_chain_status verb.
        "autopilot": {"running": bool(arm.running or trade.running)},
        "subscribers": watch_hub.subscriber_count() if watch_hub else 0,
        "replay_arm": replay_arm,
    }
    # Omitted entirely when there is no halt to report (see
    # `autoloop.intervention_block`), so a daemon that has never run a
    # loop answers exactly as it did before this field existed.
    intervention = autoloop.intervention_block(arm)
    if intervention is None:
        intervention = trade_chain.intervention_block(trade)
    # WO-FIX-SESSIONGUARDIAN-EXHAUSTED-RECONNECT-SILENT: sticky D9 exhaust
    # surfaces the same STOP-banner wire. Merge reasons when a loop halt
    # is already present — reconnect failure is not quieter than a halt.
    guardian = getattr(server, "guardian", None)
    if guardian is not None and getattr(guardian, "reconnect_exhausted", False):
        g_reason = {"code": "reconnect_exhausted"}
        if intervention is None:
            intervention = {"needs_attention": True, "reasons": [g_reason]}
        else:
            existing = intervention.get("reasons") or []
            codes = {
                (r.get("code") if isinstance(r, dict) else r) for r in existing
            }
            if "reconnect_exhausted" not in codes:
                intervention = {
                    "needs_attention": True,
                    "reasons": list(existing) + [g_reason],
                }
    if intervention is not None:
        resp["intervention"] = intervention
    if lock is not None:
        mode = getattr(lock, "mode", None)
        if isinstance(mode, str):
            resp["mode"] = mode
    # WO-P3-041: additive -- session.tail (transcript_tail.py) is
    # always present on a real Session; getattr guards test doubles
    # that predate this field (e.g. tests/test_watch.py's FakeSession)
    # so this stays additive-only, never a new hard dependency.
    tail = getattr(session, "tail", None)
    resp["log_tail"] = tail.snapshot() if tail is not None else []
    # WO-HUD-STATUS-BRIDGE: the always-on Play HUD's five tracked vitals.
    # Always present, exactly like `replay_arm` above and for the same
    # reason -- a missing key must not be the way "nothing is known" is
    # expressed, because the composer already has an honest unknown cell and
    # a silent key is indistinguishable from a bridge that broke.
    resp["hud"] = _hud_payload(session)
    # The GOALS Turns row reads a TOP-LEVEL `turns_left`, not the HUD cell
    # (`cockpit/goals.py`: `_safe_int(status.get("turns_left"))`). Emitted
    # only on a genuine reading and OMITTED otherwise, never set to `None`:
    # "no key" and `None` already mean the same thing to `_safe_int`, and an
    # explicit null would be this response's one field asserting a value it
    # does not have. Same omit-don't-null rule `sector_wire` states for its
    # own fields, and the reason a forged `0` is unreachable from here --
    # there is no branch that can write this key without a `read` outcome.
    turns = _turns_snapshot(session)
    if turns is not None and turns.outcome == OUTCOME_READ:
        resp["turns_left"] = turns.turns
    # WO-STATUS-FIGHTERS-ABOARD: GOALS Fighters + coach at_shipyard read the
    # TOP-LEVEL key. Emit only on a genuine sticky reading; omit otherwise
    # (never invent 0 from absence — that would falsely fire at_shipyard).
    fighters = _fighters_snapshot(session)
    if fighters is not None and fighters.outcome == OUTCOME_READ:
        resp["fighters_aboard"] = fighters.fighters
    # WO-BUILD-LIVE-SHIP-INTROSPECTION-ADAPTER: priority-engine row 2.
    # Emit only after a genuine I-info type read; omit otherwise (never invent).
    current_ship_snap = getattr(session, "current_ship_snapshot", None)
    if callable(current_ship_snap):
        ship = current_ship_snap()
        if isinstance(ship, dict) and isinstance(ship.get("ship_type"), str):
            payload = {
                k: ship[k]
                for k in (
                    "ship_type",
                    "ship_name",
                    "turns_per_warp",
                    "total_holds",
                    "empty_holds",
                    "fighters",
                    "source",
                    "age_s",
                )
                if k in ship
            }
            resp["current_ship"] = payload
            resp["ship_type"] = ship["ship_type"]
    # WO-STATUS-CREDITS: GOALS Credits reads TOP-LEVEL `credits`, distinct
    # from `hud.credits` (same sticky). Emit only on OUTCOME_READ; omit
    # otherwise (never invent 0 from absence — GOALS must stay `?`).
    credits = _credits_snapshot(session)
    if credits is not None and credits.outcome == OUTCOME_READ:
        resp["credits"] = credits.balance
    # WO-COACH-EXPLORE-MODE: coach exploring_frontier reads TOP-LEVEL
    # `explore_mode` (= run intent). Reuse explore_run_wire truth; emit only
    # while running with a report; omit when idle / unavailable (never invent
    # a fake mode).
    explore_wire = sector_explore.explore_run_wire(
        sector_explore.observe_explore(_explore_runner(server), lock)
    )
    run = explore_wire.get("run")
    if explore_wire.get("running") and isinstance(run, dict):
        intent = run.get("intent")
        if isinstance(intent, str) and intent:
            resp["explore_mode"] = intent
    return resp


def _state_response(session):
    """The `state` verb's answer: parsed structured game-state, read-only
    (`canon/architecture/cli-verbs.md §"Session primitives"`).

    Today that is exactly one field -- the ship's current sector, the
    precondition `canon/engine/macros.md` requires every macro replay to
    re-check "before pressing anything". Credits / turns / warps / port are
    NOT here: each needs its own provenance argument (the archive's `TL=`
    field alone carried a live defect where an `HH:MM:SS` countdown was read
    as a turn count and silently reported `turns_left=0`), and shipping five
    fields at one field's depth is how a best-effort read becomes a
    believed one. The `state` envelope is where they land when their own WOs
    do.

    **Three outcomes reach the wire, never two.** `state_parser` returns a
    verdict, not a number-or-None, and `sector_wire()` keeps the three apart
    on the wire by nesting: `state["sector"]` is an OBJECT with an
    `outcome`, and the `sector` key inside it exists only on `read`. An
    archive-shaped client doing `state["sector"]` gets a dict where it
    expected an int and fails -- and failing is the safe direction for a
    value that gates every send, since a start-anchor comparison against a
    dict cannot accidentally succeed.

    **A dead socket is `unreadable`, never a number.** With the connection
    down, pyte still holds the last frame the server painted, prompt bracket
    and all -- so the text-level read would happily resolve a sector that
    describes where the ship WAS. That is the one failure direction canon
    forbids outright (`macros.md`: the start-anchor halt "is **not**
    bypassable by force -- forcing past a *detected* mismatch is the danger
    itself"), because a stale-but-matching sector is worse than no sector:
    it satisfies the guard. `_dispatch_ensure` already refuses to classify
    across the same hazard in its own words ("a stale pyte buffer would
    misclassify a frozen last-seen frame as 'current'"); this is that rule
    applied to the sector. It is checked BEFORE the render, so no number is
    derived and then discarded.

    **Read-only: no `_driving_dispatch`, no send.** `state` acquires no
    driver slot, for the same reason `read`/`history`/`status` do not -- it
    puts nothing on the wire, so it cannot conflict with whoever holds the
    keyboard, and a spectator must be able to poll it. Making a read verb
    take the control lock would also mean a poll could be refused with
    `controller_locked_by_human`, turning "the human is playing" into
    "unreadable", which is a fourth outcome nobody asked for.

    **Settling is the caller's, not this verb's.** `state` is the
    cheap-polling verb (the archive says so outright) and does not wait: it
    reports what is on the grid right now. Canon puts screen understanding
    downstream of settle detection, so a caller that needs a settled read
    settles first (`read`, or `do`'s own wait) and then polls here. The
    honest consequence is that a poll landing mid-paint sees a half-written
    prompt -- which is `unreadable/damaged_command_prompt`, not a guess and
    not a silent absence.

    One `render()`, threaded into `render_text()` -- calling `render()` and
    then `render_text()` with no rows would be two independent lock
    acquisitions with a byte able to arrive between them, the same race
    `session.render_with_color()`'s docstring documents for text+color.
    `classification` rides along because it is `classify_screen`'s CLOSED
    vocabulary (the same bounded diagnostic `_status_response` and
    `_login_failure_response` both keep) and because it is what lets a
    consumer tell the CLASSIC-server case apart from any other `absent`:
    `main_command` + `absent` is "a command prompt that states no sector".
    The live prompt line itself is NOT a key here -- see `_status_response`.
    """
    if not session.conn.connected:
        return {
            "ok": True,
            "state": {"sector": sector_wire(sector_unreadable(REASON_SESSION_DISCONNECTED))},
            "connected": False,
        }
    rows = session.render()
    text = session.render_text(rows)
    prompt_line = rows[-1].strip() if rows else ""
    sector_read = read_current_sector(prompt_line)
    if sector_read.outcome == OUTCOME_READ and sector_read.sector is not None:
        # WO-LAST-KNOWN-SECTOR: remember a sector the screen POSITIVELY
        # stated, so a later screen that identifies itself WITHOUT carrying
        # one (every captured StarDock screen) has something to attribute a
        # per-sector fact to. Recorded only on a genuine read -- an `absent`
        # or `unreadable` outcome leaves the previous memory alone rather
        # than overwriting it with a guess, and the send-epoch stamped here
        # is what stops that memory outliving the next keystroke.
        # Duck-typed via `getattr`, matching this codebase's existing idiom
        # for optional session capabilities (`sector_explore` does the same
        # for `should_abort`/`is_driver_fenced`) -- `build_response` is handed
        # scripted stand-ins by dozens of tests, and a daemon that crashed on
        # one lacking a recording hook would be trading a real outage for a
        # bookkeeping nicety.
        #
        # The obvious objection to `getattr` is that a real `Session` which
        # LOST the method would then degrade silently, which is exactly the
        # failure this memory must not have. That is closed on the other side
        # instead: `tests/test_last_known_sector.py` asserts the contract
        # against the real `Session` class directly, so the duck-typing here
        # can only ever excuse a test double, never a regression.
        note = getattr(session, "note_sector", None)
        if callable(note):
            note(int(sector_read.sector))
    return {
        "ok": True,
        "state": {"sector": sector_wire(sector_read)},
        "classification": classify_screen(text, prompt_line),
        "connected": True,
    }


def _turns_snapshot(session):
    """The session's turn-count snapshot, or `None` for a stand-in that has
    no such store. `callable`-guarded for the same reason every other
    optional session capability on this path is: `build_response` and its
    neighbours are handed scripted doubles by dozens of tests, and a daemon
    that crashed on one lacking a HUD store would trade a real outage for a
    display nicety. The real `Session` is pinned on the other side, against
    the class itself, so this can only ever excuse a double."""
    snapshot = getattr(session, "turns_snapshot", None)
    return snapshot() if callable(snapshot) else None


def _fighters_snapshot(session):
    """The session's fighters-aboard sticky, or `None` for a stand-in."""
    snapshot = getattr(session, "fighters_snapshot", None)
    return snapshot() if callable(snapshot) else None


def _credits_snapshot(session):
    """The session's credits sticky, or `None` for a stand-in."""
    snapshot = getattr(session, "credits_snapshot", None)
    return snapshot() if callable(snapshot) else None


def _hud_cell(value, age_s):
    """One HUD cell in the shape `cockpit/hud.py` documents.

    Always both keys, always present. The composer treats a missing key, a
    `None` value and a non-dict identically (it paints `UNKNOWN_VALUE`), so
    emitting the pair unconditionally costs nothing and keeps every cell the
    same shape for anything that reads this payload without the composer.
    """
    return {"value": value, "age_s": age_s}


def _hud_payload(session):
    """`status["hud"]` -- the five tracked vitals, ages computed daemon-side.

    Canon-authored field order (`cockpit/hud.py`). Ages arrive already
    subtracted, as SECONDS: the composer is a pure function of an
    already-computed `(value, age_s)` pair and "never a clock or event
    source", so shipping a timestamp here would put the subtraction on the
    far side of a process boundary where a second clock could creep in.

    Nothing here can raise on a session that predates these stores: each
    snapshot is fetched through a `callable` guard, and an absent store is
    reported as an unknown cell -- the same answer the operator would get
    from a store that simply had not seen anything yet.
    """
    credits_snapshot = getattr(session, "credits_snapshot", None)
    credits = credits_snapshot() if callable(credits_snapshot) else None
    sector_snapshot = getattr(session, "sector_snapshot", None)
    sector = sector_snapshot() if callable(sector_snapshot) else None
    turns = _turns_snapshot(session)
    cargo_snapshot = getattr(session, "cargo_snapshot", None)
    cargo = cargo_snapshot() if callable(cargo_snapshot) else None
    profit_snapshot = getattr(session, "profit_snapshot", None)
    profit = profit_snapshot() if callable(profit_snapshot) else None

    def cell(snapshot, attr):
        if snapshot is None or snapshot.outcome != OUTCOME_READ:
            return _hud_cell(None, None)
        return _hud_cell(getattr(snapshot, attr), snapshot.age_s)

    def cargo_cell(snapshot):
        if snapshot is None or snapshot.outcome != OUTCOME_READ:
            return _hud_cell(None, None)
        # Display honesty: empty/total (or "N empty" when total unknown).
        # Empty int remains on CargoSnapshot.cargo for seed / non-HUD readers.
        return _hud_cell(
            format_cargo_hud_value(
                snapshot.cargo,
                snapshot.total_holds,
                getattr(snapshot, "holdings", None),
            ),
            snapshot.age_s,
        )

    return {
        "credits": cell(credits, "balance"),
        "sector": cell(sector, "sector"),
        "turns": cell(turns, "turns"),
        "cargo": cargo_cell(cargo),
        "profit": cell(profit, "profit"),
    }


def _explore_runner(server):
    return getattr(server, "sector_explore", None)


def _dispatch_explore_start(args, server):
    runner = _explore_runner(server)
    if runner is None:
        return {"ok": False, "error": "explore_unavailable"}
    unsupported = sorted(set(args) - sector_explore.ARGS_EXPLORE_START)
    if unsupported:
        return {"ok": False, "error": f"unsupported_arg:{unsupported[0]}"}
    world_id = args.get("world_id")
    min_sectors = args.get("min_sectors", sector_explore.DEFAULT_MIN_DISTINCT_SECTORS)
    turn_budget = args.get("turn_budget", sector_explore.DEFAULT_TURN_BUDGET)
    # WO-EXPLORE-AUTOMATION-GATE E3. Omitting `intent` keeps the pre-WO
    # behaviour exactly (map-fill), so every existing caller is unchanged;
    # an unknown value is refused by `runner.start` as `invalid_intent`
    # rather than defaulted, because a run that silently pursues a different
    # goal than the one confirmed is the failure this gate exists to prevent.
    intent = args.get("intent", _explore.INTENT_MAP_FILL)
    # WO-EXPLORE-DOCK-NEW-PORT: absent means False, matching the library
    # default. This is the only explore arg whose omission decides whether the
    # run may SPEND turns, so it is read the same way `intent` is -- taken
    # literally and refused by `runner.start` if it is not a bool, never
    # coerced (`"no"` is truthy).
    dock_new_ports = args.get("dock_new_ports", False)
    # WO-FIGHTER-TOLL-POLICY-WIRE: read exactly like `dock_new_ports` and for
    # a sharper version of the same reason -- omission must mean DISARMED, and
    # a non-bool must reach `runner.start` intact so it is refused there rather
    # than coerced into an armed run.
    fight_tolls = args.get("fight_tolls", False)
    try:
        snapshot = runner.start(
            world_id,
            min_sectors=min_sectors,
            turn_budget=turn_budget,
            intent=intent,
            dock_new_ports=dock_new_ports,
            fight_tolls=fight_tolls,
        )
    except sector_explore.ExploreRefused as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "started": True, **sector_explore.explore_run_wire(snapshot)}


def _dispatch_explore_stop(server):
    runner = _explore_runner(server)
    if runner is None:
        return {"ok": False, "error": "explore_unavailable"}
    snapshot = runner.stop()
    return {"ok": True, "stopping": True, **sector_explore.explore_run_wire(snapshot)}


def _dispatch_explore_status(server):
    runner = _explore_runner(server)
    lock = getattr(server, "control_lock", None)
    return {"ok": True, **sector_explore.explore_run_wire(sector_explore.observe_explore(runner, lock))}


def _trade_chain_runner(server):
    return getattr(server, "trade_chain", None)


def _dispatch_trade_chain_start(args, server):
    runner = _trade_chain_runner(server)
    if runner is None:
        return {"ok": False, "error": "trade_chain_unavailable"}
    unsupported = sorted(set(args) - trade_chain.ARGS_TRADE_CHAIN_START)
    if unsupported:
        return {"ok": False, "error": f"unsupported_arg:{unsupported[0]}"}
    kwargs = {}
    if "cash_floor" in args:
        kwargs["cash_floor"] = args["cash_floor"]
    if "turn_reserve" in args:
        kwargs["turn_reserve"] = args["turn_reserve"]
    if "profit_target" in args:
        kwargs["profit_target"] = args["profit_target"]
    try:
        snapshot = runner.start(
            args.get("world_id"),
            args.get("fingerprint"),
            **kwargs,
        )
    except trade_chain.TradeChainRefused as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "started": True, **trade_chain.run_wire(snapshot)}


def _dispatch_trade_chain_stop(server):
    runner = _trade_chain_runner(server)
    if runner is None:
        return {"ok": False, "error": "trade_chain_unavailable"}
    return {
        "ok": True,
        "stopping": True,
        **trade_chain.run_wire(runner.stop()),
    }


def _dispatch_trade_chain_status(server):
    runner = _trade_chain_runner(server)
    if runner is None:
        return {"ok": False, "error": "trade_chain_unavailable"}
    return {"ok": True, **trade_chain.run_wire(runner.snapshot())}


def _stardock_hold_runner(server):
    return getattr(server, "stardock_hold", None)


def _dispatch_stardock_hold_start(args, server):
    runner = _stardock_hold_runner(server)
    if runner is None:
        return {"ok": False, "error": "stardock_hold_unavailable"}
    unsupported = sorted(set(args) - stardock_hold.ARGS_STARDOCK_HOLD_START)
    if unsupported:
        return {"ok": False, "error": f"unsupported_arg:{unsupported[0]}"}
    kwargs = {}
    for key in (
        "stardock_sector",
        "empty_holds",
        "hold_price",
        "credits",
        "qty",
        "cash_floor",
    ):
        if key in args:
            kwargs[key] = args[key]
    try:
        snapshot = runner.start(
            args.get("world_id"),
            args.get("fingerprint"),
            **kwargs,
        )
    except stardock_hold.StardockHoldRefused as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "started": True, **stardock_hold.run_wire(snapshot)}


def _dispatch_stardock_hold_stop(server):
    runner = _stardock_hold_runner(server)
    if runner is None:
        return {"ok": False, "error": "stardock_hold_unavailable"}
    return {
        "ok": True,
        "stopping": True,
        **stardock_hold.run_wire(runner.stop()),
    }


def _dispatch_stardock_hold_status(server):
    runner = _stardock_hold_runner(server)
    if runner is None:
        return {"ok": False, "error": "stardock_hold_unavailable"}
    return {"ok": True, **stardock_hold.run_wire(runner.snapshot())}


def _autoloop_runner(server):
    """The daemon's background player, or ``None``.

    `getattr` for the same reason `watch_hub` / `control_lock` are read
    that way: a bare unit-test harness builds the server by hand. A verb
    that needs one answers `autoloop_unavailable` rather than pretending
    a daemon without a player can arm."""
    return getattr(server, "autoloop", None)


def _dispatch_autoloop_start(args, server):
    """WO-P2-G4-X4 + WO-AUTOLOOP-CYCLES: arm the background player for N
    passes of one taught macro (default 1). Returns as soon as the run is
    live (canon `cli-verbs.md`: "`start` returns immediately").

    **Unsupported args are REFUSED, not ignored** (`autoloop.
    ARGS_AUTOLOOP_START`). `force` stays refused: it waives a MISSING
    start-anchor, canon allows only an explicit human waiver, and a socket
    verb cannot confirm a human is behind it -- a daemon granting itself
    that waiver is the self-arming canon forbids. `param` stays refused
    for the same honesty reason.

    **`cycles` is ACCEPTED and clamped** (WO-AUTOLOOP-CYCLES) to
    `CYCLES_HARD_CEILING` because all four rails are built. Bool / float /
    ≤0 → `invalid_cycles`. Over-ceiling → clamp, never unbounded.

    **`floor` is ACCEPTED, and only because it is ENFORCED**
    (WO-P2-G4-X5). **`turn_budget` is ACCEPTED for the same reason**
    (WO-AUTOLOOP-TURN-BUDGET): a budgeted run observes turns off every
    settled render, re-checks before every send, and halts fail-closed
    (`turns_unknown` / `turns_stale` / `turns_unreadable` /
    `turn_budget_exhausted`) when it cannot. Validation here is narrow and
    refuses rather than coerces (bool/float/negative). `runner.start` then
    makes the final refusal -- `floor_unsupported` /
    `turn_budget_unsupported` -- if the daemon's own session cannot observe
    the required quantity.

    Contrast `ensure`'s `no_auto_arm`, which is accepted and unused: the
    behaviour it asks for is exactly what happens, so accepting it lies
    about nothing.
    """
    runner = _autoloop_runner(server)
    if runner is None:
        return {"ok": False, "error": "autoloop_unavailable"}
    # `profit_target` is ACCEPTED for the same reason as `floor` and
    # `turn_budget` (WO-BUILD-PROFIT-TARGET-HALT): a targeted run observes
    # profit off every settled render, re-checks before every send, and
    # halts fail-closed when it cannot. `runner.start` makes the final
    # refusal (`profit_target_unsupported`) if the session cannot observe.
    unsupported = sorted(set(args) - autoloop.ARGS_AUTOLOOP_START)
    if unsupported:
        return {"ok": False, "error": f"unsupported_arg:{unsupported[0]}"}
    name = args.get("name")
    if not isinstance(name, str) or not name.strip():
        return {"ok": False, "error": "missing_name"}
    floor = args.get("floor")
    if floor is not None and (isinstance(floor, bool) or not isinstance(floor, int)):
        # Checked here as well as in `runner.start` because JSON is where
        # the wrong type actually arrives: a client sending `"floor": true`
        # or `"floor": 500.0` gets a named refusal instead of a run armed
        # with something that is not the number it meant.
        return {"ok": False, "error": "invalid_floor"}
    turn_budget = args.get("turn_budget")
    if turn_budget is not None and (
        isinstance(turn_budget, bool) or not isinstance(turn_budget, int)
    ):
        return {"ok": False, "error": "invalid_turn_budget"}
    profit_target = args.get("profit_target")
    if profit_target is not None and (
        isinstance(profit_target, bool) or not isinstance(profit_target, int)
    ):
        return {"ok": False, "error": "invalid_profit_target"}
    cycles = args.get("cycles")
    if cycles is not None and (isinstance(cycles, bool) or not isinstance(cycles, int)):
        return {"ok": False, "error": "invalid_cycles"}
    try:
        snapshot = runner.start(
            name,
            floor=floor,
            turn_budget=turn_budget,
            profit_target=profit_target,
            cycles=cycles,
        )
    except autoloop.AutoLoopRefused as e:
        # Typed code, already in the runner's / control lock's / loader's
        # own vocabulary -- never re-spelled here.
        return {"ok": False, "error": str(e)}
    return {"ok": True, "started": True, **autoloop.run_wire(snapshot)}


def _dispatch_autoloop_stop(server):
    """Stand the run down. Idempotent, and never refuses.

    The player's arm predicate is what actually stops the run -- within
    one send-step, with an `operator_stop` halt of its own rather than
    somebody else's reason code. This verb does not touch the control
    lock: the run releases its own hold as it dies (`autoloop.py`, "One
    release path"), so a stop cannot drop the App's exclusivity out from
    under a step still in flight.
    """
    runner = _autoloop_runner(server)
    if runner is None:
        return {"ok": False, "error": "autoloop_unavailable"}
    snapshot = runner.stop()
    return {"ok": True, "stopping": True, **autoloop.run_wire(snapshot)}


def _dispatch_autoloop_pause(server):
    """Park the run and hand the keyboard back. Idempotent; never refuses.

    Mechanically the same stand-down as `autoloop_stop` — the difference is
    the recorded intent, which is what lets `autoloop_resume` know there is
    something to resume and what the operator sees. See
    `autoloop.AutoLoopRunner.pause` for why a pause cannot be a parked
    thread under the one-release-path invariant.
    """
    runner = _autoloop_runner(server)
    if runner is None:
        return {"ok": False, "error": "autoloop_unavailable"}
    snapshot = runner.pause()
    return {"ok": True, "paused": True, **autoloop.run_wire(snapshot)}


def _dispatch_autoloop_relaunch(server):
    """Re-arm a paused run from the START of its macro. **Not a resume.**

    Named `relaunch` on a hub ruling (2026-07-27, options 1+3) because
    `resume` was a lie: `replay_loop` takes no start index, so this replays
    the macro from step 1 and **re-issues sends already made**. On a trade
    macro that is live turns and credits spent twice — the class the
    confirm gate exists for (the -75/-78-turn scars). A confirm gate cannot
    fix a prompt whose verb says the wrong thing, so the verb changed.

    `tests/test_autoloop.py` anticipated this before it was built: "an
    honest `unknown_verb` beats a verb that accepts a pause it cannot
    perform — **and beats one that silently completes the run instead**."

    **Disclosure is part of the contract, not a courtesy.** The response
    carries `replays_from_start: True` and `sends_already_issued: <n>` from
    the paused report, so the cockpit's confirm gate can state what the
    operator is about to repeat. A caller that renders neither is
    misreporting a money path; `sends_already_issued` is `None` when the
    player never gave a count, which is NOT the same claim as zero and must
    not be rendered as "0 sends".

    Refuses honestly instead of guessing:

    * no runner            -> ``autoloop_unavailable``
    * nothing was paused   -> ``not_paused`` (a stop is not relaunchable;
      only a deliberate pause is, so this cannot silently restart a run the
      operator panicked)
    * no macro name        -> ``no_resumable_run``

    Re-acquiring the seat can fail — someone else may hold it now — and
    that surfaces as `start`'s own refusal rather than a new failure mode
    invented here.

    A resume is a fresh `start`, not a thaw: the macro replays from its
    beginning. The name, floor, turn_budget, and cycles come off the last
    report (`loop`/`floor`/`turn_budget`/`cycles` — exactly `start`'s
    arguments), so the
    operator does not retype them, but nothing about mid-macro position is
    restored and this docstring says so rather than letting the verb name
    imply otherwise.

    Refuses honestly instead of guessing:

    * no runner            -> ``autoloop_unavailable``
    * nothing was paused   -> ``not_paused`` (a stop is not resumable; only
      a deliberate pause is, so a resume after a panic does not silently
      relaunch a run the operator halted on purpose)
    * no macro name        -> ``no_resumable_run``

    Re-acquiring the seat can fail — someone else may hold it now — and
    that surfaces as `start`'s own refusal rather than a new failure mode
    invented here.
    """
    runner = _autoloop_runner(server)
    if runner is None:
        return {"ok": False, "error": "autoloop_unavailable"}
    snapshot = runner.snapshot()
    if snapshot.stand_down != autoloop.STAND_DOWN_PAUSE:
        # Deliberately strict: resuming a run the operator PANICKED is not
        # a convenience, it is relaunching something they halted. Only a
        # pause is resumable.
        return {"ok": False, "error": "not_paused"}
    report = snapshot.report
    name = getattr(report, "loop", None)
    if not name:
        return {"ok": False, "error": "no_resumable_run"}
    # Captured BEFORE the re-arm: `start()` publishes a fresh report, so
    # reading the count afterwards would report the new run's zero sends
    # instead of what the operator is about to repeat.
    sends_already_issued = getattr(report, "sends_issued", None)
    relaunched = runner.start(
        name,
        floor=getattr(report, "floor", None),
        turn_budget=getattr(report, "turn_budget", None),
        cycles=getattr(report, "cycles", None),
    )
    return {
        "ok": True,
        "relaunched": True,
        "replays_from_start": True,
        "sends_already_issued": sends_already_issued,
        **autoloop.run_wire(relaunched),
    }


def _dispatch_autoloop_status(server):
    """The run report: read-only, no driver slot, no send.

    Same reasoning as `state`/`read`/`history` -- it puts nothing on the
    wire, so it cannot conflict with whoever holds the keyboard, and a
    spectator must be able to poll it while the human plays. Making it
    take the control lock would let "the human is playing" come back as
    a refusal to answer.

    Kept OFF the `status` verb rather than folded into it (§C.2.1's split
    by consumer): `status["autopilot"]` is the arm chip's source and
    `status["intervention"]` is the STOP banner's, each one field with
    one job. The whole run record -- outcome, `sends_issued`, timestamps
    -- is a third consumer's question and gets its own verb.
    """
    runner = _autoloop_runner(server)
    lock = getattr(server, "control_lock", None)
    return {"ok": True, **autoloop.run_wire(autoloop.observe(runner, lock))}


def _dispatch_reflex(session, server):
    """The `reflex` verb -- what the taught rule library proposes for the
    screen on the glass right now. **A proposal, never an act.**

    Read-only in the strongest sense: it sends nothing, arms nothing, and
    takes no control lock. `NEVER_AUTO_ACTION_CLASSES` is still refused
    unconditionally at every `replay_loop` boundary, and a `Loop` carries no
    approval field, so a macro named here is subject to exactly the same
    refusals it was before this verb existed (see `rules/reflex.py`'s two
    inert landings). Arming remains the human's `y` at arm-confirm.

    **Its own verb, not a `status` field**, for the reason §C.2.1 gives about
    that split -- `status` is polled about once a second by the cockpit, and
    the rule library lives on disk. Folding this in would put a directory
    listing and N file reads on a hot path to answer a question nobody asked.

    **One snapshot, both halves.** The screen class and the guard facts are
    derived from a SINGLE `_status_response` call rather than two reads of the
    session. Two calls would let bytes land in between, and the facts would
    then describe a screen that is no longer the one classified -- the same
    race `render_with_color` was built to close, where the failure is not a
    crash but a plausible answer about the wrong moment.
    """
    from ..rules.reflex import facts_from_status, propose_macro

    status = _status_response(session, server)
    decision = propose_macro(status.get("classification"), facts_from_status(status))
    return {
        "ok": True,
        "classification": status.get("classification"),
        "reflex": {
            "macro": decision.macro,
            "rule_id": decision.rule_id,
            "stop_reason": decision.stop_reason,
            "scope": decision.scope,
        },
    }


def _dispatch_reflex_arm(args, session, server):
    """WO-REFLEX-ARMED-RUN: launch the proposal a human just confirmed --
    **after proving it is still the proposal**.

    The human's `y` happens on the client, against a preview this daemon
    answered some moments ago. Between those two instants the game screen can
    change, a rule can be approved or withdrawn, and the library can be
    edited. So the confirmation is carried here as an *identity* (`rule_id`,
    `macro`, `classification`) rather than as an instruction, and this verb
    re-derives the proposal from scratch and refuses unless all three still
    match exactly. **Nothing the client says selects the macro.** The client
    says which macro it was allowed to promise the human; if the answer has
    moved, the run does not happen and no substitute is offered.

    That is why the delegated name is `decision.macro` and not the caller's
    string even though the two are proven equal one line above. The value
    that launches should have come from this snapshot, so that weakening the
    comparison could never widen into "the client names the macro".

    **A library that now proposes nothing answers with its own reason, not
    with drift.** `autopilot_no_candidates` and `autopilot_rules_unreadable`
    say *why* there is no proposal; collapsing them into
    `autopilot_proposal_drift` would be true but less useful, and the
    operator's next move differs (teach a rule / fix the library / look
    again). Drift is reserved for "there is a proposal and it is not yours".

    Sends nothing itself and takes no control lock: on the one path that
    launches, it delegates to `_dispatch_autoloop_start`, which owns the
    start-anchor, control-lock, credit-floor, turn-budget, hazard, and
    cycles rails. Those refusals reach the caller in the runner's own
    vocabulary, unre-spelled. The `NEVER_AUTO_ACTION_CLASSES` refusal at
    every `replay_loop` boundary is untouched and unconditional -- an armed
    run of an approved rule still
    halts at a money prompt.

    **Repeating scope → multi-pass** (WO-AUTOLOOP-CYCLES): when the
    re-derived winning rule carries ``scope: repeating``, this verb asks
    ``autoloop_start`` for ``cycles=CYCLES_HARD_CEILING``. ``one-shot`` /
    missing scope stays a single pass. The client never names a cycle
    count on this verb — ``ARGS_REFLEX_ARM`` stays identity-only — so a
    client cannot smuggle an unbounded request past the hard ceiling.
    """
    from ..rule_engine import SCOPE_REPEATING
    from ..rules.reflex import (
        ARGS_REFLEX_ARM,
        facts_from_status,
        propose_macro,
        proposal_drift,
    )

    unsupported = sorted(set(args) - ARGS_REFLEX_ARM)
    if unsupported:
        # Same posture as `autoloop_start`: an arg this verb does not honour
        # is refused, never ignored. A silently-dropped `cycles` would be a
        # surface agreeing to a repetition it does not perform — and for
        # this verb, cycles are derived from rule scope, not client args.
        return {"ok": False, "error": f"unsupported_arg:{unsupported[0]}"}

    # ONE snapshot for both halves, for `_dispatch_reflex`'s reason: two reads
    # would let bytes land between them, and the identity would then be checked
    # against a screen that is no longer the one classified.
    status = _status_response(session, server)
    classification = status.get("classification")
    decision = propose_macro(classification, facts_from_status(status))

    if not decision.fired:
        return {"ok": False, "error": decision.stop_reason or "autopilot_no_candidates"}

    drift = proposal_drift(args, decision=decision, classification=classification)
    if drift:
        return {"ok": False, "error": drift}

    payload = {"name": decision.macro}
    if decision.scope == SCOPE_REPEATING:
        payload["cycles"] = autoloop.CYCLES_HARD_CEILING
    return _dispatch_autoloop_start(payload, server)



def _current_session_id(session) -> str | None:
    """Daemon continuous-play session id for ledger rows (never invent)."""
    sid = getattr(session, "session_id", None)
    if isinstance(sid, str) and sid:
        return sid
    logger = getattr(session, "logger", None)
    sid = getattr(logger, "session_id", None) if logger is not None else None
    if isinstance(sid, str) and sid:
        return sid
    return None


def _driver_was_fenced(server) -> bool:
    """True when attach fenced this dispatch mid-flight (CleanPreempt)."""
    lock = getattr(server, "control_lock", None)
    if lock is None:
        return False
    try:
        return bool(lock.is_driver_fenced())
    except Exception:  # noqa: BLE001 -- ledger must never crash the verb
        return False



def _ledger_world_id(session) -> str | None:
    """Best-effort world slug for Trace-Ledger stamps. Never raises."""
    profile_name = getattr(session, "auto_login_profile", None)
    if not profile_name:
        return None
    try:
        profile, err = _load_profile(profile_name)
        if profile is None or err is not None:
            return None
        from tw2002_aiclient import world_identity

        return world_identity.world_id_from_profile(profile)
    except Exception:  # noqa: BLE001
        return None


def _record_ledger(
    server,
    session,
    pre_text,
    input_text,
    *,
    secret: bool,
    resp,
    actor: str,
    interrupted_by_human: bool = False,
    rule_id: str | None = None,
    target_player: str | None = None,
) -> None:
    """Append one Trace-Ledger row for a do/send that already hit the wire.

    ``server.ledger`` absent (bare test harness) → silent no-op.
    Missing ``session_id`` → skip (never invent). Actor must be a live
    sender (`app`/`human`) — never ``ai``.
    """
    ledger = getattr(server, "ledger", None)
    if ledger is None:
        return
    session_id = _current_session_id(session)
    if not session_id:
        return
    if actor not in ("app", "human"):
        # Reborn north-star: AI never live-drives. Refuse to attribute.
        return
    post_text = "\n".join(resp.get("screen") or [])
    settled_class = resp.get("classification") or "unknown"
    try:
        ledger.record_do(
            pre_text,
            input_text,
            secret=bool(secret),
            post_text=post_text,
            settled_class=settled_class,
            actor=actor,
            session_id=session_id,
            interrupted_by_human=bool(interrupted_by_human),
            world_id=_ledger_world_id(session),
            rule_id=rule_id,
            target_player=target_player,
        )
    except Exception:  # noqa: BLE001 -- ledger must never fail the verb
        return


def _optional_stamp(args: object, key: str) -> str | None:
    if not isinstance(args, dict):
        return None
    raw = args.get(key)
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None

def record_attach_keystroke(server, session, pre_text, input_text, secret) -> None:
    """Route a ``tw attach`` keystroke into the same Trace-Ledger as do/send.

    Called from ``daemon.CommandHandler._handle_attach`` after ``send_raw``.
    Actor is always ``human``. Uses the caller's ``secret`` flag (same
    decision as ``session.last_sent_secret``) so transcript + ledger agree.
    """
    ledger = getattr(server, "ledger", None)
    if ledger is None:
        return
    session_id = _current_session_id(session)
    if not session_id:
        return
    try:
        post_text = session.render_text(session.render())
    except Exception:  # noqa: BLE001
        post_text = ""
    post_lines = post_text.splitlines()
    post_prompt = post_lines[-1].strip() if post_lines else ""
    try:
        settled_class = classify_screen(post_text, post_prompt)
    except Exception:  # noqa: BLE001
        settled_class = "unknown"
    try:
        ledger.record_do(
            pre_text,
            input_text,
            secret=bool(secret),
            post_text=post_text,
            settled_class=settled_class,
            actor="human",
            session_id=session_id,
            world_id=_ledger_world_id(session),
        )
    except Exception:  # noqa: BLE001
        return


def dispatch(session, verb, args, server):
    """The daemon's one dispatch chokepoint. A malformed/unrecognized
    `verb` is answered with a structured error, never an exception --
    see `daemon.py`'s `CommandHandler.handle()` for the outer
    belt-and-braces `try/except` that also catches anything this misses."""
    if verb == "screen":
        rows = session.render_raw() if args.get("raw") else None
        return build_response(session, rows=rows)

    if verb == "status":
        # NOT build_response() -- see `_status_response`'s docstring and canon
        # `DECISIONS.md` §C.2. `screen` just above (and `do`/`send`/`read`/the
        # WatchHub emit below) keep the full mirror; `status` is the
        # structured answer a spectator parses.
        return _status_response(session, server)

    if verb == "stop":
        server.request_stop()
        return {"ok": True, "stopping": True}

    if verb == "disconnect":
        # WO-PLAY-CONN-TOGGLE: close the telnet connection without stopping
        # the daemon. The `ensure` verb's own reconnect path (`session.
        # reconnect()`) is what the UI uses to re-establish a connection
        # after a disconnect or a host-side timeout/drop. Same silence
        # discipline as `session.reconnect()`'s close() exception: a dead
        # connection can raise near anything on close.
        try:
            session.conn.close()
        except Exception:  # noqa: BLE001 — already-dead socket, silence per reconnect convention
            pass
        return {"ok": True, "disconnected": True}

    if verb == "ensure":
        # WO-P2-025: full control-lock via `_driving_dispatch` (replaces
        # the earlier ensure-only `drive_lock`). Autopilot auto-arm after
        # ensure (`_maybe_auto_start_after_ensure`) still cut — no
        # autopilot.py.
        return _dispatch_ensure(session, args, server)

    if verb == "do":
        # WO-P2-OPS-VERB-B: send + wait_settle. Trace-Ledger via
        # `_record_ledger` (PWO-094 LedgerWriter; WO-DAEMON-LEDGER-WRITER-ATTACH).
        # wait_prompt is case-sensitive (settle.py HARD RULE).
        #
        # WO-DO-SETTLE-RX-GUARD: this is the ONE settle in the protocol
        # that follows a send of our own, so it is the one that must not
        # accept a `wait_prompt` the PRE-SEND screen already satisfied —
        # `Command [TL=` → `Command [TL=` is canon's own worked example
        # and returned `("prompt", 0.0)` before the game had responded at
        # all. `prompt_requires_new_bytes=True` gives the prompt branch
        # the same ">=1 byte since the send" clause the idle branch has
        # always had. `read` below deliberately does NOT set it: it sends
        # nothing, so returning immediately on a prompt that is already
        # there is its correct contract, not the same defect.
        #
        # WO-DO-PROMPT-LINE-PIN: `match_scope=MATCH_SCOPE_PROMPT_LINE` is
        # a SECOND, independent narrowing on this same settle, closing the
        # OTHER stale window — canon's P-SETTLE-LINE
        # (`canon/research/tw2002-screen-patterns.md`): "New bytes since
        # send do not prove the match is on new content — a stale copy of
        # the target text elsewhere on the grid still hits... Do not treat
        # whole-screen regex success as proof the *live* prompt matched."
        # TradeWars is a scrolling BBS door, so the `Command [TL=` this
        # `do` waits for is routinely STILL VISIBLE up the grid from two
        # screens ago; a whole-screen search confirms against that row and
        # hands the App `settled_reason: prompt` over a screen whose live
        # prompt line is something else entirely.
        #
        # What this buys is precise, and smaller than it looks: the wait
        # does NOT hold out for the real prompt. `wait_for_settle` returns
        # on the FIRST of prompt/idle/timeout, so once the stale row stops
        # matching, the keystroke echo plus one quiet debounce window
        # legitimately satisfies the IDLE branch instead. The win is a
        # DOWNGRADE OF THE CLAIM — `prompt` ("quiet on a specific, named
        # shape", false here) becomes `idle` ("it went quiet; I never saw
        # your shape", true here) — which is exactly canon's ordering of
        # the three reasons. Measured both ways in
        # tests/test_do_settle_rx_guard.py.
        #
        # Pinned HERE, at the call site, rather than defaulted in
        # `settle.py` or `Session.wait_settle`: P-SETTLE-LINE leaves the
        # DEFAULT an open canon question — "until ruled, do not flip
        # defaults in a drive-by tip; pin prompt-line scope where a WO
        # explicitly Accepts it" — and `read` below reaches settle through
        # that same door needing the OPPOSITE value, so no default could
        # serve both. The cost is the one settle.py states: a cross-row
        # `wait_prompt` (operator-supplied and free-form) can no longer
        # match on this verb and degrades to `timeout` — never to a wrong
        # match. `read` keeps whole-screen scope and can still express it.
        with _driving_dispatch(server) as lock_error:
            if lock_error is not None:
                return lock_error
            text = args.get("input", "")
            enter = args.get("enter", True)
            secret = args.get("secret", False)
            wait_prompt = args.get("wait_prompt")
            try:
                pre_text = session.render_text(session.render())
                session.send(text, enter=enter, secret=secret, sender="app")
                reason, elapsed = session.wait_settle(
                    wait_prompt=wait_prompt,
                    timeout=args.get("timeout", 8.0),
                    debounce_ms=args.get("debounce_ms", 350),
                    prompt_requires_new_bytes=True,
                    match_scope=MATCH_SCOPE_PROMPT_LINE,
                )
            except re.error as e:
                return {"ok": False, "error": f"bad_wait_prompt_regex:{e}"}
            resp = build_response(session, settled_reason=reason, extra={"elapsed": elapsed})
            history_args = {**args, "input": "<redacted>"} if secret else args
            session.record_history(
                "do", history_args, resp["prompt"], resp["classification"], reason
            )
            # WO-DAEMON-LEDGER-WRITER-ATTACH: Trace-Ledger row for this App send.
            _record_ledger(
                server,
                session,
                pre_text,
                text,
                secret=secret,
                resp=resp,
                actor="app",
                interrupted_by_human=_driver_was_fenced(server),
                rule_id=_optional_stamp(args, "rule_id"),
                target_player=_optional_stamp(args, "target_player"),
            )
            return resp

    if verb == "send":
        # WO-P2-OPS-VERB-B: raw send, no settle wait.
        # WO-SEND-HISTORY-RING: still file the history ring — same ledger as
        # `do`/`read`, same secret redaction; settled_reason is None because
        # this verb never waits.
        with _driving_dispatch(server) as lock_error:
            if lock_error is not None:
                return lock_error
            text = args.get("input", "")
            enter = args.get("enter", True)
            secret = args.get("secret", False)
            pre_text = session.render_text(session.render())
            session.send(text, enter=enter, secret=secret, sender="app")
            resp = build_response(session)
            history_args = {**args, "input": "<redacted>"} if secret else args
            session.record_history(
                "send", history_args, resp["prompt"], resp["classification"], None
            )
            _record_ledger(
                server,
                session,
                pre_text,
                text,
                secret=secret,
                resp=resp,
                actor="app",
                interrupted_by_human=_driver_was_fenced(server),
                rule_id=_optional_stamp(args, "rule_id"),
                target_player=_optional_stamp(args, "target_player"),
            )
            return resp

    if verb == "read":
        # WO-P2-OPS-VERB-B: wait-and-return, never sends (read-only).
        wait_prompt = args.get("wait_prompt")
        try:
            reason, elapsed = session.wait_settle(
                wait_prompt=wait_prompt,
                timeout=args.get("timeout", 8.0),
                debounce_ms=args.get("debounce_ms", 350),
            )
        except re.error as e:
            return {"ok": False, "error": f"bad_wait_prompt_regex:{e}"}
        resp = build_response(session, settled_reason=reason, extra={"elapsed": elapsed})
        session.record_history("read", args, resp["prompt"], resp["classification"], reason)
        return resp

    if verb == "state":
        # WO-P2-G4-X1: read-only parsed game-state. NOT build_response() and
        # NOT _driving_dispatch() -- see `_state_response`'s docstring for
        # both, and for why a dead socket answers `unreadable` rather than
        # reading a sector off the frozen frame.
        return _state_response(session)

    if verb == "autoloop_start":
        # WO-P2-G4-X4. NOT `_driving_dispatch`: a background run's
        # exclusivity is the control lock's OTHER hold (`enter_auto_loop`,
        # taken inside the runner), and taking the per-dispatch driver
        # slot here would make the two mutually exclusive -- `start` would
        # hold `_driving` and then be refused its own
        # `locked_by_active_driver`. The refusals a caller can hit are the
        # same set either way; they come from `enter_auto_loop` instead.
        return _dispatch_autoloop_start(args, server)

    if verb == "autoloop_stop":
        return _dispatch_autoloop_stop(server)

    if verb == "autoloop_pause":
        return _dispatch_autoloop_pause(server)

    if verb == "autoloop_relaunch":
        # NOT `autoloop_resume` — hub ruling 2026-07-27 (1+3). This replays
        # the macro from step 1 and re-issues sends already made, so the
        # verb is named for what it does. `autoloop_resume` stays an
        # `unknown_verb` deliberately: a caller reaching for the word that
        # promises continuation should get a refusal, not a relaunch.
        # Same non-`_driving_dispatch` reasoning as `autoloop_start`: a
        # relaunch IS a start and must reach `enter_auto_loop` without
        # holding the per-dispatch driver slot that would refuse it.
        return _dispatch_autoloop_relaunch(server)

    if verb == "autoloop_status":
        return _dispatch_autoloop_status(server)

    if verb == "trade_chain_start":
        return _dispatch_trade_chain_start(args, server)

    if verb == "trade_chain_stop":
        return _dispatch_trade_chain_stop(server)

    if verb == "trade_chain_status":
        return _dispatch_trade_chain_status(server)

    if verb == "stardock_hold_start":
        return _dispatch_stardock_hold_start(args, server)

    if verb == "stardock_hold_stop":
        return _dispatch_stardock_hold_stop(server)

    if verb == "stardock_hold_status":
        return _dispatch_stardock_hold_status(server)

    if verb == "explore_start":
        return _dispatch_explore_start(args, server)

    if verb == "explore_stop":
        return _dispatch_explore_stop(server)

    if verb == "explore_status":
        return _dispatch_explore_status(server)

    if verb == "reflex":
        # WO-RULE-ENGINE-WIRE: read-only proposal from the taught rule
        # library. Sends nothing; see `_dispatch_reflex`.
        return _dispatch_reflex(session, server)

    if verb == "reflex_arm":
        # WO-REFLEX-ARMED-RUN. NOT `_driving_dispatch`, for exactly the
        # reason `autoloop_start` is not: this delegates into
        # `enter_auto_loop`, and holding the per-dispatch driver slot here
        # would make the run refuse itself with `locked_by_active_driver`.
        return _dispatch_reflex_arm(args, session, server)

    if verb == "history":
        # WO-P2-OPS-VERB-C (partial): in-memory session history ring.
        n = int(args.get("n", 20) or 20)
        if n < 0:
            n = 0
        return {"ok": True, "history": list(session.history[-n:])}

    return {"ok": False, "error": f"unknown_verb:{verb}"}


def _load_profile(name):
    """Bounded profile loader (WO-P2-020 Wave-3 CUT vs archive
    credentials.py:162-226's `load_profile`/`Profile`): no
    `crawl_sacrificial`/`autonomous` fields (`autopilot.py` hasn't
    landed). Reads `config/profiles.toml` directly via `tomllib` for the
    game_letter/handle/allow_register fields since the ported
    `credentials.py` (WO-P0-005/WO-P1-012) only exposes read-only
    summaries (`list_profile_summaries`), not a raw section lookup --
    host/port resolution itself is delegated to the ONE shared resolver,
    `credentials.resolve_profile_host_port` (OPEN-003-A). Returns
    `(LoginProfile, None)` on success, `(None, error_str)` on failure --
    never raises, so `_dispatch_ensure` can turn a bad profile into an
    ordinary `{"ok": False, ...}` response."""
    import tomllib  # stdlib since 3.11 — requires-python >=3.11 (WO-REQUIRES-PYTHON-311)

    from . import credentials
    from .login import LoginProfile

    path = credentials.PROFILES_PATH
    if not path.exists():
        return None, f"profile_not_found:{name}"
    with open(path, "rb") as f:
        data = tomllib.load(f)
    p = data.get(name)
    if not isinstance(p, dict):
        return None, f"profile_not_found:{name}"

    game_letter = p.get("game_letter")
    handle = p.get("handle")
    allow_register = bool(p.get("allow_register", False))
    missing = []
    if not game_letter:
        missing.append("game_letter")
    # A handle is required UNCONDITIONALLY -- `allow_register` does not
    # excuse it.
    #
    # `allow_register` means "you may CREATE the character with this
    # handle", not "you need no handle": `login.py`'s own Wave-3 cuts note
    # says so outright -- "A profile must set its own `handle` (or opt into
    # `allow_register` with a handle it's fine reusing every run); no
    # drawn-identity retry loop exists yet", because `register_with_name_bank`
    # / `name_bank.py` were never ported. There is nothing in this tree that
    # can invent a name.
    #
    # The old `and not allow_register` let a handle-less profile load, and it
    # then died four layers down on the wire: the blank-reject retry
    # (WO-MICRO-LOGIN-BLANK-REJECT) answers a rejecting outer gate with
    # `profile.handle`, which was `None`, reaching `connection.send_text`
    # and surfacing as `internal_error:AttributeError`. Found live against
    # twgs.microblaster.net while registering a sacrificial profile.
    #
    # Refusing HERE turns that into `profile_incomplete:<name>:missing=
    # ['handle']` before a socket is opened -- the operator learns their
    # config is wrong instead of watching a login crash.
    if not handle:
        missing.append("handle")
    if missing:
        return None, f"profile_incomplete:{name}:missing={missing}"

    try:
        host, port = credentials.resolve_profile_host_port(name)
    except credentials.ProfileConnectionError as e:
        return None, f"profile_connection_error:{name}:{e}"

    profile = LoginProfile(
        name=name,
        handle=handle,
        game_letter=str(game_letter),
        allow_register=allow_register,
        ship_name=p.get("ship_name"),
        planet_name=p.get("planet_name"),
        clear_avoids_on_login=bool(p.get("clear_avoids_on_login", False)),
    )
    return profile, None


def _save_password(profile_name, password):
    """NEW-registration credential persistence (login-automaton.md:
    "generates a fresh password and saves it immediately"). WO-P2-020
    Wave-3 CUT vs archive credentials.py:268-278's `save_password`: the
    ported `credentials.py` (WO-P0-005/WO-P1-012) only landed the READ
    side (`get_password`) -- this mirrors its EXACT on-disk shape
    (`{profile: {"password": ...}}`) at the same chmod-600
    `SECRETS_PATH` so a later `credentials.get_password(profile_name)`
    call reads it straight back. A follow-on WO should promote this into
    `credentials.py` itself rather than leaving the write side split
    across two modules."""
    _merge_secret_entry(profile_name, password=password)


def _save_in_game_alias(profile_name, alias):
    """Persist the Alias the TWGS host accepted (or last attempted).

    WO-FIX-LOGIN-ALIAS-PROMPT-UNHANDLED: non-secret field ``in_game_alias``
    merged into the existing secrets entry so it stays discoverable beside
    the password without a third store. Does not clobber ``password``.
    """
    _merge_secret_entry(profile_name, in_game_alias=alias)


def _merge_secret_entry(profile_name, **fields):
    from . import credentials

    path = credentials.SECRETS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if path.exists():
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    entry = data.get(profile_name)
    if not isinstance(entry, dict):
        entry = {}
    else:
        entry = dict(entry)
    for key, value in fields.items():
        if value is not None:
            entry[key] = value
    data[profile_name] = entry
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    os.chmod(tmp_path, 0o600)
    os.replace(str(tmp_path), str(path))
    os.chmod(path, 0o600)


def _normalise_host(value):
    """DNS-comparable form of a host string, or `None` if it is not one.

    Two normalisations only, both of them things DNS itself treats as the
    SAME name: ASCII-case folding (`.lower()`, not `.casefold()` -- casefold
    maps `ß` to `ss`, which would make two genuinely DIFFERENT hosts compare
    EQUAL, i.e. fail open), and dropping the single trailing root dot of an
    absolute FQDN (`host.example.` == `host.example`). Exactly one trailing
    dot is dropped, not `rstrip(".")`: `host..` is malformed, not the same
    name, and must stay unequal.

    Deliberately NOT done: DNS resolution, alias/CNAME chasing, IP-literal
    canonicalisation, whitespace stripping. The first two are network I/O in
    a dispatch path (a new failure mode, and a new way for a wrong answer to
    look authoritative); the last would silently repair a malformed config
    value instead of refusing on it.

    A non-string is `None` -- the caller treats that as "cannot compare",
    which is a REFUSAL, never a pass.
    """
    if not isinstance(value, str):
        return None
    host = value.lower()
    if host.endswith("."):
        host = host[:-1]
    return host


def _profile_identity(profile_name):
    """Resolve `profile_name`'s connect target for the `ensure` identity gate.

    Returns `((host, port), None)` or `(None, error_str)` -- never raises, so
    a store that has become unreadable/malformed between `_load_profile`'s own
    resolve and this one turns into an ordinary refusal rather than a
    traceback. Fail CLOSED: any exception at all means we do not know which
    server this profile names, and an unknown identity may never be treated
    as a matching one.

    The error carries `type(e).__name__` only, never `str(e)` -- the
    type-name-only convention `watch.py`/`guardian.py` already use, so no
    exception message can carry session payload into a response. The
    ACTIONABLE version of the common failures is already delivered upstream:
    `_load_profile` runs first and turns every `ProfileConnectionError` into
    `profile_connection_error:<name>:<e>`, so this branch is reached only by
    a store that changed under us or by a failure outside that family.
    """
    from . import credentials

    try:
        host, port = credentials.resolve_profile_host_port(profile_name)
    except Exception as e:  # noqa: BLE001 -- fail closed on ANY resolve failure
        return None, f"profile_identity_unverified:{profile_name}:{type(e).__name__}"
    return (host, port), None


def _session_identity_mismatch(session, profile_name, want):
    """`None` when the live session's connect target IS `want`; the typed
    refusal string when it provably is not.

    **What this closes (WO-ENSURE-PROFILE-IDENTITY-VERIFY).** `ensure
    --profile X` used to accept a matching screen CLASS as proof of
    IDENTITY: any session already sitting at `main_command` was stamped
    `session.mark_profile(X)` regardless of which server it was actually on,
    and `mark_profile` is what arms `guardian._maybe_reconnect` to replay
    X's credential -- through `session.reconnect()`, which reconnects to the
    session's OWN host, not the profile's. So a wrong-profile `ensure`
    mislabelled the session and a later drop sent X's password to a server X
    never named. The immediate path was the same shape: when the class did
    NOT match, `run_login` ran against the EXISTING socket.

    **Purely restrictive.** The only outcome this function can add is a
    refusal. It never reconnects, never re-targets, never edits credentials
    -- correcting the connection is deliberately out of scope; refusing is
    the deliverable.

    **The "no wire target to contradict" rule.** The comparison is made iff
    `session.port` is a usable port by `credentials._valid_port` -- the
    codebase's OWN definition (positive `int`, `bool` excluded), called
    rather than re-derived so this cannot drift from the resolver's idea of
    a valid port. A session whose port is not one (0, `None`, a string) has
    no reachable TCP target: it has never spoken to a game server on that
    port and cannot, so there is no established identity for a profile to
    contradict and a first `ensure` must still work. Everything else -- an
    empty or non-string HOST with a real port -- is COMPARED, and therefore
    refuses: an empty host is still a connectable target (it resolves to the
    loopback/any address), so it is exactly the case that must not be waved
    through.

    **Deliberate non-reuse of `server_inventory.endpoint_key`.** That helper
    builds the same `(host, port)` pair into a lookup key, but it LAUNDERS
    bad values -- an unparseable port becomes `0` and a `None` host becomes
    `""` -- so two differently-broken endpoints collapse to the same key and
    compare EQUAL. That is the correct behaviour for a display/lookup key
    and precisely the wrong one for an identity gate, which must refuse on
    anything it cannot compare.

    Host and port differences get their OWN error names. A port-only
    difference reported as `profile_host_mismatch` would tell the operator
    something false about their config while it is being refused.
    """
    from . import credentials

    port = getattr(session, "port", None)
    if not credentials._valid_port(port):
        return None
    live_host = _normalise_host(getattr(session, "host", None))
    want_host = _normalise_host(want[0])
    if live_host is None or want_host is None or live_host != want_host:
        return f"profile_host_mismatch:{profile_name}"
    if port != want[1]:
        return f"profile_port_mismatch:{profile_name}"
    return None


def _login_failure_response(session, error_text):
    """The `ensure` FAILURE answer — bounded by construction, never a mirror
    of the receive buffer (canon `DECISIONS.md` §C.2, ruled 2026-07-26).

    **The carrier this exists to close.** This branch used to answer with a
    full `build_response()`, whose `screen` is the entire rendered buffer and
    whose `prompt` is its last row. On a server that ECHOES at the password
    gate — the behavior canon's RX-side no-leak guarantee openly rests on
    never happening (`canon/doctrine/secrets-and-credentials.md`, Code
    Divergence #1) — those two fields ARE the operator's credential, and they
    rode the `--json` response, `adapters.EnsureResult.raw`, and anything
    that persists either. Measured end to end through the real daemon socket
    and the real CLI, not reasoned about:
    `tests/test_ensure_login_error_redaction.py`. `prompt` mattered as much as
    `screen`: on the STALL path the current prompt line is exactly the echoed
    line `login.LoginStalled` was created to keep out of the error text, so
    closing `screen` alone would have moved the leak one field to the left.

    **The line §C.2 draws is whether the mirror LEAVES the session**, not
    whether the app may look at it. A live `attach` / cockpit paint may show
    whatever the server painted — that is the human's own eyes on their own
    game — so this function is deliberately the ONLY place the mirror is
    dropped. `screen`, `status`, `do`, `send`, `read` and the WatchHub
    seed/settle-edge emit still call `build_response()` unchanged, and the
    session's own pyte buffer is not sanitised (pinned by
    `test_the_live_paint_path_still_shows_what_the_server_painted`).

    **Unconditional, never gated on "did a secret go out".** Deciding to
    redact only when the app recognises a secret prompt fails open in exactly
    the scenario under test: the echo mutates the screen, so
    `classify_screen` answers `unknown` rather than `login_password`, and the
    NEW-registration stall reaches this branch AFTER the credential is on the
    wire. Redaction that depends on recognition is redaction that stops the
    day recognition does. An ensure that FAILED simply does not mirror the
    buffer.

    **Why omit rather than mask.** Masking would need the plaintext at this
    layer, and this layer deliberately does not have it — `session.last_sent`
    is already `"<redacted>"` for a `secret=True` send and the credential
    itself lives only inside `run_login`'s frame. Threading it out here to
    scrub a buffer would widen the secret's blast radius to serve a
    diagnostic. It would also be fail-OPEN even then, for the reasons
    `LoginStalled`'s own docstring gives about the error text and which apply
    verbatim to the buffer: pyte wraps at the column boundary, an echo can be
    partially overwritten, and the grid may hold a SIBLING profile's secret or
    one the human typed into an earlier attach — screen content this process
    never held a copy of to match against. A mask that misses ships the
    credential wearing a redacted look, which is worse than either honest
    answer.

    **What it still carries, and why each is bounded.** `classification` is
    `classify.classify_screen`'s CLOSED vocabulary — `unknown` for anything it
    cannot name, never a slice of the screen — so the operator still learns
    WHICH screen the automaton gave up on; `error` still names the failure
    mode (and, via `LoginStalled`, its own classification and step). No
    length, shape, or character-class digest of the prompt line is offered in
    the mirror's place: doctrine invariant 2 counts a length as a leak in its
    own right, and `LoginStalled` already refused exactly that digest.
    `screen_withheld` is honest absence rather than a silently missing key —
    a consumer can tell "withheld here" from "this verb never had one", and
    the key is omitted rather than set to a marker STRING so a caller doing
    `"\\n".join(resp["screen"])` fails loudly instead of joining characters.
    """
    rows = session.render()
    text = session.render_text(rows)
    return {
        "ok": False,
        "error": error_text,
        "classification": classify_screen(text, rows[-1].strip() if rows else ""),
        # Already "<redacted>" for a secret send (session.py) and app-
        # originated text otherwise -- never receive-buffer content.
        "sent_input": getattr(session, "last_sent", None),
        "already_there": False,
        "screen_withheld": "login_failure",
    }


def _dispatch_ensure(session, args, server):
    """B4: idempotent `ensure` -- classify the current screen; if already
    at `target`, no-op. Else run the login automaton via the profile's
    stored/generated credential.

    **WO-P2-025:** whole body runs under `_driving_dispatch` (control_lock
    `acquire_driver` / `release_driver`). Concurrent second ensure →
    typed `controller_busy` (or human/spectate/auto_loop refuse), never
    queued — folds the earlier ensure-only `drive_lock`. Bare harness
    without `server.control_lock` stays unrestricted for unit tests.
    Login sends use Session.send default `sender="app"` (no login edits).

    **WO-ENSURE-PROFILE-IDENTITY-VERIFY:** a matching screen CLASS is no
    longer accepted as proof of IDENTITY. Before either hazard -- the
    `cls == target` `mark_profile` stamp, and `run_login` against the
    existing socket -- the session's own `(host, port)` must match the one
    the profile resolves to, or the verb refuses (`profile_host_mismatch:` /
    `profile_port_mismatch:` / `profile_identity_unverified:`). The check is
    purely restrictive: it never reconnects and never re-targets, so a
    wrong-profile `ensure` is REFUSED rather than repaired.
    """
    with _driving_dispatch(server) as lock_error:
        if lock_error is not None:
            return lock_error

        from . import credentials
        from .login import LoginError, run_login

        target = args.get("target", "main_command")
        profile_name = args.get("profile")
        # WO-P2-022: `no_auto_arm` is accepted on the wire for symmetry with any
        # future default-arm proposal, but ensure NEVER auto-arms today
        # (`autopilot.py` not ported; `_maybe_auto_start_after_ensure` left out).
        # When auto-arm returns, it MUST gate on `bool(args.get("no_auto_arm"))`.
        _ = bool(args.get("no_auto_arm"))
        if not profile_name:
            return {"ok": False, "error": "missing_profile"}

        profile, err = _load_profile(profile_name)
        if err is not None:
            return {"ok": False, "error": err}

        # WO-ENSURE-PROFILE-IDENTITY-VERIFY: does this session actually sit on
        # the server this profile names? Placed HERE, immediately after the
        # profile loads and before anything else happens, because it is the
        # one point that precedes ALL THREE hazards at once: the
        # `cls == target` reuse stamp (`mark_profile` arms the guardian's
        # later credential replay), `run_login` on the EXISTING socket, and
        # the `reconnect()` just below -- a wrong-profile request should not
        # even buy a reconnection on that profile's behalf. Re-derived again
        # at each use point below rather than trusted forward; see
        # `_session_identity_mismatch` for what it compares and why refusing
        # is the whole remedy.
        want, err = _profile_identity(profile.name)
        if err is not None:
            return {"ok": False, "error": err}
        err = _session_identity_mismatch(session, profile.name, want)
        if err is not None:
            return {"ok": False, "error": err}

        # A dead telnet connection must be repaired before we can even
        # classify the current screen (a stale pyte buffer would
        # misclassify a frozen last-seen frame as "current").
        if not session.conn.connected:
            try:
                session.reconnect()
            except OSError as e:
                return {"ok": False, "error": f"reconnect_failed:{e}"}

        rows = session.render()
        text = session.render_text(rows)
        prompt = rows[-1].strip() if rows else ""
        cls = classify_screen(text, prompt)

        # Re-derived at the USE point, not trusted forward from the gate
        # above (Accept 2). Between the gate and here the session may have
        # been reconnected, and a stop/restart burst can land in that window;
        # nothing may stand between this line and the two hazards it guards,
        # so it sits AFTER the render/classify (the only calls that can block
        # or hand control to another thread) and immediately BEFORE both the
        # `mark_profile` stamp and the `run_login` send. The invariant this
        # enforces -- rather than assumes -- is that `Session.host`/`.port`
        # are assigned once in `__init__` and never reassigned (`reconnect()`
        # rebuilds the socket from those same two fields), so the pair that
        # was verified IS the pair the login will be sent to.
        err = _session_identity_mismatch(session, profile.name, want)
        if err is not None:
            return {"ok": False, "error": err}

        if cls == target:
            session.mark_profile(profile.name)
            seed = seed_hud_after_join(session)
            return build_response(
                session,
                extra={"already_there": True, "steps": 0, **seed},
            )

        try:
            final_cls, steps = run_login(
                session,
                profile,
                get_password=credentials.get_password,
                save_password=_save_password,
                save_alias=_save_in_game_alias,
                target=target,
            )
        except LoginError as e:
            # NOT build_response() -- see `_login_failure_response`'s docstring
            # and canon `DECISIONS.md` C.2. The success paths below keep it.
            return _login_failure_response(session, f"login_failed:{e}")

        # Third and last re-derivation (Accept 2): the login itself is the
        # longest window in this dispatch, so the stamp that ARMS the
        # guardian's future credential replay is gated on the identity still
        # holding NOW, not on the check that let the login start. A refusal
        # here cannot un-send what `run_login` already sent -- it does the
        # one thing still available, which is to leave `auto_login_profile`
        # unset so no FUTURE reconnect replays this credential against a
        # session whose target we can no longer vouch for.
        err = _session_identity_mismatch(session, profile.name, want)
        if err is not None:
            return {"ok": False, "error": err}

        session.mark_profile(profile.name)
        seed = seed_hud_after_join(session)
        return build_response(
            session,
            extra={"steps": steps, "already_there": False, **seed},
        )
