"""MT-07 — can a credential reach the `ensure` / login JSON **error surface**?

`workorders/AUDIT-MISSING-TESTS.md` row MT-07: live login tests never assert
the sentinel is absent from the `ensure` error dict that `protocol.py` builds
and `cli.py` prints. Spectators and status consumers read that JSON; a
transcript-only proof does not cover it.

**Answer, measured rather than reasoned: YES, on an echoing server.** Two
independent carriers were driven end-to-end through the REAL `cli.ensure_raw`
against a REAL daemon socket, and both put the typed credential into the JSON
an operator sees:

1. **the error text** — `login.py` raised
   ``f"automaton_stuck:classification={cls!r}:prompt={prompt!r}"``, quoting the
   observed prompt line verbatim, and `protocol._dispatch_ensure` folds it into
   ``resp["error"] = f"login_failed:{e}"``. When the server echoed the
   credential onto the current prompt line, that line WAS the credential.
   **CLOSED (WO-MT-07-FIX):** both stalled-automaton raise sites now raise
   `login.LoginStalled`, which carries the closed-vocabulary classification and
   the loop counter and is structurally incapable of carrying screen text — the
   same fix-at-the-source discipline `credentials.SecretStoreUnreadable` and
   `env.DotenvUnreadable` already use, so every renderer (`str`, `repr`, the
   traceback, the wire frame, `guardian.last_reconnect_error`) is safe by
   construction rather than individually sanitised. Gated below by
   `test_the_stuck_error_text_no_longer_copies_the_echoed_prompt`.
2. **the screen mirror** — `_dispatch_ensure`'s `LoginError` branch answers with
   a full `build_response()`, whose ``screen`` field is the whole rendered
   buffer. An echoing server leaves the credential in that buffer, so it rides
   the response even on the rejection path, where the error text is provably
   clean. **STILL OPEN, deliberately.** The screen mirror carries the credential
   because the SERVER ECHOED IT and this app is a screen mirror; whether a
   mirror may show what the server painted is a product ruling, not a mechanical
   fix. If it is ruled by-design, its `xfail` below must be DELETED, not
   flipped.

Carrier 2 is pinned as `xfail(strict=True)` so the day it is closed the test
fails loudly and asks to be flipped, instead of passing forever. Carrier 1's
former pins are now green gates: closure is measured, not assumed, and it is
measured by the SINK SET rather than by one string — the human branch of
`cli.print_response` prints only ``error`` + ``detail`` for ``ok: False``, so
that sink is the error text's own fingerprint among the four, and it is the one
that went clean.

**What is already covered elsewhere, and is not re-proven here.**
`tests/test_login_redaction.py` sweeps the login path's four sinks (return
value, exception renderings, transcript, on-disk) across nine failure
scenarios, and takes the store failures and the rejection to a real AF_UNIX
socket frame. It also records the echoing-server leak — but only against
``str(LoginError)``, never through `_dispatch_ensure`, `ensure_raw`, or
`cli.print_response`. Those three layers are this file's whole subject: the
question here is not "does the automaton's exception carry it" (answered
there) but "does it reach the JSON a client is handed" (answered here).

**Non-vacuity.** An absence assertion is worthless if the sweep cannot find
anything. The sweep helper here (`_carriers` / `_assert_absent`, over the
sinks `_drive_ensure` collects) is the SAME one in every test in this file,
with the same needle — and it demonstrably fires, on
this exact surface, in the two `xfail` tests below. That is a stronger bookend
than an injected defect would be: the green tests and the leaking tests differ
only in the server's echo behavior, not in the instrument. The harness itself
is guarded by the green control test: if the scripted server, the daemon, or
the session wiring broke, the control goes RED rather than quietly turning
every sweep into a no-op.

**Sinks swept.** The `ensure_raw` dict is serialised with `json.dumps` rather
than key-checked, because a nested carrier (`screen` is a list of rows,
`detail` is a sibling string) passes a shallow check and still crosses the
wire. Both `cli.print_response` renderings are captured too — `--json`
(`json.dumps(resp)`) and the human-readable branch, which for `ok: False`
prints only `error` + `detail` and is therefore a strictly narrower surface
than the JSON one. The daemon's owner-only local error log is swept alongside,
so a leak cannot be "fixed" on the wire by relocating it into a file.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import socket
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from tw2002_aiclient.session import cli, credentials, env, login
from tw2002_aiclient.session.session import Session

# The credential under test. Deliberately does NOT contain the substring
# "password": `classify.py`'s `login_password` gate anchor is exactly
# `re.compile(r"password", re.I)` against the current prompt line, so a
# sentinel containing it would change the automaton's own classification the
# moment a server echoed it back -- which is the scenario under test.
# Distinct from `tests/test_login_redaction.py`'s sentinel on purpose: a hit
# in this file's sinks is then always this file's own credential.
SENTINEL = "S3NT1NEL-MT07-ENSURE-4a17c9"
# A sibling profile inside the SAME secrets.json -- key and stored value. The
# store-failure scenarios never send a password at all, so these are what make
# those sweeps non-vacuous: they are provably inside the document the decoder
# just choked on, and a message that quoted the document would quote one.
CANARY_KEY = "canary-sibling-mt07-7b3e02"
CANARY_VALUE = "canary-sibling-pw-9f4a15"
NEEDLES = (SENTINEL, CANARY_KEY, CANARY_VALUE)

PROFILE = "mt07"
HANDLE = "AEGIS"
GAME_LETTER = "F"

# A real TWGS door clears and redraws between major screens. Without it pyte
# accumulates every screen forever and stale scrollback re-matches the
# automaton's nuisance regexes (both failure shapes are documented at
# `tests/fake_twgs.py`'s own `_send`). Applied per scripted step here rather
# than automatically, because one scenario below MUST leave the previous
# screen in place -- that is what an inline echo looks like.
CLEAR = "\x1b[2J\x1b[H"
PASSWORD_SCREEN = CLEAR + "Password?"


# ---------------------------------------------------------------------------
# a scripted server that starts AT the password gate
# ---------------------------------------------------------------------------


class _ScriptedTWGS:
    """A minimal single-connection scripted telnet server, local to this file.

    Deliberately local rather than shared, matching the convention
    `tests/test_login_redaction.py`'s `_BareServer` states outright: small
    harness doubles are duplicated per module instead of coupling test files to
    each other's privates. It differs from that file's same-named class in the
    one way this file needs -- steps send their bytes VERBATIM, with no implied
    screen clear, because an inline echo is defined by the previous screen
    still being there.

    Every scenario begins at the password gate. `tests/fake_twgs.py` scripts
    the whole 6-screen cold-start arc and `tests/test_login.py` already proves
    the automaton against it; the prefix costs seconds per test and exercises
    nothing here. Starting mid-flow is legitimate rather than a shortcut:
    `run_login` re-classifies the CURRENT screen every iteration, which is what
    `tests/test_login_resume.py` proves.

    A step is `(send, read)`. `send` is the exact bytes-as-text to write, or a
    callable handed the last line read (that is how a step echoes). `read` says
    whether to consume one CRLF-terminated reply before moving on.
    """

    def __init__(self, script, host: str = "127.0.0.1"):
        self._script = list(script)
        self.host = host
        self.received: list[str] = []
        self.errors: list[str] = []
        self._listener: socket.socket | None = None
        self._port: int | None = None
        self._conn: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    @property
    def port(self) -> int:
        if self._port is None:
            raise RuntimeError("_ScriptedTWGS not started")
        return self._port

    def __enter__(self) -> "_ScriptedTWGS":
        self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._listener.bind((self.host, 0))
        self._listener.listen(1)
        self._port = self._listener.getsockname()[1]
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc_info):
        self._stop.set()
        for sock in (self._listener, self._conn):
            if sock is None:
                continue
            with contextlib.suppress(OSError):
                sock.shutdown(socket.SHUT_RDWR)
            with contextlib.suppress(OSError):
                sock.close()
        if self._thread is not None:
            self._thread.join(timeout=5.0)

    def _serve(self):
        try:
            conn, _addr = self._listener.accept()
        except OSError:
            return  # listener closed under us (teardown)
        self._conn = conn
        buf = bytearray()
        last = ""
        try:
            for send, read in self._script:
                text = send(last) if callable(send) else send
                if text is not None:
                    conn.sendall(text.encode("cp437", errors="replace"))
                if not read:
                    continue
                while b"\r\n" not in buf:
                    chunk = conn.recv(4096)
                    if not chunk:
                        raise ConnectionError("peer closed")
                    buf.extend(chunk)
                line, _, rest = bytes(buf).partition(b"\r\n")
                buf = bytearray(rest)
                last = line.decode("cp437", errors="replace")
                self.received.append(last)
            while not self._stop.is_set():  # hold the connection open and quiet
                if not conn.recv(4096):
                    return
        except (ConnectionError, OSError):
            return
        except Exception as e:  # noqa: BLE001 -- a script bug must surface, never vanish
            self.errors.append(f"{type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# a real daemon on the socket path `cli.ensure_raw` actually looks at
# ---------------------------------------------------------------------------


class _Daemon:
    """A real `ThreadingUnixServer` + `CommandHandler` + run-dir error log,
    wired to a REAL telnet `Session`.

    Two things are deliberate. The socket is bound at `env.socket_path(run_dir)`
    -- not an arbitrary name -- and a pidfile carrying THIS process's pid is
    written at `env.pid_path(run_dir)`, because that pair is exactly what
    `cli.ensure_raw`'s `daemon_alive(run_dir) and sock_path.exists()` gate
    checks. Satisfying it is what lets the real `ensure_raw` be the code under
    test instead of a hand-rolled round trip, and what stops it forking a real
    daemon subprocess at our scripted server (asserted, not assumed -- see
    `_assert_no_daemon_was_spawned`).

    The handler's widest catch lives one layer above `dispatch()`, and it is
    the thing that answers the store-failure scenarios at all, so calling
    `dispatch()` directly could not prove what a client receives.
    """

    def __init__(self, run_dir: Path, session):
        from tw2002_aiclient.session.control_lock import ControlLock
        from tw2002_aiclient.session.daemon import (
            CommandHandler,
            ThreadingUnixServer,
            _open_error_log,
        )

        self.run_dir = Path(run_dir)
        self.sock_path = str(env.socket_path(self.run_dir))
        self.server = ThreadingUnixServer(self.sock_path, CommandHandler)
        self.server.session = session
        self.server.control_lock = ControlLock()
        self.server.watch_hub = None
        self.server.request_stop = lambda: None
        self.error_log = _open_error_log(self.run_dir)
        self.server.error_log = self.error_log
        env.pid_path(self.run_dir).write_text(str(os.getpid()), encoding="utf-8")
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self._thread.start()

    def log_text(self) -> str:
        from tw2002_aiclient.session.daemon import ERRLOG_NAME

        path = self.run_dir / ERRLOG_NAME
        return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self._thread.join(timeout=5)
        self.error_log.close()


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


def _good_secrets_text() -> str:
    """A well-formed store holding the sentinel plus the canary sibling."""
    return json.dumps(
        {PROFILE: {"password": SENTINEL}, CANARY_KEY: {"password": CANARY_VALUE}},
        indent=2,
    )


def _write_secrets(cfg: Path, *, text: str | None = None, raw: bytes | None = None) -> Path:
    """Write a real `secrets.json` at mode 0600 (doctrine: the secrets file is
    created and re-asserted 0600 on every write) and return its path."""
    path = cfg / "secrets.json"
    path.write_bytes(raw if raw is not None else (text or "").encode("utf-8"))
    os.chmod(path, 0o600)
    return path


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    """A real config dir with `credentials`' module-level paths pointed at it.

    Those globals are resolved at import time, so `TW_CONFIG_DIR` alone would
    not move them in an already-imported process -- the same reason
    `tests/test_daemon_internal_error_typename.py` and
    `tests/test_login_redaction.py` both monkeypatch the resolved paths
    directly. `protocol._save_password` reads `credentials.SECRETS_PATH` at
    call time too, so the write side follows this fixture as well.
    """
    d = tmp_path / "config"
    d.mkdir()
    monkeypatch.setattr(credentials, "CONFIG_DIR", d)
    monkeypatch.setattr(credentials, "SECRETS_PATH", d / "secrets.json")
    monkeypatch.setattr(credentials, "PROFILES_PATH", d / "profiles.toml")
    monkeypatch.setattr(credentials, "SERVERS_PATH", d / "servers.toml")
    return d


@pytest.fixture
def run_dir():
    """A SHORT run-dir: pytest's `tmp_path` is long enough to blow AF_UNIX's
    ~104-byte address limit, which is why `tests/conftest.py`'s fake daemon and
    both sibling wire suites use `mkdtemp` as well."""
    d = tempfile.mkdtemp(prefix="twd-mt07-")
    try:
        yield Path(d)
    finally:
        shutil.rmtree(d, ignore_errors=True)


@pytest.fixture(autouse=True)
def _fast_stagnation(monkeypatch):
    """Shorten the automaton's stagnation waits.

    A silent server means each stagnation round waits out the FULL settle
    budget (12s x 3 rounds) before `automaton_stuck` can fire. These are timing
    budgets, not the behavior under test -- every scenario here reaches the
    same decision, sooner. Same knob `tests/test_login_redaction.py` turns for
    the same reason.
    """
    monkeypatch.setattr(login, "_STEP_SETTLE_TIMEOUT_S", 1.0)
    monkeypatch.setattr(login, "_RETURNING_REJECT_SETTLE_S", 0.3)


# ---------------------------------------------------------------------------
# the surface under test
# ---------------------------------------------------------------------------


def _write_profile(cfg: Path, port: int):
    (cfg / "profiles.toml").write_text(
        f'[{PROFILE}]\nhost = "127.0.0.1"\nport = {port}\n'
        f'game_letter = "{GAME_LETTER}"\nhandle = "{HANDLE}"\n',
        encoding="utf-8",
    )


def _assert_no_daemon_was_spawned(run_dir: Path):
    """`ensure_raw` only forks when its `daemon_alive() and sock_path.exists()`
    gate fails, and the first thing that fork does is open
    `run/twd.stderr.log`. Its ABSENCE is the proof that the response came from
    the daemon this test wired up, and not from a real one that raced us onto
    the scripted server."""
    assert not (run_dir / "twd.stderr.log").exists(), (
        "ensure_raw forked a real daemon -- the pidfile/socket gate did not hold, "
        "so this test measured something other than the wired-up daemon"
    )


def _render(resp: dict) -> dict[str, str]:
    """Every rendering of the response a client can end up holding.

    `json.dumps` rather than a per-key check: `screen` is a list of rows and
    `detail` is a sibling string, so a nested carrier passes a shallow dict
    check and still crosses the wire. Both `cli.print_response` branches are
    captured because they are not the same surface -- for `ok: False` the
    human-readable one prints only `error` + `detail`, which is strictly
    narrower than the `--json` one.
    """
    import io
    from contextlib import redirect_stdout

    as_json = io.StringIO()
    with redirect_stdout(as_json):
        cli.print_response(resp, SimpleNamespace(json=True))
    as_text = io.StringIO()
    with redirect_stdout(as_text):
        cli.print_response(resp, SimpleNamespace(json=False, compact=False))
    return {
        "ensure_raw() returned dict": json.dumps(resp),
        "tw ensure --json stdout": as_json.getvalue(),
        "tw ensure stdout": as_text.getvalue(),
    }


def _drive_ensure(cfg: Path, run_dir: Path, logs: Path, script):
    """Run one scenario end to end and return `(resp, sinks, server)`.

    Real scripted telnet server -> real `Session` -> real daemon on the real
    socket path -> real `cli.ensure_raw` -> real `cli.print_response`. Nothing
    on that chain is a double.
    """
    with _ScriptedTWGS(script) as server:
        _write_profile(cfg, server.port)
        session = Session("127.0.0.1", server.port, PROFILE, str(logs))
        session.start(timeout=10)
        daemon = _Daemon(run_dir, session)
        try:
            resp = cli.ensure_raw(PROFILE, timeout=60.0, run_dir=run_dir)
            log_body = daemon.log_text()
        finally:
            daemon.stop()
            session.close()

    _assert_no_daemon_was_spawned(run_dir)
    assert not server.errors, server.errors
    sinks = {**_render(resp), "daemon local error log": log_body}
    return resp, sinks, server


def _carriers(sinks: dict[str, str], needle: str) -> list[str]:
    """Which sinks carry `needle`. A list rather than a bool so a failure names
    the carrier instead of only asserting that one exists."""
    return sorted(name for name, body in sinks.items() if needle in body)


def _assert_absent(sinks: dict[str, str]):
    for needle in NEEDLES:
        hits = _carriers(sinks, needle)
        assert not hits, f"{needle!r} reached: {', '.join(hits)}"


# ---------------------------------------------------------------------------
# GREEN -- the surface is clean on every path that does not involve an echo
# ---------------------------------------------------------------------------


def test_a_rejected_credential_stays_off_the_ensure_surface(cfg, tmp_path, run_dir):
    """MT-07's `returning_password_rejected` case, taken all the way to the
    printed JSON.

    Against a server behaving as canon assumes -- a password prompt suppresses
    echo -- the credential is sent, rejected, and appears in NOTHING the client
    receives: not the `error` string, not the `screen` mirror, not the
    `sent_input` field, not either `print_response` rendering.

    This is also the harness's own control. Every absence assertion in this
    file is measured with the same instrument, and the two `xfail` tests below
    show that instrument firing; this test is what goes RED if the scripted
    server, the daemon wiring, or the session ever stops driving a real login
    at all, instead of every sweep silently becoming a no-op.
    """
    _write_secrets(cfg, text=_good_secrets_text())
    logs = tmp_path / "logs"
    script = [(PASSWORD_SCREEN, True), (PASSWORD_SCREEN, False)]

    resp, sinks, server = _drive_ensure(cfg, run_dir, logs, script)

    # Non-vacuity: the credential really was resolved from the real store and
    # really did go out on the wire. An absence proved on a login that never
    # happened would be worth nothing.
    assert server.received == [SENTINEL]
    assert resp["ok"] is False
    assert "login_failed:returning_password_rejected" in resp["error"]
    # The nested carrier MT-07 warns about, pinned positively: `build_response`
    # puts `session.last_sent` on EVERY response, and `Session.send` stores
    # "<redacted>" for a `secret=True` send. If that redaction ever regresses,
    # every ensure response starts carrying the credential -- this is where
    # that would surface.
    assert resp["sent_input"] == "<redacted>"
    _assert_absent(sinks)


@pytest.mark.parametrize("kind", ["malformed", "non_utf8", "unreadable"])
def test_a_broken_credential_store_stays_off_the_ensure_surface(
    cfg, tmp_path, run_dir, kind
):
    """MT-07's malformed / unreadable-secrets cases, taken to the printed JSON.

    `credentials.get_password` raises from inside `run_login`, and what escapes
    is not a `LoginError` -- so `_dispatch_ensure` does not catch it and it
    lands in `daemon.py`'s widest catch, which answers with a bare type name.
    The document those exceptions carry (`JSONDecodeError.doc`,
    `UnicodeDecodeError.object` -- both hold the ENTIRE failed store) therefore
    never reaches a rendering, and neither does the operator's filesystem
    layout on the unreadable path.

    The `error` payload is asserted to be a bare Python identifier rather than
    a literal string: that is the actual invariant, and it cannot be satisfied
    by a message that happens not to contain this run's needles.
    """
    if kind == "unreadable" and hasattr(os, "geteuid") and os.geteuid() == 0:
        pytest.skip("root bypasses the 0000 mode")

    if kind == "malformed":
        # Valid-looking JSON truncated mid-object: `json.load` raises
        # `JSONDecodeError`, whose `.doc` is the whole document.
        store = _write_secrets(cfg, text=_good_secrets_text().rstrip()[:-2])
    elif kind == "non_utf8":
        # `get_password` opens with `encoding="utf-8"`, so a lone 0xFF fails
        # during the READ -- a `UnicodeDecodeError`, whose `.object` is the
        # whole file, and which is neither an `OSError` nor a `JSONDecodeError`.
        store = _write_secrets(cfg, raw=_good_secrets_text().encode("utf-8") + b"\xff")
    else:
        store = _write_secrets(cfg, text=_good_secrets_text())
        os.chmod(store, 0o000)

    logs = tmp_path / "logs"
    try:
        resp, sinks, _server = _drive_ensure(cfg, run_dir, logs, [(PASSWORD_SCREEN, False)])
    finally:
        os.chmod(store, 0o600)

    assert resp["ok"] is False
    prefix, _, payload = resp["error"].partition(":")
    assert prefix == "internal_error"
    assert payload.isidentifier(), f"a message rode the wire, not a type name: {payload!r}"
    _assert_absent(sinks)

    # Non-vacuity: the store really did hold every needle the sweep looked for,
    # so "absent" means "kept out", not "was never there". Bytes, not text --
    # one of these three stores is deliberately not valid UTF-8.
    planted = store.read_bytes()
    assert all(needle.encode("utf-8") in planted for needle in NEEDLES)


# ---------------------------------------------------------------------------
# CARRIER 1 -- CLOSED (WO-MT-07-FIX)
# ---------------------------------------------------------------------------


def test_the_stuck_error_text_no_longer_copies_the_echoed_prompt(cfg, tmp_path, run_dir):
    """CARRIER 1, closed and gated: the app no longer makes a COPY of the
    credential into a diagnostic string.

    Same scenario as the `xfail` immediately below -- the server echoes the
    credential and stalls, so the stagnation ceiling fires -- but scoped to the
    carrier this WO owns. `login.LoginStalled` carries `classification` (a
    closed vocabulary: `classify_screen` answers `unknown` for anything it
    cannot name, never a slice of the screen) and `step`, and has no field the
    prompt could ride in.

    **The assertion that proves it is the SINK SET, not a string.** For
    ``ok: False`` `cli.print_response`'s human branch prints only ``error`` and
    ``detail``, so ``tw ensure stdout`` is the error text's own fingerprint
    among the four sinks. Measured on this exact scenario:

        before  ensure_raw() returned dict, tw ensure --json stdout, tw ensure stdout
        after   ensure_raw() returned dict, tw ensure --json stdout

    The dropped sink is carrier 1. The two that remain are carrier 2 -- the
    `screen`/`prompt` mirror `build_response()` attaches to the failure answer,
    which is out of this WO's scope and awaiting a product ruling. Asserting
    the set EXACTLY, rather than only the absence, makes this one test fail in
    both directions: if the error text ever quotes the prompt again the human
    sink comes back, and if the screen mirror is ever changed underneath this
    WO the remaining pair shrinks. That second half is the "carrier 2 unchanged"
    proof, measured rather than promised.

    **Diagnosability survives, and this asserts it positively.** An absence
    test that passed because the automaton stopped reporting anything would be
    a regression wearing a green tick, so the error is required to still name
    the failure mode AND the classification.
    """
    _write_secrets(cfg, text=_good_secrets_text())
    logs = tmp_path / "logs"
    script = [(PASSWORD_SCREEN, True), (lambda last: CLEAR + last, False)]

    resp, sinks, server = _drive_ensure(cfg, run_dir, logs, script)

    # Non-vacuity: the credential really was resolved from the real store, sent
    # on the wire, and echoed back onto the screen -- an absence proved against
    # a screen that never held it would be worth nothing.
    assert server.received == [SENTINEL]
    assert any(SENTINEL in "".join(row) for row in resp["screen"]), (
        "the server did not echo -- this scenario stopped being the one under test"
    )

    # Still diagnosable: WHICH failure, and WHERE the automaton was.
    assert resp["error"].startswith("login_failed:automaton_stuck:")
    assert "classification='unknown'" in resp["error"]

    # Carrier 1: gone from the error text, and therefore from the one sink
    # built out of nothing else.
    assert SENTINEL not in resp["error"]
    assert SENTINEL not in sinks["tw ensure stdout"]

    # Carrier 1 closed AND carrier 2 untouched, in one measurement.
    assert _carriers(sinks, SENTINEL) == [
        "ensure_raw() returned dict",
        "tw ensure --json stdout",
    ]
    # The sibling profile never crosses on any path, carrier or not.
    assert _carriers(sinks, CANARY_KEY) == []
    assert _carriers(sinks, CANARY_VALUE) == []


def test_no_raise_site_in_login_quotes_what_the_server_painted(cfg):
    """Structural pin on the SHAPE of the fix, not on one message.

    The behavioral gate above covers the two raise sites that exist today. This
    covers the next one someone adds: every `raise` in `login.py` is walked and
    refused if its expression reads `prompt`, `text` or `rows` -- the three
    names in `run_login`/`_decide` that hold what the server painted. That is
    the whole defect class MT-07 found ("the app makes a new copy of the
    credential into a diagnostic string"), and a new raise site is exactly where
    it would come back, with no test exercising it.

    **Known limit, stated rather than implied:** this reads names, so
    `p = prompt; raise LoginError(f"{p}")` slips through. It is a tripwire on
    the obvious regression, not a proof of absence -- the proof is the sweep
    above. `cfg` is unused; it is requested only to keep this file's
    credentials-path isolation in force for every test in it.
    """
    import ast
    import inspect

    from tw2002_aiclient.session import login as login_module

    forbidden = {"prompt", "text", "rows"}
    tree = ast.parse(inspect.getsource(login_module))
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Raise) or node.exc is None:
            continue
        named = {n.id for n in ast.walk(node.exc) if isinstance(n, ast.Name)}
        hit = named & forbidden
        if hit:
            offenders.append((node.lineno, sorted(hit)))

    assert not offenders, (
        "login.py raise site(s) interpolate server-painted text: "
        f"{offenders}. On an echoing server that text is the operator's "
        "credential -- see login.LoginStalled for why it must stay out."
    )


# ---------------------------------------------------------------------------
# THE FINDING -- an echoing server, the screen mirror (carrier 2)
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason=(
        "MEASURED LEAK, pending a human ruling -- CARRIER 2 ONLY, since "
        "WO-MT-07-FIX. The error-text carrier is CLOSED and the two assertions "
        "above _assert_absent now PASS (login.LoginStalled cannot carry the "
        "prompt), so what still fails this whole-sink sweep is resp['prompt'] "
        "and resp['screen'] -- the mirror build_response() attaches to the "
        "failure answer. Same carrier as the test below, reached down a "
        "different path (stall rather than rejection), which is why closing it "
        "must flip BOTH or neither. If the mirror is ruled by-design, DELETE "
        "this xfail; do not flip it. strict=True so it fails loudly either way."
    ),
)
def test_an_echoing_server_puts_the_credential_on_the_ensure_surface(
    cfg, tmp_path, run_dir
):
    """The echoing-server case MT-07 names, driven to the operator's JSON.

    Canon (`doctrine/secrets-and-credentials.md`, Code Divergence #1) states the
    RX-side guarantee honestly: redaction is structural on TX only, and the
    receive channel is transcribed verbatim, so the no-leak property rests on
    the telnet convention that a password prompt suppresses echo. A server that
    does echo puts the typed credential on the current prompt line; the screen
    then classifies `unknown` and the stagnation ceiling fires.

    **What this test measures CHANGED under WO-MT-07-FIX, and the change is
    the point.** It was originally red on both carriers at once: the raised
    `automaton_stuck` quoted the prompt line verbatim AND the response mirrored
    the screen. The first is now closed at the source, so the two assertions
    before the sweep PASS and the sweep fails on the mirror alone -- the same
    isolation-by-construction the rejection-path test below uses, arrived at
    from the other direction. It stays `xfail(strict=True)` rather than being
    flipped, because the carrier it now reports is carrier 2, whose ruling is
    not this WO's to pre-empt; `test_the_stuck_error_text_no_longer_copies_the_
    echoed_prompt` above is the green gate for the half that WAS closed.

    Keeping this whole-sink sweep on the stall path (rather than re-scoping it
    to the error text and calling it green) is deliberate: the mirror leaks
    down BOTH paths, and a pin that only covered the rejection path would go
    quiet about this one.
    """
    _write_secrets(cfg, text=_good_secrets_text())
    logs = tmp_path / "logs"
    # Step 2 redraws with exactly what the client sent, and nothing else -- the
    # one server behavior canon's RX guarantee assumes will never happen.
    script = [(PASSWORD_SCREEN, True), (lambda last: CLEAR + last, False)]

    resp, sinks, server = _drive_ensure(cfg, run_dir, logs, script)

    assert server.received == [SENTINEL]
    assert "login_failed:automaton_stuck" in resp["error"]
    # CARRIER 1, CLOSED -- both of these PASS, and they are what isolates the
    # screen mirror as the sole remaining carrier on this path. The human
    # branch of print_response prints only error + detail for ok:False, so a
    # clean `tw ensure stdout` IS a clean error text.
    assert SENTINEL not in resp["error"]
    assert SENTINEL not in sinks["tw ensure stdout"]
    _assert_absent(sinks)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "MEASURED LEAK, pending a human ruling -- SECOND, independent carrier. "
        "On the rejection path the error text is provably clean, and the "
        "credential still reaches the client inside resp['screen'], the full "
        "rendered buffer build_response() attaches to _dispatch_ensure's "
        "failure answer. Redacting login.py's error text alone would NOT close "
        "this; whether a screen mirror may show what the server painted is a "
        "product ruling, not a mechanical fix. strict=True so it flips loudly."
    ),
)
def test_an_echoing_server_leaks_through_the_screen_mirror_alone(
    cfg, tmp_path, run_dir
):
    """The screen-mirror carrier, isolated by construction rather than by
    assertion order.

    This scenario is an ordinary rejection: telnet ECHO is on, so the typed
    credential is appended to the line the `Password?` prompt sits on, then the
    server answers `Invalid password.` and re-presents the gate WITHOUT
    clearing. The current prompt line is therefore a clean `Password?`, the
    screen still classifies `login_password`, and `run_login` raises the
    specific `returning_password_rejected` -- whose text carries only the
    profile name.

    So the first assertion below PASSES: the error string is clean. The only
    thing left holding the credential is `resp["screen"]`, the whole rendered
    buffer `build_response()` attaches to every failure answer. That is what
    makes this a separate finding from the error-text leak rather than a second
    view of it, and why closing that one would leave this one open.

    Note which rendering suffers: `--json` carries the screen, while the
    human-readable branch of `print_response` prints only `error` + `detail`
    for `ok: False` and stays clean. The leak is on the machine-readable
    surface -- the one spectators and status consumers actually parse.
    """
    _write_secrets(cfg, text=_good_secrets_text())
    logs = tmp_path / "logs"
    script = [
        (PASSWORD_SCREEN, True),
        (lambda last: f"{last}\r\nInvalid password.\r\nPassword?", False),
    ]

    resp, sinks, server = _drive_ensure(cfg, run_dir, logs, script)

    assert server.received == [SENTINEL]
    # The error text really is clean on this path -- this is the assertion that
    # isolates the screen mirror as the sole remaining carrier.
    assert "login_failed:returning_password_rejected" in resp["error"]
    assert SENTINEL not in resp["error"]
    _assert_absent(sinks)
