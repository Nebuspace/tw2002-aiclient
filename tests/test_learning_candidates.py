"""Candidate generation — offline unit tests."""

from twclient.learning.candidates import propose_candidates


def test_empty_known_actions_returns_empty():
    assert propose_candidates("sig", known_actions=None) == []
    assert propose_candidates("sig", known_actions=[]) == []


def test_blank_signature_returns_empty():
    assert propose_candidates("", known_actions=["1"]) == []


def test_unexplored_ranks_above_prior():
    ranked = propose_candidates(
        "sig",
        known_actions=["1", "2", "3"],
        prior_rules=[{"tried_action": "1", "confidence": 0.9}],
    )
    assert [c["action"] for c in ranked] == ["2", "3", "1"]
    assert ranked[0]["reason"] == "unexplored"
    assert ranked[-1]["reason"] == "revisit prior rule"


def test_blocked_actions_excluded():
    ranked = propose_candidates(
        "sig",
        known_actions=["1", "A", "2"],
        blocked_actions={"A"},
    )
    assert [c["action"] for c in ranked] == ["1", "2"]
