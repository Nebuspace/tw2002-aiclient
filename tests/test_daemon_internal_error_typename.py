"""WO-AUDIT-F5-TYPE-NAME — the daemon's widest catch must put a TYPE NAME on
the wire, and the full traceback in an owner-only local log.

``daemon.py``'s ``except Exception`` around ``dispatch()`` answered
``internal_error:{e}``. Because that catch is unbounded, the string it
rendered was whatever the raising frame happened to say, and two different
classes of disclosure were reproduced through it over a REAL AF_UNIX socket:

* **server state the client never supplied** — ``ensure`` against an
  unreadable config answered ``internal_error:[Errno 21] Is a directory:
  '<absolute path>'``, putting the operator's filesystem layout on the wire;
* **the caller's own bytes, echoed** — ``history`` with a non-integer ``n``
  answered ``int()``'s ``ValueError``, which reprs its argument. Those bytes
  come out of the same ``args`` dict a ``--secret`` payload rides in.

Proven over a real ``ThreadingUnixServer`` + ``CommandHandler`` on a real
unix socket rather than by calling ``dispatch()`` directly, because the claim
under test is about *what reaches a client*, which is a wire claim.

Two things these tests deliberately do NOT claim:

* **Not "no secret can leak."** Six real secret-bearing failure paths were
  driven with a sentinel during the audit and none leaked; the leak
  *mechanism* is proven on this catch, the coincidence with a real secret
  value is unobserved. These tests pin the mechanism, not a safety verdict.
* **Not "never emit ``str(e)``."** The rule is about the CATCH: full text
  when it is narrow enough to bound the message's provenance, type name when
  it is unbounded. ``guardian.py``'s ``except (OSError, LoginError)`` keeps
  ``str(e)`` on purpose (and ``tests/test_guardian.py`` pins that text), while
  its own ``except Exception`` already records a type name. Nothing here
  should be read as licensing a sweep of the narrow sites.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import tempfile
import threading
from pathlib import Path

import pytest

# A value that could not possibly arise from anywhere but this test, so a hit
# is always a real echo and never a coincidence.
NOT_AN_INT = "NOT-AN-INT-F5-CANARY-8f21c4"
# Shaped like a credential and sitting in the SAME args dict as the value that
# actually raises -- the whole point of keeping `args` out of the local log.
SECRET_SHAPED = "hunter2-F5-CANARY-3d90ab"


class _Conn:
    connected = True


class _Session:
    """The minimum surface `dispatch()` touches on the probe paths. Both
    probes raise before any real session work, so a fuller double would only
    hide which frame actually blew up."""

    def __init__(self):
        self.conn = _Conn()
        self.history = []

    def render(self):
        return ["Command [TL=00:00:00]:[1] (?=Help)? : "]

    def render_text(self, rows=None):
        return "\n".join(rows or self.render())

    def mark_profile(self, name):
        pass


class _Daemon:
    """Real server + handler, own run-dir, own error log -- the same wiring
    `main()` does, minus the telnet session."""

    def __init__(self, run_dir, with_error_log=True):
        from tw2002_aiclient.session.control_lock import ControlLock
        from tw2002_aiclient.session.daemon import (
            CommandHandler,
            ThreadingUnixServer,
            _open_error_log,
        )

        self.run_dir = Path(run_dir)
        self.sock_path = str(self.run_dir / "s.sock")
        self.server = ThreadingUnixServer(self.sock_path, CommandHandler)
        self.server.session = _Session()
        self.server.control_lock = ControlLock()
        self.server.watch_hub = None
        self.server.request_stop = lambda: None
        self.error_log = _open_error_log(self.run_dir) if with_error_log else None
        if self.error_log is not None:
            self.server.error_log = self.error_log
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self._thread.start()

    def request(self, verb, args, timeout=5.0):
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect(self.sock_path)
        try:
            s.sendall((json.dumps({"verb": verb, "args": args}) + "\n").encode("utf-8"))
            buf = b""
            while not buf.endswith(b"\n"):
                chunk = s.recv(65536)
                assert chunk, "daemon closed the connection instead of answering"
                buf += chunk
        finally:
            s.close()
        # Return the RAW line too: an assertion about disclosure has to look
        # at every byte that crossed the wire, not just the `error` field.
        return json.loads(buf.decode("utf-8")), buf.decode("utf-8")

    def log_text(self):
        from tw2002_aiclient.session.daemon import ERRLOG_NAME

        path = self.run_dir / ERRLOG_NAME
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self._thread.join(timeout=5)
        if self.error_log is not None:
            self.error_log.close()


@pytest.fixture
def unreadable_config(monkeypatch, tmp_path):
    """Point `credentials`' module-level paths at a config dir whose
    `profiles.toml` is a DIRECTORY, so `_load_profile`'s `open(path, "rb")`
    raises `IsADirectoryError` -- the audit's reproduction, and a realistic
    stand-in for any unreadable-config OSError.

    `credentials.CONFIG_DIR` and friends are resolved at import time, so
    `TW_CONFIG_DIR` alone would not move them in an already-imported process;
    monkeypatch the resolved paths directly and let pytest undo it.
    """
    from tw2002_aiclient.session import credentials

    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "profiles.toml").mkdir()
    monkeypatch.setattr(credentials, "CONFIG_DIR", cfg)
    monkeypatch.setattr(credentials, "PROFILES_PATH", cfg / "profiles.toml")
    monkeypatch.setattr(credentials, "SECRETS_PATH", cfg / "secrets.json")
    monkeypatch.setattr(credentials, "SERVERS_PATH", cfg / "servers.toml")
    return cfg


@pytest.fixture
def run_dir():
    """A SHORT run-dir. `tmp_path` is unusable for the socket here: pytest's
    per-test path is long enough to blow AF_UNIX's ~104-byte address limit
    (`OSError: AF_UNIX path too long`), which is why conftest's own fake
    daemon uses `mkdtemp` too."""
    d = tempfile.mkdtemp(prefix="twd-f5-")
    try:
        yield Path(d)
    finally:
        shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def daemon(run_dir):
    d = _Daemon(run_dir)
    try:
        yield d
    finally:
        d.stop()


# --- the wire ---------------------------------------------------------------


def test_an_unreadable_config_does_not_put_a_filesystem_path_on_the_wire(
    daemon, unreadable_config
):
    resp, raw = daemon.request("ensure", {"profile": "anything"})

    assert resp["ok"] is False
    assert resp["error"] == "internal_error:IsADirectoryError"
    # Pre-fix this line read `internal_error:[Errno 21] Is a directory:
    # '<cfg>/profiles.toml'`. Check the whole raw frame, not just `error`:
    # disclosure is about bytes that crossed, wherever they sat.
    assert str(unreadable_config) not in raw
    assert "profiles.toml" not in raw
    assert "Errno" not in raw


def test_a_bad_int_arg_does_not_echo_the_callers_bytes_back(daemon):
    resp, raw = daemon.request("history", {"n": NOT_AN_INT})

    assert resp["ok"] is False
    assert resp["error"] == "internal_error:ValueError"
    # `int()`'s ValueError reprs its own argument -- that repr is what used to
    # ride back out. The caller's bytes and a secret share one `args` dict.
    assert NOT_AN_INT not in raw


def test_the_wire_error_is_only_ever_the_type_name(daemon, unreadable_config):
    """Both probes at once, stated as the shape rather than two literals: the
    payload after `internal_error:` must be a bare Python identifier."""
    for verb, args in (("ensure", {"profile": "anything"}), ("history", {"n": NOT_AN_INT})):
        resp, _raw = daemon.request(verb, args)
        prefix, _, payload = resp["error"].partition(":")
        assert prefix == "internal_error"
        assert payload.isidentifier(), f"{verb} leaked a message, not a type name: {payload!r}"


def test_a_clean_request_is_untouched_and_logs_nothing(daemon):
    """The catch must not have become a tax on the happy path -- and an
    unknown verb is a structured answer, not an exception, so it must not
    manufacture a log entry either."""
    ok, _ = daemon.request("history", {"n": 5})
    assert ok == {"ok": True, "history": []}

    unknown, _ = daemon.request("no-such-verb", {})
    assert unknown == {"ok": False, "error": "unknown_verb:no-such-verb"}

    assert daemon.log_text() == ""


# --- the local log ----------------------------------------------------------


def test_the_local_log_keeps_the_detail_the_wire_gave_up(daemon, unreadable_config):
    """Type-name-only would be a net loss if the detail simply vanished: before
    this change the daemon kept NO record of these exceptions anywhere, so the
    wire string was the sole diagnostic. This is the half that makes the
    change honest rather than merely quieter."""
    daemon.request("ensure", {"profile": "anything"})
    daemon.request("history", {"n": NOT_AN_INT})

    body = daemon.log_text()
    # the two things the wire stopped carrying, still available locally
    assert str(unreadable_config) in body
    assert NOT_AN_INT in body
    # ...plus the frame chain the wire never carried at all
    assert body.count("Traceback (most recent call last):") == 2
    assert "in _load_profile" in body
    assert "IsADirectoryError" in body and "ValueError" in body
    # the routing key, which is the daemon's own verb literal, not caller text
    assert "verb='ensure'" in body and "verb='history'" in body


def test_the_local_log_does_not_render_the_request_args(daemon):
    """The precise boundary, not a vague "we're careful": the value the
    exception message itself reprs DOES land in the log (that is `str(e)`,
    which is the diagnostic), but its siblings in the same `args` dict do not
    -- and `args` is structurally where a `--secret` payload lives."""
    resp, raw = daemon.request("history", {"n": NOT_AN_INT, "password": SECRET_SHAPED})

    assert resp["error"] == "internal_error:ValueError"
    assert SECRET_SHAPED not in raw

    body = daemon.log_text()
    assert NOT_AN_INT in body, "the raising value is the diagnostic -- it must be kept"
    assert SECRET_SHAPED not in body, "a sibling arg is not diagnostic and must not be logged"


def test_the_local_log_is_owner_only_even_over_a_pre_existing_loose_file(tmp_path):
    """A log that can carry caller-supplied bytes never gets the umask
    default -- same discipline `logging_util.TranscriptLogger` and
    `protocol._save_password` already apply, re-asserted rather than trusted
    from creation."""
    from tw2002_aiclient.session.daemon import ERRLOG_NAME, _open_error_log

    path = tmp_path / ERRLOG_NAME
    path.write_text("pre-existing\n", encoding="utf-8")
    os.chmod(path, 0o644)
    assert path.stat().st_mode & 0o777 == 0o644  # genuinely loose before

    fh = _open_error_log(tmp_path)
    try:
        assert path.stat().st_mode & 0o777 == 0o600
    finally:
        fh.close()


def test_a_daemon_without_a_run_dir_sink_still_records_the_traceback(run_dir, capfd):
    """A bare harness builds the server by hand and has no run-dir. The catch
    must not go silent there -- it falls back to stderr, which is that
    context's log."""
    d = _Daemon(run_dir, with_error_log=False)
    try:
        resp, raw = d.request("history", {"n": NOT_AN_INT})
    finally:
        d.stop()

    assert resp["error"] == "internal_error:ValueError"
    assert NOT_AN_INT not in raw

    err = capfd.readouterr().err
    assert "Traceback (most recent call last):" in err
    assert NOT_AN_INT in err
    assert d.log_text() == "", "no run-dir sink was configured, so none should appear"
