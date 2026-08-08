"""WO-BUILD-COVERAGE-METRICS-TEACHING-PROVENANCE-AXIS — origin + third axis."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tw2002_aiclient.cockpit.covermeter import compose_coverage_meter, coverage_percentages
from tw2002_aiclient.coverage_metrics import (
    ORIGIN_BUCKET_UNKNOWN,
    teaching_provenance_counts,
    teaching_provenance_share,
)
from tw2002_aiclient.rule_engine import (
    ORIGIN_AI_APPROVED,
    ORIGIN_HUMAN,
    Rule,
    RuleDocumentError,
    rule_from_dict,
    rule_to_dict,
)
from tw2002_aiclient.rules.store import read_rule_store
from tw2002_aiclient.rules.writer import promote_draft, write_draft


def _base(**extra):
    doc = {
        "rule_id": "dock-when-idle",
        "screen_match": "main_command",
        "do": "dock",
        "priority": 10,
        "approved": True,
    }
    doc.update(extra)
    return doc


def test_origin_persists_and_reloads(tmp_path: Path) -> None:
    write_draft(
        {**_base(approved=False), "origin": ORIGIN_AI_APPROVED},
        state_dir=tmp_path,
    )
    promote_draft("dock-when-idle", state_dir=tmp_path)
    on_disk = json.loads((tmp_path / "rules" / "dock-when-idle.json").read_text())
    assert on_disk["origin"] == ORIGIN_AI_APPROVED
    report = read_rule_store(state_dir=tmp_path)
    assert report["rules"][0].origin == ORIGIN_AI_APPROVED


def test_legacy_document_without_origin_loads_as_unknown_bucket(tmp_path: Path) -> None:
    """Pre-field store must load unchanged — never invent human/ai-approved."""
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    legacy = _base()  # no origin key
    (rules_dir / "dock-when-idle.json").write_text(json.dumps(legacy), encoding="utf-8")
    report = read_rule_store(state_dir=tmp_path)
    rule = report["rules"][0]
    assert rule.origin is None
    assert "origin" not in rule_to_dict(rule)
    counts = teaching_provenance_counts(report["rules"])
    assert counts == {
        ORIGIN_HUMAN: 0,
        ORIGIN_AI_APPROVED: 0,
        ORIGIN_BUCKET_UNKNOWN: 1,
        "total": 1,
    }


def test_invalid_origin_is_rejected() -> None:
    with pytest.raises(RuleDocumentError, match="origin"):
        rule_from_dict(_base(origin="trainer"))


def test_teaching_provenance_third_axis_counts_approved_only() -> None:
    rules = (
        Rule(
            rule_id="h",
            screen_match="main_command",
            do="dock",
            priority=1,
            approved=True,
            origin=ORIGIN_HUMAN,
        ),
        Rule(
            rule_id="a",
            screen_match="main_command",
            do="dock",
            priority=1,
            approved=True,
            origin=ORIGIN_AI_APPROVED,
        ),
        Rule(
            rule_id="a2",
            screen_match="main_command",
            do="dock",
            priority=1,
            approved=True,
            origin=ORIGIN_AI_APPROVED,
        ),
        Rule(
            rule_id="legacy",
            screen_match="main_command",
            do="dock",
            priority=1,
            approved=True,
            origin=None,
        ),
        # draft — excluded from playable repertoire counts
        Rule(
            rule_id="draft",
            screen_match="main_command",
            do="dock",
            priority=99,
            approved=False,
            origin=ORIGIN_AI_APPROVED,
        ),
    )
    counts = teaching_provenance_counts(rules)
    assert counts == {
        ORIGIN_HUMAN: 1,
        ORIGIN_AI_APPROVED: 2,
        ORIGIN_BUCKET_UNKNOWN: 1,
        "total": 4,
    }
    assert teaching_provenance_share(counts) == 0.5


def test_live_app_human_axis_unchanged() -> None:
    """Pin: teaching provenance must not alter covermeter share math."""
    assert coverage_percentages(app=3, human=1) == (75, 25)
    assert compose_coverage_meter(app=3, human=1) == "COV 75% · App 3 · Hum 1"
    assert compose_coverage_meter(app=0, human=0) == "COV ? · App 0 · Hum 0"
    assert compose_coverage_meter(app=None, human=None) == "COV ?"
