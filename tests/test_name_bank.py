"""Name bank tests (WO-MS-4 rider) -- no network, tmp_path only."""

import random

import pytest

from twclient import name_bank
from twclient.credentials import Profile

from .conftest import FAKE_HOST, FAKE_PORT


def _write_bank(tmp_path, handles=("Dice",), ships=("Vantage Holdings",), planets=("Meridian Prime",)):
    path = tmp_path / "name_bank.toml"
    fmt = lambda vals: ", ".join(f'"{v}"' for v in vals)
    path.write_text(f"[names]\nhandles = [{fmt(handles)}]\nships = [{fmt(ships)}]\nplanets = [{fmt(planets)}]\n")
    return path


def _bare_profile(handle=None, ship_name=None, planet_name=None, allow_register=True):
    return Profile(
        name="crawler", host=FAKE_HOST, port=FAKE_PORT, game_letter="F", handle=handle,
        ship_name=ship_name, planet_name=planet_name, allow_register=allow_register,
    )


# -- the real bank file ------------------------------------------------------

def test_real_name_bank_loads_and_is_well_formed():
    bank = name_bank.load_name_bank()
    for key in ("handles", "ships", "planets"):
        assert len(bank[key]) > 0
        for value in bank[key]:
            assert isinstance(value, str) and value.strip()
            # TWGS' own registration prompts cap ship/planet names at 30
            # letters ("(30 letters)") -- a bank entry that silently gets
            # truncated/rejected server-side defeats the point of drawing
            # from it.
            assert len(value) <= 30


def test_real_name_bank_path_points_at_tracked_data_file():
    assert name_bank.NAME_BANK_PATH.name == "name_bank.toml"
    assert name_bank.NAME_BANK_PATH.parent.name == "data"
    assert name_bank.NAME_BANK_PATH.exists()


# -- load_name_bank -----------------------------------------------------------

def test_load_name_bank_missing_file_raises(tmp_path):
    with pytest.raises(name_bank.NameBankError, match="name_bank_not_found"):
        name_bank.load_name_bank(path=tmp_path / "does_not_exist.toml")


def test_load_name_bank_missing_section_raises(tmp_path):
    path = tmp_path / "name_bank.toml"
    path.write_text('[names]\nhandles = ["Dice"]\nships = ["Ship"]\n')  # planets omitted
    with pytest.raises(name_bank.NameBankError, match=r"name_bank_incomplete.*planets"):
        name_bank.load_name_bank(path=path)


def test_load_name_bank_returns_the_three_lists(tmp_path):
    path = _write_bank(tmp_path, handles=("A", "B"), ships=("ShipA",), planets=("PlanetA", "PlanetB"))
    bank = name_bank.load_name_bank(path=path)
    assert bank == {"handles": ["A", "B"], "ships": ["ShipA"], "planets": ["PlanetA", "PlanetB"]}


# -- resolve_bank_identity ----------------------------------------------------

def test_resolve_bank_identity_draws_all_three_when_none_explicit(tmp_path):
    path = _write_bank(tmp_path, handles=("OnlyHandle",), ships=("OnlyShip",), planets=("OnlyPlanet",))
    profile = _bare_profile()  # handle/ship_name/planet_name all None
    handle, ship_name, planet_name = name_bank.resolve_bank_identity(profile, path=path)
    assert (handle, ship_name, planet_name) == ("OnlyHandle", "OnlyShip", "OnlyPlanet")


def test_resolve_bank_identity_explicit_handle_always_wins(tmp_path):
    """Per-field, not all-or-nothing: pinning `handle` alone does NOT also
    pin ship_name/planet_name -- credentials.py's "<handle>Ship" default
    is a Profile-level convenience for OTHER (non-bank-draw) callers, but
    it isn't "explicit" from resolve_bank_identity's point of view (its
    `*_explicit` flag is only True when the CALLER passed a concrete
    value). Leaving ship_name/planet_name unset still bank-draws them
    even though handle is pinned."""
    path = _write_bank(tmp_path, handles=("BankHandle",), ships=("BankShip",), planets=("BankPlanet",))
    profile = _bare_profile(handle="Pinned")
    handle, ship_name, planet_name = name_bank.resolve_bank_identity(profile, path=path)
    assert handle == "Pinned"
    assert ship_name == "BankShip"
    assert planet_name == "BankPlanet"


def test_resolve_bank_identity_explicit_ship_and_planet_names_also_win(tmp_path):
    path = _write_bank(tmp_path, handles=("BankHandle",), ships=("BankShip",), planets=("BankPlanet",))
    profile = _bare_profile(handle="Pinned", ship_name="PinnedShip", planet_name="PinnedWorld")
    handle, ship_name, planet_name = name_bank.resolve_bank_identity(profile, path=path)
    assert (handle, ship_name, planet_name) == ("Pinned", "PinnedShip", "PinnedWorld")


def test_resolve_bank_identity_per_field_override_mixes_pinned_and_drawn(tmp_path):
    """A profile may pin ONE field while leaving the others to the bank --
    per-field, not all-or-nothing."""
    path = _write_bank(tmp_path, handles=("BankHandle",), ships=("BankShip",), planets=("BankPlanet",))
    profile = _bare_profile(handle=None, ship_name="PinnedShip", planet_name=None)
    handle, ship_name, planet_name = name_bank.resolve_bank_identity(profile, path=path)
    assert handle == "BankHandle"
    assert ship_name == "PinnedShip"  # never overridden by the bank
    assert planet_name == "BankPlanet"


def test_resolve_bank_identity_is_deterministic_with_a_seeded_rng(tmp_path):
    path = _write_bank(tmp_path, handles=("A", "B", "C", "D"), ships=("S1", "S2"), planets=("P1", "P2"))
    profile = _bare_profile()
    result_1 = name_bank.resolve_bank_identity(profile, rng=random.Random(42), path=path)
    result_2 = name_bank.resolve_bank_identity(profile, rng=random.Random(42), path=path)
    assert result_1 == result_2  # same seed -> same draw, proving rng is genuinely used


def test_resolve_bank_identity_missing_bank_propagates_name_bank_error(tmp_path):
    profile = _bare_profile()
    with pytest.raises(name_bank.NameBankError):
        name_bank.resolve_bank_identity(profile, path=tmp_path / "nope.toml")
