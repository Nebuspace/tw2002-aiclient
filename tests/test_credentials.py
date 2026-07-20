"""Secure credential store tests (DESIGN-v2 B2) — no network, tmp_path
only, never touches the real config/ directory."""

import json
import os
import stat

import pytest

from twclient import credentials


def _write_profiles(tmp_path, body):
    path = tmp_path / "profiles.toml"
    path.write_text(body, encoding="utf-8")
    return path


def test_load_profile_reads_required_fields(tmp_path):
    p = _write_profiles(
        tmp_path,
        '[default]\nhost = "example.com"\nport = 23\ngame_letter = "F"\nhandle = "AEGIS"\n',
    )
    profile = credentials.load_profile("default", profiles_path=p)
    assert profile.host == "example.com"
    assert profile.port == 23
    assert profile.game_letter == "F"
    assert profile.handle == "AEGIS"
    # ship/planet default deterministically from handle when unset.
    assert profile.ship_name == "AEGISShip"
    assert profile.planet_name == "AEGISWorld"


def test_load_profile_honors_optional_ship_planet_overrides(tmp_path):
    p = _write_profiles(
        tmp_path,
        '[default]\nhost = "example.com"\nport = 23\ngame_letter = "F"\nhandle = "AEGIS"\n'
        'ship_name = "Vantage"\nplanet_name = "Anchorage"\n',
    )
    profile = credentials.load_profile("default", profiles_path=p)
    assert profile.ship_name == "Vantage"
    assert profile.planet_name == "Anchorage"


def test_load_profile_missing_name_raises(tmp_path):
    p = _write_profiles(tmp_path, '[other]\nhost = "x"\nport = 23\ngame_letter = "F"\nhandle = "H"\n')
    with pytest.raises(credentials.CredentialError):
        credentials.load_profile("default", profiles_path=p)


def test_load_profile_incomplete_raises(tmp_path):
    p = _write_profiles(tmp_path, '[default]\nhost = "x"\nport = 23\n')
    with pytest.raises(credentials.CredentialError):
        credentials.load_profile("default", profiles_path=p)


# -- WO-MS-4: allow_register policy gate -------------------------------------

def test_allow_register_defaults_false_for_every_pre_existing_profile_shape(tmp_path):
    p = _write_profiles(
        tmp_path,
        '[default]\nhost = "example.com"\nport = 23\ngame_letter = "F"\nhandle = "AEGIS"\n',
    )
    profile = credentials.load_profile("default", profiles_path=p)
    assert profile.allow_register is False


def test_allow_register_true_is_read_from_toml(tmp_path):
    p = _write_profiles(
        tmp_path,
        '[default]\nhost = "example.com"\nport = 23\ngame_letter = "F"\nhandle = "AEGIS"\nallow_register = true\n',
    )
    profile = credentials.load_profile("default", profiles_path=p)
    assert profile.allow_register is True


def test_missing_handle_raises_unless_allow_register_is_set(tmp_path):
    """A normal profile still requires `handle` exactly as before this
    change -- only an allow_register=true profile may omit it (the
    name-bank rider draws one fresh per attempt instead)."""
    p = _write_profiles(tmp_path, '[default]\nhost = "example.com"\nport = 23\ngame_letter = "F"\n')
    with pytest.raises(credentials.CredentialError, match=r"profile_incomplete.*handle"):
        credentials.load_profile("default", profiles_path=p)


def test_missing_handle_is_allowed_when_allow_register_is_true(tmp_path):
    p = _write_profiles(
        tmp_path,
        '[default]\nhost = "example.com"\nport = 23\ngame_letter = "F"\nallow_register = true\n',
    )
    profile = credentials.load_profile("default", profiles_path=p)
    assert profile.handle is None
    assert profile.ship_name is None  # never derives "NoneShip" from a blank handle
    assert profile.planet_name is None
    assert profile.allow_register is True


def test_profile_explicit_flags_reflect_what_the_caller_actually_passed():
    """The name-bank rider (twclient/name_bank.py) distinguishes an
    explicitly-set field from a defaulted/blank one via these flags --
    they must reflect the raw constructor argument, before any
    defaulting, not the post-defaulting value."""
    explicit = credentials.Profile(
        name="p", host="h", port=23, game_letter="F", handle="AEGIS", ship_name="Vantage", planet_name="Anchorage",
    )
    assert (explicit.handle_explicit, explicit.ship_name_explicit, explicit.planet_name_explicit) == (True, True, True)

    handle_only = credentials.Profile(name="p", host="h", port=23, game_letter="F", handle="AEGIS")
    assert handle_only.handle_explicit is True
    # ship_name/planet_name were DEFAULTED from handle, not explicitly given.
    assert (handle_only.ship_name_explicit, handle_only.planet_name_explicit) == (False, False)
    assert (handle_only.ship_name, handle_only.planet_name) == ("AEGISShip", "AEGISWorld")

    blank = credentials.Profile(name="p", host="h", port=23, game_letter="F", allow_register=True)
    assert (blank.handle_explicit, blank.ship_name_explicit, blank.planet_name_explicit) == (False, False, False)


def test_list_profiles(tmp_path):
    p = _write_profiles(
        tmp_path,
        '[default]\nhost="x"\nport=23\ngame_letter="F"\nhandle="H"\n'
        '[alt]\nhost="y"\nport=23\ngame_letter="A"\nhandle="J"\n',
    )
    assert credentials.list_profiles(profiles_path=p) == ["alt", "default"]


def test_get_password_returns_none_when_nothing_saved(tmp_path, monkeypatch):
    monkeypatch.delenv("TW2002_PASSWORD_DEFAULT", raising=False)
    secrets_path = tmp_path / "secrets.json"
    assert credentials.get_password("default", secrets_path=secrets_path) is None


def test_save_then_get_password_roundtrips(tmp_path, monkeypatch):
    monkeypatch.delenv("TW2002_PASSWORD_DEFAULT", raising=False)
    secrets_path = tmp_path / "secrets.json"
    credentials.save_password("default", "abc12345", secrets_path=secrets_path)
    assert credentials.get_password("default", secrets_path=secrets_path) == "abc12345"


def test_secrets_file_is_chmod_600(tmp_path):
    secrets_path = tmp_path / "secrets.json"
    credentials.save_password("default", "abc12345", secrets_path=secrets_path)
    mode = stat.S_IMODE(os.stat(secrets_path).st_mode)
    assert mode == 0o600
    assert credentials.secrets_file_mode_ok(secrets_path=secrets_path)


def test_env_var_takes_precedence_over_secrets_file(tmp_path, monkeypatch):
    secrets_path = tmp_path / "secrets.json"
    credentials.save_password("default", "from-file", secrets_path=secrets_path)
    monkeypatch.setenv("TW2002_PASSWORD_DEFAULT", "from-env")
    assert credentials.get_password("default", secrets_path=secrets_path) == "from-env"


def test_env_var_name_sanitizes_profile_name(tmp_path, monkeypatch):
    monkeypatch.setenv("TW2002_PASSWORD_MY_LANE_2", "envpw")
    secrets_path = tmp_path / "secrets.json"
    assert credentials.get_password("my-lane-2", secrets_path=secrets_path) == "envpw"


def test_generated_password_is_short_alnum_and_csprng_varies():
    seen = {credentials.generate_password() for _ in range(20)}
    assert len(seen) == 20  # no collisions across 20 draws -- real randomness
    for pw in seen:
        assert len(pw) == credentials._GENERATED_PASSWORD_LEN
        assert pw.isalnum()


def test_save_password_never_writes_plaintext_to_profiles_toml(tmp_path):
    """The password must land ONLY in the secrets file, never anywhere
    near the (potentially-shared/less-locked-down) profiles.toml."""
    p = _write_profiles(
        tmp_path, '[default]\nhost="x"\nport=23\ngame_letter="F"\nhandle="H"\n'
    )
    secrets_path = tmp_path / "secrets.json"
    credentials.save_password("default", "supersecretpw", secrets_path=secrets_path)
    assert "supersecretpw" not in p.read_text(encoding="utf-8")


def test_secrets_json_shape(tmp_path):
    secrets_path = tmp_path / "secrets.json"
    credentials.save_password("default", "abc12345", secrets_path=secrets_path)
    data = json.loads(secrets_path.read_text(encoding="utf-8"))
    assert data == {"default": {"password": "abc12345"}}


def test_save_password_preserves_other_profiles(tmp_path):
    secrets_path = tmp_path / "secrets.json"
    credentials.save_password("a", "pw-a", secrets_path=secrets_path)
    credentials.save_password("b", "pw-b", secrets_path=secrets_path)
    assert credentials.get_password("a", secrets_path=secrets_path) == "pw-a"
    assert credentials.get_password("b", secrets_path=secrets_path) == "pw-b"
