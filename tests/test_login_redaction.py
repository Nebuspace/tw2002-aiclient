"""Login-path credential redaction — the FAILURE half (WO-AUDIT-LOGIN-REDACTION-REHAB).

`session/login.py`'s module docstring makes a four-part claim in prose:

    "The password NEVER touches this module's return values, exceptions, or
     any log call"

`tests/test_login.py` pins the transcript-log third of that on four *successful*
or cleanly-refused arcs. Nothing collected pinned the **exceptions** third at
all — this file was on `pytest.ini`'s banked-rehab ignore list still importing
the deleted `twclient` package, so it looked like coverage while running zero
tests. This is the rehab, and the exception sink is its centre.

**Why every scenario here drives a real failure.** A sibling suite
(`tests/test_attach_redaction.py`) is a good suite with a genuine falsification
test, and it stayed 8/8 GREEN while the forbidden defect sat in the send
*failure* path — because every one of its tests drives a *successful* send. A
green suite says nothing about a path it never exercises. So the scenarios below
are: a rejected password, a credential store that is malformed, one that is not
valid UTF-8, one that cannot be read at all, a send that dies on the wire
mid-password, an unrecognized screen after the password, the NEW branch's retry
ceiling, and a store that fails on the *save* side rather than the read side.

**The four sinks** each scenario is swept for:

1. **return value** — `run_login`'s `(classification, steps)` tuple.
2. **exception** — `LoginError` *and anything else that escapes `run_login`*,
   rendered every way this codebase renders an exception (`str`, `repr`, both
   f-string forms, `traceback.format_exception`, type name, and the
   `__cause__`/`__context__` chain). Two of the scenarios below raise something
   that is NOT a `LoginError` at all, which is exactly why the sweep is written
   against "whatever escaped" rather than against a type. `repr` joined the set
   with WO-SECRETS-REPR-GET-PASSWORD-REHAB — see `_exception_renderings`.
3. **transcript sinks** — the `TranscriptLogger` file (as text, as raw bytes,
   and via `grep -a`), plus the live LOGS-band ring, `last_sent`, and the whole
   JSON-dumped `status` / `ensure` wire response.
4. **ledger sink** — there is no ledger module in the reborn tree
   (`loops/store.py` says so outright), so a name-scoped assertion would prove
   nothing about a sink that does not exist. Instead every byte the run left on
   disk under its own tmp root is swept, minus the one sanctioned home
   (`config/secrets.json`). Same claim without the name, and a ledger that
   lands later is covered the day it first writes a file.

**Canaries, not just the password.** A decoder's own text can carry document
content, and the leak depends on the error's SHAPE rather than on the file:
measured this session, `tomllib` renders a duplicate table as
``Cannot declare ('canary_key',) twice`` — lifting a name straight out of the
document — while a duplicate *key* renders ``Cannot overwrite a value`` and
leaks nothing. `JSONDecodeError.doc` and `UnicodeDecodeError.object` hold the
ENTIRE failed-to-parse file. `config/secrets.json` is parsed on `run_login`'s
own path, so the store failures below plant a canary KEY and a canary VALUE
(a sibling profile's stored credential) inside the failing document alongside
the sentinel, and assert against all three.

**Methodology note (carried forward from the archived suite).** A plain shell
`grep` on a transcript can be FALSE-CLEAN: real RX traffic legitimately carries
NUL/control bytes, and grep's `-I` ("treat a binary-looking file as never
matching") makes one NUL ahead of the needle enough to report "no match". Every
shell-level check here goes through `_grep_a_contains` (`grep -a -F`), and every
in-process check uses Python containment on text AND on raw bytes.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import socket
import subprocess
import tempfile
import threading
import traceback
from pathlib import Path

import pytest

from tw2002_aiclient.session import credentials, login, protocol
from tw2002_aiclient.session.connection import TelnetConnection
from tw2002_aiclient.session.session import Session

from .fake_twgs import FakeTWGS

# The credential under test. Deliberately does NOT contain the substring
# "password": `classify.py`'s `login_password` gate anchor is exactly
# `re.compile(r"password", re.I)` against the current prompt line, so a
# sentinel containing it would change the automaton's own classification the
# moment a server echoed it back (the echo scenario below).
SENTINEL = "S3NT1NEL-LOGIN-PW-4d91c7"
# A sibling profile inside the SAME secrets.json: the key names it, the value
# is its stored credential. Both are document content, and a decoder message
# that quotes the document quotes one of these long before it quotes the
# profile actually being logged in.
CANARY_KEY = "canary-sibling-profile-7b3e02"
CANARY_VALUE = "canary-sibling-pw-9f4a15"

# Every needle, for the sweeps. A store-failure scenario never sends the
# password at all, so the canaries are what make those sweeps non-vacuous:
# they are provably inside the document the decoder just choked on.
NEEDLES = (SENTINEL, CANARY_KEY, CANARY_VALUE)

PROFILE = "redaction"
HANDLE = "AEGIS"
GAME_LETTER = "F"


# ---------------------------------------------------------------------------
# the credential store — real files, real failures
# ---------------------------------------------------------------------------


def _good_secrets_text() -> str:
    """A well-formed store holding the sentinel plus the canary sibling."""
    return json.dumps(
        {
            PROFILE: {"password": SENTINEL},
            CANARY_KEY: {"password": CANARY_VALUE},
        },
        indent=2,
    )


def _malformed_secrets_text() -> str:
    """Valid-looking JSON, truncated mid-object -- `json.load` raises
    `JSONDecodeError`, whose `.doc` holds the whole document. Shaped so the
    canary sits AFTER the sentinel and BEFORE the damage, i.e. a message that
    quoted "the part it was reading" would quote a credential."""
    return _good_secrets_text().rstrip()[:-2]


def _non_utf8_secrets_bytes() -> bytes:
    """The same well-formed document with a lone 0xFF appended.
    `credentials.get_password` opens with `encoding="utf-8"`, so the decode
    fails during the READ -- a `UnicodeDecodeError`, which is neither an
    `OSError` nor a `JSONDecodeError`, and whose `.object` is the entire file."""
    return _good_secrets_text().encode("utf-8") + b"\xff"


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
    `tests/test_daemon_internal_error_typename.py` monkeypatches the resolved
    paths directly. `protocol._save_password` reads `credentials.SECRETS_PATH`
    at call time too, so the write side follows this fixture as well.
    """
    d = tmp_path / "config"
    d.mkdir()
    monkeypatch.setattr(credentials, "CONFIG_DIR", d)
    monkeypatch.setattr(credentials, "SECRETS_PATH", d / "secrets.json")
    monkeypatch.setattr(credentials, "PROFILES_PATH", d / "profiles.toml")
    monkeypatch.setattr(credentials, "SERVERS_PATH", d / "servers.toml")
    return d


# ---------------------------------------------------------------------------
# the sinks
# ---------------------------------------------------------------------------


def _grep_a_contains(path, needle: str) -> bool:
    """`grep -a` (force text) + `-F` (fixed string) + exit-code only. See the
    module docstring: a bare `grep` can silently miss a real match in a
    control-byte-laden transcript."""
    return subprocess.run(["grep", "-a", "-q", "-F", "--", needle, str(path)]).returncode == 0


def _transcript_logs(log_dir: Path) -> list[Path]:
    logs = sorted(Path(log_dir).glob("session-*.log"))
    assert logs, "expected the session to have written a transcript log"
    return logs


def _exception_renderings(exc: BaseException) -> dict[str, str]:
    """Every way this codebase renders an exception, applied to whatever
    escaped `run_login`.

    `repr()` used to be deliberately EXCLUDED here, and the exclusion was a
    measured decision rather than an oversight: `repr(UnicodeDecodeError)`
    renders `args`, and `args[1]` was the ENTIRE undecodable secrets file. The
    omission was defensible only because nothing on the login path reprs an
    exception -- `daemon.py` puts `type(e).__name__` on the wire and
    `traceback.format_exc()` in the owner-only local log, and `guardian.py`
    renders `str(e)` for its typed catch and a type name for its broad one --
    while the now-retired `menu/crawl_driver.py` DID repr, into a persisted
    file, one caller away.

    WO-SECRETS-REPR-GET-PASSWORD-REHAB closed that at the source:
    `credentials.get_password` now raises a bounded
    `credentials.SecretStoreUnreadable` instead of the decoder's own
    exception, so `repr()` is a rendering the product may safely perform and
    it belongs in this set. The residual -- the cause still owns the buffer,
    and nothing renders it -- is pinned in
    `tests/test_secrets_store_redaction.py`.
    """
    chain: list[BaseException] = []
    seen = set()
    cur: BaseException | None = exc
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        chain.append(cur)
        cur = cur.__cause__ or cur.__context__
    return {
        "str(exc)": str(exc),
        "repr(exc)": repr(exc),
        'f"{exc}"': f"{exc}",
        'f"{exc!r}"': f"{exc!r}",
        "type(exc).__name__": type(exc).__name__,
        "exc.__cause__/__context__ chain": " | ".join(str(e) for e in chain),
        "traceback.format_exception": "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        ),
    }


def _live_sinks(session, server=None) -> dict[str, str]:
    """The in-process carriers a ledger row (or a cockpit poll) is built from:
    the LOGS-band ring, the TX `last_sent` triple, the recent-history ring, and
    the WHOLE json-dumped `status` response -- swept as one blob rather than
    field by field, because a field-scoped absence assert only ever proves that
    one field is clean."""
    status = protocol.dispatch(session, "status", {}, server or _BareServer())
    return {
        "session.tail (LOGS band)": json.dumps(session.tail.snapshot()),
        "session.last_sent": json.dumps(
            [session.last_sent, session.last_sender, session.last_sent_secret]
        ),
        "session.history": json.dumps(session.history),
        "status verb (whole response)": json.dumps(status),
        "build_response (whole response)": json.dumps(protocol.build_response(session)),
    }


def _transcript_sinks(log_dir: Path) -> dict[str, str]:
    sinks = {}
    for path in _transcript_logs(log_dir):
        raw = path.read_bytes()
        sinks[f"transcript text {path.name}"] = raw.decode("utf-8", errors="replace")
        # A bytes-level check catches an escaped/partial form that a decoded
        # read could smooth over; `latin-1` is total, so nothing is dropped.
        sinks[f"transcript bytes {path.name}"] = raw.decode("latin-1")
    return sinks


def _on_disk_sinks(root: Path, sanctioned: Path) -> dict[str, str]:
    """Every byte this run left on disk under `root`, EXCEPT the one sanctioned
    home for a credential.

    The honest stand-in for the archived suite's replay-LEDGER sink: there is no
    ledger module in the reborn tree, so a name-scoped assertion would prove
    nothing about a sink that does not exist yet. Sweeping whatever the run
    actually wrote makes the same claim without the name -- and a ledger landing
    later is covered the day it first writes a file, with no edit here.
    """
    sanctioned = sanctioned.resolve()
    sinks = {}
    for path in sorted(Path(root).rglob("*")):
        if not path.is_file() or path.resolve() == sanctioned:
            continue
        try:
            sinks[f"on-disk {path.relative_to(root)}"] = path.read_bytes().decode("latin-1")
        except OSError:
            # An unreadable file is one this run could not have written a
            # secret into either (the chmod-000 scenario plants exactly one).
            continue
    return sinks


def _assert_absent(sinks: dict[str, str], needles=NEEDLES):
    for name, text in sinks.items():
        for needle in needles:
            assert needle not in text, f"credential material leaked into {name}"


def _assert_transcript_marker_fired(log_dir: Path, expected: int | None = None):
    """The non-vacuity bookend for every transcript assertion in this file: an
    absence alone cannot tell "properly redacted" from "this path never logged
    anything at all" -- a dead call site would pass just as silently.

    Counts **TX** redaction markers only (secret sends). RX markers are a
    separate PWO-111 choke and must not inflate the send-count pin.
    """
    body = "".join(p.read_text(encoding="utf-8", errors="replace") for p in _transcript_logs(log_dir))
    tx_count = sum(
        1
        for line in body.splitlines()
        if "secret input redacted" in line and "] TX" in line
    )
    if expected is None:
        assert tx_count >= 1, "no TX redaction marker fired -- the secret send never happened"
    else:
        assert tx_count == expected, f"expected {expected} TX redaction markers, got {tx_count}"


class _BareServer:
    """No `control_lock` / `watch_hub` -- `protocol.py`'s status branch reads
    both via `getattr(..., None)`, and `_driving_dispatch` treats a missing
    lock as unrestricted. Same convention as the identically-named local
    fixtures in `tests/test_attach_redaction.py` / `tests/test_transcript_tail.py`
    (separate classes in separate modules -- no cross-file coupling)."""


# ---------------------------------------------------------------------------
# a scripted server that starts AT the password gate
# ---------------------------------------------------------------------------


class _ScriptedTWGS:
    """A minimal single-connection scripted telnet server, local to this file.

    NOT a replacement for `tests/fake_twgs.py`. That harness scripts the whole
    6-screen cold-start arc, which is the right shape for proving the automaton
    -- and `tests/test_login.py` already does. Every scenario HERE begins at the
    password gate instead, because the pre-login prefix costs ~3.5s per test and
    exercises nothing this file proves. Starting mid-flow is legitimate rather
    than a shortcut: `run_login` is reactive (it re-classifies the CURRENT
    screen every iteration), which is precisely what
    `tests/test_login_resume.py` proves.

    A step is `(send, read)`: `send` is the screen text (or a callable handed
    the last line read, for the echo scenario), `read` says whether to consume a
    CRLF-terminated reply before moving on. Screens carry the same leading
    `ESC[2J ESC[H` a real TWGS door's redraw discipline provides -- without it
    pyte accumulates every screen forever and stale scrollback re-matches the
    automaton's nuisance regexes (both failure shapes are documented at
    `fake_twgs.py`'s own `_send`).
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
            return
        self._conn = conn
        buf = bytearray()
        last = ""
        try:
            for send, read in self._script:
                text = send(last) if callable(send) else send
                if text is not None:
                    conn.sendall(("\x1b[2J\x1b[H" + text).encode("cp437", errors="replace"))
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


_PASSWORD_SCREEN = "Password?"
_MAIN_COMMAND_SCREEN = "Command [TL=00:00:00]:[24146] (?=Help)? :"
_CHAR_CREATE_SCREEN = (
    "You were not found in the player database.\r\n"
    "Would you like to start a new character in this game?  (Type Y or N)"
)


@contextlib.contextmanager
def _session_against(port: int, log_dir: Path):
    """A real `Session` over a real loopback socket -- no mocked session."""
    session = Session("127.0.0.1", port, PROFILE, str(log_dir))
    session.start(timeout=10)
    try:
        yield session
    finally:
        session.close()


def _profile(**kw) -> login.LoginProfile:
    kw.setdefault("name", PROFILE)
    kw.setdefault("handle", HANDLE)
    kw.setdefault("game_letter", GAME_LETTER)
    return login.LoginProfile(**kw)


def _run(session, *, get_password=None, save_password=None, allow_register=False, **kw):
    """Drive the REAL `run_login` with the REAL live wiring by default --
    `credentials.get_password` (env-first, then the chmod-600 store) and
    `protocol._save_password`, exactly what `protocol._dispatch_ensure` and
    `daemon.main()` inject. A scenario that needs to observe or perturb one of
    them passes its own."""
    return login.run_login(
        session,
        _profile(allow_register=allow_register, **kw),
        get_password=get_password or credentials.get_password,
        save_password=save_password or protocol._save_password,
    )


# ---------------------------------------------------------------------------
# 1. the green control -- the full cold-start arc, real store, every sink
# ---------------------------------------------------------------------------


def test_successful_returning_login_keeps_the_credential_out_of_every_sink(cfg, tmp_path):
    """The positive control the failure sweeps below are measured against: the
    whole 6-screen cold-start arc through `tests/fake_twgs.py`, resolving the
    sentinel out of a REAL chmod-600 `secrets.json` via the REAL
    `credentials.get_password` -- not an injected closure."""
    store = _write_secrets(cfg, text=_good_secrets_text())
    fake = FakeTWGS(handle=HANDLE, game_letter=GAME_LETTER, password=SENTINEL, mode="returning")
    logs = tmp_path / "logs"

    with fake, _session_against(fake.port, logs) as session:
        cls, steps = _run(session)
        sinks = {
            "run_login return value": json.dumps([cls, steps]),
            **_live_sinks(session),
        }
        session.logger.close()
        sinks.update(_transcript_sinks(logs))
        sinks.update(_on_disk_sinks(tmp_path, store))

    assert not fake.errors, fake.errors
    assert cls == "main_command"
    # Non-vacuity: the credential really did travel, so every absence below is
    # about a sink that had something to redact.
    assert fake.received_passwords == [SENTINEL]
    assert store.read_text(encoding="utf-8").count(SENTINEL) == 1
    _assert_absent(sinks)
    _assert_transcript_marker_fired(logs, expected=1)
    # The secret decision the LOGS-band ring consumed (and that any future
    # ledger row would read back) really was live for this send -- so the
    # redacted `last_sent` above is redaction, not an unset default.
    assert session.last_sent == "<redacted>"
    assert session.last_sent_secret is True
    for path in _transcript_logs(logs):
        assert _grep_a_contains(path, SENTINEL) is False


# ---------------------------------------------------------------------------
# 2. FAILURE -- the returning-flow rejection path
# ---------------------------------------------------------------------------


def test_rejected_password_keeps_the_credential_out_of_every_sink(cfg, tmp_path, monkeypatch):
    """The server re-presents the SAME password gate after the single send --
    canon's fail-fast, send-once rejection signal (`login-automaton.md`). The
    automaton raises `returning_password_rejected` having sent the credential
    exactly once, and none of the four sinks may carry it.

    `_RETURNING_REJECT_SETTLE_S` is shortened from 2.5s to 0.3s: it is a
    settle-grace BUDGET, not the behavior under test (the rejection still
    requires the full `_STAGNANT_ROUNDS_LIMIT` rounds, and
    `tests/test_login.py::test_wrong_saved_password_fails_fast_never_reaches_main_command`
    pins the real timing against the real fake server)."""
    monkeypatch.setattr(login, "_RETURNING_REJECT_SETTLE_S", 0.3)
    store = _write_secrets(cfg, text=_good_secrets_text())
    script = [(_PASSWORD_SCREEN, True), (_PASSWORD_SCREEN, False)]
    logs = tmp_path / "logs"

    with _ScriptedTWGS(script) as server, _session_against(server.port, logs) as session:
        with pytest.raises(login.LoginError) as excinfo:
            _run(session)
        sinks = {
            **_exception_renderings(excinfo.value),
            **_live_sinks(session),
        }
        session.logger.close()
        sinks.update(_transcript_sinks(logs))
        sinks.update(_on_disk_sinks(tmp_path, store))

    assert not server.errors, server.errors
    assert "returning_password_rejected" in str(excinfo.value)
    assert server.received == [SENTINEL]  # sent exactly once -- and it DID travel
    _assert_absent(sinks)
    _assert_transcript_marker_fired(logs, expected=1)
    # Shell-level check on a FAILURE path too: credential must not appear even
    # under `grep -a`. RX frames at the password gate (and the post-secret
    # echo window) are now fully redacted markers (PWO-111), so we no longer
    # require ANSI bytes in the file as proof the RX path ran — the RX
    # redaction markers are that proof.
    for path in _transcript_logs(logs):
        raw = path.read_bytes()
        assert b"RX <<secret input redacted>>" in raw
        assert _grep_a_contains(path, SENTINEL) is False


# ---------------------------------------------------------------------------
# 3. FAILURE -- a store that was read fine, for a profile that has no entry
# ---------------------------------------------------------------------------


def test_no_saved_password_error_never_quotes_the_store_it_just_read(cfg, tmp_path):
    """`returning_no_saved_password` embeds the profile name and handle. The
    store WAS read successfully here and holds a sibling profile's credential,
    so this is the shape where an error built from "what I found in the file"
    would leak somebody else's password rather than the caller's."""
    store = _write_secrets(cfg, text=json.dumps({CANARY_KEY: {"password": CANARY_VALUE}}))
    logs = tmp_path / "logs"

    with _ScriptedTWGS([(_PASSWORD_SCREEN, False)]) as server, _session_against(
        server.port, logs
    ) as session:
        with pytest.raises(login.LoginError) as excinfo:
            _run(session)
        sinks = {**_exception_renderings(excinfo.value), **_live_sinks(session)}
        session.logger.close()
        sinks.update(_transcript_sinks(logs))
        sinks.update(_on_disk_sinks(tmp_path, store))

    assert "returning_no_saved_password" in str(excinfo.value)
    assert server.received == []  # nothing was ever sent -- there was nothing to send
    # Non-vacuity: the canary credential really is in the file that was read.
    assert CANARY_VALUE in store.read_text(encoding="utf-8")
    _assert_absent(sinks)


# ---------------------------------------------------------------------------
# 4-6. FAILURE -- the store itself fails, at the password gate
# ---------------------------------------------------------------------------


def _drive_store_failure(tmp_path, logs) -> tuple[BaseException, dict[str, str]]:
    """Drive `run_login` to the password gate against whatever store the caller
    planted, and return `(what escaped, every sink)`.

    Nothing is caught by type here, because "whatever escapes" IS the claim
    under test: `run_login`'s contract says it raises `LoginError`, and all
    three of these paths break that contract with the credential store's own
    exception -- two of which are not even an `OSError`, so no typed handler
    between here and the daemon's widest catch sees them. Each CALLER pins the
    exact type it expected immediately after, so an unrelated raise (a typo in
    this file, say) cannot slip through this net and be swept as clean.
    """
    with _ScriptedTWGS([(_PASSWORD_SCREEN, False)]) as server, _session_against(
        server.port, logs
    ) as session:
        with pytest.raises(BaseException) as excinfo:  # noqa: PT011 -- see the docstring
            _run(session)
        assert server.received == [], "the store failed before any send -- nothing may have gone out"
        sinks = {**_exception_renderings(excinfo.value), **_live_sinks(session)}
        session.logger.close()
        sinks.update(_transcript_sinks(logs))
    return excinfo.value, sinks


def test_malformed_secrets_file_never_renders_the_document_it_failed_to_parse(cfg, tmp_path):
    """A truncated `secrets.json`. `json.load` raises `JSONDecodeError`, whose
    `.doc` attribute holds the ENTIRE file -- every profile's credential, not
    just the one being logged in. The assertion is against the canary KEY and
    the canary VALUE as well as the sentinel, because a decoder message that
    quotes the document quotes whatever it was reading at the damage, which is
    not necessarily the profile the caller asked for.

    Post-WO-SECRETS-REPR-GET-PASSWORD-REHAB the escaping type is
    `credentials.SecretStoreUnreadable`, not the decoder's own exception; the
    `JSONDecodeError` that still owns the document is its `__cause__`."""
    store = _write_secrets(cfg, text=_malformed_secrets_text())
    logs = tmp_path / "logs"
    exc, sinks = _drive_store_failure(tmp_path, logs)
    sinks.update(_on_disk_sinks(tmp_path, store))

    assert isinstance(exc, credentials.SecretStoreUnreadable)
    assert exc.cause == credentials.CAUSE_CORRUPT
    # Non-vacuity, twice over: the underlying exception really is carrying the
    # document (so a renderer that reached through to it WOULD leak), and the
    # document really does contain all three needles.
    assert isinstance(exc.__cause__, json.JSONDecodeError)
    assert all(needle in exc.__cause__.doc for needle in NEEDLES)
    assert all(needle in store.read_text(encoding="utf-8") for needle in NEEDLES)
    _assert_absent(sinks)


def test_non_utf8_secrets_file_never_renders_the_document_it_failed_to_decode(cfg, tmp_path):
    """One 0xFF byte appended to a well-formed store. `credentials.get_password`
    opens with `encoding="utf-8"`, so this fails in the READ, as a
    `UnicodeDecodeError` -- neither an `OSError` nor a `JSONDecodeError`, i.e.
    it used to escape every typed handler between here and the daemon's widest
    catch. `.object` holds the entire file, and `repr()` renders it.

    This is the shape WO-SECRETS-REPR-GET-PASSWORD-REHAB closed:
    `get_password` now classifies it into a bounded
    `credentials.SecretStoreUnreadable`, which is why `repr()` is in the sweep
    above at all. The buffer-owning exception survives as `__cause__`, and the
    assertions below keep both halves visible."""
    store = _write_secrets(cfg, raw=_non_utf8_secrets_bytes())
    logs = tmp_path / "logs"
    exc, sinks = _drive_store_failure(tmp_path, logs)
    sinks.update(_on_disk_sinks(tmp_path, store))

    assert isinstance(exc, credentials.SecretStoreUnreadable)
    assert exc.cause == credentials.CAUSE_CORRUPT
    assert isinstance(exc.__cause__, UnicodeDecodeError)
    assert all(needle.encode() in exc.__cause__.object for needle in NEEDLES)
    _assert_absent(sinks)


@pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="root bypasses the 0000 mode, so the read would succeed and prove nothing",
)
def test_unreadable_secrets_file_never_renders_the_document_it_could_not_read(cfg, tmp_path):
    """Mode 0000 on the FILE, with the config directory left readable so the
    open is genuinely attempted.

    A bare `PermissionError` used to escape here -- an `OSError`, so unlike the
    two above it was caught by `guardian.py`'s typed
    `except (OSError, LoginError)`, which keeps `str(e)` on purpose and would
    therefore stash the store's absolute PATH into `last_reconnect_error`.
    Post-WO-SECRETS-REPR-GET-PASSWORD-REHAB the escaping type is
    `credentials.SecretStoreUnreadable`, which is NOT an `OSError`, so that
    typed branch no longer fires and guardian's broad catch records a bare
    `guardian_tick_error:SecretStoreUnreadable` instead -- a deliberate
    narrowing, not a lost message: the actionable reason is on the exception
    (`exc.reason`) and reaches the owner-only local log via the traceback.

    Neither shape ever carried file CONTENTS; the path's own disclosure is a
    separate, already-pinned concern
    (`tests/test_daemon_internal_error_typename.py`), and the wire test below
    re-proves it stays off the wire on this path too."""
    store = _write_secrets(cfg, text=_good_secrets_text())
    os.chmod(store, 0o000)
    logs = tmp_path / "logs"
    try:
        exc, sinks = _drive_store_failure(tmp_path, logs)
    finally:
        os.chmod(store, 0o600)
    sinks.update(_on_disk_sinks(tmp_path, store))

    assert isinstance(exc, credentials.SecretStoreUnreadable)
    assert exc.cause == credentials.CAUSE_DENIED
    assert not isinstance(exc, OSError), (
        "guardian's typed `except (OSError, LoginError)` keeps str(e) -- a "
        "secrets-store failure must not land there"
    )
    assert isinstance(exc.__cause__, PermissionError)
    assert all(needle in store.read_text(encoding="utf-8") for needle in NEEDLES)
    _assert_absent(sinks)


def test_an_undecodable_store_no_longer_reaches_the_caller_as_the_decoder_error(cfg):
    """CLOSED RECORD — this test previously pinned the hazard; it now pins the fix.

    What was measured here: the `UnicodeDecodeError` that escaped
    `credentials.get_password` rendered CLEAN through `str()` and through
    `traceback.format_exception()` -- which is why every sweep above passed and
    why nothing leaked on the daemon path -- but its `args[1]` IS the entire
    undecodable file, so `repr()` and `f"{exc!r}"` rendered every credential in
    the store verbatim, and the now-retired `menu/crawl_driver.py` wrote
    `repr(exc)` into a PERSISTED status file. The old docstring said "closing
    it should update THIS test"; WO-SECRETS-REPR-GET-PASSWORD-REHAB
    (DECISIONS §C) closed it.

    `get_password` now classifies the decoder failure into a bounded
    `credentials.SecretStoreUnreadable` carrying `_decoder_detail` (type name +
    integer offset), exactly as `credentials._load_toml_store` already did for
    the TOML side. Both renderings are clean, which is the whole claim.

    **The trap that made this subtle is kept visible.** The same store,
    malformed rather than undecodable, raises `JSONDecodeError`, whose `args` is
    only its message: `repr()` there was ALWAYS clean, while `.doc` still holds
    the whole file. The exposure depends on the error's SHAPE, not on the file --
    the same asymmetry `_load_toml_store` documents for `tomllib` (a duplicate
    TABLE quotes a key out of the document; a duplicate KEY quotes nothing). Both
    halves stay asserted so a future reader cannot check the cheap one and
    conclude "safe".

    The buffer-owning exception survives as `__cause__` and is asserted to still
    own the document -- that is what keeps every absence here non-vacuous, and
    the residual is stated in full in `tests/test_secrets_store_redaction.py`.
    """
    _write_secrets(cfg, raw=_non_utf8_secrets_bytes())
    with pytest.raises(credentials.SecretStoreUnreadable) as excinfo:
        credentials.get_password(PROFILE)

    exc = excinfo.value
    for needle in NEEDLES:
        assert needle not in str(exc)
        assert needle not in repr(exc), (
            "the decode error's buffer is back in a rendering the product "
            "performs -- now-retired crawl_driver.py used to persist repr(exc)"
        )
        assert needle not in f"{exc!r}"
        assert needle not in "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        # Non-vacuity: the document really is still one attribute away.
        assert needle.encode() in exc.__cause__.object
        assert needle in repr(exc.__cause__)

    # The half that never leaked through repr -- same store, different damage.
    _write_secrets(cfg, text=_malformed_secrets_text())
    with pytest.raises(credentials.SecretStoreUnreadable) as excinfo:
        credentials.get_password(PROFILE)

    malformed = excinfo.value
    for needle in NEEDLES:
        assert needle not in repr(malformed)
        assert needle not in repr(malformed.__cause__), (
            "repr is clean HERE -- do not generalize from it"
        )
        assert needle in malformed.__cause__.doc, (
            "...while the document is still on the underlying exception"
        )


# ---------------------------------------------------------------------------
# 7. FAILURE -- the send itself dies, mid-password
# ---------------------------------------------------------------------------


class _DeadSocket:
    """A socket double whose `sendall` always raises, having transmitted
    nothing. Same deterministic stand-in `tests/test_tx_record_honesty.py`
    uses for the real broken pipe it separately proves against a live peer --
    a genuine network failure would add nondeterminism without adding
    evidence."""

    def __init__(self):
        self.attempts = []

    def sendall(self, data):
        self.attempts.append(data)
        raise BrokenPipeError(32, "Broken pipe")

    # `Session.close()` reaches these during teardown; `TelnetConnection.close`
    # only guards OSError, so a double missing them raises AttributeError out
    # of the context manager and masks the result under test.
    def shutdown(self, how):
        pass

    def close(self):
        pass


def test_send_failure_during_the_password_step_keeps_the_credential_out_of_every_sink(cfg, tmp_path):
    """The failure path that made a sibling suite blind: every one of ITS tests
    drove a *successful* send, so a defect in the failure branch stayed green.

    The socket is killed at the exact moment the credential is about to go out
    -- from inside the `get_password` call, which `_decide` makes immediately
    before returning the send action. `connection.send_text` then writes its
    honest `TX-FAILED` record (`WO-AUDIT-TX-RECORD-HONESTY`) and re-raises, so
    an `OSError` -- not a `LoginError` -- escapes `run_login`. The failure
    record must be redacted exactly like a successful one: marker only, no
    payload, no byte count."""
    _write_secrets(cfg, text=_good_secrets_text())
    logs = tmp_path / "logs"
    dead = _DeadSocket()

    with _ScriptedTWGS([(_PASSWORD_SCREEN, False)]) as server, _session_against(
        server.port, logs
    ) as session:

        def kill_then_resolve(name):
            session.conn._sock = dead
            return credentials.get_password(name)

        with pytest.raises(OSError) as excinfo:
            _run(session, get_password=kill_then_resolve)
        sinks = {**_exception_renderings(excinfo.value), **_live_sinks(session)}
        session.logger.close()
        sinks.update(_transcript_sinks(logs))
        sinks.update(_on_disk_sinks(tmp_path, credentials.SECRETS_PATH))

    # Non-vacuity: the credential really was handed to the socket layer.
    assert dead.attempts and SENTINEL.encode() in dead.attempts[0]
    assert not isinstance(excinfo.value, login.LoginError)
    _assert_absent(sinks)
    body = "".join(p.read_text(encoding="utf-8", errors="replace") for p in _transcript_logs(logs))
    assert "TX-FAILED" in body and "secret input redacted" in body
    # No byte count on the failure record either -- a length is itself a leak
    # (doctrine, invariant 2). `log_redacted` takes no content parameter, so
    # this asserts the FAILED record went to that sink and not to `log_raw`.
    assert f"{len(SENTINEL) + 2} bytes" not in body


# ---------------------------------------------------------------------------
# 8-9. FAILURE -- the NEW branch: retry ceiling, and a save-side store failure
# ---------------------------------------------------------------------------


def test_new_branch_retry_exhaustion_keeps_the_credential_out_of_every_sink(cfg, tmp_path):
    """The NEW-registration branch's bounded "didn't match" re-TYPE budget,
    driven past its ceiling: the server keeps re-presenting the create/repeat
    password screen until `password_retries_exhausted` fires.

    The credential here is resolved from the real store (login.py's
    `get_password(...) or _fresh_password()`), so the sentinel -- not an
    unpredictable CSPRNG value -- is what is sent on all seven attempts and
    what every sink is swept for."""
    store = _write_secrets(cfg, text=_good_secrets_text())
    rounds = login._MAX_PASSWORD_RETRIES + 1
    script = [(_CHAR_CREATE_SCREEN, True)] + [
        ("Please enter a password for this game account.\r\nPassword?", True) for _ in range(rounds)
    ]
    logs = tmp_path / "logs"

    with _ScriptedTWGS(script) as server, _session_against(server.port, logs) as session:
        with pytest.raises(login.LoginError) as excinfo:
            _run(session, allow_register=True)
        sinks = {**_exception_renderings(excinfo.value), **_live_sinks(session)}
        session.logger.close()
        sinks.update(_transcript_sinks(logs))
        sinks.update(_on_disk_sinks(tmp_path, store))

    assert not server.errors, server.errors
    assert "password_retries_exhausted" in str(excinfo.value)
    assert server.received == ["Y"] + [SENTINEL] * login._MAX_PASSWORD_RETRIES
    _assert_absent(sinks)
    _assert_transcript_marker_fired(logs, expected=login._MAX_PASSWORD_RETRIES)


def test_malformed_store_on_the_SAVE_path_never_renders_the_document(cfg, tmp_path):
    """The other half of the store's exposure: `protocol._save_password` --
    the live writer `_dispatch_ensure` and `daemon.main()` inject -- reads the
    existing `secrets.json` with `json.load` before merging. A malformed store
    therefore raises on the WRITE side too, at a different call site from
    `get_password`, and on the NEW branch this happens BEFORE the first send
    (login.py saves the moment the value is chosen)."""
    store = _write_secrets(cfg, text=_malformed_secrets_text())
    logs = tmp_path / "logs"

    with _ScriptedTWGS([(_CHAR_CREATE_SCREEN, True), (_PASSWORD_SCREEN, False)]) as server, (
        _session_against(server.port, logs)
    ) as session:
        with pytest.raises(json.JSONDecodeError) as excinfo:
            # get_password is injected here ONLY to make the value under test a
            # known sentinel rather than a CSPRNG one; the failing call is the
            # real `protocol._save_password` on the real malformed file.
            _run(session, get_password=lambda name: SENTINEL, allow_register=True)
        sinks = {**_exception_renderings(excinfo.value), **_live_sinks(session)}
        session.logger.close()
        sinks.update(_transcript_sinks(logs))
        sinks.update(_on_disk_sinks(tmp_path, store))

    assert server.received == ["Y"], "the save failed before the credential could be sent"
    assert all(needle in excinfo.value.doc for needle in NEEDLES)
    _assert_absent(sinks)


def test_registration_refused_error_never_quotes_the_store_it_never_read(cfg, tmp_path):
    """`registration_not_permitted` -- the char_create hard gate, raised before
    a single byte goes out. The store is never even opened on this path, which
    is precisely why it is worth sweeping: an error built by a future edit that
    "helpfully" reported whether a credential exists would have to read it."""
    store = _write_secrets(cfg, text=_good_secrets_text())
    logs = tmp_path / "logs"

    with _ScriptedTWGS([(_CHAR_CREATE_SCREEN, False)]) as server, _session_against(
        server.port, logs
    ) as session:
        with pytest.raises(login.LoginError) as excinfo:
            _run(session, allow_register=False)
        sinks = {**_exception_renderings(excinfo.value), **_live_sinks(session)}
        session.logger.close()
        sinks.update(_transcript_sinks(logs))
        sinks.update(_on_disk_sinks(tmp_path, store))

    assert "registration_not_permitted" in str(excinfo.value)
    assert server.received == []  # not even the "Y"
    _assert_absent(sinks)


def test_unconfirmed_password_sends_keep_the_credential_out_of_every_sink(cfg, tmp_path, monkeypatch):
    """`automaton_send_unconfirmed`: the credential goes out, and the resulting
    screen is never positively confirmed. Reachable only on the NEW branch --
    RETURNING sends once and never re-sends, so its repeat lands on the
    rejection path instead -- and it is the one error text carrying the SETTLE
    layer's own `reason` alongside the classification and prompt.

    Four secret sends, none confirmed, every one of which must still be
    redacted: this is the shape where a "diagnostics on the unhappy path"
    instinct would be most tempting. `_STEP_SETTLE_TIMEOUT_S` is shortened
    because an unconfirmed send costs the FULL settle budget by definition."""
    monkeypatch.setattr(login, "_STEP_SETTLE_TIMEOUT_S", 0.6)
    store = _write_secrets(cfg, text=_good_secrets_text())
    # The server answers char_create, presents the password prompt ONCE, then
    # goes silent -- reading each re-send without ever painting a new screen,
    # so no send can be confirmed.
    script = [(_CHAR_CREATE_SCREEN, True), (_PASSWORD_SCREEN, True)] + [(None, True)] * 3
    logs = tmp_path / "logs"

    with _ScriptedTWGS(script) as server, _session_against(server.port, logs) as session:
        with pytest.raises(login.LoginError) as excinfo:
            _run(session, allow_register=True)
        sinks = {**_exception_renderings(excinfo.value), **_live_sinks(session)}
        session.logger.close()
        sinks.update(_transcript_sinks(logs))
        sinks.update(_on_disk_sinks(tmp_path, store))

    assert "automaton_send_unconfirmed" in str(excinfo.value)
    assert server.received == ["Y"] + [SENTINEL] * 4
    _assert_absent(sinks)
    _assert_transcript_marker_fired(logs, expected=4)


# ---------------------------------------------------------------------------
# 10-11. FAILURE -- an unrecognized screen after the password step
# ---------------------------------------------------------------------------


def test_automaton_stuck_after_the_password_step_keeps_the_credential_out_of_every_sink(
    cfg, tmp_path, monkeypatch
):
    """`automaton_stuck` is the one `LoginError` that embeds server-controlled
    text verbatim: `f"automaton_stuck:classification={cls!r}:prompt={prompt!r}"`,
    which `_dispatch_ensure` folds straight into `resp["error"]`. Against a
    server behaving as canon assumes (a password prompt suppresses echo), that
    text is credential-free -- proven here rather than reasoned about.

    `_STEP_SETTLE_TIMEOUT_S` is shortened because a silent server means each
    stagnation round waits out the FULL settle budget (12s x 3). It is a
    timing budget, not the behavior under test."""
    monkeypatch.setattr(login, "_STEP_SETTLE_TIMEOUT_S", 1.0)
    store = _write_secrets(cfg, text=_good_secrets_text())
    script = [(_PASSWORD_SCREEN, True), ("Some unrecognized post-login screen ###", False)]
    logs = tmp_path / "logs"

    with _ScriptedTWGS(script) as server, _session_against(server.port, logs) as session:
        with pytest.raises(login.LoginError) as excinfo:
            _run(session)
        sinks = {**_exception_renderings(excinfo.value), **_live_sinks(session)}
        session.logger.close()
        sinks.update(_transcript_sinks(logs))
        sinks.update(_on_disk_sinks(tmp_path, store))

    assert "automaton_stuck" in str(excinfo.value)
    assert server.received == [SENTINEL]
    _assert_absent(sinks)
    _assert_transcript_marker_fired(logs, expected=1)


def test_an_echoing_server_no_longer_reaches_the_login_error_text(
    cfg, tmp_path, monkeypatch
):
    """CLOSED GATE. This test was, until WO-MT-07-FIX, the opposite assertion --
    a HAZARD RECORD asserting ``SENTINEL in str(excinfo.value)``, with a message
    telling whoever closed the divergence to come here and update it. This is
    that update, and the direction of travel is the point: the leak was measured
    first and pinned positively, so closing it had to fail loudly.

    What IS closed (error text): the login automaton's own diagnostic string.
    `automaton_stuck` used to quote the observed prompt line verbatim, so on an
    echoing server the app made a fresh COPY of the credential into a diagnostic
    string and `_dispatch_ensure` folded it into `resp["error"]` -- the CLI's
    JSON. `login.LoginStalled` cannot carry screen text.

    What IS closed (PWO-111 RX transcript): after a ``secret=True`` password
    send, RX chunks (including echo without the word ``password``) route through
    ``log_redacted`` — same vocabulary as TX. The live pyte screen may still
    paint the echo (live-paint residual / Code Divergence #1 narrowed); that is
    deliberate and still asserted below as non-vacuity for the error-text claim.

    Deliberately NOT swept here: the live screen paint. That remains the human's
    own eyes on their own game. The ensure/CLI JSON surface is swept end-to-end
    in `tests/test_ensure_login_error_redaction.py`.
    """
    monkeypatch.setattr(login, "_STEP_SETTLE_TIMEOUT_S", 1.0)
    _write_secrets(cfg, text=_good_secrets_text())
    # Step 2 echoes back exactly what the client sent -- the one server
    # behavior that used to land the credential in the transcript.
    script = [(_PASSWORD_SCREEN, True), (lambda last: last, False)]
    logs = tmp_path / "logs"

    with _ScriptedTWGS(script) as server, _session_against(server.port, logs) as session:
        with pytest.raises(login.LoginError) as excinfo:
            _run(session)
        # Non-vacuity, captured while the session is still open: the credential
        # really is on the screen at the moment of the raise. Without this the
        # absence below would also pass on a run where the echo never happened.
        screen_text = session.render_text(session.render())
        session.logger.close()

    assert server.received == [SENTINEL]
    assert SENTINEL in screen_text, (
        "the server did not echo -- this test stopped measuring the hazard it "
        "was written for"
    )

    # Diagnosability survives the redaction: the operator is still told WHICH
    # failure and WHERE the automaton was. An absence that passed because the
    # error went silent would be a regression wearing a green tick.
    assert isinstance(excinfo.value, login.LoginStalled)
    assert "automaton_stuck" in str(excinfo.value)
    assert "classification='unknown'" in str(excinfo.value)

    # The closed carrier, swept across every rendering this codebase performs.
    for name, body in _exception_renderings(excinfo.value).items():
        assert SENTINEL not in body, f"the credential reached {name}"

    # TX + RX transcript redaction held (PWO-111): echo must not persist.
    body = "".join(p.read_text(encoding="utf-8", errors="replace") for p in _transcript_logs(logs))
    assert "secret input redacted" in body
    assert "RX" in body
    assert SENTINEL not in body
    assert SENTINEL.encode() not in b"".join(
        p.read_bytes() for p in _transcript_logs(logs)
    )


# ---------------------------------------------------------------------------
# 12. the wire -- a real daemon, a real unix socket, real store failures
# ---------------------------------------------------------------------------


class _Daemon:
    """A real `ThreadingUnixServer` + `CommandHandler` + run-dir error log,
    wired to a REAL telnet `Session` -- the same shape
    `tests/test_daemon_internal_error_typename.py` uses, differing only in that
    its session is real, because the claim here is about a real login driving a
    real credential store.

    Whether the store's exception reaches a client is a WIRE claim and cannot be
    proven by calling `dispatch()` directly: the handler's widest catch is the
    thing under test, and it lives one layer above `dispatch`."""

    def __init__(self, run_dir: Path, session):
        from tw2002_aiclient.session.control_lock import ControlLock
        from tw2002_aiclient.session.daemon import (
            CommandHandler,
            ThreadingUnixServer,
            _open_error_log,
        )

        self.run_dir = Path(run_dir)
        self.sock_path = str(self.run_dir / "s.sock")
        self.server = ThreadingUnixServer(self.sock_path, CommandHandler)
        self.server.session = session
        self.server.control_lock = ControlLock()
        self.server.watch_hub = None
        self.server.request_stop = lambda: None
        self.error_log = _open_error_log(self.run_dir)
        self.server.error_log = self.error_log
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self._thread.start()

    def request(self, verb, args, timeout=30.0):
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
        # The RAW frame too: disclosure is about every byte that crossed, not
        # just the field a narrower assert would have scoped to.
        return json.loads(buf.decode("utf-8")), buf.decode("utf-8")

    def log_text(self) -> str:
        from tw2002_aiclient.session.daemon import ERRLOG_NAME

        path = self.run_dir / ERRLOG_NAME
        return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self._thread.join(timeout=5)
        self.error_log.close()


@pytest.fixture
def run_dir():
    """A SHORT run-dir: pytest's `tmp_path` is long enough to blow AF_UNIX's
    ~104-byte address limit, which is why conftest's own fake daemon and the F5
    suite both use `mkdtemp`."""
    d = tempfile.mkdtemp(prefix="twd-login-redact-")
    try:
        yield Path(d)
    finally:
        shutil.rmtree(d, ignore_errors=True)


@pytest.mark.parametrize(
    "label, kind",
    [
        ("malformed", "malformed"),
        ("non-utf8", "non_utf8"),
        ("unreadable", "unreadable"),
    ],
)
def test_store_failures_never_reach_the_wire_or_the_local_error_log(
    cfg, tmp_path, run_dir, label, kind
):
    """End-to-end over a real AF_UNIX socket: `tw ensure` against a store that
    fails at the password gate. The escaping exception is neither a
    `LoginError` (so `_dispatch_ensure` does not catch it) nor an `OSError` in
    two of three cases, so it lands in `daemon.py`'s widest catch -- which puts
    the TYPE NAME on the wire and `traceback.format_exc()` in the owner-only
    local log.

    Both are swept. The local-log half is the load-bearing one: `format_exc()`
    is the only rendering on this path that COULD have carried the document,
    and the exception is provably carrying it (see the residual test above)."""
    if kind == "unreadable" and hasattr(os, "geteuid") and os.geteuid() == 0:
        pytest.skip("root bypasses the 0000 mode")

    if kind == "malformed":
        store = _write_secrets(cfg, text=_malformed_secrets_text())
    elif kind == "non_utf8":
        store = _write_secrets(cfg, raw=_non_utf8_secrets_bytes())
    else:
        store = _write_secrets(cfg, text=_good_secrets_text())
        os.chmod(store, 0o000)

    logs = tmp_path / "logs"
    try:
        with _ScriptedTWGS([(_PASSWORD_SCREEN, False)]) as server, _session_against(
            server.port, logs
        ) as session:
            (cfg / "profiles.toml").write_text(
                f'[{PROFILE}]\nhost = "127.0.0.1"\nport = {server.port}\n'
                f'game_letter = "{GAME_LETTER}"\nhandle = "{HANDLE}"\n',
                encoding="utf-8",
            )
            daemon = _Daemon(run_dir, session)
            try:
                resp, raw = daemon.request("ensure", {"profile": PROFILE})
                log_body = daemon.log_text()
            finally:
                daemon.stop()
            session.logger.close()
    finally:
        os.chmod(store, 0o600)

    assert resp["ok"] is False
    prefix, _, payload = resp["error"].partition(":")
    assert prefix == "internal_error"
    assert payload.isidentifier(), f"a message rode the wire, not a type name: {payload!r}"
    _assert_absent(
        {
            f"wire frame ({label})": raw,
            f"local error log ({label})": log_body,
            **_transcript_sinks(logs),
            **_on_disk_sinks(tmp_path, store),
        }
    )
    # Non-vacuity: the daemon really did handle a raise (the log has the frame
    # chain), and the store really does hold all three needles.
    assert "Traceback (most recent call last):" in log_body
    os.chmod(store, 0o600)
    # Bytes, not text: one of these three stores is deliberately not valid
    # UTF-8, which is the whole point of that parametrization.
    planted = store.read_bytes()
    assert all(needle.encode() in planted for needle in NEEDLES)


def test_a_rejected_password_never_reaches_the_wire(cfg, tmp_path, run_dir, monkeypatch):
    """The rejection path again, this time through the REAL `ensure` verb over
    a real socket. `_dispatch_ensure` catches `LoginError` and folds its text
    into `resp["error"] = f"login_failed:{e}"` -- a structured, expected answer
    rather than the widest catch, so this sweeps the shape an operator actually
    sees when a saved credential has gone stale."""
    monkeypatch.setattr(login, "_RETURNING_REJECT_SETTLE_S", 0.3)
    store = _write_secrets(cfg, text=_good_secrets_text())
    logs = tmp_path / "logs"

    with _ScriptedTWGS([(_PASSWORD_SCREEN, True), (_PASSWORD_SCREEN, False)]) as server, (
        _session_against(server.port, logs)
    ) as session:
        (cfg / "profiles.toml").write_text(
            f'[{PROFILE}]\nhost = "127.0.0.1"\nport = {server.port}\n'
            f'game_letter = "{GAME_LETTER}"\nhandle = "{HANDLE}"\n',
            encoding="utf-8",
        )
        daemon = _Daemon(run_dir, session)
        try:
            resp, raw = daemon.request("ensure", {"profile": PROFILE})
            log_body = daemon.log_text()
        finally:
            daemon.stop()
        session.logger.close()

    assert resp["ok"] is False
    assert "login_failed:returning_password_rejected" in resp["error"]
    assert server.received == [SENTINEL]  # it really was sent
    _assert_absent(
        {
            "wire frame": raw,
            "local error log": log_body,
            **_transcript_sinks(logs),
            **_on_disk_sinks(tmp_path, store),
        }
    )


# ---------------------------------------------------------------------------
# MANDATORY falsification -- inject the leak, in both directions
# ---------------------------------------------------------------------------


def _leaky_log_tx(self, channel, data, secret, exc):
    """`connection.py`'s `_log_tx` with the `if secret:` redaction choke
    removed -- the single branch every send on both channels and BOTH outcomes
    routes through. Patched in, never edited on disk; `monkeypatch` reverts at
    teardown. Does not arm the RX echo window (paired with `_leaky_log_rx`)."""
    if not self.logger:
        return
    from tw2002_aiclient.session.connection import _tx_direction

    self.logger.log_raw(_tx_direction(channel, exc), data)


def _leaky_log_rx(self, data):
    """`connection.py`'s `_log_rx` with the password-anchor / post-secret gate
    removed — so falsification can prove the TX leak without RX markers
    masking the "no redaction fired" assertion."""
    if not self.logger or not data:
        return
    self.logger.log_raw("RX", data)


def _drive_rejection(tmp_path, cfg):
    """The rejection scenario, reusable by both falsification directions."""
    _write_secrets(cfg, text=_good_secrets_text())
    logs = tmp_path / "logs"
    with _ScriptedTWGS([(_PASSWORD_SCREEN, True), (_PASSWORD_SCREEN, False)]) as server, (
        _session_against(server.port, logs)
    ) as session:
        with pytest.raises(login.LoginError):
            _run(session)
        session.logger.close()
    return logs, server


def test_falsification_removing_the_redaction_choke_leaks_on_the_FAILURE_path_RED(
    cfg, tmp_path, monkeypatch
):
    """The direction that matters most here. A sibling suite's falsification
    passed while the defect sat in the failure branch, because every test it
    ran drove a SUCCESSFUL send -- so this injects the defect and drives the
    scenario that FAILS: a rejected password, ending in `LoginError`.

    Without this, "the failure paths are clean" would rest on tests that have
    never been shown capable of going red at all."""
    monkeypatch.setattr(login, "_RETURNING_REJECT_SETTLE_S", 0.3)
    monkeypatch.setattr(TelnetConnection, "_log_tx", _leaky_log_tx)
    monkeypatch.setattr(TelnetConnection, "_log_rx", _leaky_log_rx)
    logs, server = _drive_rejection(tmp_path, cfg)

    body = "".join(p.read_text(encoding="utf-8", errors="replace") for p in _transcript_logs(logs))
    assert server.received == [SENTINEL]
    assert SENTINEL in body  # RED: the leak is caught by this file's own sweep shape
    assert "secret input redacted" not in body
    with pytest.raises(AssertionError):
        _assert_absent(_transcript_sinks(logs))


def test_falsification_the_same_failure_path_is_green_again_once_the_choke_is_restored(
    cfg, tmp_path, monkeypatch
):
    """Bookend to the RED test above, in the SAME module/process: with no
    patch, the identical rejection scenario is clean -- so the red result was
    caused by the injection, not by state a previous test left behind."""
    monkeypatch.setattr(login, "_RETURNING_REJECT_SETTLE_S", 0.3)
    logs, server = _drive_rejection(tmp_path, cfg)

    assert server.received == [SENTINEL]
    _assert_absent(_transcript_sinks(logs))
    _assert_transcript_marker_fired(logs, expected=1)


def test_falsification_removing_the_redaction_choke_leaks_on_the_SUCCESS_path_RED(
    cfg, tmp_path, monkeypatch
):
    """The same injection against the green control, so the falsification
    covers both the path that completes and the path that fails."""
    monkeypatch.setattr(TelnetConnection, "_log_tx", _leaky_log_tx)
    monkeypatch.setattr(TelnetConnection, "_log_rx", _leaky_log_rx)
    _write_secrets(cfg, text=_good_secrets_text())
    fake = FakeTWGS(handle=HANDLE, game_letter=GAME_LETTER, password=SENTINEL, mode="returning")
    logs = tmp_path / "logs"

    with fake, _session_against(fake.port, logs) as session:
        cls, _steps = _run(session)
        session.logger.close()

    assert cls == "main_command"  # the login still completes identically
    body = "".join(p.read_text(encoding="utf-8", errors="replace") for p in _transcript_logs(logs))
    assert SENTINEL in body
    assert "secret input redacted" not in body


def test_falsification_the_on_disk_sweep_can_actually_find_a_planted_credential(cfg, tmp_path):
    """The ledger-sink stand-in has to be shown capable of failing: a sweep that
    walks a tree and finds nothing proves nothing unless it would have found
    something. Plants the sentinel in an ordinary file under the run's own tmp
    root -- the shape a ledger row, a checkpoint, or a crash dump would take --
    and confirms the sweep goes red, while the sanctioned store carrying the
    same value stays exempt."""
    store = _write_secrets(cfg, text=_good_secrets_text())
    (tmp_path / "state").mkdir()
    (tmp_path / "state" / "ledger.jsonl").write_text(
        json.dumps({"input": SENTINEL, "prompt": "Password?"}) + "\n", encoding="utf-8"
    )

    with pytest.raises(AssertionError, match="ledger.jsonl"):
        _assert_absent(_on_disk_sinks(tmp_path, store))

    # ...and the sanctioned store, holding the very same value, is exempt --
    # otherwise every sweep in this file would be red for the wrong reason.
    (tmp_path / "state" / "ledger.jsonl").unlink()
    _assert_absent(_on_disk_sinks(tmp_path, store))
    assert SENTINEL in store.read_text(encoding="utf-8")
