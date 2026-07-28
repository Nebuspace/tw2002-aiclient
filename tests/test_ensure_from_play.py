"""End-to-end proof for WO-P2-020's Accept: `ensure_session()` drives a
REAL daemon subprocess, over a REAL (loopback) telnet connection, through
a scripted RETURNING login, to `main_command` -- with NO real game, CI-
provable, via `tests/fake_twgs.py`.

**Why this test writes to the REAL `config/profiles.toml` (not a
tmp_path-isolated one), despite `credentials.PROFILES_PATH` looking
monkeypatchable:** `ensure_raw()` (session/cli.py) resolves host/port
in-process (a monkeypatch DOES work there) but then spawns the daemon as
a SEPARATE PROCESS (`subprocess.Popen(["-m", "tw2002_aiclient.session.
daemon", ...])`). That daemon's own `_dispatch_ensure` (session/
protocol.py) re-reads `credentials.PROFILES_PATH` fresh, inside its OWN
freshly-imported process, for the profile's handle/game_letter/
allow_register -- an in-process `monkeypatch.setattr` on this test's own
`credentials` module object never crosses that subprocess boundary.
Unlike `env.RUN_DIR_VAR`/`TW_RUN_DIR`, `credentials.py` has NO env-var
override for `PROFILES_PATH`/`SECRETS_PATH`/`CONFIG_DIR` -- so the ONLY
seam that reaches the spawned daemon is the real on-disk path both
processes agree on. `config/profiles.toml` is gitignored and (confirmed
via `git status`/`git log`) currently absent in this repo -- exactly the
local/ephemeral slot this code is designed to read from -- so
`_temporary_profile()` below writes ONE test section into it and deletes
it again in a `finally`, flock-serialized against a sibling process doing
the same. **Never a backup-and-restore of a PRESENT file:** a hard-killed
test process (SIGKILL, a CI timeout) skips a generator's `finally` same
as any other Python teardown, which would otherwise leave an operator's
real config permanently replaced by the test's content -- so a file
that's already present is left completely untouched and the whole test
SKIPS instead of ever touching it (team-lead hardening, 2026-07-23).
Flagged to the team lead as a follow-on-WO candidate: a `TW_CONFIG_DIR`
override mirroring `TW_RUN_DIR` would remove the need for this real-path
dance entirely.

The one Accept criterion that genuinely never needs the daemon subprocess
to see a profile at all (`test_ensure_bounded_typed_error_on_dead_port`
below -- the daemon crashes on connection refusal before it ever reaches
`_dispatch_ensure`) uses a plain `monkeypatch.setattr(credentials,
"PROFILES_PATH", ...)` against an isolated `tmp_path` file instead, same
as the WO originally described.
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

from tw2002_aiclient import adapters
from tw2002_aiclient.session import credentials
from tw2002_aiclient.session import env as session_env

from .fake_twgs import FakeTWGS

_PY = sys.executable


# -- process/port helpers ---------------------------------------------------

@contextlib.contextmanager
def _short_run_dir():
    """A run/ directory OUTSIDE pytest's own `tmp_path` tree.

    `tmp_path` nests under `.../pytest-of-<user>/pytest-<N>/<test-name>0/`
    -- routinely 90+ characters before `run/twd.sock` is even appended,
    which blows macOS's ~104-byte `AF_UNIX` path ceiling (confirmed live:
    `OSError: AF_UNIX path too long` out of `ThreadingUnixServer.
    server_bind()`). `tempfile.mkdtemp()`'s own default base is flat and
    short enough with room to spare. Always removed on exit, including a
    daemon's still-open pidfile/socket left behind by a test that didn't
    clean up (best-effort -- a genuinely orphaned live process is the
    caller's own job to kill first)."""
    d = tempfile.mkdtemp(prefix="tw2002e2e-")
    try:
        yield Path(d) / "run"
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _grab_and_release_free_port(host: str = "127.0.0.1") -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((host, 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _wait_for_pid_exit(pid: int, timeout: float = 5.0) -> bool:
    """The daemon is `ensure_raw()`'s own `subprocess.Popen` child --
    i.e. OUR direct child, just never `.wait()`-ed by anything (that
    Popen object is a local inside `ensure_raw()`, discarded once it
    returns). A plain `os.kill(pid, 0)` liveness probe alone is NOT
    enough here: after SIGTERM, an un-reaped own-child becomes a zombie,
    and a zombie's PID stays valid (kill(pid, 0) keeps succeeding) until
    something calls `waitpid()` on it -- caught live, a `_kill_daemon()`
    that only signalled and probed left a permanent zombie behind that
    this function's own timeout-based probe could never see die. Reap it
    ourselves via `WNOHANG`; fall back to the plain probe for a PID that
    was never our child (or was already reaped by someone/something else)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            reaped_pid, _status = os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            try:
                os.kill(pid, 0)
            except OSError:
                return True
        else:
            if reaped_pid == pid:
                return True
        time.sleep(0.05)
    return False


def _kill_daemon(pid: int):
    """Never `cli stop` (the graceful QUIT sequence needs a fake server
    still driving its own script -- see fake_twgs.py's terminal-state
    comment) -- SIGTERM, escalating to SIGKILL if it doesn't exit
    promptly. Always leaves no live process behind."""
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return  # already gone
    if not _wait_for_pid_exit(pid, timeout=5.0):
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
        _wait_for_pid_exit(pid, timeout=5.0)


# -- the real-profiles.toml dance (see module docstring) --------------------

@contextlib.contextmanager
def _temporary_profile(section_name: str, **fields):
    """Writes ONE `[section_name]` table into the REAL `config/
    profiles.toml` for the duration of the `with` block -- see module
    docstring for why. Team-lead hardening (2026-07-23): this NEVER backs
    up and overwrites an already-present real file, even temporarily. A
    hard-killed test process (SIGKILL, a CI timeout) skips this
    generator's OWN `finally` just like any other Python teardown --
    which, under the earlier backup/restore design, would have left an
    operator's real profiles.toml permanently replaced by the test's
    content. Instead: a file that's genuinely ABSENT (today's clean-
    checkout/CI state) is safe to create-then-delete; a file that's
    already PRESENT is left completely untouched and the whole test
    SKIPS via `pytest.skip()` instead of ever touching it."""
    path = credentials.PROFILES_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.parent / ".profiles-test.lock"
    lock_fh = open(lock_path, "a+", encoding="utf-8")
    fcntl.flock(lock_fh, fcntl.LOCK_EX)
    try:
        # This fixture only ever WRITES to profiles.toml (the password
        # always goes through TW2002_PASSWORD_<PROFILE> env, never
        # secrets.json) -- but secrets.json is checked too, defensively,
        # since both live under the same real, un-isolated CONFIG_DIR and
        # a future edit here should never be able to silently start
        # writing to it without this guard already in place.
        if path.exists() and path.read_text(encoding="utf-8").strip():
            pytest.skip(
                "real config/profiles.toml present -- WO-P2-020 proof needs the "
                "TW_CONFIG_DIR isolation seam; skipping to avoid clobbering operator config"
            )
        secrets_path = credentials.SECRETS_PATH
        if secrets_path.exists() and secrets_path.read_text(encoding="utf-8").strip():
            pytest.skip(
                "real config/secrets.json present -- WO-P2-020 proof needs the "
                "TW_CONFIG_DIR isolation seam; skipping to avoid clobbering operator config"
            )
        lines = [f"\n[{section_name}]"]
        for key, value in fields.items():
            if isinstance(value, bool):
                lines.append(f"{key} = {'true' if value else 'false'}")
            elif isinstance(value, int):
                lines.append(f"{key} = {value}")
            else:
                lines.append(f'{key} = "{value}"')
        block = "\n".join(lines) + "\n"
        with open(path, "a", encoding="utf-8") as f:
            f.write(block)
        try:
            yield
        finally:
            path.unlink(missing_ok=True)
    finally:
        fcntl.flock(lock_fh, fcntl.LOCK_UN)
        lock_fh.close()
        # Best-effort -- leaves no stray untracked file behind in the real
        # config/ dir for the common case (no concurrent sibling holding
        # it open); harmless if a sibling test IS concurrently using it,
        # since unlinking a path a peer already has open doesn't disturb
        # that peer's own still-valid file descriptor on POSIX.
        try:
            lock_path.unlink(missing_ok=True)
        except OSError:
            pass


# -- Accept 1-4: full flow against the fake TWGS server ---------------------

def test_ensure_from_play_full_flow(tmp_path, monkeypatch):
    """One connected proof of WO-P2-020's Accept criteria 1-4 (kept in one
    test rather than four, since each needs the SAME already-logged-in
    daemon -- standing up a fresh fake server + daemon per criterion would
    just re-run the same ~4s login four times for no extra coverage)."""
    handle = "AEGIS"
    game_letter = "F"
    password = "sAvEd123Test"
    profile_name = "wo_p2_020_e2e"

    monkeypatch.setenv(credentials._env_var_name(profile_name), password)

    daemon_pid = None
    log_dir = session_env.LOG_DIR
    logs_before = set(log_dir.glob("session-*.log")) if log_dir.exists() else set()

    with FakeTWGS(handle=handle, game_letter=game_letter, password=password) as fake, \
            _short_run_dir() as run_dir:
        with _temporary_profile(
            profile_name,
            host="127.0.0.1",
            port=fake.port,
            game_letter=game_letter,
            handle=handle,
            allow_register=False,
        ):
            try:
                # -- Accept 1: ensure_session reaches main_command ---------
                result = adapters.ensure_session(profile_name, run_dir=run_dir, timeout=30.0)
                # Capture the pid BEFORE any assertion that could raise --
                # a daemon can be up (and need killing) even when a later
                # assertion in this block fails; capturing it late left a
                # live orphan behind on every assertion failure caught
                # live during this test's own debugging.
                pid_path = session_env.pid_path(run_dir)
                if pid_path.exists():
                    daemon_pid = int(pid_path.read_text().strip())
                assert not fake.errors, f"fake TWGS script desync: {fake.errors}"
                assert result.ok is True, result
                assert result.classification == "main_command"

                # -- Accept 2: run/ files (socket + pidfile) exist ---------
                sock_path = session_env.socket_path(run_dir)
                assert sock_path.exists()
                assert pid_path.exists()
                assert daemon_pid is not None

                # -- Accept 3: status from a 2nd shell (fresh subprocess) --
                status_env = {**os.environ, session_env.RUN_DIR_VAR: str(run_dir)}
                proc = subprocess.run(
                    [_PY, "-m", "tw2002_aiclient.session.cli", "status", "--json"],
                    cwd=str(session_env.PROJECT_ROOT),
                    env=status_env,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                assert proc.returncode == 0, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
                status = json.loads(proc.stdout)
                assert status["ok"] is True
                assert status["classification"] == "main_command"
                # WO-STATUS-EXPOSE-REPLAY-ARM: arm always present; after ensure
                # it reports the stamped profile + reconnect (host, port).
                assert "replay_arm" in status
                arm = status["replay_arm"]
                assert arm["armed"] is True
                assert arm["profile"] == profile_name
                assert arm["host"] == "127.0.0.1"
                assert arm["port"] == fake.port
                assert password not in proc.stdout

                # -- Accept 4: idempotent 2nd ensure, no 2nd daemon --------
                result2 = adapters.ensure_session(profile_name, run_dir=run_dir, timeout=30.0)
                assert result2.ok is True
                assert result2.classification == "main_command"
                assert int(pid_path.read_text().strip()) == daemon_pid, "a 2nd daemon was spawned"

                assert not fake.errors, f"fake TWGS script desync: {fake.errors}"

                # -- Transcript-clean: the password never lands in the log -
                # `logs/` is the SHARED, un-isolated project log dir (same
                # `credentials.py`-class gap as the profiles.toml dance --
                # see module docstring; pending the TW_CONFIG_DIR seam, no
                # per-daemon isolation exists), so a concurrent sibling's
                # daemon can write its OWN new `session-*.log` into this
                # same before/after diff. That's fine for the security
                # check below (password absence is a valid, meaningful
                # assertion over EVERY freshly-written transcript during
                # this window, ours or a sibling's) but NOT fine for a
                # positive "our redaction marker is in there" assertion --
                # team-lead finding, 2026-07-23: a sibling's own log
                # legitimately has no reason to carry OUR marker text, so
                # requiring it in every new log is a false failure under
                # real concurrency, not a real signal. This assertion is
                # narrower and non-negotiable: the plaintext password must
                # never appear in ANY transcript written during this run.
                # Positive redaction coverage lives elsewhere: Cipher's
                # WO-P2-020 audit traces every secret send through
                # `log_redacted()` end to end, and the Wave-2 in-session
                # manual smoke confirmed a real password on the wire shows
                # as `<redacted>` in both `last_sent` and the transcript.
                # `test_login_redaction.py`/`test_credentials.py`/
                # `test_logging_util.py`/`test_session.py`/
                # `test_connection.py` are NOT currently collectable in
                # this checkout (still `import twclient`, the dead
                # package) -- pending the test-suite rehab's re-point,
                # not a citable proof today.
                logs_after = set(log_dir.glob("session-*.log")) if log_dir.exists() else set()
                new_logs = logs_after - logs_before
                assert new_logs, "expected the daemon to have written a transcript log"
                for log_path in new_logs:
                    content = log_path.read_text(encoding="utf-8", errors="replace")
                    assert password not in content, f"password leaked into {log_path}"
            finally:
                if daemon_pid is not None:
                    _kill_daemon(daemon_pid)

    # -- orphan-free: no live daemon process survives teardown ------------
    if daemon_pid is not None:
        assert _wait_for_pid_exit(daemon_pid, timeout=1.0), "daemon process survived teardown"


# -- Accept 5: bounded typed error, never a silent hang ---------------------

def test_ensure_bounded_typed_error_on_dead_port(tmp_path, monkeypatch):
    """A profile pointing at a port with nothing listening must produce a
    typed failure within a bounded margin of the requested timeout --
    never a silent hang. No fake server, no real-config write needed: the
    daemon subprocess crashes on `session.start()`'s connection refusal
    before it ever reaches `_dispatch_ensure`'s profile read at all (see
    module docstring)."""
    profiles_path = tmp_path / "profiles.toml"
    dead_port = _grab_and_release_free_port()
    profiles_path.write_text(
        '[deadport]\nhost = "127.0.0.1"\n'
        f"port = {dead_port}\n"
        'game_letter = "F"\nhandle = "AEGIS"\nallow_register = false\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(credentials, "PROFILES_PATH", profiles_path)

    with _short_run_dir() as run_dir:
        timeout = 3.0
        started = time.monotonic()
        result = adapters.ensure_session("deadport", run_dir=run_dir, timeout=timeout)
        elapsed = time.monotonic() - started

        assert result.ok is False
        assert result.reason in (
            adapters.REASON_SPAWN_FAILED,
            adapters.REASON_TIMEOUT,
            adapters.REASON_CONNECT_FAILED,
        ), result
        # Generous margin over the requested budget -- profile resolution +
        # subprocess startup both eat a slice of the same deadline, but this
        # must never look like an unbounded hang.
        assert elapsed < timeout + 5.0, f"took {elapsed:.1f}s against a {timeout}s budget -- looks like a hang"

        pid_path = session_env.pid_path(run_dir)
        if pid_path.exists():
            pid = int(pid_path.read_text().strip())
            _kill_daemon(pid)
