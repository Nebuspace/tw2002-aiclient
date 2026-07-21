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
from .state_parser import is_genuine_sector_status, parse_port_report, parse_state


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

    `getattr`-guarded on `auto_login_profile` like every other optional
    session surface this module reads (`server.watch_hub`,
    `session.cursor_pos`) -- absent on bare fake-session test doubles
    that predate it."""
    profile_name = getattr(session, "auto_login_profile", None)
    if not profile_name:
        return None
    from . import credentials

    try:
        profile = credentials.load_profile(profile_name)
    except credentials.CredentialError:
        return None
    return world_identity.world_id(session.host, profile.game_letter, profile.handle)


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
      own shape is never trusted as the provenance signal by itself."""
    wid = _current_world_id(session)
    if wid is None:
        return
    try:
        if is_genuine_sector_status(text):
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
            _record_ledger(server, session, pre_text, text, secret, resp)
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
            _record_ledger(server, session, pre_text, text, secret, resp)
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
        # Cross-seat trace transport (WO-P2d, additive/dry-run-only): no
        # AutopilotEngine exists on a real daemon yet (P1-d auto-start is
        # deliberately deferred -- see autopilot.py's own docstring), so
        # this is `None` on every real daemon today; a caller (the
        # spectate Decisions panel) must never special-case a missing key,
        # same null-safe convention as `play` above.
        autopilot_engine = getattr(server, "autopilot_engine", None)
        autopilot_trace = None
        if autopilot_engine is not None:
            trace_log = autopilot_engine.trace_log()
            if trace_log:
                autopilot_trace = trace_log[-1]  # most-recent tick only -- see AutopilotEngine.trace_log()
        return {
            "ok": True,
            "connected": session.conn.connected,
            "idle_ms": int((time.monotonic() - session.last_rx) * 1000),
            "classification": classify_screen(text, prompt),
            "host": session.host,
            "port": session.port,
            "name": session.name,
            "subscribers": watch_hub.subscriber_count() if watch_hub else 0,
            # Explicit, observable control-MODE state (interactive-attach
            # addendum, extensible enum -- see control_lock.py): one of
            # "ai_pilot" (default), "human" (a `tw attach` session has
            # the keyboard), "auto_loop" (LoopPlayer driving solo),
            # "spectate" (paused).
            "mode": lock.mode if lock is not None else MODE_AI_PILOT,
            # AUTO-LOOP live progress (Trainer Control Panel) -- present
            # even when nothing has ever run this daemon session (all
            # fields default/None then), so a caller never has to
            # special-case "field missing" vs "nothing running".
            "play": player.snapshot() if player is not None else None,
            # See autopilot_engine/autopilot_trace computed above.
            "autopilot_trace": autopilot_trace,
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
            return _dispatch_ensure(session, args)

    if verb == "crawl_start":
        return _dispatch_crawl_start(server, session, args)

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


def _record_ledger(server, session, pre_text, input_text, secret, resp, actor=None):
    """C1 hook: every `do`/`send`/`haggle` dispatch appends one
    Trace-Ledger entry (twclient/ledger.py), tagged with the
    currently-open `tw record` capture name if any, plus TW-05's
    actor/session_id attribution. `actor=None` (do/send's case) derives
    the actor from mode via `_current_actor()`; a caller with its own
    fixed attribution (haggle -- a deterministic, no-LLM engine per
    knowledge/architecture/autonomy-loop.md's own "trainer" definition)
    passes an explicit override instead. `server.ledger` is absent in
    tests that build a bare dispatch harness -- silently a no-op then,
    same convention as `status`'s `getattr(server, "watch_hub", None)`."""
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
    as `_record_ledger`."""
    from .skills import ReplayDivergence, SkillError, load_skill, replay_skill

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
        )
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
    `replay_skill()` call by `play_skill` itself."""
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
    _record_ledger(server, session, pre_text, input_desc, False, resp, actor="trainer")
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
            )
        except CrawlSafetyError as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True, **result}


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
    if cls == target:
        resp = build_response(session, extra={"already_there": True, "steps": 0})
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
        resp = build_response(session, extra={"already_there": False})
        resp["ok"] = False
        resp["error"] = f"login_failed:{e}"
        return resp

    session.mark_profile(profile.name)
    resp = build_response(session, extra={"steps": steps, "already_there": False})
    session.record_history(
        "ensure", {"profile": profile_name, "target": target}, resp["prompt"], resp["classification"], "ensure"
    )
    return resp
