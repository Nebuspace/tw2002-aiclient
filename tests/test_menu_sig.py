"""menu_sig.menu_signature — the shared, pure signature primitive.

Byte-identical-move guard: this hash is a persisted map key
(game_knowledge nodes are keyed by it), so any of these breaking is a
real regression, not a style nit.
"""

from twclient import menu_crawler
from twclient.menu_sig import menu_signature

SCREEN = "Command [TL=00:00:00]:? \n\n  <A> Amplifier\n  <B> Bridge\n  <Q> Quit\n"


def test_deterministic():
    assert menu_signature(SCREEN) == menu_signature(SCREEN)


def test_whitespace_normalized():
    padded = "\n\n" + "\n".join(line + "   " for line in SCREEN.splitlines()) + "\n\n\n"
    assert menu_signature(padded) == menu_signature(SCREEN)


def test_different_content_different_hash():
    other = SCREEN.replace("Bridge", "Bay")
    assert menu_signature(other) != menu_signature(SCREEN)


def test_hash_is_16_char_hex():
    sig = menu_signature(SCREEN)
    assert len(sig) == 16
    int(sig, 16)  # raises ValueError if not valid hex


def test_byte_identical_to_current_algorithm():
    # Hardcoded expected value, computed once from the exact algorithm
    # this module moved verbatim out of menu_crawler._signature. Any
    # future algorithm change must break this test loudly -- a silent
    # hash drift orphans every already-persisted menu-map lookup.
    assert menu_signature(SCREEN) == "840a49a3aab0b5fd"


def test_menu_crawler_alias_is_menu_signature():
    assert menu_crawler._signature is menu_signature
