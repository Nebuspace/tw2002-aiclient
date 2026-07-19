"""Player Bank tests (TW-31 client-side half) — no network, tmp_path only,
never touches the real config/ or state/ directories."""

import fcntl
import json
import os
import stat
import threading
import time

import pytest

from twclient import player_bank


def _write_profiles(tmp_path, body):
    path = tmp_path / "profiles.toml"
    path.write_text(body, encoding="utf-8")
    return path


_ALPHA_PROFILE = '[alpha]\nhost="alpha.test.example"\nport=23\ngame_letter="F"\nhandle="ALPHAH"\n'
_BRAVO_PROFILE = '[bravo]\nhost="bravo.test.example"\nport=23\ngame_letter="F"\nhandle="BRAVOH"\n'


# -- load_bank / save_bank ---------------------------------------------------

def test_load_bank_missing_file_returns_fresh_empty_bank(tmp_path):
    bank_path = tmp_path / "player_bank.json"
    bank = player_bank.load_bank(bank_path=bank_path)
    assert bank == {"version": 1, "players": []}
    assert not bank_path.exists()  # load never creates the file


def test_save_then_load_round_trips(tmp_path):
    bank_path = tmp_path / "player_bank.json"
    original = {"version": 1, "players": [{"name": "alpha", "last_played": None}]}
    player_bank.save_bank(original, bank_path=bank_path)
    assert player_bank.load_bank(bank_path=bank_path) == original


def test_save_bank_leaves_no_temp_file_after_success(tmp_path):
    bank_path = tmp_path / "player_bank.json"
    player_bank.save_bank({"version": 1, "players": []}, bank_path=bank_path)
    tmp_sibling = bank_path.with_suffix(bank_path.suffix + ".tmp")
    assert not tmp_sibling.exists()
    assert bank_path.exists()


def test_save_bank_atomic_write_survives_a_crash_before_rename(tmp_path, monkeypatch):
    """The whole point of temp-then-rename: if the rename step itself
    fails (simulating a crash between write and rename), the
    destination file must be left exactly as it was -- never a
    half-written or truncated bank."""
    bank_path = tmp_path / "player_bank.json"
    original = {"version": 1, "players": [{"name": "alpha", "last_played": None}]}
    player_bank.save_bank(original, bank_path=bank_path)

    def boom(*_a, **_kw):
        raise OSError("simulated crash before rename")

    monkeypatch.setattr(player_bank.os, "replace", boom)

    with pytest.raises(OSError):
        player_bank.save_bank({"version": 1, "players": [{"name": "bravo"}]}, bank_path=bank_path)

    assert player_bank.load_bank(bank_path=bank_path) == original


def test_save_bank_creates_file_with_0600_permissions(tmp_path):
    """Cipher finding #9: umask-default 0644 would leave the bank
    (real handle/host/game_letter metadata) group/world-readable.
    Matches `credentials.py::_write_secrets`'s exact 0600 treatment."""
    bank_path = tmp_path / "player_bank.json"
    player_bank.save_bank({"version": 1, "players": []}, bank_path=bank_path)
    assert stat.S_IMODE(os.stat(bank_path).st_mode) == 0o600


def test_save_bank_overwrite_still_leaves_0600_permissions(tmp_path):
    """A second write onto an existing file must not regress permissions
    (e.g. via a broader-mode tmp file surviving into the rename)."""
    bank_path = tmp_path / "player_bank.json"
    player_bank.save_bank({"version": 1, "players": []}, bank_path=bank_path)
    player_bank.save_bank({"version": 1, "players": [{"name": "alpha"}]}, bank_path=bank_path)
    assert stat.S_IMODE(os.stat(bank_path).st_mode) == 0o600


# -- add_player ---------------------------------------------------------------

def test_add_player_pulls_fields_from_the_named_profile(tmp_path):
    profiles_path = _write_profiles(tmp_path, _ALPHA_PROFILE)
    bank_path = tmp_path / "player_bank.json"

    entry = player_bank.add_player("alpha", profiles_path=profiles_path, bank_path=bank_path)

    assert entry["name"] == "alpha"
    assert entry["handle"] == "ALPHAH"
    assert entry["host"] == "alpha.test.example"
    assert entry["port"] == 23
    assert entry["game_letter"] == "F"
    assert entry["last_played"] is None
    assert entry["turns_state"] == "active"
    assert "created" in entry


def test_add_player_persists_to_disk(tmp_path):
    profiles_path = _write_profiles(tmp_path, _ALPHA_PROFILE)
    bank_path = tmp_path / "player_bank.json"
    player_bank.add_player("alpha", profiles_path=profiles_path, bank_path=bank_path)

    on_disk = json.loads(bank_path.read_text(encoding="utf-8"))
    assert on_disk["players"][0]["name"] == "alpha"


def test_add_player_refuses_duplicate_name(tmp_path):
    profiles_path = _write_profiles(tmp_path, _ALPHA_PROFILE)
    bank_path = tmp_path / "player_bank.json"
    player_bank.add_player("alpha", profiles_path=profiles_path, bank_path=bank_path)

    with pytest.raises(player_bank.PlayerBankError):
        player_bank.add_player("alpha", profiles_path=profiles_path, bank_path=bank_path)

    # still only one entry -- the refused add never appended a second row.
    assert len(player_bank.list_players(bank_path=bank_path)) == 1


def test_add_player_unknown_profile_raises_credential_error(tmp_path):
    profiles_path = _write_profiles(tmp_path, _ALPHA_PROFILE)
    bank_path = tmp_path / "player_bank.json"

    from twclient import credentials

    with pytest.raises(credentials.CredentialError):
        player_bank.add_player("nope", profiles_path=profiles_path, bank_path=bank_path)
    assert not bank_path.exists()


def test_add_player_refuses_password_shaped_notes_keys(tmp_path):
    profiles_path = _write_profiles(tmp_path, _ALPHA_PROFILE)
    bank_path = tmp_path / "player_bank.json"

    with pytest.raises(player_bank.PlayerBankError):
        player_bank.add_player(
            "alpha", profiles_path=profiles_path, bank_path=bank_path,
            notes={"password": "hunter2"},
        )
    # rejected before any write -- no partial/leaked bank file at all.
    assert not bank_path.exists()


@pytest.mark.parametrize("bad_key", ["Password", "SECRET_TOKEN", "credential", "api_token"])
def test_add_player_refuses_password_shaped_notes_keys_case_and_synonym_insensitive(tmp_path, bad_key):
    profiles_path = _write_profiles(tmp_path, _ALPHA_PROFILE)
    bank_path = tmp_path / "player_bank.json"

    with pytest.raises(player_bank.PlayerBankError):
        player_bank.add_player(
            "alpha", profiles_path=profiles_path, bank_path=bank_path,
            notes={bad_key: "x"},
        )


@pytest.mark.parametrize("bad_key", ["pw", "pwd", "auth", "apikey", "creds"])
def test_add_player_refuses_broadened_alias_notes_keys(tmp_path, bad_key):
    """Cipher finding #8: the original denylist (pass/secret/token/
    credential) missed these common aliases entirely -- a caller could
    stash a password under `pw`/`pwd`/`auth`/`apikey`/`creds` and it
    would sail straight through the old check."""
    profiles_path = _write_profiles(tmp_path, _ALPHA_PROFILE)
    bank_path = tmp_path / "player_bank.json"

    with pytest.raises(player_bank.PlayerBankError):
        player_bank.add_player(
            "alpha", profiles_path=profiles_path, bank_path=bank_path,
            notes={bad_key: "x"},
        )
    assert not bank_path.exists()


def test_add_player_refuses_nested_dict_notes_value(tmp_path):
    """Cipher finding #8's value-smuggling bypass: the original check
    only scanned top-level keys, so a secret hidden a level down under
    an innocuous key (here `favorite_route`) sailed straight through.
    Nested containers are now refused outright, closing it."""
    profiles_path = _write_profiles(tmp_path, _ALPHA_PROFILE)
    bank_path = tmp_path / "player_bank.json"

    with pytest.raises(player_bank.PlayerBankError):
        player_bank.add_player(
            "alpha", profiles_path=profiles_path, bank_path=bank_path,
            notes={"favorite_route": {"password": "hunter2"}},
        )
    assert not bank_path.exists()


def test_add_player_refuses_nested_list_notes_value(tmp_path):
    profiles_path = _write_profiles(tmp_path, _ALPHA_PROFILE)
    bank_path = tmp_path / "player_bank.json"

    with pytest.raises(player_bank.PlayerBankError):
        player_bank.add_player(
            "alpha", profiles_path=profiles_path, bank_path=bank_path,
            notes={"tags": ["sector 4-5", "hunter2"]},
        )
    assert not bank_path.exists()


def test_add_player_refuses_overlong_notes_value(tmp_path):
    profiles_path = _write_profiles(tmp_path, _ALPHA_PROFILE)
    bank_path = tmp_path / "player_bank.json"

    with pytest.raises(player_bank.PlayerBankError):
        player_bank.add_player(
            "alpha", profiles_path=profiles_path, bank_path=bank_path,
            notes={"route_notes": "x" * 201},
        )
    assert not bank_path.exists()


def test_add_player_accepts_benign_scalar_notes(tmp_path):
    """Cipher finding #8's allow-list: str/int/float/bool are the only
    permitted notes value types."""
    profiles_path = _write_profiles(tmp_path, _ALPHA_PROFILE)
    bank_path = tmp_path / "player_bank.json"

    entry = player_bank.add_player(
        "alpha", profiles_path=profiles_path, bank_path=bank_path,
        notes={
            "favorite_route": "sector 4-5",
            "favorite_sector": 45,
            "profit_margin": 12.5,
            "auto_haggle": True,
        },
    )
    assert entry["notes"] == {
        "favorite_route": "sector 4-5",
        "favorite_sector": 45,
        "profit_margin": 12.5,
        "auto_haggle": True,
    }


def test_no_secret_shaped_key_or_value_ever_reaches_the_saved_bank_file(tmp_path):
    """End-to-end defensive proof (renamed from
    test_no_password_shaped_value_ever_lands_in_the_saved_bank_file per
    cipher's finding #8 -- same proof, now against the broadened
    denylist): even if a caller tries to sneak a password into notes,
    it never reaches disk -- and the entry pulled from the profile has
    no password field to begin with (Profile structurally carries
    none)."""
    profiles_path = _write_profiles(tmp_path, _ALPHA_PROFILE)
    bank_path = tmp_path / "player_bank.json"

    with pytest.raises(player_bank.PlayerBankError):
        player_bank.add_player(
            "alpha", profiles_path=profiles_path, bank_path=bank_path,
            notes={"password": "hunter2", "favorite_route": "sector 4-5"},
        )
    assert not bank_path.exists()

    # a clean add succeeds and the on-disk JSON contains no password-shaped
    # key anywhere in the whole file.
    player_bank.add_player("alpha", profiles_path=profiles_path, bank_path=bank_path)
    raw_text = bank_path.read_text(encoding="utf-8")
    assert "password" not in raw_text.lower()
    assert "hunter2" not in raw_text


def test_rejected_notes_key_is_redacted_in_the_error_message(tmp_path):
    """Cipher finding #10: the refused key must never appear verbatim
    in the exception message -- only a truncated form -- so a
    secret-shaped KEY itself can't land in a log/traceback."""
    profiles_path = _write_profiles(tmp_path, _ALPHA_PROFILE)
    bank_path = tmp_path / "player_bank.json"

    long_secret_key = "password_for_the_seraph_account_do_not_share"
    with pytest.raises(player_bank.PlayerBankError) as excinfo:
        player_bank.add_player(
            "alpha", profiles_path=profiles_path, bank_path=bank_path,
            notes={long_secret_key: "x"},
        )
    assert long_secret_key not in str(excinfo.value)


# -- list_players ---------------------------------------------------------------

def test_list_players_returns_copies_not_live_references(tmp_path):
    profiles_path = _write_profiles(tmp_path, _ALPHA_PROFILE)
    bank_path = tmp_path / "player_bank.json"
    player_bank.add_player("alpha", profiles_path=profiles_path, bank_path=bank_path)

    players = player_bank.list_players(bank_path=bank_path)
    players[0]["turns_state"] = "exhausted"  # mutate the returned copy

    # the on-disk bank must be unaffected by mutating the returned list.
    fresh = player_bank.list_players(bank_path=bank_path)
    assert fresh[0]["turns_state"] == "active"


# -- mark_played ---------------------------------------------------------------

def test_mark_played_stamps_last_played_and_updates_turns_state(tmp_path):
    profiles_path = _write_profiles(tmp_path, _ALPHA_PROFILE)
    bank_path = tmp_path / "player_bank.json"
    player_bank.add_player("alpha", profiles_path=profiles_path, bank_path=bank_path)

    updated = player_bank.mark_played("alpha", turns_state="exhausted", bank_path=bank_path)
    assert updated["turns_state"] == "exhausted"
    assert updated["last_played"] is not None

    persisted = player_bank.list_players(bank_path=bank_path)[0]
    assert persisted["turns_state"] == "exhausted"
    assert persisted["last_played"] == updated["last_played"]


def test_mark_played_without_turns_state_leaves_it_unchanged(tmp_path):
    profiles_path = _write_profiles(tmp_path, _ALPHA_PROFILE)
    bank_path = tmp_path / "player_bank.json"
    player_bank.add_player("alpha", profiles_path=profiles_path, bank_path=bank_path)

    updated = player_bank.mark_played("alpha", bank_path=bank_path)
    assert updated["turns_state"] == "active"  # unchanged from add_player's default
    assert updated["last_played"] is not None


def test_mark_played_unknown_player_raises(tmp_path):
    bank_path = tmp_path / "player_bank.json"
    with pytest.raises(player_bank.PlayerBankError):
        player_bank.mark_played("nope", bank_path=bank_path)


# -- next_player (pure rotation helper) ------------------------------------------

def test_next_player_prefers_least_recently_played():
    bank = {
        "version": 1,
        "players": [
            {"name": "alpha", "last_played": "2026-07-18T00:00:00Z", "turns_state": "active"},
            {"name": "bravo", "last_played": "2026-07-19T00:00:00Z", "turns_state": "active"},
        ],
    }
    assert player_bank.next_player(bank) == "alpha"


def test_next_player_prioritizes_never_played_over_any_last_played():
    bank = {
        "version": 1,
        "players": [
            {"name": "alpha", "last_played": "2026-07-19T00:00:00Z", "turns_state": "active"},
            {"name": "bravo", "last_played": None, "turns_state": "active"},
        ],
    }
    assert player_bank.next_player(bank) == "bravo"


def test_next_player_skips_exhausted_players():
    bank = {
        "version": 1,
        "players": [
            {"name": "alpha", "last_played": None, "turns_state": "exhausted"},
            {"name": "bravo", "last_played": "2026-07-19T00:00:00Z", "turns_state": "active"},
        ],
    }
    assert player_bank.next_player(bank) == "bravo"


def test_next_player_returns_none_when_all_exhausted():
    bank = {
        "version": 1,
        "players": [
            {"name": "alpha", "last_played": None, "turns_state": "exhausted"},
            {"name": "bravo", "last_played": "2026-07-19T00:00:00Z", "turns_state": "exhausted"},
        ],
    }
    assert player_bank.next_player(bank) is None


def test_next_player_returns_none_for_empty_bank():
    assert player_bank.next_player({"version": 1, "players": []}) is None


def test_next_player_avoids_repeating_current_when_an_alternative_exists():
    bank = {
        "version": 1,
        "players": [
            {"name": "alpha", "last_played": "2026-07-18T00:00:00Z", "turns_state": "active"},
            {"name": "bravo", "last_played": "2026-07-19T00:00:00Z", "turns_state": "active"},
        ],
    }
    assert player_bank.next_player(bank, current="alpha") == "bravo"


def test_next_player_returns_current_again_when_no_alternative_exists():
    bank = {
        "version": 1,
        "players": [
            {"name": "alpha", "last_played": "2026-07-18T00:00:00Z", "turns_state": "active"},
        ],
    }
    assert player_bank.next_player(bank, current="alpha") == "alpha"


def test_next_player_never_touches_disk(tmp_path, monkeypatch):
    """Purity check: next_player must not import/read/write anything --
    point BANK_PATH somewhere that would explode if touched."""
    monkeypatch.setattr(player_bank, "BANK_PATH", tmp_path / "should-not-be-touched.json")
    bank = {
        "version": 1,
        "players": [{"name": "alpha", "last_played": None, "turns_state": "active"}],
    }
    assert player_bank.next_player(bank) == "alpha"
    assert not (tmp_path / "should-not-be-touched.json").exists()


# -- ensure_seeded ---------------------------------------------------------------

def test_ensure_seeded_creates_bank_from_the_named_profile(tmp_path):
    profiles_path = _write_profiles(tmp_path, _ALPHA_PROFILE)
    bank_path = tmp_path / "player_bank.json"

    result = player_bank.ensure_seeded(
        seed_profile_name="alpha", profiles_path=profiles_path, bank_path=bank_path,
    )
    assert result["name"] == "alpha"
    assert len(player_bank.list_players(bank_path=bank_path)) == 1


def test_ensure_seeded_is_idempotent_never_overwrites_an_existing_bank(tmp_path):
    profiles_path = _write_profiles(tmp_path, _ALPHA_PROFILE + _BRAVO_PROFILE)
    bank_path = tmp_path / "player_bank.json"

    player_bank.ensure_seeded(seed_profile_name="alpha", profiles_path=profiles_path, bank_path=bank_path)
    # mutate the bank so a second seed call touching it would be visible.
    player_bank.mark_played("alpha", turns_state="exhausted", bank_path=bank_path)

    result = player_bank.ensure_seeded(seed_profile_name="bravo", profiles_path=profiles_path, bank_path=bank_path)
    final = player_bank.list_players(bank_path=bank_path)
    assert len(final) == 1  # bravo was NOT added -- bank already existed
    assert final[0]["turns_state"] == "exhausted"  # untouched by the second call
    assert result == player_bank.load_bank(bank_path=bank_path)


def test_ensure_seeded_noop_when_seed_profile_is_missing(tmp_path):
    profiles_path = _write_profiles(tmp_path, '[other]\nhost="x"\nport=23\ngame_letter="F"\nhandle="H"\n')
    bank_path = tmp_path / "player_bank.json"

    result = player_bank.ensure_seeded(
        seed_profile_name="alpha", profiles_path=profiles_path, bank_path=bank_path,
    )
    assert result is None
    assert not bank_path.exists()


def test_ensure_seeded_default_profile_name_matches_the_default_convention(tmp_path):
    """No project-specific handle is baked into the source default --
    it matches profiles.toml's own [default] section convention."""
    profiles_path = _write_profiles(tmp_path, '[default]\nhost="x"\nport=23\ngame_letter="F"\nhandle="H"\n')
    bank_path = tmp_path / "player_bank.json"

    result = player_bank.ensure_seeded(profiles_path=profiles_path, bank_path=bank_path)
    assert result["name"] == "default"


# -- real project paths are never touched by these tests -------------------------

def test_module_level_bank_path_is_under_the_real_gitignored_state_dir():
    """Sanity check on the constants themselves -- doesn't touch disk."""
    assert player_bank.STATE_DIR.name == "state"
    assert player_bank.BANK_PATH.parent == player_bank.STATE_DIR
    assert player_bank.BANK_PATH.name == "player_bank.json"


# -- corrupt/malformed bank files (mack finding #3, #4, #5) -------------------

def test_load_bank_raises_on_truncated_json(tmp_path):
    bank_path = tmp_path / "player_bank.json"
    bank_path.write_text('{"version": 1, "players": [', encoding="utf-8")
    with pytest.raises(player_bank.PlayerBankError):
        player_bank.load_bank(bank_path=bank_path)


def test_load_bank_raises_on_empty_file(tmp_path):
    bank_path = tmp_path / "player_bank.json"
    bank_path.write_text("", encoding="utf-8")
    with pytest.raises(player_bank.PlayerBankError):
        player_bank.load_bank(bank_path=bank_path)


def test_load_bank_never_silently_resets_a_corrupt_file_to_empty(tmp_path):
    """The failure mode this whole finding is about: a corrupt file
    must raise, never quietly come back as `{"version": 1, "players":
    []}` -- that would be real data loss disguised as a fresh start."""
    bank_path = tmp_path / "player_bank.json"
    bank_path.write_text("not json at all {{{", encoding="utf-8")
    try:
        player_bank.load_bank(bank_path=bank_path)
    except player_bank.PlayerBankError:
        pass
    else:
        pytest.fail("expected PlayerBankError, got a silent empty bank instead")


def test_load_bank_raises_on_unsupported_version(tmp_path):
    bank_path = tmp_path / "player_bank.json"
    bank_path.write_text(json.dumps({"version": 999, "players": []}), encoding="utf-8")
    with pytest.raises(player_bank.PlayerBankError, match="999"):
        player_bank.load_bank(bank_path=bank_path)


def test_load_bank_raises_on_name_less_entry(tmp_path):
    """A required field (`name`) missing from an entry is structural
    corruption -- distinct from an optional field like `last_played`
    being absent, which is a legitimate, safely-defaulted state."""
    bank_path = tmp_path / "player_bank.json"
    bank_path.write_text(
        json.dumps({"version": 1, "players": [{"handle": "X"}]}), encoding="utf-8"
    )
    with pytest.raises(player_bank.PlayerBankError):
        player_bank.load_bank(bank_path=bank_path)


def test_next_player_tolerates_missing_optional_last_played_key(tmp_path):
    """Optional metadata (`last_played`) missing entirely -- not even
    `None` -- must be treated the same as never-played, via `.get()`,
    never a KeyError."""
    bank = {
        "version": 1,
        "players": [
            {"name": "alpha", "turns_state": "active"},  # no last_played key at all
            {"name": "bravo", "last_played": "2026-07-19T00:00:00Z", "turns_state": "active"},
        ],
    }
    assert player_bank.next_player(bank) == "alpha"


# -- orphaned .tmp cleanup on write failure (mack finding #6) ------------------

def test_save_bank_removes_orphaned_tmp_file_on_write_failure(tmp_path, monkeypatch):
    bank_path = tmp_path / "player_bank.json"
    original = {"version": 1, "players": []}
    player_bank.save_bank(original, bank_path=bank_path)

    def boom(*_a, **_kw):
        raise ValueError("simulated write-time failure")

    monkeypatch.setattr(player_bank.json, "dump", boom)

    with pytest.raises(ValueError):
        player_bank.save_bank(
            {"version": 1, "players": [{"name": "alpha"}]}, bank_path=bank_path
        )

    tmp_sibling = bank_path.with_suffix(bank_path.suffix + ".tmp")
    assert not tmp_sibling.exists(), "orphaned .tmp file left behind after a failed write"
    assert player_bank.load_bank(bank_path=bank_path) == original


# -- empty-name refusal (mack finding #7) --------------------------------------

def test_add_player_refuses_empty_name(tmp_path):
    profiles_path = _write_profiles(tmp_path, _ALPHA_PROFILE)
    bank_path = tmp_path / "player_bank.json"
    with pytest.raises(player_bank.PlayerBankError):
        player_bank.add_player("", profiles_path=profiles_path, bank_path=bank_path)
    assert not bank_path.exists()


def test_add_player_refuses_whitespace_only_name(tmp_path):
    profiles_path = _write_profiles(tmp_path, _ALPHA_PROFILE)
    bank_path = tmp_path / "player_bank.json"
    with pytest.raises(player_bank.PlayerBankError):
        player_bank.add_player("   ", profiles_path=profiles_path, bank_path=bank_path)
    assert not bank_path.exists()


# -- concurrency: lock closes the lost-update races (mack finding #1, #2) ------

def test_bank_lock_real_flock_blocks_second_acquirer_until_released(tmp_path):
    """Real flock proof -- no monkeypatch, no threads: a second, wholly
    independent open-file-description on the same lock path cannot
    take LOCK_EX while the first holds it, and can immediately after
    the first releases. This is the actual OS-level guarantee every
    other concurrency test in this section relies on."""
    bank_path = tmp_path / "player_bank.json"
    lock_path = player_bank._lock_path(bank_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    fd1 = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
    fcntl.flock(fd1, fcntl.LOCK_EX)
    try:
        fd2 = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
        try:
            with pytest.raises(BlockingIOError):
                fcntl.flock(fd2, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            os.close(fd2)
    finally:
        fcntl.flock(fd1, fcntl.LOCK_UN)
        os.close(fd1)

    fd3 = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd3, fcntl.LOCK_EX | fcntl.LOCK_NB)  # must not raise now
        fcntl.flock(fd3, fcntl.LOCK_UN)
    finally:
        os.close(fd3)


def test_concurrent_add_player_never_loses_an_update_trace1_bravo_vanishes(tmp_path, monkeypatch):
    """Mack's Trace-1: without a lock spanning the FULL load-mutate-save
    critical section, two concurrent add_player calls can race so the
    second caller's save (built from a stale, pre-first-caller load)
    silently overwrites the first caller's write -- one player just
    vanishes. Real threads + a monkeypatch hook pause the alpha-adding
    thread mid-critical-section (still holding the real flock) so the
    bravo-adding thread's own lock acquisition is forced to actually
    block until release, proving the fix."""
    profiles_path = _write_profiles(tmp_path, _ALPHA_PROFILE + _BRAVO_PROFILE)
    bank_path = tmp_path / "player_bank.json"

    real_save_bank = player_bank.save_bank
    alpha_holding = threading.Event()
    release_alpha = threading.Event()

    def hook(bank, bank_path=None):
        if any(p["name"] == "alpha" for p in bank["players"]):
            alpha_holding.set()
            assert release_alpha.wait(timeout=5), "test deadlocked waiting for release"
        return real_save_bank(bank, bank_path)

    monkeypatch.setattr(player_bank, "save_bank", hook)

    errors = []

    def add(name):
        try:
            player_bank.add_player(name, profiles_path=profiles_path, bank_path=bank_path)
        except Exception as e:
            errors.append(e)

    t_alpha = threading.Thread(target=add, args=("alpha",))
    t_bravo = threading.Thread(target=add, args=("bravo",))

    t_alpha.start()
    assert alpha_holding.wait(timeout=5), "alpha thread never reached its critical section"
    t_bravo.start()
    time.sleep(0.2)  # give bravo's add_player a real chance to attempt (and block on) the lock
    release_alpha.set()

    t_alpha.join(timeout=5)
    t_bravo.join(timeout=5)

    assert not errors, f"unexpected error(s) from concurrent add_player: {errors}"
    names = {p["name"] for p in player_bank.list_players(bank_path=bank_path)}
    assert names == {"alpha", "bravo"}, "lost update -- one add_player call was silently discarded"


def test_concurrent_mark_played_never_reverts_turns_state_trace2_mark_reverts(tmp_path, monkeypatch):
    """Mack's Trace-2: a caller that merely re-stamps last_played
    (turns_state=None, "leave unchanged") loads a STALE pre-exhaustion
    copy, then a concurrent caller exhausts the player and fully
    commits, then the first caller finally saves ITS stale copy --
    silently REVERTING the exhaustion mark it never saw. The hook
    pauses the FIRST caller (restamp) right after its own load (so it's
    holding a stale, pre-exhaustion in-memory copy) for as long as it
    takes the second caller (exhaust) to run to completion in between.
    Without the lock, exhaust's full run-to-completion happens in that
    gap and gets clobbered when restamp resumes and saves; with the
    lock, restamp's load and save are one atomic unit, so exhaust can
    only ever run before or after it, never straddling it."""
    profiles_path = _write_profiles(tmp_path, _ALPHA_PROFILE)
    bank_path = tmp_path / "player_bank.json"
    player_bank.add_player("alpha", profiles_path=profiles_path, bank_path=bank_path)

    real_load_bank = player_bank.load_bank
    restamp_paused = threading.Event()
    release_restamp = threading.Event()

    def load_hook(bank_path=None):
        data = real_load_bank(bank_path)
        if not restamp_paused.is_set():
            restamp_paused.set()  # only the FIRST caller (restamp) pauses
            assert release_restamp.wait(timeout=5), "test deadlocked waiting for release"
        return data

    monkeypatch.setattr(player_bank, "load_bank", load_hook)

    errors = []

    def restamp():
        try:
            player_bank.mark_played("alpha", bank_path=bank_path)
        except Exception as e:
            errors.append(e)

    def exhaust():
        try:
            player_bank.mark_played("alpha", turns_state="exhausted", bank_path=bank_path)
        except Exception as e:
            errors.append(e)

    t_restamp = threading.Thread(target=restamp)
    t_exhaust = threading.Thread(target=exhaust)

    t_restamp.start()
    assert restamp_paused.wait(timeout=5), "restamp thread never reached its paused load"
    t_exhaust.start()
    time.sleep(0.2)  # give exhaust a real chance to run (or block on the lock)
    release_restamp.set()

    t_restamp.join(timeout=5)
    t_exhaust.join(timeout=5)

    assert not errors, f"unexpected error(s) from concurrent mark_played: {errors}"
    final = player_bank.list_players(bank_path=bank_path)[0]
    assert final["turns_state"] == "exhausted", "lost update -- exhaustion mark was silently reverted"


def test_concurrent_ensure_seeded_toctou_never_double_seeds(tmp_path, monkeypatch):
    """Mack's ensure_seeded TOCTOU: two first-run callers (seeding
    DIFFERENT profiles, so a lost update is observable) can each
    observe "no bank file yet"; without the existence re-check
    happening INSIDE the lock, the second caller's save silently
    discards the first's. With the fix, the second caller's re-check
    only happens after it acquires the lock -- by which point the
    first has already committed, so it takes the already-exists branch
    instead of re-seeding from scratch."""
    profiles_path = _write_profiles(tmp_path, _ALPHA_PROFILE + _BRAVO_PROFILE)
    bank_path = tmp_path / "player_bank.json"

    real_save_bank = player_bank.save_bank
    first_holding = threading.Event()
    release_first = threading.Event()

    def hook(bank, bank_path=None):
        first_holding.set()
        assert release_first.wait(timeout=5), "test deadlocked waiting for release"
        return real_save_bank(bank, bank_path)

    monkeypatch.setattr(player_bank, "save_bank", hook)

    errors = []

    def seed(name):
        try:
            player_bank.ensure_seeded(
                seed_profile_name=name, profiles_path=profiles_path, bank_path=bank_path
            )
        except Exception as e:
            errors.append(e)

    t1 = threading.Thread(target=seed, args=("alpha",))
    t2 = threading.Thread(target=seed, args=("bravo",))

    t1.start()
    assert first_holding.wait(timeout=5), "first seed thread never reached its critical section"
    t2.start()
    time.sleep(0.2)  # give the second seed() a real chance to attempt (and block on) the lock
    release_first.set()

    t1.join(timeout=5)
    t2.join(timeout=5)

    assert not errors, f"unexpected error(s) from concurrent ensure_seeded: {errors}"
    final = player_bank.list_players(bank_path=bank_path)
    assert len(final) == 1, "TOCTOU -- the bank was seeded twice instead of once"
    assert final[0]["name"] == "alpha"  # whichever call actually held the lock first wins


# -- acceptance bar: genuine real-writer concurrency, no monkeypatch synchronization ---

def test_real_concurrent_add_player_across_many_threads_never_loses_an_update(tmp_path):
    """The acceptance bar (hub-sharpened): actual OS-level concurrency,
    no monkeypatch hooks, no artificial pauses -- just N real threads
    hammering the real public API against ONE shared bank file at the
    same instant (a `threading.Barrier` maximizes overlap). The lock
    must guarantee zero lost updates regardless of how the OS actually
    schedules them. The deterministic Trace-1 test above documents the
    exact failure shape; this test is the empirical proof."""
    n = 16
    names = [f"player{i}" for i in range(n)]
    profiles_body = "".join(
        f'[player{i}]\nhost="host{i}.test.example"\nport=23\ngame_letter="F"\nhandle="H{i}"\n'
        for i in range(n)
    )
    profiles_path = _write_profiles(tmp_path, profiles_body)
    bank_path = tmp_path / "player_bank.json"

    errors = []
    barrier = threading.Barrier(n)

    def worker(name):
        try:
            barrier.wait(timeout=5)  # release all N threads at (as close to) the same instant
            player_bank.add_player(name, profiles_path=profiles_path, bank_path=bank_path)
        except Exception as e:
            errors.append((name, e))

    threads = [threading.Thread(target=worker, args=(name,)) for name in names]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert not errors, f"unexpected error(s) from real concurrent add_player: {errors}"
    final_names = {p["name"] for p in player_bank.list_players(bank_path=bank_path)}
    assert final_names == set(names), (
        f"lost update(s) under real concurrency -- expected {n} players, "
        f"got {len(final_names)}: missing {set(names) - final_names}"
    )


def test_real_concurrent_mark_played_across_many_threads_never_loses_an_update(tmp_path):
    """Same acceptance bar, for `mark_played`: N real threads each
    stamping a DIFFERENT already-existing player's `turns_state`
    concurrently in the same shared bank file. Without the lock, a
    losing thread's stale whole-bank copy silently reverts every
    sibling's concurrent change it didn't itself make; with the lock,
    every one of the N distinct marks must survive."""
    n = 16
    names = [f"player{i}" for i in range(n)]
    profiles_body = "".join(
        f'[player{i}]\nhost="host{i}.test.example"\nport=23\ngame_letter="F"\nhandle="H{i}"\n'
        for i in range(n)
    )
    profiles_path = _write_profiles(tmp_path, profiles_body)
    bank_path = tmp_path / "player_bank.json"
    for name in names:
        player_bank.add_player(name, profiles_path=profiles_path, bank_path=bank_path)

    errors = []
    barrier = threading.Barrier(n)

    def worker(name):
        try:
            barrier.wait(timeout=5)
            player_bank.mark_played(name, turns_state=f"state-{name}", bank_path=bank_path)
        except Exception as e:
            errors.append((name, e))

    threads = [threading.Thread(target=worker, args=(name,)) for name in names]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert not errors, f"unexpected error(s) from real concurrent mark_played: {errors}"
    final = {p["name"]: p for p in player_bank.list_players(bank_path=bank_path)}
    lost = [
        name for name in names
        if final[name]["turns_state"] != f"state-{name}" or final[name]["last_played"] is None
    ]
    assert not lost, f"lost update(s) under real concurrency for: {lost}"
