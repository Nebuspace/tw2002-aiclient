"""WO-AUDIT-CREDENTIALS-LAUNCHER-CRASH — the launcher's first read stops
crashing, and stops calling an unreachable config directory "no characters".

``app._load_profiles()`` is the first thing ``app._run`` does, before the
operator can press a key. It calls ``credentials.list_profile_summaries()``
unguarded, and that call had two different failure modes, both measured
against real files rather than a mocked ``open``:

* **it raised** — an unreadable ``profiles.toml``, a directory standing where
  it should be, a symlink loop, corrupt TOML, non-UTF-8 bytes, and every one
  of the same conditions on ``servers.toml`` (read first, through
  ``_catalog()``), plus a ``servers = 5`` that reached ``.items()`` and threw
  ``AttributeError``. A raise here is not an error message, it is a dead
  launcher.
* **it lied** — an unreadable *config directory* returned ``[]``, which the
  launcher draws as an empty picker with a lone "Create New Player" call to
  action: "you have no characters", said about a directory nobody could open.

Every condition below is driven for real — ``chmod 000`` on the file and on
the directory containing it, a real symlink loop, genuinely corrupt bytes,
genuinely non-UTF-8 bytes — because the defect being fenced off was precisely
that the *real* conditions arrived at the same two answers. A mock that raises
proves the handler; only the real condition proves the classification, and
only the real condition catches the ones that reach no handler at all
(``UnicodeDecodeError`` subclasses ``ValueError``, so neither the ``OSError``
family nor ``tomllib.TOMLDecodeError`` ever saw it).

The two-sided assertions matter as much as the positive ones. "This condition
is honest now" is not proven by a row appearing; it is proven by the row
appearing *and* the genuine negative still answering ``[]``, since a handler
that shouts on everything has only moved the collapse.

Isolation: ``TW_CONFIG_DIR`` + a real module reload — the sanctioned mechanism
per ``credentials``' own docstring — so the real ``config/`` tree is never
read, written, or chmod-ed.
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest

from tw2002_aiclient.session import credentials

from .pty_helpers import capture_pty, pty_curses_supported, pyte_grid

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# chmod-based denial proves nothing as root: the kernel lets root read a 000
# file, so the "denied" branch would never be reached and the test would pass
# for the wrong reason.
_needs_unprivileged = pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="root bypasses file permissions — the denial can't be provoked",
)
_PTY_SKIP = pytest.mark.skipif(
    not pty_curses_supported(),
    reason="no controlling-terminal/pty support — can't init curses in a pty subprocess",
)

GOOD_SERVERS = (
    '[servers.demo]\n'
    'name = "Demo Server"\n'
    'host = "demo.example.test"\n'
    'port = 2323\n'
)
GOOD_PROFILES = (
    '[alpha]\n'
    'server = "demo"\n'
    'game_letter = "A"\n'
    'handle = "AlphaPilot"\n'
)


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    """Point ``credentials`` at an isolated config dir and hand back the path.

    Same ``TW_CONFIG_DIR`` + ``importlib.reload`` idiom as
    ``test_profile_resolver.isolated_credentials``. Teardown restores every
    mode this test file may have cleared, before the reload and before
    pytest's own tmp cleanup, so a ``chmod 000`` can never outlive its test.
    """
    monkeypatch.setenv("TW_CONFIG_DIR", str(tmp_path))
    importlib.reload(credentials)
    assert credentials.CONFIG_DIR == tmp_path
    try:
        yield tmp_path
    finally:
        try:
            tmp_path.chmod(0o755)
            for child in tmp_path.iterdir():
                if not child.is_symlink():
                    child.chmod(0o644 if child.is_file() else 0o755)
        except OSError:
            pass
        monkeypatch.delenv("TW_CONFIG_DIR", raising=False)
        importlib.reload(credentials)


def _write(cfg_dir: Path, *, profiles=GOOD_PROFILES, servers=GOOD_SERVERS) -> None:
    if servers is not None:
        (cfg_dir / "servers.toml").write_text(servers, encoding="utf-8")
    if profiles is not None:
        (cfg_dir / "profiles.toml").write_text(profiles, encoding="utf-8")


def _launcher_rows():
    """The real launcher-startup call, not a stand-in.

    ``app._load_profiles()`` is what ``app._run`` calls to build the first
    screen; going through it rather than straight to ``credentials`` keeps
    these assertions about the path that actually died.
    """
    from tw2002_aiclient import app

    return app._load_profiles()


def _only_failure_row(rows):
    assert len(rows) == 1, f"expected exactly one diagnostic row, got {rows!r}"
    row = rows[0]
    assert row.error, "a store-failure row must carry an error or the launcher will launch it"
    return row


# ---------------------------------------------------------------------------
# The controls: what an honest empty answer looks like.
#
# These are the reason the fix is a classification and not a blanket "report
# something went wrong". If any of these started reporting a fault, the
# collapse would simply have moved: an operator with no characters yet would
# be told their config is broken.
# ---------------------------------------------------------------------------


def test_happy_path_is_unchanged(cfg):
    _write(cfg)
    rows = _launcher_rows()
    assert len(rows) == 1
    row = rows[0]
    assert (row.name, row.handle, row.game_letter) == ("alpha", "AlphaPilot", "A")
    assert row.host == "demo.example.test"  # resolved THROUGH the catalog
    assert row.error is None


def test_absent_profiles_file_is_still_an_honest_empty_list(cfg):
    _write(cfg, profiles=None)
    assert _launcher_rows() == []


def test_absent_config_dir_is_still_an_honest_empty_list(cfg, tmp_path, monkeypatch):
    monkeypatch.setenv("TW_CONFIG_DIR", str(tmp_path / "not-created-yet"))
    importlib.reload(credentials)
    assert _launcher_rows() == []


def test_empty_profiles_file_is_still_an_honest_empty_list(cfg):
    _write(cfg, profiles="")
    assert _launcher_rows() == []


def test_dangling_symlink_is_still_an_honest_empty_list(cfg):
    """Deliberately shares the answer with a file that was never written.

    Its target does not exist, so there is no store content that went
    unread — the same call ``player_bank._load_bank_raw`` makes, and the
    reason the symlink cases are split in two rather than lumped together
    (see the loop test below, which does NOT get this answer).
    """
    _write(cfg, profiles=None)
    (cfg / "profiles.toml").symlink_to(cfg / "never-written.toml")
    assert _launcher_rows() == []


@_needs_unprivileged
def test_a_search_only_config_dir_still_reads(cfg):
    """The other half of the directory proof.

    ``0o111`` is traversable but not listable, and the read succeeds — which
    is why the denial branch tests ``os.access(parent, X_OK)`` rather than
    assuming any awkward directory mode is the cause. If this ever starts
    reporting a fault, the "on the containing directory" hint has become a
    guess.
    """
    _write(cfg)
    cfg.chmod(0o111)
    try:
        rows = _launcher_rows()
    finally:
        cfg.chmod(0o755)
    assert len(rows) == 1 and rows[0].error is None


def test_top_level_scalars_stay_per_row_errors_not_a_store_failure(cfg):
    """Valid TOML of the wrong shape was ALREADY honest, per row.

    Pinned so the new whole-store failure path doesn't swallow it: these
    entries were read successfully, so they are named, and only the entries
    themselves are marked broken.
    """
    _write(cfg, profiles='alpha = 1\nbravo = "x"\n')
    rows = _launcher_rows()
    assert [r.name for r in rows] == ["alpha", "bravo"]
    assert all(r.error == "profile section is not a table" for r in rows)


# ---------------------------------------------------------------------------
# profiles.toml — the conditions that killed the launcher, or lied to it.
# ---------------------------------------------------------------------------


@_needs_unprivileged
def test_unreadable_profiles_file_survives_startup_and_reports_denied(cfg):
    """Accept #1. Pre-fix: ``PermissionError`` straight out of ``_load_profiles``."""
    _write(cfg)
    (cfg / "profiles.toml").chmod(0o000)
    try:
        row = _only_failure_row(_launcher_rows())
    finally:
        (cfg / "profiles.toml").chmod(0o644)

    assert row.name == "(profiles.toml)"
    assert row.error.startswith(f"{credentials.CAUSE_DENIED}: ")
    assert "Permission denied" in row.error
    # The file is readable-in-principle; only its mode is wrong. Sending the
    # operator to the directory here would waste their time.
    assert "containing directory" not in row.error


@_needs_unprivileged
def test_unreadable_config_dir_is_not_reported_as_having_no_profiles(cfg):
    """Accept #3 — the collapse, and the one that never even raised.

    ``Path.exists()`` answers ``False`` for a file under a directory it
    cannot traverse, so the old code returned ``[]`` and the launcher drew
    "no characters yet". The profile below exists the whole time.
    """
    _write(cfg)
    cfg.chmod(0o000)
    try:
        rows = _launcher_rows()
    finally:
        cfg.chmod(0o755)

    assert rows != [], "an unreachable config directory reported as 'no profiles'"
    row = _only_failure_row(rows)
    assert row.error.startswith(f"{credentials.CAUSE_DENIED}: ")
    # Naming the directory is the whole point: chmod-ing profiles.toml would
    # not fix this, and its mode is already fine.
    assert "on the containing directory" in row.error
    assert str(cfg) in row.error
    # Nothing was read, so nothing may be claimed about contents.
    assert "alpha" not in row.error and row.host == "?"


def test_a_directory_where_profiles_should_be_is_unusable_not_absent(cfg):
    _write(cfg, profiles=None)
    (cfg / "profiles.toml").mkdir()
    row = _only_failure_row(_launcher_rows())
    assert row.error.startswith(f"{credentials.CAUSE_UNUSABLE}: ")
    assert "Is a directory" in row.error


def test_a_symlink_loop_is_unusable_not_absent(cfg):
    """Splits from the dangling-symlink control above.

    ``Path.exists()`` answers ``False`` for both, which is exactly how they
    collapsed into one answer. A loop has no target that "was never
    written" — the path itself cannot be followed.
    """
    _write(cfg, profiles=None)
    (cfg / "profiles.toml").symlink_to(cfg / "profiles.toml")
    row = _only_failure_row(_launcher_rows())
    assert row.error.startswith(f"{credentials.CAUSE_UNUSABLE}: ")


def test_corrupt_profiles_toml_survives_startup(cfg):
    """Accept #2. Pre-fix: ``TOMLDecodeError`` straight out of ``_load_profiles``."""
    _write(cfg, profiles='[alpha\nserver = "demo"\n')
    row = _only_failure_row(_launcher_rows())
    assert row.error.startswith(f"{credentials.CAUSE_CORRUPT}: ")
    assert "not valid TOML" in row.error
    assert "TOMLDecodeError" in row.error


def test_non_utf8_profiles_toml_survives_startup(cfg):
    """The condition that reached no handler at all.

    ``UnicodeDecodeError`` subclasses ``ValueError``, not ``OSError``, and is
    a *different* ``ValueError`` subclass from the TOML decoder — so the
    resolver's ``except tomllib.TOMLDecodeError`` never saw it and it went
    all the way out through ``curses.wrapper``.
    """
    _write(cfg, profiles=None)
    (cfg / "profiles.toml").write_bytes(b'[alpha]\nhandle = "\xff\xfe"\n')
    row = _only_failure_row(_launcher_rows())
    assert row.error.startswith(f"{credentials.CAUSE_CORRUPT}: ")
    assert "not valid UTF-8" in row.error
    assert "UnicodeDecodeError" in row.error


# ---------------------------------------------------------------------------
# servers.toml — read FIRST, through _catalog(), and just as fatal.
# ---------------------------------------------------------------------------


def test_absent_servers_catalog_still_lists_profiles(cfg):
    """The control for the catalog axis: absent is a real negative.

    An absent catalog keeps the shipped fallback — the profile is listed and
    its ``server`` key stands in for the host — so the failure paths below
    are not just "any awkward catalog hides your characters".
    """
    _write(cfg, servers=None)
    rows = _launcher_rows()
    assert len(rows) == 1
    assert rows[0].name == "alpha" and rows[0].error is None


@_needs_unprivileged
def test_unreadable_servers_catalog_survives_startup(cfg):
    _write(cfg)
    (cfg / "servers.toml").chmod(0o000)
    try:
        row = _only_failure_row(_launcher_rows())
    finally:
        (cfg / "servers.toml").chmod(0o644)
    assert row.name == "(servers.toml)"
    assert row.error.startswith(f"{credentials.CAUSE_DENIED}: ")


def test_corrupt_servers_catalog_survives_startup(cfg):
    _write(cfg, servers="[servers.demo\n")
    row = _only_failure_row(_launcher_rows())
    assert row.name == "(servers.toml)"
    assert "not valid TOML" in row.error


def test_non_utf8_servers_catalog_survives_startup(cfg):
    _write(cfg, servers=None)
    (cfg / "servers.toml").write_bytes(b'[servers.demo]\nname = "\xff\xfe"\n')
    row = _only_failure_row(_launcher_rows())
    assert row.name == "(servers.toml)"
    assert "not valid UTF-8" in row.error


def test_a_directory_where_servers_should_be_survives_startup(cfg):
    _write(cfg, servers=None)
    (cfg / "servers.toml").mkdir()
    row = _only_failure_row(_launcher_rows())
    assert row.error.startswith(f"{credentials.CAUSE_UNUSABLE}: ")


def test_a_non_table_servers_key_survives_startup(cfg):
    """Pre-fix this was not even a decode failure: ``data.get("servers")``
    returned an ``int`` and the next line called ``.items()`` on it, so the
    launcher died with a bare ``AttributeError``."""
    _write(cfg, servers="servers = 5\n")
    row = _only_failure_row(_launcher_rows())
    assert row.error.startswith(f"{credentials.CAUSE_MALFORMED}: ")
    assert "expected a table" in row.error


# ---------------------------------------------------------------------------
# Content boundary — what an error message is allowed to carry.
#
# `profiles.toml` is not the secrets file, but it sits in the same config
# directory and the same lane, and a decoder is the one exception type that
# can quote the document it failed on.
# ---------------------------------------------------------------------------


def test_a_toml_error_message_never_quotes_the_document(cfg):
    """``tomllib`` lifts keys straight out of the file into its message.

    A duplicated table renders as ``Cannot declare ('canary_key',) twice``.
    That message used to be interpolated verbatim into ``ProfileMalformed``.
    The replacement is a type name plus integer coordinates, which locate the
    damage without quoting any of it.
    """
    _write(
        cfg,
        profiles='[canary_key]\nhandle = "canary-value"\n[canary_key]\nhandle = "x"\n',
    )
    row = _only_failure_row(_launcher_rows())

    assert "canary_key" not in row.error
    assert "canary-value" not in row.error
    assert "Cannot declare" not in row.error
    # Not merely silent: still locates the damage.
    assert "TOMLDecodeError at line" in row.error and "column" in row.error

    # Same boundary on the exception itself, which is what non-display
    # callers (env.py, cli.py, protocol.py) render.
    with pytest.raises(credentials.ProfileStoreMalformed) as caught:
        credentials.resolve_profile_host_port("canary_key")
    text = f"{caught.value} {caught.value.reason}"
    assert "canary_key" not in text.replace(str(cfg / "profiles.toml"), "")
    assert "canary-value" not in text


def test_a_decode_error_message_never_carries_the_file_bytes(cfg):
    """``UnicodeDecodeError`` keeps the WHOLE input on ``.object`` / ``args[1]``.

    ``str(exc)`` happens not to render it today; the point is that the
    message is built from the type name and an integer offset, so no future
    edit to the format string can reach the document.
    """
    _write(cfg, profiles=None)
    (cfg / "profiles.toml").write_bytes(
        b'[alpha]\nhandle = "canary-value-in-bytes"\nbad = "\xff\xfe"\n'
    )
    row = _only_failure_row(_launcher_rows())
    assert "canary-value-in-bytes" not in row.error
    assert "\\xff" not in row.error and "0xff" not in row.error
    assert "not valid UTF-8 (UnicodeDecodeError at byte" in row.error


def test_a_readable_profile_secret_shaped_value_never_reaches_a_row(cfg):
    """``profiles.toml`` structurally has no password field, but an operator
    can still type one into it. Nothing this listing emits carries an unknown
    key's value, on the happy path or the failure path."""
    _write(
        cfg,
        profiles=(
            '[alpha]\nserver = "demo"\ngame_letter = "A"\nhandle = "AlphaPilot"\n'
            'password = "canary-secret-value"\n'
        ),
    )
    rows = credentials.list_profile_summaries()
    assert "canary-secret-value" not in repr(rows)
    assert all("password" not in row for row in rows)


# ---------------------------------------------------------------------------
# The typed family — callers classify by TYPE, not by message text.
# ---------------------------------------------------------------------------


@_needs_unprivileged
def test_an_unreadable_store_is_not_reported_as_a_missing_profile(cfg):
    """The resolver's own version of the same lie.

    ``resolve_profile_host_port`` used to answer ``ProfileNotFound: <path>
    does not exist`` for a profiles.toml under an unreadable directory —
    which ``env.py`` classifies as "absent, fall through quietly". The file
    exists; the operator would have been told to create a profile they have.
    """
    _write(cfg)
    cfg.chmod(0o000)
    try:
        with pytest.raises(credentials.ProfileStoreUnreadable) as caught:
            credentials.resolve_profile_host_port("alpha")
        assert not isinstance(caught.value, credentials.ProfileNotFound)
    finally:
        cfg.chmod(0o755)
    assert caught.value.cause == credentials.CAUSE_DENIED
    assert "does not exist" not in str(caught.value)


def test_a_genuinely_absent_store_is_still_profile_not_found(cfg):
    """The control for the test above — the message and type are unchanged."""
    _write(cfg, profiles=None)
    with pytest.raises(credentials.ProfileNotFound) as caught:
        credentials.resolve_profile_host_port("alpha")
    assert "does not exist" in str(caught.value)


def test_the_two_store_failures_sit_in_different_places_in_the_family(cfg):
    """Both are ``ProfileConnectionError``, so ``cli.py`` / ``protocol.py``
    (which catch the base) inherit both. Only the content failure is a
    ``ProfileMalformed``.

    ``env.py`` used to branch on ``ProfileMalformed`` to decide between
    "nothing here, fall through" and "something is broken, say so", which is
    precisely why ``ProfileStoreUnreadable`` — correctly NOT a
    ``ProfileMalformed`` — escaped it as a startup traceback. It now
    enumerates the closed absent side and catches the base for the rest; the
    positions asserted below are what make that split legible, and
    ``tests/test_twd_profile_store_unreadable.py`` holds it.
    """
    assert issubclass(credentials.ProfileStoreUnreadable, credentials.ProfileConnectionError)
    assert issubclass(credentials.ProfileStoreMalformed, credentials.ProfileConnectionError)
    assert issubclass(credentials.ProfileStoreMalformed, credentials.ProfileMalformed)
    # An unreadable store is NOT malformed: nothing was read, so nothing can
    # be said about its content.
    assert not issubclass(credentials.ProfileStoreUnreadable, credentials.ProfileMalformed)


def test_corrupt_toml_still_classifies_as_malformed_for_env_py(cfg):
    """``env.py`` turns ``ProfileMalformed`` into an actionable
    ``EnvResolutionError`` and lets everything else fall through as "absent".
    Bad TOML must stay on the loud side of that branch."""
    from tw2002_aiclient.session import env

    _write(cfg, profiles="[alpha\n")
    with pytest.raises(env.EnvResolutionError):
        env._load_profile_host_port("alpha", profiles_path=cfg / "profiles.toml")


@_needs_unprivileged
def test_the_strict_and_display_halves_disagree_on_purpose(cfg):
    """The split exists because one caller renders its own failure and the
    other hands its result straight to a screen it cannot guard."""
    _write(cfg)
    (cfg / "profiles.toml").chmod(0o000)
    try:
        with pytest.raises(credentials.ProfileStoreUnreadable):
            credentials.load_profile_summaries()
        rows = credentials.list_profile_summaries()  # same condition, no raise
    finally:
        (cfg / "profiles.toml").chmod(0o644)
    assert len(rows) == 1 and rows[0]["error"]


@_needs_unprivileged
def test_the_bank_reports_an_unreadable_profile_store_instead_of_an_empty_bank(
    cfg, tmp_path, monkeypatch
):
    """The bank listing is built from two stores, so it inherits this one.

    ``list_players`` filters out rows carrying an error — a broken profile has
    no honest rotation columns — so the display half's diagnostic row would be
    dropped and the view would paint "(bank empty)". Taking the strict half
    keeps that from trading the launcher's lie for the bank's.
    """
    from tw2002_aiclient.session import player_bank

    _write(cfg)
    monkeypatch.setattr(player_bank, "BANK_PATH", tmp_path / "no-bank-here.json")
    (cfg / "profiles.toml").chmod(0o000)
    try:
        with pytest.raises(player_bank.BankUnreadable) as caught:
            player_bank.list_players()
    finally:
        (cfg / "profiles.toml").chmod(0o644)
    assert caught.value.cause == player_bank.CAUSE_DENIED
    assert caught.value.reason.startswith("profiles.toml: ")


# ---------------------------------------------------------------------------
# Layer B — the operator's actual screen.
#
# Accept #3 is a claim about what a human sees at startup, so it is proven
# where they see it: real curses in a real pty, driving the real ``app._run``
# launcher loop against a real config directory, replayed through pyte.
# ---------------------------------------------------------------------------

ROWS, COLS = 30, 160

_BOOTSTRAP = r"""
import os
import sys

for var in ("TW2002_LAUNCHER_SMOKE", "TW2002_HANDOFF_SMOKE", "TW2002_BANK_SMOKE",
            "TW2002_LAUNCHER_DEMO", "TW2002_LAUNCHER_FIXTURE"):
    os.environ.pop(var, None)
os.environ["TW_CONFIG_DIR"] = {config_dir!r}

sys.path.insert(0, {project_root!r})

import curses

from tw2002_aiclient import app

curses.wrapper(app._run)
"""


def _drive_launcher_pty(config_dir: Path, timeout: float = 12.0) -> str:
    script = _BOOTSTRAP.format(project_root=str(PROJECT_ROOT), config_dir=str(config_dir))
    captured = capture_pty(
        [sys.executable, "-c", script],
        # The footer is the last thing painted before refresh(), so once it is
        # on the wire the whole frame has been queued.
        lambda buf: b"q quit" in buf,
        timeout=timeout,
        rows=ROWS,
        cols=COLS,
    )
    return "\n".join(pyte_grid(captured, ROWS, COLS))


@_PTY_SKIP
def test_pty_a_real_empty_config_still_paints_the_cold_join_screen(tmp_path):
    """The control. A genuine negative keeps the bare "create one" screen."""
    (tmp_path / "servers.toml").write_text(GOOD_SERVERS, encoding="utf-8")
    grid = _drive_launcher_pty(tmp_path)
    assert "Create New Player" in grid
    assert "ERROR" not in grid


@_PTY_SKIP
@_needs_unprivileged
def test_pty_an_unreachable_config_dir_paints_a_fault_not_an_empty_picker(tmp_path):
    """Pre-fix this screen was byte-identical to the control above.

    Two-sided on purpose: the failure screen must GAIN the fault row, and the
    operator must not be left reading a picker that says their characters do
    not exist.
    """
    _write(tmp_path)
    tmp_path.chmod(0o000)
    try:
        grid = _drive_launcher_pty(tmp_path)
    finally:
        tmp_path.chmod(0o755)

    assert "ERROR" in grid
    assert "Permission denied" in grid
    assert "on the containing directory" in grid


@_PTY_SKIP
def test_pty_corrupt_toml_paints_a_fault_instead_of_killing_the_launcher(tmp_path):
    """Pre-fix the frame below did not exist: ``TOMLDecodeError`` escaped
    ``curses.wrapper`` before the first draw, so the operator got a traceback
    on a restored terminal, not a launcher."""
    _write(tmp_path, profiles='[alpha\nserver = "demo"\n')
    grid = _drive_launcher_pty(tmp_path)
    assert "(profiles.toml)" in grid
    assert "not valid TOML" in grid
    # The row is a fault, not a character: it must not offer a game letter.
    assert "AlphaPilot" not in grid
