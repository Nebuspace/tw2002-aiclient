"""Thin adapters from the product TUI onto twclient backend APIs."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

from twclient import credentials, servers
from twclient.intervention_labels import (
    INTERVENTION_REASON_LABELS,
    intervention_reason_label,
)


def _retired_profile_names(profiles_path=None) -> set[str]:
    """Names with ``retired = true`` in profiles.toml (launcher hygiene).

    Profiles stay on disk (world-models preserved); the product launcher
    greys them and skips select. Safe-by-omission: missing/false = active.
    """
    path = Path(profiles_path) if profiles_path else credentials.PROFILES_PATH
    try:
        data = credentials._load_toml(path)
    except credentials.CredentialError:
        return set()
    return {
        name
        for name, body in data.items()
        if isinstance(body, dict) and bool(body.get("retired", False))
    }


def list_launcher_rows(profiles_path=None, servers_path=None):
    """Launcher rows: active first, then retired (marked, still listed)."""
    rows = credentials.list_profile_summaries(
        profiles_path=profiles_path, servers_path=servers_path
    )
    retired = _retired_profile_names(profiles_path=profiles_path)
    for row in rows:
        row["retired"] = row["name"] in retired
    # Active first (False < True), then name for stable order within each group.
    rows.sort(key=lambda r: (bool(r.get("retired")), r["name"]))
    return rows


def list_server_keys(servers_path=None):
    return [rec["key"] for rec in servers.list_servers(path=servers_path)]


def server_label(key, servers_path=None):
    rec = servers.get_server(key, path=servers_path)
    return f"{rec['key']}  {rec['hostname']}:{rec['port']}"


def create_profile(name, **kwargs):
    """Create a profiles.toml section — non-secret shape only.

    Password is never accepted here. Supply credentials out-of-band via
    ``TW2002_PASSWORD_<PROFILE>`` or ``config/secrets.json`` before the
    first ``ensure`` / play (see ``docs/OPERATOR.md``).
    """
    # Refuse accidental password kwargs so create cannot become a secret sink.
    if "password" in kwargs:
        raise TypeError(
            "create_profile does not accept password — use secrets.json / env"
        )
    return credentials.create_profile(name, **kwargs)


def set_autopilot(profile_name, enabled, profiles_path=None):
    credentials.set_profile_autopilot(profile_name, enabled, profiles_path=profiles_path)


def load_profile(name, profiles_path=None, servers_path=None):
    return credentials.load_profile(
        name, profiles_path=profiles_path, servers_path=servers_path
    )


def resolve_run_dir(profile_name=None, run_dir=None) -> Path:
    """Daemon run directory for product play (WO-RUN-DIR-DEFAULT).

    Priority:
      1. explicit ``run_dir`` argument
      2. ``TW_RUN_DIR`` env (absolute, or relative to project root) — opt-in
         isolation e.g. ``TW_RUN_DIR=run/rogue`` for the live test seat
      3. default ``run/`` under the project root (one shared runtime)
    """
    import os

    from twclient.cli import PROJECT_ROOT, RUN_DIR

    if run_dir is not None:
        return Path(run_dir)
    env = (os.environ.get("TW_RUN_DIR") or "").strip()
    if env:
        p = Path(env).expanduser()
        return p if p.is_absolute() else (PROJECT_ROOT / p)
    return Path(RUN_DIR)


def default_run_dir_for_profile(profile_name: str) -> Path:
    """Back-compat alias — prefer ``resolve_run_dir``.

    Historically returned ``run/<profile>/``; product default is now shared
    ``run/`` (isolation via ``TW_RUN_DIR``).
    """
    return resolve_run_dir(profile_name=profile_name)


def _configure(run_dir: Path | str):
    from twclient import cli as twcli

    twcli._configure_run_paths(str(run_dir))


def ensure_session(profile_name, *, run_dir=None, timeout=60.0):
    """Spawn daemon if needed and drive ``ensure`` to main_command.

    Reuses ``twclient.cli`` spawn/ensure paths — no duplicate login logic.
    Returns the daemon JSON response dict (``ok`` / ``error`` / screen…).
    """
    from twclient import cli as twcli

    run_dir = resolve_run_dir(profile_name=profile_name, run_dir=run_dir)
    _configure(run_dir)
    twcli._active_run_dir.mkdir(parents=True, exist_ok=True)
    twcli.LOG_DIR.mkdir(exist_ok=True)

    try:
        profile = credentials.load_profile(profile_name)
    except credentials.CredentialError as e:
        return {"ok": False, "error": str(e)}

    if not (twcli.daemon_alive() and twcli._active_sock_path.exists()):
        daemon_log = open(twcli._active_run_dir / "twd.stderr.log", "ab")
        cmd = [
            str(twcli.DAEMON_SCRIPT),
            "--host", profile.host,
            "--port", str(profile.port),
            "--run-dir", str(twcli._active_run_dir),
            "--log-dir", str(twcli.LOG_DIR),
        ]
        subprocess.Popen(
            cmd,
            cwd=str(twcli.PROJECT_ROOT),
            stdout=daemon_log,
            stderr=daemon_log,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
        deadline = time.time() + 10
        while time.time() < deadline and not twcli._active_sock_path.exists():
            time.sleep(0.1)
        if not twcli._active_sock_path.exists():
            return {
                "ok": False,
                "error": (
                    f"daemon failed to start (no socket after 10s) — "
                    f"see {twcli._active_run_dir / 'twd.stderr.log'}"
                ),
            }
        # First settled screen (mirrors ``tw ensure`` / ``tw start``).
        twcli.send_request("read", {"timeout": timeout}, timeout=timeout + 5)

    return twcli.send_request(
        "ensure",
        {"target": "main_command", "profile": profile_name},
        timeout=timeout + 5,
    )


def arm_autopilot(profile_name, *, run_dir=None, max_ticks=None, cash_floor=None):
    """``autopilot_start`` — fail-closed on profile.autonomous inside daemon.

    ``max_ticks=None`` (default) arms a continuous run; pass an int to
    apply an optional safety ceiling (see ``AutopilotLoop`` /
    ``--max-ticks``).
    """
    from twclient import cli as twcli

    run_dir = resolve_run_dir(profile_name=profile_name, run_dir=run_dir)
    _configure(run_dir)
    args = {"profile": profile_name, "max_ticks": max_ticks, "cash_floor": cash_floor}
    return twcli.send_request("autopilot_start", args)


def stop_autopilot(*, run_dir=None, profile_name=None):
    """``autopilot_stop`` — leaves session connected, mode back to AI_PILOT."""
    from twclient import cli as twcli

    if run_dir is None:
        run_dir = resolve_run_dir(profile_name=profile_name)
    _configure(run_dir)
    return twcli.send_request("autopilot_stop", {})


def ensure_and_sync_autopilot(profile_name, *, run_dir=None, timeout=60.0):
    """Play-screen entry: ensure session, then arm/disarm from profile flag.

    Autopilot ON → ``autopilot_start`` (trainer on next loop boundary).
    Autopilot OFF → ``autopilot_stop`` (manual; safe if already stopped).
    """
    run_dir = resolve_run_dir(profile_name=profile_name, run_dir=run_dir)
    ensure_resp = ensure_session(profile_name, run_dir=run_dir, timeout=timeout)
    if not ensure_resp.get("ok"):
        return {
            "ok": False,
            "phase": "ensure",
            "ensure": ensure_resp,
            "autopilot": None,
            "message": ensure_resp.get("error") or "ensure failed",
        }

    try:
        profile = credentials.load_profile(profile_name)
        want_ap = bool(profile.autopilot)
    except credentials.CredentialError as e:
        return {
            "ok": False,
            "phase": "profile",
            "ensure": ensure_resp,
            "autopilot": None,
            "message": str(e),
        }

    if want_ap:
        ap_resp = arm_autopilot(profile_name, run_dir=run_dir)
        if not ap_resp.get("ok"):
            return {
                "ok": False,
                "phase": "autopilot_start",
                "ensure": ensure_resp,
                "autopilot": ap_resp,
                "message": ap_resp.get("error") or "autopilot start failed",
            }
        return {
            "ok": True,
            "phase": "armed",
            "ensure": ensure_resp,
            "autopilot": ap_resp,
            "message": "ensured · Autopilot armed",
        }

    ap_resp = stop_autopilot(run_dir=run_dir)
    # stop may fail if never started — treat as manual OK when ensure succeeded
    return {
        "ok": True,
        "phase": "manual",
        "ensure": ensure_resp,
        "autopilot": ap_resp,
        "message": "ensured · Autopilot OFF (manual)",
    }


def intervention_from_status(status_resp):
    """Extract the WS5 ``intervention`` block from a ``tw status --json`` dict."""
    if not isinstance(status_resp, dict):
        return None
    block = status_resp.get("intervention")
    if isinstance(block, dict):
        return block
    return {
        "needs_attention": False,
        "reasons": [],
        "autopilot": status_resp.get("autopilot")
        or {
            "running": False,
            "ticks_done": 0,
            "last_error": None,
            "last_reason": None,
        },
        "mode": status_resp.get("mode") or "ai_pilot",
    }


def poll_status(profile_name=None, *, run_dir=None):
    """Read-only ``status`` poll for the product play screen."""
    from twclient import cli as twcli

    run_dir = resolve_run_dir(profile_name=profile_name, run_dir=run_dir)
    _configure(run_dir)
    try:
        return twcli.send_request("status", {})
    except Exception as e:  # noqa: BLE001 — surface as failed status for UI
        return {"ok": False, "error": str(e)}


def goals_snapshot_from_status(status_resp):
    """Thin GoalsSnapshot from ``tw status`` fields (no world-model crawl)."""
    from twclient.spectate_layout import GoalsSnapshot

    status_resp = status_resp if isinstance(status_resp, dict) else {}
    credits = status_resp.get("credits")
    turns = status_resp.get("turns_left")
    fighters = status_resp.get("fighters_aboard")
    return GoalsSnapshot(
        turns_known=turns is not None,
        turns_count=turns,
        credits_known=credits is not None,
        credits_amount=credits,
        fighters_known=fighters is not None,
        fighters_count=fighters,
    )


def sector_from_status(status_resp):
    """Best-effort current sector from the status prompt line."""
    from twclient.state_parser import sector_from_command_prompt

    if not isinstance(status_resp, dict):
        return None
    prompt = status_resp.get("prompt") or ""
    return sector_from_command_prompt(prompt)


def compose_play_panels(status_resp, *, width: int = 36) -> dict:
    """Read-only play chrome from spectate compose helpers + status JSON.

    Returns dict of panel title → list[str] plus a metrics strip.
    Reuses ``spectate_layout`` — no duplicate chain/trade ranking.
    """
    from twclient.spectate_layout import (
        compose_decisions_placeholder,
        compose_intervention_strip,
        compose_primary_goals_lines,
        compose_priorities_lines,
        format_autopilot_trace_lines,
    )

    width = max(12, int(width))
    status_resp = status_resp if isinstance(status_resp, dict) else {}
    snap = goals_snapshot_from_status(status_resp)
    trace = status_resp.get("autopilot_trace")
    intervention = intervention_from_status(status_resp) or {}
    ap = intervention.get("autopilot") or status_resp.get("autopilot") or {}

    sector = sector_from_status(status_resp)
    credits = status_resp.get("credits")
    turns = status_resp.get("turns_left")
    metrics = (
        f"Sector {sector if sector is not None else '?'}  "
        f"Credits {credits if credits is not None else '?'}  "
        f"Turns {turns if turns is not None else '?'}"
    )

    goals = ["— GOALS —"] + compose_primary_goals_lines(snap, width=width)
    focus = ["— FOCUS —"] + compose_priorities_lines(trace, width=width)
    if trace:
        decisions = ["— DECISIONS —"] + format_autopilot_trace_lines(trace, cols=width)
    else:
        decisions = ["— DECISIONS —"] + compose_decisions_placeholder()

    reason_labels = []
    log_lines = ["— LOG —"]
    for reason in intervention.get("reasons") or []:
        if isinstance(reason, dict):
            label = intervention_reason_label(reason.get("code"))
        else:
            label = intervention_reason_label(reason)
        reason_labels.append(label)
        log_lines.append(f"· {label}"[:width])
    last_err = ap.get("last_error")
    last_reason = ap.get("last_reason")
    if last_err:
        log_lines.append(f"halt: {last_err}"[:width])
    elif last_reason:
        log_lines.append(str(last_reason)[:width])
    if len(log_lines) == 1:
        log_lines.append("—")

    # Same strip formatter as ops spectate (``! label; …``); healthy → None.
    needs_attention = bool(intervention.get("needs_attention"))
    attention_banner = compose_intervention_strip(status_resp)
    if attention_banner:
        log_lines.insert(1, attention_banner)

    return {
        "metrics": metrics,
        "mode": intervention.get("mode") or status_resp.get("mode") or "ai_pilot",
        "needs_attention": needs_attention,
        "attention_banner": attention_banner,
        "reason_labels": reason_labels,
        "goals": goals,
        "focus": focus,
        "decisions": decisions,
        "log": log_lines,
        "priorities": goals + [""] + focus,  # PRIORITIES chrome = GOALS+FOCUS
    }


def toggle_autopilot_and_sync(profile_name, *, run_dir=None):
    """Persist toggle, then arm/stop the live trainer to match."""
    profile = credentials.load_profile(profile_name)
    new_on = not bool(profile.autopilot)
    set_autopilot(profile_name, new_on)
    run_dir = resolve_run_dir(profile_name=profile_name, run_dir=run_dir)
    if new_on:
        ap_resp = arm_autopilot(profile_name, run_dir=run_dir)
        label = "ON"
    else:
        ap_resp = stop_autopilot(run_dir=run_dir)
        label = "OFF"
    ok = bool(ap_resp.get("ok")) or (not new_on)
    return {
        "ok": ok,
        "autopilot": new_on,
        "response": ap_resp,
        "message": (
            f"Autopilot {label} — saved"
            + ("" if ok else f" ({ap_resp.get('error') or 'runtime sync failed'})")
        ),
    }


def run_attach(profile_name=None, *, run_dir=None):
    """Hand the keyboard via ``interactive_app`` (same engine as ``tw attach``).

    Takes control_lock MODE_HUMAN for the attach connection lifetime;
    keystrokes are human-only — the product spectator/play panels never
    send game I/O. Caller must not own the terminal in an active curses
    session; use ``suspend_and_attach`` from the play screen.

    If Autopilot is running, stop the runtime trainer first so
    ``take_human`` is not refused with ``locked_by_auto_loop``. Does
    **not** write profile Autopilot OFF — that remains the product
    toggle; attach only clears the live lock.
    """
    from twclient import cli as twcli
    from twclient import interactive_app

    run_dir = resolve_run_dir(profile_name=profile_name, run_dir=run_dir)
    _configure(run_dir)
    if not twcli._active_sock_path.exists():
        return {"ok": False, "code": 1, "error": "daemon_not_running"}

    # Explicit stop-then-attach: MODE_AUTO_LOOP blocks take_human().
    # Only when Autopilot reports running — LoopPlayer's AUTO_LOOP is a
    # different stop verb; do not fail-closed on autopilot_not_started.
    # Does not write profile Autopilot OFF.
    stopped_ap = False
    status = poll_status(profile_name, run_dir=run_dir)
    ap = (status if isinstance(status, dict) else {}).get("autopilot") or {}
    if bool(ap.get("running")):
        stop_resp = stop_autopilot(run_dir=run_dir, profile_name=profile_name)
        if not stop_resp.get("ok"):
            err = stop_resp.get("error") or "autopilot_stop_failed"
            return {
                "ok": False,
                "code": 1,
                "error": err,
                "autopilot_stopped": False,
                "message": f"attach blocked — could not stop Autopilot ({err})",
            }
        stopped_ap = True

    code = interactive_app.run_interactive_attach(
        twcli._active_sock_path, twcli._active_pid_path
    )
    msg = "detached · back to play" if code == 0 else f"attach exited {code}"
    if stopped_ap and code == 0:
        msg = "detached · Autopilot stopped for attach · back to play"
    return {
        "ok": code == 0,
        "code": int(code),
        "error": None if code == 0 else f"attach exited {code}",
        "autopilot_stopped": stopped_ap,
        "message": msg,
    }


def suspend_and_attach(stdscr, profile_name=None, *, run_dir=None):
    """Suspend outer curses, run ``tw attach`` engine, resume play panels.

    Same def_prog_mode/endwin/reset idiom as ``spectate_app``'s A/a
    path — but calls ``interactive_app`` in-process (thin wrap, no second
    attach engine). Never raises into the play loop; failures become a
    status string. Always restores curses via ``finally``.
    """
    import curses

    error = None
    curses.def_prog_mode()
    curses.endwin()
    try:
        try:
            result = run_attach(profile_name, run_dir=run_dir)
        except Exception as e:  # noqa: BLE001 — surface on play status line
            error = f"attach failed: {e}"
            result = {"ok": False, "error": error}
        else:
            if not result.get("ok"):
                error = result.get("error") or result.get("message") or "attach failed"
    finally:
        curses.reset_prog_mode()
        try:
            stdscr.clear()
            stdscr.refresh()
        except curses.error:
            pass
    return error
