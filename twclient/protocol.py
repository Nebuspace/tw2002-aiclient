"""JSON verb protocol shared by the daemon's socket server and the CLI.

Wire format: one line-delimited JSON object per request/response over the
unix-domain socket. Request: {"verb": "...", "args": {...}}.
Response: always has "ok"; on success carries verb-specific fields, on
failure carries "error".
"""

import re
import time

from .classify import classify_screen
from .control_lock import MODE_AI_PILOT, MODE_AUTO_LOOP, MODE_HUMAN, ControlModeConflict
from .state_parser import parse_state


def _control_lock_error(server):
    """Shared do/send/play/replay/haggle guard: None when the AI is free
    to drive (default, no server.control_lock at all in a bare
    dispatch-harness test, or mode == ai_pilot); otherwise an error
    response naming WHO/WHAT currently holds the lock, so a caller (or a
    test) can tell a human attach apart from a running AUTO-LOOP or a
    plain paused/spectate state -- never just one flat "locked" string."""
    lock = getattr(server, "control_lock", None)
    if lock is None or lock.ai_may_send():
        return None
    mode = lock.mode
    if mode == MODE_HUMAN:
        return {"ok": False, "error": "controller_locked_by_human"}
    if mode == MODE_AUTO_LOOP:
        return {"ok": False, "error": "controller_locked_by_auto_loop"}
    return {"ok": False, "error": f"controller_locked:{mode}"}


def build_response(session, rows=None, settled_reason=None, extra=None):
    color = None
    if rows is None:
        # The common path: current settled screen, text+color captured
        # together (D13) so they can't drift out of alignment.
        rows, color = session.render_with_color()
    text = session.render_text(rows)
    prompt = rows[-1].strip() if rows else ""
    resp = {
        "ok": True,
        "screen": rows,
        "color": color,
        "prompt": prompt,
        "classification": classify_screen(text, prompt),
        "state": parse_state(text),
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
    return resp


def dispatch(session, verb, args, server):
    if verb == "screen":
        rows = session.render_raw() if args.get("raw") else None
        return build_response(session, rows=rows)

    if verb == "do":
        lock_error = _control_lock_error(server)
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
        _record_ledger(server, pre_text, text, secret, resp)
        _record_skill_step(server, text, wait_prompt, resp["classification"], secret)
        return resp

    if verb == "send":
        lock_error = _control_lock_error(server)
        if lock_error is not None:
            return lock_error
        text = args.get("input", "")
        enter = args.get("enter", True)
        secret = args.get("secret", False)
        pre_text = session.render_text(session.render())
        session.send(text, enter=enter, secret=secret)
        resp = build_response(session)
        _record_ledger(server, pre_text, text, secret, resp)
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
        text = session.render_text()
        return {"ok": True, "state": parse_state(text)}

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
        return _dispatch_ensure(session, args)

    # -- v2.1 item 11: macro/recording/pattern-learning verbs -----------
    if verb == "record_start":
        return _dispatch_record_start(server, args)

    if verb == "record_stop":
        return _dispatch_record_stop(server)

    if verb == "replay":
        lock_error = _control_lock_error(server)
        if lock_error is not None:
            return lock_error
        return _dispatch_replay(session, args)

    if verb == "mine":
        return _dispatch_mine(args)

    if verb == "play":
        lock_error = _control_lock_error(server)
        if lock_error is not None:
            return lock_error
        return _dispatch_play(session, args)

    if verb == "haggle":
        lock_error = _control_lock_error(server)
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


def _record_ledger(server, pre_text, input_text, secret, resp):
    """C1 hook: every `do`/`send` dispatch appends one Trace-Ledger entry
    (twclient/ledger.py), tagged with the currently-open `tw record`
    capture name if any. `server.ledger` is absent in tests that build a
    bare dispatch harness -- silently a no-op then, same convention as
    `status`'s `getattr(server, "watch_hub", None)`."""
    ledger = getattr(server, "ledger", None)
    if ledger is None:
        return
    capture = None
    recorder = getattr(server, "skill_recorder", None)
    if recorder is not None:
        capture = recorder.active_name
    post_text = "\n".join(resp["screen"])
    ledger.record_do(pre_text, input_text, secret, post_text, resp["classification"], capture=capture)


def _record_skill_step(server, input_text, wait_prompt, post_class, secret):
    """C3 hook: while a `tw record` capture is open, also accumulate this
    step into the in-progress skill (twclient.skills.SkillRecorder)."""
    recorder = getattr(server, "skill_recorder", None)
    if recorder is None or not recorder.recording:
        return
    recorder.record_step(input_text, wait_prompt, post_class, secret=secret)


def _dispatch_record_start(server, args):
    from .skills import SkillError

    recorder = getattr(server, "skill_recorder", None)
    if recorder is None:
        return {"ok": False, "error": "recording_unavailable"}
    try:
        name = recorder.start(args.get("name"))
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


def _dispatch_replay(session, args):
    from .skills import ReplayDivergence, SkillError, load_skill, replay_skill

    name = args.get("name")
    if not name:
        return {"ok": False, "error": "missing_name"}
    try:
        skill = load_skill(name)
    except SkillError as e:
        return {"ok": False, "error": str(e)}
    try:
        results = replay_skill(session, skill, params=args.get("params") or {}, step_timeout=args.get("step_timeout", 8.0))
    except ReplayDivergence as e:
        return {"ok": False, "error": "divergence", **e.as_dict()}
    return {"ok": True, "name": name, "results": results}


def _dispatch_mine(args):
    from .miner import mine_ledger

    result = mine_ledger(min_support=args.get("min_support", 2))
    return {"ok": True, **result}


def _dispatch_play(session, args):
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
    _record_ledger(server, pre_text, input_desc, False, resp)
    return resp


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
    "play_progress" events), not this response."""
    from .loop_player import LoopPlayerError
    from .skills import SkillError, load_skill

    name = args.get("name")
    if not name:
        return {"ok": False, "error": "missing_name"}
    player = getattr(server, "loop_player", None)
    if player is None:
        return {"ok": False, "error": "loop_player_unavailable"}
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
