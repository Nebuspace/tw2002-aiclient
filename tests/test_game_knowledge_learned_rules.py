"""Learned-rule store tests — offline, tmp_path only."""

import importlib.util
import sys
import types

import pytest

if importlib.util.find_spec("twclient.world_identity") is None:
    _stub = types.ModuleType("twclient.world_identity")

    def _stub_world_id(host, game_letter, handle):
        raw = f"{host}_{game_letter}_{handle}".lower()
        return "".join(c if c.isalnum() or c in "-_" else "_" for c in raw)

    _stub.world_id = _stub_world_id
    sys.modules["twclient.world_identity"] = _stub

from twclient import game_knowledge  # noqa: E402


def test_new_knowledge_includes_learned_rules():
    data = game_knowledge._new_knowledge()
    assert data["learned_rules"] == {}
    assert data["version"] == game_knowledge.SCHEMA_VERSION


def test_upsert_learned_rule_round_trip(tmp_path):
    path = tmp_path / "game_knowledge.json"
    rule = game_knowledge.upsert_learned_rule(
        path, "sig-a", "1", "sig-b", 0.4
    )
    assert rule["state_signature"] == "sig-a"
    assert rule["tried_action"] == "1"
    assert rule["observed_transition"] == "sig-b"
    assert rule["confidence"] == 0.4
    assert "first_seen_ts" in rule and "last_seen_ts" in rule

    got = game_knowledge.get_learned_rule(path, "sig-a", "1")
    assert got == rule


def test_upsert_learned_rule_idempotent_updates(tmp_path):
    path = tmp_path / "game_knowledge.json"
    first = game_knowledge.upsert_learned_rule(path, "s", "2", "t1", 0.2)
    second = game_knowledge.upsert_learned_rule(path, "s", "2", "t2", 0.9)
    assert second["first_seen_ts"] == first["first_seen_ts"]
    assert second["observed_transition"] == "t2"
    assert second["confidence"] == 0.9
    assert len(game_knowledge.list_learned_rules(path)) == 1


def test_list_learned_rules_for_state(tmp_path):
    path = tmp_path / "game_knowledge.json"
    game_knowledge.upsert_learned_rule(path, "here", "1", "a", 0.1)
    game_knowledge.upsert_learned_rule(path, "here", "2", "b", 0.2)
    game_knowledge.upsert_learned_rule(path, "elsewhere", "1", "c", 0.3)
    here = game_knowledge.list_learned_rules_for_state(path, "here")
    assert {r["tried_action"] for r in here} == {"1", "2"}


@pytest.mark.parametrize(
    "kwargs",
    [
        {"state_signature": "", "tried_action": "1", "observed_transition": "x", "confidence": 0.5},
        {"state_signature": "s", "tried_action": "", "observed_transition": "x", "confidence": 0.5},
        {"state_signature": "s", "tried_action": "1", "observed_transition": "", "confidence": 0.5},
        {"state_signature": "s", "tried_action": "1", "observed_transition": "x", "confidence": 1.5},
        {"state_signature": "s", "tried_action": "1", "observed_transition": "x", "confidence": -0.1},
    ],
)
def test_upsert_learned_rule_validation(tmp_path, kwargs):
    path = tmp_path / "game_knowledge.json"
    with pytest.raises(game_knowledge.GameKnowledgeError):
        game_knowledge.upsert_learned_rule(path, **kwargs)


def test_load_defaults_learned_rules_on_legacy_file(tmp_path):
    path = tmp_path / "game_knowledge.json"
    legacy = {
        "version": 1,
        "menu_map": {"nodes": {}, "edges": []},
        "game_data": {t: {} for t in game_knowledge.GAME_DATA_TABLES},
    }
    game_knowledge.save_knowledge(legacy, path)
    loaded = game_knowledge.load_knowledge(path)
    assert loaded["learned_rules"] == {}
