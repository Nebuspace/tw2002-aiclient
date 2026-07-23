"""Thin adapters from the product TUI onto twclient backend APIs."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

from twclient import credentials, servers


def list_launcher_rows(profiles_path=None, servers_path=None):
    return credentials.list_profile_summaries(
        profiles_path=profiles_path, servers_path=servers_path
    )


def list_server_keys(servers_path=None):
    return [rec["key"] for rec in servers.list_servers(path=servers_path)]


def server_label(key, servers_path=None):
    rec = servers.get_server(key, path=servers_path)
    return f"{rec['key']}  {rec['hostname']}:{rec['port']}"


def create_profile(**kwargs):
    return credentials.create_profile(**kwargs)


def set_autopilot(profile_name, enabled, profiles_path=None):
    credentials.set_profile_autopilot(profile_name, enabled, profiles_path=profiles_path)


def load_profile(name, profiles_path=None, servers_path=None):
    return credentials.load_profile(
        name, profiles_path=profiles_path, servers_path=servers_path
    )


def save_password(profile_name, password, secrets_path=None):
    if password:
        credentials.save_password(profile_name, password, secrets_path=secrets_path)


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
    """``autopilot_start`` — fail-closed on profile.autonomous inside daemon."""
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
