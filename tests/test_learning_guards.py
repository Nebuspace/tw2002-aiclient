"""Paladin / combat-authority pure guards."""

from twclient.learning.guards import blocked_actions_for_context, is_combat_action


def test_is_combat_action():
    assert is_combat_action("A") is True
    assert is_combat_action("attack") is True
    assert is_combat_action("1") is False


def test_blocked_until_human_confirms():
    blocked = blocked_actions_for_context(authority="ai", human_combat_confirmed=False)
    assert "A" in blocked
    assert blocked_actions_for_context(human_combat_confirmed=True) == frozenset()
