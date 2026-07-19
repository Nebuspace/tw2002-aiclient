"""TW-13 coaching KB loader tests."""

from pathlib import Path

import pytest

from twclient.coach_kb import default_kb_paths, load_coach_kb, validate_strategy

ROOT = Path(__file__).resolve().parent.parent
STRATEGIES, PARAMS = default_kb_paths(ROOT / "data" / "coach")


def test_default_kb_loads_with_triggers():
    kb = load_coach_kb(STRATEGIES, PARAMS)
    assert kb.version == 1
    assert len(kb.strategies) >= 8
    assert kb.by_trigger("docked_at_port")
    assert kb.by_trigger("toll_or_gate")
    ids = {s.id for s in kb.strategies}
    assert "pair_trade_loop" in ids
    assert "longest_profit_chain" in ids


def test_params_are_mostly_unverified_hypotheses():
    kb = load_coach_kb(STRATEGIES, PARAMS)
    assert kb.param("port_regrowth_pct_per_day") is not None
    unverified = [p for p in kb.params if not p.verified_vs_live]
    assert len(unverified) >= 4  # §16 flag: do not pretend these are proven


def test_okf_refs_are_bundle_relative():
    kb = load_coach_kb(STRATEGIES, PARAMS)
    for s in kb.strategies:
        assert s.okf_refs, s.id
        for ref in s.okf_refs:
            assert ref.startswith("/"), ref


def test_reject_incomplete_strategy():
    with pytest.raises(ValueError, match="missing fields"):
        validate_strategy({"id": "x", "title": "t"})
