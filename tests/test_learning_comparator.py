"""Transition comparator — offline unit tests."""

from twclient.learning.comparator import compare_transition


def test_exploratory_transition():
    r = compare_transition("aaa", "bbb", prior_confidence=0.0)
    assert r["matched"] is True
    assert r["observed_transition"] == "bbb"
    assert r["confidence_delta"] == 0.1
    assert r["new_confidence"] == 0.1


def test_exploratory_same_screen():
    r = compare_transition("aaa", "aaa")
    assert r["matched"] is False
    assert r["confidence_delta"] == 0.0


def test_expected_match():
    r = compare_transition("a", "b", expected_transition="b", prior_confidence=0.5)
    assert r["matched"] is True
    assert r["new_confidence"] == 0.7


def test_expected_mismatch_clamps_floor():
    r = compare_transition("a", "c", expected_transition="b", prior_confidence=0.05)
    assert r["matched"] is False
    assert r["new_confidence"] == 0.0


def test_expected_same_screen_mismatch():
    r = compare_transition("a", "a", expected_transition="b", prior_confidence=0.5)
    assert r["matched"] is False
    assert "same screen" in r["reason"]


def test_confidence_ceiling():
    r = compare_transition("a", "b", expected_transition="b", prior_confidence=0.95)
    assert r["new_confidence"] == 1.0
