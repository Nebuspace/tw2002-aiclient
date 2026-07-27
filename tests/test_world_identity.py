"""World identity tests (TW-06) -- pure string derivation, no I/O."""

import pytest

from tw2002_aiclient import world_identity


class _FakeProfile:
    def __init__(self, host, game_letter, handle):
        self.host = host
        self.game_letter = game_letter
        self.handle = handle


# -- determinism ---------------------------------------------------------

def test_world_id_is_deterministic_for_the_same_inputs():
    a = world_identity.world_id("trade.example.com", "A", "CAPTAIN")
    b = world_identity.world_id("trade.example.com", "A", "CAPTAIN")
    assert a == b


def test_world_id_is_a_string_and_filesystem_safe():
    wid = world_identity.world_id("trade.example.com", "A", "CAPTAIN")
    assert isinstance(wid, str)
    # No path separators or other characters a filesystem component would choke on.
    assert "/" not in wid
    assert "\\" not in wid
    assert "\0" not in wid


def test_world_id_host_is_case_insensitive():
    """Network hostnames are conventionally case-insensitive -- two
    profiles differing only in host casing must resolve to the SAME
    world, not two spurious ones."""
    a = world_identity.world_id("Trade.Example.COM", "A", "CAPTAIN")
    b = world_identity.world_id("trade.example.com", "A", "CAPTAIN")
    assert a == b


# -- distinctness (the anti-galaxy-bleed guarantee) -----------------------

def test_world_id_distinct_hosts_produce_distinct_ids():
    a = world_identity.world_id("host-one.example", "A", "CAPTAIN")
    b = world_identity.world_id("host-two.example", "A", "CAPTAIN")
    assert a != b


def test_world_id_distinct_game_letters_produce_distinct_ids():
    a = world_identity.world_id("trade.example.com", "A", "CAPTAIN")
    b = world_identity.world_id("trade.example.com", "B", "CAPTAIN")
    assert a != b


def test_world_id_distinct_handles_produce_distinct_ids():
    """The core canon requirement: two different characters registered
    on the same host+game_letter are two different worlds (a fresh
    registration produces a fresh generated galaxy even on the same
    game letter)."""
    a = world_identity.world_id("trade.example.com", "A", "ALPHA")
    b = world_identity.world_id("trade.example.com", "A", "BRAVO")
    assert a != b


def test_world_id_handle_case_is_preserved_not_folded():
    """Unlike host, handle is an exact in-game identifier where case
    can be a real distinction -- not free-form user text to normalize."""
    a = world_identity.world_id("trade.example.com", "A", "Captain")
    b = world_identity.world_id("trade.example.com", "A", "CAPTAIN")
    assert a != b


# -- world_id_from_profile -------------------------------------------------

def test_world_id_from_profile_matches_direct_call():
    profile = _FakeProfile(host="trade.example.com", game_letter="A", handle="CAPTAIN")
    assert world_identity.world_id_from_profile(profile) == world_identity.world_id(
        "trade.example.com", "A", "CAPTAIN"
    )


def test_world_id_from_profile_accepts_duck_typed_object():
    """Works against any object exposing .host/.game_letter/.handle --
    not hard-wired to credentials.Profile specifically."""
    class Duck:
        host = "duck.example.com"
        game_letter = "Z"
        handle = "QUACK"

    assert world_identity.world_id_from_profile(Duck()) == world_identity.world_id(
        "duck.example.com", "Z", "QUACK"
    )


# -- structural validation --------------------------------------------------

@pytest.mark.parametrize("bad_host", [None, "", "   "])
def test_world_id_refuses_empty_or_missing_host(bad_host):
    with pytest.raises(world_identity.WorldIdentityError):
        world_identity.world_id(bad_host, "A", "CAPTAIN")


@pytest.mark.parametrize("bad_game_letter", [None, "", "  "])
def test_world_id_refuses_empty_or_missing_game_letter(bad_game_letter):
    with pytest.raises(world_identity.WorldIdentityError):
        world_identity.world_id("trade.example.com", bad_game_letter, "CAPTAIN")


@pytest.mark.parametrize("bad_handle", [None, "", "  "])
def test_world_id_refuses_empty_or_missing_handle(bad_handle):
    with pytest.raises(world_identity.WorldIdentityError):
        world_identity.world_id("trade.example.com", "A", bad_handle)


def test_world_id_sanitizes_punctuation_without_colliding_common_cases():
    """Distinct raw handles that only differ by trailing punctuation
    must not collapse to the same sanitized slug (no stripping of
    trailing underscores after sanitizing)."""
    plain = world_identity.world_id("trade.example.com", "A", "john")
    punctuated = world_identity.world_id("trade.example.com", "A", "john!")
    assert plain != punctuated
