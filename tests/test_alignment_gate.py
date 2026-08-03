"""PWO-113 — alignment gate refuses PvP-aggression rule proposals.

DoD pins (hub GO plan B):
1. write_draft refuses PvP aggression — no draft file written
2. promote_draft refuses a hand-edited PvP draft
3. bridge_to_kernel_document refuses PvP screen + attack macro
4. corp-toll negative control still allowed
"""

from __future__ import annotations

import json

import pytest

from tw2002_aiclient.alignment_gate import AlignmentRefusal, refuse_pvp_aggression_rule
from tw2002_aiclient.cockpit.draft_approve import DraftBridgeError, bridge_to_kernel_document
from tw2002_aiclient.rules.store import drafts_dir, resolve_roots
from tw2002_aiclient.rules.writer import RuleWriteError, promote_draft, write_draft


def test_refuse_attack_player_do():
    with pytest.raises(AlignmentRefusal, match="initiates PvP"):
        refuse_pvp_aggression_rule(
            {
                "rule_id": "bad",
                "screen_match": "command_prompt",
                "do": "attack-player",
                "priority": 1,
            }
        )


def test_refuse_player_attack_screen():
    with pytest.raises(AlignmentRefusal, match="PvP|player-combat"):
        refuse_pvp_aggression_rule(
            {
                "rule_id": "bad",
                "screen_match": "player_attack",
                "do": "y",
                "priority": 1,
            }
        )


def test_corp_toll_negative_control_allowed():
    refuse_pvp_aggression_rule(
        {
            "rule_id": "corp-toll-a",
            "screen_match": "fighter_toll",
            "do": "a",
            "priority": 5,
        }
    )


def test_write_draft_refuses_pvp_and_writes_nothing(tmp_path):
    with pytest.raises(RuleWriteError, match="alignment refuses"):
        write_draft(
            {
                "rule_id": "pvp-y",
                "screen_match": "player_attack",
                "do": "y",
                "priority": 10,
            },
            state_dir=tmp_path,
        )
    assert list(drafts_dir(tmp_path).glob("*.json")) == []


def test_promote_draft_refuses_hand_edited_pvp(tmp_path):
    """Bypass write_draft by planting a draft JSON, then promote must refuse."""
    blessed, drafts = resolve_roots(state_dir=tmp_path)
    drafts.mkdir(parents=True, exist_ok=True)
    planted = {
        "rule_id": "hand-pvp",
        "screen_match": "pvp_combat",
        "do": "attack",
        "priority": 3,
        "scope": "one-shot",
        "approved": False,
        "guards": [],
    }
    (drafts / "hand-pvp.json").write_text(json.dumps(planted) + "\n", encoding="utf-8")

    with pytest.raises(RuleWriteError, match="alignment refuses"):
        promote_draft("hand-pvp", state_dir=tmp_path)

    assert list(blessed.glob("*.json")) == []
    # Draft remains (promote refused before blessing) — still not live.
    assert (drafts / "hand-pvp.json").is_file()


def test_bridge_refuses_pvp_aggression():
    stub = {"when": {"screen": "player_attack", "guards": []}, "source": "analyze"}
    with pytest.raises(DraftBridgeError, match="alignment refuses"):
        bridge_to_kernel_document(
            stub,
            rule_id="pvp-bridge",
            do="attack-player",
            priority=1,
            scope="one-shot",
        )


def test_write_draft_allows_corp_toll(tmp_path):
    path = write_draft(
        {
            "rule_id": "corp-toll-a",
            "screen_match": "fighter_toll",
            "do": "a",
            "priority": 5,
        },
        state_dir=tmp_path,
    )
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["approved"] is False
    assert on_disk["screen_match"] == "fighter_toll"
    assert on_disk["do"] == "a"
