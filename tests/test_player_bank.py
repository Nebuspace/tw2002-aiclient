"""Player bank stub tests (WO-P1-015) — metadata-only list_players.

Live API is thin: list_players() + NEVER/TURNS_UNKNOWN sentinels.
No load_bank/save_bank/add_player/next_player yet. Never touches the
real config/ or state/ trees (BANK_PATH + credentials monkeypatched).

Store-honesty coverage (WO-AUDIT-PLAYER-BANK-STORE-HONESTY) lives in the
second half of this file. Those conditions are driven for real -- ``chmod
000`` on the file, ``chmod 000`` on the directory containing it, genuinely
corrupt bytes, non-UTF-8 bytes, a directory standing where the file should be
-- rather than by mocking ``open`` to raise, because the defect being fenced
off was precisely that the *real* conditions all arrived at the same answer.
A mock proves the handler; only the real condition proves the classification.
"""

import errno
import json
import os

import pytest

from tw2002_aiclient.session import credentials, player_bank

# chmod-based denial proves nothing as root: the kernel lets root read a
# 000 file, so the "denied" branch would never be reached and the test
# would pass for the wrong reason.
_needs_unprivileged = pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="root bypasses file permissions — the denial can't be provoked",
)


def _point_bank_at(tmp_path, monkeypatch, body=None):
    bank_path = tmp_path / "player_bank.json"
    monkeypatch.setattr(player_bank, "BANK_PATH", bank_path)
    if body is not None:
        bank_path.write_text(json.dumps(body), encoding="utf-8")
    return bank_path


def _no_profiles(monkeypatch):
    monkeypatch.setattr(credentials, "load_profile_summaries", lambda: [])


def _one_profile(monkeypatch):
    monkeypatch.setattr(
        credentials,
        "load_profile_summaries",
        lambda: [
            {
                "name": "alpha",
                "handle": "ALPHAH",
                "host": "alpha.test.example",
                "game_letter": "F",
            }
        ],
    )


def test_constants_and_paths():
    assert player_bank.NEVER == "never"
    assert player_bank.TURNS_UNKNOWN == "-"
    assert player_bank.STATE_DIR.name == "state"
    assert player_bank.BANK_PATH.name == "player_bank.json"
    # The truncation mark is one cell wide, so a marked value still fits the
    # column exactly; and it is not one of the unknown markers, because "cut
    # to fit" is not "unknown" and an operator acts on them differently.
    assert player_bank.LAST_PLAYED_WIDTH == 21
    assert len(player_bank.TRUNCATED) == 1
    assert player_bank.TRUNCATED not in (player_bank.NEVER, player_bank.TURNS_UNKNOWN, "?")


def test_list_players_empty_when_no_profiles_and_no_bank(tmp_path, monkeypatch):
    _point_bank_at(tmp_path, monkeypatch)
    monkeypatch.setattr(credentials, "load_profile_summaries", lambda: [])
    assert player_bank.list_players() == []


def test_list_players_joins_profile_with_never_turns_when_bank_empty(tmp_path, monkeypatch):
    _point_bank_at(tmp_path, monkeypatch)
    monkeypatch.setattr(
        credentials,
        "load_profile_summaries",
        lambda: [
            {
                "name": "alpha",
                "handle": "ALPHAH",
                "host": "alpha.test.example",
                "server": "alpha.test.example",
                "game_letter": "F",
            }
        ],
    )
    rows = player_bank.list_players()
    assert len(rows) == 1
    assert rows[0] == {
        "name": "alpha",
        "handle": "ALPHAH",
        "host": "alpha.test.example",
        "game_letter": "F",
        "last_played": player_bank.NEVER,
        "turns_state": player_bank.TURNS_UNKNOWN,
    }


def test_list_players_merges_bank_rotation_fields(tmp_path, monkeypatch):
    _point_bank_at(
        tmp_path,
        monkeypatch,
        {
            "version": 1,
            "players": [
                {
                    "name": "alpha",
                    "last_played": "2026-07-23T12:00:00Z",
                    "turns_state": "exhausted",
                }
            ],
        },
    )
    monkeypatch.setattr(
        credentials,
        "load_profile_summaries",
        lambda: [
            {
                "name": "alpha",
                "handle": "ALPHAH",
                "host": "alpha.test.example",
                "game_letter": "F",
            }
        ],
    )
    rows = player_bank.list_players()
    assert rows[0]["last_played"] == "2026-07-23T12:00:00Z"
    assert rows[0]["turns_state"] == "exhausted"


def test_list_players_surfaces_bank_only_orphan_after_profile_removed(tmp_path, monkeypatch):
    _point_bank_at(
        tmp_path,
        monkeypatch,
        {
            "version": 1,
            "players": [
                {
                    "name": "ghost",
                    "handle": "GHOSTH",
                    "host": "old.example",
                    "game_letter": "A",
                    "last_played": "2026-01-01T00:00:00Z",
                    "turns_state": "ok",
                }
            ],
        },
    )
    monkeypatch.setattr(credentials, "load_profile_summaries", lambda: [])
    rows = player_bank.list_players()
    assert len(rows) == 1
    assert rows[0]["name"] == "ghost"
    assert rows[0]["handle"] == "GHOSTH"
    assert rows[0]["last_played"] == "2026-01-01T00:00:00Z"


def test_list_players_surfaces_a_broken_profile_instead_of_dropping_it(
    tmp_path, monkeypatch
):
    """Replaces ``test_list_players_skips_profile_rows_with_error``.

    That test asserted the defect. "Skips" was the tell: a profile whose
    summary carried an ``error`` vanished from the listing entirely, and the
    bank view then painted the remaining rows as a complete table. That is the
    same collapse this module's docstring exists to prevent -- "there is no
    such character" and "that character's profile is broken" are different
    facts an operator acts on differently, and they rendered alike (both:
    absent).

    Unlike the bank-unreadable case, there IS an honest row here: the bank was
    read, so ``last_played``/``turns_state`` are real, and every identity
    column this function cannot fill already has an established marker (``?``).
    """
    _point_bank_at(tmp_path, monkeypatch)
    monkeypatch.setattr(
        credentials,
        "load_profile_summaries",
        lambda: [{"name": "broken", "error": "missing host", "handle": "X"}],
    )
    rows = player_bank.list_players()
    assert len(rows) == 1
    row = rows[0]
    assert row["name"] == "broken"
    assert row["error"] == "missing host"
    # Invents nothing it did not read -- the same `?` this function already
    # uses, never a fabricated host or game letter.
    assert row["host"] == "?"
    assert row["game_letter"] == "?"
    # The bank WAS read, so these two are honest, not manufactured.
    assert row["last_played"] == player_bank.NEVER
    assert row["turns_state"] == player_bank.TURNS_UNKNOWN


def test_a_broken_profile_never_shrinks_the_listing_around_it(tmp_path, monkeypatch):
    """The healthy rows keep their exact shape; only the broken row differs.

    ``error`` is present on a broken row and ABSENT (not ``None``) on a healthy
    one, so ``entry.get("error")`` is the surface's whole branch and a healthy
    row's six-key contract is untouched.
    """
    _point_bank_at(tmp_path, monkeypatch)
    monkeypatch.setattr(
        credentials,
        "load_profile_summaries",
        lambda: [
            {
                "name": "good",
                "handle": "GOODH",
                "host": "good.test.example",
                "game_letter": "A",
            },
            {"name": "broken", "error": "missing game_letter", "handle": "B"},
        ],
    )
    rows = player_bank.list_players()
    assert [r["name"] for r in rows] == ["good", "broken"]  # order preserved
    assert rows[0] == {
        "name": "good",
        "handle": "GOODH",
        "host": "good.test.example",
        "game_letter": "A",
        "last_played": player_bank.NEVER,
        "turns_state": player_bank.TURNS_UNKNOWN,
    }
    assert "error" not in rows[0]
    assert rows[1]["error"] == "missing game_letter"


def test_a_broken_profile_shows_its_own_metadata_not_the_banks(tmp_path, monkeypatch):
    """The nastier half of the drop: a broken profile that HAS a bank entry.

    It did not vanish -- it came back through the bank-only loop below wearing
    the BANK's stored ``handle``/``host``/``game_letter`` (the profile's own
    were never consulted) and carrying no error at all, so a broken profile
    rendered as an ordinary healthy character described by a different store.
    That is a positive false claim, not merely an omission.

    Exactly one row, identity from the profile, rotation from the bank.
    """
    _point_bank_at(
        tmp_path,
        monkeypatch,
        {
            "version": 1,
            "players": [
                {
                    "name": "broken",
                    "handle": "STALE-BANK-HANDLE",
                    "host": "stale.bank.example",
                    "game_letter": "Z",
                    "last_played": "2026-07-23T12:00:00Z",
                    "turns_state": "ok",
                }
            ],
        },
    )
    monkeypatch.setattr(
        credentials,
        "load_profile_summaries",
        lambda: [
            {
                "name": "broken",
                "handle": "PROFILEH",
                "host": "profile.test.example",
                "game_letter": "",
                "error": "missing game_letter",
            }
        ],
    )
    rows = player_bank.list_players()
    assert len(rows) == 1, "the profile row and the bank row must not both emit"
    row = rows[0]
    assert row["error"] == "missing game_letter"
    assert row["handle"] == "PROFILEH"
    assert row["host"] == "profile.test.example"
    assert "STALE-BANK-HANDLE" not in json.dumps(row)
    assert "stale.bank.example" not in json.dumps(row)
    # ...but the rotation columns are the bank's, because the bank is where
    # they live and it was read.
    assert row["last_played"] == "2026-07-23T12:00:00Z"
    assert row["turns_state"] == "ok"


# ---------------------------------------------------------------------------
# Unmarked timestamp truncation (WO-PLAYERBANK-LISTING-HONESTY, defect B)
#
# `last_played` is cut to the launcher's column width. The cut itself is a
# layout necessity; doing it SILENTLY was the defect -- a cut value read as a
# whole one, and two different stored stamps rendered byte-identical.
# ---------------------------------------------------------------------------

_LONG_A = "2026-07-23T12:00:00.000001+00:00"  # 32 chars
_LONG_B = "2026-07-23T12:00:00.000002+00:00"  # differs only at char 27


def test_last_played_says_so_when_it_had_to_be_cut(tmp_path, monkeypatch):
    _point_bank_at(
        tmp_path,
        monkeypatch,
        {"version": 1, "players": [{"name": "alpha", "last_played": _LONG_A}]},
    )
    _one_profile(monkeypatch)
    shown = player_bank.list_players()[0]["last_played"]
    assert shown.endswith(player_bank.TRUNCATED)
    assert shown != _LONG_A
    # Column-preserving: never wider than the launcher's `last_played` field,
    # so marking the cut cannot shove the `turns` column off its position.
    assert len(shown) == player_bank.LAST_PLAYED_WIDTH
    assert shown == _LONG_A[: player_bank.LAST_PLAYED_WIDTH - 1] + player_bank.TRUNCATED


def test_two_stamps_that_differ_past_the_cut_no_longer_claim_to_be_whole(
    tmp_path, monkeypatch
):
    """The bug as an operator meets it: two rows, one rendering.

    Marking does not make them distinguishable -- the information really is
    gone at this width -- but neither row now presents itself as the complete
    stored value, which is the claim that was false.
    """
    _point_bank_at(
        tmp_path,
        monkeypatch,
        {
            "version": 1,
            "players": [
                {"name": "alpha", "last_played": _LONG_A},
                {"name": "bravo", "last_played": _LONG_B},
            ],
        },
    )
    monkeypatch.setattr(
        credentials,
        "load_profile_summaries",
        lambda: [
            {"name": "alpha", "handle": "A", "host": "a.example", "game_letter": "A"},
            {"name": "bravo", "handle": "B", "host": "b.example", "game_letter": "B"},
        ],
    )
    shown = {r["name"]: r["last_played"] for r in player_bank.list_players()}
    assert shown["alpha"].endswith(player_bank.TRUNCATED)
    assert shown["bravo"].endswith(player_bank.TRUNCATED)
    # The pre-fix rendering was this bare prefix, which reads as a complete
    # fractional-second stamp and is what made the collision invisible.
    assert shown["alpha"] != _LONG_A[: player_bank.LAST_PLAYED_WIDTH]
    assert shown["bravo"] != _LONG_B[: player_bank.LAST_PLAYED_WIDTH]


@pytest.mark.parametrize(
    "stamp",
    [
        "2026-07-23T12:00:00Z",  # 20 -- the common case, room to spare
        "2026-07-23T12:00:00.0Z",  # 22 -> must be cut
        "x" * 21,  # exactly the width: fits, must NOT be marked
        "x" * 22,  # one over: must be marked
    ],
)
def test_a_last_played_is_marked_if_and_only_if_it_was_cut(
    tmp_path, monkeypatch, stamp
):
    """A false truncation mark is its own lie -- the boundary is pinned."""
    _point_bank_at(
        tmp_path,
        monkeypatch,
        {"version": 1, "players": [{"name": "alpha", "last_played": stamp}]},
    )
    _one_profile(monkeypatch)
    shown = player_bank.list_players()[0]["last_played"]
    if len(stamp) <= player_bank.LAST_PLAYED_WIDTH:
        assert shown == stamp
        assert not shown.endswith(player_bank.TRUNCATED)
    else:
        assert shown.endswith(player_bank.TRUNCATED)
        assert len(shown) == player_bank.LAST_PLAYED_WIDTH


def test_the_bank_only_orphan_row_marks_its_truncation_too(tmp_path, monkeypatch):
    """The second call site. Both loops cut ``last_played``; the rule is one
    helper now precisely so a fix to one can never leave the other lying."""
    _point_bank_at(
        tmp_path,
        monkeypatch,
        {
            "version": 1,
            "players": [
                {
                    "name": "ghost",
                    "handle": "GHOSTH",
                    "host": "old.example",
                    "game_letter": "A",
                    "last_played": _LONG_A,
                }
            ],
        },
    )
    monkeypatch.setattr(credentials, "load_profile_summaries", lambda: [])
    rows = player_bank.list_players()
    assert len(rows) == 1
    assert rows[0]["last_played"].endswith(player_bank.TRUNCATED)
    assert len(rows[0]["last_played"]) == player_bank.LAST_PLAYED_WIDTH


def test_list_players_refuses_to_invent_never_rows_for_a_corrupt_bank(tmp_path, monkeypatch):
    """Replaces ``test_list_players_tolerates_corrupt_bank_json``.

    That test asserted the defect: a corrupt bank yielded one row whose
    ``last_played`` read ``never`` -- a positive claim about a character's
    rotation history, manufactured from bytes nobody could parse. "Tolerates"
    was the tell. The profile row is real, but every column this function
    joins onto it comes from the bank, so there is no honest partial row to
    emit.
    """
    bank_path = tmp_path / "player_bank.json"
    monkeypatch.setattr(player_bank, "BANK_PATH", bank_path)
    bank_path.write_text("{not-json", encoding="utf-8")
    _one_profile(monkeypatch)

    with pytest.raises(player_bank.BankUnreadable) as caught:
        player_bank.list_players()
    assert caught.value.cause == player_bank.CAUSE_CORRUPT
    assert "invalid JSON" in caught.value.reason


def test_list_players_never_includes_password_keys(tmp_path, monkeypatch):
    _point_bank_at(
        tmp_path,
        monkeypatch,
        {
            "version": 1,
            "players": [{"name": "alpha", "password": "should-never-surface"}],
        },
    )
    monkeypatch.setattr(
        credentials,
        "load_profile_summaries",
        lambda: [
            {
                "name": "alpha",
                "handle": "ALPHAH",
                "host": "alpha.test.example",
                "game_letter": "F",
            }
        ],
    )
    row = player_bank.list_players()[0]
    assert "password" not in row
    assert "should-never-surface" not in json.dumps(row)


# ---------------------------------------------------------------------------
# Store honesty (WO-AUDIT-PLAYER-BANK-STORE-HONESTY)
#
# Nine distinct real conditions used to arrive at one of two dishonest
# answers: eight returned the identical reassuring `{"version": 1,
# "players": []}` -- "there are no players" -- and the ninth (non-UTF-8)
# escaped as an unhandled UnicodeDecodeError and took the launcher's bank
# view down with it. Each test below drives its condition for real.
# ---------------------------------------------------------------------------


def test_absent_bank_is_the_one_condition_entitled_to_report_no_players(
    tmp_path, monkeypatch
):
    """Control case -- green before this WO and after.

    A bank that was never written is a genuine negative: the read succeeded
    and there is nothing there. It must keep returning the empty bank, or the
    fix would have traded a false "empty" for a false "broken".
    """
    _point_bank_at(tmp_path, monkeypatch)
    assert player_bank._load_bank_raw() == {"version": 1, "players": []}


@_needs_unprivileged
def test_permission_denied_on_the_bank_file_is_not_an_empty_bank(tmp_path, monkeypatch):
    bank_path = _point_bank_at(
        tmp_path, monkeypatch, {"version": 1, "players": [{"name": "alpha"}]}
    )
    os.chmod(bank_path, 0o000)
    try:
        with pytest.raises(player_bank.BankUnreadable) as caught:
            player_bank._load_bank_raw()
    finally:
        os.chmod(bank_path, 0o600)
    assert caught.value.cause == player_bank.CAUSE_DENIED


@_needs_unprivileged
def test_unreadable_parent_directory_is_not_an_absent_bank(tmp_path, monkeypatch):
    """The condition ``Path.exists()`` used to hide at the very first line.

    A populated bank inside a ``chmod 000`` directory: ``exists()`` answers
    ``False`` there (it swallows the ``PermissionError``), so "no bank was
    ever written" and "the bank is behind a door I can't open" were the same
    answer before any of the reader's error handling got a turn. Opening the
    file is what tells them apart -- this raises ``PermissionError``, never
    ``FileNotFoundError``.
    """
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    bank_path = state_dir / "player_bank.json"
    bank_path.write_text(
        json.dumps({"version": 1, "players": [{"name": "alpha"}]}), encoding="utf-8"
    )
    monkeypatch.setattr(player_bank, "BANK_PATH", bank_path)
    os.chmod(state_dir, 0o000)
    try:
        # The premise: exists() really does lie here. If this ever stops being
        # true the test above it is no longer proving what it claims.
        assert bank_path.exists() is False
        with pytest.raises(player_bank.BankUnreadable) as caught:
            player_bank._load_bank_raw()
    finally:
        os.chmod(state_dir, 0o700)
    assert caught.value.cause == player_bank.CAUSE_DENIED
    # It must name the directory, not the file. The file's own permissions are
    # fine; an operator told only "Permission denied (…/player_bank.json)"
    # would chmod the wrong object and get nowhere.
    assert str(state_dir) in caught.value.reason
    assert "directory" in caught.value.reason


@_needs_unprivileged
def test_a_denied_file_does_not_blame_its_directory(tmp_path, monkeypatch):
    """The converse of the test above -- the two denials stay apart.

    Same cause (both are "fix the permissions"), different object, so the
    reason must not accuse the directory when the directory is readable.
    """
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    bank_path = state_dir / "player_bank.json"
    bank_path.write_text(json.dumps({"version": 1, "players": []}), encoding="utf-8")
    monkeypatch.setattr(player_bank, "BANK_PATH", bank_path)
    os.chmod(bank_path, 0o000)
    try:
        with pytest.raises(player_bank.BankUnreadable) as caught:
            player_bank._load_bank_raw()
    finally:
        os.chmod(bank_path, 0o600)
    assert caught.value.cause == player_bank.CAUSE_DENIED
    assert "directory" not in caught.value.reason
    assert caught.value.path == str(bank_path)


def test_corrupt_json_is_not_an_empty_bank(tmp_path, monkeypatch):
    bank_path = _point_bank_at(tmp_path, monkeypatch)
    bank_path.write_text("{not json at all,,,", encoding="utf-8")
    with pytest.raises(player_bank.BankUnreadable) as caught:
        player_bank._load_bank_raw()
    assert caught.value.cause == player_bank.CAUSE_CORRUPT
    assert "invalid JSON" in caught.value.reason


def test_non_utf8_bank_is_reported_not_crashed(tmp_path, monkeypatch):
    """The ninth condition, and the only one that was never a collapse.

    ``UnicodeDecodeError`` subclasses ``ValueError``, not ``OSError``, and it
    is a *different* ``ValueError`` subclass from ``json.JSONDecodeError`` --
    so the old ``except (OSError, json.JSONDecodeError)`` never caught it. It
    escaped through ``list_players()`` and out of the launcher's bank view.
    ``loops/store.py`` already catches this one by name; this file did not.
    """
    bank_path = _point_bank_at(tmp_path, monkeypatch)
    bank_path.write_bytes(b'{"version": 1, "players": [{"name": "\xff\xfe"}]}')
    with pytest.raises(player_bank.BankUnreadable) as caught:
        player_bank._load_bank_raw()
    assert caught.value.cause == player_bank.CAUSE_CORRUPT
    assert caught.value.reason == "not valid UTF-8"
    # The point of the test: it is no longer the raw decode error.
    assert not isinstance(caught.value, UnicodeDecodeError)


def test_top_level_json_list_is_not_an_empty_bank(tmp_path, monkeypatch):
    _point_bank_at(tmp_path, monkeypatch, [{"name": "alpha"}])
    with pytest.raises(player_bank.BankUnreadable) as caught:
        player_bank._load_bank_raw()
    assert caught.value.cause == player_bank.CAUSE_MALFORMED
    assert "list" in caught.value.reason


def test_absent_players_key_is_not_a_claim_of_zero_players(tmp_path, monkeypatch):
    """``{"version": 1}`` does not say "zero players"; it says nothing."""
    _point_bank_at(tmp_path, monkeypatch, {"version": 1})
    with pytest.raises(player_bank.BankUnreadable) as caught:
        player_bank._load_bank_raw()
    assert caught.value.cause == player_bank.CAUSE_MALFORMED
    assert caught.value.reason == "no 'players' list"


def test_players_of_the_wrong_type_is_not_a_claim_of_zero_players(tmp_path, monkeypatch):
    _point_bank_at(tmp_path, monkeypatch, {"version": 1, "players": "oops"})
    with pytest.raises(player_bank.BankUnreadable) as caught:
        player_bank._load_bank_raw()
    assert caught.value.cause == player_bank.CAUSE_MALFORMED
    assert "str" in caught.value.reason
    # Distinct from the absent-key reason -- two different repairs.
    assert caught.value.reason != "no 'players' list"


def test_a_directory_where_the_bank_should_be_is_not_a_permission_problem(
    tmp_path, monkeypatch
):
    """Both are ``OSError``; they are not the same job for the operator.

    "Fix the permissions on this file" and "something else is sitting at this
    path" lead to different actions, so they do not share a cause.
    """
    bank_path = tmp_path / "player_bank.json"
    bank_path.mkdir()
    monkeypatch.setattr(player_bank, "BANK_PATH", bank_path)
    with pytest.raises(player_bank.BankUnreadable) as caught:
        player_bank._load_bank_raw()
    assert caught.value.cause == player_bank.CAUSE_UNUSABLE
    assert caught.value.cause != player_bank.CAUSE_DENIED
    assert caught.value.reason == os.strerror(errno.EISDIR)


@_needs_unprivileged
def test_no_two_failure_conditions_render_alike(tmp_path, monkeypatch):
    """The anti-collapse assertion, stated directly.

    Drives every failure condition through the reader and requires the
    ``(cause, reason)`` pairs to be pairwise distinct -- and none of them to
    be the empty-bank answer. With the pre-WO reader in place this collects
    one repeated value (or dies on the non-UTF-8 case), which is the whole
    defect in one assert.
    """
    outcomes: dict[str, tuple[str, str]] = {}
    restore = []

    def record(label, path):
        monkeypatch.setattr(player_bank, "BANK_PATH", path)
        with pytest.raises(player_bank.BankUnreadable) as caught:
            player_bank._load_bank_raw()
        outcomes[label] = (caught.value.cause, caught.value.reason)

    try:
        denied = tmp_path / "denied.json"
        denied.write_text(json.dumps({"version": 1, "players": []}), encoding="utf-8")
        os.chmod(denied, 0o000)
        restore.append((denied, 0o600))
        record("file denied", denied)

        walled = tmp_path / "walled"
        walled.mkdir()
        inner = walled / "player_bank.json"
        inner.write_text(json.dumps({"version": 1, "players": []}), encoding="utf-8")
        os.chmod(walled, 0o000)
        restore.append((walled, 0o700))
        record("directory denied", inner)
    finally:
        for path, mode in restore:
            os.chmod(path, mode)

    as_dir = tmp_path / "as_dir.json"
    as_dir.mkdir()
    record("path is a directory", as_dir)

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{not json at all,,,", encoding="utf-8")
    record("corrupt JSON", bad_json)

    bad_utf8 = tmp_path / "bad_utf8.json"
    bad_utf8.write_bytes(b'{"players": [{"name": "\xff"}]}')
    record("not UTF-8", bad_utf8)

    top_list = tmp_path / "top_list.json"
    top_list.write_text(json.dumps([1, 2]), encoding="utf-8")
    record("top level is a list", top_list)

    no_key = tmp_path / "no_key.json"
    no_key.write_text(json.dumps({"version": 1}), encoding="utf-8")
    record("no players key", no_key)

    wrong_type = tmp_path / "wrong_type.json"
    wrong_type.write_text(json.dumps({"version": 1, "players": {}}), encoding="utf-8")
    record("players is not a list", wrong_type)

    assert len(outcomes) == 8
    assert len(set(outcomes.values())) == 8, (
        "two failure conditions render identically: "
        f"{sorted(outcomes.items(), key=lambda kv: kv[1])}"
    )
    # Denial and corruption are the pair the operator most needs kept apart.
    assert outcomes["file denied"][0] == player_bank.CAUSE_DENIED
    assert outcomes["directory denied"][0] == player_bank.CAUSE_DENIED
    assert outcomes["corrupt JSON"][0] == player_bank.CAUSE_CORRUPT

    # ...and the genuine negative is still its own, non-raising answer.
    absent = tmp_path / "never_written.json"
    monkeypatch.setattr(player_bank, "BANK_PATH", absent)
    assert player_bank._load_bank_raw() == {"version": 1, "players": []}


@_needs_unprivileged
def test_list_players_propagates_rather_than_shortening_the_list(tmp_path, monkeypatch):
    """A denied bank must not surface as "this operator has no characters"."""
    bank_path = _point_bank_at(
        tmp_path, monkeypatch, {"version": 1, "players": [{"name": "ghost"}]}
    )
    os.chmod(bank_path, 0o000)
    _one_profile(monkeypatch)
    try:
        with pytest.raises(player_bank.BankUnreadable) as caught:
            player_bank.list_players()
    finally:
        os.chmod(bank_path, 0o600)
    assert caught.value.cause == player_bank.CAUSE_DENIED
    assert caught.value.path == str(bank_path)


def test_bank_unreadable_message_carries_reason_and_path():
    exc = player_bank.BankUnreadable(
        player_bank.CAUSE_DENIED, "Permission denied", "/nowhere/player_bank.json"
    )
    assert exc.cause == player_bank.CAUSE_DENIED
    assert exc.reason == "Permission denied"
    assert exc.path == "/nowhere/player_bank.json"
    assert "Permission denied" in str(exc)
    assert "/nowhere/player_bank.json" in str(exc)
