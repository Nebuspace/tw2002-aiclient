"""The `status` verb's prompt field, measured on BOTH sides of canon
`DECISIONS.md` §C.2.

§C.2 draws the line at whether a mirror of the receive buffer LEAVES the
session: structured mirrors (CLI JSON, logs, persisted reasons, anything a
spectator parses) must not carry a server-echoed credential; the live TUI paint
of the telnet stream may show whatever the server painted, because that is the
human's own eyes on their own game.

`status` was named as sitting on both sides at once. **It does not, and this
file is the measurement that says so.** The live paint of the game reaches the
cockpit through `subscribe` -> `watchfeed.WatchFeed` -> `cockpit/viewport.py`'s
`event["screen"]`, and through the one-shot `screen`/`attach` verbs -- all of
them `protocol.build_response()`, all untouched. `status` has only structured
consumers: `tw status` (both print branches -- a status response has no
`screen` key, so `cli.print_response` falls through to `json.dumps` either
way), and any spectator holding the socket. No cockpit panel reads
`status["prompt"]`; `test_no_cockpit_panel_changes_when_the_prompt_field_
disappears` proves that by running every status-consuming composer with and
without the field and comparing, rather than by asserting it.

So the fix is a verb-level split, not a field-level one: `status` stops
duplicating a live-paint field onto the structured answer
(`protocol._status_response`), and every live-paint path keeps its full mirror.

Four things are pinned here, and two of them pass by FINDING the credential:

  1. it is gone from every serialised `status` surface (`_assert_absent`);
  2. it is STILL on the live-paint surface -- the session's own buffer,
     `build_response()`, and the real `cockpit/viewport.py` composer fed from
     it (`test_the_live_paint_path_still_shows_what_the_server_painted`);
  3. a recognition-gated redactor would have FAILED OPEN on this exact screen
     (`test_a_recognition_gated_redactor_would_have_failed_open_here`) -- which
     is why the omission is unconditional and relies on no heuristic;
  4. putting the field back puts the credential back, named sink by sink
     (`test_restoring_the_prompt_puts_the_credential_back_on_the_surface`).

No network, no live daemon, no real `config/`, no real `run/` -- a scripted
loopback server, a tmp config dir, and a `mkdtemp` run-dir, exactly as
`tests/test_ensure_login_error_redaction.py` and `tests/test_login_redaction.py`
do. The scripted-server and daemon harnesses below are deliberately LOCAL to
this module rather than imported from a sibling test: small harness doubles are
duplicated per module in this suite instead of coupling test files to each
other's privates (`tests/test_ensure_login_error_redaction.py::_ScriptedTWGS`
states that convention outright, citing `tests/test_login_redaction.py`).
"""

import ast
import contextlib
import io
import json
import os
import shutil
import socket
import tempfile
import threading
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from typing import NamedTuple

import pytest

from tw2002_aiclient import screens
from tw2002_aiclient.cockpit import arm as cockpit_arm
from tw2002_aiclient.cockpit import focus as cockpit_focus
from tw2002_aiclient.cockpit import goals as cockpit_goals
from tw2002_aiclient.cockpit import hud as cockpit_hud
from tw2002_aiclient.cockpit import logsband as cockpit_logsband
from tw2002_aiclient.cockpit import stopbanner as cockpit_stopbanner
from tw2002_aiclient.cockpit import viewport as cockpit_viewport
from tw2002_aiclient.session import cli, classify, credentials, env, login, protocol
from tw2002_aiclient.session.protocol import build_response
from tw2002_aiclient.session.session import Session

# The credential under test. Deliberately does NOT contain the substring
# "password": `classify.py`'s `login_password` gate anchor is exactly
# `re.compile(r"password", re.I)` against the current prompt line, so a sentinel
# containing it would change the automaton's own classification the moment the
# server echoed it back -- which is the scenario under test. Distinct from the
# sentinels in `tests/test_ensure_login_error_redaction.py` and
# `tests/test_login_redaction.py` so a hit in this file's sinks is always this
# file's own credential.
SENTINEL = "S3NT1NEL-C21-STATUS-8d4f6b"
NEEDLES = (SENTINEL,)

PROFILE = "c21"
HANDLE = "AEGIS"
GAME_LETTER = "F"

# A real TWGS door clears and redraws between major screens; without it pyte
# accumulates every screen forever and stale scrollback re-matches the
# automaton's nuisance regexes.
CLEAR = "\x1b[2J\x1b[H"
PASSWORD_SCREEN = CLEAR + "Password?"

# The one server behavior canon's RX-side no-leak guarantee assumes will never
# happen (`canon/doctrine/secrets-and-credentials.md`, Code Divergence #1):
# redraw with exactly what the client just sent, and nothing else. The echoed
# credential then IS the current prompt line -- the row `status["prompt"]` was
# built from.
ECHO_SCRIPT = [(PASSWORD_SCREEN, True), (lambda last: CLEAR + last, False)]
# The control scenario: the same gate, no echo. Used where the point is the
# SHAPE of the answer rather than a leak, so `classification` is a real label
# (`login_password`) and diagnosability is visible rather than asserted.
POLITE_SCRIPT = [(PASSWORD_SCREEN, True), (PASSWORD_SCREEN, False)]


# ---------------------------------------------------------------------------
# a scripted server that starts AT the password gate
# ---------------------------------------------------------------------------


class _ScriptedTWGS:
    """A minimal single-connection scripted telnet server, local to this file.

    A step is `(send, read)`. `send` is the exact bytes-as-text to write, or a
    callable handed the last line read (that is how a step echoes). `read` says
    whether to consume one CRLF-terminated reply before moving on. Steps send
    their bytes VERBATIM, with no implied screen clear, because an inline echo
    is defined by the previous screen still being there.

    Every scenario begins at the password gate rather than replaying the whole
    6-screen cold start: `run_login` re-classifies the CURRENT screen every
    iteration (`tests/test_login_resume.py` proves that), so starting mid-flow
    is legitimate rather than a shortcut, and the prefix would exercise nothing
    this file measures.
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
# a real daemon on the socket path the real CLI actually looks at
# ---------------------------------------------------------------------------


class _Daemon:
    """A real `ThreadingUnixServer` + `CommandHandler` + run-dir error log,
    wired to a REAL telnet `Session`.

    The socket is bound at `env.socket_path(run_dir)` and a pidfile carrying
    THIS process's pid is written at `env.pid_path(run_dir)`, because that pair
    is exactly what `cli.cmd_status`'s `daemon_alive(run_dir)` gate and
    `cli.ensure_raw`'s spawn gate check. Satisfying it is what lets the real CLI
    entry points be the code under test instead of a hand-rolled round trip, and
    what stops `ensure_raw` forking a real daemon at our scripted server
    (asserted, not assumed -- `_assert_no_daemon_was_spawned`).
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


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    """A real config dir with `credentials`' module-level paths pointed at it.

    Those globals are resolved at import time, so `TW_CONFIG_DIR` alone would
    not move them in an already-imported process -- the same reason
    `tests/test_login_redaction.py` and
    `tests/test_ensure_login_error_redaction.py` both monkeypatch the resolved
    paths directly. This is also what guarantees the operator's real
    `config/secrets.json` is never read or written by this file.
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
    both sibling wire suites use `mkdtemp` as well. Never the real `run/`."""
    d = tempfile.mkdtemp(prefix="twd-c21-")
    try:
        yield Path(d)
    finally:
        shutil.rmtree(d, ignore_errors=True)


@pytest.fixture(autouse=True)
def _fast_stagnation(monkeypatch):
    """Shorten the automaton's stagnation waits -- these are timing budgets, not
    the behavior under test, and every scenario here reaches the same decision
    sooner. Same knob the sibling redaction suites turn, for the same reason."""
    monkeypatch.setattr(login, "_STEP_SETTLE_TIMEOUT_S", 1.0)
    monkeypatch.setattr(login, "_RETURNING_REJECT_SETTLE_S", 0.3)


# ---------------------------------------------------------------------------
# the surface under test
# ---------------------------------------------------------------------------


def _write_secrets(cfg: Path) -> Path:
    """A well-formed store holding the sentinel, written at mode 0600 (doctrine:
    the secrets file is created and re-asserted 0600 on every write)."""
    path = cfg / "secrets.json"
    path.write_text(json.dumps({PROFILE: {"password": SENTINEL}}, indent=2), encoding="utf-8")
    os.chmod(path, 0o600)
    return path


def _write_profile(cfg: Path, port: int):
    (cfg / "profiles.toml").write_text(
        f'[{PROFILE}]\nhost = "127.0.0.1"\nport = {port}\n'
        f'game_letter = "{GAME_LETTER}"\nhandle = "{HANDLE}"\n',
        encoding="utf-8",
    )


def _assert_no_daemon_was_spawned(run_dir: Path):
    """`ensure_raw` only forks when its `daemon_alive() and sock_path.exists()`
    gate fails, and the first thing that fork does is open `run/twd.stderr.log`.
    Its ABSENCE is the proof that the responses came from the daemon this test
    wired up, and not from a real one that raced us onto the scripted server."""
    assert not (run_dir / "twd.stderr.log").exists(), (
        "ensure_raw forked a real daemon -- the pidfile/socket gate did not hold, "
        "so this test measured something other than the wired-up daemon"
    )


def _capture_cmd_status(run_dir: Path, *, as_json: bool) -> str:
    """Real `cli.cmd_status` -> real `cli.print_response` -> captured stdout.

    Both branches are captured because a future `screen`-bearing status payload
    would silently switch `print_response` from `json.dumps(resp, indent=2)` to
    the row-printing branch and narrow this sink without anything going red --
    `test_tw_status_serialises_the_whole_dict_on_both_branches` is the guard
    that keeps this instrument honest.
    """
    buf = io.StringIO()
    args = SimpleNamespace(run_dir=str(run_dir), json=as_json, compact=False)
    with redirect_stdout(buf):
        cli.cmd_status(args)
    return buf.getvalue()


class _Run(NamedTuple):
    """One scenario's measurements.

    `status` / `status_sinks` are the surface under test and its instrument.
    `painted` and `live` are the OTHER side of the ruling and are deliberately
    NOT sinks -- see `_assert_absent`'s own note.
    """

    status: dict
    status_sinks: dict[str, str]
    server: "_ScriptedTWGS"
    # What the daemon's own pyte buffer held at the moment it answered the
    # status round trip -- i.e. what the server actually painted. The credential
    # being HERE is the scenario working, not a leak (§C.2 permits the live
    # paint to show it), and it is what makes every absence assertion below
    # non-vacuous now that `status` no longer carries a prompt to look in.
    painted: list[str]
    # `protocol.build_response(session)` against that same buffer -- the exact
    # call `screen`, `attach`, `do`, `send`, `read` and the WatchHub seed /
    # settle-edge emit make. The settle-edge emit is what feeds `watchfeed.py`
    # -> `cockpit/viewport.py`, i.e. the live paint itself.
    live: dict


def _drive(cfg: Path, run_dir: Path, logs: Path, script) -> _Run:
    """Run one scenario end to end and return a `_Run`.

    Real scripted telnet server -> real `Session` -> real daemon on the real
    socket path -> real `cli.ensure_raw` (which is what puts the credential on
    the wire, from the real credential store, via the real login automaton) ->
    real `cli.cmd_status` -> real `cli.print_response`. Nothing on that chain is
    a double.

    The `ensure` leg is not the subject; it is the only honest way to get a
    SERVER-ECHOED credential onto the buffer. Driving it means the sentinel on
    the prompt line is provably the operator's stored password making a round
    trip, not a string this test painted onto the screen itself.
    """
    with _ScriptedTWGS(script) as server:
        _write_profile(cfg, server.port)
        session = Session("127.0.0.1", server.port, PROFILE, str(logs))
        session.start(timeout=10)
        daemon = _Daemon(run_dir, session)
        try:
            cli.ensure_raw(PROFILE, timeout=60.0, run_dir=run_dir)
            # THE SUBJECT: a status round trip over the same live socket, after
            # the echo has landed on the buffer.
            status = cli.send_request("status", {}, run_dir=run_dir)
            as_json = _capture_cmd_status(run_dir, as_json=True)
            as_text = _capture_cmd_status(run_dir, as_json=False)
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
    sinks = {
        "status verb response dict": json.dumps(status),
        "tw status --json stdout": as_json,
        "tw status stdout": as_text,
        "daemon local error log": log_body,
    }
    return _Run(status=status, status_sinks=sinks, server=server, painted=painted, live=live)


def _carriers(sinks: dict[str, str], needle: str) -> list[str]:
    """Which sinks carry `needle`. A list rather than a bool so a failure names
    the carrier instead of only asserting that one exists."""
    return sorted(name for name, body in sinks.items() if needle in body)


def _assert_absent(sinks: dict[str, str]):
    """Sweep the sinks a copy can LEAVE the session through.

    `json.dumps` of the whole response rather than a per-key check: a nested
    value passes a shallow key check and still crosses the wire and reaches
    disk.

    `_Run.painted` and `_Run.live` are deliberately never passed here. They are
    the session's own buffer and the live-paint response built from it -- §C.2
    permits those to show what the server painted, and sweeping them would turn
    this file into an argument for sanitising the operator's own screen, which
    the ruling explicitly refuses.
    """
    for needle in NEEDLES:
        hits = _carriers(sinks, needle)
        assert not hits, f"{needle!r} reached: {', '.join(hits)}"


# ---------------------------------------------------------------------------
# THE STRUCTURED SIDE -- what §C.2 rules out
# ---------------------------------------------------------------------------


def test_an_echoing_server_no_longer_reaches_the_status_surface(cfg, tmp_path, run_dir):
    """The echoing-server case, driven all the way to the operator's `tw status`
    stdout.

    Canon (`doctrine/secrets-and-credentials.md`, Code Divergence #1) states the
    RX-side guarantee honestly: redaction is structural on TX only, the receive
    channel is transcribed verbatim, and the no-leak property rests on the
    telnet convention that a password prompt suppresses echo. Its "Status-verb
    wire" paragraph (Mack PoC, P3-041) names this surface specifically: a server
    that does echo puts the typed credential on the current prompt line, and
    `status["prompt"]` was built from exactly that row.

    Unlike `ensure`'s failure answer, there is no narrower human-readable
    branch to hide behind here -- a status response has no `screen` key, so both
    `tw status` and `tw status --json` serialise the whole dict.
    """
    _write_secrets(cfg)
    run = _drive(cfg, run_dir, tmp_path / "logs", ECHO_SCRIPT)

    # Non-vacuity, in three parts: the credential really went out, it really
    # came back, and it came back on the CURRENT prompt line -- the row the
    # withdrawn field was built from.
    assert run.server.received == [SENTINEL]
    assert any(SENTINEL in row for row in run.painted), (
        "the server did not echo -- this scenario stopped being the one under test"
    )
    assert SENTINEL in run.painted[-1], (
        "the echo is not on the prompt line -- this scenario no longer isolates "
        "status['prompt'] as the carrier"
    )
    assert run.status["ok"] is True, run.status

    _assert_absent(run.status_sinks)


def test_the_status_answer_carries_only_bounded_fields(cfg, tmp_path, run_dir):
    """The status answer's field set, asserted EXACTLY.

    The sweep above is a content assertion: it goes red when a credential
    reaches a sink, which needs the day's scripted server to have echoed. This
    is the structural complement -- it goes red the moment an unbounded field is
    attached to the status answer, echo or no echo, and it is therefore what
    protects the fix from a well-meaning "restore the diagnostic context" edit
    tested against a polite server.

    The expected set is written out here rather than imported from `protocol.py`:
    a test that read the module's own constant would follow any edit to it and
    pin nothing.

    Every field is bounded by construction, and that is the property under test,
    not the count:

      `ok`/`connected`        booleans
      `idle_ms`/`subscribers` scalars
      `classification`        `classify_screen`'s CLOSED vocabulary; `unknown`
                              for anything it cannot name, never a slice of the
                              screen
      `host`/`port`/`name`    the PROFILE's own values, not receive-buffer content
      `autopilot`             one `bool` from `autoloop.arm_block()` — a live
                              runtime fact since `session/autoloop.py` landed,
                              no longer the hardcoded literal this row used to
                              describe. Still carries no receive-buffer content,
                              which is what this table is about.
      `mode`                  `control_lock`'s closed vocabulary
      `log_tail`              TX-only, redact-at-INSERT: `transcript_tail.
                              TranscriptTail.append_redacted()` cannot accept a
                              payload at all, so no receive-side byte can enter
                              that ring
      `prompt_withheld`       a closed literal saying WHY the line is absent

    Run against the POLITE script on purpose: with no echo the screen still
    classifies `login_password`, so this doubles as the positive diagnosability
    assertion. An empty/None classification would satisfy every absence
    assertion in this file and be a regression.

    `prompt` is asserted absent by KEY, and the key is omitted rather than set
    to a marker string, so a caller doing `resp["prompt"]` fails loudly instead
    of formatting `"<withheld>"` into a plausible-looking prompt line.
    """
    _write_secrets(cfg)
    run = _drive(cfg, run_dir, tmp_path / "logs", POLITE_SCRIPT)
    status = run.status

    assert set(status) == {
        "ok",
        "connected",
        "idle_ms",
        "classification",
        "prompt_withheld",
        "host",
        "port",
        "name",
        "autopilot",
        "subscribers",
        "mode",
        "log_tail",
    }
    assert "prompt" not in status
    assert "screen" not in status
    assert "color" not in status
    assert status["prompt_withheld"] == "structured_mirror"
    assert status["classification"] == "login_password"
    # The profile fields are the profile's, not the screen's -- pinned so a
    # future "helpful" edit cannot quietly repoint one at the buffer.
    assert status["name"] == PROFILE
    assert status["host"] == "127.0.0.1"


def test_tw_status_serialises_the_whole_dict_on_both_branches(cfg, tmp_path, run_dir):
    """Instrument check for `_assert_absent`'s two stdout sinks.

    `cli.print_response` only takes its narrow row-printing branch when the
    response has a `screen` key; a status response has none, so BOTH `tw status`
    and `tw status --json` dump the entire dict. That is what makes those two
    sinks meaningful. If a future change gave `status` a `screen` key, the human
    branch would silently stop printing most fields and the sweep would narrow
    without anything going red -- so the property is asserted, not assumed.
    """
    _write_secrets(cfg)
    run = _drive(cfg, run_dir, tmp_path / "logs", POLITE_SCRIPT)

    for sink in ("tw status stdout", "tw status --json stdout"):
        body = run.status_sinks[sink]
        for field in ("classification", "idle_ms", "log_tail", "prompt_withheld"):
            assert field in body, f"{sink} no longer carries {field} -- this sink narrowed"
        # The CLI's own two additions ride both branches too.
        assert "daemon_running" in body
        assert "run_dir" in body


def test_a_recognition_gated_redactor_would_have_failed_open_here(cfg, tmp_path, run_dir):
    """Why the omission is unconditional, measured rather than argued.

    The tempting cheaper fix is to redact only when the prompt "looks
    secret-adjacent" -- `classify.py`'s `login_password` gate anchor is
    literally `re.compile(r"password", re.I)`, and `is_probable_secret_prompt()`
    is a wider word list over the same idea, so the signal genuinely exists.

    It fails OPEN in exactly the scenario that matters, and this test executes
    that failure: an echoing server REPLACES the word "password" on the prompt
    line with the credential, so both recognisers answer "not a secret prompt"
    about a line that is nothing but a secret. A redactor gated on either one
    would have handed the credential straight through.

    This is the executable form of `_status_response`'s "redaction that depends
    on recognition is redaction that stops the day recognition does".
    """
    _write_secrets(cfg)
    run = _drive(cfg, run_dir, tmp_path / "logs", ECHO_SCRIPT)

    echoed_line = run.painted[-1]
    assert SENTINEL in echoed_line  # non-vacuity: this IS the credential's row

    assert not classify.is_probable_secret_prompt(echoed_line), (
        "is_probable_secret_prompt() now recognises the echoed line -- if that is "
        "a deliberate widening, this test's argument needs revisiting, but a "
        "heuristic gate on the secrets path still fails open on the next shape"
    )
    assert (
        classify.classify_screen("\n".join(run.painted), echoed_line) != "login_password"
    ), "the echoed screen still classifies as login_password -- rewrite this scenario"
    # And the answer is clean anyway, because it never asked either of them.
    _assert_absent(run.status_sinks)


# ---------------------------------------------------------------------------
# THE OTHER HALF OF THE RULING -- what §C.2 deliberately does NOT redact
# ---------------------------------------------------------------------------


def test_the_live_paint_path_still_shows_what_the_server_painted(cfg, tmp_path, run_dir):
    """§C.2's carve-out, executable: the fix withholds what LEAVES the session,
    never what the operator's own eyes see.

    Over-applying the redaction into the cockpit paint would break the product's
    whole purpose, so the boundary is pinned by execution rather than by
    intention. After the SAME echoing session whose `status` answer is now
    clean:

      * the session's own pyte buffer still holds the echoed credential --
        nothing sanitised the terminal;
      * `protocol.build_response(session)` still mirrors it in `screen` AND in
        its own `prompt` -- that is the exact call `screen`, `attach`, `do`,
        `send`, `read` and the WatchHub seed / settle-edge emit make; and
      * `cockpit/viewport.py`'s REAL composer, fed that response the way
        `watchfeed.WatchFeed` feeds it, still paints it.

    That last one is the assertion that actually answers "does the HUD still
    show what the server painted": it runs the product's own GAME-viewport
    composer, not a description of it.

    This is the one place in the file where finding the sentinel is the PASSING
    condition. If a future change starts scrubbing the buffer, the shared
    `build_response`, or the viewport, this goes red first and names the ruling
    -- which is the failure mode worth catching, because every other test here
    only gets *stricter* when that happens.
    """
    _write_secrets(cfg)
    run = _drive(cfg, run_dir, tmp_path / "logs", ECHO_SCRIPT)

    # The structured answer is clean (the rest of this file's subject) ...
    _assert_absent(run.status_sinks)

    # ... and the live paint is UNCHANGED. Both halves in one measurement, so
    # neither can be "fixed" by breaking the other.
    assert any(SENTINEL in row for row in run.painted), (
        "the session's own screen no longer holds what the server painted -- "
        "DECISIONS.md §C.2 permits the live paint to show it; sanitising the "
        "buffer itself is the over-application the ruling forbids"
    )
    assert any(SENTINEL in row for row in run.live["screen"]), (
        "protocol.build_response() stopped mirroring the buffer -- that call feeds "
        "screen/attach/do/send/read and the WatchHub emit behind the cockpit viewport"
    )
    assert SENTINEL in run.live["prompt"], (
        "build_response() stopped carrying the live prompt line -- the withholding "
        "belongs to the `status` verb alone, not to the live-paint answer"
    )

    painted_rows = cockpit_viewport.compose_viewport_lines(run.live, width=200, height=40)
    assert any(SENTINEL in row for row in painted_rows), (
        "the GAME viewport composer no longer paints what the server painted -- "
        "this is the product's core purpose, not a diagnostic"
    )


# ---------------------------------------------------------------------------
# THE SPLIT ITSELF -- `status` has no live-paint consumer to break
# ---------------------------------------------------------------------------
#
# Every product surface that is handed the shared `status` snapshot (app.py's
# `_daemon_status_provider` -> `PlayShellScreen.draw`), enumerated from the
# `status.get(` / `status[` reads in `cockpit/` and `screens.py`.
#
# `viewport` is absent on purpose: it composes from the subscribe EVENT, never
# from `status`, which is the whole reason the verb-level split works.
# `cockpit/control_seat.py` is absent because it is not a consumer -- it
# discusses `status["mode"]` in prose, but every composer it exports takes
# primitives, not the status dict.
#
# `screens._resolve_last_rx_age_s` is private; it is included anyway because
# the claim under test is about CONSUMERS, and a private one consumes just as
# hard as a public one. `PlayShellScreen._viewport_border_attr` reads the same
# two fields (`connected`/`idle_ms`) through it and needs a curses window, so
# it is represented by this helper rather than instantiated.
_STATUS_PANELS = {
    "GOALS": lambda s: cockpit_goals.compose_goals_lines(s, width=30),
    "FOCUS": lambda s: cockpit_focus.compose_focus_lines(s, width=30),
    "LOGS band": lambda s: cockpit_logsband.compose_logs_lines(s, width=80, height=3),
    "LOGS newest": lambda s: cockpit_logsband.newest_tail_entry(s),
    "STOP banner": lambda s: cockpit_stopbanner.compose_stop_banner_lines(s, width=80),
    "STOP needs_attention": lambda s: cockpit_stopbanner.needs_attention(s),
    "ARM chip": lambda s: cockpit_arm.compose_arm_chip(s),
    "HUD cells": lambda s: cockpit_hud.compose_hud_cells(s, width=60),
    "viewport border freshness": lambda s: screens._resolve_last_rx_age_s(s),
}


# One perturbation per panel: the field(s) THAT panel is documented to read.
# Applied all at once, so every entry in `_STATUS_PANELS` must move -- which is
# what turns "the panel ignored `prompt`" from a trivial fact about an inert
# composer into a fact about a live one.
_PANEL_SENSITIVITY_PROBE = {
    "turns_left": 42,  # GOALS
    "focus": {"candidates": [{"kind": "run_chain", "ev_per_turn": 12.5, "gated": False}]},
    "log_tail": ["app> a line no panel can ignore"],  # LOGS band + newest
    "intervention": {"needs_attention": True, "reason": "manual_stop"},  # STOP
    "mode": "human",  # STOP banner's handoff marker
    "autopilot": {"running": True},  # ARM chip
    "hud": {"credits": {"value": 1234, "age_s": 1.0}},  # HUD cells
    "idle_ms": 987654,  # viewport border freshness
}


def _paint_every_panel(status: dict) -> dict[str, str]:
    """Every status-consuming cockpit composer's output, as comparable text."""
    return {name: repr(fn(status)) for name, fn in _STATUS_PANELS.items()}


def test_no_cockpit_panel_changes_when_the_prompt_field_disappears(cfg, tmp_path, run_dir):
    """The measurement behind the whole design: `status["prompt"]` had no
    live-paint consumer, so withholding it changes nothing the operator sees.

    §C.2.1 poses `status` as one field with two consumers pulling opposite ways.
    Run against the tree, it is one field with one KIND of consumer: every
    cockpit panel is composed twice from the SAME real status payload -- once
    with the echoed prompt line put back on it, once as the daemon now answers
    -- and the two paints are compared byte for byte. They are identical,
    because no panel reads the field. The live paint the operator actually
    watches is the GAME viewport, and it is fed by the subscribe event
    (`test_the_live_paint_path_still_shows_what_the_server_painted`).

    **Every panel is proven individually live before its indifference counts.**
    A composer that reads nothing at all would satisfy the equality assertion
    trivially, and several of these panels DO render all-unknown against today's
    daemon (`focus`/`hud` have no wire bridge yet). So the control perturbs, in
    one pass, the field each panel is documented to read, and requires EVERY
    entry to move. A panel that stops moving has either lost its subject or gone
    inert -- either way its silence about `prompt` stops being evidence, and
    this test says so by name instead of passing quietly.
    """
    _write_secrets(cfg)
    run = _drive(cfg, run_dir, tmp_path / "logs", ECHO_SCRIPT)

    as_answered = dict(run.status)
    with_prompt = {**as_answered, "prompt": run.painted[-1]}
    assert SENTINEL in with_prompt["prompt"]  # non-vacuity: the leak is present

    # SENSITIVITY CONTROL first -- prove each panel can move at all.
    baseline = _paint_every_panel(as_answered)
    probed = _paint_every_panel({**as_answered, **_PANEL_SENSITIVITY_PROBE})
    inert = sorted(name for name in baseline if probed[name] == baseline[name])
    assert not inert, (
        f"{inert} did not move when the field(s) they read were perturbed -- an inert "
        "composer's indifference to status['prompt'] is not evidence of anything, so "
        "the equality assertion below would be vacuous for those panels"
    )

    before = _paint_every_panel(with_prompt)
    assert before == baseline, (
        "a cockpit panel's paint changed when status['prompt'] disappeared -- "
        "the verb-level split assumed no panel consumes that field; it now does, "
        "and DECISIONS.md §C.2.1 needs re-deciding rather than this test relaxed"
    )
    # And, positively: even WITH the field present, no panel ever painted it.
    for name, painted in before.items():
        assert SENTINEL not in painted, f"{name} renders status['prompt'] verbatim"


# ---------------------------------------------------------------------------
# THE SHAPE OF THE FIX -- pinned structurally
# ---------------------------------------------------------------------------


def _forbidden_call_names(tree) -> set[str]:
    """`build_response` plus every module-level alias of it.

    `tests/test_ensure_login_error_redaction.py`'s sibling tripwire records
    alias evasion as a stated limit; this one closes the two spellings that are
    actually reachable in a single-module refactor -- a rebinding
    (`_br = build_response`) and a re-import under another name -- so the pin
    does not quietly lapse the day someone tidies the imports.
    """
    names = {"build_response"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for a in node.names:
                if a.name == "build_response" and a.asname:
                    names.add(a.asname)
        elif isinstance(node, ast.Assign) and isinstance(node.value, ast.Name):
            if node.value.id in names:
                names.update(t.id for t in node.targets if isinstance(t, ast.Name))
    return names


# The fields that mirror the receive buffer. `build_response()` is allowed to
# carry all three; the structured `status` answer is allowed none of them.
_MIRROR_FIELDS = frozenset({"screen", "prompt", "color"})

# Opaque constructors: a `resp.update(x)` / `eval` / `exec` inside the builder
# puts keys on the response that no AST walk can enumerate.
_OPAQUE_CALLS = frozenset({"update", "eval", "exec", "setattr", "vars", "locals"})


def _mirror_violations(region, forbidden_call_names) -> list[str]:
    """Every way `region` could put a receive-buffer mirror on its response that
    this walker can either SEE or refuses to be blind to.

    Returns human-readable problem strings (empty == clean) rather than
    asserting, so the same walker can be pointed at a synthetic region to prove
    it fires.

    Four families:

      * a call to `build_response` or a resolved alias of it -- the mirror
        builder itself, in either the bare or the `protocol.`-qualified spelling;
      * an opaque call (`update`/`eval`/`exec`/...) that adds keys this walk
        cannot enumerate;
      * a mirror field named as a dict key or assigned by subscript;
      * a name this walker cannot EVALUATE -- a computed dict key, a computed
        subscript, or `getattr(x, <non-literal>)`. Literal reflection is fine
        (`getattr(server, "watch_hub", None)` is exactly how the builder reads
        its optional collaborators); it is the unreadable name that is refused,
        because that is the shape an evasion takes.
    """
    problems: list[str] = []

    for n in ast.walk(region):
        if isinstance(n, ast.Call):
            name = None
            if isinstance(n.func, ast.Name):
                name = n.func.id
            elif isinstance(n.func, ast.Attribute):
                name = n.func.attr
            if name in forbidden_call_names:
                problems.append(
                    f"calls {name}() -- that response mirrors the whole receive buffer, "
                    "which on an echoing server IS the credential (canon DECISIONS.md §C.2)"
                )
            elif name in _OPAQUE_CALLS:
                problems.append(
                    f"calls {name}() -- it can add response keys this walk cannot enumerate"
                )
            elif name in ("getattr", "setdefault") and len(n.args) >= 2:
                attr = n.args[1]
                if not (isinstance(attr, ast.Constant) and isinstance(attr.value, str)):
                    problems.append(
                        f"reaches a field via {name}() on a computed name -- this tripwire "
                        "cannot see through it, so it is refused rather than trusted"
                    )
                elif attr.value in _MIRROR_FIELDS:
                    problems.append(f"reaches mirror field {attr.value!r} via {name}()")

        elif isinstance(n, ast.Dict):
            for k in n.keys:
                if k is None:  # `{**other}` -- unenumerable
                    problems.append("splats another mapping into a response dict (`{**...}`)")
                elif not (isinstance(k, ast.Constant) and isinstance(k.value, str)):
                    problems.append("builds a response dict with a computed key")
                elif k.value in _MIRROR_FIELDS:
                    problems.append(f"names mirror field {k.value!r} as a response key")

        elif isinstance(n, ast.Subscript) and isinstance(n.ctx, ast.Store):
            sl = n.slice
            if isinstance(sl, ast.Constant) and isinstance(sl.value, str):
                if sl.value in _MIRROR_FIELDS:
                    problems.append(f"assigns mirror field {sl.value!r} onto the response")
            else:
                problems.append("assigns a response key through a computed subscript")

    return problems


def test_the_status_answer_is_built_without_reaching_for_the_mirror():
    """Structural tripwire on the SHAPE of the fix, in the same family as
    `tests/test_ensure_login_error_redaction.py::
    test_the_failure_answer_is_built_without_reaching_for_the_mirror`.

    The behavioral pins above cover the code that exists today. This covers the
    edit that would undo it: `_status_response` and `dispatch`'s `status` branch
    are walked and refused if either calls `build_response` (or an alias of it),
    names a mirror field as a response dict key / subscript assignment, or
    reaches a field through a name this walker CANNOT EVALUATE -- a computed
    dict key, a computed subscript, `resp.update(...)`, or a
    `getattr(x, <non-literal>)`. That last family is how a literal-node
    tripwire is normally evaded, so it is refused rather than trusted.

    Literal reflection is deliberately still allowed: `_status_response` reads
    `getattr(server, "watch_hub", None)` and friends, whose attribute names are
    constants the walker CAN read and check. The rule is "I refuse what I
    cannot see", not "I refuse `getattr`" -- a blanket ban would have to be
    suppressed on day one, and a suppressed tripwire is not a tripwire.

    Deliberately narrow: it does NOT forbid `build_response` in `protocol.py` at
    large, because `screen`, `do`, `send`, `read` and every ensure SUCCESS path
    must keep calling it -- §C.2 rules on the structured answer, not on the
    mirror.

    **Known limit, stated rather than implied:** this reads the AST of two named
    regions, so a leak routed through a helper defined elsewhere still slips
    through. It is a tripwire on the reachable regressions, not a proof of
    absence -- the proof is the whole-sink sweeps above.
    """
    import inspect

    from tw2002_aiclient.session import protocol as protocol_module

    tree = ast.parse(inspect.getsource(protocol_module))
    funcs = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    forbidden = _forbidden_call_names(tree)

    builder = funcs["_status_response"]
    status_branch = [
        n
        for n in ast.walk(funcs["dispatch"])
        if isinstance(n, ast.If)
        and isinstance(n.test, ast.Compare)
        and any(isinstance(c, ast.Constant) and c.value == "status" for c in n.test.comparators)
    ]
    assert status_branch, "no `verb == \"status\"` branch in dispatch -- this pin lost its subject"

    for region, label in [
        (builder, "_status_response"),
        (status_branch[0], "dispatch status branch"),
    ]:
        for problem in _mirror_violations(region, forbidden):
            pytest.fail(f"{label}: {problem}")


def test_the_status_answer_carries_no_alias_of_the_mirror_builder():
    """The alias spelling, pinned separately so the main tripwire's own
    resolution step cannot rot silently.

    `_forbidden_call_names` resolves `build_response`'s module-level rebindings
    and re-imports; this proves the resolver actually finds one, against a
    synthetic module rather than by hoping `protocol.py` ever grows an alias.
    """
    tree = ast.parse(
        "from .protocol import build_response as _br\n"
        "_mirror = build_response\n"
        "def _status_response(session, server):\n"
        "    return _br(session)\n"
    )
    names = _forbidden_call_names(tree)
    assert {"build_response", "_br", "_mirror"} <= names

    builder = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}["_status_response"]
    problems = _mirror_violations(builder, names)
    assert any("_br" in p for p in problems), problems


@pytest.mark.parametrize(
    "label, source, expect",
    [
        (
            "the literal regression: the pre-fix `prompt` key restored",
            "def f(session, server):\n"
            "    rows = session.render()\n"
            "    prompt = rows[-1].strip() if rows else ''\n"
            "    return {'ok': True, 'prompt': prompt}\n",
            "names mirror field 'prompt'",
        ),
        (
            "the subscript spelling",
            "def f(session, server):\n"
            "    resp = {'ok': True}\n"
            "    resp['prompt'] = session.render()[-1]\n"
            "    return resp\n",
            "assigns mirror field 'prompt'",
        ),
        (
            "the computed-key evasion a literal walker would miss",
            "def f(session, server):\n"
            "    key = 'pro' + 'mpt'\n"
            "    return {'ok': True, key: session.render()[-1]}\n",
            "computed key",
        ),
        (
            "the computed-subscript evasion",
            "def f(session, server):\n"
            "    resp = {'ok': True}\n"
            "    resp['pro' 'mpt'.upper().lower()] = session.render()[-1]\n"
            "    return resp\n",
            "computed subscript",
        ),
        (
            "the mapping-splat evasion",
            "def f(session, server):\n"
            "    return {'ok': True, **build_response(session)}\n",
            "splats another mapping",
        ),
        (
            "the reflection evasion",
            "def f(session, server):\n"
            "    name = 'pro' + 'mpt'\n"
            "    return {'ok': True, 'x': getattr(session, name)}\n",
            "computed name",
        ),
    ],
)
def test_the_tripwire_fires_on_each_way_the_mirror_could_come_back(label, source, expect):
    """Bookend for the tripwire: a walker that never fires proves nothing.

    Each case is a builder that puts the mirror back by a DIFFERENT spelling --
    the literal key, the subscript, and the four evasions a naive literal-node
    walker would sail past (computed key, computed subscript, mapping splat,
    reflection on a computed name). None is ever written to disk or imported;
    they are parsed from strings.

    The last four are the reason `_mirror_violations` refuses what it cannot
    evaluate rather than only rejecting what it recognises: recorded lesson from
    this suite's AST-guard family -- a tripwire keyed on literal nodes alone is
    evaded by the first refactor that builds a name.
    """
    builder = ast.parse(source).body[0]
    problems = _mirror_violations(builder, {"build_response"})
    assert any(expect in p for p in problems), f"{label}: {problems}"


def test_the_tripwire_is_quiet_on_the_shape_the_builder_actually_uses():
    """Sensitivity's other half: the walker must NOT fire on literal reflection
    and constant keys, or `_status_response` could only stay green by suppressing
    it -- and a suppressed tripwire is not a tripwire."""
    source = (
        "def f(session, server):\n"
        "    watch_hub = getattr(server, 'watch_hub', None)\n"
        "    resp = {'ok': True, 'classification': classify_screen(t, p)}\n"
        "    resp['log_tail'] = getattr(session, 'tail', None)\n"
        "    return resp\n"
    )
    assert _mirror_violations(ast.parse(source).body[0], {"build_response"}) == []


# ---------------------------------------------------------------------------
# MANDATORY falsification -- put the field back, watch the sweep fire
# ---------------------------------------------------------------------------


def _leaky_status_response(session, server):
    """`dispatch`'s PRE-FIX `status` branch, verbatim (protocol.py at 3489865,
    the commit this work branched from) -- the `prompt` key restored and nothing
    else changed.

    Patched in with `monkeypatch`, never edited on disk -- the same idiom
    `tests/test_ensure_login_error_redaction.py::_leaky_login_failure_response`
    and `tests/test_login_redaction.py::_leaky_log_tx` use, and for the same
    reason: the fix stays applied on disk for the whole run, so nothing else (a
    concurrent xdist worker included) can observe a half-reverted tree.
    """
    import time

    from tw2002_aiclient.session.classify import classify_screen

    rows = session.render()
    text = session.render_text(rows)
    prompt = rows[-1].strip() if rows else ""
    watch_hub = getattr(server, "watch_hub", None)
    resp = {
        "ok": True,
        "connected": session.conn.connected,
        "idle_ms": int((time.monotonic() - session.last_rx) * 1000),
        "classification": classify_screen(text, prompt),
        "prompt": prompt,
        "host": session.host,
        "port": session.port,
        "name": session.name,
        "autopilot": {"running": False},
        "subscribers": watch_hub.subscriber_count() if watch_hub else 0,
    }
    lock = getattr(server, "control_lock", None)
    if lock is not None:
        mode = getattr(lock, "mode", None)
        if isinstance(mode, str):
            resp["mode"] = mode
    tail = getattr(session, "tail", None)
    resp["log_tail"] = tail.snapshot() if tail is not None else []
    return resp


def test_restoring_the_prompt_puts_the_credential_back_on_the_surface(
    cfg, tmp_path, run_dir, monkeypatch
):
    """The bookend every absence assertion in this file needs.

    A green sweep proves nothing unless the sweep can go red. Re-attach the
    pre-fix `prompt` field -- changing nothing else, not the server, not the
    scenario, not the instrument -- and the credential is back on the operator's
    JSON, in every serialised sink at once. That reproduces the carrier on demand
    instead of relying on a `git`-archaeology claim, and it is what makes
    `test_an_echoing_server_no_longer_reaches_the_status_surface` (the same
    scenario, unpatched) a measurement rather than a hope.

    Note WHICH sinks light up, because it is the difference from the `ensure`
    carrier: there, only `--json` leaked and the human-readable branch was always
    clean. Here BOTH stdout renderings carry it, because a status payload has no
    `screen` key for `print_response`'s narrow branch to trigger on.

    `_assert_absent` is exercised through `pytest.raises` rather than only
    checking `_carriers`: the helper is the thing every other test in this file
    trusts, so it is the thing this proves fires.
    """
    monkeypatch.setattr(protocol, "_status_response", _leaky_status_response)
    _write_secrets(cfg)
    run = _drive(cfg, run_dir, tmp_path / "logs", ECHO_SCRIPT)

    assert "prompt" in run.status
    assert _carriers(run.status_sinks, SENTINEL) == [
        "status verb response dict",
        "tw status --json stdout",
        "tw status stdout",
    ]
    with pytest.raises(AssertionError, match=SENTINEL):
        _assert_absent(run.status_sinks)
