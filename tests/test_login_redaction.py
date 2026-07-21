"""Cipher security gate (2026-07-20): sentinel-password redaction proof
across the TW-02 `send_and_confirm` login/password swap (a2e99f6).

Background: a2e99f6 replaced login.py's password send from a bare
`session.send()` + idle-only `wait_settle()` to `settle.send_and_confirm`,
which adds a NEW behavior vs the old path -- a settle-confirm buffer
read-back after the send. This file proves a KNOWN SENTINEL password never
lands in cleartext in any of:
  (a) the session transcript log (twclient/logging_util.py)
  (b) the send_and_confirm confirm-echo buffer read (twclient/settle.py)
  (c) run_login's own return value / raised LoginError text (what
      protocol.py's `_dispatch_ensure` folds straight into the CLI's JSON
      response)
  (d) a replay-ledger `record_do` entry -- proven EMPIRICALLY, not just by
      reading source: drives the REAL `twclient.protocol.dispatch()` entry
      point (the actual `tw ensure` call graph) end-to-end with a REAL
      `twclient.ledger.LedgerWriter` wired to `server.ledger`, and confirms
      zero ledger entries are ever written for the login/password flow --
      `dispatch()`'s "ensure" branch (protocol.py:413-424) never calls
      `_record_ledger` at all, only "do"/"send"/replay/trainer do (grep
      confirms every `_record_ledger` call site; the empirical test proves
      it by spying on `_record_ledger` directly AND by checking the ledger
      file was never created). guardian.py's D9 reconnect-replay caller is
      likewise ledger-free and funnels through the exact same
      `run_login`/LoginError text this file proves sentinel-free (sink (c)).
      A dedicated falsification proves this check is a real signal: it CAN
      catch a leak, by simulating the hypothetical bug of ledgering a
      password send with the secret flag forgotten.

**Methodology note (hub feedback, 2026-07-20): plain shell `grep` on a
session transcript can be FALSE-CLEAN.** A transcript log can legitimately
contain NUL/control/ANSI bytes (real RX traffic does), and GNU/BSD grep's
standard `-I` flag (`--binary-files=without-match`: "treat a binary-
looking file as never matching") makes a single NUL byte before the
needle enough to silently report "no match" even when the needle IS
present -- confirmed deterministically (`test_demonstrates_plain_grep_
without_dash_a_is_a_false_negative_risk`): `grep -I -qF` exits 1
(false-clean) on such a file while `grep -a -qF` exits 0. This is not
hypothetical for this exact working environment either: Claude Code's own
Bash-tool `grep` resolves to a shell FUNCTION (confirmed via `type grep`
this session) that hardcodes `-I` on every invocation -- an operator who
naively ran `grep <sentinel> logs/session-*.log` INTERACTIVELY inside a
Claude Code session would be silently exposed to exactly this false
negative. Every log-content check in this file therefore either uses
Python-level `open(...).read()`/`open(..., "rb").read()` + `in` (a
`subprocess.run(...)` call, and Python's own string/bytes containment,
both bypass that shell function and any `-I`-style binary-skip heuristic
entirely) or explicit `grep -a` via `_grep_a_contains()` -- never a bare
interactive-shell `grep`.

`SentinelLoginSession` deliberately reuses the REAL
`twclient.connection.TelnetConnection.send_text` (the actual secret/
non-secret branch, connection.py:71-80) against a REAL
`twclient.logging_util.TranscriptLogger` writing to a real tmp file --
not a hand-mirrored approximation of that branch -- so the log-transcript
assertions below exercise production code, not just this test's own idea
of what it does.
"""

import subprocess

import pytest

from twclient import credentials, protocol
from twclient.connection import TelnetConnection
from twclient.ledger import LedgerWriter, read_entries
from twclient.login import LoginError, _decide, run_login
from twclient.logging_util import TranscriptLogger
from twclient.settle import wait_for_settle

from .conftest import FAKE_HOST, FAKE_PORT
from .test_login import FakeProfile, _is, _is_secret

SENTINEL = "S3NT1NEL_PW_xyz"


def _grep_a_contains(path, needle):
    """The non-vacuous shell-level absence/presence check: `grep -a`
    (force-text) + `-F` (fixed string, no regex-metachar surprises) +
    `-q` (exit-code only). See the module docstring's methodology note --
    a bare `grep` can silently miss a real match in a control-byte-laden
    transcript."""
    result = subprocess.run(["grep", "-a", "-q", "-F", needle, str(path)])
    return result.returncode == 0


class _StubSocket:
    """Discards every byte instead of touching a real network socket --
    TelnetConnection.send_text() only ever calls `.sendall()` on it."""

    def __init__(self):
        self.sent_bytes = []

    def sendall(self, data):
        self.sent_bytes.append(data)


class SentinelLoginSession:
    """`FakeLoginSession` (tests/test_login.py) with one change: `send()`
    routes through the REAL `TelnetConnection.send_text` against a REAL
    `TranscriptLogger`, instead of test_login.py's own bare
    `self.sent.append((text, secret))` bookkeeping. Also records every
    `render_text()` call's return value, so the settle-confirm buffer-read
    sink (send_and_confirm's own regex-match path in settle.py) can be
    grepped for the sentinel across the WHOLE run, not just reasoned about
    from source."""

    def __init__(self, steps, logger):
        self.t = 0.0
        self.rx_count = 0
        self.last_rx = 0.0
        self._steps = steps
        self._i = 0
        self.sent = []  # [(text, secret), ...] -- same bookkeeping shape as FakeLoginSession
        self._pending_advance = False
        self.last_sent = None
        self.render_text_calls = []
        self._conn = TelnetConnection(FAKE_HOST, FAKE_PORT, terminal=None, negotiator=None, logger=logger)
        self._conn._sock = _StubSocket()

    # -- settle-detection protocol surface (matches Session) -------------
    def clock(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds
        if self._pending_advance:
            self._pending_advance = False
            if self._i < len(self._steps) - 1:
                self._i += 1
            self.rx_count += 1
            self.last_rx = self.t

    def render(self):
        return self._steps[self._i]["screen"].split("\n")

    def render_text(self, rows=None):
        text = "\n".join(rows) if rows is not None else self._steps[self._i]["screen"]
        self.render_text_calls.append(text)
        return text

    def wait_settle(self, wait_prompt=None, timeout=8.0, debounce_ms=350):
        result = wait_for_settle(self, wait_prompt=wait_prompt, timeout_s=timeout, debounce_ms=debounce_ms)
        step = self._steps[self._i]
        if step.get("auto_advance") and self._i < len(self._steps) - 1:
            self._i += 1
            self.rx_count += 1
            self.last_rx = self.t
        return result

    # -- driving -----------------------------------------------------------
    def send(self, text, enter=True, secret=False):
        self.sent.append((text, secret))
        step = self._steps[self._i]
        if step.get("expect") is not None:
            assert step["expect"](text, secret), f"step {self._i}: unexpected send {text!r} secret={secret!r}"
        self._conn.send_text(text, enter=enter, secret=secret)  # REAL production code path
        self.last_sent = "<redacted>" if secret else text
        self._pending_advance = True


def _returning_login_steps(profile, password):
    """Byte-for-byte the RETURNING-login script test_login.py's own
    `test_returning_login_uses_saved_password_and_skips_registration`
    already proves (tests/test_login.py:463-473), parametrized by
    password value so this file can drive it with SENTINEL instead of a
    literal test string."""
    return [
        {"screen": "Please enter your name (ENTER for none):", "expect": _is("")},
        {"screen": "<F> Bob the Builder\nSelect a game :", "expect": _is(profile.game_letter)},
        {"screen": "T - Play Trade Wars 2002\nI - Introduction & Help\nEnter your choice:", "expect": _is("T")},
        {"screen": "What is your name?", "expect": _is(profile.handle)},
        {"screen": "Use ANSI graphics?", "expect": _is("Y")},
        {"screen": "Show today's log? (Y/N) [N]", "expect": _is("N")},
        # No char_create prompt at all -- the handle WAS found (RETURNING).
        {"screen": "Password?", "expect": _is_secret(password)},
        {"screen": f"Hello {profile.handle}, welcome to:", "expect": None, "auto_advance": True},
        {"screen": "Command [TL=00:00:00]:[24146] (?=Help)? :", "expect": None},
    ]


def _run_returning_login(tmp_path, password=SENTINEL, log_dir=None):
    logger = TranscriptLogger(str(log_dir or tmp_path))
    profile = FakeProfile()
    saved = {"default": password}
    session = SentinelLoginSession(_returning_login_steps(profile, password), logger)
    cls, taken = run_login(session, profile, get_password=lambda n: saved.get(n), save_password=lambda n, pw: None)
    logger.close()
    return session, logger, cls, taken


def _run_returning_login_with_realistic_rx_noise(tmp_path, password=SENTINEL):
    """Same as `_run_returning_login`, plus one extra REAL `log_raw("RX", ...)`
    call injecting a NUL pad byte + an ANSI cursor-reposition escape --
    a stand-in for the kind of post-login screen redraw a real TWGS server
    legitimately sends -- so the resulting transcript is NOT pure ASCII
    text, and a plain (non `-a`) `grep` absence-check would be unsafe
    against it (see module docstring's methodology note)."""
    logger = TranscriptLogger(str(tmp_path))
    profile = FakeProfile()
    saved = {"default": password}
    session = SentinelLoginSession(_returning_login_steps(profile, password), logger)
    cls, taken = run_login(session, profile, get_password=lambda n: saved.get(n), save_password=lambda n, pw: None)
    logger.log_raw("RX", b"\x1b[2J\x1b[H\x00Welcome back, trader!\r\n")
    logger.close()
    return session, logger, cls, taken


# -- (a) transcript log -----------------------------------------------------


def test_green_sentinel_absent_from_log_transcript_with_redaction_on(tmp_path):
    session, logger, cls, _taken = _run_returning_login(tmp_path)
    assert cls == "main_command"
    content = open(logger.path, encoding="utf-8").read()
    assert SENTINEL not in content
    # An "absence" assertion alone can't distinguish "properly redacted"
    # from "this code path never ran / never logged anything at all" (a
    # dead call site would pass just as silently) -- confirm log_redacted's
    # own marker actually fired.
    assert "secret input redacted" in content
    # Also never present as a repr/escaped form (e.g. inside a bytes repr
    # or partial-match fragment).
    assert SENTINEL.encode() not in open(logger.path, "rb").read()


# -- (b) settle-confirm buffer read -----------------------------------------


def test_green_sentinel_absent_from_settle_confirm_buffer_reads(tmp_path):
    session, _logger, cls, _taken = _run_returning_login(tmp_path)
    assert cls == "main_command"
    assert session.render_text_calls  # sanity: the run actually read screens
    for text in session.render_text_calls:
        assert SENTINEL not in text


def test_login_password_step_passes_no_confirm_prompt_to_send_and_confirm():
    """Point 4 of the gate, proven directly against the real `_decide`
    (not inferred from reading login.py:428-468): the login_password
    branch always returns `wait_hint=None`, so `send_and_confirm`'s ONLY
    `render_text()`-for-regex-matching branch (settle.py:208-246, gated on
    `confirm_prompt is not None`) is structurally never entered for a
    password send -- it can only ever confirm via the idle+stability path
    (settle.py:248-262), which never regex-matches or otherwise inspects
    render_text() content at all."""
    profile = FakeProfile()
    state = {"registering": False, "password": None, "password_attempts": 0, "bank_draw": False}
    send_text, secret, wait_hint = _decide(
        "login_password",
        "Password?",
        "Password?",
        profile,
        state,
        get_password=lambda n: SENTINEL,
        save_password=lambda n, pw: None,
        session=None,
    )
    assert send_text == SENTINEL
    assert secret is True
    assert wait_hint is None


# -- (c) run_login return value / raised error text -------------------------


def test_green_sentinel_absent_from_run_login_success_return_value(tmp_path):
    _session, _logger, cls, taken = _run_returning_login(tmp_path)
    assert SENTINEL not in cls
    assert SENTINEL not in str(taken)


def test_green_sentinel_absent_from_login_error_text_on_retry_exhaustion(tmp_path):
    """Forces `password_retries_exhausted` with the sentinel active as the
    RETURNING-branch saved credential, and checks the raised LoginError's
    own text -- this is exactly what `_dispatch_ensure` (protocol.py:941-
    945) folds verbatim into `resp["error"]`, the CLI's JSON response."""
    profile = FakeProfile()
    saved = {"default": SENTINEL}
    # RETURNING branch: password re-sent every step (server keeps re-asking,
    # e.g. a wrong/stale saved credential), never advancing past
    # login_password -- exhausts _MAX_PASSWORD_RETRIES (6).
    steps = [{"screen": "Password?", "expect": _is_secret(SENTINEL)}]
    logger = TranscriptLogger(str(tmp_path))
    session = SentinelLoginSession(steps, logger)
    with pytest.raises(LoginError) as excinfo:
        run_login(session, profile, get_password=lambda n: saved.get(n), save_password=lambda n, pw: None)
    logger.close()
    assert "password_retries_exhausted" in str(excinfo.value)
    assert SENTINEL not in str(excinfo.value)
    log_content = open(logger.path, encoding="utf-8").read()
    assert SENTINEL not in log_content


def test_green_sentinel_absent_from_automaton_stuck_error_text(tmp_path):
    """A DIFFERENT failure shape: the password send is confirmed, but the
    NEXT screen is never recognized (automaton_stuck) -- the resulting
    LoginError text embeds the CURRENT (unrecognized) screen's classification
    and prompt (login.py:222), not the password step's, but this proves
    that shape is sentinel-free too, in case a future unrecognized screen
    ever echoes something server-controlled back at this stage."""
    profile = FakeProfile()
    saved = {"default": SENTINEL}
    steps = [
        {"screen": "Password?", "expect": _is_secret(SENTINEL)},
        {"screen": "Some unrecognized post-login screen ###", "expect": None},
    ]
    logger = TranscriptLogger(str(tmp_path))
    session = SentinelLoginSession(steps, logger)
    with pytest.raises(LoginError) as excinfo:
        run_login(session, profile, get_password=lambda n: saved.get(n), save_password=lambda n, pw: None)
    logger.close()
    assert "automaton_stuck" in str(excinfo.value)
    assert SENTINEL not in str(excinfo.value)


# -- MANDATORY falsification: prove the green results above are a real signal ----


def test_falsification_bypassed_redaction_leaks_sentinel_into_log_RED(tmp_path, monkeypatch):
    """Temporarily patches `TelnetConnection.send_text` to take the
    `log_raw` branch UNCONDITIONALLY -- as if connection.py:76's
    `if secret:` redaction gate were removed/bypassed -- and confirms the
    SAME scenario that was green above now goes RED (the sentinel appears
    in the transcript log). A green test that can't be made to fail this
    way would prove nothing. `monkeypatch` reverts this automatically at
    teardown; twclient/connection.py is never edited on disk."""

    def _leaky_send_text(self, text, enter=True, secret=False):
        data = text.encode("utf-8", errors="replace")
        if enter:
            data += b"\r\n"
        self.logger.log_raw("TX", data)  # BUG (simulated): redaction gate removed
        self._sock.sendall(data)

    monkeypatch.setattr(TelnetConnection, "send_text", _leaky_send_text)

    session, logger, cls, _taken = _run_returning_login(tmp_path)
    assert cls == "main_command"  # the login itself still completes identically
    content = open(logger.path, encoding="utf-8").read()
    assert SENTINEL in content  # RED: the leak is caught by this same test shape
    # Confirm this is actually a *content* leak, not merely losing the
    # redaction marker -- the raw password text is present verbatim.
    secret_sends = [t for t, s in session.sent if s]
    assert secret_sends == [SENTINEL]
    assert SENTINEL in content


def test_falsification_confirms_default_send_text_still_redacts(tmp_path):
    """Sanity bookend to the RED test above: with NO monkeypatch, the
    identical scenario is green again in the SAME test module/process --
    proving the RED result above was caused by the monkeypatch, not by
    process-wide state the previous test left behind."""
    session, logger, cls, _taken = _run_returning_login(tmp_path)
    assert cls == "main_command"
    content = open(logger.path, encoding="utf-8").read()
    assert SENTINEL not in content
    assert "secret input redacted" in content


# -- (a) transcript log, non-vacuous shell-level check (hub feedback) -------


def test_demonstrates_plain_grep_without_dash_a_is_a_false_negative_risk(tmp_path):
    """NOT a test of this project's code -- a grounding/documentation test
    proving the hub's methodology flag is real and concretely identifying
    its mechanism, so the `grep -a` usage below (and this module's
    docstring) is justified rather than cargo-culted.

    Root cause, confirmed against THIS session: Claude Code's own Bash
    tool resolves `grep` to a shell FUNCTION (`type grep`), not the system
    binary -- and that function hardcodes `-I` (`--binary-files=
    without-match`, i.e. GNU/BSD grep's standard "treat a binary-looking
    file as never matching" flag) on every invocation. A `subprocess.run`
    call from Python (as `_grep_a_contains` uses, and as this test uses
    below) bypasses that shell function entirely and calls the real `grep`
    binary directly -- but an operator who instead typed `grep <sentinel>
    logs/session-*.log` INTERACTIVELY inside a Claude Code Bash-tool
    session would silently be running with `-I` baked in, and would miss
    a real leak in any transcript containing a NUL/control byte (a
    realistic occurrence -- see `_run_returning_login_with_realistic_rx_noise`).

    Reproduced directly with the real `-I` flag (deterministic and
    portable -- no dependency on any particular shell's function
    definitions, ugrep vs GNU grep, or this specific host): a single NUL
    byte ahead of the needle is enough to make `grep -I -qF` report "no
    match" (returncode != 0) even though the needle IS present, while
    `grep -a -qF` correctly reports a match (returncode == 0)."""
    p = tmp_path / "synthetic_binary.log"
    p.write_bytes(b"[RX]\x00" + SENTINEL.encode() + b"\r\n")

    ignore_binary = subprocess.run(["grep", "-I", "-q", "-F", SENTINEL, str(p)])
    forced_text = subprocess.run(["grep", "-a", "-q", "-F", SENTINEL, str(p)])

    assert ignore_binary.returncode != 0  # false-clean: misses a needle that IS there
    assert forced_text.returncode == 0  # -a correctly finds it
    assert _grep_a_contains(p, SENTINEL) is True  # this file's own helper agrees


def test_green_sentinel_absent_via_grep_a_non_vacuous_check(tmp_path):
    """The real login-redaction transcript, re-verified with the
    non-vacuous shell-level method (`grep -a -qF`) instead of (or in
    addition to) the Python-level `open(...).read()` + `in` checks used
    elsewhere in this file -- against a transcript deliberately made
    non-ASCII (a NUL pad byte + ANSI cursor-reposition escape injected via
    a REAL `log_raw("RX", ...)` call, standing in for a real post-login
    screen redraw) so this isn't a vacuous pass against an all-ASCII file
    that could never have tripped grep's binary-file heuristic either
    way."""
    session, logger, cls, _taken = _run_returning_login_with_realistic_rx_noise(tmp_path)
    assert cls == "main_command"
    raw = open(logger.path, "rb").read()
    assert b"\x00" in raw  # sanity: the file really does contain binary-ish noise
    assert _grep_a_contains(logger.path, SENTINEL) is False
    assert "secret input redacted" in raw.decode("utf-8", errors="replace")


# -- (d) replay-ledger `record_do` entry -- empirical proof ------------------


class _EnsureFakeConn:
    """Just enough of TelnetConnection's surface for `_dispatch_ensure`'s
    `session.conn.connected` check (protocol.py:919) -- mirrors
    conftest.py's own `_FakeConn`."""

    def __init__(self):
        self.connected = True


class _EnsureFakeServer:
    """Bare `server` double matching test_ensure_protocol.py's own
    `FakeServer` convention (no `.control_lock` -- `_driving_dispatch`
    treats that as unrestricted), plus a REAL `LedgerWriter` so this test
    can prove the ledger sink empirically instead of by reading source."""

    def __init__(self, ledger):
        self.ledger = ledger


class EnsureDispatchSentinelSession(SentinelLoginSession):
    """`SentinelLoginSession` plus the extra surface
    `protocol.dispatch()`/`build_response()`/`_dispatch_ensure()` need
    beyond `run_login`'s own settle-detection protocol (`.conn.connected`,
    `render_with_color()`, `cursor_pos()`, `record_history()`,
    `mark_profile()`) -- so the `ensure` verb can be driven through the
    REAL production `protocol.dispatch()` entry point end-to-end (the
    actual `tw ensure` call graph), not just `run_login` in isolation."""

    def __init__(self, steps, logger):
        super().__init__(steps, logger)
        self.host = FAKE_HOST
        self.port = FAKE_PORT
        self.name = None
        self.conn = _EnsureFakeConn()
        self.history = []
        self.auto_login_profile = None

    def render_with_color(self):
        return self.render(), []

    def cursor_pos(self):
        return {"x": 0, "y": 0}

    def record_history(self, verb, args, prompt, classification, settled_reason):
        self.history.append(
            {
                "verb": verb,
                "args": args,
                "prompt": prompt,
                "classification": classification,
                "settled_reason": settled_reason,
            }
        )

    def mark_profile(self, profile_name):
        self.auto_login_profile = profile_name


def test_green_sentinel_absent_from_ledger_across_real_dispatch_ensure(tmp_path, monkeypatch):
    """Empirical (not merely static) proof of sink (d): drives the REAL
    `twclient.protocol.dispatch()` entry point for the "ensure" verb --
    the actual production call graph a `tw ensure` CLI invocation goes
    through -- with a REAL `twclient.ledger.LedgerWriter` wired to
    `server.ledger`, and confirms zero ledger entries are EVER written for
    the login/password flow. Two independent checks: (1) the ledger file
    itself was never created at all (LedgerWriter.append() is the only
    thing that ever writes to it), and (2) a direct spy on
    `protocol._record_ledger` recorded zero calls."""
    profiles_path = tmp_path / "profiles.toml"
    profiles_path.write_text('[default]\nhost = "test.example"\nport = 2002\ngame_letter = "F"\nhandle = "AEGIS"\n')
    monkeypatch.setattr(credentials, "PROFILES_PATH", profiles_path)
    monkeypatch.setattr(credentials, "get_password", lambda name, secrets_path=None: SENTINEL)
    save_calls = []
    monkeypatch.setattr(
        credentials, "save_password", lambda name, pw, secrets_path=None: save_calls.append((name, pw))
    )

    record_ledger_calls = []
    real_record_ledger = protocol._record_ledger

    def _spy_record_ledger(*args, **kwargs):
        record_ledger_calls.append((args, kwargs))
        return real_record_ledger(*args, **kwargs)

    monkeypatch.setattr(protocol, "_record_ledger", _spy_record_ledger)

    profile_for_script = credentials.load_profile("default")  # sanity: real profile load works
    logger = TranscriptLogger(str(tmp_path / "logs"))
    session = EnsureDispatchSentinelSession(_returning_login_steps(profile_for_script, SENTINEL), logger)

    ledger_path = tmp_path / "state" / "ledger.jsonl"
    server = _EnsureFakeServer(ledger=LedgerWriter(path=ledger_path))

    resp = protocol.dispatch(session, "ensure", {"profile": "default"}, server)
    logger.close()

    assert resp["ok"] is True
    assert resp["classification"] == "main_command"
    assert record_ledger_calls == []  # (2): never called
    assert not ledger_path.exists()  # (1): nothing was ever appended -- file never created
    log_content = open(logger.path, encoding="utf-8").read()
    assert SENTINEL not in log_content


def test_ledger_record_do_redacts_secret_input_and_prompt(tmp_path):
    """Floor check on ledger.py's OWN redaction, independent of the
    "ensure never reaches it" finding above: if some OTHER verb
    (do/send/replay/trainer) ever legitimately ledgers a secret-flagged
    send, `record_do` redacts both `input` and `prompt` -- confirmed
    against the REAL `LedgerWriter`/`read_entries`, not by reading source."""
    ledger_path = tmp_path / "ledger.jsonl"
    writer = LedgerWriter(path=ledger_path)
    writer.record_do(
        pre_text="Password?",
        input_text=SENTINEL,
        secret=True,
        post_text="Command [TL=00:00:00]:[1] (?=Help)? :",
        settled_class="main_command",
    )
    entries = read_entries(path=ledger_path)
    assert len(entries) == 1
    assert entries[0]["input"] == "<redacted>"
    assert entries[0]["prompt"] == "<redacted>"
    raw = open(ledger_path, encoding="utf-8").read()
    assert SENTINEL not in raw
    assert _grep_a_contains(ledger_path, SENTINEL) is False


def test_falsification_ledger_would_leak_sentinel_if_secret_flag_forgotten_RED(tmp_path):
    """Falsification for the LEDGER sink specifically -- the one the hub
    flagged as most likely to be missed. Simulates the hypothetical bug of
    ledgering a password send WITHOUT the secret flag (`secret=False`) and
    confirms the ledger file/`read_entries()` WOULD actually surface the
    sentinel in that case -- proving the "ensure never reaches the ledger"
    finding and the redaction check above are real signals, not artifacts
    of a check that could never fail."""
    ledger_path = tmp_path / "ledger.jsonl"
    writer = LedgerWriter(path=ledger_path)
    writer.record_do(
        pre_text="Password?",
        input_text=SENTINEL,
        secret=False,  # BUG (simulated): secret flag forgotten/bypassed
        post_text="Command [TL=00:00:00]:[1] (?=Help)? :",
        settled_class="main_command",
    )
    entries = read_entries(path=ledger_path)
    assert entries[0]["input"] == SENTINEL  # RED: the leak is caught
    assert _grep_a_contains(ledger_path, SENTINEL) is True
