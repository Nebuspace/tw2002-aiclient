"""The play-shell's entry point into the session engine (WO-P2-020).

`ensure_session()` wraps the client-side `ensure` round trip
(`session.cli.ensure_raw`) into a typed result so a caller never has to
parse a raw wire dict or catch a bare exception out of the transport layer.
Per canon (`architecture/cli-verbs.md`, `architecture/session-engine.md`):
"Play does not hang past a bounded timeout -- a failure surfaces a typed
error, not a silent stall." `ensure_session()` is what upholds that promise
for anything importing it directly, rather than shelling out to `tw ensure`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .session import cli as _cli
from .session import env as _env
from . import world_identity as _wi

# Machine-readable failure reasons `ensure_session()` may return on
# `EnsureResult.reason`. Callers should switch on these constants, not on
# the daemon's raw `error` strings (see `_REASON_BY_DAEMON_ERROR` below for
# the mapping from the wire's vocabulary to this one).
REASON_TIMEOUT = "timeout"
REASON_SPAWN_FAILED = "spawn_failed"
REASON_PROFILE_INVALID = "profile_invalid"
REASON_LOGIN_FAILED = "login_failed"
REASON_ALREADY_DRIVING = "already_driving"
REASON_CONNECT_FAILED = "connect_failed"
REASON_UNKNOWN = "unknown"

# Direct 1:1 hits against `ensure_raw`'s own locally-synthesized `error`
# values (profile resolution / spawn / budget failures that never reached
# the daemon -- see `session/cli.py::ensure_raw`).
_REASON_BY_DAEMON_ERROR = {
    "profile_invalid": REASON_PROFILE_INVALID,
    "spawn_failed": REASON_SPAWN_FAILED,
    "timeout": REASON_TIMEOUT,
    "daemon_not_running": REASON_CONNECT_FAILED,
    "empty_response": REASON_CONNECT_FAILED,
}


@dataclass(frozen=True)
class EnsureResult:
    """Typed outcome of `ensure_session()` -- never a bare bool/string,
    and never a raw exception reaching the caller. `ok=True` guarantees
    `classification` is set. `ok=False` guarantees `reason` is one of this
    module's `REASON_*` constants (falling back to `REASON_UNKNOWN` for a
    daemon error string not yet mapped here -- `detail` always carries the
    raw text in that case, so nothing is silently swallowed). `raw` is the
    underlying wire dict, kept for debugging/logging -- never required
    reading for correct control flow.
    """

    ok: bool
    classification: str | None = None
    reason: str | None = None
    detail: str | None = None
    raw: dict | None = None


def ensure_session(
    profile: str,
    *,
    target: str = "main_command",
    timeout: float = 20.0,
    no_auto_arm: bool = False,
    run_dir: Path | None = None,
) -> EnsureResult:
    """Idempotent auto-login for `profile`, bounded by `timeout` seconds
    total -- daemon spawn-wait and the login round trip together, never a
    silent stall past this budget. No-ops (returns success immediately)
    when the daemon already sits at `target`; spawns the daemon first if
    none is running. Never raises for an expected failure mode -- every
    path returns a typed `EnsureResult`.
    """
    resolved_run_dir = run_dir or _env.resolve_run_dir()
    try:
        resp = _cli.ensure_raw(
            profile,
            target=target,
            timeout=timeout,
            no_auto_arm=no_auto_arm,
            run_dir=resolved_run_dir,
        )
    except Exception as e:  # noqa: BLE001 -- belt-and-suspenders: ensure_raw is
        # written to always return a typed dict, never raise, but this typed
        # wrapper's whole contract is that ITS caller never sees a bare
        # traceback either, so a surprise exception is still caught here.
        return EnsureResult(ok=False, reason=REASON_UNKNOWN, detail=f"{type(e).__name__}: {e}")

    if resp.get("ok"):
        return EnsureResult(
            ok=True,
            classification=resp.get("class") or resp.get("classification") or target,
            raw=resp,
        )

    return EnsureResult(ok=False, reason=_classify_failure(resp), detail=_failure_detail(resp), raw=resp)


def disconnect_session(*, run_dir: "Path | None" = None) -> bool:
    """WO-PLAY-CONN-TOGGLE: close the daemon's telnet connection without
    stopping the daemon process.  Returns ``True`` on success (the daemon
    reported ``"disconnected": True``), ``False`` on any transport or
    protocol failure.  Never raises.

    The companion re-entry path is the existing ``ensure_session()``: the
    daemon's ``ensure`` verb already calls ``session.reconnect()`` when
    ``session.conn.connected`` is ``False``, so ``ensure_session()`` after a
    ``disconnect_session()`` is the correct reconnect sequence — no new
    reconnect verb is needed.
    """
    resolved_run_dir = run_dir or _env.resolve_run_dir()
    try:
        resp = _cli.send_request("disconnect", {}, run_dir=resolved_run_dir)
        return bool(resp.get("ok"))
    except Exception:  # noqa: BLE001 — transport failure, caller checks the bool
        return False


def _classify_failure(resp: dict) -> str:
    error = str(resp.get("error") or "")
    reason = _REASON_BY_DAEMON_ERROR.get(error)
    if reason is not None:
        return reason
    if error.startswith("connect_failed") or error.startswith("bad_response"):
        return REASON_CONNECT_FAILED
    # FLAG for Worker D: confirm the daemon's `ensure` verb actually emits
    # `controller_locked_by_human` / `controller_locked_by_auto_loop` /
    # `controller_busy` verbatim on a lock conflict (per
    # `architecture/session-engine.md`'s `ControlModeConflict` naming) --
    # this module assumes that vocabulary and has never seen it on the wire.
    if error.startswith("controller_"):
        return REASON_ALREADY_DRIVING
    if "login" in error or "register" in error:
        return REASON_LOGIN_FAILED
    return REASON_UNKNOWN


def _failure_detail(resp: dict) -> str | None:
    return resp.get("detail") or (resp.get("error") or None)


# ---------------------------------------------------------------------------
# Explore adapter — WO-PLAY-EXPLORE-ADAPTER (Play ladder L2)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExploreResult:
    """Typed outcome of ``explore_start`` / ``explore_stop`` / ``explore_status``.

    ``ok=True``: the daemon accepted the request. ``ok=False``: transport or
    protocol failure — ``reason`` carries a machine-readable tag, ``detail``
    carries the raw daemon error string (never silently swallowed). ``raw``
    is the full wire dict, kept for debugging / L4 readers that need
    ``distinct_sectors`` / ``outcome`` / other daemon-side fields.
    """

    ok: bool
    reason: str | None = None   # machine-readable when ok=False
    detail: str | None = None
    raw: dict | None = None     # wire dict; L4 reads distinct_sectors/outcome from here


def explore_start(
    world_id: str,
    *,
    min_sectors: int | None = None,
    turn_budget: int | None = None,
    intent: str | None = None,
    dock_new_ports: bool | None = None,
    fight_tolls: bool | None = None,
    run_dir: Path | None = None,
) -> ExploreResult:
    """Start the sector explorer for *world_id*.

    Sends ``explore_start`` to the daemon via :func:`session.cli.send_request`.
    Payload mirrors ``cmd_explore_start``'s discipline: ``world_id`` is always
    sent; ``min_sectors`` and ``turn_budget`` are included only when explicitly
    supplied (``None`` → omit, letting the daemon apply its own defaults of 5
    and 50 respectively).

    Never raises for expected transport / protocol failures — every path
    returns a typed :class:`ExploreResult`.
    """
    resolved_run_dir = run_dir or _env.resolve_run_dir()
    payload: dict = {"world_id": world_id}
    if min_sectors is not None:
        payload["min_sectors"] = min_sectors
    if turn_budget is not None:
        payload["turn_budget"] = turn_budget
    if intent is not None:
        # Omitted when None so the daemon keeps its pre-WO default (map-fill)
        # -- same "None -> omit" discipline as the two args above, and it is
        # what keeps every existing caller byte-identical on the wire.
        payload["intent"] = intent
    if dock_new_ports is not None:
        # WO-EXPLORE-DOCK-NEW-PORT. Same "None -> omit" discipline, and here it
        # carries real weight: an omitted flag leaves the daemon at False, so a
        # caller that has not been taught about turn-spending docking cannot
        # start one by accident.
        payload["dock_new_ports"] = bool(dock_new_ports)
    if fight_tolls is not None:
        # WO-ADAPTERS-FIGHT-TOLLS. Same "None -> omit" discipline as the flags
        # above, and it carries the most weight of any of them: omitted leaves
        # the daemon at False, so a caller that has never been taught about the
        # toll policy cannot arm an ATTACK by accident. Play and every other
        # adapter caller could not arm this at all before -- automation was
        # CLI-only -- but "reachable" must not become "on".
        #
        # DELIBERATELY NOT `bool(fight_tolls)`, which is where `dock_new_ports`
        # above differs. `runner.start` refuses a non-bool with
        # `invalid_fight_tolls` precisely because `"no"` is truthy in Python --
        # coercing here would hand the daemon a valid `True` and the refusal
        # would never fire. Local coercion does not defend the caller; it
        # destroys the evidence the daemon needs to defend them.
        #
        # So the value is forwarded UNCHANGED and the daemon adjudicates. That
        # is also consistent with this module's contract: expected protocol
        # failures come back as a typed `ExploreResult`, not an exception.
        payload["fight_tolls"] = fight_tolls
    try:
        resp = _cli.send_request("explore_start", payload, run_dir=resolved_run_dir)
    except Exception as e:  # noqa: BLE001 — belt-and-suspenders; send_request never raises
        return ExploreResult(ok=False, reason="unknown", detail=f"{type(e).__name__}: {e}")
    if resp.get("ok"):
        return ExploreResult(ok=True, raw=resp)
    return ExploreResult(
        ok=False,
        reason=resp.get("error") or "unknown",
        detail=resp.get("detail") or resp.get("error") or None,
        raw=resp,
    )


def explore_stop(*, run_dir: Path | None = None) -> ExploreResult:
    """Stop the running sector explorer.

    Sends ``explore_stop`` to the daemon. Never raises; always returns a typed
    :class:`ExploreResult`.
    """
    resolved_run_dir = run_dir or _env.resolve_run_dir()
    try:
        resp = _cli.send_request("explore_stop", {}, run_dir=resolved_run_dir)
    except Exception as e:  # noqa: BLE001
        return ExploreResult(ok=False, reason="unknown", detail=f"{type(e).__name__}: {e}")
    if resp.get("ok"):
        return ExploreResult(ok=True, raw=resp)
    return ExploreResult(
        ok=False,
        reason=resp.get("error") or "unknown",
        detail=resp.get("detail") or resp.get("error") or None,
        raw=resp,
    )


def explore_status(*, run_dir: Path | None = None) -> ExploreResult:
    """Query sector explorer status.

    Sends ``explore_status`` to the daemon. Never raises; always returns a
    typed :class:`ExploreResult`.
    """
    resolved_run_dir = run_dir or _env.resolve_run_dir()
    try:
        resp = _cli.send_request("explore_status", {}, run_dir=resolved_run_dir)
    except Exception as e:  # noqa: BLE001
        return ExploreResult(ok=False, reason="unknown", detail=f"{type(e).__name__}: {e}")
    if resp.get("ok"):
        return ExploreResult(ok=True, raw=resp)
    return ExploreResult(
        ok=False,
        reason=resp.get("error") or "unknown",
        detail=resp.get("detail") or resp.get("error") or None,
        raw=resp,
    )


@dataclass(frozen=True)
class AutoLoopResult:
    """Typed outcome of ``autoloop_stop`` (WO-P5-071).

    Deliberately a separate type from :class:`ExploreResult` rather than a
    reuse: the two verbs answer about different runners, and a shared
    result type invites a caller to hand an explore outcome to a panic
    consumer (or the reverse) with nothing catching it. The field shape is
    intentionally identical so the transport-handling idiom stays one
    idiom.
    """

    ok: bool
    reason: str | None = None   # machine-readable when ok=False
    detail: str | None = None
    raw: dict | None = None     # wire dict; carries `stopping` + the run report


def autoloop_start(
    name: str,
    *,
    floor: int | None = None,
    run_dir: Path | None = None,
) -> AutoLoopResult:
    """Arm the background player for **one pass** of the taught macro *name*.

    The transport for the money path. Sends ``autoloop_start``; never raises;
    always returns a typed :class:`AutoLoopResult`.

    **One pass, not a repetition count.** The daemon plays a single pass and
    *refuses* ``cycles`` outright (``unsupported_arg:cycles``) because two of
    the four rails that make repetition safe are not built yet — see
    ``session/protocol.py::_dispatch_autoloop_start``. So this adapter has no
    ``cycles`` parameter to pass one through: a keyword the daemon will refuse
    is a keyword that invites a caller to compose a confirm prompt promising
    repetition that cannot happen. ``force`` is absent for the same reason and
    a stronger one — it waives a missing start-anchor, and canon allows only an
    explicit *human* waiver.

    **A blank name fails closed here, without reaching the wire.** The daemon
    answers ``missing_name`` for the same input, so this is not a second
    opinion — it is a guarantee that the refusal is reachable when there is no
    daemon at all, which is exactly the state a caller is in when it has no
    loop to name. WO-PLAY-AUTOLOOP-START's constraint is "fail closed with a
    typed error when missing — do not guess", and a guess here would arm
    *some* macro rather than none.

    **``floor`` is deliberately NOT re-validated here.** The daemon rejects a
    bool or a float with a named ``invalid_floor`` and documents why the check
    belongs there — "JSON is where the wrong type actually arrives". Copying
    that rule into the adapter would create a second place for it to drift,
    and the failure mode of drift is a floor the operator believes is armed.
    One owner, and it is the layer that can actually enforce it.

    Caller contract: this is a **live-money call**. Canon
    (``canon/surfaces/mode-line-and-teach-controls.md`` §"Confirm-gate — never
    one keystroke to live money") requires an explicit confirm gate showing
    what will run *before* this function is reached. Calling it straight off a
    keystroke is the −75/−78-turn scar.
    """
    if not isinstance(name, str) or not name.strip():
        return AutoLoopResult(
            ok=False,
            reason="missing_name",
            detail="no taught loop named; refusing to guess which macro to arm",
        )
    payload: dict = {"name": name}
    if floor is not None:
        # Omitted when None so the daemon applies its own policy, mirroring
        # `explore_start`'s "None -> omit" discipline. Sent unvalidated: see
        # the docstring on who owns `invalid_floor`.
        payload["floor"] = floor
    return _autoloop_verb("autoloop_start", run_dir, payload=payload)


def autoloop_stop(*, run_dir: Path | None = None) -> AutoLoopResult:
    """Halt the background taught-run player. The panic path's transport.

    Sends ``autoloop_stop`` to the daemon. Never raises; always returns a
    typed :class:`AutoLoopResult`.

    The verb it wraps is **idempotent and never refuses**
    (``session/protocol.py::_dispatch_autoloop_stop``) — the player's own
    arm predicate stops the run within one send-step, and the run releases
    its control-lock hold as it dies. So a double-press is harmless and a
    stop cannot drop the App's exclusivity out from under an in-flight
    step. The one non-``ok`` answer the daemon itself produces is
    ``autoloop_unavailable`` (no player attached), which is surfaced as
    ``reason`` rather than being smoothed into a success — an operator who
    hit panic is entitled to know the halt did not reach a runner.

    NOTE: this stops the AUTO-LOOP player only, not an ``explore`` run
    (which has its own ``explore_stop``). Canon's "halts *all* automation"
    is not yet literally true on tip; see ``cockpit/panic.py``.
    """
    resolved_run_dir = run_dir or _env.resolve_run_dir()
    try:
        resp = _cli.send_request("autoloop_stop", {}, run_dir=resolved_run_dir)
    except Exception as e:  # noqa: BLE001
        return AutoLoopResult(ok=False, reason="unknown", detail=f"{type(e).__name__}: {e}")
    if resp.get("ok"):
        return AutoLoopResult(ok=True, raw=resp)
    return AutoLoopResult(
        ok=False,
        reason=resp.get("error") or "unknown",
        detail=resp.get("detail") or resp.get("error") or None,
        raw=resp,
    )


def autoloop_pause(*, run_dir: Path | None = None) -> AutoLoopResult:
    """Park the taught run and hand the keyboard back (WO-AUTOLOOP-PAUSE-RESUME).

    Mechanically the same stand-down as :func:`autoloop_stop` — the daemon
    records the *intent* so a later relaunch can tell a parked run from a
    panicked one. Never raises; always returns a typed result.
    """
    return _autoloop_verb("autoloop_pause", run_dir)


def autoloop_status(*, run_dir: Path | None = None) -> AutoLoopResult:
    """Read-only taught-run status (WO-AUTOLOOP-RELAUNCH-COCKPIT preview).

    Sends ``autoloop_status`` to the daemon. Same transport idiom as
    :func:`explore_status` / the other ``autoloop_*`` adapters: never raises;
    always returns a typed :class:`AutoLoopResult`. Cockpit preview of
    ``run.sends_issued`` before a relaunch confirm MUST go through this
    adapter — ``app.py`` must not call ``send_request`` with any verb other
    than the adjudicated ``status`` allowlist entry.
    """
    return _autoloop_verb("autoloop_status", run_dir)


def autoloop_relaunch(*, run_dir: Path | None = None) -> AutoLoopResult:
    """Re-arm a paused run **from the start of its macro**. Not a resume.

    The caller MUST disclose two fields from ``raw`` before committing:
    ``replays_from_start`` and ``sends_already_issued``. This replays steps
    the paused run already executed, so on a trade macro it re-spends live
    turns and credits — the operator has to see that before confirming.

    ``sends_already_issued`` is ``None`` when the player never produced a
    count. That is "unknown", NOT zero, and must not be rendered as
    "0 sends already issued" — the same honest-`?` rule the coverage meter
    follows.
    """
    return _autoloop_verb("autoloop_relaunch", run_dir)


def _autoloop_verb(
    verb: str,
    run_dir: "Path | None",
    *,
    payload: dict | None = None,
) -> AutoLoopResult:
    """Shared transport for the autoloop verbs — one place that decides how
    a daemon refusal becomes a typed result, so `pause` and `relaunch`
    cannot drift apart in how honestly they report failure.

    ``payload`` exists so ``autoloop_start`` — the one verb of the family that
    carries args — routes through this same decision instead of forking a
    second transport. That fork is precisely how a start could end up
    reporting failure less honestly than the stop that has to clean up after
    it. Verbs with no args pass ``None`` and send ``{}`` exactly as before."""
    resolved_run_dir = run_dir or _env.resolve_run_dir()
    try:
        resp = _cli.send_request(verb, payload or {}, run_dir=resolved_run_dir)
    except Exception as e:  # noqa: BLE001
        return AutoLoopResult(ok=False, reason="unknown", detail=f"{type(e).__name__}: {e}")
    if resp.get("ok"):
        return AutoLoopResult(ok=True, raw=resp)
    return AutoLoopResult(
        ok=False,
        reason=resp.get("error") or "unknown",
        detail=resp.get("detail") or resp.get("error") or None,
        raw=resp,
    )


@dataclass(frozen=True)
class ReflexResult:
    """Typed outcome of :func:`reflex_propose` (WO-REFLEX-CLIENT-REACH).

    Its own type rather than a reuse of :class:`AutoLoopResult`, for the reason
    that class gives about :class:`ExploreResult`: the verbs answer about
    different things, and a shared type invites a caller to hand one verb's
    outcome to another verb's consumer with nothing catching it. Here the
    hazard is sharper than usual -- an ``AutoLoopResult`` describes a run that
    is *doing* something, and this describes a proposal that is not.

    ``macro`` is a suggestion and **nothing more**. It is not armed, not
    queued, and not executed; the taught run path still requires the human's
    ``y`` at arm-confirm, and `rules/reflex.py` documents the two landings
    that stay inert regardless of what this names.

    ``ok`` is about the *transport*, not the decision. A proposal that
    resolves to a STOP is a perfectly successful call: ``ok=True`` with
    ``macro=None`` and a populated ``stop_reason``. Collapsing those would
    make "the daemon refused to answer" and "the library answered, and the
    answer is do nothing" the same value, which is the distinction
    `rules/reflex.py` split ``autopilot_rules_unreadable`` out of
    ``autopilot_no_candidates`` to preserve. A caller must branch on ``ok``
    first and only then read ``macro``.
    """

    ok: bool
    macro: str | None = None
    rule_id: str | None = None
    stop_reason: str | None = None
    classification: str | None = None
    reason: str | None = None   # machine-readable transport failure when ok=False
    detail: str | None = None
    raw: dict | None = None


def reflex_propose(*, run_dir: Path | None = None) -> ReflexResult:
    """Ask the daemon what the taught rule library proposes for the live screen.

    **Read-only.** Sends the ``reflex`` control verb and nothing else; adds no
    keystroke path and takes no control lock. Never raises -- a dead socket, a
    missing daemon, or a malformed reply all come back as ``ok=False`` with a
    type-named reason, the same transport-honesty contract ``_autoloop_verb``
    exists to keep from drifting between verbs.

    The rule **writer** does not exist yet, so on a normal install
    ``state/rules/`` is absent and the honest answer is a STOP reading
    ``autopilot_no_candidates:<screen_class>``. That is a successful call
    reporting an empty library, not a failure -- see :class:`ReflexResult`.
    """
    resolved_run_dir = run_dir or _env.resolve_run_dir()
    try:
        resp = _cli.send_request("reflex", {}, run_dir=resolved_run_dir)
    except Exception as e:  # noqa: BLE001
        return ReflexResult(ok=False, reason="unknown", detail=f"{type(e).__name__}: {e}")
    if not isinstance(resp, dict):
        # A non-dict reply is a broken transport, not an empty proposal.
        return ReflexResult(ok=False, reason="malformed_response",
                            detail=type(resp).__name__)
    if not resp.get("ok"):
        return ReflexResult(
            ok=False,
            reason=resp.get("error") or "unknown",
            detail=resp.get("detail") or resp.get("error") or None,
            raw=resp,
        )
    # `.get` on a missing/!dict `reflex` block yields None everywhere rather
    # than raising: an older daemon that does not know this verb answers `ok`
    # without the block, and a client that crashed on it would turn a version
    # skew into a traceback instead of an empty proposal.
    block = resp.get("reflex")
    block = block if isinstance(block, dict) else {}
    return ReflexResult(
        ok=True,
        macro=block.get("macro"),
        rule_id=block.get("rule_id"),
        stop_reason=block.get("stop_reason"),
        classification=resp.get("classification"),
        raw=resp,
    )


def explore_start_for_profile(
    profile: object,
    *,
    min_sectors: int | None = None,
    turn_budget: int | None = None,
    intent: str | None = None,
    dock_new_ports: bool | None = None,
    fight_tolls: bool | None = None,
    run_dir: Path | None = None,
) -> ExploreResult:
    """Convenience wrapper: derive *world_id* from *profile*, then call
    :func:`explore_start`.

    *profile* must expose ``.host``, ``.game_letter``, and ``.handle``
    (a ``credentials.Profile`` or any duck-typed equivalent). Raises
    :class:`world_identity.WorldIdentityError` if the profile lacks a
    required field — this is a programmer error (bad profile object), not
    an expected transport failure, so it is not swallowed.
    """
    world_id = _wi.world_id_from_profile(profile)
    return explore_start(
        world_id,
        min_sectors=min_sectors,
        turn_budget=turn_budget,
        intent=intent,
        dock_new_ports=dock_new_ports,
        fight_tolls=fight_tolls,
        run_dir=run_dir,
    )
