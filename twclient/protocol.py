"""JSON verb protocol shared by the daemon's socket server and the CLI.

Wire format: one line-delimited JSON object per request/response over the
unix-domain socket. Request: {"verb": "...", "args": {...}}.
Response: always has "ok"; on success carries verb-specific fields, on
failure carries "error".
"""

import re
import time
from contextlib import contextmanager

from . import world_identity, world_model
from .classify import classify_screen
from .control_lock import MODE_AI_PILOT, MODE_AUTO_LOOP, MODE_HUMAN, ControlModeConflict
from .state_parser import (
    is_genuine_port_report,
    is_genuine_sector_status,
    parse_port_report,
    parse_state,
    sector_from_command_prompt,
)


def _build_status_intervention(
    *,
    mode,
    autopilot_status,
    credits,
    credits_age_ms,
    fighters_aboard,
    fighters_age_ms,
    credits_stale_ms=None,
):
    """WS5 read-only intervention snapshot for AI spectators.

    ``needs_attention`` is truthy only when autopilot has sticky-halted
    (``last_error`` set while not running) or a human attach holds
    MODE_HUMAN (trainer/autopilot cannot drive). Credit/fighter freshness
    flags land in ``reasons`` for situational awareness but do not alone
    raise ``needs_attention`` — same contract as autopilot's own fail-open
    on unknown/stale readings until a halt actually fires.
    """
    if credits_stale_ms is None:
        from .autopilot import DEFAULT_CREDITS_STALE_MS

        credits_stale_ms = DEFAULT_CREDITS_STALE_MS

    reasons = []
    last_error = autopilot_status.get("last_error")
    running = bool(autopilot_status.get("running"))

    if last_error and not running:
        reasons.append({"code": "autopilot_halted", "detail": last_error})

    if mode == MODE_HUMAN:
        reasons.append({"code": "human_attach_blocks_trainer"})

    if credits is None:
        reasons.append({"code": "credits_unknown"})
    elif credits_age_ms is None or credits_age_ms > credits_stale_ms:
        reasons.append(
            {
                "code": "credits_stale",
                "detail": {"age_ms": credits_age_ms, "threshold_ms": credits_stale_ms},
            }
        )

    if fighters_aboard is None:
        reasons.append({"code": "fighters_unknown"})
    elif fighters_age_ms is None or fighters_age_ms > credits_stale_ms:
        reasons.append(
            {
                "code": "fighters_stale",
                "detail": {"age_ms": fighters_age_ms, "threshold_ms": credits_stale_ms},
            }
        )

    needs_attention = bool((last_error and not running) or mode == MODE_HUMAN)

    return {
        "needs_attention": needs_attention,
        "reasons": reasons,
        "autopilot": dict(autopilot_status),
        "mode": mode,
    }


def _control_lock_error(server):
    """Shared do/send/play/replay/haggle/ensure MODE guard: None when the AI is
    free to drive (default, no server.control_lock at all in a bare
    dispatch-harness test, or mode == ai_pilot); otherwise an error
    response naming WHO/WHAT currently holds the lock, so a caller (or a
    test) can tell a human attach apart from a running AUTO-LOOP or a
    plain paused/spectate state -- never just one flat "locked" string.

    This is a FAST, non-atomic pre-check only -- a clear early error for
    the common (non-racing) case, one layer below `_driving_dispatch()`,
    which additionally reserves the single active-driver slot (TW-04).
    It is deliberately NOT the source of truth for mode: a mode
    transition (`enter_auto_loop()`/`take_human()`) can land in the
    window between this check returning None and `acquire_driver()`
    actually running, so `control_lock.ControlLock.acquire_driver()`
    itself re-checks mode atomically under the same lock as the driver-
    slot claim (see its own docstring) -- this function's result is only
    ever a hint, never relied on for correctness."""
    lock = getattr(server, "control_lock", None)
    if lock is None or lock.ai_may_send():
        return None
    mode = lock.mode
    if mode == MODE_HUMAN:
        return {"ok": False, "error": "controller_locked_by_human"}
    if mode == MODE_AUTO_LOOP:
        return {"ok": False, "error": "controller_locked_by_auto_loop"}
    return {"ok": False, "error": f"controller_locked:{mode}"}


@contextmanager
def _driving_dispatch(server):
    """Shared do/send/play/replay/haggle/ensure guard (TW-04): layers the
    single active-driver slot on top of `_control_lock_error`'s mode
    check, without changing any of these call sites' existing shape
    (`with _driving_dispatch(server) as lock_error: if lock_error is not
    None: return lock_error`).

    A second concurrent ai_pilot dispatch -- e.g. two `tw do` processes
    racing in from separate one-shot CLI connections, each its own
    socket round trip (DESIGN.md's one-shot-CLI shape means there's no
    persistent "connection" to hold a lock across; the driver slot's
    lifetime IS one dispatch call) -- is refused outright with a clear
    protocol error rather than queued or silently interleaved.

    `lock.acquire_driver()` below is the ATOMIC authority on both mode
    and the driver slot (see its docstring) -- the `_control_lock_error`
    check above it is only a fast up-front hint, so a mode-refusal
    caught HERE instead (an `enter_auto_loop()`/`take_human()` that slipped
    in between the two checks) still yields the identical
    `{"ok": False, "error": ...}` shape via the `except ControlModeConflict`
    below, indistinguishable to the caller from the fast-path case.

    Always releases on the way out -- success, an early `return` from
    inside the `with` block, or an uncaught exception -- crash-safe like
    take_human()/release_human()."""
    lock_error = _control_lock_error(server)
    if lock_error is not None:
        yield lock_error
        return
    lock = getattr(server, "control_lock", None)
    if lock is None:
        # Bare dispatch-harness test with no control_lock at all -- same
        # "unrestricted" convention _control_lock_error already uses one
        # call up.
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


def _driver_was_fenced(server):
    """Read once, right after a do/send/haggle dispatch's own send-then-
    settle window closes -- immediately before its `_record_ledger` call
    -- was a `take_human()` call fenced against THIS dispatch while it
    was still mid-flight (WO-CLEANPREEMPT; see control_lock.ControlLock.
    take_human()/is_driver_fenced())? A single lock-guarded read via
    `is_driver_fenced()` -- never a second raw peek at `_driving`/
    `_driver_fenced`, which `_driving_dispatch`'s own
    `finally: lock.release_driver()` is about to clear anyway. `None`/
    no-control_lock (a bare dispatch-harness test) reads as "never
    fenced", same convention as `_control_lock_error`'s own getattr
    guard."""
    lock = getattr(server, "control_lock", None)
    if lock is None:
        return False
    return lock.is_driver_fenced()


def _current_actor(server):
    """TW-05 actor attribution (knowledge/architecture/autonomy-loop.md):
    who/what generated this dispatch's send. Direct do/send/haggle in
    the default ai_pilot mode is `"ai"` (an LLM worker deciding what to
    send); `"human"` when the connection is itself in MODE_HUMAN.
    do/send/haggle are actually refused outright while MODE_HUMAN holds
    the lock (`_control_lock_error`), so this branch is inert via those
    verbs today -- kept anyway so `_record_ledger`'s actor stays correct
    the moment any future change lets a human-attributed send reach this
    same choke point (e.g. routing `send_raw()`'s attach keystrokes
    through the same ledger sink)."""
    lock = getattr(server, "control_lock", None)
    if lock is not None and lock.mode == MODE_HUMAN:
        return "human"
    return "ai"


def _current_session_id(session):
    """TW-05: the daemon's own continuous-play-session id, reused as-is
    rather than minted fresh here -- `TranscriptLogger` (session.py)
    already generates one per daemon run (`session.logger.session_id`)
    and names that session's own transcript log file, so a ledger
    entry's `session_id` and its transcript's filename correlate for
    free. `getattr`-guarded like every other optional session surface
    this module reads (`server.watch_hub`, `session.cursor_pos`) --
    absent on the bare fake-session test doubles that predate it."""
    logger = getattr(session, "logger", None)
    return getattr(logger, "session_id", None) if logger is not None else None


def _current_world_id(session):
    """TW-06/TW-25 world-model write-hook keying
    (knowledge/architecture/world-model.md's World Identity section):
    the `world_id` this session's parsed reads should be attributed to,
    or `None` when there's no attributable world -- manual play with no
    configured character (`session.auto_login_profile` unset), or a
    profile name that no longer resolves (`credentials.CredentialError`
    -- deleted/renamed profile, malformed profiles.toml entry, etc).

    Deliberately NEVER falls back to a host-only key: the canon is
    explicit that host-only keying causes galaxy-bleed between
    different characters sharing a host+game -- no-key-means-no-write
    is the correct, safe default here, not a gap to paper over.

    WO-STATUS-WORLD-ID: once a world_id has been successfully resolved
    for this connection, it is sticky on the session (``_sticky_world_id``)
    so a transient profiles.toml load failure or mid-edit CredentialError
    does not flip ``tw status`` to ``world_id: null`` while still connected.
    Sticky is only set after a successful resolve -- never invented.

    `getattr`-guarded on `auto_login_profile` like every other optional
    session surface this module reads (`server.watch_hub`,
    `session.cursor_pos`) -- absent on bare fake-session test doubles
    that predate it."""
    sticky = getattr(session, "_sticky_world_id", None)
    profile_name = getattr(session, "auto_login_profile", None)
    if not profile_name:
        return sticky
    from . import credentials

    try:
        profile = credentials.load_profile(profile_name)
    except credentials.CredentialError:
        return sticky
    try:
        wid = world_identity.world_id(session.host, profile.game_letter, profile.handle)
    except world_identity.WorldIdentityError:
        return sticky
    try:
        session._sticky_world_id = wid
    except Exception:  # noqa: BLE001 -- bare fakes may reject new attrs
        pass
    return wid


def _log_world_model_failure(session, where, exc):
    """mack Finding 4 (2026-07-19 adversarial review): `_write_world_model`
    must never let a world-model failure fail the caller's response (see
    its own docstring), but swallowing it with ZERO trace anywhere left a
    corrupt-store or persistent failure 100% invisible forever -- no log
    call existed in this module at all. Routes the swallowed exception to
    the session's own transcript logger (`logging_util.TranscriptLogger`,
    the same object every password-redaction call already goes through)
    as a single diagnostic line -- never raised, never affecting the
    response. `getattr`-guarded like every other optional session surface
    this module reads (`server.watch_hub`, `session.cursor_pos`): a bare
    fake-session test double with no `.logger` at all is a silent no-op
    here, exactly as before this fix."""
    logger = getattr(session, "logger", None)
    log_note = getattr(logger, "log_note", None)
    if log_note is not None:
        log_note(f"world_model {where} failed: {exc!r}")


def _write_world_model(session, text, prompt, parsed_state):
    """TW-06/TW-25 world-model write-hook: fire-and-forget side effect
    of `build_response` -- see `_current_world_id()` for the no-profile-
    means-no-write guarantee. Never allowed to affect the response: a
    store I/O error, a corrupt-store `WorldModelError`, or any other
    world_model failure is swallowed here exactly like daemon.py's
    dispatch-level `except Exception` guard -- a persistence hiccup must
    never fail the `tw do`/`tw read`/`tw screen`/`tw state` response the
    caller is waiting on -- but is no longer silent: see
    `_log_world_model_failure` (mack Finding 4). Two independent write
    paths, each independently guarded so a failure in one never blocks
    the other:

    - The single-sector `parse_state()` mapping -- gated on `parse_state`
      having found a real `sector` to attribute the reading to
      (`write_from_state`'s own no-sector-means-no-write guard) AND
      (mack round-3 finding) on `is_genuine_sector_status` finding that
      sector's line-start match co-occurring with a sibling status-block
      marker (`Ports :` / `Warps to Sector(s) :`) immediately beneath
      it. Round 2's line-anchored `_SECTOR_RE` only required the forged
      "Sector : N" be alone on ITS line, not alone on the SCREEN -- a
      line-isolated forgery inside an otherwise-narrative block (a
      planet-comment/bulletin post) still won last-match-wins over an
      earlier, genuine status line elsewhere on the same screen. See
      `state_parser.is_genuine_sector_status`'s docstring for the full
      provenance rationale (mirrors `classify._is_genuine_cim_report`'s
      shape-not-text-match philosophy).
    - The batch `parse_port_report()` mapping -- mack Finding 2: this
      used to run unconditionally on every response text with zero
      provenance check, so any screen merely REPRODUCING a CIM report's
      header/footer punctuation (a help screen quoting it as a worked
      example, a forged chat broadcast) got ingested as real sector
      data. Now gated on `classify_screen` returning the dedicated
      `cim_report` classification (see `classify._is_genuine_cim_report`'s
      docstring for what "genuine" means) -- text-matching the report's
      own shape is never trusted as the provenance signal by itself.
    - The docked commerce-report mapping (WO-FA2b, world-model.md's
      Write Hooks: "every parsed game-state read (sector, port
      commodities) writes its sector's port field"): a docked "Commerce
      report for <name>:" screen carries NO "Sector : N" line of its own
      (see `state_parser.is_genuine_port_report`'s module comment for the
      full rationale). WO-FA2b REVISE (mack CRITICAL): the original
      design anchored this to a cross-screen `session.last_genuine_sector`
      set the last time a genuine sector-status screen was parsed -- but
      pyte has NO scrollback (a fixed viewport only), so a long
      warp-then-dock burst can scroll the "Sector : N" line off the
      settled grid before that branch ever runs, leaving the anchor
      stale (or, on a fresh connection, unset) while the commerce report
      still arrives -- misattributing real port data to a stale/wrong
      sector, and never resetting across a `session.reconnect()` either.
      Anchors instead to `state_parser.sector_from_command_prompt(text)`
      -- THIS SAME SCREEN's own trailing ship Command prompt, which
      (see that function's docstring) survives exactly the scroll-off
      case that broke the cross-screen anchor. Gated on
      `is_genuine_port_report(text)` AND a command-prompt sector actually
      being present on this screen -- absent (an unusual dock flow, or a
      classic-shape TWGS server with no `[NNNN]` segment) means there's
      no sector to attribute the reading to -- silently skipped, same
      "nothing to write, not a failure" convention `write_from_state`'s
      own no-sector guard already uses; the write itself is still wrapped
      in the same `except Exception` swallow-and-log guarantee as the
      other two paths."""
    wid = _current_world_id(session)
    if wid is None:
        return
    if is_genuine_sector_status(text):
        try:
            world_model.write_from_state(wid, parsed_state)
        except Exception as exc:  # noqa: BLE001 -- a world-model write must never fail the response
            _log_world_model_failure(session, "write_from_state", exc)

    if classify_screen(text, prompt) == "cim_report":
        try:
            records = parse_port_report(text)
            if records:
                world_model.bulk_upsert(wid, records)
        except Exception as exc:  # noqa: BLE001 -- same guarantee for the batch path
            _log_world_model_failure(session, "bulk_upsert", exc)

    if is_genuine_port_report(text):
        anchor_sector = sector_from_command_prompt(text)
        parsed_port = parsed_state.get("port")
        if anchor_sector is not None and parsed_port:
            try:
                world_model.write_port_only(wid, anchor_sector, parsed_port)
            except Exception as exc:  # noqa: BLE001 -- same guarantee for this path too
                _log_world_model_failure(session, "write_port_only", exc)


def build_response(session, rows=None, settled_reason=None, extra=None):
    color = None
    if rows is None:
        # The common path: current settled screen, text+color captured
        # together (D13) so they can't drift out of alignment.
        rows, color = session.render_with_color()
    text = session.render_text(rows)
    prompt = rows[-1].strip() if rows else ""
    parsed_state = parse_state(text)
    resp = {
        "ok": True,
        "screen": rows,
        "color": color,
        "prompt": prompt,
        "classification": classify_screen(text, prompt),
        "state": parsed_state,
        # TX channel ("Core transparency", TUI-POLISH-PLAN.md) + attach's
        # MANUAL-mode caret -- both optional on the session surface
        # (getattr/hasattr-guarded like server.watch_hub/server.ledger
        # elsewhere in this module) so a bare fake-session test harness
        # that predates these fields doesn't have to grow them just to
        # keep building a response.
        "sent_input": getattr(session, "last_sent", None),
        "cursor": session.cursor_pos() if hasattr(session, "cursor_pos") else None,
    }
    if settled_reason is not None:
        resp["settled_reason"] = settled_reason
    if extra:
        resp.update(extra)
    # TW-06/TW-25 world-model write-hook (knowledge/architecture/world-
    # model.md's Write Hooks section): every parsed game-state read
    # feeds the per-world sector store as a pure side effect -- see
    # _write_world_model()'s docstring for the swallow-guard this relies
    # on never being able to fail the response above.
    _write_world_model(session, text, prompt, parsed_state)
    # WO-FA7a: passive credits-supervision capture, independent of
    # _write_world_model()'s no-profile-means-no-write guard above -- see
    # `Session.observe_credits()`'s own docstring (session.py) for why this
    # is a sibling call, not folded inside `_write_world_model`, and for the
    # full list of every other autonomous settled-screen site that also
    # calls it (skills.py's replay_skill/play_skill, crawl_driver.py).
    # hasattr-guarded like cursor/sent_input above -- a bare fake-session
    # test double that predates this method doesn't have to grow it just
    # to keep building a response.
    if hasattr(session, "observe_credits"):
        session.observe_credits(text)
    if hasattr(session, "observe_turns"):
        session.observe_turns(text)
    if hasattr(session, "observe_fighters"):
        session.observe_fighters(text)
    # WO-FRAMES-0: persist full 80×25 raw grid for post-mortem grep
    # (Option?/qty prompts). Optional on the session — tests without a
    # recorder keep working; never fails the response.
    recorder = getattr(session, "frame_recorder", None)
    if recorder is not None:
        recorder.record(
            session,
            cropped_rows=rows,
            settled_reason=settled_reason,
            classification=resp["classification"],
            prompt=prompt,
            state=parsed_state,
        )
    return resp


def dispatch(session, verb, args, server):
    if verb == "screen":
        rows = session.render_raw() if args.get("raw") else None
        return build_response(session, rows=rows)

    if verb == "do":
        with _driving_dispatch(server) as lock_error:
            if lock_error is not None:
                return lock_error
            text = args.get("input", "")
            enter = args.get("enter", True)
            secret = args.get("secret", False)
            wait_prompt = args.get("wait_prompt")
            pre_text = session.render_text(session.render())
            try:
                session.send(text, enter=enter, secret=secret)
                reason, elapsed = session.wait_settle(
                    wait_prompt=wait_prompt,
                    timeout=args.get("timeout", 8.0),
                    debounce_ms=args.get("debounce_ms", 350),
                )
            except re.error as e:
                return {"ok": False, "error": f"bad_wait_prompt_regex:{e}"}
            resp = build_response(session, settled_reason=reason, extra={"elapsed": elapsed})
            history_args = {**args, "input": "<redacted>"} if secret else args
            session.record_history("do", history_args, resp["prompt"], resp["classification"], reason)
            # WO-CLEANPREEMPT FIX 1 (cipher-confirmed Concern-1): default
            # actor="ai", mirroring haggle's own explicit actor="trainer"
            # below -- NEVER `_current_actor()`'s live-mode derivation.
            # `_driving_dispatch` only ever reaches this line while THIS
            # dispatch legitimately acquired the driver slot under
            # ai_pilot mode (acquire_driver()'s own atomic mode+slot
            # check), so the true originating actor is unconditionally
            # "ai" regardless of whether mode has since flipped to
            # MODE_HUMAN (a fence, not a refusal -- see control_lock.py).
            # Explicit args.actor=="human" is the spectate idle-prompt
            # overlay escape hatch (operator answered from the TUI) --
            # the future branch `_current_actor`'s docstring anticipated.
            # `_current_actor()`'s human-branch reading mode AT
            # LEDGER-WRITE TIME (post-fence) was the corrupted signal
            # spectate_layout.compute_autonomy_ratio() consumed --
            # `interrupted_by_human` is the correct, authoritative flag
            # for that instead.
            ledger_actor = "human" if args.get("actor") == "human" else "ai"
            _record_ledger(
                server, session, pre_text, text, secret, resp,
                actor=ledger_actor, interrupted_by_human=_driver_was_fenced(server),
            )
            _record_skill_step(server, text, wait_prompt, resp["classification"], secret)
            return resp

    if verb == "send":
        with _driving_dispatch(server) as lock_error:
            if lock_error is not None:
                return lock_error
            text = args.get("input", "")
            enter = args.get("enter", True)
            secret = args.get("secret", False)
            pre_text = session.render_text(session.render())
            session.send(text, enter=enter, secret=secret)
            resp = build_response(session)
            # WO-CLEANPREEMPT FIX 1: same explicit actor="ai" as `do`
            # above -- see that block's comment for the full rationale.
            _record_ledger(
                server, session, pre_text, text, secret, resp,
                actor="ai", interrupted_by_human=_driver_was_fenced(server),
            )
            _record_skill_step(server, text, None, resp["classification"], secret)
            return resp

    if verb == "read":
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
        # D13 discipline: one render() call, threaded into render_text()
        # -- calling render() and render_text() with no rows separately
        # would be two independent lock acquisitions racing a byte
        # arriving in between (same hazard render_with_color()'s own
        # docstring warns about for text+color).
        rows = session.render()
        text = session.render_text(rows)
        prompt = rows[-1].strip() if rows else ""
        parsed_state = parse_state(text)
        # mack Finding 5: `tw state` observes the current sector just
        # like `do`/`read`/`screen` do, but never fed the world-model
        # write-hook at all -- an inconsistent coverage gap for a verb
        # explicitly meant for cheap polling. Dedup (Finding 3a) makes
        # this effectively free on the common no-change-since-last-poll
        # case.
        _write_world_model(session, text, prompt, parsed_state)
        # WO-FA7a: same passive credits capture as build_response() above
        # -- `tw state` is explicitly the cheap-polling verb, so it must
        # feed the credits-supervision surface too, not just build_response's
        # do/read/screen path. hasattr-guarded, same reason as build_response.
        if hasattr(session, "observe_credits"):
            session.observe_credits(text)
        if hasattr(session, "observe_turns"):
            session.observe_turns(text)
        if hasattr(session, "observe_fighters"):
            session.observe_fighters(text)
        return {"ok": True, "state": parsed_state}

    if verb == "history":
        n = args.get("n", 20)
        return {"ok": True, "history": session.history[-n:]}

    if verb == "status":
        rows = session.render()
        text = session.render_text(rows)
        prompt = rows[-1].strip() if rows else ""
        watch_hub = getattr(server, "watch_hub", None)
        lock = getattr(server, "control_lock", None)
        player = getattr(server, "loop_player", None)
        # Cross-seat trace transport (WO-P2d, additive/dry-run-only):
        # `None` on every real daemon TODAY, since every shipped profile
        # keeps `autonomous` at its default `False` -- but no longer
        # structurally deferred: WO-FA6 wires `ensure`'s post-login
        # `_maybe_auto_start_after_ensure` to fill this same slot the
        # instant an operator arms a profile with `autonomous = true` (see
        # that function's own docstring), same as a manual `autopilot_
        # start` already does. A caller (the spectate Decisions panel)
        # must never special-case a missing key, same null-safe
        # convention as `play` above.
        autopilot_engine = getattr(server, "autopilot_engine", None)
        autopilot_trace = None
        if autopilot_engine is not None:
            trace_log = autopilot_engine.trace_log()
            if trace_log:
                autopilot_trace = trace_log[-1]  # most-recent tick only -- see AutopilotEngine.trace_log()
        # Explicit AutopilotLoop snapshot (WO-STATUS-AUTOLOOP-FIELD):
        # consumers previously inferred running state from mode +
        # autopilot_trace only. Always present; defaults when no loop.
        autopilot_loop = getattr(server, "autopilot_loop", None)
        if autopilot_loop is not None and hasattr(autopilot_loop, "snapshot"):
            _ap_snap = autopilot_loop.snapshot()
            autopilot_status = {
                "running": bool(_ap_snap.get("running")),
                "ticks_done": int(_ap_snap.get("ticks_done") or 0),
                "last_error": _ap_snap.get("last_error"),
                "last_reason": _ap_snap.get("last_reason"),
            }
        else:
            autopilot_status = {
                "running": False,
                "ticks_done": 0,
                "last_error": None,
                "last_reason": None,
            }
        # WO-FA7a revise 3 (mack-confirmed HIGH), superseded by WO-FA-SAFE
        # (hub-ratified revise, item 2): snapshotted into LOCALS once,
        # here, BEFORE `time.monotonic()` is read below for
        # `credits_age_ms` -- a concurrent `observe_credits()` write
        # landing a NEWER ts in the gap between this snapshot and the
        # later `time.monotonic()` call would otherwise make `now < ts`
        # possible, producing a negative "age" (mack: reproduced under
        # thread stress). Snapshotting first means a race can only ever
        # bias the reported age LARGER (staler), never negative -- the
        # field's whole point is a non-negative staleness signal.
        #
        # `_cbal`/`_cts` now come from ONE atomic `credits_snapshot()` call
        # (session.py, Rook must-fix #3) rather than two SEPARATE unlocked
        # `getattr()`s (`last_credits_ts` here, `last_credits` later at the
        # `"credits"` key below) -- the two-getattr shape could itself
        # return a torn pair (an old balance paired with a new ts, or vice
        # versa) if a write landed between them; a single locked read
        # closes that regardless of which field this dict happens to
        # reference first. hasattr-guarded for a bare fake-session test
        # double that predates the credits-supervision surface entirely
        # (e.g. test_world_model_integration.py's FakeSession) -- reads as
        # `(None, None)`, the same clean default the two separate
        # `getattr()`s already gave it.
        if hasattr(session, "observe_credits"):
            session.observe_credits(text)
        if hasattr(session, "observe_turns"):
            session.observe_turns(text)
        if hasattr(session, "observe_fighters"):
            session.observe_fighters(text)
        # Snapshot AFTER the observe above (same thread) so a ship-info
        # screen already on the viewport seeds status without a send.
        # Still ONE atomic pair each — never two unlocked getattrs —
        # then age is computed from that pair (WO-FA-SAFE race shape).
        if hasattr(session, "credits_snapshot"):
            _cbal, _cts = session.credits_snapshot()
        else:
            _cbal, _cts = None, None
        if hasattr(session, "turns_snapshot"):
            _tbal, _tts = session.turns_snapshot()
        else:
            _tbal, _tts = None, None
        if hasattr(session, "fighters_snapshot"):
            _fbal, _fts = session.fighters_snapshot()
        else:
            _fbal, _fts = None, None
        _mode = lock.mode if lock is not None else MODE_AI_PILOT
        _credits_age_ms = (
            int((time.monotonic() - _cts) * 1000) if _cts is not None else None
        )
        _turns_age_ms = int((time.monotonic() - _tts) * 1000) if _tts is not None else None
        _fighters_age_ms = (
            int((time.monotonic() - _fts) * 1000) if _fts is not None else None
        )
        _intervention = _build_status_intervention(
            mode=_mode,
            autopilot_status=autopilot_status,
            credits=_cbal,
            credits_age_ms=_credits_age_ms,
            fighters_aboard=_fbal,
            fighters_age_ms=_fighters_age_ms,
        )
        return {
            "ok": True,
            "connected": session.conn.connected,
            "idle_ms": int((time.monotonic() - session.last_rx) * 1000),
            "classification": classify_screen(text, prompt),
            "prompt": prompt,
            "host": session.host,
            "port": session.port,
            "name": session.name,
            "subscribers": watch_hub.subscriber_count() if watch_hub else 0,
            # Explicit, observable control-MODE state (interactive-attach
            # addendum, extensible enum -- see control_lock.py): one of
            # "ai_pilot" (default), "human" (a `tw attach` session has
            # the keyboard), "auto_loop" (LoopPlayer driving solo),
            # "spectate" (paused).
            "mode": _mode,
            # AUTO-LOOP live progress (Trainer Control Panel) -- present
            # even when nothing has ever run this daemon session (all
            # fields default/None then), so a caller never has to
            # special-case "field missing" vs "nothing running".
            "play": player.snapshot() if player is not None else None,
            # See autopilot_engine/autopilot_trace computed above.
            "autopilot_trace": autopilot_trace,
            # WO-STATUS-AUTOLOOP-FIELD: explicit loop snapshot (additive).
            "autopilot": autopilot_status,
            # WO-FA7a passive credits-supervision surface (E2 supervised-run
            # prerequisite): the last credits balance `Session.
            # observe_credits()` saw on any settled screen (see its
            # docstring, session.py, for every site that feeds it -- the
            # two dispatch chokepoints below plus skills.py's replay_skill/
            # play_skill and crawl_driver.py), plus its own capture ts --
            # both sourced from the ONE `credits_snapshot()` read above
            # (WO-FA-SAFE, item 2), so this pair is always internally
            # consistent even under a concurrent `observe_credits()` write
            # -- never two independently-racing `getattr()`s. `credits_ts`
            # is a raw `time.monotonic()` reading -- only meaningful for
            # cross-poll change-detection WITHIN this one daemon process (a
            # caller comparing it to a PRIOR `credits_ts` it already
            # holds), never as an absolute age: an external `tw status`
            # caller (a separate process, or a fresh `tw` invocation) has
            # no reference to the daemon's own monotonic clock to diff it
            # against. `credits_age_ms` below is the externally-meaningful
            # staleness signal -- see its own comment.
            "credits": _cbal,
            "credits_ts": _cts,
            # WO-FA7a revise 2 (team-lead-caught contract gap): a COMPUTED
            # age, mirroring `idle_ms` above (`int((time.monotonic() -
            # session.last_rx) * 1000)`) rather than the raw `credits_ts` --
            # the DoD's "ts exposes staleness" only actually holds for a
            # value the caller can read on its own, with no daemon-clock
            # reference of its own needed. `None` when no balance has ever
            # been captured (`_cts` still `None`). Computed from the SAME
            # `_cts` snapshot as `credits_ts`/`credits` above (WO-FA7a
            # revise 3 / WO-FA-SAFE item 2) -- see the snapshot's own
            # comment for why capturing it BEFORE this `time.monotonic()`
            # call, rather than re-reading it here, is what keeps this age
            # from ever going negative under a concurrent
            # `observe_credits()` write.
            "credits_age_ms": _credits_age_ms,
            # WO-HUD-CREDITS-TURNS-JOIN: sticky turn COUNT for spectate HUD
            # seed (mirrors credits/credits_age_ms). Never the TL timer.
            "turns_left": _tbal,
            "turns_age_ms": _turns_age_ms,
            "fighters_aboard": _fbal,
            "fighters_age_ms": _fighters_age_ms,
            # WO-AICLIENT-WS5-INTERVENTION: read-only spectator/trainer feed.
            "intervention": _intervention,
            # WO-TUI-METRICS: spectate's live METRICS gutter keys off the
            # active session's world_id (see `_current_world_id()`); the
            # sole-directory heuristic breaks once a second world store
            # exists on disk (e.g. crawl_sac + crawl_geek both crawled).
            "world_id": _current_world_id(session),
        }

    if verb == "set_mode":
        # A plain, non-exclusive mode switch -- see control_lock.py's
        # module docstring for why this is a clean one-shot verb (no
        # connection lifetime involved) distinct from take_human()'s
        # exclusive, connection-scoped path. This is the seam the
        # forthcoming Trainer Control Panel's mode selector calls.
        lock = getattr(server, "control_lock", None)
        if lock is None:
            return {"ok": False, "error": "control_lock_unavailable"}
        new_mode = args.get("mode")
        try:
            lock.set_mode(new_mode)
        except ValueError as e:
            return {"ok": False, "error": f"invalid_mode:{e}"}
        except ControlModeConflict as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True, "mode": lock.mode}

    if verb == "stop":
        server.request_stop()
        return {"ok": True, "stopping": True}

    if verb == "ensure":
        # Safety fix: `ensure` drives the login automaton (a keystroke-
        # sending verb, same as do/send/replay/play/haggle) but was
        # dispatched with no control-lock gate at all -- it could inject
        # a keystroke even while a human held MODE_HUMAN via `tw attach`.
        # Same shared guard those five verbs already use (see
        # `_driving_dispatch`'s docstring): refuses under MODE_HUMAN/
        # MODE_AUTO_LOOP, still succeeds under the default ai_pilot mode.
        with _driving_dispatch(server) as lock_error:
            if lock_error is not None:
                return lock_error
            resp = _dispatch_ensure(session, args)
        # WO-FA6 / WO-AUTOPILOT-AFTER-ENSURE: post-ensure auto-start for
        # `profile.autonomous` profiles. Fires on ANY successful `ensure`
        # (genuine login OR already_there) so a mid-session `tw ensure`
        # arms live_tick without a manual `autopilot start` / `play`.
        #
        # Sticky-halt is the sole anti-resurrect gate: checked inside
        # `_maybe_auto_start_after_ensure` (`server.autopilot_loop is not
        # None` -- running OR halted-with-last_error). A halted loop stays
        # stashed until an explicit `autopilot_stop` clears it; routine
        # re-ensure cannot silently re-arm over that brake (mack HIGH).
        # The earlier genuine-connect-only gate (`already_there is False`)
        # blocked the mid-session arm the WO accepts, and also false-
        # negatived when a pre-classify HUD I-probe left the session
        # already at target after a one-step login fixture.
        #
        # Deliberately fired AFTER the `with` block above has released the
        # active-driver slot, never from inside it: `AutopilotLoop.start()`
        # -> `control_lock.enter_auto_loop()` raises `ControlModeConflict
        # ("locked_by_active_driver")` outright while `_driving_dispatch`
        # still holds that slot (see control_lock.py's `enter_auto_loop`/
        # `acquire_driver` docstrings) -- attempting this INSIDE the `with`
        # above would make every auto-start attempt silently decline, never
        # actually arming. Mirrors `_dispatch_autopilot_start`'s own shape:
        # that dispatch is likewise never wrapped in `_driving_dispatch`,
        # for the identical reason.
        if resp.get("ok") and not args.get("no_auto_arm"):
            _maybe_auto_start_after_ensure(server, session, args.get("profile"))
        return resp

    if verb == "crawl_start":
        return _dispatch_crawl_start(server, session, args)

    # -- WO-P1-d: §22/§23 autonomous goal-orchestrator (autopilot.py) ----
    if verb == "autopilot_preview":
        return _dispatch_autopilot_preview(server, session, args)

    if verb == "autopilot_start":
        return _dispatch_autopilot_start(server, session, args)

    if verb == "autopilot_stop":
        return _dispatch_autopilot_stop(server)

    # -- v2.1 item 11: macro/recording/pattern-learning verbs -----------
    if verb == "record_start":
        return _dispatch_record_start(server, session, args)

    if verb == "record_stop":
        return _dispatch_record_stop(server)

    if verb == "replay":
        with _driving_dispatch(server) as lock_error:
            if lock_error is not None:
                return lock_error
            return _dispatch_replay(server, session, args)

    if verb == "mine":
        return _dispatch_mine(args)

    if verb == "play":
        with _driving_dispatch(server) as lock_error:
            if lock_error is not None:
                return lock_error
            return _dispatch_play(server, session, args)

    if verb == "haggle":
        with _driving_dispatch(server) as lock_error:
            if lock_error is not None:
                return lock_error
            return _dispatch_haggle(server, session, args)

    # -- Trainer Control Panel: Learned-Loops Library + AUTO-LOOP background
    # driver (TUI-POLISH-PLAN.md) -------------------------------------------
    if verb == "list_skills":
        return _dispatch_list_skills(server, args)

    if verb == "play_start":
        return _dispatch_play_start(server, args)

    if verb == "play_stop":
        return _dispatch_play_stop(server)

    if verb == "play_pause":
        return _dispatch_play_pause(server)

    if verb == "play_resume":
        return _dispatch_play_resume(server)

    return {"ok": False, "error": f"unknown_verb:{verb}"}


def _record_ledger(server, session, pre_text, input_text, secret, resp, actor=None, interrupted_by_human=False):
    """C1 hook: every `do`/`send`/`haggle` dispatch appends one
    Trace-Ledger entry (twclient/ledger.py), tagged with the
    currently-open `tw record` capture name if any, plus TW-05's
    actor/session_id attribution. `actor=None` (do/send's case) derives
    the actor from mode via `_current_actor()`; a caller with its own
    fixed attribution (haggle -- a deterministic, no-LLM engine per
    knowledge/architecture/autonomy-loop.md's own "trainer" definition)
    passes an explicit override instead. `server.ledger` is absent in
    tests that build a bare dispatch harness -- silently a no-op then,
    same convention as `status`'s `getattr(server, "watch_hub", None)`.

    `interrupted_by_human` (WO-CLEANPREEMPT, additive on top of TW-05's
    actor fields) -- True when this dispatch's own driver slot was
    fenced mid-flight by a `tw attach` taking control out from under it
    (see `_driver_was_fenced()`); every do/send/haggle call site computes
    it fresh right before calling here. Passed straight through to
    `ledger.record_do()` so a pattern-learning consumer can exclude a
    corrupted action->outcome mapping instead of silently trusting it."""
    ledger = getattr(server, "ledger", None)
    if ledger is None:
        return
    capture = None
    recorder = getattr(server, "skill_recorder", None)
    if recorder is not None:
        capture = recorder.active_name
    post_text = "\n".join(resp["screen"])
    ledger.record_do(
        pre_text,
        input_text,
        secret,
        post_text,
        resp["classification"],
        capture=capture,
        actor=actor if actor is not None else _current_actor(server),
        session_id=_current_session_id(session),
        interrupted_by_human=interrupted_by_human,
    )


def record_attach_keystroke(server, session, pre_text, input_text, secret):
    """WO-CLEANPREEMPT: routes a `tw attach` keystroke into the same
    Trace-Ledger every do/send/haggle dispatch already writes to --
    `actor="human"`, the branch `_current_actor()`'s own docstring has
    anticipated since TW-05 ("routing send_raw()'s attach keystrokes
    through the same ledger sink"). Called by daemon.py's
    `CommandHandler._handle_attach` right after `session.send_raw()`
    returns -- an attach connection never re-enters the one-shot verb
    `dispatch()` at all (see `_handle_attach`'s own docstring), so this
    is a second, parallel entry point onto the SAME ledger sink, not a
    new branch of `_record_ledger`. No leading underscore (unlike this
    module's other dispatch-internal helpers): this is the one function
    here another module (daemon.py) calls directly.

    There is no `resp`-shaped `build_response()` result to read
    `post_text`/`classification` from here, unlike `_record_ledger`'s
    do/send/haggle callers -- attach's live screen streams over a
    SEPARATE `subscribe` connection (interactive_app.SpectateClient),
    never through this request/response path -- so this reads the
    post-send screen itself, immediately, with no `wait_settle` (an
    interactive keystroke is never "settled"; the same immediacy the
    `send` verb's own ledger write already accepts).

    `secret` (WO-CLEANPREEMPT secret sub-diff) is now a REQUIRED
    parameter, not derived here at all: mack's staleness finding showed
    deriving it from `pre_text` (captured in `_handle_attach` BEFORE
    `send_raw()`'s own up-to-10s fence-wait) could under-redact against
    a screen that transitioned to a secret prompt DURING that wait. The
    caller passes `session.last_sent_secret` -- the SAME send-time
    decision (`classify.is_probable_secret_prompt()` against the CURRENT
    screen, evaluated inside `send_raw()` right before the byte hit the
    wire) that already gated the transcript LOG sink
    (`TelnetConnection.send_bytes(secret=...)`) -- so both sinks agree,
    always, by construction, never two independent derivations that
    could disagree. `ledger.record_do()`'s existing secret branch
    (input/prompt both -> "<redacted>") does the actual redaction from
    there (TW-02b invariant: a human-typed secret must never land
    cleartext in the ledger)."""
    ledger = getattr(server, "ledger", None)
    if ledger is None:
        return
    post_text = session.render_text(session.render())
    post_lines = post_text.splitlines()
    post_prompt = post_lines[-1].strip() if post_lines else ""
    settled_class = classify_screen(post_text, post_prompt)
    ledger.record_do(
        pre_text,
        input_text,
        secret,
        post_text,
        settled_class,
        actor="human",
        session_id=_current_session_id(session),
    )


def _record_skill_step(server, input_text, wait_prompt, post_class, secret):
    """C3 hook: while a `tw record` capture is open, also accumulate this
    step into the in-progress skill (twclient.skills.SkillRecorder)."""
    recorder = getattr(server, "skill_recorder", None)
    if recorder is None or not recorder.recording:
        return
    recorder.record_step(input_text, wait_prompt, post_class, secret=secret)


def _dispatch_record_start(server, session, args):
    """TW-03 wiring: a new capture's `start_anchor` is the sector the
    caller is standing in RIGHT NOW (parse_state on the current settled
    text) -- computed here, at the one place a `tw record start` capture
    begins, rather than asked of the caller; `None` when the current
    screen doesn't parse a sector (e.g. mid-login), same as any other
    unparseable-state case elsewhere in this module."""
    from .skills import SkillError

    recorder = getattr(server, "skill_recorder", None)
    if recorder is None:
        return {"ok": False, "error": "recording_unavailable"}
    text = session.render_text(session.render())
    start_anchor = parse_state(text).get("sector")
    try:
        name = recorder.start(args.get("name"), start_anchor=start_anchor)
    except SkillError as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, "recording": name}


def _dispatch_record_stop(server):
    recorder = getattr(server, "skill_recorder", None)
    if recorder is None:
        return {"ok": False, "error": "recording_unavailable"}
    result = recorder.stop()
    if result is None:
        return {"ok": False, "error": "not_recording"}
    return {"ok": True, **result}


def _dispatch_replay(server, session, args):
    """TW-03/TW-04 wiring: `force` is the caller's explicit opt-in to
    waive a missing/legacy `start_anchor` (see skills._check_start_anchor
    -- never bypasses a DETECTED mismatch); `ledger`/`session_id` route
    every replayed step into the same Trace-Ledger this daemon's
    do/send/haggle dispatches already write to, tagged `actor="trainer"`
    by replay_skill itself. `server.ledger` is absent in bare
    dispatch-harness tests -- same getattr(..., None) no-op convention
    as `_record_ledger`.

    WO-CLEANPREEMPT (multi-step fence, mack's repro): this dispatch
    reserves the driver slot (`_driving_dispatch`, one `acquire_driver()`
    call, protocol.py's "replay" verb block) for the WHOLE multi-step
    run, not per-step -- so a `tw attach` racing in mid-replay fences the
    entire run once, and `replay_skill()` must keep re-checking that
    fence at every step boundary rather than firing every remaining
    step's send regardless (see `replay_skill`'s own docstring).
    `is_driver_fenced=lambda: _driver_was_fenced(server)` wires that
    check through; `ReplayFenced` (distinct from `ReplayDivergence` --
    an orderly human preemption, not "reality disagreed") gets its own
    clean `"human_fenced"` error, never folded into `"divergence"`."""
    from .skills import ReplayDivergence, ReplayFenced, SkillError, load_skill, replay_skill

    name = args.get("name")
    if not name:
        return {"ok": False, "error": "missing_name"}
    try:
        skill = load_skill(name)
        results = replay_skill(
            session,
            skill,
            params=args.get("params") or {},
            step_timeout=args.get("step_timeout", 8.0),
            force=args.get("force", False),
            ledger=getattr(server, "ledger", None),
            session_id=_current_session_id(session),
            is_driver_fenced=lambda: _driver_was_fenced(server),
        )
    except ReplayFenced as e:
        return {"ok": False, "error": "human_fenced", **e.as_dict()}
    except ReplayDivergence as e:
        return {"ok": False, "error": "divergence", **e.as_dict()}
    except SkillError as e:
        # A missing/legacy start_anchor (skills._check_start_anchor) also
        # raises SkillError, same as load_skill's own not-found/corrupt
        # cases -- one shared try block, matching _dispatch_play's
        # existing convention below, so both raise shapes get the same
        # clean {"ok": False, "error": "..."} instead of falling through
        # to daemon.py's generic internal_error catch-all.
        return {"ok": False, "error": str(e)}
    return {"ok": True, "name": name, "results": results}


def _dispatch_mine(args):
    from .miner import mine_ledger

    result = mine_ledger(min_support=args.get("min_support", 2))
    return {"ok": True, **result}


def _dispatch_play(server, session, args):
    """TW-03/TW-04 wiring -- same `force`/`ledger`/`session_id` contract
    as `_dispatch_replay` above, forwarded into every cycle's
    `replay_skill()` call by `play_skill` itself.

    WO-CLEANPREEMPT: same `is_driver_fenced` wiring as `_dispatch_replay`
    -- `play_skill()` already catches its own `ReplayFenced` internally
    (same shape as its existing `ReplayDivergence` handling) and reports
    `"halted": "human_fenced"` as part of `result`, so no new `except`
    clause is needed here either."""
    from .skills import SkillError, load_skill, play_skill

    name = args.get("name")
    if not name:
        return {"ok": False, "error": "missing_name"}
    try:
        skill = load_skill(name)
        result = play_skill(
            session,
            skill,
            cycles=args.get("cycles", 1),
            floor=args.get("floor"),
            params=args.get("params") or {},
            step_timeout=args.get("step_timeout", 8.0),
            force=args.get("force", False),
            ledger=getattr(server, "ledger", None),
            session_id=_current_session_id(session),
            is_driver_fenced=lambda: _driver_was_fenced(server),
        )
    except SkillError as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, "name": name, **result}


def _dispatch_haggle(server, session, args):
    """DESIGN-v2.md §9: deterministic auto-haggle, NO LLM. Negotiates the
    OFFER sub-dialogue the session must already be sitting at (quantity/
    commodity selection is the caller's job via ordinary `do` calls,
    same as any other port-trade step) -- see haggle.run_haggle for the
    strategy contract. Recorded as ONE Trace-Ledger entry for the whole
    negotiation (like a `do`, not like each of login.py's internal
    sends -- a haggle round-trip is the meaningful caller-visible
    action, not each individual round)."""
    from .haggle import run_haggle
    from .settle import wait_until_settled

    # P0 finding 5: gate this capture on the SAME freshness check
    # run_haggle's own opening read uses (haggle.py's `wait_until_settled`
    # pre-send gate) rather than reading `session.render()` the instant
    # this dispatch is entered -- an ungated read here can grab a
    # still-transitional frame that doesn't match the settled screen
    # haggle actually negotiated against, corrupting the ledger's
    # pre_state baseline (e.g. silently omitting a credits reading that
    # WAS present a beat later). Uses haggle.py's own gate defaults, so
    # in the overwhelmingly common case (nothing changes between this
    # call and run_haggle's own internal gate a moment later) it
    # resolves instantly -- run_haggle's gate then finds the SAME
    # already-quiet screen and settles immediately too, never a
    # double wait in practice.
    wait_until_settled(session)
    pre_text = session.render_text(session.render())
    result = run_haggle(
        session,
        fair_value=args.get("fair_value"),
        accept_threshold_pct=args.get("accept_threshold_pct", 5.0),
        open_aggression_pct=args.get("open_aggression_pct", 15.0),
        round_cap=args.get("round_cap", 4),
        step_timeout=args.get("step_timeout", 8.0),
    )
    resp = build_response(session, extra={"haggle": result})
    input_desc = f"<haggle:{result['outcome']}>"
    # TW-05: haggle is the deterministic, no-LLM engine autonomy-loop.md
    # names explicitly as a "trainer" example -- never the mode-derived
    # "ai" default `_current_actor()` would otherwise give it.
    _record_ledger(
        server,
        session,
        pre_text,
        input_desc,
        False,
        resp,
        actor="trainer",
        interrupted_by_human=_driver_was_fenced(server),
    )
    return resp


def _dispatch_crawl_start(server, session, args):
    """TW-26 live-crawl driver wiring. Gated behind TWO independent
    checks, in order: a fast, up-front `crawl_sacrificial` check on the
    loaded profile (a clear, cheap refusal before the driver slot is
    even reserved for a request that's going to be refused anyway — same
    "fast hint, not the source of truth" discipline `_control_lock_error`
    uses one layer above `acquire_driver()`), then `_driving_dispatch`
    (server) — the SAME ai_pilot driving-lock guard do/send/replay/play/
    haggle already share — so a crawl is refused outright, never queued,
    if a human attach or another driver (including a second concurrent
    crawl) currently holds the connection. `crawl_driver.run_live_crawl`
    re-checks `crawl_sacrificial` itself, structurally, regardless of
    this fast check ever running at all — that is the true, authoritative
    gate (see its own docstring).

    Synchronous: this dispatch blocks the calling one-shot connection for
    the crawl's full duration, mirroring `_dispatch_play`'s/
    `_dispatch_haggle`'s own shape (not loop_player.py's background-
    thread model — a backgrounded crawl is a natural follow-up, not
    built here). There is currently no live cross-connection abort
    channel over the wire protocol (`abort_check=None` below) — a JSON
    request/response round trip has no way to carry a callable, and this
    dispatch's own driver-slot hold blocks any second connection from
    reaching a hypothetical `crawl_abort` verb until this one returns
    anyway. See the TW-26 crawl-driver handoff report's Concerns for why
    that is a deliberate, documented scope line rather than an oversight.

    `path`/`log_path` are REQUIRED, caller-resolved arguments, not
    computed here: a `crawl_sacrificial` profile paired with
    `allow_register` (WO-MS-4) may not have a fixed `handle` in
    `profiles.toml` at all (the name-bank rider draws one fresh per
    registration attempt), so this dispatch cannot always derive a
    `game_knowledge.knowledge_path()` up front the way `ensure`'s
    `_current_world_id` can for an already-registered profile. Left to
    the caller (`cli.py`'s `tw crawl`, which falls back to a per-profile
    path under `state/`/`logs/` when it can) rather than papered over
    with a guess.

    The `session_factory` handed to `run_live_crawl` here is a bare
    closure returning THIS daemon's one persistent `session` object on
    every call — NOT a fresh per-node reconnect.
    `menu_crawler.crawl_menus()`'s BFS-via-replay traversal assumes
    `session_factory()` always returns a session already sitting at the
    world's STABLE START CONTEXT (see that module's own Traversal
    docstring); a real reconnect-capable factory is explicitly flagged
    there as "a separate future lane, not this one" — this dispatch
    wires the gate/shape ahead of that lane landing, not a claim that a
    live daemon crawl is fully load-bearing yet."""
    from . import credentials
    from .crawl_driver import CrawlSafetyError, run_live_crawl

    profile_name = args.get("profile")
    if not profile_name:
        return {"ok": False, "error": "missing_profile"}
    try:
        profile = credentials.load_profile(profile_name)
    except credentials.CredentialError as e:
        return {"ok": False, "error": str(e)}
    if not getattr(profile, "crawl_sacrificial", False):
        return {"ok": False, "error": f"not_crawl_sacrificial:{profile_name}"}

    path = args.get("path")
    log_path = args.get("log_path")
    if not path or not log_path:
        return {"ok": False, "error": "missing_path_or_log_path"}

    with _driving_dispatch(server) as lock_error:
        if lock_error is not None:
            return lock_error
        try:
            result = run_live_crawl(
                profile,
                lambda: session,
                path=path,
                log_path=log_path,
                max_nodes=args.get("max_nodes", 200),
                step_timeout=args.get("step_timeout", 8.0),
                # WO-CLEANPREEMPT (multi-step fence): this dispatch holds
                # the driver slot for the crawl's ENTIRE duration, same as
                # replay/play above -- a `tw attach` racing in mid-crawl
                # stops it at the next node boundary rather than letting
                # it keep emitting keystrokes. Same `_driver_was_fenced()`
                # reader as do/send/replay/play; `run_live_crawl` already
                # has an `abort_check` seam for exactly this shape of
                # external stop, so this is a second, independent trigger
                # on the identical clean-stop path (see its docstring).
                is_driver_fenced=lambda: _driver_was_fenced(server),
            )
        except CrawlSafetyError as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True, **result}


# -- WO-P1-d: §22/§23 autonomous goal-orchestrator (autopilot.py) wiring ---
#
# `autopilot_preview` is the safe pre-enablement proof surface (dry-run,
# NEVER sends, regardless of `profile.autonomous` -- see
# `AutopilotEngine.dry_run_tick()`'s own docstring): it proves the real
# ASSESS -> SELECT pipeline runs against the CURRENT live screen/world-
# model, with zero risk. `autopilot_start`/`autopilot_stop` arm/halt the
# background `AutopilotLoop` (mirrors `_dispatch_play_start`/
# `_dispatch_play_stop`'s own shape one section up) -- `live_tick()`'s own
# fail-closed gate (`AutopilotGateError` unless `profile.autonomous` is
# True) is never bypassed here; this dispatch only ever constructs the
# engine and calls `AutopilotLoop.start()`, which raises straight through.

_AUTOPILOT_EXPLORE_TURN_BUDGET = 10  # matches spectate_app.py's own _explore_plan_for_mode budget

# WO-FA4: `trade_adapter.build_trade_hops()` is O(ports^2) (not bounded --
# FA3's own precompute measured ~9% of a 1000-port galaxy's cost even after
# that fix), so it must be refreshed per-CYCLE, never per-tick, or a large
# known galaxy would slow the tick->settle cadence into a sluggish witness
# experience. A plain time-based TTL cache (mirrors `session.last_credits`/
# `last_credits_ts`'s own attribute-pair convention, applied via
# getattr/setattr rather than a session.py edit -- see `_cached_trade_hops()`
# below) -- config-not-hardcoded per WO-FA4's explicit requirement, though
# (like `credits_stale_ms` before WO-FA-SAFE) there is no CLI-level override
# for it yet.
_DEFAULT_TRADE_HOPS_CACHE_TTL_S = 60.0


def _cached_trade_hops(session, world_id):
    """Session-scoped cache of `trade_adapter.build_trade_hops()`'s output
    -- rebuilt only once `_DEFAULT_TRADE_HOPS_CACHE_TTL_S` has elapsed since
    the last build, or `world_id` changes (a fresh `tw ensure`/profile swap
    mid-session). `getattr`/`setattr`-guarded on a plain
    `session._trade_hops_cache` attribute rather than a session.py edit --
    same "hasattr-guarded cross-module session extension" convention this
    file already uses for `observe_credits`/`credits_snapshot`/
    `cursor_pos`, just read-modify-write instead of read-only.
    Swallow-and-log on a build failure (same convention as the seed
    write/`plan_find_stardock` call in `_autopilot_snapshot_kwargs()`) -- an
    availability hiccup here must never crash a tick; a stale cached value
    (if any, for this same world_id) is kept rather than dropped to empty."""
    from . import trade_adapter

    now = time.monotonic()
    cache = getattr(session, "_trade_hops_cache", None)
    if (
        cache is not None
        and cache.get("world_id") == world_id
        and (now - cache.get("ts", 0.0)) < _DEFAULT_TRADE_HOPS_CACHE_TTL_S
    ):
        return cache["hops"]
    try:
        hops, _note = trade_adapter.build_trade_hops(world_id)
    except Exception as exc:  # noqa: BLE001 -- availability only, see docstring
        _log_world_model_failure(session, "build_trade_hops", exc)
        hops = cache["hops"] if cache is not None and cache.get("world_id") == world_id else ()
    session._trade_hops_cache = {"world_id": world_id, "ts": now, "hops": hops}
    return hops


def _autopilot_snapshot_kwargs(session):
    """Best-effort LIVE `assess()` kwargs for one autopilot tick. Also
    seeds the world-model with THIS tick's current sector/warps before
    planning off it -- see the "WO-FA1 cold-start seed" comment below.

    HONEST SCOPE NOTE (verified while wiring this, not assumed): this
    wires ONLY the explore/StarDock-hunt lane -- `world_id` -> a single
    read-only `explore.plan_find_stardock()` call, the exact same
    planner + turn-budget convention `spectate_app.py`'s own
    `_explore_plan_for_mode(mode="stardock")` already uses live (it
    naturally falls back to a Map-fill frontier hunt when no StarDock is
    landmarked yet -- see that function's own docstring), so both
    `stardock_route` and `explore_next_sector`/`explore_mode` come from
    ONE consistent plan.

    WO-FA4 wires the `hops`/`world_id`/`state_dir` lane: `trade_adapter.
    build_trade_hops()` (cached per-cycle, never per-tick -- see
    `_cached_trade_hops()`) turns this session's `world_id`'s persisted
    port records into `chains.TradeHop` edges, so `select()`'s `run_chain`
    scorer can genuinely fire on a live daemon now (previously always
    skipped -- see the paragraph below, kept for what's STILL not wired).
    `world_id`/`state_dir` are threaded straight through (never derived
    from `rendered_text`) so `AutopilotEngine._execute()` can actually
    DRIVE a chosen `run_chain` candidate via `trade_driver.run_chain()`,
    which needs both to resolve the known-graph navigation path a bare
    `TradeHop` doesn't itself carry.

    Deliberately does NOT populate `ship_catalog`/`loop`/`current_ship`:
    no adapter exists ANYWHERE in this codebase from `world_model`'s
    stored StarDock listings into `ship_upgrade_decision.ShipSpec`/
    `LoopEconomics` -- `game_data.py`'s own module docstring: "this
    project has no current-ship-name introspection yet". Building that
    bridge is a separate, substantially bigger effort than this wiring WO
    -- not invented here unreviewed. Practical consequence: `select()`'s
    `upgrade` scorer still always skips on a live daemon today (fail-
    closed by design, see `_score_upgrade()`), so a live autopilot tick
    can currently only ever choose `"run_chain"`, `"explore"`, or nothing
    (before the first sector is ever parsed) -- see this module's
    `_dispatch_autopilot_preview`/`_dispatch_autopilot_start` docstrings,
    and report this honestly rather than paper over it.

    Returns `{}` (every `assess()` default applies -- an all-empty
    `WorldSnapshot`) whenever `world_id`/the current sector can't be
    resolved: manual play with no configured `--profile`, or before the
    daemon has ever settled on a screen carrying a sector line."""
    world_id = _current_world_id(session)
    if world_id is None:
        return {}
    text = session.render_text(session.render())
    parsed = parse_state(text)
    sector = parsed.get("sector")
    if sector is None:
        return {}

    # WO-FA1 cold-start seed: guarantee the world-model already knows
    # THIS tick's current sector + its (now-complete, see state_parser's
    # WO-FA1 fix) warps BEFORE the frontier/route planners below read the
    # graph. Without this, a tick whose own settled screen was never
    # previously written via `_write_world_model` (e.g. the very first
    # tick right after login, before any `tw do`/`tw read`/`tw screen`
    # response happened to carry a genuine sector-status block) sees the
    # current sector absent from `explore.known_graph()` entirely --
    # `frontier_edges()` requires `start in graph` and returns [] outright
    # -- so `explore_next_sector` stays None forever and the very first
    # tick can never move. Reuses `_write_world_model`'s own single-sector
    # write path/gate exactly (`is_genuine_sector_status` +
    # `world_model.write_from_state`, same swallow-and-log failure
    # handling) -- idempotent and safe to call every tick even when the
    # same screen was already written moments earlier through the normal
    # `build_response` hook.
    #
    # FORGED-BLOCK RESIDUAL (mack/cipher adversarial re-verify, 2026-07-21,
    # documented not fixed here -- hub-tracked roadmap prerequisite): a
    # forged in-band chat/broadcast text reproducing a "Sector : N" +
    # sibling-marker block byte-for-byte can still pass
    # `is_genuine_sector_status()` (a PRE-EXISTING gap in that function,
    # not introduced by this seed -- see its own docstring's "residual"
    # section) and get seeded here as if it were the ship's real position.
    # BOUNDED today: HIGH-2's classify-gate still requires the LIVE screen
    # to classify as `main_command` before any send at all, the (a)/(b)
    # fixes above mean only an actually-adjacent target ever gets sent,
    # and EXECUTE is explore-only (never Genesis/PvP/colonist-commitment)
    # -- so a forged seed can misdirect exploration bookkeeping, never
    # trigger an unsafe send. On a SOLO/isolated game there's no other
    # player who could forge such a broadcast in the first place. This
    # stops being merely "non-exploitable today" and becomes a HARD GATE
    # the moment autonomous mode runs on a multiplayer/shared server --
    # closing it needs anchor-to-live-prompt hardening in
    # `is_genuine_sector_status()` itself, tracked as a roadmap
    # prerequisite, deliberately NOT attempted in this revise.
    if is_genuine_sector_status(text):
        try:
            world_model.write_from_state(world_id, parsed)
        except Exception as exc:  # noqa: BLE001 -- best-effort seed only, see _write_world_model's own swallow-guard
            _log_world_model_failure(session, "write_from_state", exc)

    from .explore import plan_find_stardock

    try:
        plan = plan_find_stardock(
            world_id,
            current_sector=sector,
            turn_budget=_AUTOPILOT_EXPLORE_TURN_BUDGET,
            epsilon=0.0,  # deterministic nearest-frontier pick for the trainer -- see explore.py's pick_frontier_edge
        )
    except Exception as exc:  # noqa: BLE001 -- MED fix (mack re-verify, 2026-07-21): a
        # corrupt on-disk sector file raises `world_model.WorldModelError` (a
        # plain Exception), which the old `except OSError` didn't catch --
        # an uncaught raise here would have crashed the whole autopilot tick
        # (both preview and the background AutopilotLoop's snapshot_provider)
        # over a pure READ-availability hiccup with zero safety impact (the
        # outer HIGH-2 classify-gate + the fail-closed autonomous gate are
        # what actually guard every send; this is purely "can we plan a
        # frontier at all"). Swallow-and-log, same convention as the seed
        # write immediately above.
        _log_world_model_failure(session, "plan_find_stardock", exc)
        return {}
    return {
        "stardock_route": plan.route,
        "explore_next_sector": plan.next_sector,
        "explore_mode": plan.mode,
        "hops": _cached_trade_hops(session, world_id),
        "world_id": world_id,
        "state_dir": None,
    }


def _get_or_build_autopilot_engine(server, session, profile, caps=None):
    """Lazily builds/reuses this daemon's ONE `AutopilotEngine` -- fills
    `server.autopilot_engine`'s reserved slot (daemon.py) the first time
    either `autopilot_preview` or `autopilot_start` is dispatched.

    `preview` and `start` deliberately share the SAME engine instance
    (never a disposable one-off per call) so `dry_run_tick()`'s own
    `interrupted` flag genuinely answers "would this interrupt the real
    driven history" against the actual `live_tick()` history -- exactly
    the concurrent preview-vs-live-loop scenario `AutopilotEngine`'s own
    class docstring (HIGH-3 note) already anticipates and is lock-guarded
    against.

    Rebuilt (replacing any cached engine, dropping its trace history)
    whenever the requested profile differs from the cached one's name, or
    `caps` is explicitly supplied -- both change state that's fixed at
    construction (`self.enabled`/`self.caps`), so a fresh instance is the
    only correct way to apply either change. Callers that would rebuild
    while a loop bound to the OLD engine is still running must refuse
    BEFORE calling this (see `_dispatch_autopilot_start`'s own
    `already_running` guard) -- this function has no way to know about a
    caller's separate `AutopilotLoop` object."""
    from .autopilot import AutopilotEngine, EconCaps

    existing = getattr(server, "autopilot_engine", None)
    if existing is not None and caps is None and getattr(existing.profile, "name", None) == profile.name:
        return existing
    engine = AutopilotEngine(
        session,
        profile,
        server.control_lock,
        ledger=getattr(server, "ledger", None),
        session_id=_current_session_id(session),
        caps=caps if caps is not None else EconCaps(),
    )
    server.autopilot_engine = engine
    return engine


def _dispatch_autopilot_preview(server, session, args):
    """`tw autopilot preview` -- the pre-enablement proof surface: ASSESS
    the CURRENT live screen/world-model + SELECT the highest-EV candidate,
    ZERO sends, regardless of the bound profile's `autonomous` flag (see
    `AutopilotEngine.dry_run_tick()`). `profile` is required (unlike
    `start`, there's no meaningful "run against whatever's cached"
    default here on a cold daemon) so a caller always knows exactly whose
    gate/world this decision was scored against."""
    from .autopilot import decision_to_trace

    profile_name = args.get("profile")
    if not profile_name:
        return {"ok": False, "error": "missing_profile"}
    from . import credentials

    try:
        profile = credentials.load_profile(profile_name)
    except credentials.CredentialError as e:
        return {"ok": False, "error": str(e)}
    engine = _get_or_build_autopilot_engine(server, session, profile)
    decision = engine.dry_run_tick(**_autopilot_snapshot_kwargs(session))
    return {"ok": True, "decision": decision_to_trace(decision)}


def _dispatch_autopilot_start(server, session, args):
    """`tw autopilot start` -- arms a background `AutopilotLoop` bound to
    `profile`; returns immediately once armed (mirrors
    `_dispatch_play_start`'s shape, not `_dispatch_play`'s synchronous
    one). `AutopilotLoop.start()` -> `control_lock.enter_auto_loop()` is
    the atomic mode authority (refuses under a human attach or an
    already-running loop); `live_tick()`'s own `AutopilotGateError`
    fail-closed gate (never bypassed here) is what actually decides
    whether a single byte ever reaches the wire -- see that method's own
    docstring. `cash_floor`/`max_ticks` are the two caller-tunable knobs
    the WO asked for; every other `EconCaps`/`AutopilotLoop` default
    (turn_reserve, tick_interval_s, the loop's own hard tick ceiling)
    stays untouched.

    `credits_stale_ms` (WO-FA-SAFE, hub-ratified revise, item 3): a THIRD
    caller-tunable `EconCaps` knob, threaded through exactly like
    `cash_floor` -- so an operator can arm tighter (or looser) than the
    15s default, and re-arm with a different value on a later `stop` ->
    `start` (a fresh `EconCaps` forces `_get_or_build_autopilot_engine` to
    rebuild the engine -- see that function's own docstring for why
    `caps is not None` is what triggers a rebuild rather than reusing the
    cached one). This is the ONLY caller-facing knob for the freshness
    bound the credit-floor stop-loss (`AutopilotEngine._fresh_credits()`)
    reads -- `loop_player.py`'s/`skills.play_skill()`'s own sibling gates
    still only get the 15s default via their own CLI surfaces (a deferred
    follow-on, not built here -- see their own docstrings).

    `min_margin_per_hop` (WO-FA4): a FOURTH caller-tunable `EconCaps` knob,
    threaded through identically -- `trade_driver.run_chain()`'s realized-
    margin abort (a `run_chain` candidate's own per-hop live buy/sell
    totals, not the pre-execution pct-based estimate `chains.py`/
    `trade_adapter.py` rank chains by) reads it via a fresh
    `TradeDriverConfig` built at `AutopilotEngine._execute()`'s own
    `run_chain` call site. An invalid `EconCaps`/`max_ticks` value (a
    negative floor, a non-positive `credits_stale_ms`, a non-integer
    `max_ticks`) is refused with a named `invalid_econ_caps:.../
    invalid_max_ticks` error rather than ever silently disabling the gate
    it was meant to tune (see `EconCaps.__post_init__`)."""
    from . import credentials
    from .autopilot import AutopilotGateError, AutopilotLoop, AutopilotLoopError, EconCaps
    from .control_lock import ControlModeConflict

    profile_name = args.get("profile")
    if not profile_name:
        return {"ok": False, "error": "missing_profile"}
    try:
        profile = credentials.load_profile(profile_name)
    except credentials.CredentialError as e:
        return {"ok": False, "error": str(e)}

    existing_loop = getattr(server, "autopilot_loop", None)
    if existing_loop is not None and existing_loop.running:
        return {"ok": False, "error": "already_running"}

    cash_floor = args.get("cash_floor")
    credits_stale_ms = args.get("credits_stale_ms")
    min_margin_per_hop = args.get("min_margin_per_hop")
    caps_kwargs = {}
    if cash_floor is not None:
        caps_kwargs["cash_floor"] = cash_floor
    if credits_stale_ms is not None:
        caps_kwargs["credits_stale_ms"] = credits_stale_ms
    if min_margin_per_hop is not None:
        caps_kwargs["min_margin_per_hop"] = min_margin_per_hop
    # WO-FA4 (cipher): a socket-tunable EconCaps must fail LOUD on an
    # invalid value (a negative floor, a non-positive staleness bound --
    # see EconCaps.__post_init__) rather than let a malformed caller arg
    # silently disable a stop-loss/turn-reserve/realized-margin gate.
    try:
        caps = EconCaps(**caps_kwargs) if caps_kwargs else None
    except (TypeError, ValueError) as e:
        return {"ok": False, "error": f"invalid_econ_caps:{e}"}
    engine = _get_or_build_autopilot_engine(server, session, profile, caps=caps)

    loop_kwargs = {}
    max_ticks = args.get("max_ticks")
    if max_ticks is not None:
        try:
            loop_kwargs["max_ticks"] = int(max_ticks)
        except (TypeError, ValueError):
            return {"ok": False, "error": "invalid_max_ticks"}
    loop = AutopilotLoop(engine, lambda: _autopilot_snapshot_kwargs(session), **loop_kwargs)
    try:
        loop.start()
    except (AutopilotGateError, AutopilotLoopError, ControlModeConflict) as e:
        return {"ok": False, "error": str(e)}
    server.autopilot_loop = loop
    return {"ok": True, **loop.snapshot()}


def _dispatch_autopilot_stop(server):
    """Also (like `_dispatch_play_stop`) a harmless no-op when nothing is
    running -- never itself refused by whatever it's trying to release."""
    loop = getattr(server, "autopilot_loop", None)
    if loop is None:
        return {"ok": False, "error": "autopilot_not_started"}
    stopped = loop.stop()
    return {"ok": True, "stopped": stopped, **loop.snapshot()}


def _dispatch_list_skills(server, args):
    """Trainer Control Panel's Learned-Loops Library (`L`): lists every
    saved skill with browsable metadata. skills.py has no list function
    of its own (deliberately not added there -- this build only reads
    its already-public load/path primitives, never edits its replay
    internals), so the directory walk lives here.

    Profit metadata is READ, never fabricated: a "mined" skill already
    carries `mined_stats` (cr_per_turn/cr_per_action/support, computed
    by miner.py); a "recorded" skill instead gets `demo_profit` -- the
    observed credits delta summed across the ledger entries tagged with
    its capture name during the ONE original recording (ledger.py,
    read-only via read_entries()) -- deliberately NOT a fabricated
    "per-cycle rate" for something that's only ever been demonstrated
    once. If the panel's own LoopPlayer has ever run this skill this
    daemon session, its live/last cycle progress rides along too."""
    from . import skills
    from .ledger import read_entries

    include_drafts = bool(args.get("include_drafts", False))
    dirs = [(skills.SKILLS_DIR, False)]
    if include_drafts:
        dirs.append((skills.DRAFTS_DIR, True))

    player = getattr(server, "loop_player", None)
    ledger_entries = None  # lazily loaded once, only if a recorded skill needs it
    loops = []
    for directory, is_draft in dirs:
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.json")):
            try:
                doc = skills.load_skill(path.stem, draft=is_draft)
            except skills.SkillError:
                continue  # corrupt/unreadable -- skip rather than fail the whole listing
            entry = {
                "name": doc["name"],
                "source": doc.get("source", "recorded"),
                "created_ts": doc.get("created_ts"),
                "steps": len(doc.get("steps") or []),
                "draft": is_draft,
            }
            mined_stats = doc.get("mined_stats")
            if mined_stats:
                entry["profit_per_turn"] = mined_stats.get("cr_per_turn")
                entry["profit_per_action"] = mined_stats.get("cr_per_action")
                entry["support"] = mined_stats.get("support")
            elif entry["source"] == "recorded":
                if ledger_entries is None:
                    ledger_entries = read_entries()
                entry["demo_profit"] = sum(
                    (e.get("reward") or {}).get("d_credits") or 0
                    for e in ledger_entries
                    if e.get("capture") == doc["name"]
                )
            if player is not None and player.skill_name == doc["name"]:
                snap = player.snapshot()
                entry["last_run"] = {
                    "running": snap["running"],
                    "cycle": snap["cycle"],
                    "cycles_total": snap["cycles_total"],
                    "result": snap["last_result"],
                }
            loops.append(entry)
    return {"ok": True, "loops": loops}


def _dispatch_play_start(server, args):
    """Trainer Control Panel's AUTO-LOOP "start" -- arms LoopPlayer
    (loop_player.py) on a saved skill and returns immediately; progress
    streams over the watch subscribe channel (WatchHub.broadcast_extra,
    "play_progress" events), not this response.

    TW-04 preempt guard: refuses up front, with a clear error naming the
    active driver, if an ai_pilot dispatch (do/send/replay/play/haggle)
    is mid-flight right now -- instead of silently preempting a driving
    pilot. LoopPlayer.start() -> ControlLock.enter_auto_loop() re-checks
    the SAME active-driver slot atomically under its own lock (the true
    source of truth, race-free against a dispatch starting in the
    instant between this check and that call); this early check just
    gives a fast, named error without first loading the skill file off
    disk for a request that's going to be refused anyway."""
    from .loop_player import LoopPlayerError
    from .skills import SkillError, load_skill

    name = args.get("name")
    if not name:
        return {"ok": False, "error": "missing_name"}
    player = getattr(server, "loop_player", None)
    if player is None:
        return {"ok": False, "error": "loop_player_unavailable"}
    lock = getattr(server, "control_lock", None)
    if lock is not None and lock.is_driving():
        return {"ok": False, "error": "locked_by_active_driver"}
    try:
        skill = load_skill(name)
    except SkillError as e:
        return {"ok": False, "error": str(e)}
    try:
        player.start(
            skill,
            name,
            cycles=args.get("cycles", 1),
            floor=args.get("floor"),
            params=args.get("params") or {},
            step_timeout=args.get("step_timeout", 8.0),
            force=args.get("force", False),
        )
    except (LoopPlayerError, ControlModeConflict) as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, **player.snapshot()}


def _dispatch_play_stop(server):
    """Also the Trainer Control Panel's Panic-key backstop: ALWAYS
    allowed regardless of current mode (a stop request must never itself
    be rejected by the very lock it's trying to release)."""
    player = getattr(server, "loop_player", None)
    if player is None:
        return {"ok": False, "error": "loop_player_unavailable"}
    player.stop()
    return {"ok": True, **player.snapshot()}


def _dispatch_play_pause(server):
    from .loop_player import LoopPlayerError

    player = getattr(server, "loop_player", None)
    if player is None:
        return {"ok": False, "error": "loop_player_unavailable"}
    try:
        player.pause()
    except LoopPlayerError as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, **player.snapshot()}


def _dispatch_play_resume(server):
    from .loop_player import LoopPlayerError

    player = getattr(server, "loop_player", None)
    if player is None:
        return {"ok": False, "error": "loop_player_unavailable"}
    try:
        player.resume()
    except LoopPlayerError as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, **player.snapshot()}


def _dispatch_ensure(session, args):
    """B4: idempotent `ensure` — classify the current screen; if already
    at `target`, no-op. Else run the login automaton (B1/B3) via the
    profile's stored/generated credential, and remember the profile so
    the daemon's SessionGuardian (D9) can auto-replay this login after a
    later drop without the caller re-specifying anything."""
    from . import credentials
    from .login import LoginError, run_login

    target = args.get("target", "main_command")
    profile_name = args.get("profile")
    if not profile_name:
        return {"ok": False, "error": "missing_profile"}

    try:
        profile = credentials.load_profile(profile_name)
    except credentials.CredentialError as e:
        return {"ok": False, "error": str(e)}

    # D9: a dead telnet connection must be repaired before we can even
    # classify the current screen (a stale pyte buffer would misclassify
    # a frozen last-seen frame as "current").
    if not session.conn.connected:
        try:
            session.reconnect()
        except OSError as e:
            return {"ok": False, "error": f"reconnect_failed:{e}"}

    rows = session.render()
    text = session.render_text(rows)
    prompt = rows[-1].strip() if rows else ""
    cls = classify_screen(text, prompt)

    # WO-OPTION-CLEAR-ENSURE: clear fighter Option? BEFORE hud I-seed.
    # Seed skips Option? when detected, but a prior mid-explore I-probe
    # can already have scrolled the vs-line off the viewport — clear
    # first so ensure is not wedged on unparsed counts.
    if cls != target and bool(getattr(profile, "autonomous", False)):
        if _try_clear_fighter_option_once(session, text, prompt):
            rows = session.render()
            text = session.render_text(rows)
            prompt = rows[-1].strip() if rows else ""
            cls = classify_screen(text, prompt)

    # WO-HUD-CREDITS-TURNS-JOIN: seed sticky credits/turns (I-probe if
    # needed) BEFORE the already_there short-circuit — explore/fighter-
    # toll screens omit both, and a no-op ensure would otherwise leave
    # the spectate HUD at `-` forever. Runs after Option? clear.
    from .hud_seed import seed_hud_after_join
    hud_seed = seed_hud_after_join(session)

    rows = session.render()
    text = session.render_text(rows)
    prompt = rows[-1].strip() if rows else ""
    cls = classify_screen(text, prompt)

    if cls == target:
        # Attribute the world even on the no-op path — otherwise status
        # world_id stays None (spectate PRIORITIES/goals empty) whenever
        # ensure short-circuits after a recycle that left us already at
        # the target class (WO-TUI-PRIORITIES-DECISIONS-REGRESS).
        session.mark_profile(profile.name)
        resp = build_response(
            session,
            extra={"already_there": True, "steps": 0, **hud_seed},
        )
        return resp

    try:
        final_cls, steps = run_login(
            session,
            profile,
            get_password=credentials.get_password,
            save_password=credentials.save_password,
            target=target,
        )
    except LoginError as e:
        # Login can land on a fighter Option? the automaton does not know
        # (WO-AUTOPILOT-AFTER-ENSURE live): clear once when autonomous,
        # then treat main_command as ensure success so auto-start arms.
        if bool(getattr(profile, "autonomous", False)):
            rows = session.render()
            text = session.render_text(rows)
            prompt = rows[-1].strip() if rows else ""
            if _try_clear_fighter_option_once(session, text, prompt):
                rows = session.render()
                text = session.render_text(rows)
                prompt = rows[-1].strip() if rows else ""
                cls = classify_screen(text, prompt)
                if cls == target:
                    hud_seed = seed_hud_after_join(session)
                    session.mark_profile(profile.name)
                    resp = build_response(
                        session,
                        extra={
                            "steps": 0,
                            "already_there": False,
                            "fighter_option_cleared": True,
                            **hud_seed,
                        },
                    )
                    session.record_history(
                        "ensure",
                        {"profile": profile_name, "target": target},
                        resp["prompt"],
                        resp["classification"],
                        "ensure",
                    )
                    return resp
        resp = build_response(session, extra={"already_there": False, **hud_seed})
        resp["ok"] = False
        resp["error"] = f"login_failed:{e}"
        return resp

    # Mark the profile immediately on login success — before the post-login
    # hud I-probe — so concurrent status calls see world_id correctly
    # during the probe's settle wait (WO-STATUS-WORLD-ID: the settle window
    # was the only gap where auto_login_profile was still None mid-session).
    session.mark_profile(profile.name)
    # Re-seed after login — the I-probe above may have run on a pre-login
    # screen; a post-login main_command still often lacks credits/turns.
    hud_seed = seed_hud_after_join(session)
    resp = build_response(
        session,
        extra={"steps": steps, "already_there": False, **hud_seed},
    )
    session.record_history(
        "ensure", {"profile": profile_name, "target": target}, resp["prompt"], resp["classification"], "ensure"
    )
    return resp


def _try_clear_fighter_option_once(session, text, prompt) -> bool:
    """Send Attack/Retreat (and Attack qty) for a fighter ``Option?``.

    Returns True iff a keystroke was sent (caller should re-classify).
    Never sends Pay. After ``A``, answers ``How many fighters…`` when
    that sub-prompt appears (empty Enter = 0 = live stick).
    """
    from .fighter_toll_policy import next_fighter_option_input
    from .settle import send_and_confirm

    fo = next_fighter_option_input(text, prompt)
    if not fo.detected or fo.key is None:
        return False
    # A/R are single-keystroke Option? menu — no trailing Enter; qty digits need it.
    send_and_confirm(session, fo.key, confirm_prompt=None, enter=fo.key.isdigit())
    if fo.key == "A":
        rows = session.render()
        text2 = session.render_text(rows)
        prompt2 = rows[-1].strip() if rows else ""
        fo2 = next_fighter_option_input(text2, prompt2)
        if fo2.detected and fo2.key is not None and fo2.key.isdigit():
            send_and_confirm(session, fo2.key, confirm_prompt=None, enter=True)
    return True


def _maybe_auto_start_after_ensure(server, session, profile_name):
    """WO-FA6: the `ensure`-verb integration `autopilot.py`'s standalone
    `maybe_auto_start()` (P1-d) names as its intended call site -- wiring
    only, no change to that function's own gates or execution posture.

    Reloads the profile by name (a cheap TOML read) rather than
    threading the `Profile` object `_dispatch_ensure` already loaded
    internally back out through an extra return value -- same
    reload-by-name convention `_dispatch_autopilot_preview`/
    `_dispatch_autopilot_start` already use, and it keeps
    `_dispatch_ensure`'s own signature/response shape untouched.

    No-ops (never attempts a start) when there's no `profile_name`, no
    `server.control_lock` at all (the bare dispatch-harness convention
    every other optional server surface in this module already follows),
    or the name no longer resolves -- all silent, since `ensure`'s own
    response has already succeeded and must not be affected by any of
    this. `maybe_auto_start` itself never raises for its two ordinary
    "declined" cases (`profile.autonomous` False, or a human/auto_loop
    already holding the lock) -- it returns `None`, which is exactly what
    a real daemon sees on every real connect while every shipped profile
    keeps `autonomous` at its default `False`: WIRING ONLY, no arm-
    posture change. The broad `except` below is belt-and-suspenders for
    anything else (e.g. a `snapshot_provider` call raising mid-tick) --
    a post-login hook declining or failing to start must never crash the
    ensure/login success path it's attached to.

    On an actual start, the returned loop is stashed on `server.
    autopilot_loop` -- the same attribute `_dispatch_autopilot_start`/
    `_dispatch_autopilot_stop` already use, so a later `tw autopilot
    stop` (or `tw status`) finds it exactly like a manually-armed loop --
    and `loop.engine` onto `server.autopilot_engine`, so `tw status`'s
    `autopilot_trace` reflects this loop's ticks too, the same slot
    `_get_or_build_autopilot_engine` fills for the manual-start path.

    **STICKY HALT (mack HIGH, WO-FA6 revise).** Checked FIRST, before
    even looking at `profile_name`: if `server.autopilot_loop` is already
    set -- running, OR halted with `.last_error` set (a crash, or the
    `settle_unconfirmed` desync halt -- see `AutopilotLoop._run()`'s own
    two halt branches) -- this hook NEVER touches it. A halt is the
    engine's own safety brake; silently re-arming a fresh loop over a
    halted one on the very next routine `ensure` (the daemon's guardian
    reconnect-replay, or any caller defensively re-ensuring an
    already-connected session) would erase `last_error` and resume
    driving as if nothing happened -- exactly the "sticky" part a safety
    halt requires. Recovery is a DELIBERATE supervisor action instead:
    the halt is visible via `tw status`'s `play`/`autopilot_trace` (or
    reading `last_error` directly), an operator investigates, an explicit
    `autopilot_stop` clears the stash (`_dispatch_autopilot_stop` doesn't
    special-case a halted loop -- it stops/reads it same as a running
    one), and only THEN does a later `ensure`/`autopilot_start` see
    `autopilot_loop is None` again and re-arm. The call site fires on
    every successful ensure; this sticky-halt check is what keeps a
    deliberate brake from being silently cleared."""
    if getattr(server, "autopilot_loop", None) is not None:
        return
    if not profile_name:
        return
    control_lock = getattr(server, "control_lock", None)
    if control_lock is None:
        return
    from . import credentials
    from .autopilot import maybe_auto_start

    try:
        profile = credentials.load_profile(profile_name)
    except credentials.CredentialError:
        return
    try:
        loop = maybe_auto_start(
            session,
            profile,
            control_lock,
            lambda: _autopilot_snapshot_kwargs(session),
            ledger=getattr(server, "ledger", None),
            session_id=_current_session_id(session),
        )
    except Exception as exc:  # noqa: BLE001 -- a post-login hook must never crash the ensure success path
        logger = getattr(session, "logger", None)
        log_note = getattr(logger, "log_note", None)
        if log_note is not None:
            log_note(f"maybe_auto_start failed: {exc!r}")
        return
    if loop is not None:
        server.autopilot_loop = loop
        server.autopilot_engine = loop.engine
