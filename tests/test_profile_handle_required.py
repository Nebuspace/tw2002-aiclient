"""A profile must carry a handle — `allow_register` does not excuse it.

`login.py`'s Wave-3 cuts note is the contract: "A profile must set its own
`handle` (or opt into `allow_register` with a handle it's fine reusing every
run); no drawn-identity retry loop exists yet" — `register_with_name_bank` /
`name_bank.py` were never ported, so **nothing in this tree can invent a
name**.

`_load_profile` used to accept a handle-less profile when `allow_register`
was set. That profile then died four layers down: the blank-reject retry
(WO-MICRO-LOGIN-BLANK-REJECT) answers a rejecting outer name gate with
`profile.handle`, which was `None`, reaching `connection.send_text` and
surfacing as `internal_error:AttributeError`. Reproduced live against
twgs.microblaster.net while registering a sacrificial profile, 2026-07-27.

Refusing at load turns a crash-on-the-wire into a config error before a
socket is opened.
"""

from __future__ import annotations

import pytest

from tw2002_aiclient.session import credentials, protocol


def _profiles(tmp_path, monkeypatch, body: str):
    p = tmp_path / "profiles.toml"
    p.write_text(body, encoding="utf-8")
    monkeypatch.setattr(credentials, "PROFILES_PATH", p, raising=False)
    return p


COMPLETE = """
[good]
handle = "Pathfind"
host = "127.0.0.1"
port = 2002
game_letter = "A"
allow_register = true
"""

NO_HANDLE_REGISTERING = """
[registering]
host = "127.0.0.1"
port = 2002
game_letter = "A"
allow_register = true
"""

NO_HANDLE_PLAIN = """
[plain]
host = "127.0.0.1"
port = 2002
game_letter = "A"
allow_register = false
"""


def test_a_complete_profile_still_loads(tmp_path, monkeypatch):
    _profiles(tmp_path, monkeypatch, COMPLETE)
    profile, err = protocol._load_profile("good")
    assert err is None, err
    assert profile.handle == "Pathfind"
    assert profile.allow_register is True


def test_allow_register_does_not_excuse_a_missing_handle(tmp_path, monkeypatch):
    """THE pin. Nothing in this tree can draw a name, so a registering
    profile without a handle is unusable — and used to fail on the wire
    instead of at load."""
    _profiles(tmp_path, monkeypatch, NO_HANDLE_REGISTERING)
    profile, err = protocol._load_profile("registering")
    assert profile is None
    assert "missing" in err and "handle" in err


def test_a_plain_profile_without_a_handle_is_still_refused(tmp_path, monkeypatch):
    """Unchanged behaviour — pinned so the fix is known to have narrowed
    acceptance in exactly one direction."""
    _profiles(tmp_path, monkeypatch, NO_HANDLE_PLAIN)
    profile, err = protocol._load_profile("plain")
    assert profile is None
    assert "handle" in err


def test_the_refusal_is_typed_and_names_the_profile(tmp_path, monkeypatch):
    """`profile_incomplete:<name>:missing=[...]` — the operator has to be
    able to find which profile in their file is wrong."""
    _profiles(tmp_path, monkeypatch, NO_HANDLE_REGISTERING)
    _profile, err = protocol._load_profile("registering")
    assert err.startswith("profile_incomplete:")
    assert "registering" in err


def test_a_blank_handle_counts_as_missing(tmp_path, monkeypatch):
    """`handle = ""` is not a handle. Sending an empty string to the module's
    character prompt is a different failure than refusing here, and a config
    with a placeholder empty string is a config the operator has not finished."""
    _profiles(tmp_path, monkeypatch, COMPLETE.replace('"Pathfind"', '""'))
    profile, err = protocol._load_profile("good")
    assert profile is None
    assert "handle" in err


def test_a_missing_game_letter_is_still_reported_too(tmp_path, monkeypatch):
    """The `missing` list must not have become handle-only."""
    body = COMPLETE.replace('game_letter = "A"\n', "")
    _profiles(tmp_path, monkeypatch, body)
    profile, err = protocol._load_profile("good")
    assert profile is None
    assert "game_letter" in err
