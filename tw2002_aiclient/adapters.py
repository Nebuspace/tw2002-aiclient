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
