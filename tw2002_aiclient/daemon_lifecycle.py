"""App-owned daemon presence + stop helpers (client lifecycle UX).

Bounded, never-raising wrappers around the existing ``status`` / ``stop``
protocol verbs. The launcher marks at most one profile ONLINE from a
read-only status poll; whole-app quit may issue exactly one ``stop``.
Esc→launcher is outside this module's callers by design.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .cockpit import armconfirm
from .session import cli as _cli
from .session import env as _env

# Presence kinds — callers switch on these, never on raw wire strings.
PRESENCE_OFFLINE = "offline"
PRESENCE_ONLINE = "online"
PRESENCE_UNREACHABLE = "unreachable"

# Bounded budgets — presence must never stall the launcher; stop may take longer.
STATUS_TIMEOUT_S = 2.0
STOP_TIMEOUT_S = 15.0

CONFIRM = armconfirm.CONFIRM
CANCEL = armconfirm.CANCEL
CONFIRM_HINT = "y/N"
UNKNOWN_PROFILE = "?"


@dataclass(frozen=True)
class Presence:
    """Read-only daemon presence for the launcher.

    ``profile`` is set only when ``kind == PRESENCE_ONLINE`` and is the
    exact ``replay_arm.profile`` string from status — never inferred from
    host/handle.
    """

    kind: str
    profile: str | None = None
    detail: str | None = None
    raw: dict | None = None


@dataclass(frozen=True)
class StopResult:
    """Outcome of one ``stop`` attempt — never a raised exception."""

    ok: bool
    reason: str | None = None
    detail: str | None = None
    raw: dict | None = None


def read_presence(
    *,
    run_dir: Path | None = None,
    timeout: float = STATUS_TIMEOUT_S,
) -> Presence:
    """Bounded read-only ``status`` poll. Never raises.

    ONLINE only when ``connected is True`` and ``replay_arm.profile`` is a
    non-empty string. Daemon absent → offline. Transport/protocol failure
    while a pidfile looks alive → unreachable (honest unknown; no ONLINE).
    """
    resolved = run_dir or _env.resolve_run_dir()
    try:
        alive = _cli.daemon_alive(resolved)
    except Exception as e:  # noqa: BLE001 — presence must never raise
        return Presence(
            kind=PRESENCE_UNREACHABLE,
            detail=f"{type(e).__name__}: {e}",
        )
    if not alive:
        return Presence(kind=PRESENCE_OFFLINE, detail="daemon_not_running")

    try:
        resp = _cli.send_request("status", {}, timeout=float(timeout), run_dir=resolved)
    except Exception as e:  # noqa: BLE001
        return Presence(
            kind=PRESENCE_UNREACHABLE,
            detail=f"{type(e).__name__}: {e}",
        )
    if not isinstance(resp, dict):
        return Presence(
            kind=PRESENCE_UNREACHABLE,
            detail=f"malformed_response:{type(resp).__name__}",
        )
    if not resp.get("ok"):
        return Presence(
            kind=PRESENCE_UNREACHABLE,
            detail=str(resp.get("error") or "status_unreachable"),
            raw=resp,
        )

    connected = resp.get("connected")
    if connected is not True:
        return Presence(kind=PRESENCE_OFFLINE, detail="not_connected", raw=resp)

    arm = resp.get("replay_arm")
    profile = None
    if isinstance(arm, dict):
        raw_profile = arm.get("profile")
        if isinstance(raw_profile, str) and raw_profile.strip():
            profile = raw_profile
    if profile is None:
        return Presence(kind=PRESENCE_OFFLINE, detail="no_active_profile", raw=resp)
    return Presence(kind=PRESENCE_ONLINE, profile=profile, raw=resp)


def online_profile_name(presence: Presence | None) -> str | None:
    """Exact active profile name, or None when nothing may be marked ONLINE."""
    if not isinstance(presence, Presence):
        return None
    if presence.kind != PRESENCE_ONLINE:
        return None
    if not isinstance(presence.profile, str) or not presence.profile:
        return None
    return presence.profile


def is_profile_online(presence: Presence | None, profile_name: object) -> bool:
    """True only on exact name match against the single ONLINE profile."""
    active = online_profile_name(presence)
    return active is not None and profile_name == active


def presence_note(presence: Presence | None) -> str | None:
    """Operator-facing note when presence cannot mark anyone online honestly."""
    if not isinstance(presence, Presence):
        return None
    if presence.kind == PRESENCE_UNREACHABLE:
        return "daemon status unavailable — no profile marked online"
    return None


def quit_profile_label(presence: Presence | None) -> str:
    """Profile token for the quit confirm line — never empty, never secret."""
    active = online_profile_name(presence)
    if active is not None:
        return active
    return UNKNOWN_PROFILE


def compose_quit_confirm_line(profile: object = None) -> str:
    """``Stop daemon and disconnect <profile>? y/N`` — not money-path wording."""
    if isinstance(profile, str) and profile.strip():
        name = " ".join(profile.split())
    else:
        name = UNKNOWN_PROFILE
    return f"Stop daemon and disconnect {name}? {CONFIRM_HINT}"


def resolve_quit_confirm_key(key: object) -> str:
    """Same default-deny posture as the arm confirm: only ``y``/``Y`` confirm."""
    return armconfirm.resolve_arm_confirm_key(key)


def stop_daemon(
    *,
    run_dir: Path | None = None,
    timeout: float = STOP_TIMEOUT_S,
) -> StopResult:
    """Issue exactly one existing ``stop`` verb. Never raises."""
    resolved = run_dir or _env.resolve_run_dir()
    try:
        if not _cli.daemon_alive(resolved):
            return StopResult(ok=True, reason="daemon_not_running", detail="already stopped")
    except Exception as e:  # noqa: BLE001
        return StopResult(ok=False, reason="unknown", detail=f"{type(e).__name__}: {e}")

    try:
        resp = _cli.send_request("stop", {}, timeout=float(timeout), run_dir=resolved)
    except Exception as e:  # noqa: BLE001
        return StopResult(ok=False, reason="unknown", detail=f"{type(e).__name__}: {e}")
    if not isinstance(resp, dict):
        return StopResult(
            ok=False,
            reason="malformed_response",
            detail=type(resp).__name__,
        )
    if resp.get("ok"):
        return StopResult(ok=True, raw=resp)
    return StopResult(
        ok=False,
        reason=str(resp.get("error") or "stop_failed"),
        detail=str(resp.get("detail") or resp.get("error") or "stop failed"),
        raw=resp,
    )


def should_confirm_quit_stop(*, run_dir: Path | None = None) -> bool:
    """True when a daemon appears held — then the quit popup is required."""
    resolved = run_dir or _env.resolve_run_dir()
    try:
        return bool(_cli.daemon_alive(resolved))
    except Exception:  # noqa: BLE001
        # Honest unknown with a possible live daemon → still ask.
        return True
