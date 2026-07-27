"""Credentials module tests (reborn: tw2002_aiclient.session.credentials).

Replaced the stale ``twclient`` imports + archive-API tests that no longer
exist in the reborn module (WO-PASSWORD-MINT-CANON).  This file focuses on
the canonical password mint; deeper store-honesty tests live in
``test_credentials_store_honesty.py``.
"""

import pytest

import tw2002_aiclient.session.credentials as credentials


# ---------------------------------------------------------------------------
# generate_password — canonical mint
# ---------------------------------------------------------------------------


def test_generated_password_is_short_alnum_and_csprng_varies():
    seen = {credentials.generate_password() for _ in range(20)}
    assert len(seen) == 20  # no collisions across 20 draws — real CSPRNG
    for pw in seen:
        assert len(pw) == credentials._GENERATED_PASSWORD_LEN
        assert pw.isalnum()


def test_generate_password_default_length_is_8():
    pw = credentials.generate_password()
    assert len(pw) == 8


def test_generate_password_length_param_accepted_within_bounds():
    pw = credentials.generate_password(length=1)
    assert len(pw) == 1
    assert pw.isalnum()

    pw7 = credentials.generate_password(length=7)
    assert len(pw7) == 7
    assert pw7.isalnum()


def test_generate_password_rejects_zero_and_negative():
    with pytest.raises(ValueError):
        credentials.generate_password(0)
    with pytest.raises(ValueError):
        credentials.generate_password(-1)


def test_generate_password_rejects_above_8():
    with pytest.raises(ValueError):
        credentials.generate_password(9)
    with pytest.raises(ValueError):
        credentials.generate_password(100)
