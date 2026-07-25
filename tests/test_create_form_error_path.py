"""WO-CREATEFORM-ERROR-PATH — the create form's error line stops printing the
full absolute store path, and starts saying what the launcher already says.

``CreateFormScreen._try_save`` rendered every save failure as ``str(exc)``.
For the two store-read failures that is not a message, it is a message plus
the store's full absolute path, because ``credentials._StoreReadFailure.
__init__`` appends ``f"{reason} ({self.path})"``. That line is drawn at
column 3, so on an 80-column form it has 77 cells. Measured against a
51-character store path, the corrupt and malformed messages render 103 and
90 cells and the denied one 73; a deeper install path overflows all three.
The overflow is not cosmetic -- the line is clipped from the RIGHT, so the
part that falls off is the BASENAME, i.e. exactly the "which of the two
stores failed" that the path was being carried for.

The house had already ruled on this one function over.
``credentials._store_failure_row``, which renders the SAME failures as the
launcher's row, says in its own docstring: it "carries ``reason`` and not
``str(exc)``: the exception's text appends the full store path, which on an
80-column launcher line would push the operator's actual next action off the
right edge. Callers that want the path have the exception." One surface
applied that rule and the adjacent one did not. These tests pin them
together: the create form's line is now literally that row's ``name`` and
``error`` fields, space-joined, from that function's own spellings.

Two-sided on purpose. The fix is a change to what the message SAYS, not to
how the save path behaves, so every store-failure test also asserts the save
was still rejected and the operator's typed values survived -- and a whole
leg below asserts ``create_profile``'s ``ValueError``s ("unknown server
catalog key: …", "profile already exists: …") still arrive VERBATIM. Those
are the operator's actual next action; a blanket path-strip that mangled
them would be worse than the bug being fixed.

Real conditions, not mocked exceptions, for the store legs: a real ``chmod
000``, real non-UTF-8 bytes, a real wrong-shaped table -- same reasoning as
``tests/test_credentials_store_honesty.py``, whose ``TW_CONFIG_DIR`` +
``importlib.reload`` isolation idiom this file reuses so the real ``config/``
tree is never read, written or chmod-ed.
"""

from __future__ import annotations

import importlib
import os
from pathlib import Path

import pytest

from tw2002_aiclient import screens as screens_mod
from tw2002_aiclient.session import credentials

# chmod-based denial proves nothing as root: the kernel lets root read a 000
# file, so the "denied" branch would never be reached and the test would pass
# for the wrong reason.
_needs_unprivileged = pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="root bypasses file permissions — the denial can't be provoked",
)

# The form is an 80-column screen and the error line is written at column 3,
# so `cockpit.draw.safe_write` clips it to `max_x - x` cells. Every message
# this WO is about must fit inside that budget rather than be truncated into
# a fragment.
FORM_COLS = 80
ERROR_COL = 3
ERROR_CELL_BUDGET = FORM_COLS - ERROR_COL

GOOD_SERVERS = (
    '[servers.demo]\n'
    'name = "Demo Server"\n'
    'host = "demo.example.test"\n'
    'port = 2323\n'
)


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    """Isolated config dir for ``credentials``; teardown restores every mode.

    Same idiom as ``tests/test_credentials_store_honesty.py``'s own ``cfg``:
    ``TW_CONFIG_DIR`` + a real reload, the mechanism ``credentials``
    sanctions, so a ``chmod 000`` can never outlive its test.
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


class _StubScr:
    """Only what ``CreateFormScreen`` touches outside ``draw()``."""

    def getmaxyx(self):
        return (24, FORM_COLS)


def _open_form(monkeypatch):
    """Build the real form the way an operator opens it: on a READABLE catalog.

    That ordering is the point. ``__init__`` calls ``list_servers()`` too, so
    a catalog already broken at open time never reaches the save handler at
    all -- the failures this file is about arrive in the window between
    opening the form and pressing ``s``, which is precisely when
    ``create_profile``'s own second ``list_servers()`` read happens.

    ``_init_colors`` calls ``curses.has_colors()``, which needs a live
    terminal; forced monochrome is the same escape every non-pty screen test
    in this suite uses.
    """
    monkeypatch.setattr(screens_mod.curses, "has_colors", lambda: False)
    form = screens_mod.CreateFormScreen(_StubScr())
    form.values["handle"] = "Alpha"
    form.values["game_letter"] = "B"
    return form


def _save(form):
    """Press ``s``. Returns the handler's action (``None`` on a rejection)."""
    return form.handle_key(ord("s"))


def _drawn(form) -> str:
    """The literal cells ``draw()`` writes for the error line."""
    return f"! {form.error}"


def _assert_rejected_with_values_intact(form, action):
    """The control-flow half: this WO changed wording, not behavior."""
    assert action is None, "a failed save must not report itself saved"
    assert form.values["handle"] == "Alpha"
    assert form.values["game_letter"] == "B"


def _write_catalog(cfg_dir: Path, text: str = GOOD_SERVERS) -> None:
    (cfg_dir / "servers.toml").write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# The defect: an absolute store path on the error line.
#
# Each of these breaks the catalog AFTER the form is open, which is the only
# way a store failure reaches `_try_save` at all, and asserts three things:
# the abs path is gone, the line fits the cells it is drawn into, and the
# operator can still tell WHICH store failed and WHY.
# ---------------------------------------------------------------------------


@_needs_unprivileged
def test_denied_catalog_does_not_print_the_store_path(cfg, monkeypatch):
    _write_catalog(cfg)
    form = _open_form(monkeypatch)

    (cfg / "servers.toml").chmod(0o000)
    action = _save(form)

    assert str(cfg) not in form.error
    assert form.error == "(servers.toml) denied: Permission denied"
    assert len(_drawn(form)) <= ERROR_CELL_BUDGET
    _assert_rejected_with_values_intact(form, action)


def test_non_utf8_catalog_does_not_print_the_store_path(cfg, monkeypatch):
    _write_catalog(cfg)
    form = _open_form(monkeypatch)

    (cfg / "servers.toml").write_bytes(b'[servers.demo]\nname = "\xff\xfe"\n')
    action = _save(form)

    assert str(cfg) not in form.error
    assert form.error.startswith("(servers.toml) corrupt: not valid UTF-8")
    assert len(_drawn(form)) <= ERROR_CELL_BUDGET
    _assert_rejected_with_values_intact(form, action)


def test_malformed_catalog_does_not_print_the_store_path(cfg, monkeypatch):
    _write_catalog(cfg)
    form = _open_form(monkeypatch)

    (cfg / "servers.toml").write_text("servers = 5\n", encoding="utf-8")
    action = _save(form)

    assert str(cfg) not in form.error
    assert form.error == "(servers.toml) malformed: 'servers' is int, expected a table"
    assert len(_drawn(form)) <= ERROR_CELL_BUDGET
    _assert_rejected_with_values_intact(form, action)


def test_the_two_surfaces_now_render_the_same_failure_the_same_way(cfg):
    """The WO's actual goal, asserted against the sibling rather than a literal.

    Not a restatement of the tests above: those pin the create form's own
    spelling, this one pins it to ``_store_failure_row``'s. If the launcher's
    row is ever reworded, this fails and the two surfaces get re-agreed
    deliberately instead of drifting apart again the way they already did
    once.
    """
    _write_catalog(cfg, "servers = 5\n")
    (cfg / "profiles.toml").write_text("", encoding="utf-8")

    row = credentials.list_profile_summaries()[0]
    with pytest.raises(credentials.ProfileStoreMalformed) as caught:
        credentials.create_profile(server="demo", game_letter="B", handle="Alpha")

    assert screens_mod._create_error_text(caught.value) == f"{row['name']} {row['error']}"


# ---------------------------------------------------------------------------
# The regression this fix could plausibly have caused.
#
# `create_profile`'s ValueErrors are the operator's actual guidance. They must
# survive byte-for-byte -- so the expected text is CAPTURED from the real
# function rather than transcribed here, and a reworded guard cannot make
# these pass by accident.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kwargs", "duplicate_first"),
    [
        pytest.param({"server": "", "game_letter": "B", "handle": "A"}, False, id="empty-server"),
        pytest.param({"server": "demo", "game_letter": "", "handle": "A"}, False, id="empty-letter"),
        pytest.param({"server": "demo", "game_letter": "B", "handle": ""}, False, id="empty-handle"),
        pytest.param({"server": "no", "game_letter": "B", "handle": "A"}, False, id="unknown-key"),
        pytest.param({"server": "demo", "game_letter": "B", "handle": "A"}, True, id="duplicate"),
    ],
)
def test_create_profile_value_errors_reach_the_error_line_verbatim(
    cfg, monkeypatch, kwargs, duplicate_first
):
    _write_catalog(cfg)
    if duplicate_first:
        credentials.create_profile(server="demo", game_letter="B", handle="A")

    with pytest.raises(ValueError) as caught:
        credentials.create_profile(**kwargs)
    real = caught.value
    assert str(cfg) not in str(real), "precondition: these messages carry no path"

    form = _open_form(monkeypatch)
    monkeypatch.setattr(
        credentials,
        "create_profile",
        lambda **_kw: (_ for _ in ()).throw(real),
    )
    action = _save(form)

    assert form.error == str(real)
    _assert_rejected_with_values_intact(form, action)


def test_a_real_unknown_catalog_key_survives_the_whole_save_path(cfg, monkeypatch):
    """The one ``ValueError`` reachable end-to-end without patching anything.

    ``validate_create_form`` runs first and catches empty fields and known
    duplicates, so most of ``create_profile``'s guards are unreachable from
    this screen. This one is not: the form holds the catalog it read at open
    time, and ``create_profile`` re-reads the catalog for itself.
    """
    _write_catalog(cfg)
    form = _open_form(monkeypatch)

    _write_catalog(
        cfg,
        '[servers.other]\nname = "Other"\nhost = "other.example.test"\nport = 2323\n',
    )
    action = _save(form)

    assert form.error == "unknown server catalog key: 'demo'"
    _assert_rejected_with_values_intact(form, action)


# ---------------------------------------------------------------------------
# The renderer on its own: everything that is not a store-read failure keeps
# `str(exc)`. This is the fence against the over-correction -- a blanket
# path-strip would pass every test above and fail this one.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "exc",
    [
        pytest.param(ValueError("profile already exists: alpha"), id="value-error"),
        pytest.param(RuntimeError("something else entirely"), id="runtime-error"),
        pytest.param(OSError(13, "Permission denied"), id="os-error"),
    ],
)
def test_non_store_failures_keep_their_own_text(exc):
    assert screens_mod._create_error_text(exc) == str(exc)


def test_store_failures_are_matched_by_class_not_by_message_shape(cfg):
    """Both store-failure classes are handled -- they are siblings, not a
    base and its subclass, so covering one proves nothing about the other
    (``ProfileStoreUnreadable`` hangs off ``ProfileConnectionError`` while
    ``ProfileStoreMalformed`` hangs off ``ProfileMalformed``; see their own
    docstrings for why that split is deliberate)."""
    unreadable = credentials.ProfileStoreUnreadable(
        credentials.CAUSE_DENIED, "Permission denied", cfg / "servers.toml"
    )
    malformed = credentials.ProfileStoreMalformed(
        credentials.CAUSE_CORRUPT, "not valid TOML", cfg / "profiles.toml"
    )

    assert screens_mod._create_error_text(unreadable) == (
        "(servers.toml) denied: Permission denied"
    )
    assert screens_mod._create_error_text(malformed) == (
        "(profiles.toml) corrupt: not valid TOML"
    )
    # The half that is the whole point: neither rendering carries the path
    # that `str(exc)` would have appended.
    for exc in (unreadable, malformed):
        assert str(cfg) not in screens_mod._create_error_text(exc)
        assert str(cfg) in str(exc), "precondition: str(exc) is still the leaky one"
