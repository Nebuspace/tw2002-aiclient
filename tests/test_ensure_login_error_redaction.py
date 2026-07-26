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
2. **the screen mirror** — `_dispatch_ensure`'s `LoginError` branch answered
   with a full `build_response()`, whose ``screen`` field is the whole rendered
   buffer and whose ``prompt`` is its last row. An echoing server leaves the
   credential in that buffer, so it rode the response even on the rejection
   path, where the error text is provably clean.
   **CLOSED (WO-MT-07-CARRIER-2).** Ruled by canon `DECISIONS.md` §C.2
   (2026-07-26): structured ensure diagnostics — screen mirror in error
   payloads, CLI JSON, logs, persisted reason strings — must not carry
   server-echoed credentials, while the live TUI paint of the telnet stream
   may still show what the server painted. So the failure branch now answers
   with `protocol._login_failure_response`, which never builds a mirror:
   ``screen``, ``prompt`` and ``color`` are gone, ``classification`` (closed
   vocabulary) and ``sent_input`` (already `"<redacted>"`) stay, and an
   explicit ``screen_withheld`` marker makes the omission honest rather than
   silently missing. Both fields mattered: on the STALL path the echoed
   credential IS the prompt line, so closing ``screen`` alone would have moved
   the leak one field left rather than closing it.

Both carriers' `xfail(strict=True)` pins have been FLIPPED to green gates
(flipped, not deleted — §C.2 ruled fix, and deletion was the branch reserved
for a by-design ruling). Closure is measured, not assumed, and it is measured
by the SINK SET rather than by one string — the human branch of
`cli.print_response` prints only ``error`` + ``detail`` for ``ok: False``, so
that sink is the error text's own fingerprint among the four. Carrier 1 dropped
it; carrier 2 dropped the remaining two, and the set is now empty.

**The other half of the ruling is pinned too.** §C.2 permits the live paint,
and over-applying the redaction into the cockpit/attach path would damage the
product's core purpose, so
`test_the_live_paint_path_still_shows_what_the_server_painted` asserts that
after the same failed ensure the session's pyte buffer AND the shared
`protocol.build_response()` still carry what the server painted. It is the one
test here whose PASSING condition is finding the sentinel.

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
with the same needle. Now that both carriers are closed, nothing in the file
leaks on its own any more, so the bookend is explicit:
`test_restoring_the_mirror_puts_the_credential_back_on_the_surface`
monkeypatches the PRE-FIX failure answer back in — changing nothing else, not
the server, not the scenario, not the instrument — and measures the credential
returning to exactly the two sinks the historical measurement named. Every
scenario also proves the server really echoed, against `_Run.painted` (the
daemon's own buffer) rather than against a response field, so "absent" always
means "kept out", never "was never there". The harness itself is guarded by
the green control test: if the scripted server, the daemon, or the session
wiring broke, the control goes RED rather than quietly turning every sweep
into a no-op.

**Sinks swept.** The `ensure_raw` dict is serialised with `json.dumps` rather
than key-checked, because a nested carrier passes a shallow check and still
crosses the wire — that is precisely how carrier 2 was found (`screen` was a
list of rows; `detail` is a sibling string). The serialisation sweep stays the
instrument even though the failure answer is flat today, since the next field
added to it will not be. Both `cli.print_response` renderings are captured too — `--json`
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
from typing import NamedTuple

import pytest

from tw2002_aiclient.session import cli, credentials, env, login, protocol
from tw2002_aiclient.session.protocol import build_response
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


class _Run(NamedTuple):
    """One scenario's measurements.

    `resp` / `sinks` / `server` are the surface under test and its instrument.
    `painted` and `live` are the OTHER side of the ruling and are deliberately
    NOT sinks -- see their fields below and `_assert_absent`'s own note.
    """

    resp: dict
    sinks: dict[str, str]
    server: "_ScriptedTWGS"
    # What the daemon's own pyte buffer held at the moment it answered -- i.e.
    # what the server actually painted. The credential being HERE is the
    # scenario working, not a leak: canon `DECISIONS.md` C.2 rules that a live
    # attach/cockpit may show what the server painted. It is what makes every
    # absence assertion in this file non-vacuous now that `resp` no longer
    # carries a screen to look in.
    painted: list[str]
    # `protocol.build_response(session)` taken against that same buffer -- the
    # exact call `screen`, `do`, `send`, `read` and the WatchHub seed /
    # settle-edge emit (the cockpit viewport's feed) make. Kept so the
    # PERMITTED half of C.2 is pinned by execution rather than by promise.
    live: dict


def _drive_ensure(cfg: Path, run_dir: Path, logs: Path, script) -> _Run:
    """Run one scenario end to end and return a `_Run`.

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
            # Both taken BEFORE teardown, against the same buffer the daemon
            # just answered from -- a snapshot read after `session.close()`
            # would prove nothing about the moment under test.
            painted = session.render()
            live = build_response(session)
        finally:
            daemon.stop()
            session.close()

    _assert_no_daemon_was_spawned(run_dir)
    assert not server.errors, server.errors
    sinks = {**_render(resp), "daemon local error log": log_body}
    return _Run(resp=resp, sinks=sinks, server=server, painted=painted, live=live)


def _carriers(sinks: dict[str, str], needle: str) -> list[str]:
    """Which sinks carry `needle`. A list rather than a bool so a failure names
    the carrier instead of only asserting that one exists."""
    return sorted(name for name, body in sinks.items() if needle in body)


def _assert_absent(sinks: dict[str, str]):
    """Sweep the sinks a copy can LEAVE the session through.

    `_Run.painted` and `_Run.live` are deliberately never passed here. They are
    the session's own buffer and the live-paint response built from it -- canon
    `DECISIONS.md` C.2 permits those to show what the server painted, and
    sweeping them would turn this file into an argument for sanitising the
    operator's own screen, which the ruling explicitly refuses.
    """
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
    receives: not the `error` string, not the `sent_input` field, not either
    `print_response` rendering. (Since WO-MT-07-CARRIER-2 there is no `screen`
    mirror on this answer at all -- `test_the_ensure_failure_answer_carries_
    only_bounded_fields` is what pins that structurally.)

    This is also the harness's own control. Every absence assertion in this
    file is measured with the same instrument, and
    `test_restoring_the_mirror_puts_the_credential_back_on_the_surface` shows
    that instrument firing; this test is what goes RED if the scripted server,
    the daemon wiring, or the session ever stops driving a real login at all,
    instead of every sweep silently becoming a no-op.
    """
    _write_secrets(cfg, text=_good_secrets_text())
    logs = tmp_path / "logs"
    script = [(PASSWORD_SCREEN, True), (PASSWORD_SCREEN, False)]

    run = _drive_ensure(cfg, run_dir, logs, script)
    resp, sinks, server = run.resp, run.sinks, run.server

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
        run = _drive_ensure(cfg, run_dir, logs, [(PASSWORD_SCREEN, False)])
    finally:
        os.chmod(store, 0o600)
    resp, sinks = run.resp, run.sinks

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

    Same scenario as the whole-sink sweep immediately below -- the server
    echoes the credential and stalls, so the stagnation ceiling fires -- but
    scoped to carrier 1. `login.LoginStalled` carries `classification` (a
    closed vocabulary: `classify_screen` answers `unknown` for anything it
    cannot name, never a slice of the screen) and `step`, and has no field the
    prompt could ride in.

    **The assertion that proves it is the SINK SET, not a string.** For
    ``ok: False`` `cli.print_response`'s human branch prints only ``error`` and
    ``detail``, so ``tw ensure stdout`` is the error text's own fingerprint
    among the four sinks. Measured on this exact scenario, across both WOs:

        WO-MT-07-FIX       before  returned dict, --json stdout, ensure stdout
                           after   returned dict, --json stdout
        WO-MT-07-CARRIER-2 after   (none)

    The sink dropped by the first fix is carrier 1. The pair that survived it
    was carrier 2 -- the `screen`/`prompt` mirror `build_response()` used to
    attach to the failure answer -- and `DECISIONS.md` C.2 has since ruled it
    out too, so the set is now empty. Asserting the set EXACTLY, rather than
    only the absence, is what makes this test fail in BOTH directions: if the
    error text ever quotes the prompt again, or the mirror ever comes back,
    the named sink reappears and this goes red pointing at which one.

    **Diagnosability survives, and this asserts it positively.** An absence
    test that passed because the automaton stopped reporting anything would be
    a regression wearing a green tick, so the error is required to still name
    the failure mode AND the classification.

    **Where the non-vacuity moved.** This used to prove the server echoed by
    looking in `resp["screen"]`. That field is gone, so the echo is now proved
    against `run.painted` -- the daemon's OWN pyte buffer at the moment it
    answered. That is a strictly better instrument for this file's question:
    it separates "the server painted the credential" (true, permitted, and
    what makes the sweep meaningful) from "a copy of it left the session"
    (false, and the whole point).
    """
    _write_secrets(cfg, text=_good_secrets_text())
    logs = tmp_path / "logs"
    script = [(PASSWORD_SCREEN, True), (lambda last: CLEAR + last, False)]

    run = _drive_ensure(cfg, run_dir, logs, script)
    resp, sinks, server = run.resp, run.sinks, run.server

    # Non-vacuity: the credential really was resolved from the real store, sent
    # on the wire, and echoed back onto the screen -- an absence proved against
    # a screen that never held it would be worth nothing.
    assert server.received == [SENTINEL]
    assert any(SENTINEL in row for row in run.painted), (
        "the server did not echo -- this scenario stopped being the one under test"
    )

    # Still diagnosable: WHICH failure, and WHERE the automaton was.
    assert resp["error"].startswith("login_failed:automaton_stuck:")
    assert "classification='unknown'" in resp["error"]

    # Carrier 1: gone from the error text, and therefore from the one sink
    # built out of nothing else.
    assert SENTINEL not in resp["error"]
    assert SENTINEL not in sinks["tw ensure stdout"]

    # Both carriers closed, in one measurement.
    assert _carriers(sinks, SENTINEL) == []
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
# CARRIER 2 -- CLOSED (WO-MT-07-CARRIER-2, canon DECISIONS.md C.2)
# ---------------------------------------------------------------------------


def test_an_echoing_server_no_longer_reaches_the_ensure_surface_on_the_stall_path(
    cfg, tmp_path, run_dir
):
    """The echoing-server case MT-07 names, driven to the operator's JSON.

    Canon (`doctrine/secrets-and-credentials.md`, Code Divergence #1) states the
    RX-side guarantee honestly: redaction is structural on TX only, and the
    receive channel is transcribed verbatim, so the no-leak property rests on
    the telnet convention that a password prompt suppresses echo. A server that
    does echo puts the typed credential on the current prompt line; the screen
    then classifies `unknown` and the stagnation ceiling fires.

    **This test has been red twice and is now green, and the history is the
    point.** Originally it failed on both carriers at once: the raised
    `automaton_stuck` quoted the prompt line verbatim AND the response mirrored
    the screen. WO-MT-07-FIX closed the first at the source (`LoginStalled`),
    leaving it `xfail(strict=True)` on the mirror alone. `DECISIONS.md` C.2
    then ruled the mirror out of structured ensure diagnostics, and
    WO-MT-07-CARRIER-2 closed it in `protocol._login_failure_response`. The
    `xfail` was flipped rather than deleted because the ruling was FIX, not
    by-design -- deletion was the branch reserved for the other answer.

    Keeping this whole-sink sweep on the stall path (rather than folding it
    into the rejection-path test) is deliberate: the mirror rode BOTH paths,
    and a pin that only covered one would go quiet about the other. The stall
    path is also the harsher of the two, because here the echoed credential is
    the CURRENT prompt line -- so it was `resp["prompt"]`, not only
    `resp["screen"]`, that carried it.
    """
    _write_secrets(cfg, text=_good_secrets_text())
    logs = tmp_path / "logs"
    # Step 2 redraws with exactly what the client sent, and nothing else -- the
    # one server behavior canon's RX guarantee assumes will never happen.
    script = [(PASSWORD_SCREEN, True), (lambda last: CLEAR + last, False)]

    run = _drive_ensure(cfg, run_dir, logs, script)
    resp, sinks, server = run.resp, run.sinks, run.server

    assert server.received == [SENTINEL]
    assert "login_failed:automaton_stuck" in resp["error"]
    # Non-vacuity: the echo really did land, and it landed on the CURRENT
    # prompt line -- the field that used to carry it.
    assert SENTINEL in run.painted[-1], (
        "the echo is not on the prompt line -- this scenario stopped being the "
        "one that isolates resp['prompt'] as a carrier"
    )
    # CARRIER 1, CLOSED. The human branch of print_response prints only
    # error + detail for ok:False, so a clean `tw ensure stdout` IS a clean
    # error text.
    assert SENTINEL not in resp["error"]
    assert SENTINEL not in sinks["tw ensure stdout"]
    # CARRIER 2, CLOSED -- and the sweep is whole-sink, so this covers both.
    _assert_absent(sinks)


def test_an_echoing_server_no_longer_leaks_through_the_screen_mirror_alone(
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

    So the first assertion below PASSES, and always did: the error string is
    clean. The only thing that ever held the credential here was
    `resp["screen"]`, the whole rendered buffer `build_response()` used to
    attach to every failure answer. That is what made this a separate finding
    from the error-text leak rather than a second view of it, and why
    WO-MT-07-FIX closed that one and left this one open.

    **CLOSED by WO-MT-07-CARRIER-2** (canon `DECISIONS.md` C.2): the failure
    branch answers with `protocol._login_failure_response`, which never builds
    a mirror at all. Note which rendering used to suffer: `--json` carried the
    screen, while the human-readable branch of `print_response` prints only
    `error` + `detail` for `ok: False` and was always clean. The leak was on
    the machine-readable surface -- the one spectators and status consumers
    actually parse -- which is exactly the surface C.2 rules on, and the
    opposite end from the live paint it leaves alone.

    The prompt line is a clean `Password?` on this path, so this test says
    nothing about `resp["prompt"]`; the stall-path test above is what covers
    that field.
    """
    _write_secrets(cfg, text=_good_secrets_text())
    logs = tmp_path / "logs"
    script = [
        (PASSWORD_SCREEN, True),
        (lambda last: f"{last}\r\nInvalid password.\r\nPassword?", False),
    ]

    run = _drive_ensure(cfg, run_dir, logs, script)
    resp, sinks, server = run.resp, run.sinks, run.server

    assert server.received == [SENTINEL]
    # Non-vacuity, and it is what makes this carrier's isolation structural:
    # the credential IS on the grid, and it is NOT on the prompt line.
    assert any(SENTINEL in row for row in run.painted), (
        "the server did not echo -- this scenario stopped being the one under test"
    )
    assert SENTINEL not in run.painted[-1], (
        "the echo landed on the prompt line -- this scenario no longer isolates "
        "the screen mirror from the prompt field"
    )
    # The error text really is clean on this path -- this is the assertion that
    # isolates the screen mirror as the sole carrier that ever existed here.
    assert "login_failed:returning_password_rejected" in resp["error"]
    assert SENTINEL not in resp["error"]
    _assert_absent(sinks)


# ---------------------------------------------------------------------------
# THE OTHER HALF OF THE RULING -- what C.2 deliberately does NOT redact
# ---------------------------------------------------------------------------


def test_the_live_paint_path_still_shows_what_the_server_painted(cfg, tmp_path, run_dir):
    """C.2's carve-out, executable: the fix redacts what LEAVES the session,
    never what the operator's own eyes see.

    `DECISIONS.md` C.2 rules on structured ensure diagnostics -- "screen mirror
    in error payloads, CLI JSON, logs, persisted reason strings" -- and in the
    same breath permits the live TUI paint of the telnet stream to show what
    the server painted, because that is the human looking at their own game.
    Over-applying the redaction into the cockpit/attach paint would damage the
    product's whole purpose, so the boundary is pinned by execution rather than
    by intention: after the SAME failed ensure whose response is now clean,

      * the session's own pyte buffer still holds the echoed credential
        (`run.painted`) -- nothing sanitised the terminal, and
      * `protocol.build_response(session)` still mirrors it (`run.live`) --
        that is the exact call `screen`, `do`, `send`, `read` and the WatchHub
        seed / settle-edge emit make, and the settle-edge emit is what feeds
        `watchfeed.py` -> `cockpit/viewport.py`'s `event["screen"]`, i.e. the
        live paint itself.

    So this test is the one place in the file where finding the sentinel is
    the PASSING condition. If a future change starts scrubbing the buffer or
    the shared `build_response`, this goes red first and names the ruling --
    which is the failure mode worth catching, because it would be invisible to
    every other test here (they all only get stricter when that happens).

    The scenario is the rejection path rather than the stall path so the echo
    sits in the body of the screen: that isolates the `screen` mirror, the
    field the live viewport actually paints.
    """
    _write_secrets(cfg, text=_good_secrets_text())
    logs = tmp_path / "logs"
    script = [
        (PASSWORD_SCREEN, True),
        (lambda last: f"{last}\r\nInvalid password.\r\nPassword?", False),
    ]

    run = _drive_ensure(cfg, run_dir, logs, script)

    # The ensure answer is clean (that is the rest of this file's subject) ...
    assert run.resp["ok"] is False
    _assert_absent(run.sinks)

    # ... and the live paint is UNCHANGED. Both halves in one measurement, so
    # neither can be "fixed" by breaking the other.
    assert any(SENTINEL in row for row in run.painted), (
        "the session's own screen no longer holds what the server painted -- "
        "DECISIONS.md C.2 permits the live paint to show it; redacting the "
        "buffer itself is the over-application the ruling forbids"
    )
    assert any(SENTINEL in row for row in run.live["screen"]), (
        "protocol.build_response() stopped mirroring the buffer -- that call "
        "feeds `screen`/`do`/`send`/`read` and the WatchHub emit behind the "
        "cockpit viewport, none of which C.2 rules on"
    )
    assert SENTINEL in json.dumps(run.live), (
        "the live-paint response no longer carries it in any field"
    )


# ---------------------------------------------------------------------------
# THE SHAPE OF THE FIX -- pinned by key set and by structure
# ---------------------------------------------------------------------------


def test_the_ensure_failure_answer_carries_only_bounded_fields(cfg, tmp_path, run_dir):
    """The failure answer's field set, asserted EXACTLY.

    The sweeps above are content assertions: they go red when a credential
    reaches a sink, which needs the day's scripted server to have echoed. This
    is the structural complement -- it goes red the moment an unbounded field
    is re-attached to the failure answer, echo or no echo, and it is therefore
    what protects the fix from a well-meaning "restore the diagnostic context"
    edit that happens to be tested against a polite server.

    The expected set is written out here rather than imported from
    `protocol.py`: a test that reads the module's own constant would follow any
    edit to it and pin nothing.

    Every field is bounded by construction, and that is the property under
    test, not the count:

      `ok` / `already_there`   booleans
      `error`                  `login.py`'s own vocabulary -- and since
                               WO-MT-07-FIX, `LoginStalled` is structurally
                               incapable of carrying screen text
      `classification`         `classify_screen`'s CLOSED vocabulary; `unknown`
                               for anything it cannot name, never a slice of
                               the screen
      `sent_input`             `"<redacted>"` for a secret send, app-originated
                               text otherwise -- never receive-buffer content
      `screen_withheld`        a closed literal saying WHY the mirror is absent

    `screen` is asserted absent by KEY rather than by value, and the key is
    omitted rather than set to a marker string on purpose: a caller doing
    `"\\n".join(resp["screen"])` must fail loudly, not silently join the
    characters of a `"<withheld>"` placeholder into plausible-looking text.
    """
    _write_secrets(cfg, text=_good_secrets_text())
    logs = tmp_path / "logs"
    script = [(PASSWORD_SCREEN, True), (PASSWORD_SCREEN, False)]

    run = _drive_ensure(cfg, run_dir, logs, script)
    resp = run.resp

    assert resp["ok"] is False
    assert set(resp) == {
        "ok",
        "error",
        "classification",
        "sent_input",
        "already_there",
        "screen_withheld",
    }
    assert "screen" not in resp
    assert "prompt" not in resp
    assert "color" not in resp
    assert resp["screen_withheld"] == "login_failure"
    assert resp["already_there"] is False
    # Diagnosability, positively: the operator still learns WHICH screen the
    # automaton gave up on. An empty/None classification would satisfy every
    # absence assertion in this file and be a regression.
    assert resp["classification"] == "login_password"


def test_the_failure_answer_is_built_without_reaching_for_the_mirror():
    """Structural tripwire on the SHAPE of the fix, in the same family as
    `test_no_raise_site_in_login_quotes_what_the_server_painted`.

    The behavioral pins above cover the code that exists today. This covers the
    edit that would undo it: `_dispatch_ensure`'s `LoginError` handler and
    `_login_failure_response` are walked and refused if either calls
    `build_response` (the exact regression -- that call IS carrier 2) or names
    a mirror field as a dict key / subscript assignment.

    Deliberately narrow: it does NOT forbid `build_response` in `protocol.py`
    at large, because every SUCCESS path and every other verb must keep calling
    it -- C.2 rules on the failure payload, not on the mirror.

    **Known limit, stated rather than implied:** this reads the AST of two
    named regions, so a leak routed through a helper defined elsewhere, or
    through an alias (`from .protocol import build_response as _br`), slips
    through. It is a tripwire on the obvious regression, not a proof of
    absence -- the proof is the whole-sink sweeps above.
    """
    import ast
    import inspect

    from tw2002_aiclient.session import protocol as protocol_module

    mirror_fields = {"screen", "prompt", "color"}
    tree = ast.parse(inspect.getsource(protocol_module))
    funcs = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}

    builder = funcs["_login_failure_response"]
    handlers = [
        h
        for h in ast.walk(funcs["_dispatch_ensure"])
        if isinstance(h, ast.ExceptHandler)
        and "LoginError" in ast.dump(h.type or ast.Constant(value=None))
    ]
    assert handlers, "no `except LoginError` in _dispatch_ensure -- this pin lost its subject"

    for region, label in [(builder, "_login_failure_response"), (handlers[0], "except LoginError")]:
        called = set()
        for n in ast.walk(region):
            if not isinstance(n, ast.Call):
                continue
            # Both spellings: the bare same-module call a regression would
            # actually use, and the qualified `protocol.build_response(...)`
            # form a refactor could arrive at.
            if isinstance(n.func, ast.Name):
                called.add(n.func.id)
            elif isinstance(n.func, ast.Attribute):
                called.add(n.func.attr)
        assert "build_response" not in called, (
            f"{label} calls build_response() -- that response mirrors the whole "
            "receive buffer, which on an echoing server IS the credential "
            "(canon DECISIONS.md C.2)"
        )

    keys = {
        k.value
        for d in ast.walk(builder)
        if isinstance(d, ast.Dict)
        for k in d.keys
        if isinstance(k, ast.Constant)
    }
    assert not (keys & mirror_fields), (
        f"_login_failure_response names mirror field(s) {sorted(keys & mirror_fields)} "
        "as response keys"
    )
    stored = {
        n.slice.value
        for n in ast.walk(builder)
        if isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant)
    }
    assert not (stored & mirror_fields), (
        f"_login_failure_response assigns mirror field(s) {sorted(stored & mirror_fields)} "
        "onto the response"
    )


# ---------------------------------------------------------------------------
# MANDATORY falsification -- put the mirror back, watch the sweep fire
# ---------------------------------------------------------------------------


def _leaky_login_failure_response(session, error_text):
    """`_dispatch_ensure`'s PRE-FIX failure answer, verbatim (protocol.py at
    297abc1, the commit this WO branched from):

        resp = build_response(session, extra={"already_there": False})
        resp["ok"] = False
        resp["error"] = f"login_failed:{e}"

    Patched in with `monkeypatch`, never edited on disk -- the same idiom
    `tests/test_login_redaction.py`'s `_leaky_log_tx` uses, and for the same
    reason: the fix stays applied on disk for the whole run, so nothing else
    (a concurrent xdist worker included) can observe a half-reverted tree.
    """
    resp = build_response(session, extra={"already_there": False})
    resp["ok"] = False
    resp["error"] = error_text
    return resp


def test_restoring_the_mirror_puts_the_credential_back_on_the_surface(
    cfg, tmp_path, run_dir, monkeypatch
):
    """The bookend every absence assertion in this file needs.

    A green sweep proves nothing unless the sweep can go red. Re-attach the
    pre-fix mirror to the failure answer -- changing nothing else, not the
    server, not the scenario, not the instrument -- and the credential is back
    on the operator's JSON, in exactly the two sinks the historical measurement
    named. That reproduces carrier 2 on demand instead of relying on a
    `git`-archaeology claim, and it is what makes
    `test_an_echoing_server_no_longer_leaks_through_the_screen_mirror_alone`
    (the same scenario, unpatched) a measurement rather than a hope.

    `_assert_absent` is exercised directly through `pytest.raises` rather than
    only checking `_carriers`: the helper is the thing every other test in this
    file trusts, so it is the thing this proves fires.
    """
    monkeypatch.setattr(protocol, "_login_failure_response", _leaky_login_failure_response)
    _write_secrets(cfg, text=_good_secrets_text())
    logs = tmp_path / "logs"
    script = [
        (PASSWORD_SCREEN, True),
        (lambda last: f"{last}\r\nInvalid password.\r\nPassword?", False),
    ]

    run = _drive_ensure(cfg, run_dir, logs, script)

    # The mirror is back, and with it the leak -- named sink by sink.
    assert "screen" in run.resp
    assert _carriers(run.sinks, SENTINEL) == [
        "ensure_raw() returned dict",
        "tw ensure --json stdout",
    ]
    with pytest.raises(AssertionError, match=SENTINEL):
        _assert_absent(run.sinks)
