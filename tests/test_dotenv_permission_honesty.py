"""WO-LOAD-DOTENV-PERMISSION-HONESTY — an unreadable `.env` is not an absent
`.env`, and neither one may reach the operator as a traceback.

``load_dotenv`` asked ``path.exists()`` and then ``read_text()``. That pair got
BOTH answers wrong, by two different doors:

* a ``chmod 000`` ``.env`` — ``exists()`` True, ``read_text()`` raised a bare
  ``PermissionError`` out of ``resolve_host_port``. ``daemon.main`` catches only
  ``env.EnvResolutionError``, so ``twd`` died at startup with a full traceback:
  the identical shape ``c263f16`` had just fixed one function over.
* a readable ``.env`` under an unreadable DIRECTORY — ``exists()`` answers
  False there, so the loader returned ``{}`` and startup reported "could not
  resolve the game server host", sending the operator to write a ``.env`` they
  already have.

The second one is the reason the fix is not "one more ``except``": ``exists()``
itself is the defect, exactly as ``credentials._load_toml_store`` documents for
the profile store. Opening and classifying is what holds absent and unreadable
apart.

Four layers, because each proves something the others cannot:

* **A — the daemon's startup path.** ``daemon.main`` driven for real against
  real ``chmod 000`` conditions. A traceback here is an exception escaping
  ``main`` rather than a ``SystemExit``, so the assertion is structural.
* **B — the loader's own contract.** Absent stays ``{}`` and silent; every
  other condition is a typed ``DotenvUnreadable`` naming what to fix.
* **C — the deferral policy**, both sides. An unreadable ``.env`` is loud iff
  resolution actually reached tier 3. A rule that only ever shouts, or only
  ever shrugs, would pass half of these and fail the other half.
* **D — the tripwires.** The properties that make the NEXT failure safe rather
  than this one fixed: subclass-catches, and the secrets boundary on the
  message.

Every ``chmod`` in this file lands inside pytest's ``tmp_path`` and is restored
in a ``finally``. The repo's own ``.env``/``config/``/``run/`` are never read,
written, or chmod-ed — an operator may be mid-session against them.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from tw2002_aiclient.session import credentials, daemon, env

# chmod-based denial proves nothing as root: the kernel lets root read a 000
# file, so the "denied" branch is never reached and the test passes for the
# wrong reason.
_needs_unprivileged = pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="root bypasses file permissions — the denial can't be provoked",
)

DOTENV_BODY = "TW2002_HOST=dotenv.example.test\nTW2002_PORT=2323\n"
PROFILE_BODY = '[default]\nhost = "profile.example.test"\nport = 4242\n'


@pytest.fixture
def env_home(tmp_path, monkeypatch):
    """An isolated repo-root stand-in: a `.env` this suite may chmod freely,
    an absent profile store, and every higher tier silenced.

    Silencing the higher tiers is load-bearing, not hygiene. ``resolve_host_port``
    consults `.env` before anything else but answers from tiers 1-2 first, so a
    stray ``TW2002_HOST`` on the machine running the suite would settle
    resolution before the tier under test mattered and the test would pass
    without ever exercising it.

    ``TW_RUN_DIR`` is redirected even though every ``daemon.main`` call here
    exits at resolution: if a regression ever let resolution SUCCEED, the run
    dir is where it would claim a pidfile, and that must not be a real ``run/``.
    Hosts are in the reserved ``.test`` TLD (RFC 2606, the convention
    ``conftest.resolve_fake_host_port`` uses), so the connect a regression would
    attempt cannot resolve, let alone reach a live server.
    """
    dotenv = tmp_path / ".env"
    dotenv.write_text(DOTENV_BODY, encoding="utf-8")
    monkeypatch.setattr(env, "DOTENV_PATH", dotenv)
    monkeypatch.setattr(credentials, "PROFILES_PATH", tmp_path / "config" / "profiles.toml")
    monkeypatch.delenv(env.HOST_VAR, raising=False)
    monkeypatch.delenv(env.PORT_VAR, raising=False)
    monkeypatch.setenv(env.RUN_DIR_VAR, str(tmp_path / "run"))
    try:
        yield dotenv
    finally:
        # Restore every mode this file clears, before pytest's own tmp cleanup,
        # so a `chmod 000` can never outlive its test.
        for target in (dotenv, tmp_path):
            try:
                target.chmod(0o755)
            except OSError:
                pass


def _twd_start(capsys, argv=None):
    """Run ``twd``'s entry point and report what the operator got: (code, err).

    Deliberately NOT wrapped in a bare ``except Exception``. An unhandled error
    inside ``main`` must fail the test by propagating out of it — that IS the
    defect being fenced off, and swallowing it here to assert on a string would
    test the wrong thing.
    """
    with pytest.raises(SystemExit) as caught:
        daemon.main(argv if argv is not None else [])
    return caught.value.code, capsys.readouterr().err


# ---------------------------------------------------------------------------
# Layer A — the daemon's own startup path.
# ---------------------------------------------------------------------------


@_needs_unprivileged
def test_unreadable_dotenv_is_a_line_not_a_traceback(env_home, capsys):
    """The headline defect: `chmod 000 .env` used to kill `twd` with a bare
    ``PermissionError`` traceback."""
    env_home.chmod(0o000)
    try:
        code, err = _twd_start(capsys)
    finally:
        env_home.chmod(0o644)
    assert code == 1
    assert "Traceback" not in err
    assert "PermissionError" not in err
    assert err.startswith("twd: ")
    # Actionable means: which file, why, and what to do instead.
    assert str(env_home) in err
    assert "Permission denied" in err
    assert env.HOST_VAR in err and env.PORT_VAR in err


@_needs_unprivileged
def test_dotenv_under_an_unreadable_directory_is_a_line_not_a_silence(tmp_path, monkeypatch, capsys):
    """The half ``exists()`` hid in the OTHER direction.

    The file is readable; the directory is not. ``exists()`` answers False, so
    the loader used to return ``{}`` and the operator was told to go set a
    variable their `.env` already declares. Nothing raised, nothing was logged,
    and the answer was wrong.
    """
    home = tmp_path / "home"
    home.mkdir()
    dotenv = home / ".env"
    dotenv.write_text(DOTENV_BODY, encoding="utf-8")
    monkeypatch.setattr(env, "DOTENV_PATH", dotenv)
    monkeypatch.setattr(credentials, "PROFILES_PATH", tmp_path / "config" / "profiles.toml")
    monkeypatch.delenv(env.HOST_VAR, raising=False)
    monkeypatch.delenv(env.PORT_VAR, raising=False)
    monkeypatch.setenv(env.RUN_DIR_VAR, str(tmp_path / "run"))

    home.chmod(0o000)
    try:
        code, err = _twd_start(capsys)
    finally:
        home.chmod(0o755)
    assert code == 1
    assert "Traceback" not in err
    # NOT the generic "nothing configured" message — that was the lie.
    assert "could not resolve the game server host" not in err
    # Names the directory to fix, not the file that is already fine.
    assert str(home) in err
    assert "containing directory" in err


def test_a_genuinely_absent_dotenv_still_says_could_not_resolve(env_home, capsys):
    """The control, and the whole point of keeping the two apart. Absence is
    routine — most runs have no `.env` — so it must still fall through to
    ``resolve_host_port``'s own "pass --host / set TW2002_HOST" message, not to
    the new loud branch. A handler that shouts on everything has only moved the
    collapse."""
    env_home.unlink()
    code, err = _twd_start(capsys)
    assert code == 1
    assert "Traceback" not in err
    assert "could not resolve the game server host" in err
    assert "the .env overlay could not be read" not in err


# ---------------------------------------------------------------------------
# Layer B — the loader's own contract.
# ---------------------------------------------------------------------------


def test_absent_dotenv_returns_empty_silently(tmp_path):
    assert env.load_dotenv(tmp_path / "nope.env") == {}


def test_a_dangling_symlink_counts_as_absent(tmp_path):
    """Its target does not exist, so no content went unread. ``open`` raises
    ENOENT, which is the same honest answer ``credentials._load_toml_store``
    gives for the same shape."""
    link = tmp_path / ".env"
    link.symlink_to(tmp_path / "no-such-target")
    assert env.load_dotenv(link) == {}


@_needs_unprivileged
def test_unreadable_file_raises_typed_denied(tmp_path):
    path = tmp_path / ".env"
    path.write_text(DOTENV_BODY, encoding="utf-8")
    path.chmod(0o000)
    try:
        with pytest.raises(env.DotenvUnreadable) as caught:
            env.load_dotenv(path)
    finally:
        path.chmod(0o644)
    assert caught.value.cause == credentials.CAUSE_DENIED
    assert caught.value.path == str(path)
    assert isinstance(caught.value.__cause__, PermissionError)


@_needs_unprivileged
def test_unreadable_directory_names_the_directory(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    path = home / ".env"
    path.write_text(DOTENV_BODY, encoding="utf-8")
    home.chmod(0o000)
    try:
        with pytest.raises(env.DotenvUnreadable) as caught:
            env.load_dotenv(path)
    finally:
        home.chmod(0o755)
    assert caught.value.cause == credentials.CAUSE_DENIED
    assert str(home) in str(caught.value)


def test_a_directory_named_dotenv_is_unusable_not_absent(tmp_path):
    """``exists()`` answers True and ``read_text()`` raised ``IsADirectoryError``
    — a third bare traceback out of the same two lines."""
    path = tmp_path / ".env"
    path.mkdir()
    with pytest.raises(env.DotenvUnreadable) as caught:
        env.load_dotenv(path)
    assert caught.value.cause == credentials.CAUSE_UNUSABLE
    assert isinstance(caught.value.__cause__, OSError)


def test_non_utf8_dotenv_is_corrupt_not_absent(tmp_path):
    """``UnicodeDecodeError`` is a ``ValueError``, not an ``OSError`` — it left
    this function by a different door than the ``PermissionError`` did, and it
    was just as uncaught."""
    path = tmp_path / ".env"
    path.write_bytes(b"TW2002_HOST=a.example.test\n\xff\xfe\n")
    with pytest.raises(env.DotenvUnreadable) as caught:
        env.load_dotenv(path)
    assert caught.value.cause == credentials.CAUSE_CORRUPT
    assert "not valid UTF-8" in str(caught.value)


def test_a_readable_dotenv_is_untouched_by_all_of_this(tmp_path, monkeypatch):
    """The load path itself did not change: same parse, same return, same
    `os.environ` application."""
    monkeypatch.delenv(env.HOST_VAR, raising=False)
    monkeypatch.delenv(env.PORT_VAR, raising=False)
    path = tmp_path / ".env"
    path.write_text('# c\n\nTW2002_HOST="a.example.test"\nTW2002_PORT=23\n', encoding="utf-8")
    assert env.load_dotenv(path) == {"TW2002_HOST": "a.example.test", "TW2002_PORT": "23"}
    assert os.environ[env.HOST_VAR] == "a.example.test"


# ---------------------------------------------------------------------------
# Layer C — the deferral policy, both sides.
# ---------------------------------------------------------------------------


@pytest.fixture
def unreadable_dotenv(tmp_path, monkeypatch):
    """A `chmod 000` `.env` plus an isolated, ABSENT profile store — so any
    loudness observed below comes from the dotenv rule and not from tier 4
    having nothing to say."""
    path = tmp_path / ".env"
    path.write_text(DOTENV_BODY, encoding="utf-8")
    monkeypatch.delenv(env.HOST_VAR, raising=False)
    monkeypatch.delenv(env.PORT_VAR, raising=False)
    path.chmod(0o000)
    try:
        yield path
    finally:
        try:
            path.chmod(0o644)
        except OSError:
            pass


@_needs_unprivileged
def test_cli_host_and_port_resolve_despite_an_unreadable_dotenv(unreadable_dotenv, tmp_path):
    """Tier 1 outranks `.env`, so the unread file could not have changed this
    answer — and a startup that needed nothing from it must not die over it.
    This is the escape hatch that keeps a root-owned leftover `.env` from
    bricking the daemon."""
    host, port = env.resolve_host_port(
        cli_host="cli.example.test",
        cli_port=99,
        dotenv_path=unreadable_dotenv,
        profiles_path=tmp_path / "nope.toml",
    )
    assert (host, port) == ("cli.example.test", 99)


@_needs_unprivileged
def test_process_env_resolves_despite_an_unreadable_dotenv(unreadable_dotenv, tmp_path, monkeypatch):
    """Tier 2, same reasoning — and the second documented escape hatch."""
    monkeypatch.setenv(env.HOST_VAR, "envvar.example.test")
    monkeypatch.setenv(env.PORT_VAR, "2002")
    host, port = env.resolve_host_port(
        dotenv_path=unreadable_dotenv, profiles_path=tmp_path / "nope.toml"
    )
    assert (host, port) == ("envvar.example.test", 2002)


@_needs_unprivileged
def test_a_half_override_is_still_loud(unreadable_dotenv, tmp_path, monkeypatch):
    """`--host` alone does NOT settle resolution: port is still open, and the
    unread file is exactly what would have supplied it. Silence here would be
    the same wrong-answer risk as no override at all."""
    with pytest.raises(env.EnvResolutionError) as caught:
        env.resolve_host_port(
            cli_host="cli.example.test",
            dotenv_path=unreadable_dotenv,
            profiles_path=tmp_path / "nope.toml",
        )
    assert "the .env overlay could not be read" in str(caught.value)


@_needs_unprivileged
def test_an_unreadable_dotenv_does_not_silently_fall_through_to_the_profile(
    unreadable_dotenv, tmp_path, monkeypatch
):
    """The wrong-answer case, stated as a test.

    `profiles.toml` here resolves perfectly — and answering from it would mean
    connecting to ``profile.example.test`` while the operator's own `.env`,
    which OUTRANKS it, names a different server. For a game with persistent
    per-server character state that is a real wrong answer, not a cosmetic one.
    So tier 4 is not consulted at all.
    """
    profiles = tmp_path / "profiles.toml"
    profiles.write_text(PROFILE_BODY, encoding="utf-8")
    with pytest.raises(env.EnvResolutionError) as caught:
        env.resolve_host_port(dotenv_path=unreadable_dotenv, profiles_path=profiles)
    message = str(caught.value)
    assert "the .env overlay could not be read" in message
    assert "profile.example.test" not in message


def test_the_absent_dotenv_path_still_reaches_the_profile(tmp_path, monkeypatch):
    """The two-sided control for the test above: with no `.env` at all, tier 4
    is consulted exactly as it always was. The new branch must be reachable
    only via a real read failure."""
    monkeypatch.delenv(env.HOST_VAR, raising=False)
    monkeypatch.delenv(env.PORT_VAR, raising=False)
    profiles = tmp_path / "profiles.toml"
    profiles.write_text(PROFILE_BODY, encoding="utf-8")
    host, port = env.resolve_host_port(
        dotenv_path=tmp_path / "nope.env", profiles_path=profiles
    )
    assert (host, port) == ("profile.example.test", 4242)


@_needs_unprivileged
def test_a_bad_port_var_still_wins_over_the_dotenv_report(unreadable_dotenv, tmp_path, monkeypatch):
    """Tier 2 is more specific and outranks: an operator who set
    ``TW2002_PORT=abc`` needs to hear about THAT, not about `.env`."""
    monkeypatch.setenv(env.PORT_VAR, "abc")
    with pytest.raises(env.EnvResolutionError) as caught:
        env.resolve_host_port(
            dotenv_path=unreadable_dotenv, profiles_path=tmp_path / "nope.toml"
        )
    assert env.PORT_VAR in str(caught.value)
    assert "the .env overlay could not be read" not in str(caught.value)


# ---------------------------------------------------------------------------
# Layer D — the tripwires.
# ---------------------------------------------------------------------------


def test_dotenv_unreadable_is_an_env_resolution_error():
    """The fail-safe, pinned. ``daemon.main`` catches exactly
    ``EnvResolutionError``; this subclassing is the ONLY reason a
    ``DotenvUnreadable`` that escaped ``resolve_host_port``'s handler would
    still reach the operator as a line instead of a traceback."""
    assert issubclass(env.DotenvUnreadable, env.EnvResolutionError)


def test_a_future_dotenv_failure_subtype_is_still_a_line(env_home, monkeypatch, capsys):
    """Inject a failure type that did not exist when the handler was written.

    ``resolve_host_port`` catches ``DotenvUnreadable`` — the family BASE, not a
    list of causes — so a new subtype needs no edit to `env.py` to reach the
    operator as a line. Same property c263f16 bought for the profile-store
    family, proven the same way: by injection, not by reading the handler.
    """

    class DotenvFromTheFuture(env.DotenvUnreadable):
        pass

    def _raiser(path=None):
        raise DotenvFromTheFuture(credentials.CAUSE_DENIED, "invented", Path("/nonexistent/.env"))

    monkeypatch.setattr(env, "load_dotenv", _raiser)
    code, err = _twd_start(capsys)
    assert code == 1
    assert "Traceback" not in err
    assert err.startswith("twd: ")
    assert "the .env overlay could not be read" in err


def test_the_message_never_carries_file_content(tmp_path):
    """The secrets boundary, and the reason it is not optional here: a `.env`
    is exactly where a ``TW2002_PASSWORD_<PROFILE>`` value legitimately lives
    (env-first credentials). ``str(UnicodeDecodeError)`` quotes the offending
    bytes and ``exc.object`` holds the ENTIRE file, so a decode failure is the
    one path that could put a password on stderr."""
    path = tmp_path / ".env"
    path.write_bytes(b"TW2002_PASSWORD_DEFAULT=hunter2-not-a-real-secret\n\xff\xfe\n")
    with pytest.raises(env.DotenvUnreadable) as caught:
        env.load_dotenv(path)
    message = str(caught.value)
    assert "hunter2" not in message
    assert "TW2002_PASSWORD" not in message
    # What it IS allowed to say: a type name and an integer position.
    assert "UnicodeDecodeError" in message
    assert caught.value.reason.count("\n") == 0


def test_the_shared_decoder_renderer_still_exists():
    """`load_dotenv` reaches into ``credentials._decoder_detail`` so this
    codebase has ONE rendering of a decoder failure rather than two that can
    drift. It is private and ``credentials.py`` is the human-gated secrets lane,
    so it cannot be promoted to a public name from here — this pins the coupling
    instead, failing in a fast unit test rather than at a daemon start."""
    assert callable(getattr(credentials, "_decoder_detail", None))


def test_the_cause_vocabulary_is_the_shared_one():
    """Not a second dialect: the same three operator jobs keep the same three
    words they have in ``credentials`` and ``player_bank``."""
    assert {credentials.CAUSE_DENIED, credentials.CAUSE_UNUSABLE, credentials.CAUSE_CORRUPT} == {
        "denied",
        "unusable",
        "corrupt",
    }
